# libmpv LGPL build: CI run 40202006764

This document covers the source-built Windows x86-64 artifact from
[run 40202006764](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/40202006764),
build scripts at commit `b65a4ccb7fb139500b8909031151f4b6c71441e2`.
The product remains MIT and unchanged; this spike dynamically loads libmpv.
The old 101,511,680-byte prebuilt remains measurement-only and must never ship.

## Verified binary inventory

| DLL | Bytes | SHA-256 |
| --- | ---: | --- |
| libmpv-2.dll | 33266600 | `d7126e232340dcd767f0a2197ec0ab60ac32146aa7a1291bcd172c57c49a5b4c` |
| libspirv-cross-c-shared.dll | 2965767 | `a0d43e62453adfed48e42d152c92ed382facfdf5d38da3615acbdea430d49ef9` |
| libwinpthread-1.dll | 324451 | `fc9f14551f6609dd51801daec2c194579d35345551ef84fe465cbdb3339c2a6f` |

The three DLLs total **36,556,818 bytes (36.557 decimal MB)**, versus
101,511,680 bytes for the prebuilt. Keep all three together. libgcc and libstdc++
are statically linked under the GCC Runtime Library Exception; winpthreads is
actually shared in this artifact (the `.a` input is an import library).

Windows libmpv properties report `mpv v0.41.0-UNKNOWN`, `-Dgpl=false`, and
FFmpeg `8.0`. The exact pinned mpv commit is in the manifest; UNKNOWN is the
archive build's version suffix, not a different source revision.
The embedded FFmpeg configuration was read directly from this DLL and has
`--disable-gpl --disable-nonfree`, with no `--enable-gpl`, `--enable-nonfree`
or `--enable-version3`. No companion ffmpeg.exe was used as configuration proof.
PE import tables were read locally and matched the checksum-verified CI objdump
receipts. All non-system imports are the two bundled dependencies above;
there is no Vulkan loader, libstdc++ DLL or libgcc DLL import.
Five B1 fixtures passed with `hwdec-current=d3d11va` on Windows.

## Components and notices to distribute

The complete generated [source-manifest.json](source-manifest.json) retains
exact upstream URLs, source SHA-256 values, commands, configuration receipts,
recipe changes and toolchain versions, plus the Windows acceptance supplement.
The original artifact manifest is separately authenticated in that supplement.

| Component | Version / commit | Source licence (SPDX) | Artifact notices |
| --- | --- | --- | --- |
| zlib | 1.3.1 | Zlib | `LICENSES/zlib/` |
| freetype | 2.14.1 | FTL | `LICENSES/freetype/` |
| fribidi | 1.0.17 | LGPL-2.1-or-later | `LICENSES/fribidi/` |
| harfbuzz | 15.0.0 | MIT | `LICENSES/harfbuzz/` |
| libass | 0.17.5 | ISC | `LICENSES/libass/` |
| dav1d | 1.5.4 | BSD-2-Clause | `LICENSES/dav1d/` |
| spirv-cross | vulkan-sdk-1.4.321.0 | Apache-2.0 | `LICENSES/spirv-cross/` |
| libplacebo | 7.360.1 | LGPL-2.1-or-later | `LICENSES/libplacebo/` |
| ffmpeg | 8.0 | LGPL-2.1-or-later | `LICENSES/ffmpeg/` |
| mpv | 0fae4695470bf2c0c06762503292ee5379f62f62 | LGPL-2.1-or-later | `LICENSES/mpv/` |
| shaderc | v2025.4 | Apache-2.0 | `LICENSES/shaderc/` |
| glslang | d213562e35573012b6348b2d584457c3704ac09b | BSD-3-Clause AND BSD-2-Clause AND MIT AND Apache-2.0 AND (GPL-3.0-or-later WITH Bison-exception-2.2) | `LICENSES/glslang/` |
| spirv-headers | 01e0577914a75a2569c846778c2f93aa8e6feddd | MIT | `LICENSES/spirv-headers/` |
| spirv-tools | 19042c8921f35f7bec56b9e5c96c5f5691588ca8 | Apache-2.0 | `LICENSES/spirv-tools/` |
| vulkan-headers | vulkan-sdk-1.4.321.0 | Apache-2.0 AND (Apache-2.0 OR MIT) | `LICENSES/vulkan-headers/` |

