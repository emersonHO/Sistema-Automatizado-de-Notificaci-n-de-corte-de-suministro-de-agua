# Instantánea de Compose: estado, health y recursos. No borra volúmenes.
# No usa docker compose down -v.
param(
    [string]$EnvFile = ".env.docker"
)

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptPath
Set-Location $Proyecto

Write-Host "=== docker compose ps ==="
docker compose --env-file $EnvFile ps

Write-Host "`n=== docker stats (un muestreo) ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

Write-Host "`n=== health HTTP web ==="
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/salud" -TimeoutSec 5 | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/salud/listo" -TimeoutSec 5 | ConvertTo-Json -Compress
} catch {
    Write-Host "web no respondió: $_"
}

Write-Host "`n=== n8n /healthz ==="
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:5678/healthz" -TimeoutSec 5 -UseBasicParsing | Select-Object -ExpandProperty StatusCode
} catch {
    Write-Host "n8n no respondió: $_"
}

Write-Host "`nTimestamps de esta instantánea: UTC. CPU/memoria son de docker stats, no de Prometheus."
