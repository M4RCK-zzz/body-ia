# Worker de simulación (Fase 8) — Windows
# Uso continuo:      powershell -ExecutionPolicy Bypass -File backend\scripts\run-simulation-worker.ps1
# Un lote y salir:   powershell -ExecutionPolicy Bypass -File backend\scripts\run-simulation-worker.ps1 -Once
#
# Calcula los escenarios hipotéticos solicitados desde la API. El motor es
# determinista y NUNCA escribe en la tabla `measurements`: sólo lee la fotografía
# guardada en `simulation_baselines`. Se detiene con Ctrl+C.

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

# Reutiliza el .env del backend (DATABASE_URL, JWT_SECRET, SIMULATION_*).
# No necesita el modelo de pose ni fpdf2: sólo aritmética con Decimal.
if ($Once) {
    & $VenvPython -m app.workers.simulation_worker --once
} else {
    Write-Host "Worker de simulación en marcha. Ctrl+C para detenerlo." -ForegroundColor Cyan
    & $VenvPython -m app.workers.simulation_worker
}
