param(
    [string]$Manifest = "models\datasets\fer2013_vr\manifest.csv",
    [string]$Output = "models\trained"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
Set-Location $root
foreach ($region in @("upper_face", "lower_face")) {
    & $python -m adaptive_vr.train_baseline --manifest $Manifest --output $Output --task expression --region $region
    if ($LASTEXITCODE -ne 0) { throw "Training failed for $region." }
}
