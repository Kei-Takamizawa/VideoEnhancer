# GitHub Actions LGPL libmpv build

Route (b): Ubuntu 24.04 MinGW-w64 packages supply the compiler, SDK and compiler
runtimes. All fourteen source components (including shader headers) come from
pinned upstream source archives. This avoids bootstrapping GCC and keeps the dependency
graph smaller than mpv-winbuild-cmake. No PC MSYS2 tree is used.

The dedicated workflow runs only for this directory, its workflow file or a
manual dispatch. It uses the free ubuntu-24.04 runner, read-only contents access,
no secrets, full action commit pins and a 330-minute job bound. It does not alter
the product's CI, package or player. The operator commits and pushes this round.

## Stages

1. prepare.sh installs native Linux build tools. It resolves the seven Ubuntu
   cross-toolchain package versions once from authenticated apt indexes into
   toolchain-plan.txt. The exact versions are used for installation and the
   cache key, along with every recipe/source pin. The plan is retained in the
   artifact. A later runner's apt candidate can differ; it gets a different key
   and is disclosed in the manifest rather than silently reusing an old compiler.
2. toolchain.sh installs those exact packages. The cache contains downloaded
   compiler packages and their corresponding source archives, not target build
   output. apt verifies packages normally. For each compiler package's source
   and Built-Using records, the script downloads available exact Ubuntu sources
   and checks their files against the signed Sources SHA-256 index. A version
   absent from deb-src is recorded as `unavailable in deb-src`, with its exact
   name/version and Launchpad source URL, without stopping the build. Compiler
   and binutils sources are supplementary, not part of the LGPL source offer.
   Authentication, download and checksum failures remain fatal.
   `toolchain.runtime_components` separately records the actual installed owners
   and versions of CRT/header, winpthreads and static GCC/libstdc++ inputs,
   their licences and exact source references. Available runtime sources are
   archived too; unavailable ones retain the Launchpad reference. Package notices
   are retained even for runtime owners installed as transitive dependencies.
   GitHub's `mirror+file:` source URIs are resolved using actual download `Get:`
   lines. The receipt retains the planned URI, all hosts reported for that source
   download and those log lines. Hosts must be official Ubuntu archive hosts or
   ubuntu.com hosts listed in `/etc/apt/apt-mirrors.txt`; SHA-256 from the signed
   source index remains the authority for every file. Reused cache files are
   rehashed and their recorded origins revalidated. Old cache entries without
   origin receipts are downloaded once into a fresh staging directory, because
   apt emits no `Get:` lines for existing files. Shell stages force `LC_ALL=C`.
3. build.sh requires fresh src/, build/ and prefix/ trees. Each cached upstream
   archive is rehashed before safe extraction. Libraries are built in dependency
   order; Meson wraps cannot download unpinned subprojects. Target pkg-config
   lookup is confined to the source-built prefix. Every command and exit status,
   source hash and actual Meson option is recorded, not inferred from the lock.
4. package.sh fails closed on wrong FFmpeg features/licence flags, missing
   D3D11VA codecs/filters, incorrect mpv options, or unlisted/unbundled imports.
   It checks the FFmpeg configuration in the built static library and final DLL,
   and mpv's gpl=false in both actual build options and final DLL strings.
5. One 30-day artifact contains DLLs, SHA256SUMS, the generated manifest,
   licence texts, objdump reports and the exact sources.tar.zst. DLL hashes are
   printed in the log before upload. No artifact is uploaded after a failed gate.

Most dependencies are static. The shaderc and SPIRV-Cross shared C APIs are
kept as separate permissive DLLs because the pinned mpv D3D11 render API explicitly requires both.
libplacebo also needs their shader compilation/translation functions.
GCC/libstdc++ runtimes are requested static;
the strict import closure copies any required MinGW runtime DLLs and accounts
for their source references and runtime-exception/permissive licences.
The DLL allowlist is explicit; an unexpected DLL cannot be legalized by merely
copying it into the output folder. See DISTRIBUTION.md for source/replacement
obligations and the LGPL-3.0-or-later election for Apache shader dependencies.

FreeType's optional HarfBuzz backend is disabled to avoid a dependency cycle;
HarfBuzz is built after FreeType and used by libass. FreeType logging/dlg is not
enabled. Fontconfig, libunibreak and unrelated target libraries are disabled.
shaderc uses exactly its DEPS revisions of glslang, SPIRV-Tools and SPIRV-Headers;
all four archives are pinned and hashed. No git-sync-deps or unpinned test
dependencies (googletest, effcee, re2, abseil) are fetched. The three child
components share shaderc's successful actual build commands in the manifest;
SPIRV-Headers is explicitly header-only. Upstream target tests/examples and
the tarball-inapplicable copyright-year check are disabled as cross-build
configuration, not after a test failure. Independent licence gates remain on. The FFmpeg AV1 native decoder and dav1d
provide hardware/software paths; all four D3D11VA and D3D11VA2 pairs are gated.

