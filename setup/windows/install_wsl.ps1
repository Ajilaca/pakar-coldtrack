# Pasang WSL2 Ubuntu 24.04 dan batas memori WSL untuk sintesis dan layout ColdTrack.
# Jalankan di PowerShell sebagai Administrator, lalu restart Windows:
#   powershell -ExecutionPolicy Bypass -File setup\windows\install_wsl.ps1
#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

wsl --install -d Ubuntu-24.04

$cfg = Join-Path $env:USERPROFILE ".wslconfig"
if (Test-Path $cfg) {
    Write-Host ".wslconfig sudah ada, tidak ditimpa: $cfg"
    Write-Host "Bandingkan isinya dengan setup\windows\wslconfig.example."
} else {
    Copy-Item (Join-Path $PSScriptRoot "wslconfig.example") $cfg
    Write-Host "Dibuat: $cfg"
}

Write-Host ""
Write-Host "Selanjutnya:"
Write-Host "  1. Restart Windows."
Write-Host "  2. Buka 'Ubuntu 24.04' dari Start menu, buat user Linux."
Write-Host "  3. Pasang Docker Desktop, centang 'Use WSL 2', aktifkan WSL Integration untuk Ubuntu-24.04."
Write-Host "  4. Lanjut ke setup/README.md bagian 2."
