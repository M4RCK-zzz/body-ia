# Arquitectura (Fase 1 y 2)

## Capas del backend
| Capa | Carpeta | Regla |
|---|---|---|
| Contrato HTTP | `api/routes` | Solo parseo/respuesta; sin lógica ni SQL |
| Composición | `api/deps.py` | Único lugar que conecta sesión → repositorio → servicio |
| Reglas de negocio | `services` | No importa FastAPI ni SQLAlchemy; lanza `AppError` |
| Acceso a datos | `repositories` | Interfaz abstracta + implementación SQLAlchemy |
| Persistencia | `models` | Entidades ORM |
| Contratos | `schemas` | DTOs Pydantic de entrada/salida |
| Dominio puro | `domain` | Enums y reglas sin framework (`DataKind`) |
| Tareas pesadas | `workers` | Fase 5 |

Transacciones: los repositorios hacen `flush`; el servicio confirma mediante `UnitOfWork`.

## Regla de oro: tipos de dato (`DataKind`)
`observed` · `visual_estimate` · `approximate_reconstruction` · `simulation`.
Nunca se mezclan en API ni UI; cada dato mostrado lleva su etiqueta (`DataKindBadge`).

## ADR-002 · Mediciones inmutables y correcciones versionadas
- Una medición nunca se actualiza. Corregir = insertar una fila con `supersedes_id`, `correction_reason`, `created_by` y `recorded_at`.
- "Vigente" = ninguna otra fila la reemplaza. `UNIQUE(supersedes_id)` impide bifurcar la cadena.
- Un trigger de PostgreSQL rechaza `UPDATE` sobre `measurements` (defensa en profundidad).
- Rangos técnicos = plausibilidad, no criterios clínicos. Fuente única: `MetricCatalog`.
- Las simulaciones (Fase 8) viven en otra tabla y no entran en las series reales.

## Frontend
`app` (rutas/layouts/providers) · `components` (UI base) · `features` (módulos por dominio) ·
`services` (clientes API). Los módulos aún no implementados aparecen deshabilitados con su fase.

## Decisiones vigentes
- Cola de workers (Fase 5) respaldada por PostgreSQL (`FOR UPDATE SKIP LOCKED`), sin Redis.
- Almacenamiento de medios (Fase 4) tras una interfaz `StorageBackend`.
- Python 3.11 fijo por compatibilidad futura con MediaPipe en Windows.
## ADR-003 · Identidad, RBAC y auditoría append-only (Fase 3A)
- **Autenticación:** JWT de acceso de corta vida (30 min). El token solo identifica (`sub`); roles y estado de la cuenta se consultan en BD en cada petición.
- **Contraseñas:** Argon2id. Política técnica mínima (10+ caracteres, letra y número).
- **Fuerza bruta:** bloqueo temporal por cuenta tras N fallos; respuesta uniforme para no permitir enumeración de cuentas.
- **RBAC:** `admin`, `professional`, `user`. `admin` gestiona cuentas, no obtiene acceso implícito a expedientes.
- **Auditoría:** `audit_events` es append-only (trigger `BEFORE UPDATE OR DELETE`).
- **Límites conocidos:** sin refresh token ni revocación en servidor; token en `sessionStorage`; sin rate limiting por IP.
## ADR-004: Acceso por expediente, consentimiento y auditoría de denegaciones

**Estado:** Aceptada (Fase 3B)

### Contexto

Tras la Fase 3A existe identidad (usuarios, roles, auditoría), pero los expedientes y sus mediciones no tienen propietario ni control de acceso, y no hay consentimiento registrado. Los documentos de referencia exigen consentimiento válido antes de capturar o registrar datos y trazabilidad sin sobrescritura.

### Decisiones

