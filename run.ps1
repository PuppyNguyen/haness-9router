$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Runtime is not installed. Run: .\scripts\bootstrap.ps1" }
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$env:PYTHONPATH" } else { $Root }
& $Python -m agent_harness @args
exit $LASTEXITCODE
