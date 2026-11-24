# Estado de la pila y del túnel. No imprime contraseñas.
$ErrorActionPreference = "Continue"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

Write-Host "=== Contenedores ==="
docker compose --env-file .env.docker --profile publico ps

Write-Host ""
Write-Host "=== Salud FastAPI (localhost) ==="
try {
    $salud = Invoke-RestMethod -Uri "http://127.0.0.1:8000/salud" -TimeoutSec 8
    $salud | ConvertTo-Json -Compress
}
catch {
    Write-Host "FALLO /salud: $_"
}

Write-Host ""
Write-Host "=== URL pública en el contenedor web ==="
docker compose --env-file .env.docker exec -T web python -c "from pathlib import Path; p=Path('/app/data/url_publica.txt'); print(p.read_text(encoding='utf-8').strip() if p.is_file() else 'NO HAY url_publica.txt')"

Write-Host ""
Write-Host "=== BASE_URL y SMTP (sin secretos) ==="
Get-Content .env.docker | Where-Object {
    $_ -match '^(BASE_URL|OPERACION_PUBLICA|SMTP_ENABLED|MODO_ENVIO|SMTP_HOST|SMTP_PORT|SMTP_STARTTLS|SMTP_FROM|SMTP_FROM_NAME|SMTP_USER|API_URL|INTERNAL_PERMITIR_FIXTURE)='
} | ForEach-Object {
    if ($_ -match '^SMTP_USER=') { "SMTP_USER=(definido: $($_.Length -gt 10))" } else { $_ }
}
$pass = (Get-Content .env.docker | Where-Object { $_ -match '^SMTP_PASSWORD=' })
if ($pass) {
    $valor = $pass -replace '^SMTP_PASSWORD=', ''
    if ($valor) { Write-Host "SMTP_PASSWORD=(presente, no se muestra)" } else { Write-Host "SMTP_PASSWORD=(vacío)" }
}

Write-Host ""
Write-Host "=== Filtro Caddy local (debe ser 404 en /admin) ==="
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8088/admin" -MaximumRedirection 0 -SkipHttpErrorCheck -TimeoutSec 8
    Write-Host "GET /admin via :8088 -> $($r.StatusCode)"
}
catch { Write-Host "GET /admin via :8088 -> $_" }
try {
    $r2 = Invoke-WebRequest -Uri "http://127.0.0.1:8088/" -TimeoutSec 8
    Write-Host "GET / via :8088 -> $($r2.StatusCode)"
}
catch { Write-Host "GET / via :8088 -> $_" }

Write-Host ""
Write-Host "=== Últimas líneas del túnel ==="
docker compose --env-file .env.docker logs --tail 25 tunel

Write-Host ""
Write-Host "=== pipeline-worker / notification-worker (cola) ==="
docker compose --env-file .env.docker logs --tail 8 pipeline-worker
docker compose --env-file .env.docker logs --tail 8 notification-worker

Write-Host ""
Write-Host "Si OPERACION_PUBLICA=true y SMTP_ENABLED no es true con MODO_ENVIO=real, los ciudadanos no recibirán correo."
Write-Host "n8n, Grafana y Prometheus solo en localhost. No los abra con la URL trycloudflare."
