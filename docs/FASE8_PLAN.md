# Fase 8 — Simulación de escenarios hipotéticos (plan técnico)

> **Documento histórico.** Plan de ejecución de la Fase 8, conservado como registro. Las
> cifras y rutas definitivas están en `README.md` y `docs/ARQUITECTURA.md` (ADR-009).
**Estado:** propuesta, pendiente de confirmación. **No se ha escrito código de Fase 8.**

> Regla rectora: una simulación es un **escenario hipotético** (`DataKind=simulation`) que
> responde a "¿y si…?" sobre una **fotografía inmutable** de mediciones ya registradas.
> Nunca crea, modifica ni reemplaza mediciones observadas; nunca se dibuja sobre la serie
> real; nunca se presenta como predicción ni como recomendación.

---

## 1. Alcance

### Incluye (8A)

1. Crear un escenario sobre un expediente con acceso: `draft` → `queued` → `completed`
   (o `failed`), y archivarlo (`archived`).
2. Motor **aritmético, determinista y versionado** que aplica deltas hipotéticos a métricas
   corporales y devuelve valores de escenario + deltas + indicadores derivados.
3. Comparador **base observada vs escenario** con etiquetado permanente de tipo de dato.
4. Trazabilidad completa: referencia exacta a las mediciones base, versión del motor,
   checksum del resultado y auditoría de cada transición.

### No incluye (queda para Fase 9 o posterior)

- Predicción temporal, regresión, curvas de evolución o "proyección a 3 meses".
- Deformación de malla 3D, cambio de geometría o generación de cuerpos sintéticos.
- Recomendaciones, objetivos de peso, interpretación clínica o nutricional.
- Reportes PDF/CSV de simulaciones (ver decisión **D9**).
- Purga automática de escenarios (retención entra en Fase 9, igual que reportes).

---

## 2. Modelo de datos

### 2.1 `simulations`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `profile_id` | `uuid` FK `profiles.id` **RESTRICT** | Mismo criterio que el resto del modelo |
| `label` | `varchar(80)` | Nombre del escenario ("Escenario A") |
| `status` | `varchar(16)` | `draft·queued·completed·failed·archived` |
| `data_kind` | `varchar(16)` | Siempre `simulation` (CHECK) |
| `engine_name` | `varchar(40)` | `bodyvision.scenario` |
| `engine_version` | `varchar(20)` | `1.0.0` (ver §4) |
| `engine_config` | `jsonb` | Umbrales/límites usados (delta máx., redondeo, catálogo) |
| `parameters_json` | `jsonb` | Entrada del usuario: `{metric: {mode, value}}` |
| `baseline_hash` | `varchar(64)` | SHA-256 del snapshot canónico de la base |
| `result_json` | `jsonb` NULL | Salida del motor (§4.3) |
| `result_checksum` | `varchar(64)` NULL | SHA-256 del resultado canónico |
| `notes` | `varchar(500)` NULL | Nota libre del autor |
| `error_message` | `varchar(300)` NULL | Sólo `failed` |
| `created_by_user_id` | `uuid` FK `users.id` **RESTRICT** | Autoría fijada por el servidor |
| `created_by_snapshot` | `varchar(120)` | Nombre congelado (patrón de `reports`) |
| `created_at` | `timestamptz` | `now()` |
| `queued_at` / `started_at` / `completed_at` / `archived_at` | `timestamptz` NULL | Hitos |
| `duration_ms` | `int` NULL | |
| `attempt_count` | `int` | Default `0` |

**CHECKs (nombres lógicos cortos, la metadata antepone `ck_<tabla>_`):**

- `status` ∈ (`draft`, `queued`, `completed`, `failed`, `archived`)
- `data_kind = 'simulation'`
- `lifecycle` — invariantes por estado:
  - `draft`: sin `queued_at/started_at/completed_at`, sin `result_json`, sin `error_message`, sin `archived_at`
  - `queued`: `queued_at` NOT NULL; sin `started_at/completed_at`, sin resultado
  - `completed`: `started_at` + `completed_at` + `result_json` + `result_checksum` NOT NULL; `error_message` NULL; `archived_at` NULL
  - `failed`: `completed_at` + `error_message` NOT NULL; `result_json` NULL; `archived_at` NULL
  - `archived`: `result_json` + `completed_at` + `archived_at` NOT NULL
