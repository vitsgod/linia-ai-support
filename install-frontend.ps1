$ErrorActionPreference = 'Stop'
$pnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node'
$projectNode = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $runtimeRoot 'bin\node.exe' }
$bundledPnpm = Join-Path $runtimeRoot 'node_modules\pnpm\bin\pnpm.cjs'
Push-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
try {
    if ($pnpmCommand) { & $pnpmCommand.Source install --frozen-lockfile }
    elseif ((Test-Path -LiteralPath $projectNode) -and (Test-Path -LiteralPath $bundledPnpm)) {
        & $projectNode $bundledPnpm install --frozen-lockfile
    }
    else { throw 'Install Node.js 24 and pnpm 11, then run this script again.' }
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation exited with code $LASTEXITCODE" }
}
finally { Pop-Location }
