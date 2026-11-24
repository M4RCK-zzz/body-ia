<#
.SYNOPSIS
    Genera un certificado TLS AUTOFIRMADO para probar HTTPS en local/staging (Fase 9).

.DESCRIPTION
    Escribe fullchain.pem / privkey.pem / chain.pem en -OutDir y deja la clave con
    ACL restringida al usuario actual. El navegador avisará de que el certificado
    no es de confianza: es lo esperado y NO sirve para producción.

    Para producción: monta los ficheros de Let's Encrypt
    (/etc/letsencrypt/live/$DOMAIN/) o tu certificado corporativo y arranca sin
    ALLOW_SELFSIGNED.

.PARAMETER Domain
    Nombre del certificado (CN + SAN). Por defecto el de $env:DOMAIN o 'localhost'.

.PARAMETER Days
    Vigencia en días (1..825). Por defecto 30.

.PARAMETER OutDir
    Directorio de salida. Por defecto docker\nginx\certs.

.PARAMETER Force
    Regenera aunque ya exista un certificado.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\tls-selfsigned.ps1
    powershell -ExecutionPolicy Bypass -File scripts\tls-selfsigned.ps1 -Domain localhost -Days 60
#>
[CmdletBinding()]
param(
    [string]$Domain = $(if ($env:DOMAIN) { $env:DOMAIN } else { 'localhost' }),
    [ValidateRange(1, 825)]
    [int]$Days = 30,
    [string]$OutDir = 'docker\nginx\certs',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# 1. Comprobaciones previas ----------------------------------------------------
$openssl = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $openssl) {
    throw "No se encontró 'openssl' en el PATH. Instálalo (Git for Windows suele incluirlo) o usa docker."
}

$certsDir = Join-Path $OutDir ''
$fullchain = Join-Path $certsDir 'fullchain.pem'
$privkey = Join-Path $certsDir 'privkey.pem'

if ((Test-Path $fullchain) -and (-not $Force)) {
    Write-Host "Ya existe $fullchain."
    Write-Host "Si quieres regenerarlo, bórralo o ejecuta con -Force."
    return
}

if (-not (Test-Path $certsDir)) {
    New-Item -ItemType Directory -Path $certsDir -Force | Out-Null
}

# 2. Generación ---------------------------------------------------------------
Write-Host "Generando certificado autofirmado para '$Domain' ($Days días) en $certsDir ..." -ForegroundColor Cyan

& openssl req -x509 -nodes -newkey rsa:2048 -days $Days `
    -keyout $privkey `
    -out $fullchain `
    -subj "/CN=$Domain" `
    -addext "subjectAltName=DNS:$Domain,DNS:localhost,IP:127.0.0.1" 2>$null

if ($LASTEXITCODE -ne 0) {
    throw "openssl falló con código $LASTEXITCODE."
}

Copy-Item $fullchain (Join-Path $certsDir 'chain.pem') -Force

# 3. Permisos: la clave privada solo para el usuario actual --------------------
# En Windows se usan ACL; en Linux/macOS con PowerShell se usa chmod.
if ($IsWindows) {
    $acl = Get-Acl $privkey
    $acl.SetAccessRuleProtection($true, $false)
    $acl.Access | ForEach-Object { $acl.RemoveAccessRule($_) | Out-Null }
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
        'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -Path $privkey -AclObject $acl
} else {
    & chmod 600 $privkey
}

# 4. Resumen ------------------------------------------------------------------
Write-Host ""
Write-Host "Certificado generado:" -ForegroundColor Green
& openssl x509 -in $fullchain -noout -subject
& openssl x509 -in $fullchain -noout -enddate
Write-Host ""
Write-Host "Recuerda: solo para pruebas. En producción, certificado real." -ForegroundColor Yellow
Write-Host "Montaje en docker-compose.prod.yml: ./docker/nginx/certs:/etc/nginx/certs:ro"
