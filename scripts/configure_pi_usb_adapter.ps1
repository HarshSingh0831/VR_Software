[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$logPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".rpi-provisioning\usb-adapter-config.log"
Start-Transcript -LiteralPath $logPath -Force
try {
$alias = "Ethernet 4"
$adapter = Get-NetAdapter -Name $alias
if ($adapter.InterfaceDescription -notmatch "Raspberry Pi USB Remote NDIS") {
    throw "$alias is not the Raspberry Pi USB RNDIS adapter."
}

Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Dhcp Disabled
Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne "10.12.194.2" } |
    Remove-NetIPAddress -Confirm:$false

if (-not (Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq "10.12.194.2" -and $_.PrefixLength -eq 28 })) {
    New-NetIPAddress -InterfaceAlias $alias -IPAddress "10.12.194.2" -PrefixLength 28 | Out-Null
}

Restart-NetAdapter -Name $alias
Start-Sleep -Seconds 3
Write-Output "Configured $alias as 10.12.194.2/28"
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
finally {
    Stop-Transcript
}
