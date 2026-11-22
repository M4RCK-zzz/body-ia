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

## Fase 4 - Captura corporal (segura)

Las fotos son **material de referencia**, no mediciones. Flujo:

1. Entras en **Captura corporal** (icono del menú lateral).
2. Seleccionas un expediente y revisas la **guía de encuadre** (no se valida calidad; orientación).
3. **Subes** el archivo: JPEG / PNG / WebP, máx. 10 MB. El backend lo valida, transfolia (EXIF), borra metadatos/GPS y re-encodea. Los rechazos se persisten como registros con motivo.
4. Ves la lista de capturas del expediente con su estado (ready/rejected/deleted), dimensiones, tamaño, check de integridad y retención. Solo `ready` descargable vía endpoint autenticado.
5. Los bytes viven en `backend/storage/` (privado, chmod 600, clave aleatoria sin nombres), nunca en el navegador.

Subida y borrado requieren: acceso **owner/editor** + consentimiento `data_processing` vigente + expediente **active**. Los **viewers** solo leen.

### Verificación
```powershell
# Backend (desde backend/)
python -m pytest                 # 154 tests
ruff check app/ tests/          # ruff (B008 conocido en rutas FastAPI)
# Frontend (desde frontend/)
npm run build && npm run lint
# Smoke (API local, arriba)
powershell -ExecutionPolicy Bypass -File scripts/smoke_phase4.ps1
```
Nota: esta máquina (Linux sandbox) no tiene Postgres/Docker; la verificación E2E contra Postgres (`alembic upgrade head`, smoke real) se ejecuta en Windows con la BD arriba.
