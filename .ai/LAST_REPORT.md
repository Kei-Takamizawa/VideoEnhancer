Task ID: VE-P1e-3c1 / Cycle: GitHub Actions build, round 1 of at most 6
Status: PARTIAL
Awaiting CI build

## Outcome and scope

Implemented section 11.2 step 1. No Linux cross-build, GitHub Actions run or
new libmpv binary exists from this round. This report supersedes the previous
cycle report; accepted Part B/C evidence was not rerun or presented as new proof.
The prebuilt DLL remains unsuitable for distribution under this task.

Read AGENTS.md, CLAUDE.md, docs/WORKSPACE.md and CURRENT_TASK.md, including
sections 10 and 11. Execution terminal: Windows / PowerShell in the development
workspace. Initial read-only Git inspection showed branch
claude/project-thread-6lra47, HEAD d799388324c5b78bba89120746cf6e4c3f7f6c80,
and a clean working tree. Git inspection required sandbox escalation; no Git
mutation, commit, push, workflow dispatch or merge was performed. The operator
owns commit/push under section 11.2. CURRENT_TASK.md was already authoritative
and was preserved unchanged.

## Implementation and changed files

- .github/workflows/libmpv-lgpl.yml: dedicated ubuntu-24.04 workflow;
  workflow_dispatch and path-filtered push/PR; contents: read; no secrets;
  full SHA action pins with version comments; timeout 330 minutes; source and
  compiler cache; one 30-day libmpv-lgpl-0fae469547 artifact.
- spikes/mpv/ci-build/env.sh, prepare.sh, toolchain.sh, build.sh, package.sh,
  run.sh: Linux environment, versioned compiler plan, authenticated compiler
  download/install, source compilation and gated packaging stages.
- spikes/mpv/ci-build/mingw.ini.in, mingw.cmake.in: restricted MinGW cross files.
- spikes/mpv/ci-build/sources.lock.json, toolchain-packages.txt: pinned source
  archives and explicit compiler package set.
- spikes/mpv/ci-build/driver.py: source hash/layout/licence validation, actual
  build receipts, configuration and PE dependency gates, generated manifest,
  exact source offer, licence collection and SHA256SUMS generation.
- spikes/mpv/ci-build/test_driver.py: 12 fail-closed configuration/import tests.
- spikes/mpv/ci-build/README.md, DISTRIBUTION.md: invocation, provenance,
  licence handling and remaining validation boundaries.
- .ai/LAST_REPORT.md: this report.

Route (b) was selected: Ubuntu MinGW packages avoid bootstrapping GCC, while
all fourteen upstream source components are built from pinned archives.
The compiler's seven package versions are resolved once per run from authenticated
Ubuntu indexes, then installed at those exact versions. Their version plan is
part of the cache key and artifact; later apt candidates may differ, so compiler
versions are not claimed to be globally immutable. Exact Ubuntu source and
Built-Using archives are collected with Sources-index SHA-256 verification.
No PC MSYS2 executable or tree was used or modified.

The pinned mpv D3D11 render implementation requires shaderc and SPIRV-Cross.
shaderc's glslang, SPIRV-Tools and SPIRV-Headers pins match its upstream DEPS.
The build disables GPL/nonfree paths and unnecessary features; upstream example
and test executables are disabled for the cross-build, not removed after failures.
Runtime GCC exceptions and mixed MinGW notices are explicitly documented.
Product CI, product implementation, prior B1 spike files, LICENSES.md and the
existing source-manifest.json were not changed. Actual manifest/licence product
updates wait for a successful artifact and PC verification.

## Validation: expected and actual

| Check | Result | Actual / limitation |
| --- | --- | --- |
| YAML parsing and independent workflow assertions | PASS | Exact triggers/path filters, read permissions, Ubuntu runner, timeout, full action pins, no secret references, 30-day retention |
| actionlint 1.7.12 | PASS | Final workflow exit 0; external shellcheck disabled because unavailable |
| Bash parse/format with shfmt 3.14.1 | PASS | Six shell scripts parse and format cleanly |
| bash -n | NOT_RUN | No permitted Bash available; PC MSYS2 trees were excluded |
| Ruff check and format check | PASS | New helpers pass final checks |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | 12 tests, exit 0 |
| Pinned upstream archives | PASS | All 14 actual downloads rehashed; archive roots and declared licence paths checked; shaderc DEPS pins match |
| Linux dependency compilation and source extraction pipeline | NOT_RUN | Cannot execute Linux build locally; awaiting CI |
| Generated DLL architecture/import/configuration checks | NOT_RUN | Implemented gates, no new binary to inspect |
| Actual artifact manifest, source offer and SHA256SUMS | NOT_RUN | Generated only after a successful build; no placeholder artifact |
| GPU/GUI playback, libmpv properties, five fixtures, H.264 timing and size | NOT_RUN | Section 11.2 step 4 requires downloaded successful artifact |
| Two-run reproducibility | NOT_RUN | Requires two CI builds |
| Product build/test and accepted Part B/C reruns | NOT_RUN | Outside this round's scope |

