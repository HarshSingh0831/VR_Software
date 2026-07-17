param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9_-]+$")]
    [string]$Participant,

    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "focused", "thinking", "confused", "frustrated", "happy", "answering",
        "bored", "drowsy", "looking_away", "distracted", "idle", "headset_removed"
    )]
    [string]$Label,

    [ValidatePattern("^[A-Za-z0-9_-]*$")]
    [string]$Session = "",

    [string]$PiHost = "adaptive-vr-pi.local"
)

$ErrorActionPreference = "Stop"
$command = "PYTHONPATH=/opt/adaptive-vr/host python3 -m adaptive_vr.calibration_control start --participant $Participant --label $Label"
if ($Session) {
    $command += " --session $Session"
}
& ssh "vrpi@$PiHost" $command
if ($LASTEXITCODE -ne 0) { throw "Unable to start the calibration session." }