1. **Propiedad y niveles.** Cada expediente tiene un `owner_id` (`NOT NULL`) y concesiones en `profile_access` con niveles `owner`, `editor` y `viewer`. Un único propietario activo por expediente (índice parcial único).
2. **Sin acceso implícito para `admin`.** El rol administra cuentas, no datos.
3. **404 frente a 403.** Sin concesión activa → `404` (no revela existencia). Con concesión insuficiente → `403 insufficient_access`.
4. **Concesión por email** a cualquier cuenta activa (no se exige rol `professional`). Solo el propietario concede y revoca. No se puede conceder `owner`, ni a uno mismo, ni revocar al propietario. Cambiar de nivel revoca la fila anterior y crea otra (queda historial). La revocación es inmediata porque el acceso se lee de BD en cada petición.
5. **Consentimiento** (`consents`: finalidad, versión, quién y cuándo aceptó, revocación). Solo el propietario acepta o revoca. Aceptar la misma versión es idempotente; una versión nueva revoca la anterior. Un trigger de BD impide borrar filas y modificar nada salvo `revoked_at`/`revoked_by`; la revocación es definitiva.
6. **Efecto del consentimiento:** sin consentimiento vigente, registrar o corregir mediciones devuelve `422 consent_required`. Las lecturas siguen permitidas para poder consultar y gestionar el expediente.
7. **Auditoría ampliada:** todas las escrituras y los accesos denegados (`access.denied`, con motivo `no_access` o `insufficient_level`). Las lecturas normales no se auditan.
8. **Autoría del servidor.** `created_by` deja de venir del cliente: es una instantánea de `actor.full_name`, y `created_by_user_id` guarda la referencia. Enviar `created_by` produce `422` (`extra=forbid`).
9. **Migración 0004** aborta si existen expedientes sin propietario; se resuelve con `reset-dev-data.ps1` (solo desarrollo).

### Permisos

| Acción | viewer | editor | owner |
|---|:---:|:---:|:---:|
| Ver expediente, mediciones, historial | ✔ | ✔ | ✔ |
| Registrar / corregir mediciones* | ✘ | ✔ | ✔ |
| Renombrar, archivar, restaurar | ✘ | ✘ | ✔ |
| Gestionar accesos y consentimiento | ✘ | ✘ | ✔ |

*\* Requiere expediente activo y consentimiento vigente.*

### Compromisos conocidos (aceptados por ahora)

* `display_code` sigue siendo único global: un `409` revela que el seudónimo existe en otra cuenta. Se puede pasar a unicidad por propietario más adelante.
* Conceder por email devuelve `404` si la cuenta no existe: un usuario autenticado puede enumerar cuentas (igual que el `409` de registro, ADR-003).
* Las denegaciones solo se auditan si el expediente existe; el sondeo con UUID aleatorios no se registra.
* El texto de consentimiento es un **borrador pendiente de revisión legal** (Ley 29733); no debe usarse con datos reales sin esa revisión.
* No hay transferencia de propiedad.
* No hay limitación de intentos por IP ni revocación de tokens en servidor.

### Consecuencias

* Los servicios reciben siempre `actor` como primer parámetro y delegan la autorización en `AccessGuard`.
* `ProfileRepository.list_page` se sustituye por `list_accessible`, que solo devuelve expedientes con concesión activa.
* Las fases de captura y análisis (4 y 5) reutilizarán `AccessGuard` y `ConsentService.ensure_valid`.
## ADR-005 · Captura segura y storage privado (Fase 4)

**Estado:** Aceptada (Fase 4)

### Contexto

Tras la Fase 3B, los expedientes tienen identidad, accesos y consentimiento, pero aún no existe un canal para capturar imágenes de referencia de forma segura. El Documento Maestro exige, antes de datos reales: validación de MIME real y contenido, límite de tamaño, re-encoding, borrado de EXIF, hash/checksum, almacenamiento privado privado con claves no predecibles, retención y borrado auditado.

### Decisiones

