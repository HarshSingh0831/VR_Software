[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$diskNumber = 2
$expectedSerial = "121220160204"
$expectedFriendlyName = "Mass Storage Device"
$expectedMinimumBytes = 29GB
$expectedMaximumBytes = 31GB

$workspace = Split-Path -Parent $PSScriptRoot
$sourceScript = Join-Path $workspace ".rpi-provisioning\private\enable-usb-gadget.sh"
$statusPath = Join-Path $workspace ".rpi-provisioning\usb-gadget-injection-status.json"
$transcriptPath = Join-Path $workspace ".rpi-provisioning\usb-gadget-injection.log"

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
    if (-not (Test-Path -LiteralPath $sourceScript -PathType Leaf)) {
        throw "The prepared USB gadget script is missing."
    }

    $disk = Get-Disk -Number $diskNumber
    $actualSerial = "$($disk.SerialNumber)".Trim()

    if ($disk.IsBoot -or $disk.IsSystem) {
        throw "Safety check failed: Disk $diskNumber is a boot/system disk."
    }
    if ($disk.BusType -ne "USB") {
        throw "Safety check failed: Disk $diskNumber is not USB."
    }
    if ($actualSerial -ne $expectedSerial) {
        throw "Safety check failed: serial number changed."
    }
    if ($disk.FriendlyName -ne $expectedFriendlyName) {
        throw "Safety check failed: device name changed."
    }
    if ($disk.Size -lt $expectedMinimumBytes -or $disk.Size -gt $expectedMaximumBytes) {
        throw "Safety check failed: card size changed."
    }
    if ($disk.IsReadOnly) {
        throw "The memory card is write-protected."
    }

    $bootPartition = Get-Partition `
        -DiskNumber $diskNumber `
        -PartitionNumber 1
    if (-not $bootPartition.DriveLetter) {
        $bootPartition | Add-PartitionAccessPath -AssignDriveLetter
        Start-Sleep -Seconds 2
        $bootPartition = Get-Partition `
            -DiskNumber $diskNumber `
            -PartitionNumber 1
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

    if (-not (Test-Path -LiteralPath $cmdlinePath -PathType Leaf)) {
        throw "cmdline.txt was not found on bootfs."
    }
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        throw "config.txt was not found on bootfs."
    }

    Set-InjectionStatus -Phase "injecting" -Message "Writing USB gadget boot configuration."
    [System.IO.File]::WriteAllBytes(
        $targetScript,
        [System.IO.File]::ReadAllBytes($sourceScript)
    )

    $config = [System.IO.File]::ReadAllText($configPath)
    if (-not $config.Contains("dtoverlay=dwc2")) {
        if (-not $config.EndsWith("`n")) {
            $config += "`n"
        }
        $config += "`n[all]`ndtoverlay=dwc2,dr_mode=peripheral`n"
        [System.IO.File]::WriteAllText(
            $configPath,
            $config,
            [System.Text.UTF8Encoding]::new($false)
        )
    }

    $cmdline = [System.IO.File]::ReadAllText($cmdlinePath).Trim()
    $cmdline = [regex]::Replace($cmdline, "\s+systemd\.run=.*$", "")
    if (-not $cmdline.Contains("modules-load=dwc2,g_ether")) {
        $cmdline += " modules-load=dwc2,g_ether"
    }
    $hook = "systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
    $cmdline += " $hook"
    [System.IO.File]::WriteAllText(
        $cmdlinePath,
        "$cmdline`n",
        [System.Text.Encoding]::ASCII
    )

    $sourceHash = (Get-FileHash -LiteralPath $sourceScript -Algorithm SHA256).Hash
    $targetHash = (Get-FileHash -LiteralPath $targetScript -Algorithm SHA256).Hash
    $writtenConfig = [System.IO.File]::ReadAllText($configPath)
    $writtenCmdline = [System.IO.File]::ReadAllText($cmdlinePath)

    if ($sourceHash -ne $targetHash) {
        throw "The copied USB gadget script failed hash verification."
    }
    if (-not $writtenConfig.Contains("dtoverlay=dwc2")) {
        throw "The dwc2 overlay failed verification."
    }
    if (-not $writtenCmdline.Contains("modules-load=dwc2,g_ether")) {
        throw "The gadget module boot setting failed verification."
    }
    if (-not $writtenCmdline.Contains("systemd.run=/boot/firstrun.sh")) {
        throw "The USB gadget first-run hook failed verification."
    }

    $message = "USB gadget configuration verified on bootfs drive $letter`:."
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
