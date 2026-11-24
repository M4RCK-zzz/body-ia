# Fase 9 — Producción, QA y mantenimiento (plan técnico)

**Estado:** propuesta, pendiente de confirmación. **No se ha escrito código de Fase 9.**

> Regla rectora: la Fase 9 no añade producto nuevo. Endurece lo que ya existe, hace
> observable y recuperable lo que ya funciona, y deja por escrito cómo se opera. Ningún
> cambio puede debilitar las garantías de las fases 1–8: `DataKind` separado, mediciones
> inmutables, consentimiento con auditoría, `admin` sin acceso implícito, avisos no
> clínicos permanentes y simulación siempre hipotética.

---

## 0. Estado de partida (verificado en el repo, no supuesto)

| Área | Hoy | Consecuencia |
|---|---|---|
| Contenedores | Solo `docker-compose.yml` con **PostgreSQL 16.6** (+ pgadmin opcional). Sin `Dockerfile`. | No hay imagen reproducible de API ni de frontend. |
| Entornos | `ENVIRONMENT ∈ {local, staging, production}` existe en `Settings`, pero solo se usa en `/api/health`. | El valor no cambia comportamiento: nada se endurece en `production`. |
| CORS | `allow_origins` explícito, pero `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True`. | Superficie innecesaria; imposible razonar qué métodos expone el borde. |
| Cabeceras de seguridad | Solo `X-Content-Type-Options: nosniff` en las descargas (`media`, `reports`). Sin HSTS, CSP, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`. | El frontend no tiene defensa de borde frente a clickjacking/inline script. |
| OpenAPI | `/api/docs`, `/api/redoc` y `/api/openapi.json` siempre montados; 43 rutas / 53 operaciones. | En producción se publica el mapa completo de la API. |
| Rate limiting | Ninguno. El bloqueo de login (`LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCK_MINUTES`) es por **cuenta**, no por IP. | Fuerza bruta distribuida y abuso de endpoints costosos sin freno. |
| Trazabilidad de petición | `register_request_id_middleware` genera `X-Request-ID` y lo devuelve, pero **no** entra al log ni a la auditoría. | Un incidente no se puede correlacionar entre log y `audit_events`. |
| Logs | `logging.basicConfig` con formato de texto plano a stderr. | Ilegible para agregación; sin campos. |
| Healthchecks | `GET /api/health` comprueba **solo** la BD. No hay readiness, ni estado de storage, ni señal de workers vivos. | Compose no puede decidir si la API puede recibir tráfico ni si un worker murió. |
| Backups | No hay script ni procedimiento. Datos en `bodyvision_pgdata` + storage privado `UPLOAD_DIR`. | Pérdida total ante fallo de volumen; sin RPO/RTO definidos. |
| Retención | `MEDIA_RETENTION_DAYS` se calcula y **se guarda** en `retention_until`, pero nada purga. Reportes y simulaciones tampoco. | Promesa de retención documentada sin implementación. |
| Ads de `ruff` | 21 avisos en `alembic/env.py`, `0002`–`0006`, `routes/media.py:26` (B008), `routes/pose.py`, `security_errors.py`, `domain/metrics.py`, `main.py`, `models/identity.py`, `repositories/sqlalchemy_measurement_repository.py`, `services/measurement_service.py`. | `ruff check .` no es un gate honesto de CI. |
| Tests | `335 passed` (327 funciones de test + parametrizaciones). Sin job de CI. | La verificación es manual y depende de la máquina del desarrollador. |
| Lockfiles frontend | Coexisten `package-lock.json` (npm) y `pnpm-lock.yaml` + `pnpm-workspace.yaml`. | Build no reproducible: dos árboles de dependencias posibles. |
| Documentación de cierre | `docs/QA_CHECKLIST.md` y `docs/SEGURIDAD_Y_PRIVACIDAD.md` están **vacíos** (0 bytes). | No hay evidencia de QA ni modelo de amenazas publicado. |

---

## 1. Alcance

### Incluye (9A–9D)

1. **9A — Despliegue e infraestructura**: imágenes Docker de API y frontend/Nginx, TLS y
   cabeceras de seguridad en el borde, Compose de producción, separación de entornos,
   secretos fuera del repo, política de migraciones controladas.
2. **9B — Seguridad y estabilidad**: auditoría anti-IDOR con tests dedicados, rate limiting,
   cabeceras de seguridad en la API, CORS estricto, limpieza de los 21 avisos de `ruff`.
3. **9C — Observabilidad y operación**: `correlation_id` en logs estructurados y en
   auditoría, healthchecks de API/BD/storage/workers, backup y restauración verificables,
   retención y purga.
4. **9D — Documentación y cierre**: `docs/QA_CHECKLIST.md`, `docs/SEGURIDAD_Y_PRIVACIDAD.md`,
   runbooks operativos, **ADR-010**, CI mínimo y criterios de cierre.

### No incluye (queda fuera del proyecto, o para una fase posterior explícita)

- Alta disponibilidad real: clúster PostgreSQL, réplicas de lectura, balanceo multi-nodo.
- Kubernetes, service mesh, autoscaling, Terraform.
- Observabilidad con Prometheus/Grafana/OpenTelemetry, APM o tracing distribuido.
- Redis, Celery u otra cola externa: se mantiene la cola PostgreSQL de fases 5/7/8.
- Nuevas funcionalidades de producto (nuevas métricas, nuevos reportes, malla 3D derivada).
- Firma de PDFs, cifrado en reposo a nivel de aplicación, KMS.
- Migración a cookies httpOnly + CSRF (ver **D7**; se decide, no se implementa a la ligera).

---

## 2. 9A — Despliegue y hardening

### 2.1 Imágenes

**`docker/backend.Dockerfile`** (multi-stage, base `python:3.13-slim` para alinear con la
verificación local en Python 3.13):

- Etapa `builder`: `pip install --prefix=/install -r requirements.txt` (con `--no-cache-dir`).
  `mediapipe` y `psycopg[binary]` instalan ruedas: se documenta el peso de la imagen del
  worker de pose y se separa **una imagen de worker de pose** con las librerías de sistema
  que `mediapipe`/`cv2` necesitan (`libgl1`, `libglib2.0-0`), frente a una imagen de API que
  no las necesita. Decisión **D2**.
- Etapa final: usuario sin privilegios (`app`, uid 10001), `PYTHONDONTWRITEBYTECODE=1`,
  `PYTHONUNBUFFERED=1`, `HEALTHCHECK` contra `/api/health/live`, `CMD` con
  `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}`.
- Sin código de migraciones automáticas en el arranque (ver **D3**).
- `.dockerignore` propio: excluye `.venv`, `storage`, `models`, `tests`, `__pycache__`.

**`docker/frontend.Dockerfile`**:

- Etapa `node:22-alpine` con **un único lockfile** (decisión **D12**): `npm ci` o `pnpm
  install --frozen-lockfile`, nunca los dos.
- Build `npm run build` → `dist/` copiado a `nginx:1.27-alpine`.
- Nginx sirve SPA (`try_files $uri /index.html`), con `gzip` y cache-control por tipo
  (assets con hash: `immutable`; `index.html`: `no-store`).

**`docker/nginx/`**: `nginx.conf` + `conf.d/bodyvision.conf` con:

- `listen 443 ssl http2` + `ssl_certificate`/`ssl_certificate_key` montados como secreto;
  `ssl_protocols TLSv1.2 TLSv1.3`; cifrados modernos; `ssl_session_cache`.
- `server` en `:80` que solo redirige a HTTPS (y expone `/healthz` interno de Nginx).
- **Proxy inverso a la API bajo el mismo origen** (`/api/` → `backend:8000`), de forma que
  el navegador no cruce orígenes en producción y `connect-src 'self'` sea viable en la CSP.
  El frontend seguirá usando URLs relativas cuando `VITE_API_URL` no esté definido (ver **D9**).
- Cabeceras de seguridad (ver §3.3), `client_max_body_size` alineado con `MAX_UPLOAD_MB`,
  `limit_req` por zona (login, subidas, descargas), timeouts y `proxy_buffering` para
  descargas autenticadas.

### 2.2 Compose de producción

`docker-compose.prod.yml` como **overlay** (no duplica el de desarrollo):

| Servicio | Notas |
|---|---|
| `db` | `postgres:16.6`, puerto **sin publicar** (solo red interna), `shared_buffers`/`max_connections` básicos, healthcheck `pg_isready`, volumen nombrado. |
| `migrate` | one-shot: `alembic upgrade head` + `alembic current`; `profiles: ["migrate"]`, `restart: "no"`. La API depende de que termine bien. |
| `backend` | imagen API, usuario no root, `ENVIRONMENT=production`, `depends_on: db (healthy)`, `healthcheck` `/api/health/ready`, replicas 1. |
| `worker-pose` | imagen worker de pose (con GL), `restart: unless-stopped`, sin puertos. |
| `worker-report` | imagen API reutilizada, `python -m app.workers.report_worker`. |
| `worker-simulation` | imagen API reutilizada, `python -m app.workers.simulation_worker`. |
| `frontend` | Nginx + `dist`, publica `80`/`443`, depende de `backend (healthy)`. |
| `backup` | perfil `ops`, one-shot programado por el host (cron/Task Scheduler) o `profiles: ["ops"]`. |

Sin `pgadmin` en producción (se deja solo en el perfil `tools` del compose de desarrollo).
`restart`, `logging` (`json-file` con `max-size`/`max-file`) y `read_only` donde aplique.

### 2.3 Separación de entornos

| Ajuste | `local` | `staging` | `production` |
|---|---|---|---|
| `ENVIRONMENT` | `local` | `staging` | `production` |
| `/api/docs`, `/api/redoc`, `/api/openapi.json` | activos | activos | **desactivados** |
| `DEBUG` | `false` (default) | `false` | `false` (forzado) |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | dominio de staging | dominio real, lista explícita |
| TLS | no | sí (certificado de staging) | sí (Let's Encrypt o corporativo) |
| Cabeceras estrictas (HSTS) | no | sí, `max-age` corto | sí, 1 año + `preload` |
| Rate limiting | activo, límites laxos | activo | activo |
| Backups | no | diarios, retención 7 d | diarios + semanales + mensuales |
| `ALLOW_REGISTRATION` | `true` | `false` | `false` (usuarios por invitación/admin) |
| Secretos | `.env` local | `.env.staging` fuera del repo | secreto montado, rotado |

Regla dura: **arrancar en `production` con un secreto de ejemplo, `DEBUG=true`, CORS `*` o
`ALLOW_REGISTRATION=true` debe fallar al iniciar**, no avisar por log. La validación vive en
`Settings` (ya existe para `JWT_SECRET`; se extiende a las demás condiciones).

### 2.4 Secretos

- Nada de valores reales en el repo. `.env.example` sigue siendo la plantilla **sin
  secretos**, con un bloque `# --- Producción ---` que indica qué es obligatorio.
