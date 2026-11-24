# Runbook · Backup y restauración

**Objetivo de recuperación (D11): RPO 24 h · RTO 2 h.**
Un backup no verificado no es un backup: la restauración de ensayo es parte del procedimiento.

## Qué se guarda

| Artefacto | Contenido | Por qué |
|---|---|---|
| `db.dump` | `pg_dump -Fc` de toda la base | Datos estructurados |
| `storage.tar` | `UPLOAD_DIR` completo | Imágenes y binarios de reportes **no están en PostgreSQL** |
| `manifest.json` | SHA-256 de cada artefacto, revisión Alembic, conteos por tabla | Demuestra integridad |

## Backup

**Windows**
```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -OutDir D:\backups -Keep 14
# Contra el contenedor (sin pg_dump en el host):
powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -UseDocker
```

**Linux**
```bash
bash backend/scripts/backup.sh                     # con pg_dump en el host
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
```

**En contenedor (sin cliente de PostgreSQL en el host).** Los servicios `backup` y
`restore` se construyen desde `docker/ops.Dockerfile` (`postgres:16.6-alpine` +
`pg_dump`/`pg_restore`/`psql`), no desde la imagen de la API, que no trae el cliente.

**Programación:** Programador de tareas (Windows) o `cron` (Linux) una vez al día, en hora
valle. Ejemplo de cron:

```
0 3 * * * cd /opt/bodyvision && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup >> /var/log/bodyvision-backup.log 2>&1
```

## Restauración de ensayo (obligatoria)

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 `
  -From D:\backups\20260101T030000Z -TargetDatabase bodyvision_qa
```
```bash
bash backend/scripts/restore.sh /backups/20260101T030000Z --target bodyvision_qa
# En contenedor: la carpeta es la del bind mount `./backups`; sin argumento usa la
# más reciente de $BACKUP_DIR.
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm restore --target bodyvision_qa
```

Qué comprueba el script, en este orden:

1. SHA-256 de `db.dump` y `storage.tar` contra el manifiesto → **aborta si no coincide**.
2. Crea una base **nueva** (no toca la de producción sin `-Force`).
3. `pg_restore --exit-on-error`.
4. Conteos por tabla contra el manifiesto → **aborta si hay descuadre**.
5. Imprime la revisión de Alembic restaurada.
6. Extrae el storage en `<UPLOAD_DIR>.restored-<ts>`: nunca borra el actual.

## Restauración real

1. Detener API y workers (`docker compose ... stop backend worker-pose worker-report
   worker-simulation frontend`; Compose no expande comodines en nombres de servicio).
2. Ejecutar el restore con `-Force` (o `--force`) sobre la base de la app.
3. Sustituir el directorio de storage por el extraído, tras revisarlo.
4. Levantar y verificar con `/api/health/ready` y el checklist funcional.

## Retención

7 diarios · 4 semanales · 12 mensuales (ajustar `-Keep` / `BACKUP_KEEP`). Los backups deben
vivir **fuera** del servidor de la aplicación: un disco que muere se lleva los datos y las
copias.
