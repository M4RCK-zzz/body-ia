# Checklist de QA — cierre de proyecto (Fase 9)

> **Cómo se usa.** Cada ítem tiene una casilla, el comando o la acción concreta que lo
> verifica y la evidencia esperada. Un ítem marcado sin evidencia es un ítem que no se ha
> comprobado. La columna de resultado se rellena en la ejecución de cierre y se fecha.

| Campo | Valor |
|---|---|
| Versión verificada | `0.1.0` |
| Fecha de la ejecución | _pendiente de ejecutar en Windows + PostgreSQL_ |
| Verificado por | _nombre_ |
| Entorno | Windows + PostgreSQL 16.6 + Python 3.13 + Node 22 |

---

## 1. Entorno y build

- [ ] **1.1** Python 3.13 disponible y usado por el `.venv` del backend.
  - `python --version` → `Python 3.13.x`
- [ ] **1.2** Dependencias del backend instaladas sin conflictos.
  - `cd backend && .venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  - Evidencia: sin errores de resolución; `pip check` sin conflictos.
- [ ] **1.3** Node 22 y **un único lockfile** (npm, decisión D12).
  - `node --version` → `v22.x`
  - `ls frontend\pnpm-lock.yaml frontend\pnpm-workspace.yaml` → **no existen**
  - `cd frontend && npm ci` → instala desde `package-lock.json`.
- [ ] **1.4** `docker compose` disponible y con versión ≥ 2.20.

---

## 2. Migraciones (PostgreSQL real, no mocks)

- [ ] **2.1** Base limpia y migración completa.
  - `cd backend && .venv\Scripts\python.exe -m alembic upgrade head`
  - Evidencia: aplica `0001` → `0009` sin error.
- [ ] **2.2** Ida y vuelta completa (los `downgrade()` siempre existieron; aquí se prueban).
  - `alembic downgrade base` → `alembic upgrade head` → sin error.
  - Evidencia: la base queda con las 9 revisiones y los datos de prueba intactos.
- [ ] **2.3** Sin divergencia entre modelos y migraciones.
  - `alembic check` → `No new upgrade operations detected.`
- [ ] **2.4** Revisión aplicada.
  - `alembic current` → `0009 (head)`
- [ ] **2.5** Triggers y CHECKs presentes.
  - `psql -c "\d+ simulations"` → `trg_simulations_protect`, `trg_simulations_no_delete`.
  - `psql -c "\d+ audit_events"` → trigger append-only.
  - `psql -c "\d+ worker_heartbeats"` → `trg_worker_heartbeats_monotonic` + índice `last_seen_at`.
- [ ] **2.6** El trigger del heartbeat funciona.
  - `UPDATE worker_heartbeats SET last_seen_at = now() - interval '1 day' WHERE name='report';`
  - Evidencia: el valor **no retrocede**.

---

## 3. Backend

- [ ] **3.1** Suite completa en verde.
  - `cd backend && .venv\Scripts\python.exe -m pytest -q`
  - Evidencia esperada: **418+ passed**, 0 failed (el número sube con cada suite nueva;
    lo importante es 0 failed). Medición de cierre: **418 passed** (incluye 8 de
    `test_deployment_assets.py`).
- [ ] **3.2** `ruff` sin ningún aviso (gate de CI, decisión D13).
  - `.venv\Scripts\ruff.exe check .` → `All checks passed!`
- [ ] **3.3** Composición de producción validada sin Docker.
  - `python backend\scripts\validate_compose.py --env .env.prod` → `✓ composición válida`

---

## 4. Frontend

- [ ] **4.1** Lint limpio. `cd frontend && npm run lint`
- [ ] **4.2** Typecheck + build de producción. `npm run build`
- [ ] **4.3** Build con URL relativa (D9): el bundle **no** contiene `127.0.0.1`.
  - `$env:VITE_API_URL=""; npx vite build --outDir dist-prod`
  - `Select-String -Path dist-prod\assets\index-*.js -Pattern "127.0.0.1:8000"` → sin resultados.

---

## 5. Seguridad

- [ ] **5.1** Anti-IDOR en todos los recursos.
  - `pytest tests/test_security_idor.py -q` → 35 passed
  - Cubre: mediciones, series, analítica, media, pose, reportes, simulaciones, accesos,
    consentimientos y listados globales, con usuario ajeno y con `admin` sin concesión.
- [ ] **5.2** Rate limiting por endpoint.
  - `pytest tests/test_rate_limit.py -q` → 7 passed
  - Manual: 6 intentos de login seguidos → el 6.º responde **429** con `Retry-After`.
- [ ] **5.3** `/api/health*` nunca se limita.
  - Manual: 20 peticiones seguidas a `/api/health/live` → todas 200.
- [ ] **5.4** Cabeceras de seguridad presentes.
  - `curl -I https://$DOMAIN/` → `Content-Security-Policy`, `Strict-Transport-Security`,
    `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`.
  - `curl -I https://$DOMAIN/api/health/live` → las mismas cabeceras.