- Producción: archivos leídos por Compose como `secrets:` (`POSTGRES_PASSWORD`,
  `JWT_SECRET`, `SSL_CERT`, `SSL_KEY`) o variables inyectadas por el orquestador; permisos
  `600`, propietario root. Se documenta la rotación de `JWT_SECRET` (invalida sesiones: es
  el mecanismo de revocación global disponible hoy) y de la contraseña de BD.
- `git-secrets`/`detect-secrets` **no** se añaden como dependencia; se documenta la
  comprobación manual y el gate de CI que falla si aparece `.env` versionado.

### 2.5 Migraciones controladas

- Alembic corre **siempre** desde un job dedicado (`migrate`), nunca desde el `CMD` de la API
  ni desde el worker. Si el job falla, el despliegue se aborta antes de arrancar la API.
- Verificación previa: `alembic check` (sin divergencia metadata/migraciones) en CI contra un
  PostgreSQL efímero; `alembic upgrade head` + `alembic downgrade base` en un job de ida y
  vuelta (hoy los `downgrade()` existen en las 8 revisiones, pero nunca se han ejecutado en
  pruebas automáticas).
- Convención: una migración por fase, `down_revision` explícito, sin `DROP` de datos salvo
  migración documentada. Rollback = `alembic downgrade -1` **o** restaurar el backup previo,
  según lo que diga el runbook.

