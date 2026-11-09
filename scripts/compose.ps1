# Ayuda Compose en Windows. No ejecuta down -v.
param(
    [Parameter(Position = 0)]
    [string]$Accion = "up"
)

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

if (-not (Test-Path ".\.env.docker")) {
    Write-Error "Copie .env.docker.example a .env.docker y defina POSTGRES_PASSWORD y ADMIN_PASSWORD."
}

switch ($Accion) {
    "up" { docker compose --env-file .env.docker up -d --build db web }
    "pipeline" { docker compose --env-file .env.docker --profile pipeline run --rm pipeline }
    "pipeline-fixture" {
        docker compose --env-file .env.docker --profile pipeline run --rm pipeline python -m src.pipeline --desde-archivo /app/tests/fixtures/captura_minima.json
    }
    "logs" { docker compose --env-file .env.docker logs -f web }
    "down" { docker compose --env-file .env.docker down }
    default { Write-Error "Accion no reconocida. Use up | pipeline | pipeline-fixture | logs | down" }
}
