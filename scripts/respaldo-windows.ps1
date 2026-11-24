# Copia de seguridad local. No restaura. No borra volúmenes.
$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

$carpeta = Join-Path $Proyecto "backups"
New-Item -ItemType Directory -Force -Path $carpeta | Out-Null
$marca = Get-Date -Format "yyyyMMddTHHmmss"
$proyectoCompose = "notificacion-agua"

Write-Host "Volcado PostgreSQL..."
$dump = Join-Path $carpeta "pg-$marca.sql"
docker compose --env-file .env.docker exec -T db pg_dump -U agua -d notificaciones_agua | Set-Content -Path $dump -Encoding utf8
if ((Get-Item $dump).Length -lt 100) { throw "El volcado de PostgreSQL parece vacío." }

Write-Host "Archivo n8n (workflows y credenciales del volumen)..."
docker run --rm -v "${proyectoCompose}_n8n_data:/origen" -v "${carpeta}:/destino" alpine:3.20 tar -czf "/destino/n8n-$marca.tgz" -C /origen .

Write-Host "Capturas..."
docker run --rm -v "${proyectoCompose}_capturas:/origen" -v "${carpeta}:/destino" alpine:3.20 tar -czf "/destino/capturas-$marca.tgz" -C /origen .

Write-Host "Listo en $carpeta"
Get-ChildItem $carpeta | Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name, Length, LastWriteTime
Write-Host "Copie esta carpeta a un disco externo. Restauración: docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md (no automática)."