---

## 3. 9B — Seguridad y estabilidad

### 3.1 Revisión anti-IDOR

Inventario de recursos con identificador y su control actual (a verificar endpoint a
endpoint, no por muestreo):

| Recurso | Ruta base | Control esperado |
|---|---|---|
| Expediente | `/api/profiles/{id}` | `AccessGuard` (`viewer+`), 404 si no hay acceso |
| Medición | `/api/profiles/{id}/measurements` | `AccessGuard` + `profile_id` en la ruta |
| Media | `/api/profiles/{id}/media`, `/api/media/{asset_id}` | `AccessGuard` vía `asset.profile_id` |
| Pose | `/api/profiles/{id}/pose-analyses`, `/api/pose-analyses/{id}` | `AccessGuard` vía `analysis.profile_id` |
| Reporte | `/api/reports/{id}` | `AccessGuard` vía `report.profile_id` |
| Simulación | `/api/simulations/{id}` | `AccessGuard` vía `simulation.profile_id` |
| Acceso/consentimiento | `/api/profiles/{id}/access`, `/consents` | `owner` para escritura |
| Admin | `/api/admin/*` | rol `admin`, sin acceso implícito a expedientes |

Entregable: **suite paramétrica anti-IDOR** (`tests/test_security_idor.py`) que, para cada
recurso, crea dos usuarios y dos expedientes y comprueba con un usuario **ajeno**:
`404` (no revela existencia) en lectura, `403`/`404` en escritura, y que **no** se filtra el
`profile_id` ni el contenido en el cuerpo del error. Además, test de que un `admin` sin
concesión recibe `404` en cada recurso.

