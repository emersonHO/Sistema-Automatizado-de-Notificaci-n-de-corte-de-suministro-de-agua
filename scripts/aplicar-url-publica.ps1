# Escribe la URL pública en el volumen compartido y en BASE_URL de .env.docker.
# Los correos leen /app/data/url_publica.txt en cada envío; no hace falta recrear contenedores.
param(
    [Parameter(Mandatory = $true)]
    [string]$Url
)

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

$Url = $Url.Trim().TrimEnd("/")
if ($Url -notmatch '^https://[a-z0-9.-]+\.trycloudflare\.com$') {
    throw "La URL debe ser https://….trycloudflare.com (sin barra final ni texto extra)."
}

$codigo = "from pathlib import Path; p=Path('/app/data/url_publica.txt'); p.write_text('$Url', encoding='utf-8'); print(p.read_text(encoding='utf-8').strip())"
$escrita = docker compose --env-file .env.docker exec -T web python -c $codigo
if ($LASTEXITCODE -ne 0) { throw "No se pudo escribir url_publica.txt dentro del contenedor web." }
Write-Host "Archivo en contenedor: $escrita"

$envPath = Join-Path $Proyecto ".env.docker"
$lineas = Get-Content $envPath
$nueva = [System.Collections.Generic.List[string]]::new()
$visto = $false
foreach ($linea in $lineas) {
    if ($linea -match '^BASE_URL=') {
        $nueva.Add("BASE_URL=$Url") | Out-Null
        $visto = $true
    }
    else {
        $nueva.Add($linea) | Out-Null
    }
}
if (-not $visto) { $nueva.Add("BASE_URL=$Url") | Out-Null }
[System.IO.File]::WriteAllLines($envPath, $nueva)
Write-Host "BASE_URL actualizado en .env.docker (no se versiona)."
Write-Host "Si el túnel se reinicia y cambia la URL, vuelva a ejecutar este script."
