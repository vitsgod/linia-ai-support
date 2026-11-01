$ErrorActionPreference = 'Stop'
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$docker = if ($dockerCommand) { $dockerCommand.Source } else { 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' }
& $docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
$ciProject = 'provider-support-ci-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
$configDirectory = Join-Path $PSScriptRoot '.local/docker-ci'
[System.IO.Directory]::CreateDirectory($configDirectory) | Out-Null
$envFile = Join-Path $configDirectory ($ciProject + '.env')
$scriptsDirectory = Join-Path $PSScriptRoot 'scripts'
& $docker run --rm --mount "type=bind,src=$scriptsDirectory,dst=/scripts,readonly" --mount "type=bind,src=$configDirectory,dst=/config" python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f python /scripts/compose_env.py --output ('/config/' + $ciProject + '.env')
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare isolated test credentials.' }
$compose = @('compose', '--project-name', $ciProject, '--env-file', $envFile, '-f', (Join-Path $PSScriptRoot 'compose.yaml'), '--profile', 'tests')
try {
    & $docker @compose build bootstrap tests
    if ($LASTEXITCODE -ne 0) { throw 'Container build failed.' }
    & $docker @compose run --rm tests
    if ($LASTEXITCODE -ne 0) { throw 'Container tests failed.' }
}
finally {
    if ($ciProject -notmatch '^provider-support-ci-[a-f0-9]{12}$') { throw 'Refusing cleanup: unexpected test project name.' }
    & $docker @compose down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw 'Test cleanup failed; inspect only the reported CI project.' }
    Remove-Item -LiteralPath $envFile -Force
}
Write-Host 'Linux container tests passed; isolated test database removed.'
