# Inicia la pila local y el Quick Tunnel de Cloudflare.
# No usa docker compose down -v. No borra volúmenes.
param(
    [switch]$SinRebuild
)

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

function Esperar-Docker {
    for ($i = 1; $i -le 40; $i++) {
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "Esperando Docker Desktop ($i/40)..."
        Start-Sleep -Seconds 5
    }
    throw "Docker Desktop no responde. Ábralo y vuelva a ejecutar este script."
}

if (-not (Test-Path ".\.env.docker")) {
    throw "Falta .env.docker. Copie .env.docker.example a .env.docker y complete secretos y SMTP."
}

Esperar-Docker

Write-Host "Levantando servicios (incluye perfil publico: caddy-publico y tunel)..."
if ($SinRebuild) {
    docker compose --env-file .env.docker --profile publico up -d
}
else {
    docker compose --env-file .env.docker --profile publico up -d --build
}
if ($LASTEXITCODE -ne 0) { throw "docker compose up falló." }

Write-Host "Esperando URL del Quick Tunnel (trycloudflare.com)..."
$patron = 'https://[a-z0-9-]+\.trycloudflare\.com'
$url = $null
for ($i = 1; $i -le 45; $i++) {
    Start-Sleep -Seconds 2
    $logs = docker compose --env-file .env.docker logs tunel 2>&1 | Out-String
    if ($logs -match $patron) {
        $url = $Matches[0]
        break
    }
    Write-Host "  intento $i/45..."
}

if (-not $url) {
    Write-Warning "No se obtuvo la URL del túnel. Revise: docker compose --env-file .env.docker logs tunel"
    Write-Host "Cuando aparezca https://....trycloudflare.com ejecute: .\scripts\aplicar-url-publica.ps1 -Url ESA_URL"
    exit 2
}

Write-Host "URL pública: $url"
& "$PSScriptRoot\aplicar-url-publica.ps1" -Url $url

Write-Host ""
Write-Host "Local (solo esta PC):"
Write-Host "  Ciudadano local:  http://127.0.0.1:8000"
Write-Host "  Admin:            http://127.0.0.1:8000/admin"
Write-Host "  Filtro Caddy:     http://127.0.0.1:8088"
Write-Host "  n8n:              http://127.0.0.1:5678"
Write-Host "  Prometheus:       http://127.0.0.1:9090"
Write-Host "  Grafana:          http://127.0.0.1:3000"
Write-Host "  Mailpit (lab):    http://127.0.0.1:8025"
Write-Host "Internet (ciudadanos): $url"
Write-Host "Compruebe desde datos móviles, no desde el Wi-Fi de esta PC."
Write-Host "Luego ejecute: .\scripts\diagnostico-publico.ps1"
