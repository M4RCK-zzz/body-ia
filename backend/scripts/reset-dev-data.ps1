$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { Write-Error "No existe .env en la raíz del repo." }

$cfg = @{}
Get-Content $envFile -Encoding UTF8 | ForEach-Object {
    if ($_ -notmatch '^\s*#' -and $_ -match '^\s*([A-Za-z_]+)\s*=\s*(.*?)\s*$') {
        $cfg[$Matches[1]] = $Matches[2].Trim('"')
    }
}
$dbUser = $cfg["POSTGRES_USER"]; $dbName = $cfg["POSTGRES_DB"]
if (-not $dbUser -or -not $dbName) { Write-Error "Faltan POSTGRES_USER o POSTGRES_DB en .env." }

Write-Host "Esto borrará TODOS los expedientes y mediciones (y accesos/consentimientos)" -ForegroundColor Yellow
Write-Host "de la base '$dbName'. Los usuarios y la auditoría se conservan."
if ((Read-Host "Escribe BORRAR para continuar") -ne "BORRAR") { Write-Host "Cancelado."; exit 1 }

docker compose exec -T db psql -U $dbUser -d $dbName -v ON_ERROR_STOP=1 `
    -c "TRUNCATE TABLE measurements, profiles CASCADE;"
if ($LASTEXITCODE -ne 0) { Write-Error "No se pudo vaciar la base." }
Write-Host "Listo. Ahora ejecuta .\scripts\migrate.ps1" -ForegroundColor Green