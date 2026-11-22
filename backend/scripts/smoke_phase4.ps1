# Fase 4 - Captura segura: smoke test contra la API local (http://127.0.0.1:8000).
# Requiere: backend arriba (docker compose / uvicorn) y tu cuenta registrada.
# NOTA: el ascenso de imágenes usa curl.exe (incluido en Windows 10+).
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000/api"
$script:failed = $false

function Check($label, $condition) {
    if ($condition) { Write-Host "  OK   $label" -ForegroundColor Green }
    else { Write-Host "  FALLO $label" -ForegroundColor Red; $script:failed = $true }
}

function Invoke-Json($method, $path, $body, $token) {
    $headers = @{}
    if ($token) { $headers["Authorization"] = "Bearer $token" }
    $params = @{ Method = $method; Uri = "$base$path"; Headers = $headers }
    if ($null -ne $body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($body | ConvertTo-Json -Depth 5)
    }
    try { return @{ Status = 200; Data = (Invoke-RestMethod @params) } }
    catch {
        $status = [int]$_.Exception.Response.StatusCode
        return @{ Status = $status; Data = $null }
    }
}

# Escritura segura del fixture PNG (1x1) y limpieza
$tmpDir = Join-Path $env:TEMP "bv-smoke4"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
$pngB64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
$pngPath = Join-Path $tmpDir "photo.png"
[System.IO.File]::WriteAllBytes($pngPath, [Convert]::FromBase64String($pngB64))
$txtPath = Join-Path $tmpDir "not-an-image.txt"
[System.IO.File]::WriteAllText($txtPath, "esto no es una imagen")

try {
    Write-Host "Fase 4 - smoke test (capturas seguras)"
    Write-Host "  base: $base"

    $email = "smoke4$(Get-Random -Maximum 99999)@example.com"
    $pass = "SmokeTest-12345"

    $r = Invoke-Json POST "/auth/register" @{ email = $email; password = $pass; full_name = "Smoke 4" } $null
    Check "registro (200/201)" ($r.Status -eq 200 -or $r.Status -eq 201)

    $login = Invoke-Json POST "/auth/login" @{ email = $email; password = $pass } $null
    Check "login" ($login.Status -eq 200 -and $login.Data.access_token)
    $token = $login.Data.access_token

    $p = Invoke-Json POST "/profiles" @{ display_code = "SMOKE4-$(Get-Random -Maximum 99999)" } $token
    Check "perfil creado" ($p.Status -eq 201 -or $p.Status -eq 200)
    $profId = $p.Data.id

    $r = Invoke-Json POST "/profiles/$profId/consents" @{ purpose = "data_processing"; declaration = $true } $token
    Check "consentimiento data_processing (201)" ($r.Status -eq 201)

    # 1. Subida válida (curl.exe multipart)
    $upload = curl.exe --silent --output $tmpDir\upload-resp.json --write-out "%{http_code}" `
        --header "Authorization: Bearer $token" `
        --form "file=@$pngPath;type=image/png" `
        "$base/profiles/$profId/media"
    Check "subida válida -> 201" ($upload -eq "201")
    $asset = Get-Content (Join-Path $tmpDir "upload-resp.json") -Raw | ConvertFrom-Json
    Check "asset ready con mime image/png" ($asset.status -eq "ready" -and $asset.mime_type -eq "image/png")
    Check "asset no expone storage_key" ($null -eq $asset.storage_key)
    $assetId = $asset.id

    # 2. Listado
    $r = Invoke-Json GET "/profiles/$profId/media" $null $token
    Check "lista muestra 1 captura" ($r.Status -eq 200 -and $r.Data.total -eq 1)

    # 3. Contenido autenticado
    $content = curl.exe --silent --output $tmpDir\content.bin --write-out "%{http_code}" `
        --header "Authorization: Bearer $token" `
        "$base/media/$assetId/content"
    Check "descarga autenticada -> 200" ($content -eq "200")
    $contentStat = Get-Item (Join-Path $tmpDir "content.bin")
    Check "contenido no vacío" ($contentStat.Length -gt 0)

    # 4. Rechazo por tipo inexistente -> 415 (declared mime no soportado)
    $bad = curl.exe --silent --output $tmpDir\bad-resp.json --write-out "%{http_code}" `
        --header "Authorization: Bearer $token" `
        --form "file=@$txtPath;type=text/plain" `
        "$base/profiles/$profId/media"
    Check "tipo no soportado -> 415" ($bad -eq "415")

    # 5. Subida con formato incorrecto (PNG que no es PNG) -> 422 y registro persistido
    $badContent = Join-Path $tmpDir "fake.png"
    [System.IO.File]::WriteAllText($badContent, "esto no es un png en absoluto")
    $bad2 = curl.exe --silent --output $tmpDir\bad2-resp.json --write-out "%{http_code}" `
        --header "Authorization: Bearer $token" `
        --form "file=@$badContent;type=image/png" `
        "$base/profiles/$profId/media"
    Check "contenido inválido -> 422" ($bad2 -eq "422")
    $r = Invoke-Json GET "/profiles/$profId/media?status=rejected" $null $token
    Check "registro de rechazo persistido (1)" ($r.Data.total -eq 1)

    # 6. Descarga de rechazo -> 404 (solo ready)
    $r = Invoke-Json GET "/profiles/$profId/media?status=rejected" $null $token
    $rejectedId = $r.Data.items[0].id
    $content2 = curl.exe --silent --output NUL --write-out "%{http_code}" `
        --header "Authorization: Bearer $token" `
        "$base/media/$rejectedId/content"
    Check "contenido de rechazo -> 404" ($content2 -eq "404")

    # 7. Borrado (soft delete)
    $r = Invoke-Json DELETE "/media/$assetId" $null $token
    Check "borrado -> 200" ($r.Status -eq 200 -or $r.Status -eq 201 -or $r.Status -eq 204)
    Check "asset borrado con status deleted" ($r.Data.status -eq "deleted")

    $r = Invoke-Json GET "/profiles/$profId/media" $null $token
    Check "borrado exclusiva: lista excluye deleted" ($r.Data.total -eq 0)

    # 8. Borrado idempotente
    $r = Invoke-Json DELETE "/media/$assetId" $null $token
    Check "borrado idempotente (sin 5xx)" ($r.Status -eq 200 -or $r.Status -eq 204)

    # 9. Sin consentimiento: nuevo perfil sin consent -> upload no permitido (403)
    $p2 = Invoke-Json POST "/profiles" @{ display_code = "SMOKE4B-$(Get-Random -Maximum 99999)" } $token
    $profId2 = $p2.Data.id
    $noConsent = curl.exe --silent --output NUL --write-out "%{http_code}" `
        --header "Authorization: Bearer $token" `
        --form "file=@$pngPath;type=image/png" `
        "$base/profiles/$profId2/media"
    Check "sin consentimiento -> 422" ($noConsent -eq "422")
}
finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}

if ($failed) { Write-Host "`nHay fallos." -ForegroundColor Red; exit 1 }
Write-Host "`nTodo OK." -ForegroundColor Green
