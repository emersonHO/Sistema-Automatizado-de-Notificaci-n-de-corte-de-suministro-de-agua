# Detiene contenedores. Conserva volúmenes (pgdata, capturas, n8n_data, métricas).
# NUNCA usa -v.
param(
    [switch]$SoloTunel
)

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

if ($SoloTunel) {
    docker compose --env-file .env.docker stop tunel caddy-publico
    Write-Host "Túnel y Caddy público detenidos. El resto de la pila sigue local."
}
else {
    docker compose --env-file .env.docker --profile publico down
    Write-Host "Pila detenida. Volúmenes intactos. Para volver: .\scripts\iniciar-publico.ps1"
}