- `parameters_shape`: `jsonb_typeof(parameters_json) = 'object'` y `parameters_json <> '{}'::jsonb`
- `timeline`: `completed_at >= created_at`, `archived_at >= completed_at` (cuando no son NULL)
- `label_len`: `length(btrim(label)) between 1 and 80`

**Índices:** `ix_simulations_profile_created (profile_id, created_at DESC)`,
`ix_simulations_queue (queued_at) WHERE status='queued'` (parcial, para el claim),
`ix_simulations_creator (created_by_user_id, created_at DESC)`.

### 2.2 `simulation_baselines` (la referencia base)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `simulation_id` | `uuid` FK `simulations.id` **RESTRICT** | Sin borrado en cascada: la traza no se pierde |
| `metric_type` | `varchar(32)` | |
| `measurement_id` | `uuid` FK `measurements.id` **RESTRICT** | Fila exacta observada |
| `value_snapshot` | `numeric(7,2)` | Valor en el momento del escenario |
| `unit` | `varchar(8)` | |
| `measured_at` | `timestamptz` | |

`UNIQUE (simulation_id, metric_type)`; índice por `measurement_id`.

**Por qué una tabla hija y no JSONB**: el `FK` a `measurements` es verificable por la base y
`ON DELETE RESTRICT` impide que una medición usada como base desaparezca. El snapshot de
valor/fecha/ unidad se guarda además para que el escenario siga siendo legible y auditable
por sí mismo (y entra en el `baseline_hash`).

---

## 3. Migración Alembic `0008_simulations` (borrador, **no aplicada**)

`revision = "0008"`, `down_revision = "0007"` (continúa la cadena `0001 → 0007`).

```python
def upgrade() -> None:
    op.create_table(
        "simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("data_kind", sa.String(16), nullable=False, server_default="simulation"),
        sa.Column("engine_name", sa.String(40), nullable=False),
        sa.Column("engine_version", sa.String(20), nullable=False),
        sa.Column("engine_config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("parameters_json", postgresql.JSONB, nullable=False),
        sa.Column("baseline_hash", sa.String(64), nullable=False),
        sa.Column("result_json", postgresql.JSONB),
        sa.Column("result_checksum", sa.String(64)),
        sa.Column("notes", sa.String(500)),
        sa.Column("error_message", sa.String(300)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_snapshot", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('draft','queued','completed','failed','archived')", name="status"),
        sa.CheckConstraint("data_kind = 'simulation'", name="data_kind"),
        sa.CheckConstraint("<lifecycle>", name="lifecycle"),
        sa.CheckConstraint(
            "jsonb_typeof(parameters_json) = 'object' AND parameters_json <> '{}'::jsonb",
            name="parameters_shape",
        ),
        sa.CheckConstraint("length(btrim(label)) BETWEEN 1 AND 80", name="label_len"),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at", name="timeline"
        ),
    )
    op.create_table("simulation_baselines", ...)   # FKs + UNIQUE(simulation_id, metric_type)
    op.create_index("ix_simulations_profile_created", "simulations", ["profile_id", "created_at"])
    op.create_index("ix_simulations_queue", "simulations", ["queued_at"],
                    postgresql_where=sa.text("status = 'queued'"))
    op.create_index("ix_simulations_creator", "simulations", ["created_by_user_id", "created_at"])
    op.create_index("ix_simulation_baselines_measurement", "simulation_baselines", ["measurement_id"])

    # Inmutabilidad del resultado (defensa en profundidad, mismo estilo que
    # trg_measurements_immutable / trg_audit_events_append_only).
    op.execute("""
        CREATE FUNCTION protect_completed_simulation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('completed','archived') THEN
                IF NEW.result_json IS DISTINCT FROM OLD.result_json
                   OR NEW.baseline_hash IS DISTINCT FROM OLD.baseline_hash
                   OR NEW.parameters_json IS DISTINCT FROM OLD.parameters_json
                   OR NEW.engine_version IS DISTINCT FROM OLD.engine_version
                   OR NEW.engine_config IS DISTINCT FROM OLD.engine_config THEN
                    RAISE EXCEPTION 'Un escenario completado no puede modificarse';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_simulations_protect
        BEFORE UPDATE ON simulations
        FOR EACH ROW EXECUTE FUNCTION protect_completed_simulation();

        CREATE FUNCTION prevent_simulation_delete() RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('completed','archived') THEN
                RAISE EXCEPTION 'Un escenario completado no se elimina: se archiva';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_simulations_no_delete
        BEFORE DELETE ON simulations
        FOR EACH ROW EXECUTE FUNCTION prevent_simulation_delete();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_simulations_no_delete ON simulations")
    op.execute("DROP FUNCTION IF EXISTS prevent_simulation_delete()")
    op.execute("DROP TRIGGER IF EXISTS trg_simulations_protect ON simulations")
    op.execute("DROP FUNCTION IF EXISTS protect_completed_simulation()")
    op.drop_table("simulation_baselines")
    op.drop_table("simulations")   # los índices caen con las tablas
```

