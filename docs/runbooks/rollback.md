# Runbook · Rollback

**Objetivo:** volver a la versión anterior con el menor tiempo posible. **Decisión clave:** ¿la
migración es reversible?

## Clasificación de la migración

| Tipo | Cómo se reconoce | Estrategia |
|---|---|---|
| **Aditiva** | Solo `create_table`/`add_column` con NULL o default | `alembic downgrade -1` + imagen anterior. Seguro. |
| **Destructiva** | `drop_column`, `drop_table`, cambio de tipo con pérdida | **Downgrade no recupera datos**: restaurar backup completo |
| **De datos** | `op.execute` con `UPDATE`/`DELETE` | Igual que destructiva |

Antes de desplegar, anotar en la release si la migración es aditiva o destructiva.

## Rollback de código (migración aditiva)

```bash
# 1. Detener la API y los workers (la BD se queda)
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop backend \
  worker-pose worker-report worker-simulation frontend

# 2. Revertir la migración
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --entrypoint python migrate \
  -m alembic downgrade -1
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --entrypoint python migrate \
  -m alembic current

# 3. Volver a la imagen anterior
git checkout <tag-anterior>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Rollback con restauración (migración destructiva)

```powershell
# 1. Detener TODO
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# 2. Restaurar el backup previo al despliegue en la base real
powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 `
  -From D:\backups\<ts-anterior> -Force

# 3. Levantar la versión anterior
git checkout <tag-anterior>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Verificación post-rollback

- [ ] `/api/health/ready` 200.
- [ ] `/api/health/workers` con los 3 workers vivos.
- [ ] Login + abrir un expediente + descargar un reporte.
- [ ] `alembic current` coincide con la revisión esperada.
- [ ] Conteo de `measurements` igual al del backup (no se perdió nada).

## Post-mortem

Anotar: causa raíz, tiempo de detección, tiempo de recuperación, datos afectados (si hubo) y
acción preventiva. Sin post-mortem, el incidente se repetirá.
