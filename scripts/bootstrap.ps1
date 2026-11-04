$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $Root
$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) { $PythonArgs = @('-3') } else { $Python = Get-Command python -ErrorAction SilentlyContinue; $PythonArgs = @() }
if (-not $Python) { throw 'Python 3.11+ is required. Install Python and rerun: .\scripts\bootstrap.ps1' }
& $Python.Source @PythonArgs -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $Python.Source @PythonArgs -m venv --without-pip (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. Repair Python venv support, then retry.' }
}
$DataHome = if ($env:AGENT_HARNESS_HOME) { $env:AGENT_HARNESS_HOME } else { Join-Path $env:USERPROFILE '.haness-9router' }
if (-not (Test-Path -LiteralPath (Join-Path $DataHome 'config.env'))) { & $VenvPython -m agent_harness configure; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
& (Join-Path $Root 'run.ps1') doctor
exit $LASTEXITCODE
