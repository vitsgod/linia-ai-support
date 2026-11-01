$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Create the environment first: python -m venv .venv; then .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt (see README.md).'
}

Push-Location -LiteralPath $PSScriptRoot
try {
    & $projectPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
    if ($LASTEXITCODE -ne 0) { throw "Server exited with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
