Task ID: VE-P1e-3c1 / Cycle: GitHub Actions round 7 preparation (6 CI rounds used)
Status: PARTIAL
Awaiting CI build

## Outcome

Implemented section 11.9 using an installed shaderc_combined.pc build-recipe
change. Libs.private gains the compiler-discovered library directory and
-l:libstdc++.a, so a C-driver link explicitly selects the static C++ runtime.
A Linux shaderc C-driver link probe determines whether static winpthread is
actually needed; it is added only after a pthread/sem undefined-symbol failure.
Unrelated failures stop immediately. Every probe attempt is retained.

Before mpv compilation, a new check reads Ninja's generated libmpv link command
and requires the static runtime after the observed static C++ archives. It also
checks the separate SPIRV-Cross import-library decision. The recipe modification,
actual pkg-config output and generated link evidence enter the manifest and
sources.tar.zst. Upstream source archives and patches are unchanged.

Windows tests/static checks pass. Actual Linux probe/link/packaging and final
DLL imports remain NOT_RUN here. No green artifact or new-DLL proof is claimed.
Part B/C remain accepted from earlier work and were not rerun.

## Start and verified historical CI evidence

Read AGENTS.md, CURRENT_TASK.md completely (including 11.9 and updated 11.2),
CLAUDE.md and docs/WORKSPACE.md. Terminal: Windows / PowerShell.
Initial read-only Git inspection:
- Branch: claude/project-thread-6lra47
- HEAD: 52c5006e14233dcca64ac933cf33c3cea5d649ab
- Working tree: clean

Read-only Git used sandbox escalation. CURRENT_TASK.md remains unchanged.
No Git mutation, fetch, commit, push, merge, CI dispatch or paid resource usage
occurred. Operator owns commit/push.

The GitHub connector was used read-only to inspect run 40197198723, job
121180493033. It confirms the build step failed and packaging/upload were skipped.
This is historical CI evidence, not a new build. Meson version in that log is
1.3.2. The final link used gcc-posix and contained, in order:

    ... libharfbuzz.a ... libplacebo.a ... libshaderc_combined.a ... -lspirv-cross-c-shared ...

No libstdc++ archive or -lstdc++ appeared. The undefined symbols included operator
new, std::__throw_length_error and C++ ABI type-info vtables. No pthread/sem
undefined-symbol diagnostics were found in that historical failure; the next
real link probe determines whether adding the C++ runtime exposes such a need.
The log also confirms installation of libspirv-cross-c-shared.dll.a and
libspirv-cross-c-shared.dll. Only a minimal link-tail excerpt was retained locally;
the full job log was not saved to disk or committed.

Historical run: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/40197198723

## Changed files

- spikes/mpv/ci-build/driver.py: installed .pc edit; static C-driver shaderc probe;
  conditional static winpthread; actual pkg-config/link-order validation;
  generated Ninja link check; build-recipe/manifest/source-offer receipts;
  explicit Windows system pathcch.dll allowance.
- spikes/mpv/ci-build/build.sh: invoke the recipe change after shaderc install,
  refresh its receipt, and verify the generated mpv link after setup/before compile.
- spikes/mpv/ci-build/test_driver.py: six added metadata/probe/order/import-library
  tests, preserving the existing 54 tests.
- spikes/mpv/ci-build/README.md: runtime recipe, evidence and validation boundaries.
- .ai/LAST_REPORT.md: this report.

No workflow, source pin/lock, upstream patch, cross file, product, ci.yml,
existing source-manifest.json, LICENSES.md or accepted B1 implementation changed.
No PC MSYS2 tree/executable was used or modified; aggregate size metadata only
was inventoried for disk reporting.

## Why this recipe and how it is recorded

Meson 1.3.2's shaderc dependency factory prefers shaderc_combined/shaderc_static
when prefer_static=true, matching the observed CI link. Pinned shaderc's
shaderc_combined.pc template has no Libs.private. Fixing this leaf dependency
puts its runtime after the archive rather than placing a C++ flag near the
start of a gcc link or before libplacebo's dependent archives.

The edit preserves public Libs, Requires.private and existing private flags.
The compiler supplies the actual libstdc++.a directory; -l:libstdc++.a selects
that archive explicitly rather than a DLL import library. static-libgcc remains
in effect. No unconditional pthread flag is added.

The runner links a small C source using shaderc_compiler_initialize/release,
libshaderc_combined.a and the static runtime. It does not execute the output DLL.
If missing pthread/sem symbols occur, it checks the actual libwinpthread.a path,
adds that static archive and retries once. A second failure or any unrelated
first failure stops the job. The original failure and successful retry, if any,
are both recorded rather than erased.