### 3.2 Rate limiting

Implementación recomendada: **middleware propio** en `app/core/rate_limit.py` (token bucket
en memoria, ventana deslizante, clave `ip` o `ip+email`, respuesta `429` con
`Retry-After`), más `limit_req` en Nginx como segunda barrera. Sin Redis (**D5**).

| Endpoint | Límite propuesto | Clave |
|---|---|---|
| `POST /api/auth/login` | 5/min y 20/h | IP, y 10/15 min por email |
| `POST /api/auth/register` | 3/h | IP |
| `POST /api/profiles/{id}/media` | 30/h | usuario |
| `POST /api/profiles/{id}/pose-analyses` | 30/h | usuario |
| `POST /api/profiles/{id}/reports` | 20/h | usuario |
| `POST /api/profiles/{id}/simulations` y `/{id}/run` | 60/h | usuario |
| `GET /api/reports/{id}/content`, `/api/media/{id}/content` | 120/h | usuario |
| Resto de `/api/*` | 600/min | IP |

Los `429` se **auditan** (`RateLimitAction`/acción nueva) sin datos personales: solo ruta
normalizada, clave de limitación hasheada y ventana. Excepción explícita: `/api/health*`
nunca se limita (los healthchecks de infraestructura no deben caer).

### 3.3 Cabeceras de seguridad

Middleware `app/core/security_headers.py` + cabeceras en Nginx (defensa en dos capas):

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
  img-src 'self' blob: data:; connect-src 'self'; font-src 'self'; object-src 'none';
  frame-ancestors 'none'; base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

`style-src 'unsafe-inline'` se mantiene **solo** porque React aplica estilos inline en el
visor 3D; `script-src` nunca lleva `unsafe-inline` ni `unsafe-eval`. HSTS solo con TLS real
(por eso la cabecera depende de `ENVIRONMENT`). `/api/docs` se desactiva en producción.

### 3.4 CORS estricto

- `allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"]` explícito (nunca `*`).
- `allow_headers=["Authorization","Content-Type","X-Request-ID"]` explícito.
- `expose_headers=["X-Request-ID","Retry-After"]`.
- `allow_credentials=True` se conserva **solo** si el origen es una lista explícita; en
  `production` un `CORS_ORIGINS` con `*` impide arrancar.
- Test: preflight desde un origen no permitido no devuelve `Access-Control-Allow-Origin`.

### 3.5 Limpieza de `ruff` (21 avisos)

- 6 `I001` autofixables (`alembic/env.py`, `0002`–`0006`): ordenar imports **sin** tocar la
  lógica de las migraciones ya aplicadas.
- 10 `E501` (líneas > 100) en migraciones y en `app/**`: partir líneas, sin cambios de
  comportamiento.
- 1 `B008` en `routes/media.py:26` (`File(...)` en default): resolver con
  `Annotated[UploadFile, File(...)]` como el resto del repo.