1. **Medios fotográficos no son mediciones.** `media_assets` nunca entra en las series de mediciones ni se presenta como `observed`; la UI los etiqueta como "material de referencia fotográfico".
2. **Storage privado local.** Los bytes viven en `backend/storage/{shard2}/{key}`, con escritura atómica (`tmp` + `rename`), permisos `0600` y clave aleatoria `{uuid4}.{ext}` (jamás el nombre original). El navegador nunca toca el almacenamiento. La interfaz `StorageBackend` lo abstrae; el object storage (Fase 9) se añade como otra implementación sin cambiar rutas ni servicios.
3. **Descarga autenticada por streaming.** `GET /api/media/{id}/content` sirve los bytes desde la API con `Cache-Control: private, no-store` y `X-Content-Type-Options: nosniff`. No hay URLs firmadas en local; las URLs firmadas llegarán con el proveedor de almacenamiento real.
4. **Validación y sanitización.** Solo JPEG/PNG/WebP. `image` no es el contenido real: se verifica con Pillow (`.load()` + `format` en {JPEG, PNG, WEBP}). Los límites son `MAX_UPLOAD_MB` (grueso, 413) y `MEDIA_MAX_PIXELS` (25 Mpx) + 8000 px por lado. Se re-encodea con `ImageOps.exif_transpose(img)` (orientación) → flatten a blanco → `convert("RGB")` → JPEG `progressive/optimize`, PNG `optimize`, WebP `q85`. **Ningún EXIF, XMP o texto se copia**: la imagen se re-codifica desde una copia fresca.
5. **Rechazo.** Si la imagen no valida, se persiste el registro de auditoría con metadatos (`status=rejected`, razón, tamaño crudo, checksum del archivo crudo, sin bytes en disco) y la API responde 422 `media_rejected`. Tampoco se guarda el archivo físico.
6. **Ciclo de vida.** `uploaded → validating → ready / rejected / deleted`. No es una tabla append-only (las transiciones legítimas lo requieren); la trazabilidad contra borrados/cambios indebidos vive en auditoría (`media.uploaded`, `media.rejected`, `media.deleted`). El borrado es soft delete (`status=deleted` + `deleted_at` + `deleted_by_user_id`) y **borrado físico best-effort** del archivo en disco.
7. **Retención.** `retention_until = uploaded_at + MEDIA_RETENTION_DAYS` (default 365, 1–3650). Fase 4 no purga: el borrado físico lo hace el propietario/editor (o Fase 9, cuando exista el job).
8. **Autoría.** `uploaded_by_snapshot`/`uploaded_by_user_id` se fijan en el servidor; ningún cliente envía autoría.
9. **Herencia de permisos.** Upload (POST) y delete (DELETE) requieren `editor`+, expediente activo y consentimiento vigente, igual que mediciones. Lecturas (lista/metadata/content) requieren `viewer`+ vía `AccessGuard`. El `admin` no obtiene acceso implícito.

### Compromisos conocidos aceptados

- El rechazo persiste metadatos sin bytes; una imagen cifrada/maliciosa que supera el límite de tamaño se rechaza con 413 antes de cualquier escritura a disco.
- Los estados `uploaded`/`validating` son transitorios dentro de la misma request; el cliente solo observa `ready`/`rejected` (o el error). En Fase 5 entrarán el análisis asíncrono.
- El content endpoint no se audita en cada carga (se evita spam por thumbnails); en Fase 9 llegará la observabilidad de accesos.
- `media_assets` no tiene trigger append-only: la mitigación es auditoría + eventos de borrado.

### Consecuencias

- `MediaService` delega en `AccessGuard` y `ConsentService` como todas las escrituras.
- `StorageBackend` es la única vía de acceso a bytes; S3/TLS se añadirán en Fase 9 sin cambiar rutas/servicios.
- El frontend pinta los assets con una etiqueta "material de referencia" y nunca los mezclará con series de mediciones, estimaciones o simulaciones.
## ADR-006 · Análisis de pose (Fase 5)

**Estado:** Aceptada (Fase 5)

### Contexto

Tras la Fase 4 existen assets `ready` validados y almacenados privadamente. El Documento Maestro (RF-010/011) exige análisis de pose reproducible: MediaPipe Pose Landmarker, estados versionados, banderas de calidad y revisión humanas visibles — separados siempre de las mediciones observadas.

### Decisiones

