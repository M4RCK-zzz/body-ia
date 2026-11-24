#!/usr/bin/env bash
# Backup de PostgreSQL + storage privado (Fase 9). Equivalente Linux/macOS de
# backup.ps1, pensado para ejecutarse dentro del contenedor `backup` de
# docker-compose.prod.yml (perfil "ops") o desde un host con pg_dump.
#
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#     run --rm backup
#
# Produce, en $BACKUP_DIR/<UTC timestamp>/: db.dump, storage.tar, manifest.json
# El manifiesto lleva SHA-256 y conteos por tabla para verificar la restauración.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/$STAMP"
DB_NAME="${POSTGRES_DB:-bodyvision}"
DB_USER="${POSTGRES_USER:-bodyvision}"
DB_HOST="${POSTGRES_HOST:-db}"
UPLOAD_DIR="${UPLOAD_DIR:-/app/storage}"

mkdir -p "$TARGET"
echo "== Backup BODYVISION AI =="
echo "Destino: $TARGET"

# 1. Volcado de PostgreSQL (formato custom: permite restauración selectiva).
pg_dump -h "$DB_HOST" -U "$DB_USER" -Fc --no-owner -f "$TARGET/db.dump" "$DB_NAME"
pg_restore --list "$TARGET/db.dump" > /dev/null   # verifica que es legible
SIZE=$(stat -c%s "$TARGET/db.dump")
if [ "$SIZE" -lt 1024 ]; then
  echo "ERROR: volcado sospechosamente pequeño ($SIZE bytes)" >&2
  exit 1
fi

# 2. Storage privado (imágenes y binarios de reportes: NO están en PostgreSQL).
if [ -d "$UPLOAD_DIR" ]; then
  tar -cf "$TARGET/storage.tar" -C "$UPLOAD_DIR" .
else
  echo "Aviso: $UPLOAD_DIR no existe; storage vacío"
  tar -cf "$TARGET/storage.tar" --files-from /dev/null
fi

# 3. Manifiesto con checksums y conteos.
TABLES="users profiles measurements media_assets pose_analyses reports simulations simulation_baselines audit_events worker_heartbeats"
{
  echo "{"
  echo "  \"generated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"database\": \"$DB_NAME\","
  echo "  \"artifacts\": {"
  echo "    \"db\": {\"file\": \"db.dump\", \"bytes\": $SIZE, \"sha256\": \"$(sha256sum "$TARGET/db.dump" | cut -d' ' -f1)\"},"
  echo "    \"storage\": {\"file\": \"storage.tar\", \"bytes\": $(stat -c%s "$TARGET/storage.tar"), \"sha256\": \"$(sha256sum "$TARGET/storage.tar" | cut -d' ' -f1)\"}"
  echo "  },"
  echo "  \"table_counts\": {"
  first=1
  for table in $TABLES; do
    count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT count(*) FROM $table" 2>/dev/null || echo "null")
    [ $first -eq 0 ] && echo ","
    printf '    "%s": %s' "$table" "$count"
    first=0
  done
  echo ""
  echo "  }"
  echo "}"
} > "$TARGET/manifest.json"

# 4. Rotación: conserva los últimos $BACKUP_KEEP directorios (default 7).
KEEP="${BACKUP_KEEP:-7}"
if [ "$KEEP" -gt 0 ]; then
  ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
    echo "Rotando: $old"
    rm -rf "$old"
  done
fi

echo "Backup completado: $TARGET"
