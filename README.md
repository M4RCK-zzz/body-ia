# BODYVISION AI

Plataforma paramétrica de análisis, captura y simulación 3D de mediciones corporales **hipotéticas**.
**No emite diagnósticos médicos.** Toda salida de IA es una *estimación visual*; toda simulación es un
*escenario hipotético* separado de las mediciones reales.

## Requisitos
- Docker Desktop (PostgreSQL; en producción, el stack completo con `docker compose`)
- Python 3.13 (backend, `venv`; CI y despliegue usan 3.13)
- Node 22 + **npm** (único gestor: `package-lock.json`)

## 1. Base de datos
```powershell
Copy-Item .env.example .env        # edita POSTGRES_PASSWORD (solo letras y números)
docker compose up -d db
docker compose ps                  # debe mostrar "healthy"

## Fase 4 - Captura corporal (segura)

Las fotos son **material de referencia**, no mediciones. Flujo:

1. Entras en **Captura corporal** (icono del menú lateral).
2. Seleccionas un expediente y revisas la **guía de encuadre** (no se valida calidad; orientación).
3. **Subes** el archivo: JPEG / PNG / WebP, máx. 10 MB. El backend lo valida, transfolia (EXIF), borra metadatos/GPS y re-encodea. Los rechazos se persisten como registros con motivo.
4. Ves la lista de capturas del expediente con su estado (ready/rejected/deleted), dimensiones, tamaño, check de integridad y retención. Solo `ready` descargable vía endpoint autenticado.
5. Los bytes viven en `backend/storage/` (privado, chmod 600, clave aleatoria sin nombres), nunca en el navegador.

Subida y borrado requieren: acceso **owner/editor** + consentimiento `data_processing` vigente + expediente **active**. Los **viewers** solo leen.

### Verificación
```powershell
# Backend (desde backend/)
python -m pytest -q              # 444 tests (suites de fases 1-9 + admin)
ruff check .                     # 0 avisos (gate de CI)
# Frontend (desde frontend/)
npm run build && npm run lint
# Smoke (API local, arriba)
powershell -ExecutionPolicy Bypass -File backend\scripts\smoke_phase4.ps1
```
Nota: esta máquina (Linux sandbox) no tiene Postgres/Docker; la verificación E2E contra Postgres (`alembic upgrade head`, smoke real) se ejecuta en Windows con la BD arriba.

## Fase 5 - Análisis de pose (MediaPipe, worker asíncrono)

El análisis de pose es una **estimación visual** generada por un modelo de IA. **No es una medición**, no representa geometría ni diagnósticos y nunca debe mezclarse con las mediciones observadas. Todos los resultados se etiquetan `ESTIMACIÓN VISUAL` con versión del modelo.

### Flujo
1. Subes una captura (Fase 4) que queda en estado `ready`.
2. En la tarjeta de la captura (o en la sección "Análisis de pose" del expediente) pulsas **Analizar pose**.
3. El backend encola una tarea `pose_analyses` (idempotente: re-POST devuelve 200 con la tarea existente).
4. El worker la procesa (`queued → processing → completed | needs_review | failed`) y la persiste.
5. Ves el estado del análisis (refrescado cada 3 s hasta estado terminal) y abres `/analyses/:id`: esquema del cuerpo del análisis (ESTIMACIÓN), banderas de calidad, versión del modelo, autoría, tiempos y errores.

### Modelo: descarga y verificación (`backend/models/`)

El modelo oficial es `pose_landmarker_full.task` (MediaPipe Pose Landmarker, ~10 MB).

1. Descarga el modelo oficial:
   `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task`
   (fuente oficial: `mediapipe/tasks/python/vision` — el archivo está publicado por MediaPipe bajo Apache 2.0).
2. Guárdalo en `backend/models/pose_landmarker_full.task` (la carpeta `backend/models/` está gitignored).
3. Configura `POSE_MODEL_PATH=./models/pose_landmarker_full.task` en `backend/.env` (default ya lo apunta ahí).
4. Verifica que existan los campos de configuración (`POSE_COMPLETE_THRESHOLD=25`, `POSE_REVIEW_THRESHOLD=10`, `POSE_VISIBILITY_THRESHOLD=0.5`, `POSE_POLL_SECONDS=5`, `POSE_STALE_PROCESSING_SECONDS=1800`).

> El sha256 del archivo `.task` se registra en cada análisis como `model_version` (sha256[:16]) para que el resultado sea reproducible.

### Worker (Windows)

Desde la raíz del repo:

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\run-worker.ps1
```

