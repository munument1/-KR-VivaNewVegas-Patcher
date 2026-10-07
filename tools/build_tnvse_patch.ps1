param([string]$Source = '.tnvse-source')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$commit = '11c69482acc1228750a5b1aa3cae3f938d014eb1'
if (Test-Path $Source) { throw "Use a fresh source directory: $Source" }
git init $Source
if ($LASTEXITCODE) { throw 'Source initialization failed' }
git -C $Source remote add origin https://github.com/TIAIMM/tNVSE.git
git -C $Source fetch --depth 1 origin $commit
if ($LASTEXITCODE) { throw 'Pinned tNVSE download failed' }
git -C $Source checkout --detach FETCH_HEAD
if ($LASTEXITCODE) { throw 'Pinned tNVSE checkout failed' }
git -C $Source submodule update --init --recursive --depth 1
if ($LASTEXITCODE) { throw 'tNVSE dependency download failed' }
$patch = Join-Path $root 'tools/tnvse/ui-replacement-encoding.patch'
git -C $Source apply --check $patch
if ($LASTEXITCODE) { throw 'tNVSE source no longer matches the reviewed patch' }
git -C $Source apply $patch
if ($LASTEXITCODE) { throw 'tNVSE patch application failed' }
nuget restore "$Source/tnvse/packages.config" -PackagesDirectory "$Source/tnvse/packages" -NonInteractive
if ($LASTEXITCODE) { throw 'tNVSE NuGet restore failed' }
cmake -S $Source -B "$Source/out/kr-ui-fix" -G 'Visual Studio 17 2022' -A Win32 -T 'v143,host=x64' -DTNVSE_PLUGIN_PATH=
if ($LASTEXITCODE) { throw 'tNVSE CMake configure failed' }
cmake --build "$Source/out/kr-ui-fix" --config Release --parallel 2
if ($LASTEXITCODE) { throw 'tNVSE Win32 build failed' }
$dll = "$Source/out/kr-ui-fix/bin/Release/tnvse.dll"
if (-not (Test-Path $dll)) { throw 'Built tNVSE DLL is missing' }
Get-FileHash $dll -Algorithm SHA256
