param([string]$Source = '.tnvse-source', [string]$ReuseDll = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$commit = '7355fd3f2e008dc252ac484f9b376c153e584455'
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
if ($ReuseDll) {
    # Packaging-only rebuilds can reuse the DLL that passed the C++ regression
    # tests in run 37582133368. Never reuse it after changing the actual patch.
    if ((Get-FileHash $patch -Algorithm SHA256).Hash -ne '99f5c6e683bfa382915615f050b5bb6d12a85a30890b13a71cf7a8177b5fd04c' -or
        $commit -ne '7355fd3f2e008dc252ac484f9b376c153e584455' -or
        (Get-FileHash $ReuseDll -Algorithm SHA256).Hash -ne 'ad2a81f1440647919ba792f0216ed26a736d4c4a51777f875e85e270538b3d70') {
        throw 'The reused DLL does not match the validated source and patch'
    }
    $dll = "$Source/out/kr-ui-fix/bin/Release/tnvse.dll"
    New-Item -ItemType Directory -Force (Split-Path -Parent $dll) | Out-Null
    Copy-Item $ReuseDll $dll
    Write-Host 'Reusing validated Win32 tNVSE DLL; only packaging changes.'
    return
}
nuget restore "$Source/tnvse/packages.config" -PackagesDirectory "$Source/tnvse/packages" -NonInteractive
if ($LASTEXITCODE) { throw 'tNVSE NuGet restore failed' }
cmake -S $Source -B "$Source/out/kr-ui-fix" -G 'Visual Studio 17 2022' -A Win32 -T 'v143,host=x64' -DTNVSE_PLUGIN_PATH=
if ($LASTEXITCODE) { throw 'tNVSE CMake configure failed' }
cmake --build "$Source/out/kr-ui-fix" --config Release --parallel 2
if ($LASTEXITCODE) { throw 'tNVSE Win32 build failed' }
$dll = "$Source/out/kr-ui-fix/bin/Release/tnvse.dll"
if (-not (Test-Path $dll)) { throw 'Built tNVSE DLL is missing' }
Get-FileHash $dll -Algorithm SHA256
