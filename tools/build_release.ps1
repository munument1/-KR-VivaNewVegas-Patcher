param(
    [string]$Python = ".venv\Scripts\python.exe",
    [string]$Catalog = "bundles\records-release-20261005"
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Remove-Item -Recurse -Force 'build\VNVKoreanPatcher','dist\VNVKoreanPatcher' -ErrorAction SilentlyContinue
& $Python -m PyInstaller --noconfirm --onedir --windowed --name VNVKoreanPatcher vnvkr_gui.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$env:PYTHONPATH = $root
& $Python tools\prepare_release_package.py --dist 'dist\VNVKoreanPatcher' --catalog $Catalog
if ($LASTEXITCODE -ne 0) { throw 'Release package preparation failed' }
Write-Host 'Release package:' (Resolve-Path 'dist\VNVKoreanPatcher')
