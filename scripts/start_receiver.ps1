$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment is missing. Run setup_host.ps1 first."
}

Set-Location $Root
& $Python -m adaptive_vr.receiver --host 0.0.0.0 --port 8765