**Nota:** el trigger no restringe `status completed → archived` ni la escritura de
`archived_at`; todo lo demás de un escenario ya completado queda congelado. El
`downgrade` respeta el orden inverso de creación y elimina funciones antes que tablas.

**Lo que la migración NO hace:** no toca `measurements`, no añade columnas a tablas
existentes y no modifica ninguna fila de datos observados. `alembic downgrade 0007` deja la
base exactamente como está hoy.

---

## 4. Motor de simulación versionado

Módulo puro `app/domain/simulation.py` (sin FastAPI, sin SQLAlchemy, sin BD), testeable como
`domain/reports.py` en Fase 7.

### 4.1 Contrato

```python
ENGINE_NAME = "bodyvision.scenario"
ENGINE_VERSION = "1.0.0"

def build_baseline(measurements: Sequence[Measurement]) -> BaselineSnapshot
def apply_scenario(baseline: BaselineSnapshot, params: ScenarioParameters, *,
                   limits: EngineLimits) -> ScenarioResult
def canonical_hash(payload: Mapping[str, Any]) -> str      # JSON con claves ordenadas
```

- **Determinista**: mismas entradas ⇒ mismo `result_json` ⇒ mismo `result_checksum`.
  Sin aleatoriedad, sin hora del sistema, sin estado global.
- **Decimal**: se opera con `Decimal` y se cuantiza a 2 decimales (`ROUND_HALF_UP`), igual
  que mediciones y reportes; nunca `float` en el cálculo.
- **Sin acoplamiento fisiológico inventado**: cada métrica se mueve según su propio
  parámetro. No se "deriva" cintura desde peso ni se aplican ecuaciones corporales no
  verificadas. Esto es explícito en `engine_config` y en la UI.

### 4.2 Versionado

- `ENGINE_VERSION` (semver) se persiste en cada fila. **Regla:** cualquier cambio en la
  aritmética, el redondeo o los límites obliga a subir la versión (minor si cambia un
  límite, major si cambia la forma del resultado). Un resultado antiguo se explica siempre
  por su `engine_version` + `engine_config`.
- `engine_config` guarda: límite de delta, redondeo, `catalog` (min/max por métrica usados)
  y `coupled_metrics: false`. Un motor nuevo puede leer un resultado viejo sin ambigüedad.
- **Sin retroactividad**: no se recalculan escenarios antiguos al subir versión.

### 4.3 `result_json` (forma estable)

