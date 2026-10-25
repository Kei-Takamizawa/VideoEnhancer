# Reproduce the P1e-3c1 portable-toolchain prerequisite failure.
# This is a diagnostic, not a complete LGPL libmpv build recipe.
[CmdletBinding()]
param([ValidateSet('Native', 'Winbuild')][string]$Route = 'Native')
$ErrorActionPreference = 'Stop'
$work = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $work 'repo\local-env.ps1')
$version = if ($Route -eq 'Native') { '20260927' } else { '20260611' }
$expected = if ($Route -eq 'Native') {
    'ea2f31a0b6ade63914ce441ffb022f0f6aa96982bfefa2326460a26d5fb01322'
} else {
    'a2d047e8ee213c3c6a49a8de427eb1069df12207c0422ff1b3cbb5c905c34221'
}
$cache = Join-Path $work 'cache\msys2'
$folder = if ($Route -eq 'Native') { $cache } else { Join-Path $cache $version }
$evidence = Join-Path $work 'evidence\VE-P1e-3c1'
New-Item -ItemType Directory -Force $folder, $evidence | Out-Null
if ([IO.DriveInfo]::new('D:\').AvailableFreeSpace -lt 200000000000) {
    throw 'D: free space is below the 200 GB floor.'
}
$name = "msys2-base-x86_64-$version.tar.xz"
$archive = Join-Path $cache $name
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest "https://repo.msys2.org/distrib/x86_64/$name" -OutFile $archive -UseBasicParsing
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw "SHA-256 mismatch: $name"
}
$bash = Join-Path $folder 'msys64\usr\bin\bash.exe'
if (-not (Test-Path -LiteralPath $bash)) {
    $entries = & tar.exe -tf $archive
    if ($LASTEXITCODE -ne 0) { throw 'Archive listing failed.' }
    foreach ($entry in $entries) {
        if ($entry -match '(^[/\\]|^[A-Za-z]:|(^|[/\\])\.\.([/\\]|$))') {
            throw 'Unsafe archive path.'
        }
    }
    & tar.exe -xf $archive -C $folder
    if ($LASTEXITCODE -ne 0) { throw 'Archive extraction failed.' }
}
$env:MSYSTEM = if ($Route -eq 'Native') { 'UCRT64' } else { 'MSYS' }
$env:CHERE_INVOKING = '1'
$packages = if ($Route -eq 'Native') {
    'mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-meson mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-nasm mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-python'
} else {
    'cmake ninja gcc git meson python'
}
# Do not weaken SigLevel or import arbitrary third-party keys. timeout bounds
# a stalled official-key import without changing authentication behavior.
$ErrorActionPreference = 'Continue'
& $bash --noprofile --norc -c "export PATH=/usr/bin; timeout 60 pacman -Sy --noconfirm --needed $packages" 2>&1 |
    Tee-Object (Join-Path $evidence ("toolchain-probe-$Route.log"))
$result = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
exit $result
