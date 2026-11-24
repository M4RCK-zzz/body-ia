# Runbook · Worker caído o cola atascada

## Síntoma

- `/api/health/workers` muestra `alive: false` o `status: degraded`.
- Elementos en `En cola` que no avanzan (reportes, simulaciones, pose).
- `/api/health/ready` sigue en 200: la API está bien, el problema es el worker.

## Diagnóstico

```bash
# 1. ¿El proceso está vivo?
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps \
  worker-pose worker-report worker-simulation

# 2. Últimos logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 100 worker-report

# 3. Latidos en BD
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  psql -U bodyvision -d bodyvision -c \
  "SELECT name, worker_version, last_seen_at, iterations, last_error FROM worker_heartbeats ORDER BY name;"

# 4. Cola pendiente
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  psql -U bodyvision -d bodyvision -c \
  "SELECT status, count(*) FROM reports GROUP BY status;
   SELECT status, count(*) FROM simulations GROUP BY status;
   SELECT status, count(*) FROM pose_analyses GROUP BY status;"
```

## Causas frecuentes y solución

| Causa | Señal | Solución |
|---|---|---|
| Worker detenido | Sin fila en `worker_heartbeats` o `last_seen_at` viejo | `up -d worker-<x>` |
| Worker colgado en el modelo | `alive: false` pero el proceso está | `restart worker-pose` |
| Falta el modelo de pose | Log `No se puede arrancar el worker de pose` | Montar `backend/models/pose_landmarker_full.task` |
| Tareas `processing` huérfanas | `started_at` antiguo | El worker las pasa a `failed` con `processing_stale` al arrancar |
| Cola `queued` obsoleta | `queued_at` antiguo | Se marca `failed` con `queue_stale` |
| Disco lleno | `health/ready` con `storage: false` | `docs/runbooks/disk-full.md` |

## Tras la recuperación

- [ ] `/api/health/workers` con `status: ok`.
- [ ] La cola drena (los contadores de `queued` bajan).
- [ ] Un elemento nuevo procesa de principio a fin.

**Nota:** ningún elemento se reintenta automáticamente (decisión de fases 5/7/8). Un `failed`
requiere acción del usuario; los `*_stale` los recupera el worker al arrancar.

**`retention` no es un worker caído.** Se ejecuta como one-shot (`--once`, desde cron o a
mano); en `/api/health/workers` aparece con `continuous: false` y su último latido es
informativo: no altera `status` ni dispara `degraded`.