- [ ] **5.5** La CSP no rompe el visor 3D.
  - Abrir `/viewer`, cargar un modelo con Draco → **consola sin errores de CSP**.
  - Verificar en la política: `script-src 'self' 'wasm-unsafe-eval'`, `worker-src 'self' blob:`,
    `img-src 'self' blob: data:`.
- [ ] **5.6** CORS estricto: origen ajeno rechazado.
  - `curl -H "Origin: https://evil.example" -I https://$DOMAIN/api/health/live`
  - Evidencia: **sin** `Access-Control-Allow-Origin`.
- [ ] **5.7** Documentación de API cerrada en producción.
  - `curl -o /dev/null -w "%{http_code}" https://$DOMAIN/api/docs` → **404**
- [ ] **5.8** Producción no arranca con configuración insegura.
  - `$env:ENVIRONMENT="production"; $env:DEBUG="true"` → la API **falla al iniciar**.
  - Idem con `CORS_ORIGINS=*`, con `http://` y con `ENABLE_API_DOCS=true`.
- [ ] **5.9** Descargas siguen siendo privadas.
  - `curl -o /dev/null -w "%{http_code}" https://$DOMAIN/api/reports/<id>/content` sin token → **401**
  - Con token: `Cache-Control: private, no-store` y `X-Content-Type-Options: nosniff`.

---

## 6. Integridad de datos (regresión de fases 2–8)

- [ ] **6.1** Mediciones inmutables y versionadas: corregir una medición crea una nueva fila
  con `supersedes_id`; la original no cambia. (`pytest tests/test_measurement_service.py`)
- [ ] **6.2** Sin mezcla de `DataKind`: un reporte de pose no contiene filas de mediciones
  y `/api/reports` rechaza `kind=simulation_pdf` (422).
- [ ] **6.3** La simulación no contamina mediciones: huella SHA-256 de `measurements`
  idéntica antes/después de crear y ejecutar escenarios.
  (`pytest tests/test_simulation_api.py tests/test_simulation_service.py`)
- [ ] **6.4** Aislamiento del visor 3D: no superpone datos personales ni simulaciones.
- [ ] **6.5** `admin` no tiene acceso implícito a expedientes (404 uniforme).

---

## 7. Observabilidad

- [ ] **7.1** `X-Request-ID` correlaciona cabecera, log y auditoría.
  - `curl -H "X-Request-ID: qa-123456" https://$DOMAIN/api/health/live`
  - `docker compose ... logs backend | Select-String "qa-123456"` → aparece la línea JSON
    con `request_id`.
  - Crear un expediente con ese id y ver `audit_events.detail->>'request_id'`.
  - Evidencia automatizada: `pytest tests/test_logging_correlation.py -q` → 7 passed
- [ ] **7.2** Logs en JSON por línea.
  - `docker compose ... logs --tail 5 backend` → cada línea es un objeto JSON parseable.
- [ ] **7.3** `/api/health/live` responde 200 sin base de datos (parar `db`).
- [ ] **7.4** `/api/health/ready` responde **503** con el componente que falla.
  - Parar `db` → `database: false`. Con `UPLOAD_DIR` de solo lectura → `storage: false`.
- [ ] **7.5** `/api/health/workers` refleja los latidos.
  - Los 3 workers levantados → `status: ok`, `alive: true`.
  - Parar `worker-report` y esperar `WORKER_STALE_SECONDS` → `alive: false`.

---

## 8. Operación: backup y restauración

- [ ] **8.1** Backup ejecutado.
  - `powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -OutDir D:\backups`
  - Evidencia: `db.dump`, `storage.tar`, `manifest.json` con SHA-256 y conteos.
