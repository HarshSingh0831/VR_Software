$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

Set-Location $Root
& $Python -m adaptive_vr.simulator --uri ws://127.0.0.1:8765 --duration 5 --rate 10