recipe-changes.json stores component/kind, the installed .pc path, before/after
contents, resulting SHA-256, private flags, actual pkg-config --static --libs
output, probe source and every command/exit/stdout/stderr. It is attached to the
shaderc receipt and manifest build_recipe_changes, and retained in sources.tar.zst.
The change is explicitly an installed pkg-config build recipe, not an upstream
patch; all source-lock patch lists remain empty.

mpv-link.json stores the actual Ninja-generated link argv and ordering proof.
It requires static libstdc++ after libharfbuzz, libplacebo and shaderc_combined;
plain -lstdc++ alone is not accepted as static proof. It rejects static SPIRV-Cross
archives and requires its shared C API and unshadowed .dll.a import library.
The command and import-library hash enter the manifest/source offer. Package
checks revalidate the edited metadata hash and recorded link ordering.

## Look-ahead and packaging review

The historical link's C++ archives were libharfbuzz.a, libplacebo.a and
libshaderc_combined.a. Shaderc_combined contains its glslang/SPIRV-Tools children;
SPIRV-Cross was not a static C++ archive on that line. Keep its separate DLL
choice from 11.7. Its real import-library installation was confirmed in the log.

Pinned mpv calls PathCchCanonicalizeEx and PathCchRemoveFileSpec and explicitly
links the Windows pathcch library. Added pathcch.dll to the explicit system DLL
list as a concrete post-link look-ahead fix; no wildcard for unknown DLLs was
introduced. The existing runtime import closure still requires any imported
libstdc++-6.dll, libgcc_s_seh-1.dll or libwinpthread-1.dll to be copied and licensed.
Missing or unknown imported DLLs remain fatal; vulkan-1.dll remains forbidden.

Read package.sh and all package() checks. They retain: complete source/build
receipts, SHA rechecks, actual mpv gpl=false/options, FFmpeg GPL/nonfree/version3
and codec/hwaccel gates, embedded configuration strings, exact DLL import closure,
licence texts/runtime exception notices, manifest generation, exact source offer
and SHA256SUMS. The two new JSON receipts are copied into the source offer.
SHA256SUMS is computed after sources.tar.zst and covers every artifact file except
itself; each DLL hash remains printed before upload. No check was bypassed.
Actual licensing/manifest/source-offer packaging has not yet run on a successful
DLL, and the existing PC acceptance work remains required.

