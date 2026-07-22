param(
    [Parameter(Mandatory = $true)]
    [string[]]$Session,
    [string]$DatasetOutput = "models\datasets\headset_vr",
    [string]$ModelOutput = "models\fine_tuned",
    [int]$Epochs = 20,
    [int]$BatchSize = 64,
    [double]$LearningRate = 0.0001,
    [int]$FreezeFeatureEpochs = 2,
    [switch]$AllowPartialClasses
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found at $python. Run scripts\setup_host.ps1 first."
}

Set-Location $root
$datasetArguments = @("-m", "adaptive_vr.headset_dataset")
foreach ($sessionPath in $Session) {
    if (-not (Test-Path -LiteralPath $sessionPath)) {
        throw "Headset session not found: $sessionPath"
    }
    $datasetArguments += @("--session", $sessionPath)
}
$datasetArguments += @("--output", $DatasetOutput)
& $python @datasetArguments
if ($LASTEXITCODE -ne 0) { throw "Headset dataset preparation failed." }

$manifest = Join-Path $DatasetOutput "manifest.csv"
foreach ($region in @("upper_face", "lower_face")) {
    $pretrained = Join-Path "models\cnn" "expression_${region}_cnn.pt"
    if (-not (Test-Path -LiteralPath $pretrained)) {
        throw "Pretrained checkpoint not found: $pretrained"
    }
    $trainArguments = @(
        "-m", "adaptive_vr.cnn", "fine-tune",
        "--manifest", $manifest,
        "--output", $ModelOutput,
        "--task", "vr_state",
        "--region", $region,
        "--pretrained", $pretrained,
        "--epochs", $Epochs,
        "--batch-size", $BatchSize,
        "--learning-rate", $LearningRate,
        "--freeze-feature-epochs", $FreezeFeatureEpochs
    )
    if ($AllowPartialClasses) { $trainArguments += "--allow-partial-classes" }
    & $python @trainArguments
    if ($LASTEXITCODE -ne 0) { throw "Fine-tuning failed for $region." }
}

Write-Host "Fine-tuned checkpoints are ready in $ModelOutput"