## Manual Linux build

On Ubuntu 24.04 with sudo access, from the checkout:

```sh
export MPV_CI_ROOT=/tmp/libmpv-lgpl-run1
export BUILD_JOBS=2
bash spikes/mpv/ci-build/run.sh
```

The root must be outside the checkout and fresh except cache/. To reproduce,
use another fresh root, copy only cache/ and, for identical compiler versions,
reuse the recorded toolchain-plan.txt when running toolchain.sh/build.sh/
package.sh separately after installing the native tools. run.sh resolves a new
plan deliberately; compare it with the first run before interpreting DLL hashes.
On other Linux distributions, provide the same MinGW/native tools and run in
an Ubuntu 24.04 container (mount the checkout and a separate output directory),
or port only prepare.sh/toolchain.sh. Build/package scripts have no dependency
on GitHub context, credentials or the Actions cache service.

The workflow must not be run from the development Windows PC. Each round can check
YAML/actionlint, Python checks/tests and bash -n only if a non-MSYS2-tree bash
already exists. shfmt can parse Bash syntax with its native Windows binary
when bash is unavailable; this is not execution of the shell or Linux build. No Linux compilation is claimed from those checks. When CI is
green, the operator downloads and verifies the artifact, then a later round
checks Windows libmpv properties, five D3D11VA fixtures and the H.264 regression.
The designer dispatches the second clean workflow for reproduction comparison.
At most six CI rounds are allowed. Current state: **Awaiting CI build**.

## Round 4 assembly and host tools

The shared Meson cross file explicitly supplies `nasm = 'nasm'`, alongside the
target C/C++ compilers, ar, strip and windres. Every Meson component uses that
same file. libass keeps `asm=enabled`, dav1d explicitly sets `enable_asm=true`,
and FFmpeg selects `--x86asmexe=nasm --enable-asm --enable-x86asm`. Target GCC
selects its linker; CMake uses the target compilers/resource compiler and native
build-time programs. No target executable is run to discover these tools.

The toolchain receipt records actual `nasm -v` output and rejects versions older
than 2.14 (pinned libass needs 2.10, pinned dav1d needs 2.14). Pinned FFmpeg uses
instruction probes rather than a numeric minimum; those configure probes must
pass and the generated `HAVE_X86ASM` must be 1. Actual generated libass/dav1d
headers must also confirm assembly. libass's optional iconv and libpng remain
absent; `components[].features` records both as false from the built config,
and rejects unexpected enablement. Assembly cannot silently fall back off.

Windows tests verify those gates and receipt contents. The runner's actual NASM
version and assembly compilation still require the next CI build; simulated
version output in tests is not runner evidence.

## Round 2 toolchain regression coverage

Section 11.4 reports round 1 failing on the unavailable Built-Using source
`binutils=2.41.90.20240122-1ubuntu1`. Windows unit tests run the real `plan` and
`toolchain` Python orchestration with mocked apt/dpkg/compiler output and source
downloads. They check missing Built-Using/compiler/runtime sources, available
source hashing, exact package versions, runtime ownership/licences, cache-key
outputs and failure paths. They do not install Ubuntu packages or execute a
cross-compiler. Actual Linux installation/build remains for the next CI run.

## Round 3 mirror-method regression coverage

Section 11.5 reports a `mirror+file:/etc/apt/apt-mirrors.txt/...` URI and a
`Get:2 http://azure.archive.ubuntu.com/ubuntu ... (dsc) [1898 B]` download line.
Tests use those exact strings and also run mocked plan/toolchain orchestration
for mirrored downloads, cache hits with no new download lines, old caches with
no receipt, corrupt cache bytes and rejected origins. All reported download hosts
must pass the allowlist, including when more than one mirror serves a source
package. A mirror URI without actual or cached host evidence fails explicitly;
the script never invents a resolved host from the mirror-list name. Available
toolchain source hashes remain mandatory, as do all upstream library hashes.


## Pinned upstream build contracts

- [mpv D3D11 shaderc/SPIRV-Cross requirements](https://github.com/mpv-player/mpv/blob/0fae4695470bf2c0c06762503292ee5379f62f62/meson.build).
- [libplacebo D3D11 requirements](https://github.com/haasn/libplacebo/blob/cee9b076f2c63104ccfd497fa79c39a867293ec4/src/d3d11/meson.build).
- [shaderc v2025.4 dependency revisions](https://github.com/google/shaderc/blob/v2025.4/DEPS).

The source lock records every downloaded archive and hash. Its licence labels
and planned recipe do not stand in for the build-generated artifact manifest
or the later Windows/runtime and distribution review.
