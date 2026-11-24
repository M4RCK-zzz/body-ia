#!/usr/bin/env bash
# Restauración de PostgreSQL + storage (Fase 9). Equivalente Linux/macOS de
# restore.ps1. Restaura SIEMPRE en una base nueva salvo que se pase --force.
#
#   ./restore.sh /backups/20260101T030000Z                       # ensayo
#   ./restore.sh /backups/20260101T030000Z --force --target bodyvision  # real
#
# Sin argumentos de carpeta usa el backup más reciente en $BACKUP_DIR.
set -euo pipefail

FROM="${1:-}"
shift || true
FORCE=0
TARGET_DB=""
SKIP_STORAGE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --force) FORCE=1 ;;
    --target) TARGET_DB="$2"; shift ;;
    --skip-storage) SKIP_STORAGE=1 ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_NAME="${POSTGRES_DB:-bodyvision}"
DB_USER="${POSTGRES_USER:-bodyvision}"
DB_HOST="${POSTGRES_HOST:-db}"
UPLOAD_DIR="${UPLOAD_DIR:-/app/storage}"

if [ -z "$FROM" ]; then
  FROM="$(ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | head -n 1)"
  FROM="${FROM%/}"
fi
[ -n "$FROM" ] && [ -d "$FROM" ] || { echo "No existe el backup: '$FROM'" >&2; exit 1; }
[ -f "$FROM/manifest.json" ] || { echo "Falta manifest.json" >&2; exit 1; }

TARGET_DB="${TARGET_DB:-${DB_NAME}_restore}"
if [ "$TARGET_DB" = "$DB_NAME" ] && [ "$FORCE" -ne 1 ]; then
  echo "Restaurar sobre '$DB_NAME' exige --force y la API parada." >&2
  exit 1
fi

echo "== Restauración BODYVISION AI =="
# 1. Integridad: SHA-256 de cada artefacto contra el manifiesto.
for file in db.dump storage.tar; do
  expected=$(python3 -c "import json,sys; print(json.load(open('$FROM/manifest.json'))['artifacts']['${file%%.*}']['sha256'])")
  actual=$(sha256sum "$FROM/$file" | cut -d' ' -f1)
  [ "$expected" = "$actual" ] || { echo "SHA-256 no coincide en $file" >&2; exit 1; }
  echo "  $file OK"
done

# 2. Base de datos.
EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname='$TARGET_DB'")
if [ "$EXISTS" = "1" ]; then
  [ "$FORCE" -eq 1 ] || { echo "La base '$TARGET_DB' ya existe (usa --force)" >&2; exit 1; }
  psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "DROP DATABASE \"$TARGET_DB\" WITH (FORCE)"
fi
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$TARGET_DB\""
pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$TARGET_DB" --no-owner --exit-on-error "$FROM/db.dump"

# 3. Conteos contra el manifiesto.
python3 - "$FROM/manifest.json" <<'PY' > /tmp/expected_counts.txt
import json, sys
counts = json.load(open(sys.argv[1]))["table_counts"]
for table, count in counts.items():
    if count is not None:
        print(f"{table} {count}")
PY
MISMATCH=0
while read -r table expected; do
  actual=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM $table")
  if [ "$actual" != "$expected" ]; then
    echo "  DESCUADRE $table: esperado=$expected obtenido=$actual" >&2
    MISMATCH=1
  fi
done < /tmp/expected_counts.txt
[ "$MISMATCH" -eq 0 ] || { echo "La restauración no cuadra" >&2; exit 1; }
echo "  Conteos idénticos"
psql -h "$DB_HOST" -U "$DB_USER" -d "$TARGET_DB" -t -A -c "SELECT 'Alembic: ' || version_num FROM alembic_version"

# 4. Storage: se extrae en un directorio nuevo, nunca encima del actual.
if [ "$SKIP_STORAGE" -eq 0 ]; then
  STAGED="$UPLOAD_DIR.restored-$(date -u +%Y%m%d%H%M%S)"
  mkdir -p "$STAGED"
  tar -xf "$FROM/storage.tar" -C "$STAGED"
  echo "Storage extraído en $STAGED (sustitúyelo a mano tras revisarlo)"
fi

echo "Restauración verificada."
