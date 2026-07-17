param(
    [Parameter(Mandatory = $true)]
    [string]$Csv,
    [string]$Output = "models\datasets\fer2013_vr",
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$arguments = @("-m", "adaptive_vr.public_dataset", "fer2013", "--csv", $Csv, "--output", $Output)
if ($Limit -gt 0) { $arguments += @("--limit", $Limit) }
Set-Location $root
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "FER2013 preparation failed." }
