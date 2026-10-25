Task ID: VE-P1e-3c1 / Cycle: GitHub Actions round 4 preparation (3 of 6 CI rounds used)
Status: PARTIAL
Awaiting CI build

## Outcome

Implemented section 11.6. The shared Meson cross file now supplies nasm explicitly.
libass keeps assembly enabled; dav1d explicitly enables assembly; FFmpeg explicitly
selects nasm and enables assembly/x86asm. No assembly fallback was used to bypass
the failure. Runtime build receipts now check actual generated assembly settings,
and record libass iconv/libpng as disabled in the generated artifact manifest.

Windows validation passed. Actual Linux toolchain/library compilation and new-DLL
proof are NOT_RUN in this continuation. There is no successful new CI artifact or
DLL here. Part B/C remain accepted from earlier work and were not rerun.

## Start and reported CI result

Read AGENTS.md, CURRENT_TASK.md completely, CLAUDE.md and docs/WORKSPACE.md.
Terminal: Windows / PowerShell. Initial read-only Git inspection:
- Branch: claude/project-thread-6lra47
- HEAD: d85943d0784dd4cb41328335ab0484676d6f4392
- Working tree: clean

Designer section 11.6 reports run 40185905349 on b427551 passed the toolchain
step, then failed configuring libass:

    Compiler for language nasm for the host machine not found.
    libass/meson.build:268: WARNING: nasm was not found; ASM functions are disabled.
    libass/meson.build:337:8: ERROR: Problem encountered: Assembly was requested, but cannot be built; see prior messages.

Those are supplied CI results, not a local build rerun. prepare.sh already
installs nasm, but the cross file lacked the host nasm entry.
CURRENT_TASK.md remains unchanged and authoritative. No Git mutation, fetch,
commit, push, merge, CI dispatch or paid resource usage was performed. Read-only
Git inspection used sandbox escalation. Operator owns commit/push.

## Changed files

- spikes/mpv/ci-build/mingw.ini.in: nasm = 'nasm' under [binaries].
- spikes/mpv/ci-build/build.sh: dav1d -Denable_asm=true; FFmpeg
  --x86asmexe=nasm --enable-asm --enable-x86asm. libass -Dasm=enabled retained.
- spikes/mpv/ci-build/driver.py: check/record actual nasm version in the toolchain
  receipt; require NASM >=2.14; require generated libass CONFIG_ASM and dav1d
  HAVE_ASM; record libass features.iconv=false and features.libpng=false from
  generated config.h; reject unexpected optional dependency enablement; require
  generated FFmpeg HAVE_X86ASM=1 and reject assembly-disabling configure flags.
- spikes/mpv/ci-build/test_driver.py: five added tests covering version bounds,
  assembly/optional-feature gates and real complete() receipt generation.
- spikes/mpv/ci-build/README.md: round 4 host-tool/assembly policy and limitations.
- .ai/LAST_REPORT.md: this report.

No workflow, source lock, upstream patch, product, ci.yml, existing
source-manifest.json, LICENSES.md or accepted B1 implementation changed.
No PC MSYS2 executable/tree was used or modified. Only aggregate size metadata
was inventoried for the disk table.

## Pinned-source configure and host-tool review

Read the whole Meson/CMake cross files and build recipe, and inspected pinned
archive configuration/options for all fourteen source components. The six Meson
component recipes use the same cross file. A local static audit compared every
explicit Meson option name, including continued command lines, against each
pinned project's option declarations; all six matched.

- libass 0.17.5 adds host language nasm and requires NASM >=2.10. The new cross
  entry supplies it. CONFIG_ASM must be 1 in the actual generated config.h.
- dav1d 1.5.4 uses find_program('nasm'), checks >=2.14, and generates win64 objects
  for this target. It receives the shared cross file and explicit enable_asm=true;
  HAVE_ASM must be 1. No ARM gas-preprocessor is needed for x86_64.
- FFmpeg 8.0 defaults to nasm but now receives it explicitly. Its configure uses
  instruction probes (including movbe), rather than a numeric NASM minimum.
  Those probes must succeed and HAVE_X86ASM must be 1. The numeric preflight
  enforces the highest explicit project minimum, 2.14, before source builds.
- The actual runner's nasm -v output is collected during the next toolchain step;
  it is not measured locally. NASM 2.16.01 text used in tests is mock data only.
- iconv/libpng are optional direct dependency checks in libass with no dedicated
  disable option in its pinned Meson options. The target prefix contains neither;
  PNG-dependent test/compare programs remain disabled by auto-features=disabled.
  The post-build gate records actual disabled macros and rejects unexpected
  enablement, rather than fabricating options or adding target libraries.
- Cross binaries already include target C/C++, ar, strip, pkg-config and windres.
  mpv uses windows.compile_resources; windres is already supplied. GCC selects
  its target linker/binutils; build.sh exports target RANLIB. CMake names the
  target C/C++ and resource compilers, with native programs searched outside the
  target root. No project inspected required an additional manual ld/ranlib
  Meson override; none was guessed.
- Reviewed zlib, FreeType, FriBidi, HarfBuzz, libplacebo, shaderc/glslang,
  SPIRV-Tools/Headers and SPIRV-Cross configuration declarations. Disabled tests,
  examples and platform-specific optional tools remain unchanged. No further
  confirmed host-tool defect was found by this static review.

This review does not establish that the next CI build reaches FFmpeg/mpv or that
any library compiles successfully after the NASM discovery fix.

## Validation

Dot-sourced local-env.ps1 before every test/check shell. Test fixtures live only
under scratch/tmp, use mode 0755 and clean up their own mock files.

