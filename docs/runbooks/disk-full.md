# Runbook · Disco lleno

## Síntoma

- `/api/health/ready` → `503` con `storage: false` (la prueba de escritura falla).
- Subidas que devuelven 500; reportes que fallan al escribir el PDF.
- PostgreSQL puede empezar a dar errores de escritura del WAL.

## Diagnóstico

```bash
df -h                                     # espacio por volumen
docker system df                          # imágenes, contenedores y volúmenes
du -sh /var/lib/docker/volumes/bodyvision_storage/_data   # storage de la app
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 50 backend
```

## Qué se puede borrar sin pensar

| Elemento | Seguridad |
|---|---|
| Imágenes Docker sin usar | Seguro: `docker image prune -a` |
| Contenedores parados | Seguro: `docker container prune` |
| Logs rotados de Docker | Seguro (ya limitados a 10 MB × 5 por servicio) |
| Backups antiguos | Seguro si hay uno reciente **verificado** |
| `storage` de la app | **Nunca a mano**: usar el worker de retención |

## Qué NO se borra nunca

- El volumen de PostgreSQL (`bodyvision_pgdata`).
- `backend/models/` (modelo de MediaPipe; habría que volver a descargarlo).
- `audit_events` ni `measurements`.

## Liberar con retención (forma correcta)

```bash
# 1. Ver qué borraría (DRY RUN, por defecto)
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm retention --once

# 2. Revisar el log y, si es correcto, purgar de verdad
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm retention --once --apply
```

## Prevención

- Alertar al 80 % de uso del volumen.
- `MEDIA_RETENTION_DAYS`, `REPORT_RETENTION_DAYS` y `SIMULATION_RETENTION_DAYS` ajustados a la
  política real.
- Programar `retention --once --apply` (perfil `ops`) una vez al día.
