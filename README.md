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
