# Imagen de operación (Fase 9): backup/restore del stack.
#
# Por qué una imagen aparte y no la de la API: los scripts necesitan
# `pg_dump`, `pg_restore` y `psql` de la **misma versión mayor** que el servidor
# (PostgreSQL 16). La imagen de la API es `python:3.13-slim` (Debian bookworm, con
# cliente 15 si se instalara desde apt), así que se parte de la imagen oficial de
# PostgreSQL 16 y se le añade lo mínimo: bash (los scripts son Bash estricto) y
# python3 (lectura del manifiesto en `restore.sh`).
FROM postgres:16.6-alpine

RUN apk add --no-cache bash python3 \
    && addgroup -g 10001 -S app \
    && adduser -u 10001 -S -G app -h /home/app -s /sbin/nologin app

WORKDIR /app
COPY --chown=app:app backend/scripts/ /app/scripts/

USER app

HEALTHCHECK NONE
CMD ["bash", "/app/scripts/backup.sh"]
