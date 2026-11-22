# BODYVISION AI

Plataforma paramétrica de análisis, captura y simulación 3D de mediciones corporales **hipotéticas**.
**No emite diagnósticos médicos.** Toda salida de IA es una *estimación visual*; toda simulación es un
*escenario hipotético* separado de las mediciones reales.

## Requisitos
- Docker Desktop (PostgreSQL)
- Python 3.11 (backend, `venv`)
- Node 20 LTS + npm

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
python -m pytest                 # 187 tests (Fase 5 incluida)
ruff check app/ tests/          # ruff (B008 conocido en rutas FastAPI)
# Frontend (desde frontend/)
npm run build && npm run lint
# Smoke (API local, arriba)
powershell -ExecutionPolicy Bypass -File scripts/smoke_phase4.ps1
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
- Tests: `python -m pytest` (187 tests, incluye Fase 5: servicio, worker sin binario `mediapipe` y API).
- En Windows con Postgres arriba: `alembic upgrade head` (debe crear `pose_analyses`) antes de levantar API/worker.
