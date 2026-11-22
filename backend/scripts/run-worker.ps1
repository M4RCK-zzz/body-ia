# Worker de análisis de pose (Fase 5) — Windows
# Uso:  powershell -ExecutionPolicy Bypass -File backend\scripts\run-worker.ps1
# Prerrequisitos: ver README.md ("Análisis de pose") sección "Descarga del modelo".
# El worker se detiene con Ctrl+C.

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

# El script reutiliza el .env del backend (DATABASE_URL, JWT_SECRET, POSE_MODEL_PATH)
if (-not (Test-Path 'models\pose_landmarker_full.task')) {
    Write-Host "ERROR: Modelo no encontrado en backend\models\pose_landmarker_full.task" -ForegroundColor Red
    Write-Host "Sigue las instrucciones del README: sección 'Análisis de pose' → 'Descarga del modelo'."
    exit 2
}

& $VenvPython -m app.workers.pose_worker
