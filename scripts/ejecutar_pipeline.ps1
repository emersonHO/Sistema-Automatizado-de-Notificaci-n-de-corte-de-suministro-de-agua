# Programador de tareas de Windows: ejecutar el pipeline en modo simulación.
# No envía correos reales.

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $Proyecto

if (Test-Path ".\.venv\Scripts\python.exe") {
    $Python = ".\.venv\Scripts\python.exe"
} else {
    $Python = "python"
}

& $Python -m src.pipeline
exit $LASTEXITCODE
