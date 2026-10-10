param(
    [string]$Python = ".venv\Scripts\python.exe",
    [string]$Catalog = "bundles\sst-release-20261006",
    [string]$BuildRoot = ""
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$Catalog\catalog.json")) {
    throw "SST catalog is missing: $Catalog"
}
$Catalog = (Resolve-Path $Catalog).Path

$env:PYTHONPATH = $root
& $Python -c "from pathlib import Path; import vnvkr; from tools.prepare_release_package import validate_catalog; validate_catalog(vnvkr.read_json(Path(r'$Catalog')/'catalog.json')); print('catalog validation: OK')"
if ($LASTEXITCODE -ne 0) { throw 'Catalog validation failed' }

if (-not $BuildRoot) {
    $BuildRoot = & $Python -c "from pathlib import Path; import tempfile; p=Path('dist'); p.mkdir(exist_ok=True); print(tempfile.mkdtemp(prefix='VNV-release-', dir=p))"
    if ($LASTEXITCODE -ne 0) { throw 'Build workspace allocation failed' }
} elseif (Test-Path $BuildRoot) {
    throw "Use a new build directory: $BuildRoot"
}
$BuildRoot = [System.IO.Path]::GetFullPath($BuildRoot)

$workerArgs = @(
    '-m','PyInstaller','--noconfirm','--onefile','--console',
    '--name','VNVKRXEditWorker',
    '--manifest',"$root\tools\xedit_worker_utf8.manifest",
    '--distpath',$BuildRoot,
    '--workpath',"$BuildRoot\worker-build",
    '--specpath',"$BuildRoot\spec",
    "$root\vnvkr_xedit_worker.py"
)
& $Python @workerArgs
if ($LASTEXITCODE -ne 0) { throw 'XEdit worker build failed' }

$mainArgs = @(
    '-m','PyInstaller','--noconfirm','--onefile','--windowed',
    '--name','VNVKoreanPatcher',
    '--distpath',$BuildRoot,
    '--workpath',"$BuildRoot\patcher-build",
    '--specpath',"$BuildRoot\spec",
    '--add-data',"$Catalog;TranslationData",
    '--add-binary',"$BuildRoot\VNVKRXEditWorker.exe;.",
    '--add-binary',"$root\.tools\xeditlib-native\XEditLib.dll;Backend",
    '--add-data',"$root\.tools\xeditlib-native\FalloutNV.Hardcoded.dat;Backend",
    '--add-data',"$root\.tools\xeditlib-native\icudtl.dat;Backend",
    '--add-data',"$root\.tools\xeditlib-native\LICENSE;Backend",
    "$root\vnvkr_gui.py"
)
& $Python @mainArgs
if ($LASTEXITCODE -ne 0) { throw 'Patcher build failed' }

$exe = Resolve-Path "$BuildRoot\VNVKoreanPatcher.exe"
$hash = Get-FileHash $exe -Algorithm SHA256
$size = (Get-Item $exe).Length
Write-Host 'Single-file release:' $exe
Write-Host 'Size MB:' ([math]::Round($size / 1MB, 1))
Write-Host 'SHA256:' $hash.Hash
