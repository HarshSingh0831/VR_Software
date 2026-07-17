$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run scripts/setup_host.ps1 first."
}
Set-Location $root
& $python -m streamlit run streamlit_app.py