Unit tests reject GPL/nonfree/version3 options, generated GPL macro overrides,
unlisted external codecs, unwanted encoders/muxers, missing AV1 D3D11VA2,
missing runtime DLLs, unlisted bundled DLLs, wrong PE architecture and unwanted
mpv options. Tests also accept explicit Windows/system dependencies and the
minimal clean configurations. These are gate tests, not proof that real DLLs pass.

Initial actionlint rejected runner context at job-level env; fixed by deriving
paths from RUNNER_TEMP inside env.sh. Two Ruff line-length findings were fixed.
Final checks passed. PowerShell rendered unittest's stderr progress as
NativeCommandError text in the transcript; unittest itself reported OK and exit 0.
A FreeType GNU archive download timed out; the lock uses an immutable commit
archive from the official FreeType GitHub mirror instead. No test failure was
waived. No GUI operation was performed.

Local tools were downloaded from official releases and matched published hashes:
- actionlint 1.7.12 Windows amd64 ZIP:
  6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9
- shfmt 3.14.1 Windows amd64 executable:
  13629ce28442ca80b6b5a819f7574ab39e1c28c6e26734ca816c9714e04851df

Local, untracked evidence is under evidence/VE-P1e-3c1/ci-round1:
validation.log, source-and-workflow-checks.json and disk.json. Archives and
inspection files are under cache/mpv-lgpl/ci-round1-sources. They are excluded
from Git. The lock records hash origins: release-asset digests were independently
available for three assets; other immutable official archives were downloaded
and hashed locally, not claimed to match independently published checksums.

## Disk and cleanup

Measured bytes, decimal GB interpretation. Snapshot taken after validation and
before this report rewrite; report/evidence bookkeeping changes its totals slightly.

| Area | Bytes | Interpretation |
| --- | ---: | --- |
| repo | 3,527,226,484 | Whole checkout, not growth attributable to this round |
| package | 5,764,162 | Existing package area, unchanged |
| evidence/VE-P1e-3c1 | 44,114,273 | Includes previous accepted evidence |
| evidence/VE-P1e-3c1/ci-round1 | 9,163 | Before disk.json itself; small local logs only |
| scratch | 0 | No files; only new empty tmp directory before cleanup |
| cache | 8,837,493,510 | Below 40 GB budget |
| cache/msys2 | 856,811,931 | Metadata inventory only; untouched this round |
| cache/mpv-lgpl/source-build | 36,575,903 | Historical tree; untouched |
| cache/mpv-lgpl/ci-round1-sources | 64,181,348 | New downloaded archives and selected inspection files; no compiled output |
| cache/tools/actionlint-1.7.12 | 9,095,194 | New local validation tool cache |
| cache/tools/shfmt-3.14.1 | 3,801,600 | New local validation tool cache |

C: free start/end: 299,222,872,064 / 299,217,453,056 bytes.
D: free start/end: 1,002,906,816,512 / 1,002,828,259,328 bytes, above 200 GB floor.
Dependency restore: 0 bytes; no new Python/node dependency environment installed.
New source/tool cache areas total 77,078,142 bytes; additional scripts and evidence
are small, with attributable growth below 1 GB. Built DLL output: 0 bytes.
No Linux intermediate build tree or actual source-offer size exists yet.
Validation tools and verified source downloads are retained for reuse. No old
cycle, owner media, package, queue or MSYS2 cleanup was attempted. No GPG agent
or dirmngr process was started. Only this round's newly created empty scratch/tmp
is eligible for removal, after checking its absolute path and emptiness.

## Remaining work and designer decisions

The operator should commit/push these changes to the permitted working branch.
The designer reads the CI result and appends failing step/log evidence to section
11 before resuming Codex. Maximum six CI rounds; this is round 1. No current
compiler failure is known because compilation has not run. Potential upstream
cross-build/configuration incompatibilities remain unverified.

On a green build, the operator downloads the artifact into the task's prescribed
cache location and verifies SHA256SUMS. Then perform section 11.2 step 4 on the
PC, update LICENSES.md for that actual build, and compare a second dispatched
run for reproducibility. No new architecture or UI decision was made. Distribution
clearance, runtime performance and byte reproducibility are not established.

