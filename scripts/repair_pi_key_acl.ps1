[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$key = Join-Path $root ".rpi-provisioning\private\adaptive_vr_pi_ed25519"
$publicKey = "$key.pub"
if (-not (Test-Path -LiteralPath $publicKey -PathType Leaf)) {
    throw "Expected Pi public key is missing."
}

& "$env:SystemRoot\System32\takeown.exe" /F $key | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not take ownership of the Pi key." }
& "$env:SystemRoot\System32\icacls.exe" $key /inheritance:r /grant:r "$env:USERNAME`:R" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not restrict the Pi key ACL." }
& "$env:SystemRoot\System32\icacls.exe" $key /remove:g "$env:COMPUTERNAME\CodexSandboxOffline" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not remove the sandbox ACL from the Pi key." }
Write-Output "Pi private key ACL repaired and restricted to $env:USERNAME."
