# Worker de análisis de pose (Fase 5/9).
#
# MediaPipe + OpenCV necesitan bibliotecas del sistema que la imagen de la API
# no lleva. Se separan para no cargar a la API con ~400 MB de dependencias que
# nunca usa (decisión D2).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app backend/ /app/

RUN mkdir -p /app/storage /app/models && chown -R app:app /app/storage /app/models

USER app

# Healthcheck: el propio heartbeat en BD es la señal real (lo lee
# /api/health/workers); aquí solo se comprueba que el proceso sigue vivo.
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import app.workers.pose_worker" || exit 1

CMD ["python", "-m", "app.workers.pose_worker"]