El script crea `backend\.venv` si no existe, instala `requirements.txt` (incluye `mediapipe==1.2.3`) y levanta `python -m app.workers.pose_worker`. El worker se detiene con `Ctrl+C`.

Si el modelo no existe, el worker **falla claro al arrancar** con mensaje explícito (no procesas nada en silencio). Si el binario `mediapipe` no está instalado, cada tarea termina `failed` con `error_message` explicito — la API sigue funcionando.

### Endpoints (Fase 5)

- `POST /api/media/{id}/pose-analyses` — encola (201) o devuelve la tarea existente (200, si `queued`/`processing`). Solo `ready`. Editor+ (owner/editor) + expediente `active` + consentimiento vigente.
- `GET /api/media/{id}/pose-analyses` — lista del asset (viewer+).
- `GET /api/profiles/{id}/pose-analyses` — lista del expediente (viewer+).
- `GET /api/pose-analyses/{id}` — detalle (viewer+). Los landmarks solo aparecen en `completed`/`needs_review`; siempre llevan `data_kind=visual_estimate` + badge `ESTIMACIÓN VISUAL`.

### Comportamiento
- Estados: `queued → processing → completed | needs_review | failed`. `completed` ≥ 25 landmarks visibles (`visibility ≥ 0.5`); `needs_review` ≥ 10 y < 25; `failed` < 10 visibles o error de infra.
- Auditoría: `pose.queued` al encolar, `pose.completed`/`pose.needs_review`/`pose.failed` al terminar. El actor es quien inició la tarea.
- Stale: tareas `processing` con `started_at` más antiguo que `POSE_STALE_PROCESSING_SECONDS` (default 1800 s) se marcan `failed` al arranque del worker.
- Sin reintentos automáticos en Fase 5: un análisis `failed` requiere un nuovo POST explícito.

### Pruebas/observabilidad
- Tests: `python -m pytest` (incluye Fase 5: servicio, worker sin binario `mediapipe` y API).
- En Windows con Postgres arriba: `alembic upgrade head` (debe crear `pose_analyses`) antes de levantar API/worker.

## Fase 6 - Visor 3D anatómico (atlas genérico, CC BY-SA)

El visor muestra un **atlas anatómico genérico** de referencia: **no** usa imágenes, medidas ni
geometría del paciente y **no** diagnostica ni mide. Todo se etiqueta
`RECONSTRUCCIÓN APROXIMADA` (`DataKind = approximate_reconstruction`) con aviso no clínico
permanente. Ver ADR-007 en `docs/ARQUITECTURA.md`.

### Qué incluye
- **Rutas:** `/viewer` (desde el menú lateral **Visor 3D**) y `/viewer/:profileId` (botón
  "Abrir visor 3D" en la ficha del expediente; solo aporta contexto visual, no lee datos del paciente).
- **7 capas** con visibilidad y opacidad independientes: piel, esqueleto, músculos, órganos,
  arterias, venas, nervios. Carga progresiva por capa (al entrar solo baja el esqueleto).
- **Vistas** frontal / dorsal / lateral / superior + rotación automática; órbita, zoom y paneo.
- **Wireframe real** (toggle global en el panel de capas: cambia el modo de render de los triángulos cargados).
- **Ficha de procedencia** con licencia, autores, componentes retirados y sha256 por capa.
- **Resiliencia:** `ErrorBoundary` por capa y recuperación de pérdida de contexto WebGL.
- **Móvil:** DPR limitado, sin antialias/sombras y viewport ajustado.
- Sin overlay de landmarks de Fase 5 y sin contenido médico (solo geometría y nombres de capa).

