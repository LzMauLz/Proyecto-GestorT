param([int]$Puerto = 5000)

Set-Location -LiteralPath $PSScriptRoot
foreach ($entorno in '.venv', '.venv-review') {
    $pythonGestorTech = Join-Path $PSScriptRoot "$entorno\Scripts\python.exe"
    if (Test-Path -LiteralPath $pythonGestorTech) {
        & $pythonGestorTech -B -c 'import flask, openpyxl; from PIL import Image' 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Iniciando GestorTech con $entorno en http://127.0.0.1:$Puerto"
            & $pythonGestorTech -B -m flask --app wsgi:app run --host=127.0.0.1 --port=$Puerto
            exit $LASTEXITCODE
        }
    }
}
Write-Error 'No existe un entorno del proyecto con Flask, openpyxl y Pillow. Usa el entorno virtual del proyecto e instala las dependencias declaradas en requirements.txt.'
exit 1
