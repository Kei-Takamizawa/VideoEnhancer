# Run after dot-sourcing repo/local-env.ps1. No system installation is performed.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$work = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$destination = Join-Path $work 'cache\mpv-lgpl'
New-Item -ItemType Directory -Force $destination | Out-Null
$release = 'https://github.com/zhongfly/mpv-winbuild/releases/download/2026-10-23-0fae469547'
$assets = @(
    @('mpv-dev-lgpl-x86_64-20261023-git-0fae469547.7z', '81cf5b30b5729be3647eac85d70c05ea0b8dfea02dfa7c4eefed1f23a0a38a52', $destination),
    @('ffmpeg-lgpl-x86_64-git-c569ebacc.7z', '3ac8067c9f7d7588521651c86b4bc5d7cc43fe9e5fed3214d8d6427421a059f5', (Join-Path $destination 'ffmpeg'))
)
foreach ($asset in $assets) {
    $archive = Join-Path $destination $asset[0]
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest "$release/$($asset[0])" -OutFile $archive -UseBasicParsing
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset[1]) {
        throw "SHA-256 mismatch: $($asset[0]). Extraction refused."
    }
    # Refuse path traversal before extracting even a checksum-verified archive.
    $entries = & tar.exe -tf $archive
    if ($LASTEXITCODE -ne 0) { throw 'Archive listing failed.' }
    foreach ($entry in $entries) {
        if ($entry -match '(^[/\\]|^[A-Za-z]:|(^|[/\\])\.\.([/\\]|$))') { throw 'Unsafe archive path.' }
    }
    New-Item -ItemType Directory -Force $asset[2] | Out-Null
    & tar.exe -xf $archive -C $asset[2]
    if ($LASTEXITCODE -ne 0) { throw 'Archive extraction failed.' }
}
Write-Output 'Checksums verified. Candidate only: dependency licence audit remains open; do not package.'