```json
{
  "engine": {"name": "bodyvision.scenario", "version": "1.0.0"},
  "data_kind": "simulation",
  "baseline_hash": "9f2c…",
  "metrics": {
    "waist": {
      "baseline": 88.00, "simulated": 83.60, "unit": "cm",
      "delta_absolute": -4.40, "delta_percent": -5.00,
      "mode": "delta_absolute", "input": -4.40, "clamped": false
    }
  },
  "derived": {
    "waist_height": {"baseline": 0.52, "simulated": 0.49, "delta_absolute": -0.03},
    "waist_hip":    {"baseline": 0.94, "simulated": 0.89, "delta_absolute": -0.05}
  },
  "unchanged": ["weight", "height", "chest", "arm", "thigh"],
  "warnings": ["escenario_hipotetico", "sin_criterio_clinico"]
}
```

`unchanged` hace explícito **qué no se tocó** (transparencia). `clamped` indica que el
resultado se acotó al rango del catálogo.

---

## 5. Parámetros soportados y rangos válidos

### 5.1 Métricas simulables

| Métrica | Unidad | Rango técnico (catálogo) | Simulable |
|---|---|---|---|
| `weight` | kg | 2 – 500 | Sí |
| `waist` | cm | 20 – 300 | Sí |
| `hip` | cm | 20 – 300 | Sí |
| `chest` | cm | 20 – 300 | Sí |
| `arm` | cm | 5 – 100 | Sí |
| `thigh` | cm | 10 – 150 | Sí |
| `height` | cm | 30 – 272 | **No** — sólo referencia para indicadores derivados |

`height` se excluye como parámetro: la estatura no es variable en un escenario de corto
plazo y usarla como entrada invita a resultados absurdos. Sí se usa (inmutable) para el
indicador `waist_height`.

### 5.2 Modos de parámetro

Uno por métrica, mutuamente excluyente:

| Modo | Entrada | Validación |
|---|---|---|
| `delta_absolute` | `value` en la unidad de la métrica | `|value| <= max_delta_pct% × base` (redondeado a 2 decimales) |
| `delta_percent` | `value` en % | `|value| <= max_delta_pct` |
| `target_value` | valor final en la unidad | resultado dentro del rango del catálogo |

Reglas transversales:

- **1 a 4 métricas** por escenario (`MIN_METRICS=1`, `MAX_METRICS=4`).
- `max_delta_pct` por defecto **30 %** (configurable con `SIMULATION_MAX_DELTA_PERCENT`,
  rango permitido 5–50).
- El resultado **siempre** se acota al rango del catálogo; si se acota, `clamped=true` y el
  escenario se marca como advertencia en la UI (no se rechaza, se informa).
- `value = 0` es válido en `delta_*` (escenario "sin cambio" para esa métrica) pero un
  escenario con **todas** las métricas en 0 se rechaza (`422`): no aporta información.
- La base debe existir para **cada** métrica simulada: si el expediente no tiene una medición
  vigente de `hip`, no se puede simular `hip` (`422` con mensaje explícito, igual que
  `metrics_without_data` en analítica).

### 5.3 Indicadores derivados (aritmética pura, no clínica)

- `waist_height = waist / height` (requiere ambas en base).
- `waist_hip = waist / hip` (requiere ambas).
- Se muestran como **"indicador aritmético del escenario"**, sin valores de referencia,
  sin semáforos y sin texto interpretativo.
- `BMI` no se incluye por defecto (decisión **D5**).

---

## 6. Referencia base inmutable (reglas duras)

1. **Sólo mediciones vigentes**: la base se toma de `measurements` donde la fila no está
   reemplazada (`supersedes_id` no apunta a ella) y pertenece al expediente de la ruta. Una
   fila corregida no puede ser base (`422`).
2. **Sin escritura sobre `measurements`**: el servicio de simulación sólo usa lecturas; no
   existe repositorio de escritura de mediciones en su grafo de dependencias. Además el
   trigger `trg_measurements_immutable` ya rechaza cualquier `UPDATE`.
3. **Snapshot + hash**: al crear el escenario se copian `measurement_id`, `value`,
   `unit`, `measured_at` a `simulation_baselines` y se calcula `baseline_hash` sobre el JSON
   canónico de ese conjunto (claves ordenadas). El hash permite demostrar *qué* base se usó
   aunque la fila cambie de estado "vigente" más adelante.
