[CmdletBinding()]
param(
    [string]$DriveLetter = "R"
)

$ErrorActionPreference = "Stop"
$disk = Get-Disk -Number 2
$serial = "$($disk.SerialNumber)".Trim()
if (
    $disk.IsBoot -or
    $disk.IsSystem -or
    $disk.BusType -ne "USB" -or
    $serial -ne "121220160204" -or
    $disk.Size -lt 29GB -or
    $disk.Size -gt 31GB
) {
    throw "Memory-card identity safety check failed."
}

$partition = Get-Partition -DiskNumber 2 -PartitionNumber 1
if ($partition.Type -ne "FAT32 XINT13" -or $partition.Size -lt 500MB -or $partition.Size -gt 550MB) {
    throw "Partition 1 is not the expected Raspberry Pi bootfs partition."
}

$accessPath = "${DriveLetter}:\"
if (-not $partition.DriveLetter) {
    if (Test-Path -LiteralPath $accessPath) {
        throw "Drive $DriveLetter is already in use."
    }
    Add-PartitionAccessPath -DiskNumber 2 -PartitionNumber 1 -AccessPath $accessPath
}

if (-not (Test-Path -LiteralPath (Join-Path $accessPath "cmdline.txt"))) {
    throw "Mounted partition does not contain cmdline.txt."
}
Write-Output "Verified Raspberry Pi bootfs mounted at $accessPath"