- [ ] **8.2** **Restauración verificada en una base nueva** (no es un backup hasta que se
  restaura).
  - `powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 -From D:\backups\<ts> -TargetDatabase bodyvision_qa`
  - Evidencia: `Conteos idénticos` y la revisión `0009` impresa.
- [ ] **8.3** Detección de corrupción: alterar un byte de `db.dump` → el restore **falla** por
  SHA-256 antes de tocar la base.
- [ ] **8.4** Equivalente Linux: `bash backend/scripts/backup.sh` y
  `bash backend/scripts/restore.sh <dir> --skip-storage` (`bash -n` sin errores de sintaxis).
- [ ] **8.5** Retención en **DRY RUN** por defecto.
  - `python -m app.workers.retention_worker --once` → informa `DRY RUN`, no borra nada.
  - Evidencia automatizada: `pytest tests/test_retention_worker.py -q` → 5 passed
- [ ] **8.6** Purga real audita cada borrado (`media.purged`, `report.purged`,
  `simulation.purged`) y **no toca** `measurements` ni `audit_events`.

---

## 9. Despliegue

- [ ] **9.1** Composición válida.
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` → sin errores.
- [ ] **9.2** Stack completo levantado.
  - `docker compose ... up -d` → `backend`, `worker-pose`, `worker-report`,
    `worker-simulation` y `frontend` en **healthy**.
- [ ] **9.3** Las migraciones corren **antes** que la API (`migrate` one-shot en `Exited (0)`).
- [ ] **9.4** Base **no publicada**: `docker compose ... ps` → `db` sin `0.0.0.0:5432`.
- [ ] **9.5** HTTPS funcionando.
  - `curl -I https://$DOMAIN/` → 200 con `Strict-Transport-Security`.
  - `curl -I http://$DOMAIN/` → **301** a `https://`.
- [ ] **9.6** Prueba local con certificado autofirmado.
  - `powershell -ExecutionPolicy Bypass -File scripts\tls-selfsigned.ps1 -Domain localhost`
    (o `bash scripts/tls-selfsigned.sh localhost`) → `docker/nginx/certs/{fullchain,privkey,chain}.pem`
    con la clave en `600` y `openssl x509 -noout -dates` mostrando la vigencia.
  - Alternativa sin generar nada antes: `ALLOW_SELFSIGNED=true` en `.env.prod` → Nginx lo
    crea al arrancar y el navegador avisa del certificado (esperado). Con certificado real
    montado, **no** se genera nada.
  - Evidencia: `docker/nginx/certs/` está en `.gitignore` (la clave privada nunca al repo).
- [ ] **9.7** SPA: recargar en una ruta profunda (`/simulations/<id>`) no da 404.
- [ ] **9.8** Assets con cache largo e `index.html` con `no-store`.

---

## 9bis. Panel de Administración

- [ ] **9bis.1** El enlace **Administración** aparece solo con rol `admin`.
  - Sesión con rol `admin` → el ítem del menú lleva a `/admin`.
  - Sesión estándar → el ítem **no** aparece en el menú.
- [ ] **9bis.2** La ruta `/admin` está protegida también escribiéndola a mano.
  - Usuario estándar → pantalla **Acceso denegado** (403), sin datos de administración.
  - Sin sesión → redirección a `/login`.
- [ ] **9bis.3** El backend impone la regla, no solo la UI.
  - `GET /api/admin/users` con token de usuario estándar → **403**; sin token → **401**.
- [ ] **9bis.4** Aviso permanente de alcance visible en la vista:
  "El rol de Administrador no da acceso a expedientes".
- [ ] **9bis.5** Pestaña **Usuarios**: listado paginado (nombre, correo, roles, estado, alta,
  último acceso), búsqueda por nombre/correo y filtros de rol y estado.
  - `pytest tests/test_admin_api.py -q` → 15 passed.
- [ ] **9bis.6** Activar/desactivar una cuenta funciona y queda auditado
  (`admin.user_activated` / `admin.user_deactivated`) sin recargar la página.
- [ ] **9bis.7** Gestión de roles: se abre el diálogo, se guardan y la fila se actualiza;
  el evento `admin.roles_changed` aparece en la pestaña de auditoría con `before`/`after`.