4. **Corrección posterior a la base**: como las mediciones son inmutables y versionadas, si
   después se corrige una medición base, el escenario **no se recalcula ni se reescribe**.
   La UI compara la base guardada con la medición vigente actual y muestra la insignia
   "base corregida después" (informativa, sin bloquear).
5. **Prueba de no-contaminación** (obligatoria): antes y después de crear+ejecutar un
   escenario se comparan `COUNT(*)`, `MAX(recorded_at)` y un checksum de las filas de
   `measurements` del expediente; deben ser idénticas. También se verifica que
   `/api/profiles/{id}/measurements` y la analítica devuelven exactamente lo mismo.

---

## 7. Ejecución y estados

```
        POST /simulations
               │
               ▼
   ┌──────┐  run   ┌────────┐  motor  ┌───────────┐
   │draft │───────►│ queued │────────►│ completed │──┐
   └──────┘        └────────┘         └───────────┘  │ archive
        │              │ fallo              ▲         ▼
        │              ▼                    │    ┌──────────┐
        └──────────► failed ◄───────────────┘    │ archived │
                     (reintento = nuevo POST)     └──────────┘
```

- `draft` sólo si se crea el escenario **sin ejecutar** (decisión **D6**).
- `failed` nunca se reintenta automáticamente (mismo criterio que Fase 5/7): se crea uno nuevo.
- `archived` es el único borrado lógico; no hay `DELETE`.
- **Stale**: `queued`/`processing` con `queued_at` más antiguo que
  `SIMULATION_STALE_PROCESSING_SECONDS` → `failed` con `error_message='queue_stale'`.

**Ejecución (decisión D1):**
- **Opción A (recomendada) — worker**: `POST` deja `queued` y responde `201`;
  `app/workers/simulation_worker.py` (patrón exacto de Fases 5/7, `FOR UPDATE SKIP LOCKED`)
  calcula y persiste `completed`. Script `backend/scripts/run-simulation-worker.ps1`
  (con `-Once`). Coherente con el resto del sistema y deja `queued` con significado real;
  el motor pesado (3D) cabría después sin cambiar el esquema. Coste: hace falta levantar un
  tercer worker.
- **Opción B — síncrona**: el motor corre dentro del `POST` y responde `completed` en la
  misma petición (`queued` quedaría como estado transitorio no persistido). Menos piezas,
  pero rompe la simetría con Fases 5 y 7 y desaprovecha el estado `queued` que pediste.

---

## 8. API, permisos y auditoría

| Método | Ruta | Permiso | Notas |
|---|---|---|---|
| `POST` | `/api/profiles/{id}/simulations` | `editor`+ | Crea (`draft`) o crea y encola. Audita `simulation.created` |
| `POST` | `/api/simulations/{id}/run` | `editor`+ | `draft`→`queued` (sólo si D6 activa borradores) |
| `GET` | `/api/profiles/{id}/simulations` | `viewer`+ | Paginado; filtro `status` |
| `GET` | `/api/simulations/{id}` | `viewer`+ | Incluye base, resultado y `data_kind` |
| `GET` | `/api/simulations/{id}/comparison` | `viewer`+ | Base vs escenario + derivados (§8.1) |
| `POST` | `/api/simulations/{id}/archive` | `owner` o autor | `completed`→`archived`. Audita `simulation.archived` |

**Reglas de acceso** (idénticas a Fases 4–7): `editor`+ **y** expediente `active` **y**
consentimiento `data_processing` vigente para crear/ejecutar; `viewer`+ para leer. El `admin`
**no** obtiene acceso implícito. Autoría fijada en el servidor (`created_by_user_id` +
`created_by_snapshot`), nunca desde el cliente.

**Auditoría** (`AuditAction` nuevos): `simulation.created`, `simulation.queued`,
`simulation.completed`, `simulation.failed`, `simulation.archived`, `simulation.viewed`,
`simulation.exported` (si D9 habilita reporte). `detail` incluye `engine_version`,
`baseline_hash`, `metrics` simuladas y `result_checksum` — nunca valores clínicos
interpretados.

### 8.1 Contrato del comparador

