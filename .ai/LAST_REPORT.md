Task ID: VE-P1e-3c1 / Cycle: GitHub Actions round 6 preparation (5 CI rounds used)
Status: PARTIAL
Awaiting CI build

## Outcome

Implemented section 11.8. Pinned Khronos Vulkan-Headers provides only
include/vulkan and include/vk_video in the target prefix before libplacebo.
No Vulkan loader, SDK binary, pkg-config alias or upstream stub patch is added.
libplacebo and mpv explicitly configure Vulkan disabled, with checks on their
actual Meson options. The DLL import gate explicitly rejects vulkan-1.dll.

The component is recorded as header-only, compile-time-only, binary_linkage=none,
with actual installed-header hashes in its build receipt. Its source archive and
licence files are included by the existing manifest/source-offer pipeline.
Windows tests/static checks pass; actual Linux compilation, packaging and objdump
proof are NOT_RUN in this continuation. No new DLL or green artifact exists here.
Accepted Part B/C work was not rerun.

The updated 11.2 rule has no fixed round limit. The designer stops after two
consecutive rounds failing at the same step without progress. This continuation
prepares round 6; operator commit/push and subsequent CI review remain separate.

## Start and reported failure

Read AGENTS.md, CURRENT_TASK.md completely (including updated 11.2 and 11.8),
CLAUDE.md and docs/WORKSPACE.md. Terminal: Windows / PowerShell.
Initial read-only Git inspection:
- Branch: claude/project-thread-6lra47
- HEAD: 7af99b34eac4950879071934341559c457ea1930
- Working tree: clean

Section 11.8 reports run 40192912086 on c07ed2a configuring libplacebo with
d3d11 YES, shaderc YES, vulkan NO, glslang NO, then compiling 61/63 objects before:

    FAILED: src/libplacebo.a.p/vulkan_stubs.c.obj
    ../../src/libplacebo/src/include/libplacebo/vulkan.h:21:10: fatal error: vulkan/vulkan.h: No such file or directory

Those are supplied CI results, not a local rerun. Pinned libplacebo compiles
vulkan/stubs.c with Vulkan disabled; its public header still needs Vulkan types.
CURRENT_TASK.md was preserved unchanged. No Git mutation, fetch, commit, push,
merge, CI dispatch or paid resource usage occurred. Read-only Git used sandbox
escalation. Operator owns commit/push.

## Changed files

- spikes/mpv/ci-build/sources.lock.json: fifteenth source component,
  vulkan-headers, with immutable commit/archive SHA-256 and licence scope.
- spikes/mpv/ci-build/build.sh: copy only the two header directories before
  libplacebo; explicitly disable Vulkan for libplacebo and mpv.
- spikes/mpv/ci-build/driver.py: fifteen-component validation; verify Vulkan 1.4
  declarations and installed header hashes; header-only receipt; actual libplacebo
  and mpv Vulkan-disabled checks; explicit Vulkan loader import rejection.
- spikes/mpv/ci-build/test_driver.py: five added tests for header-only receipts,
  missing/changed headers, insufficient header version, Vulkan option rejection
  and forbidden loader imports; existing mpv fixtures include disabled Vulkan.
- spikes/mpv/ci-build/README.md: header-only recipe and updated round rule.
- spikes/mpv/ci-build/DISTRIBUTION.md: header-only dependency and precise licences.
- .ai/LAST_REPORT.md: this report.

No workflow, product, ci.yml, cross file, upstream patch, existing
source-manifest.json, LICENSES.md or accepted B1 implementation changed. No PC
MSYS2 executable/tree was used or modified; only aggregate size metadata was
inventoried for the required disk table.

## Source pin, licence and compatibility

Official tag: vulkan-sdk-1.4.321.0, matching the pinned SPIRV-Cross SDK.
Resolved commit: 2cd90f9d20df57eac214c148f3aed885372ddcfe.
Archive: https://github.com/KhronosGroup/Vulkan-Headers/archive/2cd90f9d20df57eac214c148f3aed885372ddcfe.tar.gz
SHA-256: e3865307e665f6a4ac4f7bbca7b3ba95e4191c7f8adf9f04b084ef514a2454e9
Downloaded bytes: 2,760,645. The tag was resolved through the official GitHub API;
the hash was computed locally and rechecked, not claimed to match an independently
published archive checksum. CI rehashes before extracting like all other sources.

