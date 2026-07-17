[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$diskNumber = 2
$expectedSerial = "121220160204"
$expectedFriendlyName = "Mass Storage Device"
$expectedMinimumBytes = 29GB
$expectedMaximumBytes = 31GB
$expectedImageSize = 2977955840
$expectedImageHash = "e235fd24fc5f039c08daba7d3abc04aecc7313f979d16d2a3fdad29dd44c33a9"
$devicePath = "\\.\PhysicalDrive$diskNumber"

$workspace = Split-Path -Parent $PSScriptRoot
$imagePath = Join-Path $workspace ".downloads\2026-06-18-raspios-trixie-arm64-lite.img"
$firstRunPath = Join-Path $workspace ".rpi-provisioning\private\firstrun.sh"
$statusPath = Join-Path $workspace ".rpi-provisioning\buffered-flash-status.json"
$transcriptPath = Join-Path $workspace ".rpi-provisioning\buffered-flash-wrapper.log"
$automountDisabled = $false

function Set-BufferedFlashStatus {
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
Set-BufferedFlashStatus -Phase "starting"

try {
    foreach ($requiredPath in @($imagePath, $firstRunPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Required file is missing: $requiredPath"
        }
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
        throw "The card reports that it is write-protected."
    }

    $image = Get-Item -LiteralPath $imagePath
    if ($image.Length -ne $expectedImageSize) {
        throw "Expanded image size mismatch."
    }

    Set-BufferedFlashStatus -Phase "hashing" -Message "Checking expanded image."
    $actualImageHash = (
        Get-FileHash -LiteralPath $imagePath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($actualImageHash -ne $expectedImageHash) {
        throw "Expanded image checksum mismatch."
    }

    Write-Host "Verified target: Disk $diskNumber / $devicePath"
    Write-Host "Device: $($disk.FriendlyName), serial $actualSerial, size $([math]::Round($disk.Size / 1GB, 2)) GB"
    Write-Host "Expanded image size and checksum verified."

    Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class BufferedRawImageWriter {
    private const uint GENERIC_READ = 0x80000000;
    private const uint GENERIC_WRITE = 0x40000000;
    private const uint FILE_SHARE_READ = 0x00000001;
    private const uint FILE_SHARE_WRITE = 0x00000002;
    private const uint OPEN_EXISTING = 3;
    private const uint FILE_ATTRIBUTE_NORMAL = 0x00000080;
    private const uint FILE_BEGIN = 0;
    private const uint FSCTL_LOCK_VOLUME = 0x00090018;
    private const uint FSCTL_UNLOCK_VOLUME = 0x0009001C;
    private const uint FSCTL_DISMOUNT_VOLUME = 0x00090020;
    private const int BUFFER_SIZE = 4 * 1024 * 1024;
    private const long PROGRESS_INTERVAL = 256L * 1024L * 1024L;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DeviceIoControl(
        SafeFileHandle device,
        uint controlCode,
        IntPtr inputBuffer,
        uint inputBufferSize,
        IntPtr outputBuffer,
        uint outputBufferSize,
        out uint bytesReturned,
        IntPtr overlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ReadFile(
        SafeFileHandle file,
        byte[] buffer,
        uint bytesToRead,
        out uint bytesRead,
        IntPtr overlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool WriteFile(
        SafeFileHandle file,
        byte[] buffer,
        uint bytesToWrite,
        out uint bytesWritten,
        IntPtr overlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetFilePointerEx(
        SafeFileHandle file,
        long distanceToMove,
        out long newFilePointer,
        uint moveMethod);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FlushFileBuffers(SafeFileHandle file);

    public static void WriteAndVerify(
        string imagePath,
        string devicePath,
        string bootVolumePath) {
        SafeFileHandle bootVolume = CreateFile(
            bootVolumePath,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            IntPtr.Zero,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            IntPtr.Zero);

        if (bootVolume.IsInvalid) {
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                "Unable to open the boot volume");
        }

        bool bootVolumeLocked = false;
        try {
            uint returned;
            if (!DeviceIoControl(
                bootVolume,
                FSCTL_LOCK_VOLUME,
                IntPtr.Zero,
                0,
                IntPtr.Zero,
                0,
                out returned,
                IntPtr.Zero)) {
                throw new Win32Exception(
                    Marshal.GetLastWin32Error(),
                    "Unable to lock the boot volume");
            }
            bootVolumeLocked = true;

            if (!DeviceIoControl(
                bootVolume,
                FSCTL_DISMOUNT_VOLUME,
                IntPtr.Zero,
                0,
                IntPtr.Zero,
                0,
                out returned,
                IntPtr.Zero)) {
                throw new Win32Exception(
                    Marshal.GetLastWin32Error(),
                    "Unable to dismount the boot volume");
            }

            SafeFileHandle device = CreateFile(
                devicePath,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                IntPtr.Zero,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                IntPtr.Zero);

            if (device.IsInvalid) {
                throw new Win32Exception(
                    Marshal.GetLastWin32Error(),
                    "Unable to open the raw destination device");
            }

            try {
                WriteImage(imagePath, device);
                VerifyImage(imagePath, device);
            }
            finally {
                device.Dispose();
            }
        }
        finally {
            if (bootVolumeLocked) {
                uint returned;
                DeviceIoControl(
                    bootVolume,
                    FSCTL_UNLOCK_VOLUME,
                    IntPtr.Zero,
                    0,
                    IntPtr.Zero,
                    0,
                    out returned,
                    IntPtr.Zero);
            }
            bootVolume.Dispose();
        }
    }

    private static void WriteImage(string imagePath, SafeFileHandle device) {
        byte[] buffer = new byte[BUFFER_SIZE];
        long total;
        long completed = 0;
        long nextProgress = PROGRESS_INTERVAL;

        using (FileStream image = new FileStream(
            imagePath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            BUFFER_SIZE,
            FileOptions.RandomAccess)) {
            total = image.Length;
            long position = total;
            while (position > 0) {
                int count = (int)Math.Min((long)buffer.Length, position);
                position -= count;
                image.Position = position;

                int imageBytesRead = 0;
                while (imageBytesRead < count) {
                    int currentRead = image.Read(
                        buffer,
                        imageBytesRead,
                        count - imageBytesRead);
                    if (currentRead == 0) {
                        throw new EndOfStreamException(
                            "Unexpected end of image at offset " + position);
                    }
                    imageBytesRead += currentRead;
                }

                long newPosition;
                if (!SetFilePointerEx(
                    device,
                    position,
                    out newPosition,
                    FILE_BEGIN)) {
                    throw new Win32Exception(
                        Marshal.GetLastWin32Error(),
                        "Unable to seek destination to offset " + position);
                }

                uint bytesWritten;
                if (!WriteFile(
                    device,
                    buffer,
                    (uint)count,
                    out bytesWritten,
                    IntPtr.Zero)) {
                    throw new Win32Exception(
                        Marshal.GetLastWin32Error(),
                        "Raw image write failed at offset " + position);
                }
                if (bytesWritten != (uint)count) {
                    throw new IOException(
                        "Short raw write at offset " + position +
                        ": expected " + count + ", wrote " + bytesWritten);
                }

                completed += count;
                if (completed >= nextProgress) {
                    Console.WriteLine(
                        "WRITE_PROGRESS {0} {1}",
                        completed,
                        total);
                    nextProgress += PROGRESS_INTERVAL;
                }
            }
        }

        if (!FlushFileBuffers(device)) {
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                "FlushFileBuffers failed after writing");
        }

        Console.WriteLine("WRITE_COMPLETE {0}", completed);
    }

    private static void VerifyImage(string imagePath, SafeFileHandle device) {
        long newPosition;
        if (!SetFilePointerEx(device, 0, out newPosition, FILE_BEGIN)) {
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                "Unable to seek for verification");
        }

        byte[] imageBuffer = new byte[BUFFER_SIZE];
        byte[] deviceBuffer = new byte[BUFFER_SIZE];
        long total;
        long completed = 0;
        long nextProgress = PROGRESS_INTERVAL;

        using (FileStream image = new FileStream(
            imagePath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            BUFFER_SIZE,
            FileOptions.SequentialScan)) {
            total = image.Length;
            int imageCount;
            while ((imageCount = image.Read(
                imageBuffer,
                0,
                imageBuffer.Length)) > 0) {
                uint deviceCount;
                if (!ReadFile(
                    device,
                    deviceBuffer,
                    (uint)imageCount,
                    out deviceCount,
                    IntPtr.Zero)) {
                    throw new Win32Exception(
                        Marshal.GetLastWin32Error(),
                        "Raw verification read failed at offset " + completed);
                }
                if (deviceCount != (uint)imageCount) {
                    throw new IOException(
                        "Short verification read at offset " + completed);
                }

                for (int index = 0; index < imageCount; index++) {
                    if (imageBuffer[index] != deviceBuffer[index]) {
                        throw new IOException(
                            "Verification mismatch at byte " +
                            (completed + index));
                    }
                }

                completed += imageCount;
                if (completed >= nextProgress) {
                    Console.WriteLine(
                        "VERIFY_PROGRESS {0} {1}",
                        completed,
                        total);
                    nextProgress += PROGRESS_INTERVAL;
                }
            }
        }

        Console.WriteLine("VERIFY_COMPLETE {0}", completed);
    }
}
"@

    Set-BufferedFlashStatus -Phase "writing" -Message "Buffered raw write in progress."
    $preWriteBootPartition = Get-Partition -DiskNumber $diskNumber |
        Sort-Object Offset |
        Select-Object -First 1
    if (-not $preWriteBootPartition.DriveLetter) {
        $preWriteBootPartition | Add-PartitionAccessPath -AssignDriveLetter
        Start-Sleep -Seconds 2
        $preWriteBootPartition = Get-Partition `
            -DiskNumber $diskNumber `
            -PartitionNumber $preWriteBootPartition.PartitionNumber
    }
    if (-not $preWriteBootPartition.DriveLetter) {
        throw "The boot partition has no drive letter for exclusive locking."
    }
    $bootVolumePath = "\\.\$($preWriteBootPartition.DriveLetter):"

    & "C:\Windows\System32\mountvol.exe" /N
    if ($LASTEXITCODE -ne 0) {
        throw "Could not temporarily disable Windows automount."
    }
    $automountDisabled = $true
    Start-Sleep -Seconds 2

    Write-Host "Writing the Raspberry Pi image with the compatible buffered path."
    try {
        [BufferedRawImageWriter]::WriteAndVerify(
            $imagePath,
            $devicePath,
            $bootVolumePath
        )
    }
    finally {
        if ($automountDisabled) {
            & "C:\Windows\System32\mountvol.exe" /E
            $automountDisabled = $false
        }
    }

    Set-BufferedFlashStatus -Phase "provisioning" -Message "Locating the boot partition."
    Write-Host "Raw image write and byte-for-byte verification succeeded."
    Update-Disk -Number $diskNumber -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5

    $partitions = @(
        Get-Partition -DiskNumber $diskNumber -ErrorAction Stop |
            Sort-Object Offset
    )
    if ($partitions.Count -lt 2) {
        throw "The written image does not expose the expected boot and root partitions."
    }

    $bootPartition = $partitions[0]
    if (-not $bootPartition.DriveLetter) {
        $bootPartition | Add-PartitionAccessPath -AssignDriveLetter
        Start-Sleep -Seconds 2
        $bootPartition = Get-Partition `
            -DiskNumber $diskNumber `
            -PartitionNumber $bootPartition.PartitionNumber
    }
    if (-not $bootPartition.DriveLetter) {
        throw "Windows could not assign a drive letter to the boot partition."
    }

    $bootRoot = "$($bootPartition.DriveLetter):\"
    $cmdlinePath = Join-Path $bootRoot "cmdline.txt"
    $configPath = Join-Path $bootRoot "config.txt"
    $targetFirstRunPath = Join-Path $bootRoot "firstrun.sh"

    if (-not (Test-Path -LiteralPath $cmdlinePath -PathType Leaf)) {
        throw "cmdline.txt was not found on the boot partition."
    }
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        throw "config.txt was not found on the boot partition."
    }

    $firstRunBytes = [System.IO.File]::ReadAllBytes($firstRunPath)
    [System.IO.File]::WriteAllBytes($targetFirstRunPath, $firstRunBytes)

    $cmdline = [System.IO.File]::ReadAllText($cmdlinePath).Trim()
    $firstRunHook = "systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
    if (-not $cmdline.Contains("systemd.run=/boot/firstrun.sh")) {
        $cmdline = "$cmdline $firstRunHook"
    }
    [System.IO.File]::WriteAllText(
        $cmdlinePath,
        "$cmdline`n",
        [System.Text.Encoding]::ASCII
    )

    $sourceFirstRunHash = (
        Get-FileHash -LiteralPath $firstRunPath -Algorithm SHA256
    ).Hash
    $targetFirstRunHash = (
        Get-FileHash -LiteralPath $targetFirstRunPath -Algorithm SHA256
    ).Hash
    if ($sourceFirstRunHash -ne $targetFirstRunHash) {
        throw "The copied first-run provisioning script failed verification."
    }
    if (-not (
        [System.IO.File]::ReadAllText($cmdlinePath)
    ).Contains("systemd.run=/boot/firstrun.sh")) {
        throw "The first-run boot hook failed verification."
    }

    $volume = Get-Volume -Partition $bootPartition
    $message = (
        "Verified boot partition {0}: label={1}, filesystem={2}; " +
        "root partition count={3}; provisioning injected."
    ) -f (
        $bootPartition.DriveLetter,
        $volume.FileSystemLabel,
        $volume.FileSystem,
        $partitions.Count
    )
    Write-Host $message
    Set-BufferedFlashStatus -Phase "complete" -ExitCode 0 -Message $message
}
catch {
    $failureMessage = $_.Exception.Message
    Set-BufferedFlashStatus -Phase "failed" -ExitCode 1 -Message $failureMessage
    Write-Error $failureMessage
    exit 1
}
finally {
    if ($automountDisabled) {
        & "C:\Windows\System32\mountvol.exe" /E
    }
    Stop-Transcript
}
