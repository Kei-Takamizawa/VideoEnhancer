# Historical P1e-3b MSVC diagnostic, not a complete LGPL build recipe.
# P1e-3c1 portable prerequisite failures: toolchain-probe.ps1 and source-manifest.json.
# Run after repo/local-env.ps1.
# Dependencies are deliberately not taken from unverified system binary bundles.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$work = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$root = Join-Path $work 'cache\mpv-lgpl\source-build'
$evidence = Join-Path $work 'evidence\VE-P1e-3c1\historical-msvc'
New-Item -ItemType Directory -Force $root, $evidence | Out-Null
$downloads = @(
    @('https://github.com/mesonbuild/meson/releases/download/1.12.1/meson-1.12.1.tar.gz', 'meson-1.12.1.tar.gz', 'ab0a6ca09f8ef70c564c8241fb5a23957886a0b53fb58412b5e07eaf07dba743'),
    @('https://github.com/mpv-player/mpv/archive/0fae4695470bf2c0c06762503292ee5379f62f62.tar.gz', 'mpv-0fae469547.tar.gz', 'a2cb3f3c1ad61b31c8df77aacb5ce106f6f47991df4e8b9e6975f94194fb386a')
)
foreach ($download in $downloads) {
    $archive = Join-Path $root $download[1]
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest $download[0] -OutFile $archive -UseBasicParsing
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $download[2]) {
        throw "Source checksum mismatch: $($download[1])"
    }
    $entries = & tar.exe -tf $archive
    if ($LASTEXITCODE -ne 0) { throw 'Source archive listing failed.' }
    foreach ($entry in $entries) {
        if ($entry -match '(^[/\\]|^[A-Za-z]:|(^|[/\\])\.\.([/\\]|$))') { throw 'Unsafe archive path.' }
    }
    & tar.exe -xf $archive -C $root
    if ($LASTEXITCODE -ne 0) { throw 'Source extraction failed.' }
}
$python = Join-Path $work 'repo\.venv\Scripts\python.exe'
$arguments = @(
    (Join-Path $root 'meson-1.12.1\meson.py'), 'setup',
    (Join-Path $root 'minimal-build'),
    (Join-Path $root 'mpv-0fae4695470bf2c0c06762503292ee5379f62f62'),
    '--backend=vs2022', '--vsenv', '--wrap-mode=nodownload', '--auto-features=disabled',
    '-Dgpl=false', '-Dlibmpv=true', '-Dcplayer=false', '-Dgl=disabled',
    '-Dd3d11=enabled', '-Dd3d-hwaccel=enabled', '-Dzlib=enabled'
)
# In the measured environment this detects MSVC, then fails on missing pkg-config
# and libavcodec development files. Failure is kept; it is not licence clearance.
& $python -c 'import subprocess,sys; result=subprocess.run(sys.argv[1:],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True); print(result.stdout); sys.exit(result.returncode)' $python @arguments |
    Tee-Object (Join-Path $evidence 'source-build-recipe.log')
$result = $LASTEXITCODE
if ($result -eq 0) {
    & $python (Join-Path $root 'meson-1.12.1\meson.py') compile -C (Join-Path $root 'minimal-build') -j 2
    $result = $LASTEXITCODE
}
exit $result
