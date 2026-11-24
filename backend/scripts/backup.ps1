# Backup de PostgreSQL + storage privado (Fase 9).
#
# Uso (desde la raíz del repo, Windows):
#   powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1
#   powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -OutDir D:\backups -Keep 14
#
# Qué produce, en <OutDir>\<UTC timestamp>\:
#   db.dump        -> pg_dump -Fc (formato custom, restaurable con pg_restore)
#   storage.tar    -> contenido de UPLOAD_DIR (imágenes y binarios de reportes)
#   manifest.json  -> versión, revisión Alembic, conteos por tabla y SHA-256
#
# Los binarios de reportes y las imágenes viven en el storage, NO en PostgreSQL:
# un backup solo de la base perdería esos ficheros y viceversa.
#
# Requisitos: pg_dump en PATH o en el contenedor `db` (se detecta solo).

param(
    [string]$OutDir = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "backups"),
    [int]$Keep = 7,
    [string]$EnvFile = ".env.prod",
    [switch]$UseDocker
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

function Read-EnvFile([string]$Path) {
    if (-not (Test-Path $Path)) { throw "No existe $Path. Copia .env.prod.example a .env.prod" }
    $map = @{}
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $map[$Matches[1]] = $Matches[2].Trim().Trim('"')
        }
    }
    return $map
}

$envMap = Read-EnvFile $EnvFile
$dbName = if ($envMap['POSTGRES_DB']) { $envMap['POSTGRES_DB'] } else { "bodyvision" }
$dbUser = if ($envMap['POSTGRES_USER']) { $envMap['POSTGRES_USER'] } else { "bodyvision" }
$dbPass = $envMap['POSTGRES_PASSWORD']
if (-not $dbPass) { throw "POSTGRES_PASSWORD no está en $EnvFile" }

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$target = Join-Path $OutDir $stamp
New-Item -ItemType Directory -Force -Path $target | Out-Null

Write-Host "== Backup BODYVISION AI ==" -ForegroundColor Cyan
Write-Host "Destino: $target"

# --- 1. Volcado de PostgreSQL ----------------------------------------------
$dump = Join-Path $target "db.dump"
if ($UseDocker) {
    Write-Host "pg_dump vía contenedor 'db'..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T `
        -e PGPASSWORD=$dbPass db pg_dump -U $dbUser -Fc --no-owner $dbName |
        Set-Content -Path $dump -AsByteStream
} else {
    $env:PGPASSWORD = $dbPass
    try {
        Write-Host "pg_dump local..."
        & pg_dump -U $dbUser -h 127.0.0.1 -p 5432 -Fc --no-owner -f $dump $dbName
        if ($LASTEXITCODE -ne 0) { throw "pg_dump falló con código $LASTEXITCODE" }
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

# Verificación: el volcado debe ser legible por pg_restore --list.
if (-not $UseDocker) {
    & pg_restore --list $dump | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "El volcado no es legible por pg_restore" }
}
$dumpSize = (Get-Item $dump).Length
if ($dumpSize -lt 1024) { throw "El volcado es sospechosamente pequeño ($dumpSize bytes)" }

# --- 2. Storage privado ----------------------------------------------------
$upload = $envMap['UPLOAD_DIR']
if (-not $upload) { $upload = "backend/storage" }
$storagePath = if ([System.IO.Path]::IsPathRooted($upload)) { $upload } else { Join-Path $RepoRoot $upload }
$storageTar = Join-Path $target "storage.tar"

if (Test-Path $storagePath) {
    Write-Host "Empaquetando storage: $storagePath"
    & tar -cf $storageTar -C $storagePath .
    if ($LASTEXITCODE -ne 0) { throw "tar falló con código $LASTEXITCODE" }
} else {
    Write-Host "Aviso: $storagePath no existe; se registra un storage vacío." -ForegroundColor Yellow
    & tar -cf $storageTar --files-from /dev/null 2>$null
}

# --- 3. Manifiesto con conteos y checksums --------------------------------
$psql = if ($UseDocker) {
    "docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T -e PGPASSWORD=$dbPass db psql -U $dbUser -d $dbName -t -A -c"
} else {
    "psql -U $dbUser -h 127.0.0.1 -d $dbName -t -A -c"
}

$tables = @(
    "users", "profiles", "measurements", "media_assets", "pose_analyses",
    "reports", "simulations", "simulation_baselines", "audit_events", "worker_heartbeats"
)
$counts = [ordered]@{}
foreach ($table in $tables) {
    try {
        $value = if ($UseDocker) {
            $env:PGPASSWORD = $dbPass
            docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db `
                psql -U $dbUser -d $dbName -t -A -c "SELECT count(*) FROM $table"
        } else {
            $env:PGPASSWORD = $dbPass
            & psql -U $dbUser -h 127.0.0.1 -d $dbName -t -A -c "SELECT count(*) FROM $table"
        }
        $counts[$table] = [int]($value | Select-Object -First 1)
    } catch {
        $counts[$table] = $null
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

$revision = $envMap['APP_VERSION']
$manifest = [ordered]@{
    generated_at     = (Get-Date).ToUniversalTime().ToString("o")
    app_version      = $revision
    domain           = $envMap['DOMAIN']
    database         = $dbName
    alembic_revision = $revision
    artifacts        = [ordered]@{
        db      = [ordered]@{ file = "db.dump"; bytes = $dumpSize; sha256 = (Get-FileHash $dump -Algorithm SHA256).Hash.ToLower() }
        storage = [ordered]@{ file = "storage.tar"; bytes = (Get-Item $storageTar).Length; sha256 = (Get-FileHash $storageTar -Algorithm SHA256).Hash.ToLower() }
    }
    table_counts     = $counts
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $target "manifest.json") -Encoding UTF8

# --- 4. Rotación -----------------------------------------------------------
if ($Keep -gt 0) {
    $old = Get-ChildItem -Path $OutDir -Directory | Sort-Object Name -Descending | Select-Object -Skip $Keep
    foreach ($dir in $old) {
        Write-Host "Rotando backup antiguo: $($dir.Name)" -ForegroundColor DarkGray
        Remove-Item -Recurse -Force $dir.FullName
    }
}

Write-Host "Backup completado: $target" -ForegroundColor Green
Write-Host "  db.dump     $([math]::Round($dumpSize / 1MB, 2)) MB"
Write-Host "  storage.tar $([math]::Round((Get-Item $storageTar).Length / 1MB, 2)) MB"
Write-Host "Verifica la restauración con: backend\scripts\restore.ps1 -From '$target' -TargetDatabase bodyvision_restore"
