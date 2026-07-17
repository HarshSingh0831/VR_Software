[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$diskNumber = 2
$expectedSerial = "121220160204"
$expectedFriendlyName = "Mass Storage Device"
$expectedMinimumBytes = 29GB
$expectedMaximumBytes = 31GB
$expectedPackageHash = "9080c652ea4e604ff66182f9cc50d1e85655873362eeb89fbd477925fc716e50"

$workspace = Split-Path -Parent $PSScriptRoot
$sourceScript = Join-Path $workspace ".rpi-provisioning\private\install-official-usb-gadget.sh"
$sourcePackage = Join-Path $workspace ".tools\rpi-imager\rpi-usb-gadget_1.0.6_arm64.deb"
$statusPath = Join-Path $workspace ".rpi-provisioning\official-gadget-injection-status.json"
$transcriptPath = Join-Path $workspace ".rpi-provisioning\official-gadget-injection.log"

function Set-InjectionStatus {
    param(
        [Parameter(Mandatory)]
        [string]$Phase,
        [int]$ExitCode = -1,
        [string]$Message = ""
    )

    $status = [ordered]@{
        phase = $Phase
        exit_code = $ExitCode
        message = $Message
        updated_at = (Get-Date).ToString("o")
    }
    [System.IO.File]::WriteAllText(
        $statusPath,
        ($status | ConvertTo-Json),
        [System.Text.UTF8Encoding]::new($false)
    )
}

Start-Transcript -LiteralPath $transcriptPath -Force
Set-InjectionStatus -Phase "starting"

try {
    foreach ($requiredPath in @($sourceScript, $sourcePackage)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Required file is missing: $requiredPath"
        }
    }

    $packageHash = (
        Get-FileHash -LiteralPath $sourcePackage -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($packageHash -ne $expectedPackageHash) {
        throw "Official USB gadget package checksum mismatch."
    }

    $disk = Get-Disk -Number $diskNumber
    $actualSerial = "$($disk.SerialNumber)".Trim()
    if (
        $disk.IsBoot -or
        $disk.IsSystem -or
        $disk.BusType -ne "USB" -or
        $actualSerial -ne $expectedSerial -or
        $disk.FriendlyName -ne $expectedFriendlyName -or
        $disk.Size -lt $expectedMinimumBytes -or
        $disk.Size -gt $expectedMaximumBytes
    ) {
        throw "Memory-card identity safety check failed."
    }
    if ($disk.IsReadOnly) {
        throw "The memory card is write-protected."
    }

    $bootPartition = Get-Partition -DiskNumber $diskNumber -PartitionNumber 1
    if (-not $bootPartition.DriveLetter) {
        $bootPartition | Add-PartitionAccessPath -AssignDriveLetter
        Start-Sleep -Seconds 2
        $bootPartition = Get-Partition -DiskNumber $diskNumber -PartitionNumber 1
    }
    if (-not $bootPartition.DriveLetter) {
        throw "Windows could not assign a drive letter to bootfs."
    }

    $letter = $bootPartition.DriveLetter
    $volume = Get-Volume -Partition $bootPartition
    if ($volume.FileSystem -ne "FAT32") {
        throw "Safety check failed: partition 1 is not FAT32."
    }
    if ($volume.HealthStatus -ne "Healthy") {
        Repair-Volume -DriveLetter $letter -OfflineScanAndFix | Out-Null
        Start-Sleep -Seconds 2
    }

    $bootRoot = "$letter`:\"
    $cmdlinePath = Join-Path $bootRoot "cmdline.txt"
    $configPath = Join-Path $bootRoot "config.txt"
    $targetScript = Join-Path $bootRoot "firstrun.sh"
    $targetPackage = Join-Path $bootRoot "rpi-usb-gadget_1.0.6_arm64.deb"

    if (
        -not (Test-Path -LiteralPath $cmdlinePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $configPath -PathType Leaf)
    ) {
        throw "Required Raspberry Pi boot files were not found."
    }

    Set-InjectionStatus -Phase "injecting" -Message "Writing official USB gadget installer."
    [System.IO.File]::WriteAllBytes(
        $targetScript,
        [System.IO.File]::ReadAllBytes($sourceScript)
    )
    [System.IO.File]::WriteAllBytes(
        $targetPackage,
        [System.IO.File]::ReadAllBytes($sourcePackage)
    )

    $cmdline = [System.IO.File]::ReadAllText($cmdlinePath).Trim()
    $cmdline = [regex]::Replace(
        $cmdline,
        "\s+modules-load=dwc2,g_ether",
        ""
    )
    $cmdline = [regex]::Replace($cmdline, "\s+systemd\.run=.*$", "")
    $hook = "systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
    $cmdline += " $hook"
    [System.IO.File]::WriteAllText(
        $cmdlinePath,
        "$cmdline`n",
        [System.Text.Encoding]::ASCII
    )

    $scriptHashSource = (
        Get-FileHash -LiteralPath $sourceScript -Algorithm SHA256
    ).Hash
    $scriptHashTarget = (
        Get-FileHash -LiteralPath $targetScript -Algorithm SHA256
    ).Hash
    $packageHashTarget = (
        Get-FileHash -LiteralPath $targetPackage -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $writtenCmdline = [System.IO.File]::ReadAllText($cmdlinePath)

    if ($scriptHashSource -ne $scriptHashTarget) {
        throw "Official gadget installer script failed verification."
    }
    if ($packageHashTarget -ne $expectedPackageHash) {
        throw "Copied official gadget package failed verification."
    }
    if ($writtenCmdline.Contains("modules-load=dwc2,g_ether")) {
        throw "The earlier manual module setting was not removed."
    }
    if (-not $writtenCmdline.Contains("systemd.run=/boot/firstrun.sh")) {
        throw "The official gadget installation hook failed verification."
    }

    $message = "Official Raspberry Pi USB gadget package verified on bootfs $letter`:."
    Set-InjectionStatus -Phase "complete" -ExitCode 0 -Message $message
    Write-Host $message

    & "C:\Windows\System32\mountvol.exe" "$letter`:" /P
    if ($LASTEXITCODE -ne 0) {
        throw "Configuration succeeded, but Windows could not eject bootfs."
    }
    Write-Host "Memory card safely ejected."
}
catch {
    $failureMessage = $_.Exception.Message
    Set-InjectionStatus -Phase "failed" -ExitCode 1 -Message $failureMessage
    Write-Error $failureMessage
    exit 1
}
finally {
    Stop-Transcript
}