```json
{
  "simulation_id": "…", "profile_id": "…", "status": "completed",
  "data_kind": "simulation",
  "engine": {"name": "bodyvision.scenario", "version": "1.0.0"},
  "created_at": "…", "created_by": "Ana Torres",
  "baseline": {
    "captured_from": "measurements_vigentes",
    "hash": "9f2c…",
    "metrics": [{"metric_type": "waist", "value": 88.00, "unit": "cm",
                 "measured_at": "…", "measurement_id": "…",
                 "superseded_since": false}]
  },
  "scenario": {"metrics": [{"metric_type": "waist", "value": 83.60, "unit": "cm",
                            "delta_absolute": -4.40, "delta_percent": -5.00,
                            "clamped": false}]},
  "derived": [{"key": "waist_height", "baseline": 0.52, "simulated": 0.49}],
  "unchanged": ["weight", "height"],
  "disclaimer": "Escenario hipotético…"
}
```

La `baseline` se **relee** de las mediciones al servir el comparador (sólo para detectar
correcciones posteriores mediante `superseded_since`); los valores del escenario salen
siempre de `result_json`, nunca se recalculan al vuelo.

---

## 9. Aislamiento estricto respecto a lo observado

1. `data_kind='simulation'` es **columna con CHECK**, no un campo libre.
2. Tabla separada: `simulations` **no** tiene `metric_type/value/unit` en columnas propias;
   esos valores viven en JSON y en la tabla hija de base. Ningún `JOIN` de analítica,
   reportes o dashboard toca `simulations`.
3. Analítica (`/analytics`), reportes (`measurements_*`) y dashboard **no cambian** su
   comportamiento: los escenarios no aparecen en `trends`, ni en el CSV/PDF de mediciones,
   ni en `measurements_total`.
4. La serie observada del expediente (`MetricChart`) **nunca** recibe puntos de escenario;
   el comparador es una vista propia con tabla y barras discontinuas.
5. Tests de aislamiento obligatorios: `measurements` sin cambios tras simular; analítica
   idéntica; `/api/reports` no acepta `kind` de simulación; dashboard sin cambios.
6. Etiqueta permanente en UI: `DataKindBadge kind="simulation"` (ya existe, cian
   discontinuo) + banner fijo de escenario hipotético montado a nivel de layout de la ruta.

---

## 10. Frontend

- **`SideNav`**: `Simulador` pasa de deshabilitado ("Fase 8") a activo → `/simulations`.
- **Rutas**: `/simulations` (lista de escenarios del usuario, patrón `/reports`),
  `/simulations/:profileId` (workspace: elegir base, parámetros y comparador),
  opcional `/simulations/:profileId/:simulationId` (detalle enlazable).
- **Workspace** (`features/simulations/`):
  - Columna base: métricas vigentes con fecha y unidad, botón "Usar como base".
  - Editor de parámetros: por métrica, selector de modo + campo numérico con `min/max`
    derivados de la regla `max_delta_pct` y del catálogo; 1–4 métricas.
  - **Previsualización**: sólo tras la respuesta del servidor (no se duplica el motor en el
    cliente, para que no haya dos verdades distintas). Mientras tanto, estado "en cola" con
    refresco automático (mismo patrón que `/reports`).
  - **Comparador**: tabla base vs escenario por métrica (valor, Δ absoluto, Δ %), fila de
    indicadores derivados y lista `unchanged`. Barras comparativas con patrón discontinuo y
    leyenda "observado / hipotético". Sin líneas temporales ni extrapolación.
  - **Aviso permanente** en cabecera de la vista y en cada tarjeta:
    "ESCENARIO HIPOTÉTICO: no describe el cuerpo real, no es una predicción y no modifica
    tus mediciones."
- **Reutilización**: `global.css` ya tiene `.kind-badge--simulation` (cian discontinuo),
  `forms.css` los campos/botones y `pose.css`/`reports.css` los patrones de lista y panel.

---

## 11. Configuración y scripts (Windows)

`.env.example` / `Settings`:

