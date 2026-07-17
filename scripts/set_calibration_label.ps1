param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "focused", "thinking", "confused", "frustrated", "happy", "answering",
        "bored", "drowsy", "looking_away", "distracted", "idle", "headset_removed"
    )]
    [string]$Label,

    [string]$PiHost = "adaptive-vr-pi.local"
)

$ErrorActionPreference = "Stop"
$command = "PYTHONPATH=/opt/adaptive-vr/host python3 -m adaptive_vr.calibration_control label $Label"
& ssh "vrpi@$PiHost" $command
if ($LASTEXITCODE -ne 0) { throw "Unable to change the calibration label." }