- Objetivo: `ruff check .` → **0 avisos**, y `ruff format --check` evaluado en **D13**.
- Riesgo controlado: los ficheros de migración se tocan solo en formato; se re-ejecuta
  `alembic upgrade head` + `downgrade base` en CI para demostrarlo.

---

## 4. 9C — Observabilidad y operación

### 4.1 `correlation_id` en logs y auditoría

- `contextvars.ContextVar` con `request_id` (ya generado en `middleware.py`) + `user_id`
  cuando haya actor autenticado.
- `app/core/logging.py` pasa a **JSON por línea** (`{"ts","level","logger","msg","request_id",
  "user_id","route","status","duration_ms"}`) cuando `ENVIRONMENT != local`; en local se
  mantiene el formato legible.
- Filtro de logging que inyecta `request_id` en todos los registros, incluidos los de
  excepciones no controladas (hoy el 500 no correlaciona nada).
- `AuditRecorder` añade `request_id` al `detail` de los eventos nuevos (la tabla
  `audit_events` **no** cambia: `detail` es `jsonb`). Sin migración.
- Un test comprueba: dos peticiones concurrentes producen `request_id` distintos, el valor
  devuelto en la cabecera coincide con el del log y con el de `detail` del evento.

### 4.2 Healthchecks

| Endpoint | Qué comprueba | Uso |
|---|---|---|
| `GET /api/health/live` | proceso vivo (sin BD) | `HEALTHCHECK` de Docker, liveness |
| `GET /api/health` | compatibilidad con lo existente (BD) | clientes actuales |
| `GET /api/health/ready` | BD (`SELECT 1`), storage escribible/legible, migración al día (`alembic_version` == head) | readiness, `depends_on` |
| `GET /api/health/workers` | estado de los workers por heartbeat | operación y alerta |

`ready` devuelve `503` con detalle por componente cuando algo falla; nunca expone rutas,
credenciales ni versiones de dependencias a usuarios anónimos (si el endpoint queda público,
solo `status`/`componentes booleans`).

**Heartbeat de workers** (**D10**): migración `0009_worker_heartbeats` con
`(name PK, worker_version, started_at, last_seen_at, iterations, last_error_at, last_error)`.
Cada worker late al final de cada pasada; `health/workers` calcula `alive` si
`last_seen_at` < `WORKER_STALE_SECONDS` (default 120 s). Sin latidos, un worker caído es
invisible hasta que la cola crece.

### 4.3 Backup y restauración

`backend/scripts/backup.ps1` (Windows) + `docs/runbooks/backup-restore.md` (equivalente
`sh` documentado para el contenedor, sin añadir dependencias):

- `pg_dump -Fc --no-owner` a `backups/<UTC timestamp>/db.dump` + `pg_restore --list` como
  verificación de que el volcado es legible.
- Storage privado: `tar` del volumen de `UPLOAD_DIR` → `storage.tar` (los binarios de
  reportes y las imágenes viven aquí, **no** en PostgreSQL).
- `manifest.json`: versión de la app, revisión de Alembic, tamaño y **SHA-256 de cada
  artefacto**, tabla de conteos por tabla (para verificar la restauración).
- Retención: 7 diarios / 4 semanales / 12 mensuales; `-Keep` configurable.
- `backend/scripts/restore.ps1 -From <carpeta>`: restaura en una BD **nueva**, comprueba
  checksums, corre `alembic current`, y compara conteos con el manifiesto antes de conmutar.
  Nunca restaura encima de la BD en uso sin `-Force`.
- Ensayo obligatorio de restauración documentado como parte del cierre (**RPO 24 h /
  RTO 2 h**, **D11**).

### 4.4 Retención y purga (**D14**)

- `app/workers/retention.py` (`--once`), mismo patrón que los demás workers:
  - Media con `retention_until < now()` y estado no retenido por expediente activo → borra
    el binario del storage y marca el asset `deleted` (sin `DELETE` físico de la fila:
    conserva la traza).
  - Reportes `failed`/`generated` más antiguos que `REPORT_RETENTION_DAYS`.
  - Simulaciones `archived` más antiguas que `SIMULATION_RETENTION_DAYS`.
  - **Nunca** toca `measurements`, `pose_analyses`, `audit_events` ni `reports` vigentes.