### Activos 3D (`frontend/public/models/`)
Generados desde el atlas [3d-human-body-anatomy](https://github.com/SeemaBansal1/3d-human-body-anatomy)
(commit `2891243`, Z-Anatomy / BodyParts3D, **CC BY-SA 4.0**), con **poda previa** de los
componentes no comerciales:

| Capa | Meshes | Triángulos |
| --- | --- | --- |
| Piel (`skin.glb`) | 256 | 154.865 |
| Esqueleto (`skeleton.glb`) | 271 | 304.452 |
| Músculos (`muscles.glb`) | 476 | 447.787 |
| Órganos (`organs.glb`, 4 nodos NC eliminados) | 293 | 387.717 |
| Arterias (`arteries.glb`) | 417 | 408.542 |
| Venas (`veins.glb`) | 226 | 305.651 |
| Nervios (`nerves.glb`) | 255 | 277.720 |
| **Total** | **2194** | **2.286.734** (~9,2 MB) |

Se eliminaron los 4 meshes del **riñón** (`Kidney.l/r.001`, `Renal pelvis.l/r.001`, Lissie Cowley,
CC BY-NC 4.0) antes de publicar; el oído interno (Dundee, CC BY-NC-SA 4.0) nunca se exportó a los GLB.
Atribución y licencias completas: `frontend/public/models/ATTRIBUTION.md` y `manifest.json`.

Regenerar los activos (opcional; los GLB ya están versionados):
```powershell
# desde frontend/
git clone --depth 1 https://github.com/SeemaBansal1/3d-human-body-anatomy.git ..\.tmp\3d-human-body-anatomy
npm run assets:anatomy -- --source ..\.tmp\3d-human-body-anatomy\web\public\models
```

### Stack
React 18.3.1 + `@react-three/fiber` 8.18 + `@react-three/drei` 9.122 + `three` 0.186.1
(con `overrides` de `three-mesh-bvh` a 0.9.18 para compatibilidad con three ≥ 0.17). El visor va en
un chunk aparte (ruta `lazy`) y el decodificador Draco se sirve local desde `frontend/public/draco/`.

### Verificación de Fase 6
```powershell
# desde frontend/
npm install          # instala three/fiber/drei + gltf-transform (dev)
npm run build        # tsc -b + vite build (debe terminar sin errores)
npm run lint
npm run dev          # http://localhost:5173 → menú "Visor 3D"
```

Checklist manual en el navegador:
1. **Menú lateral → Visor 3D** abre `/viewer` con badge `RECONSTRUCCIÓN APROXIMADA` y aviso no clínico.
2. Al entrar solo se descarga el **esqueleto** (pestaña Red: `skeleton.glb`); el contador muestra `1/7 capas`.
3. Encender cada capa (piel, músculos, órganos, arterias, venas, nervios) descarga su GLB y el contador sube.
4. **Órganos**: no aparece riñón; el resto de vísceras sí.
5. **Wireframe real**: al activarlo, todas las capas visibles pasan a aristas; al desactivarlo vuelven a superficie.
6. **Opacidad**: bajar la piel al 30 % deja ver músculos/esqueleto; **Aislar** deja solo esa capa.
7. **Vistas** frontal/dorsal/lateral/superior y **rotación automática** funcionan; el arrastre orbita.
8. **Ficha de procedencia** muestra autoría, CC BY-SA 4.0, componentes retirados y sha256 por capa.
9. **Abrir visor 3D** desde un expediente (`/viewer/:profileId`) muestra el código del expediente y el aviso de que no se superpone con sus datos.
10. **Móvil / ventana estrecha**: DPR limitado, sin antialias ni sombras, el panel pasa debajo del visor.

## Fase 7 - Analítica descriptiva y reportes (CSV/PDF)

La analítica es **solo descriptiva**: último valor, valor anterior, delta absoluto y
porcentual, mínimo/máximo, media, mediana, conteo `n`, correcciones vigentes y atípicos
marcados (mediana ± 3.5·MAD con ≥3 puntos). **No hay predicción, regresión ni
interpretación clínica**, y los datos faltantes se muestran como ausencia ("—"), nunca
como `0.00` ni interpolados.

Los reportes se **separan por `DataKind`**: `measurements_*` son `OBSERVADO` y `pose_*` son
`ESTIMACIÓN VISUAL`. Un reporte de pose no puede contener mediciones y viceversa.

### Endpoints (Fase 7)
- `GET /api/profiles/{id}/analytics?window_days=7|30|90` — resumen descriptivo (viewer+).
  Audita `analytics.viewed`. Incluye `metrics_without_data` y el aviso no clínico.
- `POST /api/profiles/{id}/reports` — encola un reporte (viewer+). `201` al crear; `200` con
  el existente si ya hay uno idéntico en cola/proceso (idempotente).
- `GET /api/profiles/{id}/reports` — reportes del expediente.
- `GET /api/reports` — reportes solicitados por el usuario (solo expedientes con acceso vigente).
- `GET /api/reports/{id}` — detalle con `storage_key` oculto, tamaño y checksum.
- `GET /api/reports/{id}/content` — descarga autenticada; revalida el checksum SHA-256 y
  responde `Cache-Control: private, no-store` + `Content-Disposition: attachment`.
- `GET /api/dashboard/summary` — KPIs reales del usuario; nunca agrega expedientes ajenos ni
  suma estimaciones de pose a las mediciones observadas.

### Worker de reportes (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\run-report-worker.ps1
# Un solo lote y salir:
powershell -ExecutionPolicy Bypass -File backend\scripts\run-report-worker.ps1 -Once
```

El worker reserva con `FOR UPDATE SKIP LOCKED`, renderiza con `fpdf2==2.9.0` (Python puro,
compatible con Python 3.13 en Windows) y `csv`, y escribe el binario en el storage privado
(`UPLOAD_DIR`). En PostgreSQL solo quedan la clave, el checksum SHA-256 y el tamaño.
Si el worker no está levantado, los reportes quedan en `En cola` y la UI se refresca sola.

### Migración y variables
```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head   # aplica 0007_reports
```
Variables nuevas en `backend/.env`: `REPORT_POLL_SECONDS=5`,
`REPORT_STALE_PROCESSING_SECONDS=1800` (ver `.env.example`).

### Frontend
- **Reportes** activo en el menú lateral → `/reports` (mis reportes) y `/reports/:id`.
- **Analítica** por expediente → `/analytics/:profileId` o botón "Ver analítica" en la ficha.
- Dashboard con indicadores reales: desaparecen los textos "Disponible en Fase 2".

### Verificación de Fase 7
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
cd ..\frontend
npm run lint
npm run build
```

Checklist manual:
1. Ficha de expediente → **Ver analítica**: cambia 7/30/90 días y los valores se recalculan;
   las métricas sin datos aparecen como "—" y se listan en el aviso superior.
2. En la misma página, **Solicitar reporte**: elegir "Mediciones (PDF)" y generar.
3. Levantar el worker de reportes → el estado pasa a **Listo** en unos segundos.
4. **Reportes → Detalle → Descargar PDF**: el archivo abre con el aviso no clínico en el pie.
5. Solicitar un reporte de **Pose (CSV)** y comprobar que el documento dice
   `visual_estimate` y no contiene filas de mediciones.
6. Dashboard: los tres KPIs muestran números reales y ninguna leyenda "Disponible en Fase 2".

## Fase 8 - Simulador de escenarios hipotéticos

El simulador responde "¿y si…?" **sin tocar nada de lo observado**. Un escenario es una
copia congelada de las mediciones vigentes del expediente (`simulation_baselines`) más un
puñado de parámetros; el resultado se guarda aparte, con `data_kind = simulation` y una
huella SHA-256. **Nunca escribe ni sobrescribe `measurements`**, y no aparece en la analítica
ni en el dashboard.

- **Motor** `bodyvision.scenario 1.0.0`, determinista y aritmético (Decimal, 2 decimales).
  Sin azar, sin modelos, sin predicción.
- **Tope ±30 %** por métrica (`SIMULATION_MAX_DELTA_PERCENT`, configurable entre 5 y 50).
  Superarlo es un error explícito (422), nunca un recorte silencioso.
- **1–4 métricas** por escenario, con tres modos: cambio absoluto, cambio porcentual y valor
  objetivo. `height` **no** es simulable: solo se usa como referencia.
- **Derivados aritméticos** `waist_height` (cintura/estatura) y `waist_hip` (cintura/cadera),
  con sus componentes a la vista. **No se calcula IMC/BMI** ni ningún indicador clínico.
- **Escenario solo numérico**: el visor 3D no se deforma ni se superpone. No se genera malla.
- **Aviso permanente** "ESCENARIO HIPOTÉTICO" en lista, formulario, comparador y detalle.

### Endpoints (Fase 8)
- `GET /api/simulations/limits` — contrato del motor: métricas simulables, modos, tope vigente,
  `height_as_reference_only=true` y aviso.
- `POST /api/profiles/{id}/simulations` — crea un escenario (`run_now=false` deja borrador).
  Requiere acceso de escritura y consentimiento vigente.
- `GET /api/profiles/{id}/simulations` — escenarios del expediente (filtro `status`).
- `GET /api/simulations` — escenarios del usuario en expedientes con acceso vigente.
- `GET /api/simulations/{id}` — detalle con parámetros, tiempos y hash de la base.
- `GET /api/simulations/{id}/comparison` — base observada vs escenario, derivados, avisos y
  checksum. Audita `simulation.viewed`.
- `POST /api/simulations/{id}/run` — encola el cálculo (`draft` → `queued`).
- `POST /api/simulations/{id}/archive` — archivo lógico (requiere `OWNER`).

### Worker de simulación (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\run-simulation-worker.ps1
# Un solo lote y salir:
powershell -ExecutionPolicy Bypass -File backend\scripts\run-simulation-worker.ps1 -Once
```
Reserva con `FOR UPDATE SKIP LOCKED`, calcula y hace commit por iteración. Sin el worker los
escenarios quedan en **En cola** y la UI se refresca sola.

### Migración y variables
```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head   # aplica 0008_simulations
```
Variables nuevas en `backend/.env`: `SIMULATION_MAX_DELTA_PERCENT=30`,
`SIMULATION_POLL_SECONDS=5`, `SIMULATION_STALE_PROCESSING_SECONDS=1800`,
`SIMULATION_MAX_ACTIVE_PER_PROFILE=20` (ver `.env.example`).

### Frontend
- **Simulador** activo en el menú lateral → `/simulations` (mis escenarios).
- `/simulations/:profileId` — crear escenario y ver comparador del expediente.
- `/simulations/:profileId/:simulationId` — detalle con traza y comparador.
- Botón **Simulador** en la ficha del expediente.

### Verificación de Fase 8
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
cd ..\frontend
npm run lint
npm run build
```

Checklist manual:
1. Ficha de expediente → **Simulador**: aparece el aviso permanente y el tope de ±30 %.
2. Crear un escenario con `waist` −4.4 cm → el estado pasa a **En cola** y luego a **Calculado**
   al levantar el worker.
3. Abrir el comparador: base observada `88.00` frente a escenario `83.60`, Δ −4.40 y −5.00 %.
4. Comprobar los derivados: `waist_height` baja y `waist_hip` baja, ambos con sus componentes.
5. Revisar `/measurements` y `/analytics` del mismo expediente: **no cambia ni un valor**.
6. Intentar simular `height` → 422; intentar un cambio de ±40 % → 422 con el mensaje del tope.
7. Corregir una medición usada como base → el escenario antiguo mantiene su copia y avisa
   "base corregida después de calcularlo".
8. Archivar un escenario con otro usuario (sin `OWNER`) → `insufficient_access`.

## Ajustes de interfaz (revisión en vivo)

- **Visor 3D — tejido adiposo:** el atlas publicado trae **7 sistemas** (piel, esqueleto,
  músculos, órganos, arterias, venas y nervios) y **no** incluye malla de grasa. Se verificó
  `frontend/public/models/` y `manifest.json`. En lugar de generar una malla sintética (sería
  geometría sin procedencia), el panel de capas declara la ausencia con el motivo y el
  procedimiento para incorporarla si algún día se añade el `.glb`. La lista de ausencias vive en
  `frontend/src/features/viewer3d/layers.ts`.
- **Píldoras de estado:** `kind-badge`, `bv-tag` y `pose-badge` usan `width: fit-content` +
  `align-self: flex-start`, así que no se estiran al ancho del contenedor en Dashboard
  ("Cómo leer los datos") ni en Análisis de pose ("EN COLA").
- **Simulador:** las métricas se muestran con su etiqueta en español (`Cintura`, `Cadera`,
  `Peso`…) desde el catálogo (`useMeasurementCatalog`), con respaldo local en
  `features/measurements/metricLabels.ts`; nunca la clave cruda del backend.
- **Reportes:** cada fila muestra el `display_code` del expediente (enlazado), congelado en el
  reporte al solicitarlo. Se expone en el contrato como `profile_display_code`.
- **Análisis de pose:** corregida la concordancia ("Los esquemas corporales generados por IA") y
  las píldoras `needs_review`/`failed` dejaron de usar clases de *alerta* dentro de una etiqueta.

## Administración (panel de administrador)

La entrada **Administración** del menú lateral solo aparece a las cuentas con rol `admin`;
el resto ve la ruta protegida con un 403 explícito y el backend responde `403` en
`/api/admin/*`. **El rol de administrador no da acceso a expedientes**: se gestionan cuentas y
roles, no datos corporales, y la vista lo dice de forma permanente.

| Pestaña | Qué hace | Endpoint |
|---|---|---|
| **Usuarios** | Listado paginado con búsqueda por nombre/correo, filtro por rol y estado; activar/desactivar cuentas y editar roles | `GET /api/admin/users`, `PUT /api/admin/users/{id}/roles`, `POST /api/admin/users/{id}/activate|deactivate` |
| **Auditoría** | Tabla paginada de `audit_events` con fecha, acción legible + código, actor, recurso, resumen del `detail` y `request_id`; filtros por acción, usuario y rango de fechas | `GET /api/admin/audit-events`, `GET /api/admin/audit-actions` |
| **Workers** | Latidos de `pose`, `report`, `simulation` (continuos, con umbral) y `retention` (bajo demanda) con último latido, estado y último error; se refresca cada 30 s | `GET /api/health/workers` (solo `admin`) |

Reglas que la UI refleja y el backend impone: un administrador **no puede desactivar su propia
cuenta** ni **quitarse el rol `admin`** a sí mismo (botón deshabilitado con el motivo + el error
real del servidor si aun así se intenta), y un usuario **no puede quedarse sin roles**. Cada
cambio de roles o de estado queda auditado (`admin.roles_changed`, `admin.user_activated`,
`admin.user_deactivated`).

Los filtros de búsqueda, rol, estado, actor y fechas se añadieron en el backend como parámetros
**opcionales**: sin ellos el endpoint se comporta exactamente como antes.

### Verificación

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q tests\test_admin_api.py   # 15 passed
cd ..\frontend
npm run lint
npm run build
```

## Fase 9 - Producción, QA y operación

La Fase 9 **no añade producto**: hace que lo construido en las fases 1–8 se pueda
desplegar, observar y recuperar.

### Despliegue con Docker

```powershell
Copy-Item .env.prod.example .env.prod     # rellena DOMAIN, POSTGRES_PASSWORD y JWT_SECRET
# Prueba local con HTTPS autofirmado:
#   DOMAIN=localhost  ALLOW_SELFSIGNED=true
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

- **Nginx** sirve la SPA y hace de proxy de `/api` **bajo el mismo origen** (TLS, CSP,
  HSTS, `limit_req`).
- **API, worker de pose, worker de reportes y worker de simulación** en contenedores
  separados; el de pose usa su propia imagen (MediaPipe necesita `libgl1`).
- **Migraciones** en un job one-shot `migrate`; la API espera a que termine.
- La base **no publica puertos** y corre como usuario sin privilegios en la app.
- `VITE_API_URL=""` en producción → URLs relativas (mismo origen).

### TLS

Los certificados viven en `docker/nginx/certs/` (bind mount, **ignorado por git** porque
contiene la clave privada):

```powershell
# Opción A — Let's Encrypt: copia /etc/letsencrypt/live/$DOMAIN/ (fullchain.pem + privkey.pem)
# Opción B — certificado corporativo: deja ahí los dos ficheros
# Opción C — pruebas locales con HTTPS autofirmado:
powershell -ExecutionPolicy Bypass -File scripts\tls-selfsigned.ps1 -Domain localhost
#   (Linux: bash scripts/tls-selfsigned.sh localhost)
#   o, sin generar nada antes, arranca con ALLOW_SELFSIGNED=true y Nginx lo crea al arrancar.
```

El certificado autofirmado sirve para verificar que HTTPS, HSTS, CSP y el proxy funcionan
antes de tener el certificado real. **No** se usa en producción.

### Comprobaciones de seguridad y salud

| Endpoint | Qué responde |
|---|---|
| `GET /api/health/live` | El proceso vive (no consulta la BD) |
| `GET /api/health` | Compatibilidad: estado de la BD |
| `GET /api/health/ready` | BD + **escritura real en storage** + migraciones al día (503 si falla) |
| `GET /api/health/workers` | Latidos frente a `WORKER_STALE_SECONDS` (**solo `admin`**, 401/403 al resto) |

- **Rate limiting** por endpoint (login 5/min + 20/h por email, subidas 60/h, descargas
  120/h, techo 600/min) con `429` y `Retry-After`. `/api/health*` nunca se limita.
- **La IP del límite no es falsificable**: con `TRUSTED_PROXIES=true` se usa `X-Real-IP`,
  que Nginx **sobrescribe** con `$remote_addr`; `X-Forwarded-For` no se lee nunca (rotarlo
  no evade el límite). Con `TRUSTED_PROXIES=false` (default) se usa la IP de la conexión.
- **Cabeceras** en dos capas (FastAPI y Nginx), con CSP que permite **Draco WASM** del visor
  3D (`'wasm-unsafe-eval'`, `worker-src blob:`) sin abrir `unsafe-eval` de JavaScript.
- **`X-Request-ID`** correlaciona cabecera, log JSON y `audit_events.detail`.
- En producción la API **no arranca** con `DEBUG=true`, CORS `*` o `http://`,
  `ENABLE_API_DOCS=true` o un `JWT_SECRET` débil.
- `/api/docs` está **cerrado** en producción (activo en local y staging).

### Backups y retención

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -OutDir D:\backups
# Restauración VERIFICADA en una base nueva (obligatoria)
powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 -From D:\backups\<ts> -TargetDatabase bodyvision_qa

# Linux
bash backend/scripts/backup.sh
bash backend/scripts/restore.sh /backups/<ts> --target bodyvision_qa

# Contenedores de operación (imagen `docker/ops.Dockerfile`: PostgreSQL 16 + cliente).
# La imagen de la API NO trae `pg_dump`/`pg_restore`/`psql`, por eso estos servicios
# usan una imagen propia. Los flags se añaden al comando, no lo sustituyen.
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm restore --target bodyvision_qa
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm retention --apply
```

Cada backup produce `db.dump` (`pg_dump -Fc`), `storage.tar` (imágenes y binarios de reportes,
que **no** están en PostgreSQL) y `manifest.json` con SHA-256 y conteos por tabla. El restore
compara los conteos y falla si no cuadran. **RPO 24 h / RTO 2 h.**

La **retención** por fin se aplica: `python -m app.workers.retention_worker --once` purga
media, reportes y resultados de escenarios caducados, con `RETENTION_DRY_RUN=true` por defecto
y auditoría de cada borrado. Nunca toca `measurements`, `pose_analyses` ni `audit_events`.

### Verificación de Fase 9

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q        # 444 passed
.venv\Scripts\ruff.exe check .                 # 0 avisos
.venv\Scripts\python.exe -m alembic check     # sin divergencias metadata/migraciones
cd ..\frontend
npm run lint
npm run build
cd ..
python backend\scripts\validate_compose.py --env .env.prod
```

CI (`.github/workflows/ci.yml`): backend con PostgreSQL 16 de servicio (migraciones de ida y
vuelta + `alembic check` + pytest + ruff), frontend (`npm ci` + lint + build con
`VITE_API_URL=""`) y validación de la composición. **Sin despliegue automático.**

### Documentación de cierre

- `docs/QA_CHECKLIST.md` — 75 ítems con comando, evidencia y firma.
- `docs/SEGURIDAD_Y_PRIVACIDAD.md` — modelo de amenazas, mapa de datos y riesgos residuales.
- `docs/runbooks/` — `deploy`, `rollback`, `backup-restore`, `incident-response`,
  `key-rotation`, `worker-down`, `disk-full`, `database-unavailable`.
- `docs/ARQUITECTURA.md` — **ADR-002 a ADR-012** (ADR-001 no llegó a escribirse: la
  numeración arranca en el 002).
