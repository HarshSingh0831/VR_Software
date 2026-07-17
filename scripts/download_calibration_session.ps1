param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9_-]+$")]
    [string]$Session,

    [string]$Destination = "calibration-data",

    [string]$PiHost = "adaptive-vr-pi.local"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root $Destination
New-Item -ItemType Directory -Path $target -Force | Out-Null
& scp -r "vrpi@${PiHost}:/var/lib/adaptive-vr/calibration/sessions/$Session" $target
if ($LASTEXITCODE -ne 0) { throw "Unable to download calibration session $Session." }
Write-Host "Session downloaded to $target"
