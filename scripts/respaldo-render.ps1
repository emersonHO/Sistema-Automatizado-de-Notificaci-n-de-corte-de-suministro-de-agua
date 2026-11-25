# Volcado de PostgreSQL de Render desde Windows. No toca volúmenes Docker locales.
# En la misma sesión de PowerShell:
#   $env:DATABASE_URL = "postgresql://... (External Database URL de Render)"
param(
    [string]$Salida = ""
)

$ErrorActionPreference = "Stop"
if (-not $env:DATABASE_URL) {
    throw "Defina `$env:DATABASE_URL con la URL externa de Render Postgres. No la suba a Git."
}
$Proyecto = Split-Path -Parent $PSScriptRoot
$carpeta = Join-Path $Proyecto "backups"
New-Item -ItemType Directory -Force -Path $carpeta | Out-Null
if (-not $Salida) {
    $marca = Get-Date -Format "yyyyMMddTHHmmss"
    $Salida = Join-Path $carpeta "render-pg-$marca.sql"
}

docker run --rm -e "DATABASE_URL=$($env:DATABASE_URL)" postgres:16.6-alpine sh -c "pg_dump `"`$DATABASE_URL`"" | Set-Content -Path $Salida -Encoding utf8
if ((Get-Item $Salida).Length -lt 200) { throw "El volcado parece vacío." }
Get-FileHash -Algorithm SHA256 $Salida | Format-List
Write-Host "Backup: $Salida"
Write-Host "Cópielo a un disco externo. La base gratuita de Render caduca cerca de 30 días."