- Config nueva: `REPORT_RETENTION_DAYS`, `SIMULATION_RETENTION_DAYS`, `RETENTION_DRY_RUN`.
- Todo borrado se audita (`media.purged`, `report.purged`, `simulation.purged`).

---

## 5. 9D — Documentación y cierre

### 5.1 `docs/QA_CHECKLIST.md` (hoy vacío)

Secciones, con casilla y comando/evidencia por ítem:

1. **Entorno y build**: Python 3.13, Node 22, `pip install -r requirements-dev.txt`,
   `npm ci`, versiones registradas.
2. **Migraciones**: `upgrade head`, `downgrade base`, `upgrade head` (ida y vuelta),
   `alembic check`, triggers y CHECKs verificados en PostgreSQL real.
3. **Backend**: `pytest -q` (335 + nuevos), `ruff check .` = 0 avisos.
4. **Frontend**: `npm run lint`, `npm run build`, `tsc -b`.
5. **Seguridad**: suite anti-IDOR, `429` en login, cabeceras presentes, CORS de origen ajeno
   rechazado, `/api/docs` cerrado en producción, `JWT_SECRET` débil rechazado al arrancar.
6. **Datos**: mediciones inmutables, cortesía `DataKind` (pose ≠ medición ≠ simulación),
   simulación no escribe mediciones, reporte de pose sin filas de mediciones.
7. **Observabilidad**: `X-Request-ID` en cabecera = log = `audit_events.detail`.
8. **Operación**: `/health/live`, `/health/ready` (200 y 503 inducido), `/health/workers`,
   backup, restauración en BD limpia con conteos iguales.
9. **Regresión manual por fase** (2 → 8): una línea por flujo crítico de cada fase.
10. **Cierre**: resultados fechados, firmas de quien verifica, desviaciones abiertas.

### 5.2 `docs/SEGURIDAD_Y_PRIVACIDAD.md` (hoy vacío)

- **Modelo de amenazas** (STRIDE abreviado) sobre los activos: credenciales, mediciones,
  imágenes de captura, estimaciones de pose, reportes, simulaciones, auditoría.
- **Mapa de datos**: qué se guarda, dónde (PostgreSQL vs storage privado), por qué,
  cuánto tiempo, quién accede y con qué base legal/consentimiento.
- **Controles existentes** con su referencia de código y test: JWT corto, argon2, bloqueo de
  login, RBAC + acceso por expediente, `admin` sin acceso implícito, auditoría append-only
  con triggers, storage privado con claves UUID, EXIF eliminado, límites de tamaño/píxeles.
- **Controles nuevos de Fase 9**: rate limiting, cabeceras, CSP, CORS estricto, TLS,
  secretos, backups cifrados en destino, retención activa.
- **Riesgos aceptados y residuales**: XSS mitigado por CSP (token en `sessionStorage`),
  rate limit en memoria por réplica, sin cifrado de aplicación en reposo, sin 2FA,
  sin revocación individual de tokens (ver **D7**).
- **Derechos del usuario**: acceso, corrección (mediciones versionadas), eliminación
  (archivado lógico + purga por retención), retirada de consentimiento con efecto
  inmediato en escrituras.

### 5.3 Runbooks (`docs/runbooks/`)

`deploy.md`, `rollback.md`, `backup-restore.md`, `incident-response.md`, `key-rotation.md`,
`worker-down.md`, `disk-full.md`, `database-unavailable.md`. Cada uno con: síntoma, impacto,
diagnóstico (comandos exactos), mitigación, verificación y post-mortem.

### 5.4 ADR-010

`ADR-010 · Producción, despliegue endurecido y operación` en `docs/ARQUITECTURA.md`, con las
decisiones de esta fase una por una, sus alternativas descartadas y consecuencias.

### 5.5 CI mínimo (**D15**)

GitHub Actions con dos jobs: `backend` (PostgreSQL 16 como servicio, `alembic upgrade head`,
`pytest -q`, `ruff check .`) y `frontend` (`npm ci`, `npm run lint`, `npm run build`).
Sin despliegue automático: el despliegue sigue siendo manual y documentado.

---

## 6. Orden de ejecución y entregables

