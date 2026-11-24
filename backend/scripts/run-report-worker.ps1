# Worker de reportes (Fase 7) — Windows
# Uso continuo:      powershell -ExecutionPolicy Bypass -File backend\scripts\run-report-worker.ps1
# Un lote y salir:   powershell -ExecutionPolicy Bypass -File backend\scripts\run-report-worker.ps1 -Once
#
# Genera los CSV/PDF solicitados desde la API. El binario se escribe en el storage
# privado (UPLOAD_DIR); PostgreSQL solo guarda la clave y el checksum SHA-256.
# El worker se detiene con Ctrl+C.

param(
    [switch]$Once
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendDir = Join-Path $RepoRoot 'backend'
Set-Location $BackendDir

$VenvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creando entorno virtual backend\.venv ..." -ForegroundColor Yellow
    python -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
} else {
    & $VenvPython -m pip install -r requirements.txt
}

# Reutiliza el .env del backend (DATABASE_URL, JWT_SECRET, UPLOAD_DIR, REPORT_*).
# No necesita el modelo de pose: los reportes de pose solo exportan metadatos
# de análisis ya calculados.
if ($Once) {
    & $VenvPython -m app.workers.report_worker --once
} else {
    Write-Host "Worker de reportes en marcha. Ctrl+C para detenerlo." -ForegroundColor Cyan
    & $VenvPython -m app.workers.report_worker
}