Intentionally deferred: CI execution, artifact download, all new-DLL PC proofs,
reproducibility comparison, product integration, paid resources and Git mutations.

## Verified upstream source pins

| Component | Version | SHA-256 |
| --- | --- | --- |
| [zlib](https://github.com/madler/zlib/archive/51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf.tar.gz) | 1.3.1 | `d9e270d46252734aa49770fbc544125391617956266f220bd63216c834f3a522` |
| [freetype](https://github.com/freetype/freetype/archive/526ec5c47b9ebccc4754c85ac0c0cdf7c85a5e9b.tar.gz) | 2.14.1 | `d24f53b60034dc5c48e90d122d432a8f04a05b9e0a98c8d8e49b4a759207ce2e` |
| [fribidi](https://github.com/fribidi/fribidi/releases/download/v1.0.17/fribidi-1.0.17.tar.xz) | 1.0.17 | `6949dcde27d41cebad1fd741fcafc36d55a1020d2d872d4a6eb3914caabbada2` |
| [harfbuzz](https://github.com/harfbuzz/harfbuzz/releases/download/15.0.0/harfbuzz-15.0.0.tar.xz) | 15.0.0 | `968536e9abd782f07f7954044c0c4020199fcdd39b41d221ec42d2a3be4a44df` |
| [libass](https://github.com/libass/libass/releases/download/0.17.5/libass-0.17.5.tar.xz) | 0.17.5 | `2dca25c0e0c837ddf00b52011b3f82cac1e4ddd3ad018227806b0c2288864acc` |
| [dav1d](https://github.com/videolan/dav1d/archive/54706fc6bc0cdecab7e9593974a4039cc038fca7.tar.gz) | 1.5.4 | `9edb11a2108b375cc58370354e705feebc93430bb780130363815c1e1ac0c250` |
| [spirv-cross](https://github.com/KhronosGroup/SPIRV-Cross/archive/d8e3e2b141b8c8a167b2e3984736a6baacff316c.tar.gz) | vulkan-sdk-1.4.321.0 | `18e4abb4ae97451c3d90bb23eb1c22859c8ef08bd5d8d3ec09e035846bbf6556` |
| [libplacebo](https://github.com/haasn/libplacebo/archive/cee9b076f2c63104ccfd497fa79c39a867293ec4.tar.gz) | 7.360.1 | `6f8fa218cbafd8e5f50b8a82d918e1d8bbb92f9f980820bc0b34d92e9b79e484` |
| [ffmpeg](https://ffmpeg.org/releases/ffmpeg-8.0.tar.xz) | 8.0 | `b2751fccb6cc4c77708113cd78b561059b6fa904b24162fa0be2d60273d27b8e` |
| [mpv](https://github.com/mpv-player/mpv/archive/0fae4695470bf2c0c06762503292ee5379f62f62.tar.gz) | 0fae4695470bf2c0c06762503292ee5379f62f62 | `a2cb3f3c1ad61b31c8df77aacb5ce106f6f47991df4e8b9e6975f94194fb386a` |
| [shaderc](https://github.com/google/shaderc/archive/refs/tags/v2025.4.tar.gz) | v2025.4 | `8a89fb6612ace8954470aae004623374a8fc8b7a34a4277bee5527173b064faf` |
| [glslang](https://github.com/KhronosGroup/glslang/archive/d213562e35573012b6348b2d584457c3704ac09b.tar.gz) | d213562e35573012b6348b2d584457c3704ac09b | `9537e5896d10bc493775675153687e078d83aead3a5a3b90e9ac28af2bc966fc` |
| [spirv-headers](https://github.com/KhronosGroup/SPIRV-Headers/archive/01e0577914a75a2569c846778c2f93aa8e6feddd.tar.gz) | 01e0577914a75a2569c846778c2f93aa8e6feddd | `494bd30dc13ba798af70edd989f8df82c90757c8ce9433598480f5e00e04c454` |
| [spirv-tools](https://github.com/KhronosGroup/SPIRV-Tools/archive/19042c8921f35f7bec56b9e5c96c5f5691588ca8.tar.gz) | 19042c8921f35f7bec56b9e5c96c5f5691588ca8 | `7ab19030df38a50cc93be26ebd3913c3e7ef3a118e1ded65a829e63b0c7ccf12` |

Cleanup result: PASS. Removed only the verified empty scratch/tmp (0 bytes); scratch is empty.

Final scope check: PASS. Read-only git status showed only this report, the new workflow and spikes/mpv/ci-build/. git diff --check exited 0. Git warned that LF in LAST_REPORT.md will become CRLF on its next write; no whitespace errors were reported. New directory inventory contains only the 14 text source/configuration/documentation files listed above, with no binaries or Python cache files.