| Sub-fase | Contenido | Entregables | Verificación |
|---|---|---|---|
| **9A** | Dockerfiles, Nginx+TLS, `docker-compose.prod.yml`, `Settings` por entorno, secretos, job `migrate` | `docker/**`, `docker-compose.prod.yml`, `.env.example` ampliado, `.dockerignore` | `docker compose -f docker-compose.prod.yml config`; arranque local con TLS autofirmado; `/health/ready` 200 |
| **9B** | Anti-IDOR, rate limit, cabeceras, CORS, `ruff` 0 | `app/core/rate_limit.py`, `security_headers.py`, `tests/test_security_idor.py`, `tests/test_rate_limit.py`, `tests/test_security_headers.py` | pytest + `ruff check .` = 0 |
| **9C** | Logs JSON con request-id, healthchecks, heartbeat, backup/restore, retención | `app/core/logging.py`, `rate_limit`/health routers, `0009_worker_heartbeats`, `scripts/backup.ps1`, `scripts/restore.ps1`, `workers/retention.py` | backup → restore en BD nueva → conteos iguales; test de correlación |
| **9D** | QA checklist, seguridad y privacidad, runbooks, ADR-010, CI | `docs/QA_CHECKLIST.md`, `docs/SEGURIDAD_Y_PRIVACIDAD.md`, `docs/runbooks/*`, ADR-010, `.github/workflows/ci.yml` | checklist completo firmado; CI en verde |

Cuatro commits (uno por sub-fase) más un commit final de cierre, siguiendo el patrón de
fases 4–8.

---

## 7. Decisiones a confirmar

| # | Decisión | Recomendación | Alternativas |
|---|---|---|---|
| **D1** | Borde de producción | **Nginx + TLS en contenedor** sirviendo SPA y **proxy `/api` bajo el mismo origen** | API y frontend en dominios separados (CORS real); proxy externo del host |
| **D2** | Imágenes | **Dos imágenes**: `api` (sin GL) y `worker-pose` (con `libgl1`); report/simulation reutilizan `api` | Una sola imagen con GL para todo (más simple, más pesada y más superficie) |
| **D3** | Migraciones | **Job one-shot `migrate`** antes de arrancar API; nada de `alembic` en el `CMD` | Migrar al arrancar la API (riesgo de carrera entre réplicas) |
| **D4** | Secretos | **Archivos montados (`secrets:`) / variables del orquestador**, plantilla sin secretos en el repo; rotación documentada | Vault/KMS fuera del alcance de esta fase |
| **D5** | Rate limiting | **Middleware propio en memoria + `limit_req` en Nginx**; límites de §3.2 | `slowapi`; Redis (rompe la simplicidad de la cola PostgreSQL) |
| **D6** | Alcance del rate limit | **Login, registro, subidas, worker-triggering y descargas**, más techo global | Solo login |
| **D7** | Sesión del navegador | **Mantener Bearer en `sessionStorage`** + CSP estricta y documentar el riesgo residual | Cookies httpOnly + CSRF (más seguro, toca frontend, backend y tests → 9B amplio) |
| **D8** | Docs de API en producción | **Desactivados** (`ENABLE_API_DOCS=false`); activos en staging | Publicar `/api/docs` con auth básica |
| **D9** | `VITE_API_URL` | **Vacío en producción** (URLs relativas, mismo origen); obligatorio en `local`/`staging` | Dominio de API separado |
| **D10** | Health y worker heartbeat | **`/health/live`, `/health/ready`, `/health/workers`** + migración `0009_worker_heartbeats` | Solo `/health` actual; detectar worker caído por antigüedad de la cola |
| **D11** | Objetivos de recuperación | **RPO 24 h / RTO 2 h**, backup diario + ensayo de restauración obligatorio | RPO 1 h con archivado WAL (más piezas: `pg_basebackup`, PITR) |
| **D12** | Lockfile frontend | **Eliminar `pnpm-workspace.yaml` + `pnpm-lock.yaml`** y quedarse con **npm** (`package-lock.json`, el que usa la verificación local) | Adoptar pnpm (cambia todos los comandos y la CI) |
| **D13** | `ruff` | **0 avisos** (`check`) y **sin** adoptar `ruff format` en esta fase | Adoptar `ruff format` también (diff masivo en migraciones) |
| **D14** | Retención y purga | **Sí**: worker `retention --once` con `RETENTION_DRY_RUN=true` por defecto y auditoría de cada borrado | Dejar `retention_until` sin efecto (promesa incumplida) |
| **D15** | CI | **GitHub Actions** con backend (PostgreSQL servicio) y frontend, sin despliegue automático | Sin CI (verificación manual, como hoy) |
| **D16** | Cifrado de backups | **Cifrado en destino** (volumen/almacenamiento cifrado) documentado; sin `gpg` en el script | Envolver `pg_dump` con `gpg` simétrico y clave gestionada aparte |

