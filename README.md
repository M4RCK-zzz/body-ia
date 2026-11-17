# BODYVISION AI

Plataforma paramétrica de análisis, captura y simulación 3D de mediciones corporales **hipotéticas**.
**No emite diagnósticos médicos.** Toda salida de IA es una *estimación visual*; toda simulación es un
*escenario hipotético* separado de las mediciones reales.

## Requisitos
- Docker Desktop (PostgreSQL)
- Python 3.11 (backend, `venv`)
- Node 20 LTS + npm

## 1. Base de datos
```powershell
Copy-Item .env.example .env        # edita POSTGRES_PASSWORD (solo letras y números)
docker compose up -d db
docker compose ps                  # debe mostrar "healthy"