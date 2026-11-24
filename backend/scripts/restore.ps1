# Restauración de PostgreSQL + storage (Fase 9).
#
# Uso (Windows, desde la raíz del repo):
#   # Ensayo: restaura en una base NUEVA y compara conteos con el manifiesto
#   powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 -From backups\20260101T030000Z -TargetDatabase bodyvision_restore
#
#   # Restauración real sobre la base de la app (exige -Force y la API parada)
#   powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 -From ... -Force
#
# Reglas de seguridad:
#   1. Sin `-Force` NUNCA escribe en la base en uso: restaura en `-TargetDatabase`.
#   2. Verifica el SHA-256 de cada artefacto antes de tocar nada.
#   3. Compara los conteos por tabla con el manifiesto y falla si no cuadran.
#   4. El storage se restaura en un directorio nuevo; nunca borra el actual.

param(
    [Parameter(Mandatory = $true)][string]$From,
    [string]$TargetDatabase = "",
    [string]$EnvFile = ".env.prod",
    [switch]$Force,
    [switch]$SkipStorage
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

if (-not (Test-Path $From)) { throw "No existe la carpeta de backup: $From" }
$manifestPath = Join-Path $From "manifest.json"
if (-not (Test-Path $manifestPath)) { throw "Falta manifest.json en $From" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json

function Read-EnvFile([string]$Path) {
    if (-not (Test-Path $Path)) { throw "No existe $Path" }
    $map = @{}
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $map[$Matches[1]] = $Matches[2].Trim().Trim('"')
        }
    }
    return $map
}

$envMap = Read-EnvFile $EnvFile
$dbUser = if ($envMap['POSTGRES_USER']) { $envMap['POSTGRES_USER'] } else { "bodyvision" }
$dbName = if ($envMap['POSTGRES_DB']) { $envMap['POSTGRES_DB'] } else { "bodyvision" }
$dbPass = $envMap['POSTGRES_PASSWORD']
if (-not $dbPass) { throw "POSTGRES_PASSWORD no está en $EnvFile" }

if (-not $TargetDatabase) { $TargetDatabase = "$dbName`_restore" }
if ($TargetDatabase -eq $dbName -and -not $Force) {
    throw "Restaurar sobre '$dbName' requiere -Force y la API/workers detenidos. Usa -TargetDatabase para un ensayo."
}

Write-Host "== Restauración BODYVISION AI ==" -ForegroundColor Cyan
Write-Host "Origen : $From"
Write-Host "Destino: $TargetDatabase"

# --- 1. Verificación de integridad ----------------------------------------
foreach ($artifact in @("db", "storage")) {
    $info = $manifest.artifacts.$artifact
    if (-not $info) { continue }
    $path = Join-Path $From $info.file
    if (-not (Test-Path $path)) { throw "Falta $($info.file)" }
    $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $info.sha256) {
        throw "SHA-256 no coincide para $($info.file): esperado $($info.sha256), obtenido $hash"
    }
    Write-Host "  $($info.file) OK ($([math]::Round((Get-Item $path).Length / 1MB, 2)) MB)"
}

# --- 2. Base de datos ------------------------------------------------------
$env:PGPASSWORD = $dbPass
try {
    $exists = & psql -U $dbUser -h 127.0.0.1 -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname = '$TargetDatabase'"
    if ($exists -eq "1") {
        if (-not $Force) { throw "La base '$TargetDatabase' ya existe. Usa -Force para recrearla." }
        Write-Host "Recreando '$TargetDatabase'..."
        & psql -U $dbUser -h 127.0.0.1 -d postgres -c "DROP DATABASE `"$TargetDatabase`" WITH (FORCE)"
    }
    & psql -U $dbUser -h 127.0.0.1 -d postgres -c "CREATE DATABASE `"$TargetDatabase`""
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la base destino" }

    Write-Host "Restaurando volcado..."
    & pg_restore -U $dbUser -h 127.0.0.1 -d $TargetDatabase --no-owner --exit-on-error (Join-Path $From $manifest.artifacts.db.file)
    if ($LASTEXITCODE -ne 0) { throw "pg_restore falló con código $LASTEXITCODE" }

    # --- 3. Comparación de conteos ----------------------------------------
    Write-Host "Comparando conteos con el manifiesto..."
    $mismatch = @()
    foreach ($table in $manifest.table_counts.PSObject.Properties.Name) {
        $expected = $manifest.table_counts.$table
        if ($null -eq $expected) { continue }
        $actual = & psql -U $dbUser -h 127.0.0.1 -d $TargetDatabase -t -A -c "SELECT count(*) FROM $table"
        if ([int]$actual -ne [int]$expected) {
            $mismatch += "$table esperado=$expected obtenido=$actual"
        }
    }
    if ($mismatch.Count -gt 0) {
        $mismatch | ForEach-Object { Write-Host "  DESCUADRE: $_" -ForegroundColor Red }
        throw "La restauración no cuadra con el manifiesto"
    }
    Write-Host "  Conteos idénticos en $($manifest.table_counts.PSObject.Properties.Name.Count) tablas"

    Write-Host "Revisión Alembic:"
    & psql -U $dbUser -h 127.0.0.1 -d $TargetDatabase -t -A -c "SELECT version_num FROM alembic_version"
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

# --- 4. Storage ------------------------------------------------------------
if (-not $SkipStorage) {
    $upload = $envMap['UPLOAD_DIR']
    if (-not $upload) { $upload = "backend/storage" }
    $storagePath = if ([System.IO.Path]::IsPathRooted($upload)) { $upload } else { Join-Path $RepoRoot $upload }
    $staged = "$storagePath.restored-$(Get-Date -Format yyyyMMddHHmmss)"
    New-Item -ItemType Directory -Force -Path $staged | Out-Null
    & tar -xf (Join-Path $From $manifest.artifacts.storage.file) -C $staged
    if ($LASTEXITCODE -ne 0) { throw "No se pudo extraer storage.tar" }
    Write-Host "Storage extraído en: $staged" -ForegroundColor Yellow
    Write-Host "Revisa el contenido y sustituye $storagePath manualmente (no se borra nada automáticamente)."
}

Write-Host "Restauración verificada. Si era un ensayo, elimina '$TargetDatabase' cuando termines." -ForegroundColor Green