Primary references consulted for the link review:
[Meson shaderc selection](https://github.com/mesonbuild/meson/blob/1.3.2/mesonbuild/dependencies/misc.py),
[Meson static dependency defaults](https://github.com/mesonbuild/meson/blob/1.3.2/mesonbuild/dependencies/base.py),
[Meson static pkg-config handling](https://github.com/mesonbuild/meson/blob/1.3.2/mesonbuild/dependencies/pkgconfig.py),
[GCC link order](https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html), and
[Windows PathCch API](https://learn.microsoft.com/en-us/windows/win32/api/pathcch/nf-pathcch-pathcchcanonicalizeex).
The pkg-config guide endpoints were unavailable; the pinned templates and Meson
implementation supplied the relevant behavior. No dependency/tool was downloaded.

## Validation

Dot-sourced local-env.ps1 before validation shells. Tests use mode-0755 directories
under scratch/tmp and remove their synthetic files. Compiler/archive/pkg-config
outputs in these tests are mocked, not actual Windows/Linux links.

| Check | Result | Actual |
| --- | --- | --- |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | Initial 60 tests, 0.594 s; final 60 tests, 0.587 s; exit 0 |
| ruff check / ruff format --check spikes/mpv/ci-build | PASS | Final exit 0 |
| actionlint 1.7.12 -shellcheck= dedicated workflow | PASS | Exit 0; external shellcheck unavailable, not run |
| shfmt 3.14.1 Bash parse/format, six shell scripts | PASS | All exit 0 |
| Static recipe order/generated-link-hook/YAML constraints | PASS | Edit before consumers, mpv hook wired, workflow constraints preserved |
| Historical CI link/install inspection | PASS | Actual old C-driver link, absent C++ runtime and shared SPIRV-Cross confirmed |
| bash -n | NOT_RUN | No permitted Bash available; MSYS2 excluded |
| Actual pkg-config edit and C-driver link probe on Linux | NOT_RUN | Unit-test fixtures only locally; next CI runs real commands |
| Actual generated round-7 Ninja link/order and final DLL imports | NOT_RUN | No new Linux build or DLL |
| Actual packaging, SHA256SUMS and sources.tar.zst output | NOT_RUN | Requires successful link |
| Windows properties/GPU/playback/size and reproducibility | NOT_RUN | Requires green artifact and later prescribed checks |
| Product checks and Part B/C reruns | NOT_RUN | No product/B1 changes |

Six new tests cover preserving/deduplicating Libs.private, rejection of duplicate
fields, runtime position/static form, retaining SPIRV-Cross shared linkage,
recipe/manifest evidence, adding winpthread only after a mock thread-symbol
failure, and rejecting an unrelated mock failure. Existing 54 tests also pass.
Negative-case linker diagnostics in unit logs are synthetic expected fixtures;
they are not newly observed compiler failures. No unit run failed; no tests were
skipped, loosened or waived. No GUI operation was performed.

Evidence outside Git: evidence/VE-P1e-3c1/ci-round7 contains historical
round6-link-excerpt.txt, initial/final unit logs, Ruff/actionlint/shfmt logs,
results.json, static-checks.json and disk.json. Mock receipts were deleted and
are not production manifests. No source archive or local tool was downloaded.

## Disk and cleanup

Decimal GB; overlapping rows are not summed. Snapshot after checks and before
report rewrite/bookkeeping. Zero inventory access errors; logical file lengths
are not allocated disk space.

| Area | Bytes | Decimal GB |
| --- | ---: | ---: |
| repo | 3,528,345,481 | 3.528345481 |
| package | 5,764,162 | 0.005764162 |
| evidence/VE-P1e-3c1 (includes accepted earlier work) | 46,338,226 | 0.046338226 |
| evidence/VE-P1e-3c1/ci-round7 (before disk.json itself) | 77,588 | 0.000077588 |
| scratch | 0 | 0 |
| cache, total | 8,905,557,096 | 8.905557096 |
| MSYS2 toolchain, cache/msys2 (untouched) | 856,811,931 | 0.856811931 |
| Historical source/build tree, cache/mpv-lgpl/source-build (untouched) | 36,575,903 | 0.036575903 |
| Prior round-1 source review cache (read-only reuse) | 64,181,348 | 0.064181348 |
| Prior round-6 source cache (untouched) | 2,760,957 | 0.002760957 |
| New Linux source/build trees and built DLL output | 0 | 0 |
| Dependency restore / new tool downloads | 0 | 0 |

| Drive free | Start bytes / GB | End snapshot bytes / GB |
| --- | ---: | ---: |
| C | 354,800,934,912 / 354.800934912 | 354,794,618,880 / 354.794618880 |
| D | 980,059,082,752 / 980.059082752 | 980,058,849,280 / 980.058849280 |

D remains above 200 GB free; cache below 40 GB; cycle evidence below 300 MB.
New text edits/logs are below 0.001 GB, with no restore/download/compiled output;
attributable persistent growth is below the 1 GB limit. No initial full-workspace
baseline was taken; drive-wide changes are not equated with this task's growth.

Cleanup candidate: this continuation's empty scratch/tmp, 0 bytes. Tests removed
their mock archives/receipts; the initial log was moved to evidence. Remove only
that verified empty directory after recording it here. No historical cache or
evidence, MSYS2, package, owner media or queues were cleaned; no GPG agent/dirmngr
was started.

## Questions for the designer

Default chosen under 11.9: leaf shaderc_combined.pc Libs.private change with an
explicit static archive; conditional static winpthread based on an actual C-driver
probe; keep SPIRV-Cross shared and all final import/licence checks. No new design
decision is required before this CI round. A green artifact still needs the
prescribed PC and licence acceptance checks.

## Remaining / intentionally deferred

Await operator commit/push and CI round 7. Six rounds have been used; no fixed
cap applies. Designer owns the two-consecutive-no-progress stop rule. Further
compiler/linker or previously unexecuted packaging failures remain possible.
On failure, designer records step/logs before resuming Codex. On success, operator
downloads and verifies SHA256SUMS, then Windows DLL/property/D3D11VA/H.264/size
proof, LICENSES.md update and second-build comparison can proceed.

No CI dispatch, artifact download, new-DLL runtime proof, product integration,
distribution clearance, paid resource usage or Git mutation was performed.

Cleanup result: PASS. Removed only verified empty scratch/tmp (0 bytes); scratch is empty. Nothing from this continuation remains for the owner to delete.

Final scope/whitespace check: PASS. Read-only git status lists exactly the five changed files above; git diff --check exited 0. Git warned about future LF-to-CRLF conversion for the report, build.sh and Python helpers; no whitespace errors were reported.
