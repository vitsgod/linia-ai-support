$ErrorActionPreference = 'Stop'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$projectNode = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
if (-not (Test-Path -LiteralPath $projectNode)) { throw 'Node.js 24 is required (see README.md).' }
$viteEntry = Join-Path $PSScriptRoot 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $viteEntry)) { throw 'Install frontend dependencies first (see README.md).' }
Push-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
try {
    & $projectNode $viteEntry
    if ($LASTEXITCODE -ne 0) { throw "Frontend exited with code $LASTEXITCODE" }
}
finally { Pop-Location }