Si no indicas lo contrario, aplico la columna de recomendaciones y lo documento en
**ADR-010**. Las decisiones **D7**, **D11** y **D12** son las que más cambian el coste: D7
toca frontend+backend+tests, D11 añade PITR, D12 rompe los comandos actuales de pnpm.

---

## 8. Riesgos y compromisos

- **Rate limit en memoria**: con más de una réplica de API el límite es por proceso. Se
  documenta como limitación aceptada (D5) y Nginx cubre el borde.
- **CSP y visor 3D**: `three`/`drei` pueden requerir ajustes (workers, blob URLs). Si el
  visor rompe con CSP estricta, se documenta la excepción mínima **antes** de relajarla.
- **Tocar migraciones antiguas para `ruff`**: riesgo de cambiar una migración ya aplicada.
  Mitigación: solo formato, revisión línea a línea y `upgrade`/`downgrade` en CI.
- **Heartbeat (0009)**: una tabla más; si el worker no late (p. ej. bloqueado en el modelo
  de pose), `health/workers` dirá "muerto" aunque esté trabajando. Se calibra el umbral.
- **Backups sin ensayo = backups falsos**: el cierre exige una restauración real verificada
  por conteos y checksums.
- **Sin 2FA ni revocación individual de tokens**: se declara como riesgo residual en
  `SEGURIDAD_Y_PRIVACIDAD.md`; la rotación de `JWT_SECRET` es la revocación global.
- **Purga**: un bug aquí borra datos. Mitigación: `DRY_RUN` por defecto, ventana amplia,
  auditoría por fichero y test que verifica que `measurements` y `audit_events` son
  intocables.

---

## 9. Criterios de cierre de la Fase 9

1. `alembic upgrade head` y `alembic downgrade base` limpios en PostgreSQL 16; `alembic check`
   sin divergencias.
2. `pytest -q` verde (335 + nuevos de seguridad, rate limit, health, correlación, retención).
3. `ruff check .` = **0 avisos** y `npm run lint` + `npm run build` verdes.
4. `docker compose -f docker-compose.prod.yml up -d` levanta API, 3 workers, frontend y BD;
   `/health/ready` 200; `/api/docs` cerrado; cabeceras de seguridad presentes; HSTS con TLS.
5. Suite anti-IDOR verde en todos los recursos de §3.1, incluido `admin` sin acceso.
6. Rate limiting devuelve `429` con `Retry-After` y deja evento de auditoría; `/health*`
   nunca se limita.
7. `X-Request-ID` correlaciona cabecera, log JSON y `audit_events.detail`.
8. Backup ejecutado y **restaurado en una BD nueva** con conteos y checksums idénticos.
9. `docs/QA_CHECKLIST.md` completo y fechado, `docs/SEGURIDAD_Y_PRIVACIDAD.md` publicado,
   runbooks y **ADR-010** en `docs/ARQUITECTURA.md`, `README.md` y `docs/ROADMAP.md` con la
   Fase 9 cerrada.
10. Commit(s) + push a `arena/59596023-body-ia`.

---

## 10. Lo que necesito de ti para arrancar

1. Confirmación de **D1–D16** (basta "aplica las recomendaciones", con las excepciones que
   quieras marcar).
2. Dominio real de producción y si el TLS será **Let's Encrypt** o certificado corporativo.
3. Si existe ya un servidor/VM concreto (Linux + Docker) o el despliegue debe quedar
   documentado como plantilla reproducible sin destino final.
4. Si quieres que la Fase 9 incluya CI en GitHub Actions (D15) o se quede fuera para no
   tocar el remoto.