```
SIMULATION_MAX_DELTA_PERCENT=30
SIMULATION_POLL_SECONDS=5
SIMULATION_STALE_PROCESSING_SECONDS=1800
SIMULATION_MAX_ACTIVE_PER_PROFILE=20
```

Scripts nuevos: `backend/scripts/run-simulation-worker.ps1` (`-Once` para un lote), mismo
formato que `run-worker.ps1` y `run-report-worker.ps1`.

---

## 12. Plan de tests y verificación (previsto)

- **Dominio** (`tests/test_simulation_domain.py`): rangos y acotado (`clamped`), % vs
  absoluto, rechazo de `height`, `target_value` fuera de rango, determinismo (mismo input ⇒
  mismo checksum), base incompleta, todas las métricas en 0, versión en la salida.
- **Servicio** (`tests/test_simulation_service.py`): permisos (`viewer` no crea), expediente
  archivado, consentimiento revocado, base corregida (`422`), base de otro expediente
  (`404`), archivar sólo `completed`, **no-contaminación de `measurements`**.
- **Worker** (`tests/test_simulation_worker.py`): claim, stale, fallo del motor → `failed`
  con `error_message`, idempotencia del claim.
- **API** (`tests/test_simulation_api.py`): contrato del comparador, `data_kind=simulation`,
  409/422 correspondientes, aislamiento (analítica, reportes y dashboard sin cambios).
- **Cierre**: `pytest -q`, `ruff check .`, `npm run lint`, `npm run build`, y validación
  manual en Windows + PostgreSQL con `alembic upgrade head` (0008) / `downgrade 0007`.

---

## 13. Decisiones a confirmar

| # | Decisión | Recomendación | Alternativas |
|---|---|---|---|
| **D1** | Ejecución del motor | **Worker** (`queued` real, patrón Fases 5/7) | Síncrona en el `POST` |
| **D2** | Modos de parámetro | `delta_absolute` + `delta_percent` (+ `target_value` opcional) | Sólo `delta_*` / sólo `target_value` |
| **D3** | Límite de cambio | **30 %** por métrica, configurable 5–50 | 20 % (más conservador) / 40 % |
| **D4** | ¿El visor 3D deforma la malla? | **No** en 8A: el visor sigue siendo genérico y el escenario es numérico | Malla derivada etiquetada / silueta 2D |
| **D5** | Indicadores derivados | `waist_height` + `waist_hip`; **sin BMI** | Incluir BMI / ninguno |
| **D6** | Borradores (`draft`) | **Sí**: guardar sin ejecutar y ejecutar luego | Sin `draft`: crear = encolar |
| **D7** | ¿Quién archiva? | **Propietario o autor** del escenario | Sólo propietario / cualquier `editor` |
| **D8** | Contador de escenarios en el dashboard | **No** cambiar el dashboard en Fase 8 | Añadir `simulations_total` como campo aparte |
| **D9** | Reportes de simulación | **Ninguno** en Fase 8 (evita mezclar en `/reports`) | `simulation_pdf` con `data_kind=simulation` |
| **D10** | Límite por expediente | 20 activos (`SIMULATION_MAX_ACTIVE_PER_PROFILE`) | Sin límite / 10 |

Si no indicas lo contrario, aplico las recomendaciones de la columna central y lo dejo
documentado en **ADR-009**.

---

## 14. Riesgos y compromisos asumidos

- **Interpretación**: un comparador numérico puede leerse como pronóstico. Mitigación: aviso
  permanente, `DataKindBadge`, sin curvas temporales, sin recomendaciones y textos en
  español que dicen explícitamente que no describe el cuerpo real.
- **Falsa precisión**: los escenarios son aritmética exacta sobre datos con error de medida;
  se redondea a 2 decimales y no se derivan métricas no medidas (sin ecuaciones corporales).
- **Tercer worker**: si no está levantado, los escenarios quedan "en cola" y la UI lo indica
  (mismo comportamiento ya validado en Fase 7).
- **Corrección posterior de la base**: el escenario queda con la base histórica y se marca
  "base corregida después"; no se recalcula para no reescribir un resultado auditado.