SPIRV-Headers and Vulkan-Headers are compile-time-only inputs. Vulkan-Headers
installs declarations for disabled Vulkan stubs; no Vulkan loader/backend ships.
The installed Vulkan header set elects Apache-2.0. libass iconv and libpng are
disabled. No extra optional media library is enabled.

Ship the artifact's **entire `LICENSES/` directory** and `DISTRIBUTION.md`, not
only this summary. It includes mpv Copyright and LGPL/GPL texts, FFmpeg licence
and LGPL/GPL texts, libplacebo, FriBidi, dav1d, libass, FreeType FTL, HarfBuzz,
zlib, shaderc, SPIRV-Cross, glslang, SPIRV-Tools, SPIRV-Headers and Vulkan-Headers
notices. Retain complete copyright/exception notices even where an archive
includes extra notices for unbuilt tests or alternative licences.

FreeType is used under the FTL option: this software uses the FreeType Project,
https://www.freetype.org/. Its FTL attribution must accompany distribution.

The LGPL-2.1-or-later components elect **LGPL-3.0-or-later for the combined
library distribution**, accommodating Apache-2.0 shader dependencies. This does
not relicense the separate MIT application. Preserve Apache notices and patent
terms, all MIT/BSD/ISC/Zlib notices and the BSD non-endorsement restrictions.
glslang includes the generated parser under GPL-3.0-or-later WITH
Bison-exception-2.2; retain that exception and the two parser files' full notices.
The exception permits the approved shader compiler use; plain GPL-only media or
shader code is not an allowed dependency. Full GPL text being included alongside
LGPL/exception notices is not evidence that GPL-only functionality was enabled.

`LICENSES/toolchain/` supplies Ubuntu package copyright files and full GPL/LGPL
texts, including the GCC Runtime Library Exception. Runtime inputs are:

- MinGW-w64 CRT/headers: `mingw-w64-x86-64-dev 11.0.1-3build1`, ZPL/public domain.
- winpthreads: MIT; its DLL is bundled and hash-pinned above.
- GCC/libstdc++: `13.2.0-6ubuntu1+26.1`, GPL-3.0-or-later WITH GCC-exception-3.1.

Exact source-package versions and Launchpad URLs are in the manifest. Missing
compiler/binutils source versions in deb-src are explicitly recorded; the
compiler tools do not ship. The approved runtime exceptions and permissive
notices apply to their incorporated runtime code.

## Corresponding source, rebuilding and replacement rights

Attach the exact artifact **`sources.tar.zst`** to every release containing these
DLLs, together with `SHA256SUMS`, the build manifest and all notices. It contains
the pinned upstream source archives, available distro sources/patches, exact
build scripts, cross files, actual command/configuration and recipe-change
receipts. Its SHA-256 is `5c79c49b82d628e44cffb82cbc64a73f759837203d1e09211143aa9599b97a28`.
A moving upstream URL does not substitute for delivery of this archive.

The supported rebuild recipe is [ci-build/run.sh](ci-build/run.sh), described in
[ci-build/README.md](ci-build/README.md), on Ubuntu 24.04 with the recorded MinGW
packages. `.github/workflows/libmpv-lgpl.yml` invokes this recipe. Historical
`source-build.ps1` and `toolchain-probe.ps1` are failed-route diagnostics, not the
successful recipe; do not run the PC MSYS2 routes.

Users must be able to replace libmpv and the bundled dependency DLLs, rebuild
modified libraries from the corresponding source, and debug those modifications.
Do not impose signatures/hash checks or licence terms that prevent these LGPL
rights in the delivered application. The spike's build-validation hashes are
not a proposed product integrity restriction. Keep the application dynamically
linked; retain the complete library rebuild/relink inputs for statically
combined LGPL dependencies. The final product distribution must preserve these
source, notice, replacement and relinking obligations.

## Remaining work

The prior dependency/configuration/source-offer OPEN items for this build have
been resolved by the generated manifest, artifact notices/source offer and PC
proof. **Reproducibility comparison is PENDING**: the designer's second manual
run artifact was not present locally at verification time. No byte-identical
claim is made; compare SHA256SUMS when that artifact arrives. Per the owner this
does not block section 11.2 step 4. Product integration/packaging is a later cycle;
this document does not claim the product has already shipped this library.