| Check | Result | Actual |
| --- | --- | --- |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | Initial 42 tests, 0.421 s; final 43 tests, 0.430 s; exit 0 |
| ruff check spikes/mpv/ci-build | PASS | Exit 0 |
| ruff format --check spikes/mpv/ci-build | PASS | Exit 0 after formatting edited helpers |
| actionlint 1.7.12 -shellcheck= .github/workflows/libmpv-lgpl.yml | PASS | Exit 0; external shellcheck unavailable, not run |
| shfmt 3.14.1 -ln bash -i 4 -d, all six shell scripts | PASS | All exit 0 |
| Cross-file/assembly-recipe assertions | PASS | NASM/target compilers/ar/windres, shared cross file, required assembly flags and no disable flag |
| Pinned Meson option-name audit | PASS | All explicit options for six component recipes exist in pinned declarations |
| YAML / independent workflow assertions | PASS | Exact trigger paths, read permissions, runner, timeout, action SHA/version comments, retention, no secret references |
| bash -n | NOT_RUN | No permitted Bash available; MSYS2 excluded |
| Real nasm version / Linux toolchain and library builds | NOT_RUN | Version parsing and pipeline tests use mocks only |
| Actual DLL imports/configuration/size and GUI/GPU/playback proof | NOT_RUN | Requires a green artifact |
| Two-run reproducibility | NOT_RUN | Requires successful CI runs |
| Product tests/build and accepted Part B/C reruns | NOT_RUN | No product/B1 implementation change |

New tests accept NASM 2.14/2.16.01, reject old/unrecognized versions, require
libass/dav1d assembly, reject libass iconv/libpng enablement, reject missing
FFmpeg x86asm or disabling flags, and verify complete() writes the expected
actual-header-derived feature fields. Existing 38 tests still pass. No failed
test run, skipped test or waived gate occurred in this continuation. No GUI
operation was performed.

Evidence outside Git: evidence/VE-P1e-3c1/ci-round4 contains initial-unittest.log,
unittest.log, ruff.log, actionlint.log, shfmt.log, results.json,
meson-options.json, static-checks.json and disk.json. Tools and source archives
were reused from existing caches. No downloads/restores were performed. Mock
receipts were deleted by tests and are not production build evidence.

## Disk and cleanup

Decimal GB; overlapping rows are not summed. Snapshot after checks and before
report rewrite/final bookkeeping. No access errors were recorded. Sizes are
logical file lengths, not allocated disk space.

| Area | Bytes | Decimal GB |
| --- | ---: | ---: |
| repo | 3,528,120,426 | 3.528120426 |
| package | 5,764,162 | 0.005764162 |
| evidence/VE-P1e-3c1 (includes accepted previous work) | 45,452,015 | 0.045452015 |
| evidence/VE-P1e-3c1/ci-round4 (before disk.json itself) | 53,477 | 0.000053477 |
| scratch | 0 | 0 |
| cache, total | 8,902,796,139 | 8.902796139 |
| MSYS2 toolchain, cache/msys2 (untouched) | 856,811,931 | 0.856811931 |
| Historical source/build tree, cache/mpv-lgpl/source-build (untouched) | 36,575,903 | 0.036575903 |
| Cached review sources, cache/mpv-lgpl/ci-round1-sources (reused read-only) | 64,181,348 | 0.064181348 |
| New Linux source/build trees and built DLL output | 0 | 0 |
| Dependency restore / new tool downloads | 0 | 0 |

| Drive free space | Start bytes / GB | End snapshot bytes / GB |
| --- | ---: | ---: |
| C | 354,810,916,864 / 354.810916864 | 354,809,933,824 / 354.809933824 |
| D | 980,063,019,008 / 980.063019008 | 980,062,801,920 / 980.062801920 |

D remains above 200 GB free; cache below 40 GB; cycle evidence below 300 MB.
No initial full-directory baseline was taken, so drive-wide changes are not
attributed to this task. New text edits/logs are below 0.001 GB, with no compiled
output/download/restore; attributable persistent growth is below the 1 GB limit.

Cleanup candidate: this continuation's empty scratch/tmp, 0 bytes. Unit tests
removed their fixture files; the initial test log was moved to evidence. Remove
only this verified empty directory after recording it here. No old evidence,
cache, MSYS2, package or owner data cleanup was attempted; no gpg-agent/dirmngr
was started.

## Questions for the designer

None requiring a new design decision. Default: enforce the pinned projects'
highest explicit NASM minimum at runtime and retain FFmpeg's own instruction
probes. Record actual generated libass optional-feature macros, with iconv/libpng
remaining disabled; do not patch upstream or add those libraries.

## Remaining / intentionally deferred

Await operator commit/push and CI round 4. Three of six CI rounds have been used.
Further assembler, compiler, linker or packaging failures remain possible; the
static and mocked checks cannot guarantee a green build. Designer should append
any next failure step/logs before resuming Codex. On success, operator downloads
and verifies the artifact, then the prescribed Windows property/D3D11VA/H.264/
size checks, LICENSES.md update and second-run comparison can proceed.

No CI dispatch, artifact download, new-DLL runtime proof, product integration,
distribution approval, paid resources or Git mutation was performed.

Cleanup result: PASS. Removed only verified empty scratch/tmp (0 bytes); scratch is empty. Nothing from this continuation remains for the owner to delete.

Final scope/whitespace check: PASS. Read-only git status lists exactly the six changed files above; git diff --check exited 0. Git warned about future LF-to-CRLF conversion for the report, shell recipe, Python helpers and cross file; no whitespace errors were reported.
