$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000/api"
function Utc($hoursAgo) { (Get-Date).ToUniversalTime().AddHours(-$hoursAgo).ToString("yyyy-MM-ddTHH:mm:ssZ") }
function Post($uri, $body) { Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body ($body | ConvertTo-Json) }

$p = Post "$base/profiles" @{ display_code = "SMOKE-$(Get-Random -Maximum 99999)" }
Write-Host "Expediente: $($p.display_code) ($($p.id))"

$m1 = Post "$base/profiles/$($p.id)/measurements" @{ metric_type="weight"; value=73.1; unit="kg"; measured_at=(Utc 48); method="scale"; created_by="Smoke" }
$m2 = Post "$base/profiles/$($p.id)/measurements" @{ metric_type="weight"; value=72.5; unit="kg"; measured_at=(Utc 24); method="scale"; created_by="Smoke" }
$fix = Post "$base/profiles/$($p.id)/measurements/$($m2.id)/corrections" @{ value=72.0; created_by="Smoke"; reason="Correccion de prueba" }

$current = Invoke-RestMethod "$base/profiles/$($p.id)/measurements"
$all = Invoke-RestMethod "$base/profiles/$($p.id)/measurements?include_superseded=true"
$hist = Invoke-RestMethod "$base/profiles/$($p.id)/measurements/$($m2.id)/history"
$series = Invoke-RestMethod "$base/profiles/$($p.id)/measurements/series?metric_type=weight"
Write-Host "Vigentes: $($current.total) (esperado 2) | Con reemplazadas: $($all.total) (esperado 3) | Versiones: $($hist.Count) (esperado 2) | Puntos serie: $($series.points.Count) (esperado 2)"

try {
    Post "$base/profiles/$($p.id)/measurements" @{ metric_type="waist"; value=80; unit="kg"; measured_at=(Utc 1); method="manual_tape"; created_by="Smoke" } | Out-Null
    Write-Host "ERROR: debia rechazar unidad incorrecta" -ForegroundColor Red
} catch {
    Write-Host "Unidad incorrecta rechazada: HTTP $($_.Exception.Response.StatusCode.value__) (esperado 422)" -ForegroundColor Green
}