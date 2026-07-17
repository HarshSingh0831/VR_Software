param(
    [string]$PiHost = "adaptive-vr-pi.local"
)

$ErrorActionPreference = "Stop"
$command = "PYTHONPATH=/opt/adaptive-vr/host python3 -m adaptive_vr.calibration_control status"
& ssh "vrpi@$PiHost" $command
if ($LASTEXITCODE -ne 0) { throw "Unable to read calibration status." }