The archive exposes VK_VERSION_1_4 and VK_HEADER_VERSION=321. Pinned libplacebo's
src/vulkan/meson.build checks for Vulkan 1.4, so this SDK meets that source-level
requirement. Audited archive contents: 37 files under include/vulkan, 12 under
include/vk_video. Only those directories are copied; no CMake project/loader is
built. Existing target-prefix C/C++ include flags make them visible to stubs.

Retained licence files: LICENSE.md, LICENSES/Apache-2.0.txt, LICENSES/MIT.txt.
Scope precision: Vulkan C and vk_video headers say Apache-2.0; C++ headers offer
Apache-2.0 OR MIT. The manifest records Apache-2.0 AND (Apache-2.0 OR MIT), electing
Apache-2.0 for the installed set. It does not claim that every C header can be
used under MIT. Both texts/notices are retained. The existing LGPL-3.0-or-later
combined-library election remains; no new runtime library is introduced.

## Look-ahead review

Reviewed pinned libplacebo install/Vulkan-stub code, FFmpeg configure checks,
mpv dependency checks, shaderc/SPIRV-Cross pkg-config generation and packaging:
- libplacebo installs its public headers (including vulkan.h) and generates
  libplacebo.pc. Prefix include flags now cover its Vulkan declarations, while
  its loader dependency may correctly remain not found with the backend disabled.
- Shaderc generates shaderc.pc linked to shaderc_shared, installed under the
  configured lib/pkgconfig. SPIRV-Cross generates spirv-cross-c-shared.pc there.
  Those names match mpv's dependency checks; no fabricated alias is needed.
- mpv requires libplacebo >=7.360.1, matching the pin. Its FFmpeg pkg-config
  requirements are libavcodec >=60.31.102, libavfilter >=9.12.100,
  libavformat >=60.16.100, libavutil >=58.29.100, libswresample >=4.12.100 and
  libswscale >=7.5.100. The recipe installs the corresponding FFmpeg 8.0 libraries.
- FFmpeg checks dxva.h, ID3D11VideoDecoder/Context and codec-specific
  DXVA_PicParams_AV1/HEVC/VP9. Actual target SDK/probe success remains unverified
  locally; configure and the existing eight D3D11VA/D3D11VA2 gates must pass in CI.
  libplacebo's reported D3D11 object compilation is historical evidence only.
- FFmpeg requires dav1d >=0.5.0 via dav1d.pc (pin 1.5.4), and checks zlib.pc or
  libz. Existing recipes provide those names under the restricted target prefix.
- Packaging accepts header-only receipts, requires successful recorded install
  commands, retains the archive/licences and rejects vulkan-1.dll even if bundled.
  The new component provides no DLL and has an empty shipped-DLL list.

No additional confirmed missing dependency was found in this static review.
This does not establish that FFmpeg, mpv or packaging will succeed in the next run.

## Validation

Dot-sourced local-env.ps1 before each validation shell. Synthetic tests create
mode-0755 directories under scratch/tmp and remove their own fixture files.

| Check | Result | Actual |
| --- | --- | --- |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | Initial 54 tests, 0.539 s; final 54 tests, 0.515 s; exit 0 |
| ruff check / ruff format --check spikes/mpv/ci-build | PASS | Final exit 0 |
| actionlint 1.7.12 -shellcheck= dedicated workflow | PASS | Exit 0; external shellcheck unavailable, not run |
| shfmt 3.14.1 Bash parse/format, six shell scripts | PASS | All exit 0 |
| Actual Vulkan-Headers archive audit | PASS | Archive hash, licence paths, Vulkan 1.4/header 321 and both header directory inventories |
| Recipe order/disabled backends, YAML constraints, updated round rule | PASS | Header install before libplacebo; both backends disabled; workflow constraints unchanged |
| bash -n | NOT_RUN | No permitted Bash found; MSYS2 excluded |
| Actual Linux header installation/compilation | NOT_RUN | Unit tests use synthetic header trees; archive audit is read-only |
| Actual objdump/import/configuration/manifest/source-offer output | NOT_RUN | No new DLL; gates implemented for the CI runner |
| Windows DLL/GPU/playback/size and reproducibility proof | NOT_RUN | Requires green artifact and later prescribed checks |
| Product build/tests and Part B/C reruns | NOT_RUN | No product/B1 changes |

All existing 49 tests still pass. New tests verify complete() emits header-only
receipt data from installed bytes, rejects missing/modified vk_video headers,
requires Vulkan 1.4, rejects enabled libplacebo Vulkan and rejects vulkan-1.dll
imports even if bundled. No tests were skipped, loosened or waived; no failed
unit-test run occurred. No GUI operation was performed.

