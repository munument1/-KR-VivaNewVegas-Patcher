$ErrorActionPreference = 'Stop'
$vnvProjectRoot = Split-Path -Parent $PSScriptRoot
$vnvToolRoot = Join-Path $vnvProjectRoot '.tools'
$vnvArchivePath = Join-Path $vnvToolRoot 'xdelta3-3.2.0-windows-x86_64.zip'
$vnvExpectedHash = '8aca331c3d49ec4465ee8f3f7e3afb92e06d36e32fdec422c3252aaa813a7d2a'
New-Item -ItemType Directory -Force -Path $vnvToolRoot | Out-Null
if (-not (Test-Path -LiteralPath $vnvArchivePath)) {
    Invoke-WebRequest -Uri 'https://github.com/jmacd/xdelta/releases/download/v3.2.0/xdelta3-3.2.0-windows-x86_64.zip' -OutFile $vnvArchivePath
}
if ((Get-FileHash -LiteralPath $vnvArchivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $vnvExpectedHash) {
    throw 'xdelta3 ZIP SHA-256 mismatch. Do not use this archive.'
}
$vnvExecutable = Join-Path $vnvToolRoot 'xdelta3-3.2.0-windows-x86_64/xdelta3.exe'
if (-not (Test-Path -LiteralPath $vnvExecutable)) {
    Expand-Archive -LiteralPath $vnvArchivePath -DestinationPath $vnvToolRoot
}
$vnvExpectedExeHash = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'xdelta_source.json') -Raw | ConvertFrom-Json).executable_sha256
if ((Get-FileHash -LiteralPath $vnvExecutable -Algorithm SHA256).Hash.ToLowerInvariant() -ne $vnvExpectedExeHash) {
    throw 'xdelta3 executable SHA-256 mismatch.'
}
& $vnvExecutable -V
if ($LASTEXITCODE -ne 0) { throw 'xdelta3 version smoke failed.' }
