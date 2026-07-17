param(
    [string]$Manifest = "models\datasets\fer2013_vr\manifest.csv",
    [string]$Output = "models\cnn",
    [int]$Epochs = 12,
    [int]$BatchSize = 128
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
Set-Location $root
foreach ($region in @("upper_face", "lower_face")) {
    & $python -m adaptive_vr.cnn train --manifest $Manifest --output $Output --task expression --region $region --epochs $Epochs --batch-size $BatchSize
    if ($LASTEXITCODE -ne 0) { throw "CNN training failed for $region." }
}
& $python -m adaptive_vr.cnn evaluate --manifest $Manifest --model-dir $Output --task expression --split test
if ($LASTEXITCODE -ne 0) { throw "CNN fusion evaluation failed." }
