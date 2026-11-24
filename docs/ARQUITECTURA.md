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

## ADR-007 · Visor 3D anatómico genérico (Fase 6)

**Estado:** Aceptada (Fase 6)

### Contexto

El Documento Maestro (MOD-06) pide un visor 3D del cuerpo. Se evaluó adaptar el atlas
abierto [`SeemaBansal1/3d-human-body-anatomy`](https://github.com/SeemaBansal1/3d-human-body-anatomy)
(commit `2891243`), construido sobre **Z-Anatomy** (CC BY-SA 4.0) y **BodyParts3D**
(DBCLS, CC BY-SA 2.1 JP): 7 capas GLB Draco, 2198 mallas, 2,29 M triángulos, 8,9 MB,
vértices en espacio de mundo, eje Y arriba, unidades en metros.

El atlas contiene dos componentes **no comerciales**: el riñón de *Lissie Cowley*
(CC BY-NC 4.0) y el oído interno de *Dundee* (CC BY-NC-SA 4.0). Además, el repo original
no tiene `LICENSE` en la raíz y su `README` advierte de la restricción del riñón.

### Decisiones

1. **El visor muestra una reconstrucción aproximada, no al paciente.** Todo lo mostrado
   es `DataKind = approximate_reconstruction`, con badge
   **RECONSTRUCCIÓN APROXIMADA** y aviso no clínico permanentes. No se mezcla ni se
   superpone con `observed`, `visual_estimate` (Fase 5) ni `simulation` (Fase 8).
2. **Sin overlay de pose.** El atlas es genérico y no tiene correspondencia anatómica
   verificada con los 33 landmarks de MediaPipe; superponerlos fabricaría una
   correspondencia falsa. El visor abre desde el expediente (`/viewer/:profileId`) solo
   como acceso contextual: **no** lee imágenes, medidas ni landmarks del expediente.
3. **Poda de los componentes NC antes de publicar (hecho).** `frontend/scripts/build-anatomy-assets.mjs`
   elimina los 4 nodos del riñón (`Kidney.l/r.001`, `Renal pelvis.l/r.001`) de
   `organs.glb` y falla si no los encuentra (poda verificable, no silenciosa). El oído
   interno de Dundee nunca se exportó a los GLB web; se documenta igualmente en la ficha
   de procedencia. Se conservan los vasos renales y suprarrenales (BodyParts3D, BY-SA).
4. **Cumplimiento CC BY-SA.** El derivado se publica bajo CC BY-SA 4.0 con la atribución
   completa en `frontend/public/models/ATTRIBUTION.md` (generado por el script, con
   sha256 por capa) y visible en la app en la **ficha de procedencia** del visor.
5. **Sin backend en el MVP.** No hay tabla `body_models` ni endpoint: el atlas es un
   activo estático versionado en git (`frontend/public/models/`) con
   `manifest.json` (meshes, triángulos, bytes, sha256, bbox y licencia por capa) como
   fuente de verdad. Si en el futuro hace falta trazabilidad por paciente o
   gobernanza de versiones, se añadirá `body_models` + `GET /api/body-models/current`
   y auditoría `body_model.viewed` **sin cambiar el frontend del visor**.
6. **Sin contenido médico en el MVP.** No se portan `content/*.json` (408 estructuras
   con descripciones de Wikipedia CC BY-SA 3.0), ni tours, ni "Dr. Buddy", ni hindi.
   Solo geometría, capas y nombres de capa en español. Las descripciones requerirían
   revisión de licencia y disclaimer educativo aparte.
7. **Stack: React 18 + `@react-three/fiber` v8 + `@react-three/drei` v9 + `three` 0.186.1.**
   Se mantiene React 18.3.1 (el resto de la app) y se fija `three` en la versión del
   atlas original. `drei` arrastra `three-mesh-bvh@0.7.8`, marcado como incompatible con
   three ≥ 0.17x, así que se fuerza con `overrides` a `three-mesh-bvh@0.9.18`. `@types/three`
   se fija a `0.186.0` para que coincida con el runtime.
8. **Streaming por capa.** Solo `skeleton` se descarga al entrar; el resto se pide al
   encenderlo (`useGLTF.preload` + `Suspense`). El visor se carga en un chunk aparte
   (ruta `lazy`) para no penalizar el arranque del resto de la app.
9. **Wireframe real.** El toggle del panel de capas cambia `wireframe` en los materiales
   de la geometría cargada; no dibuja contornos falsos ni mallas sintéticas.
10. **Resiliencia.** `ViewerErrorBoundary` por capa (un GLB corrupto no tumba el visor) y
    escucha de `webglcontextlost` con `event.preventDefault()` + botón "Reiniciar visor".
11. **Móvil.** Con `(max-width: 900px), (pointer: coarse)`: DPR limitado a `[1, 1.25]`,
    sin `antialias`, sin sombras, sin paneo por defecto y viewport más bajo.

### Compromisos conocidos aceptados

- 2194 draw calls por capa completa: el rendimiento depende del navegador. Se mitiga con
  visibilidad por capa, frustum culling y sin postproceso; el merge por capa solo se hará
  si el profiling real lo exige.
- El decodificador Draco se sirve desde `public/draco/` (copiado de three.js, MIT):
  +752 KB estáticos y sin dependencia de CDN.
- El visor no identifica estructuras concretas al hacer clic (sin picking/labels en MVP).
- No hay tests de render 3D automatizados (no hay GPU en CI): la verificación es
  `tsc -b` + `eslint` + `vite build` y un checklist manual en navegador.
- `ATTRIBUTION.md` y `manifest.json` se regeneran con el script; cualquier cambio manual
  de un GLB rompe el checksum registrado.

### Consecuencias

- Activos nuevos versionados (~9,2 MB en `frontend/public/models/` + 752 KB de Draco):
  no requieren Git LFS.
- Reproducir los activos: `npm run assets:anatomy -- --source <ruta>/web/public/models`
  (fuente clonada del atlas, no versionada).
- Rutas nuevas: `/viewer` y `/viewer/:profileId`; ítem **Visor 3D** activo en `SideNav` y
  botón "Abrir visor 3D" en la ficha del expediente.
- Fase 7 (reportes) y Fase 8 (simulador) reutilizarán este visor como base; ninguna
  deberá presentar la geometría como medición.

## ADR-008 · Analítica descriptiva y reportes trazables (Fase 7)

**Estado:** Aceptada (Fase 7)

### Contexto

Con las fases 2–6 cerradas hay mediciones inmutables y versionadas, consentimiento con
auditoría y análisis de pose etiquetados como estimación. El Documento Maestro (MOD-06,
RF-010/011) pide **analítica y reportes**: que el usuario pueda ver la evolución de su
expediente y descargar un documento. El riesgo evidente es que un "informe" se lea como
diagnóstico o que un reporte mezcle mediciones observadas con estimaciones de pose.

### Decisiones

1. **Analítica solo descriptiva.** Se calculan último valor, valor anterior, delta absoluto,
   delta porcentual, mínimo, máximo, media, mediana, conteo `n`, correcciones vigentes,
   fechas de la primera/última toma y atípicos marcados (mediana ± 3.5·MAD, con ≥3 puntos y
   MAD > 0). **No hay regresión, tendencia proyectada, predicción ni interpretación clínica.**
   No existe columna, campo ni endpoint de pronóstico.
2. **Sin datos se representa como ausencia, no como 0.** `summarize_series` devuelve `count=0`
   y todos los valores `None`; el CSV deja celdas vacías y la UI muestra "—". Las métricas del
   catálogo sin datos se listan explícitamente en `metrics_without_data`. Nunca se interpola.
3. **Separación estricta por `DataKind`.** `measurements_csv/pdf` son `observed`;
   `pose_csv/pdf` son `visual_estimate`. El tipo de reporte fija el `DataKind` en el dominio
   (`REPORT_DATA_KIND`), no el cliente, y `metrics` solo se acepta en reportes de mediciones
   (422 en caso contrario). El documento de pose no puede contener filas de mediciones.
4. **Generación asíncrona en PostgreSQL, sin cola externa.** `reports` actúa de cola:
   `queued → processing → generated | failed`. El worker reserva con
   `SELECT ... FOR UPDATE SKIP LOCKED`, marca `processing` con `started_at` y hace commit
   por iteración. Idempotencia: POST repetido sobre el mismo expediente/kind/rango en
   `queued`/`processing` devuelve `200` con el reporte existente (`201` solo al crear).
   `processing` más antiguo que `REPORT_STALE_PROCESSING_SECONDS` (default 1800 s) pasa a
   `failed` con `processing_stale`.
5. **Binarios fuera de PostgreSQL.** El renderizado (`fpdf2==2.9.0`, Python puro; CSV con
   `csv.writer`) produce bytes y el worker los escribe con `StorageBackend` privado usando
   una clave UUID nueva (`<uuid>.csv|pdf`). En la tabla solo viven `storage_key`,
   `checksum_sha256`, `size_bytes` y `mime_type`. Una clave nueva por intento evita
   sobrescribir y deja rastro de intentos previos.
6. **Trazabilidad completa.** Cada reporte guarda `requested_by_snapshot` (nombre congelado),
   `requested_by_user_id`, `parameters_json` con el código de expediente y el sello del
   pedido, `summary_json` con lo que se incluyó, `attempt_count` y `duration_ms`. La
   auditoría registra `report.requested`, `report.generated`, `report.failed` y
   `report.downloaded`; la analítica registra `analytics.viewed` y el panel `dashboard.viewed`.
7. **Descarga autenticada, nunca pública.** `GET /api/reports/{id}/content` exige sesión y
   acceso vigente al expediente, **revalida el checksum SHA-256** del binario antes de
   servirlo y responde con `Cache-Control: private, no-store`,
   `X-Content-Type-Options: nosniff` y `Content-Disposition: attachment`. Si el archivo no
   coincide con el checksum registrado se rechaza (409) en lugar de entregarse.
8. **PDF solo con fuentes core (latin-1).** El renderizador normaliza el texto a latin-1
   (`_pdf_text`) y no depende de fuentes del sistema ni de binarios externos: el documento se
   genera igual en Windows y en Linux. Cada página lleva el aviso no clínico y numeración.
9. **Formato de CSV estable.** Delimitador `;`, fin de línea `\r\n`, cabecera `#` con
   `report_id`, expediente, `data_kind`, solicitante, fechas, generador y aviso; después una
   fila por medición vigente y un bloque `# RESUMEN DESCRIPTIVO`. Los valores son
   deterministas (cuantizados a 2 decimales) para que el checksum sea reproducible.
10. **Dashboard con datos reales y sin fuga entre usuarios.** `GET /api/dashboard/summary`
    agrega **solo expedientes con acceso vigente** (`revoked_at IS NULL`) del usuario; el rol
    `admin` no obtiene acceso implícito. Mediciones y estimaciones de pose se cuentan en
    campos distintos: nunca se suma una estimación a las mediciones observadas. Desaparecen
    los placeholders "Disponible en Fase 2".
11. **Aviso no clínico permanente.** El texto está en el dominio (`DISCLAIMER`), en la
    cabecera y el pie del PDF, en la cabecera del CSV, en la página de analítica y en el
    detalle del reporte. No es configurable desde el cliente.

### Compromisos conocidos aceptados

- Sin reintentos automáticos: un reporte `failed` requiere una nueva solicitud del usuario.
- El worker de reportes se levanta aparte (`scripts/run-report-worker.ps1`, o `--once` para
  lotes); sin él, los reportes quedan `queued` (la UI lo refresca sola y lo indica).
- El tope de 500 análisis por reporte de pose acota documentos muy grandes; el resumen
  indica `pose_analyses_total_profile` para que la diferencia sea visible.
- No se purgan reportes generados en esta fase: la retención entra con la Fase 9.
- Sin `pytest` de render WebGL ni de fpdf2 en Windows; la verificación es de bytes
  (`%PDF-`/`%%EOF`, cabecera CSV) y el build del frontend.

### Consecuencias

- Tabla nueva `reports` (migración `0007_reports`) con CHECKs de `kind`, `status`,
  invariantes de ciclo de vida y de periodo.
- Endpoints nuevos: `POST|GET /api/profiles/{id}/reports`, `GET /api/reports`,
  `GET /api/reports/{id}`, `GET /api/reports/{id}/content`,
  `GET /api/profiles/{id}/analytics`, `GET /api/dashboard/summary`.
- Config nueva: `REPORT_POLL_SECONDS`, `REPORT_STALE_PROCESSING_SECONDS`.
- Frontend: ítem **Reportes** activo en `SideNav`; rutas `/reports`, `/reports/:id`,
  `/analytics/:profileId`; botón "Ver analítica" en la ficha del expediente; dashboard con
  KPIs reales.
- Fase 8 (simulador) deberá declararse `simulation` y no podrá escribir en `reports` como
  si fueran mediciones.

## ADR-009 · Simulación de escenarios hipotéticos aislada (Fase 8)

**Estado:** Aceptada (Fase 8)

### Contexto

El Documento Maestro (MOD-07, RF-012) pide un **simulador**: que el usuario pueda preguntar
"¿y si cambiara X?" sobre su expediente. Es la funcionalidad con más riesgo de todo el
sistema, porque el resultado se parece visualmente a una medición y puede leerse como
predicción corporal. Las fases 2–7 dejaron mediciones inmutables y versionadas, analítica
descriptiva sin pronóstico y separación estricta por `DataKind`. La simulación debe encajar
en ese marco sin contaminar ni un solo valor observado.

### Decisiones

1. **Copia congelada de la base, nunca datos vivos.** Al crear el escenario se copian los
   valores vigentes a `simulation_baselines` (una fila por métrica, con `measurement_id`
   `RESTRICT`, `value_snapshot`, `unit`, `measured_at`) y se calcula `baseline_hash`
   (SHA-256 canónico). El comparador y el worker leen **solo** esa copia. Si después se
   corrige una medición, el escenario conserva su base y se marca `superseded_since=true`;
   no se recalcula ni se reescribe. Esto hace el resultado reproducible y auditable años
   después.
2. **Aislamiento de escritura por diseño.** Las simulaciones viven en `simulations` +
   `simulation_baselines` con `data_kind='simulation'` fijado en el dominio. El servicio no
   tiene ninguna ruta de escritura hacia `measurements`: no las inserta, no las actualiza y
   no las borra. Los tests verifican una huella SHA-256 del estado completo de `measurements`
   idéntica antes y después de crear y ejecutar escenarios, y que ningún valor simulado
   aparece en mediciones, analítica ni dashboard.
3. **Tope del 30 % por métrica, configurable.** `SIMULATION_MAX_DELTA_PERCENT` (default 30,
   rango válido 5–50) acota cuánto puede moverse cada métrica respecto de su valor base.
   Superarlo es un error explícito (`SimulationError` → 422 con el mensaje "supera ±30%"), **nunca**
   un recorte silencioso. El acotado (`clamped`) solo actúa contra el rango técnico del
   catálogo y queda marcado en el resultado.
4. **Tres modos y 1–4 métricas por escenario.** `delta_absolute`, `delta_percent` y
   `target_value`. Se pueden combinar métricas en un mismo escenario (p. ej. cintura y peso)
   para que el usuario no tenga que crear cinco escenarios casi iguales. El máximo es 4 por
   el límite del contrato del motor.
5. **Motor determinista y aritmético.** `bodyvision.scenario 1.0.0` trabaja con `Decimal`
   (2 decimales, `HALF_UP`) y no usa aleatoriedad, modelos ni aprendizaje automático. Mismas
   entradas + misma base ⇒ mismo `result_checksum`. No hay inferencia de proporciones ni
   extrapolación entre métricas: cada parámetro afecta solo a su métrica.
6. **La estatura es solo referencia, y no hay BMI.** `height` no es simulable (422) porque
   deformar la estatura implicaría inventar un cuerpo. Sí entra como componente de los
   derivados. Los derivados son divisiones explícitas: `waist_height` (cintura/estatura) y
   `waist_hip` (cintura/cadera), cada una con sus componentes visibles en la UI. **No se
   calcula IMC/BMI**: combinar peso y estatura produciría un número con lectura clínica, y
   eso queda fuera del alcance no diagnóstico.
7. **Escenario solo numérico: el visor 3D no se toca.** Una simulación no genera malla,
   no reescala el modelo anatómico y no se superpone al visor. El plan inicial consideraba
   deformar la malla proporcionalmente; se descartó (D3/D4) porque una malla deformada
   finge una medición visual que el sistema no ha observado y rompe la separación
   observado / estimado / hipotético.
8. **Worker asíncrono sobre la propia tabla.** `simulations` es la cola:
   `draft → queued → completed | failed`, más `archived`. El worker
   (`app/workers/simulation_worker.py`, `scripts/run-simulation-worker.ps1`) reserva con
   `SELECT ... FOR UPDATE SKIP LOCKED`, escribe `started_at`, calcula y hace commit por
   iteración. `run_once()` es idempotente: devuelve `False` si no hay nada o si el escenario
   ya se procesó. Un escenario manipulado en su `value_snapshot` falla con mensaje de
   integridad (`simulation.failed`) y una cola más vieja que
   `SIMULATION_STALE_PROCESSING_SECONDS` pasa a `failed` con `queue_stale`.
9. **Borradores permitidos, sin ejecución implícita.** `POST` acepta `run_now=false` para
   dejar el escenario en `draft` y revisarlo antes; `POST /{id}/run` lo encola. También se
   puede crear y ejecutar en un mismo paso. Un borrador no calcula nada.
10. **Archivar es lógico y conserva la traza.** `POST /{id}/archive` pasa a `archived` sin
    borrar filas ni tocar `completed_at`; los triggers de la migración `0008` impiden `DELETE`
    y cualquier mutación de los campos congelados (`parameters_json`, `baseline_hash`,
    `result_json`, `result_checksum`). Archivar el escenario no archiva sus mediciones.
11. **Acceso y auditoría.** Se exige consentimiento vigente para crear y `viewer+` para leer;
    archivar requiere `OWNER` (un no-autor recibe `insufficient_access`). El rol `admin` no
    obtiene acceso implícito. Se audita `simulation.created`, `simulation.queued`,
    `simulation.completed`, `simulation.failed`, `simulation.archived` y `simulation.viewed`.
12. **Advertencia permanente de escenario hipotético.** El texto vive en el dominio
    (`SIMULATION_BANNER`/`SIMULATION_DISCLAIMER`) y se muestra en todas las superficies: lista,
    formulario, comparador y detalle, además del resultado del endpoint `comparison`. La UI
    usa borde discontinuo y la etiqueta `SIMULATION` para que nunca se confunda con una
    medición observada. No es descartable ni configurable desde el cliente.
13. **Sin reportes PDF de simulación en esta fase.** Los reportes de la Fase 7 rechazan
    `kind=simulation_pdf` (422): un PDF exportable de un escenario hipotético es exactamente
    el artefacto que más fácilmente se saca de contexto. Si se añade en Fase 9, llevará el
    aviso en cabecera, pie y marca de agua.

### Compromisos conocidos aceptados

- Sin reintentos automáticos: un escenario `failed` exige crear o relanzar otro.
- Sin edición de parámetros: un escenario calculado es inmutable; para cambiarlo se crea otro.
- Máximo 20 escenarios activos (no archivados) por expediente; al llegar al tope se pide
  archivar antes de seguir (`SIMULATION_MAX_ACTIVE_PER_PROFILE`).
- El worker se levanta aparte; sin él los escenarios quedan `queued` (la UI se refresca sola).
- La simulación no se exporta (ni CSV ni PDF) y no se agrega a la analítica ni al dashboard.

### Consecuencias

- Tablas nuevas `simulations` y `simulation_baselines` (migración `0008_simulations`), con FK
  `RESTRICT` a `measurements`, CHECKs de estado/modo y triggers de protección.
- Endpoints nuevos: `GET /api/simulations/limits`, `POST|GET /api/profiles/{id}/simulations`,
  `GET /api/simulations`, `GET /api/simulations/{id}`, `GET /api/simulations/{id}/comparison`,
  `POST /api/simulations/{id}/run`, `POST /api/simulations/{id}/archive`.
- Config nueva: `SIMULATION_MAX_DELTA_PERCENT`, `SIMULATION_POLL_SECONDS`,
  `SIMULATION_STALE_PROCESSING_SECONDS`, `SIMULATION_MAX_ACTIVE_PER_PROFILE`.
- Frontend: ítem **Simulador** activo en `SideNav`; rutas `/simulations`,
  `/simulations/:profileId` y `/simulations/:profileId/:simulationId`; botón "Simulador" en la
  ficha del expediente; comparador base vs escenario con aviso permanente.
- El visor 3D no cambia: sigue sin superponer datos personales y no consume simulaciones.
