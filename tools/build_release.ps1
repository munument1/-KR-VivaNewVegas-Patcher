param(
    [string]$Python = ".venv\Scripts\python.exe",
    [string]$Catalog = "bundles\sst-release-20261006"
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$Catalog\catalog.json")) {
    throw "SST catalog is missing: $Catalog"
}

$env:PYTHONPATH = $root
& $Python -c "from pathlib import Path; import vnvkr; from tools.prepare_release_package import validate_catalog; validate_catalog(vnvkr.read_json(Path(r'$Catalog')/'catalog.json')); print('catalog validation: OK')"
if ($LASTEXITCODE -ne 0) { throw 'Catalog validation failed' }

Remove-Item -Recurse -Force 'build\VNVKoreanPatcher','build\VNVKRXEditWorker' -ErrorAction SilentlyContinue
Remove-Item -Force 'dist\VNVKoreanPatcher.exe','dist\VNVKRXEditWorker.exe' -ErrorAction SilentlyContinue

$workerArgs = @(
    '-m','PyInstaller','--noconfirm','--onefile','--console',
    '--name','VNVKRXEditWorker',
    '--manifest','tools\xedit_worker_utf8.manifest',
    'vnvkr_xedit_worker.py'
)
& $Python @workerArgs
if ($LASTEXITCODE -ne 0) { throw 'XEdit worker build failed' }

$mainArgs = @(
    '-m','PyInstaller','--noconfirm','--onefile','--windowed',
    '--name','VNVKoreanPatcher',
    '--add-data',"$Catalog;TranslationData",
    '--add-binary','dist\VNVKRXEditWorker.exe;.',
    '--add-binary','.tools\xeditlib-native\XEditLib.dll;Backend',
    '--add-data','.tools\xeditlib-native\FalloutNV.Hardcoded.dat;Backend',
    '--add-data','.tools\xeditlib-native\icudtl.dat;Backend',
    '--add-data','.tools\xeditlib-native\LICENSE;Backend',
    'vnvkr_gui.py'
)
& $Python @mainArgs
if ($LASTEXITCODE -ne 0) { throw 'Patcher build failed' }

$exe = Resolve-Path 'dist\VNVKoreanPatcher.exe'
$hash = Get-FileHash $exe -Algorithm SHA256
$size = (Get-Item $exe).Length
Write-Host 'Single-file release:' $exe
Write-Host 'Size MB:' ([math]::Round($size / 1MB, 1))
Write-Host 'SHA256:' $hash.Hash
