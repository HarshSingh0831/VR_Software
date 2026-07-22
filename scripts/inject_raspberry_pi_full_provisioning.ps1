[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$sourceScript = Join-Path $workspace ".rpi-provisioning\private\firstrun.sh"
$statusPath = Join-Path $workspace ".rpi-provisioning\full-provisioning-status.json"
$bootRoot = "R:\"

function Write-Status([string]$Phase, [int]$ExitCode, [string]$Message) {
    [ordered]@{
        phase = $Phase
        exit_code = $ExitCode
        message = $Message
        updated_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
}

Write-Status "starting" -1 "Verifying Raspberry Pi card."
try {
    $disk = Get-WmiObject Win32_DiskDrive -Filter "Index=2"
    $serial = "$($disk.SerialNumber)".Trim()
    if (
        $disk.Model -ne "Mass Storage Device USB Device" -or
        $serial -ne "121220160204" -or
        [uint64]$disk.Size -lt 29GB -or
        [uint64]$disk.Size -gt 31GB
    ) {
        throw "Memory-card identity safety check failed."
    }
    $volume = Get-WmiObject Win32_Volume -Filter "DriveLetter='R:'"
    if ($volume.Label -ne "bootfs" -or $volume.FileSystem -ne "FAT32") {
        throw "R: is not the verified Raspberry Pi bootfs volume."
    }
    foreach ($path in @($sourceScript, (Join-Path $bootRoot "cmdline.txt"), (Join-Path $bootRoot "config.txt"))) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required file not found: $path"
        }
    }

    Write-Status "injecting" -1 "Installing complete vivo V40e provisioning."
    $targetScript = Join-Path $bootRoot "firstrun.sh"
    [System.IO.File]::WriteAllBytes($targetScript, [System.IO.File]::ReadAllBytes($sourceScript))
    $cmdlinePath = Join-Path $bootRoot "cmdline.txt"
    $cmdline = [System.IO.File]::ReadAllText($cmdlinePath).Trim()
    $cmdline = [regex]::Replace($cmdline, "\s+systemd\.run=.*$", "")
    $cmdline += " systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
    [System.IO.File]::WriteAllText($cmdlinePath, "$cmdline`n", [System.Text.Encoding]::ASCII)

    if ((Get-FileHash $sourceScript -Algorithm SHA256).Hash -ne (Get-FileHash $targetScript -Algorithm SHA256).Hash) {
        throw "Provisioning script verification failed."
    }
    if (-not ([System.IO.File]::ReadAllText($cmdlinePath).Contains("systemd.run=/boot/firstrun.sh"))) {
        throw "Provisioning boot hook verification failed."
    }
    Write-Status "complete" 0 "Full Pi provisioning verified; bootfs safely ejected."
    & "$env:SystemRoot\System32\mountvol.exe" "R:" /P
    if ($LASTEXITCODE -ne 0) { throw "Provisioning succeeded, but bootfs eject failed." }
}
catch {
    Write-Status "failed" 1 $_.Exception.Message
    Write-Error $_.Exception.Message
    exit 1
}
