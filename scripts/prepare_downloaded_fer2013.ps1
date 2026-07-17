param(
    [string]$Download = "models\downloads\fer2013",
    [string]$Output = "models\datasets\fer2013_vr",
    [int]$LimitPerSplit = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$arguments = @(
    "-m", "adaptive_vr.public_dataset", "fer2013-parquet",
    "--input", (Join-Path $Download "train-00000-of-00001.parquet"),
    "--input", (Join-Path $Download "valid-00000-of-00001.parquet"),
    "--input", (Join-Path $Download "test-00000-of-00001.parquet"),
    "--output", $Output
)
if ($LimitPerSplit -gt 0) { $arguments += @("--limit-per-split", $LimitPerSplit) }
Set-Location $root
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "Downloaded FER2013 preparation failed." }
