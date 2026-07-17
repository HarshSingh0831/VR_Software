$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BundledPython = "C:\Users\Harsh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $BundledPython)) {
    throw "Bundled Python runtime was not found at $BundledPython"
}

if (-not (Test-Path $VenvPython)) {
    & $BundledPython -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e $ProjectRoot
Write-Host "Host setup complete. Start with scripts\start_receiver.ps1"

