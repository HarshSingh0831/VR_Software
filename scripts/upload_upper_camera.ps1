$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Cli = Join-Path $Root ".tools\arduino-cli\arduino-cli.exe"
$Config = Join-Path $Root ".arduino\arduino-cli.yaml"
$Sketch = Join-Path $Root "firmware\esp32_local_processor"
$Fqbn = "esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=fatflash,PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc"

$Ports = [System.IO.Ports.SerialPort]::GetPortNames()
if ($Ports.Count -ne 1) {
    throw "Expected one serial device; detected: $($Ports -join ', ')"
}

& $Cli compile --fqbn $Fqbn $Sketch --config-file $Config
if ($LASTEXITCODE -ne 0) { throw "Firmware compilation failed." }
& $Cli upload -p $Ports[0] --fqbn $Fqbn $Sketch --config-file $Config
if ($LASTEXITCODE -ne 0) { throw "Firmware upload failed." }
