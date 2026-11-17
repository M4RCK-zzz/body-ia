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