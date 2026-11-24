# Runbook · Base de datos no disponible

## Síntoma

- `/api/health/ready` → `503` con `database: false`.
- Errores 500 con `OperationalError`/`connection refused` en los logs.
- Los workers no laten (`health/workers` degradado).

## Diagnóstico

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps db
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 100 db
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  pg_isready -U bodyvision -d bodyvision
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  psql -U bodyvision -d bodyvision -c "SELECT 1;"
```

## Causas y solución

| Causa | Señal en el log | Solución |
|---|---|---|
| Contenedor parado | `ps` sin `db` | `up -d db` |
| Credenciales mal | `password authentication failed` | Revisar `POSTGRES_PASSWORD` en `.env.prod` |
| Conexiones agotadas | `too many clients already` | Subir `max_connections` o cerrar las ociosas |
| Disco lleno | `No space left on device` | `docs/runbooks/disk-full.md` |
| Corrupción | `invalid page` / `PANIC` | **No improvisar**: restaurar desde backup (`backup-restore.md`) |

## Conexiones ociosas (síntoma habitual)

```sql
SELECT pid, usename, state, query_start, left(query, 80)
FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '30 minutes';

-- Terminar solo las claramente huérfanas y de la app
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '30 minutes'
  AND usename = 'bodyvision';
```

## Recuperación

1. Restablecer `db` y confirmar `pg_isready`.
2. `docker compose ... restart backend worker-pose worker-report worker-simulation`
   (Compose no expande comodines: hay que nombrarlos).
3. `/api/health/ready` 200 y `/api/health/workers` con los 3 vivos.
4. Verificar integridad: `SELECT count(*) FROM measurements;` coincide con lo esperado.

**Nunca** se restaura un backup por un corte transitorio: primero se agota el diagnóstico.