1. **No es medición.** Un resultado de pose es una *estimación visual* (`visual_estimate`). La UI lo etiqueta "ESTIMACIÓN VISUAL" con versión del modelo; nunca se mezcla ni re-calcula como medición observada.
2. **Cola en PostgreSQL, sin Redis/Celery.** El worker afirma la tarea con `SELECT ... FOR UPDATE SKIP LOCKED` (`status='queued'`), marca `processing` y hace commit inmediato del claim. Así es seguro múltiples workers concurrentes y el reinicio del proceso no pierde tareas. Sin job externo, sin agente externo: `python -m app.workers.pose_worker`.
3. **Worker independiente, lazy-import.** `mediapipe` no se importa en la API; el worker lo carga una vez en arranque. Si falta el binario o el modelo, el worker falla claro al arrancar y cada tarea termina `failed` con `error_message` explicito (no se cae).
4. **Idempotencia por asset.** Una asset activo solo puede tener una tarea en `queued`/`processing` al mismo tiempo. Re-POST devuelve `200` con la misma tarea (`201`/`202` solo en la creación). Nunca duplicar análisis por error de reintento.
5. **Estados.** `queued → processing → completed | needs_review | failed`. `completed` ≥ 25/33 landmarks visibles (visibility ≥ 0.5); `needs_review` ≥ 10 pero < 25 (pose parcial o baja calidad); `failed` < 10 visibles o error del modelo/archivo. `failed` también representa fallo de infra (modelo no encontrado, archivo no disponible, excepción).
6. **Versionado y reproductibilidad.** Cada análisis guarda `model_name`, `model_version` (sha256[:16] del archivo `.task`), y `model_config` (mediapipe version, sha256 completo, umbrales usados, archivo del .task, thresholds configurados). El input reproducible es el checksum del asset (`media_assets.checksum`).
7. **Solo `ready` entra.** Un asset `uploaded`/`validating`/`rejected`/`deleted` devuelve `422` con mensaje claro.
8. **Autorización.** POST/list/detail: permiso `editor`+ y expediente `active` y consentimiento `data_processing` vigente (mismo patrón Fase 4). Lectura: `viewer`+. El `admin` no obtiene acceso implícito. Autoría fija en el servidor.
9. **Auditoría.** `pose.queued` al crear (actor = quien inicia) y `pose.completed`/`pose.needs_review`/`pose.failed` al terminar (actor = quien inició, registrado en la tarea).
10. **Stale processing.** Si el worker cae o se mata, las tareas `processing` con `started_at` más antiguo que `POSE_STALE_PROCESSING_SECONDS` (default 1800 s) se marcan `failed` con `error_message='processing_stale'` en el arranque del worker.
11. **Retención.** No hay purga en Fase 5; los registros de pose se tratan con el medio (`media_assets`). La purga automatizada llega en Fase 9.

### Compromisos conocidos aceptados

- Los `landmarks_json` crecen con el número de landmarks × precisión; el default de 33 landmarks × {x,y,z,visibility} es ~50 KB por análisis. Aceptable sin compresión.
- Landmarks normalizados (0–1) del MediaPipe Pose Landmarker: son referencias visuales orientativas, no coordenadas absolutas del cuerpo.
- Sin reintentos automáticos en Fase 5: un análisis `failed` requiere un nuevo POST explícito.
- El panel de revisión es parte del listado de captura; la página `/analyses/:id` deep-linka desde cada card/análisis.

### Consecuencias

- `PoseService` crea la tarea (POST) y la lee (GET); no ejecuta el modelo.
- El worker `app/workers/pose_worker.py` ejecuta el modelo, evalua calidad y persiste el resultado.
- `Config` gana: `POSE_MODEL_PATH`, `POSE_POLL_SECONDS`, `POSE_STALE_PROCESSING_SECONDS`, `POSE_COMPLETE_THRESHOLD`, `POSE_REVIEW_THRESHOLD`.
- Fase 6 (Visor 3D) evaluará/adaptará el modelo 3D `SeemaBansal1/3d-human-body-anatomy` — **no se implementa aquí**.