- [ ] **9bis.8** Un administrador **no** puede desactivarse ni quitarse `admin` a sí mismo:
  botón deshabilitado con el motivo; forzando la llamada, la API responde **422** con el
  mensaje y la UI lo muestra.
- [ ] **9bis.9** Pestaña **Auditoría**: tabla paginada con fecha, acción legible + código,
  actor resuelto (no UUID), recurso, resumen del `detail`, `request_id` y "Ver detalle" con
  el JSON. Filtros por acción, usuario y rango de fechas funcionando.
- [ ] **9bis.10** Pestaña **Workers**: los cuatro workers con último latido, estado (vivo,
  sin latido, vivo con error) e iteraciones; se refresca sola cada 30 s.
- [ ] **9bis.11** Accesibilidad: pestañas con `role=tab`/`aria-selected`, tablas con `caption`
  y `th scope`, foco visible y ningún par texto/fondo por debajo de AA.

## 9ter. Ajustes visuales de la revisión en vivo

- [ ] **9ter.1** Visor 3D: el panel de capas declara "Grasa / tejido adiposo · No incluida", con
  el motivo (el atlas trae 7 sistemas) y un desplegable "Cómo añadirla si se incorpora el .glb".
  - `ls frontend/public/models` → 7 `.glb`; `grep -c '"id"' public/models/manifest.json` → 7.
  - No existe ninguna malla sintética ni capa activable de grasa.
- [ ] **9ter.2** Dashboard → "Cómo leer los datos": las cuatro píldoras
  (MEDICIÓN OBSERVADA, ESTIMACIÓN, RECONSTRUCCIÓN APROXIMADA, ESCENARIO HIPOTÉTICO) miden su
  texto, no el ancho de la columna.
- [ ] **9ter.3** Análisis de pose: la píldora del estado (p. ej. "EN COLA") no se estira; los
  estados `needs_review` y `failed` se ven como etiqueta ámbar/roja, no como bloque de alerta.
- [ ] **9ter.4** Análisis de pose: el aviso dice "Los **esquemas corporales** generados por IA".
- [ ] **9ter.5** Simulador → Mis escenarios: las métricas aparecen como Cintura/Cadera/Peso…,
  nunca `waist`/`hip`/`weight`. Igual en el detalle (parámetros y comparador).
- [ ] **9ter.6** Reportes: cada fila muestra el código del expediente (BV-…) enlazado a
  `/expedientes/<id>`; el API devuelve `profile_display_code`.

## 10. Regresión manual por fase

- [ ] **10.1 (F2)** Crear expediente, registrar medición, ver que aparece en el listado.
- [ ] **10.2 (F2)** Corregir una medición: se crea una nueva y la anterior queda histórica.
- [ ] **10.3 (F3)** Login, logout y bloqueo tras 5 intentos fallidos.
- [ ] **10.4 (F4)** Subir una foto: EXIF sin coordenadas, límite de tamaño respetado.
- [ ] **10.5 (F5)** Análisis de pose: estado `En cola` → `Completado` con el worker arriba.
- [ ] **10.6 (F6)** Visor 3D: capas, wireframe, opacidad, vistas y atribución CC BY-SA.
- [ ] **10.7 (F7)** Analítica 7/30/90 días y reporte PDF/CSV descargable.
- [ ] **10.8 (F8)** Simulador: escenario, comparador OBSERVADO vs SIMULACIÓN, 422 al superar
  ±30 % y archivado sin tocar mediciones.
- [ ] **10.9** En todo el recorrido: el aviso "no es diagnóstico" y "ESCENARIO HIPOTÉTICO"
  están siempre visibles donde toca.

---

## 11. Cierre

| Resultado | Valor |
|---|---|
| Ítems verificados | _n_ / 60 |
| Fallos abiertos | _ninguno / lista_ |
| Desviaciones respecto al plan | _ninguna / lista_ |
| `pytest -q` | _passed_ |
| `ruff check .` | 0 avisos |
| `npm run lint` / `npm run build` | ok / ok |
| Firma | _nombre y fecha_ |

**Un cierre con ítems sin marcar no es un cierre.** Si algo no se puede verificar en esta
máquina (p. ej. TLS con un dominio real inexistente todavía), se marca como
_pendiente de entorno_ con el motivo y el runbook que lo cubre, nunca como verificado.
