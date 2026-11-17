$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 -m venv .venv
    } else {
        python -m venv .venv
    }
}

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-dev.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado backend/.env. Revisa la contraseña de DATABASE_URL (debe coincidir con la raíz)." -ForegroundColor Yellow
}

& $python --version
Write-Host "Entorno listo." -ForegroundColor Green