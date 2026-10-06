param(
    [string]$Python = ".venv\Scripts\python.exe",
    [string]$Catalog = "bundles\sst-release-20261006"
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Remove-Item -Recurse -Force 'build\VNVKoreanPatcher','dist\VNVKoreanPatcher','build\VNVKRXEditWorker' -ErrorAction SilentlyContinue
Remove-Item -Force 'dist\VNVKRXEditWorker.exe' -ErrorAction SilentlyContinue

& $Python -m PyInstaller --noconfirm --onefile --console --name VNVKRXEditWorker --manifest 'tools\xedit_worker_utf8.manifest' vnvkr_xedit_worker.py
if ($LASTEXITCODE -ne 0) { throw 'XEdit worker build failed' }

& $Python -m PyInstaller --noconfirm --onedir --windowed --name VNVKoreanPatcher vnvkr_gui.py
if ($LASTEXITCODE -ne 0) { throw 'Patcher build failed' }

$env:PYTHONPATH = $root
& $Python tools\prepare_release_package.py --dist 'dist\VNVKoreanPatcher' --catalog $Catalog --worker 'dist\VNVKRXEditWorker.exe'
if ($LASTEXITCODE -ne 0) { throw 'Release package preparation failed' }

Write-Host 'Release package:' (Resolve-Path 'dist\VNVKoreanPatcher')
