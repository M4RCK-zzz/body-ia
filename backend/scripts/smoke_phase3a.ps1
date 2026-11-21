$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000/api"

function Call($method, $path, $body = $null, $token = $null) {
    $headers = @{}
    if ($token) { $headers["Authorization"] = "Bearer $token" }
    $params = @{ Method = $method; Uri = "$base$path"; Headers = $headers; ContentType = "application/json" }
    if ($null -ne $body) { $params.Body = ($body | ConvertTo-Json) }
    try {
        return @{ Status = 200; Data = (Invoke-RestMethod @params) }
    } catch {
        return @{ Status = [int]$_.Exception.Response.StatusCode; Data = $null }
    }
}
function Check($label, $condition) {
    if ($condition) { Write-Host "  OK   $label" -ForegroundColor Green }
    else { Write-Host "  FALLO $label" -ForegroundColor Red; $script:failed = $true }
}

$failed = $false
$email = "smoke$(Get-Random)@example.com"
$pass = "SmokeTest-12345"

Write-Host "Fase 3A - smoke test"
$r = Call POST "/auth/register" @{ email = $email; password = $pass; full_name = "Smoke Test" }
Check "registro (201/200)" ($r.Status -eq 200 -and $r.Data.roles -contains "user")

$r = Call POST "/auth/register" @{ email = $email; password = $pass; full_name = "Smoke Test" }
Check "correo duplicado -> 409" ($r.Status -eq 409)

$r = Call POST "/auth/register" @{ email = "debil$(Get-Random)@example.com"; password = "sololetraslargas"; full_name = "Debil" }
Check "contraseña débil -> 422" ($r.Status -eq 422)

$login = Call POST "/auth/login" @{ email = $email; password = $pass }
Check "login correcto" ($login.Status -eq 200 -and $login.Data.access_token)
$token = $login.Data.access_token

$r = Call GET "/auth/me" $null $token
Check "/auth/me con token" ($r.Status -eq 200 -and $r.Data.email -eq $email)

$r = Call GET "/auth/me"
Check "/auth/me sin token -> 401" ($r.Status -eq 401)

$r = Call GET "/auth/me" $null "token.falso.xyz"
Check "token falso -> 401" ($r.Status -eq 401)

$r = Call GET "/admin/users" $null $token
Check "usuario normal en /admin -> 403" ($r.Status -eq 403)

$victim = "bloq$(Get-Random)@example.com"
Call POST "/auth/register" @{ email = $victim; password = $pass; full_name = "Bloqueo" } | Out-Null
1..5 | ForEach-Object { Call POST "/auth/login" @{ email = $victim; password = "incorrecta-999" } | Out-Null }
$r = Call POST "/auth/login" @{ email = $victim; password = $pass }
Check "5 fallos -> cuenta bloqueada (contraseña correcta rechazada)" ($r.Status -eq 401)

if ($failed) { Write-Host "Hay fallos." -ForegroundColor Red; exit 1 }
Write-Host "Todo OK." -ForegroundColor Green