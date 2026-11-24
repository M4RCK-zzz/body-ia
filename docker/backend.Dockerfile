# Imagen de la API BODYVISION AI (Fase 9).
#
# Multi-stage: las dependencias se compilan en `builder` y solo el resultado
# pasa a la imagen final, sin compiladores ni caché de pip.
#
# Esta imagen NO incluye las librerías de sistema que necesita MediaPipe
# (`libgl1`, `libglib2.0-0`): el worker de pose usa `worker-pose.Dockerfile`.
# Una imagen más pequeña es una superficie de ataque más pequeña.
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY backend/requirements.txt ./requirements.txt
RUN pip install --prefix=/install -r requirements.txt

# --- imagen final ------------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    WEB_CONCURRENCY=2

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=app:app backend/ /app/

# El storage privado y los modelos se montan como volúmenes: nunca dentro de la
# imagen (son datos de usuario y binarios pesados).
RUN mkdir -p /app/storage /app/models && chown -R app:app /app/storage /app/models

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=4).status == 200 else 1)"

# Sin `--reload` y sin migraciones en el arranque: `docker compose` ejecuta el
# servicio one-shot `migrate` antes de levantar la API (decisión D3).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
