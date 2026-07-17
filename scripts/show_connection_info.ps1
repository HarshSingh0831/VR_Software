$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Secrets = Join-Path $ProjectRoot "firmware\esp32_local_processor\secrets.h"

$ipconfig = ipconfig | Out-String
$match = [regex]::Match($ipconfig, 'Wireless LAN adapter Wi-Fi:[\s\S]*?IPv4 Address[^:]*:\s*([0-9.]+)')
$currentIp = if ($match.Success) { $match.Groups[1].Value } else { "not detected" }

Write-Host "Laptop Wi-Fi IPv4: $currentIp"
Write-Host "Receiver URL: ws://${currentIp}:8765/"
Write-Host "Firmware settings: $Secrets"
Write-Host "Both the laptop and camera must use the same Wi-Fi network."

