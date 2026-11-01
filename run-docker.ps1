param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$docker = if ($dockerCommand) { $dockerCommand.Source } else { 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' }
& $docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
$configDirectory = Join-Path $PSScriptRoot '.local/docker-stack'
$envFile = Join-Path $configDirectory 'stack.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    if ($Stop) { throw 'Restore the stack env file before controlling an existing stack.' }
    $retainedVolume = & $docker volume inspect provider-support-stack_stack-data --format '{{.Name}}' 2>$null
    if ($LASTEXITCODE -eq 0) { throw 'A retained stack volume exists. Restore .local/docker-stack/stack.env; do not reset its credentials.' }
    [System.IO.Directory]::CreateDirectory($configDirectory) | Out-Null
    $scriptsDirectory = Join-Path $PSScriptRoot 'scripts'
    & $docker run --rm --mount "type=bind,src=$scriptsDirectory,dst=/scripts,readonly" --mount "type=bind,src=$configDirectory,dst=/config" python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f python /scripts/compose_env.py --output /config/stack.env
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare Compose environment.' }
}
$compose = @('compose', '--project-name', 'provider-support-stack', '--env-file', $envFile, '-f', (Join-Path $PSScriptRoot 'compose.yaml'))
if ($Stop) {
    & $docker @compose stop
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop the stack.' }
    Write-Host 'Stack stopped; database volume retained.'
    exit
}
& $docker @compose up --build -d --wait app
if ($LASTEXITCODE -ne 0) { throw 'Compose startup failed.' }
& $docker @compose --profile tools run --rm index
if ($LASTEXITCODE -ne 0) { throw 'App started, but RAG indexing failed. Check host Ollama and both installed models, then rerun.' }
$port = if ($env:STACK_HTTP_PORT) { $env:STACK_HTTP_PORT } else { '5180' }
Write-Host "Docker app ready: http://127.0.0.1:$port/ (separate data from the native app)."