Network/error record: the initial sandbox download hit WinError 10013 (socket
access denied). A reviewed escalation allowed the official API/archive download.
The download succeeded, then its first inspection command hit AttributeError
because a licence directory was treated as a file; inspection was corrected to
filter file members and passed without another download. The browser tool could
not open the GitHub URLs; the official API/archive were read via Python instead.
These were retrieval/inspection errors, not library compile or unit-test failures.

Evidence outside Git: evidence/VE-P1e-3c1/ci-round6 contains initial/final unit
logs, Ruff/actionlint/shfmt logs, results.json, vulkan-headers-audit.json,
static-checks.json and disk.json. The archive/source.json remain in
cache/mpv-lgpl/ci-round6-sources for reuse. No binaries or archives were added to
Git; no local dependency environment was installed/restored. Mock receipts were
deleted and are not production manifest evidence.

## Disk and cleanup

Decimal GB; overlapping rows are not summed. Snapshot after checks, before report
rewrite/bookkeeping. All inventories reported zero access errors; file lengths
are not disk allocation measurements.

| Area | Bytes | Decimal GB |
| --- | ---: | ---: |
| repo | 3,528,268,314 | 3.528268314 |
| package | 5,764,162 | 0.005764162 |
| evidence/VE-P1e-3c1 (includes accepted previous work) | 46,074,619 | 0.046074619 |
| evidence/VE-P1e-3c1/ci-round6 (before disk.json itself) | 59,562 | 0.000059562 |
| scratch | 0 | 0 |
| cache, total | 8,905,557,096 | 8.905557096 |
| MSYS2 toolchain, cache/msys2 (untouched) | 856,811,931 | 0.856811931 |
| Historical source/build tree, cache/mpv-lgpl/source-build (untouched) | 36,575,903 | 0.036575903 |
| Prior source review cache (read-only reuse) | 64,181,348 | 0.064181348 |
| New source cache, cache/mpv-lgpl/ci-round6-sources | 2,760,957 | 0.002760957 |
| New extracted/Linux build trees and built DLL output | 0 | 0 |
| Dependency restore / new tool downloads | 0 | 0 |

| Drive free | Start bytes / GB | End snapshot bytes / GB |
| --- | ---: | ---: |
| C | 354,804,289,536 / 354.804289536 | 354,801,823,744 / 354.801823744 |
| D | 980,062,171,136 / 980.062171136 | 980,059,181,056 / 980.059181056 |

D remains above 200 GB free; cache below 40 GB; cycle evidence below 300 MB.
New persistent source cache is 0.002760957 GB; additional edits/logs are small,
with attributable growth below 0.004 GB and below the 1 GB limit. No initial full
workspace baseline was taken; drive-wide changes are not attributed to this task.

Cleanup candidate: only this continuation's empty scratch/tmp, 0 bytes. Tests
removed their fixtures; the initial log was moved to evidence. Remove only that
verified empty directory after recording it here. No historical evidence/cache,
MSYS2, package, owner media or queues were cleaned; no GPG agent/dirmngr started.

## Questions for the designer

No new design decision is required. Defaults: matching SDK tag, exact commit and
SHA pin; compile-time headers only; Apache-2.0 election reflecting the actual
C-header licence scope; no Vulkan loader or upstream stub patch. Actual artifact
licence/runtime review and LICENSES.md update remain deferred as prescribed.

## Remaining / intentionally deferred

Await operator commit/push and CI round 6. Five CI rounds have been used; no fixed
cap now applies. Designer owns the two-consecutive-no-progress stop decision.
Further compiler/linker/packaging failures cannot be excluded by these checks.
On failure, designer records the failing step/logs before resuming Codex. On
success, operator downloads and verifies SHA256SUMS before Windows property,
D3D11VA/H.264/size proof, LICENSES.md update and second-build comparison.

No CI dispatch, artifact download, new-DLL runtime proof, product integration,
distribution clearance, paid resources or Git mutation was performed.

Cleanup result: PASS. Removed only verified empty scratch/tmp (0 bytes); scratch is empty. Nothing from this continuation remains for the owner to delete.

Final scope/whitespace check: PASS. Read-only git status lists exactly the seven changed files above; git diff --check exited 0. Git warned about future LF-to-CRLF conversion for the report, build.sh and Python helpers; no whitespace errors were reported.
