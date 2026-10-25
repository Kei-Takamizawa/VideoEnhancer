Task ID: VE-P1e-3c1 / Cycle: GitHub Actions round 5 preparation (4 of 10 CI rounds used)
Status: PARTIAL
Awaiting CI build

## Outcome

Implemented section 11.7. The Meson cross file now names the prefixed dlltool,
ranlib, nm, objcopy, objdump, ld and windmc binaries. Driver checks executable
availability during toolchain collection and again before generating cross files
and configuring any library. Missing required tools stop early; absent optional
windmc is recorded and omitted from the generated cross file.

SPIRV-Cross remains a separate C API DLL, explicitly allowlisted and recorded
per component from the actual packaged DLL set. Shaderc remains enabled because
both the pinned rendering pipeline and mpv's D3D11 contract require compilation
beyond SPIRV-Cross translation. Shader licence metadata now includes glslang's
Bison-generated parser exception, exact notice-file hashes and compatibility
rationale. Actual Linux builds and new-DLL proof are NOT_RUN in this continuation.
No green artifact or distribution acceptance is claimed.

Section 11.2's limit is now ten CI rounds; its matching stop status in 11.3 was
updated consistently. Historical designer results/counts were preserved. Accepted
Part B/C work was not rerun.

## Start and reported CI failure

Read AGENTS.md, CURRENT_TASK.md completely, CLAUDE.md and docs/WORKSPACE.md.
Terminal: Windows / PowerShell. Initial read-only Git inspection:
- Branch: claude/project-thread-6lra47
- HEAD: 9674da2ae1935c58a99dbdfb43b81153012c6d4e
- Working tree: clean

Section 11.7 reports run 40189018187 on ab0a24a built through libass and
SPIRV-Cross, then failed at libplacebo configure:

    Program llvm-dlltool dlltool found: NO
    libplacebo/src/meson.build:28:12: ERROR: Program 'llvm-dlltool dlltool' not found or not executable

This is supplied CI evidence, not a newly executed build. The pinned source uses
dlltool to generate the UCRT math import library. Cross-file tool discovery was
missing the installed x86_64-w64-mingw32-dlltool name.

Read-only Git used sandbox escalation. No Git mutation, fetch, commit, push,
merge, workflow dispatch or paid resource usage occurred. Operator owns Git work.

## Changed files

- .ai/CURRENT_TASK.md: only ten-round limit/stop consistency changes requested
  by 11.7; other task instructions and historical results preserved.
- .ai/LAST_REPORT.md: this report.
- spikes/mpv/ci-build/mingw.ini.in: explicit prefixed dlltool and other binutils.
- spikes/mpv/ci-build/build.sh: invoke configure-cross instead of sed template
  substitution; all compiler/library feature choices unchanged.
- spikes/mpv/ci-build/driver.py: executable lookup/receipts; optional windmc;
  cross-file generation; source-offer cross-tools.json; licence evidence hashes
  and Bison exception checks; actual per-component shipped_dlls in manifest.
- spikes/mpv/ci-build/test_driver.py: six additional preflight, licence and shared
  dependency tests, plus mocked executable availability for existing apt tests.
- spikes/mpv/ci-build/sources.lock.json: shader licence/provenance, child-component
  relationships and shared-DLL policy metadata; archive URLs/hashes unchanged.
- spikes/mpv/ci-build/README.md: round 5 tool/provenance behavior and ten-round cap.
- spikes/mpv/ci-build/DISTRIBUTION.md: shader/Bison licence rationale and references.

No workflow, product, ci.yml, upstream patch, cross CMake file, existing
source-manifest.json, LICENSES.md or B1 implementation changed. No PC MSYS2 tree
or executable was used or modified; aggregate size metadata only was inventoried.

## Look-ahead: SPIRV-Cross and shaderc

Decision: retain libspirv-cross-c-shared.dll separately. Both pinned libplacebo
src/d3d11/meson.build and mpv meson.build request spirv-cross-c-shared. Changing to
static would require dependency/build metadata changes. Preserve the working
shared configuration rather than aliasing a static library as the shared API.
The import allowlist already contains libspirv-cross-c-shared.dll and its no-lib
variant; shaderc_shared variants are also explicit. The source lock identifies
provided DLL names. package() populates shipped_dlls only from the actual imported
and packaged closure; root DLL hashes/imports remain actual build output.

SPIRV-Cross translates SPIR-V to the target shading language. libplacebo's D3D11
gpu.c calls pl_spirv_create, and src/glsl/meson.build supplies shaderc or glslang
for GLSL compilation. SPIRV-Cross alone does not replace that stage. Additionally,
pinned mpv's D3D11 feature explicitly requires shaderc and SPIRV-Cross. Keep
shaderc=enabled and its glslang/SPIRV-Tools/Headers dependency revisions unchanged.
No new renderer architecture or target-library feature was introduced.

Pinned-source review locations:
- libplacebo cee9b076f2c63104ccfd497fa79c39a867293ec4:
  src/meson.build (dlltool/UCRT math), src/d3d11/meson.build,
  src/d3d11/gpu.c and src/glsl/meson.build.
- mpv 0fae4695470bf2c0c06762503292ee5379f62f62: meson.build D3D11 requirements.
- glslang d213562e35573012b6348b2d584457c3704ac09b:
  LICENSE.txt and glslang/MachineIndependent/glslang_tab.cpp / glslang_tab.cpp.h.

## Shader licences and exception evidence

Shaderc itself is Apache-2.0; its included glslang, SPIRV-Tools and SPIRV-Headers
have separate manifest entries. SPIRV-Tools and SPIRV-Cross are Apache-2.0;
SPIRV-Headers is MIT. glslang's aggregate is BSD-3-Clause AND BSD-2-Clause AND MIT
AND Apache-2.0 AND (GPL-3.0-or-later WITH Bison-exception-2.2). Earlier aggregate
metadata omitted the generated parser notices; this round corrects that gap.

The immutable glslang archive matches its existing SHA-256 pin. The full archive's
C/C++ GPL-notice scan found exactly the two parser files, both retaining the
special exception. Their SHA-256 values:
- glslang_tab.cpp: 2db4d68463c01be056c78ec80b62a3e814cd573128cf9a7be9b0f5aa417781e9
- glslang_tab.cpp.h: 12d516759f0e24d59dafc61f4ca8e5405f4bce2066092308f6c4c8b5d91f7891

Their full original source notices are included in the licence-file set; GPLv3
text is already retained under LICENSES/toolchain/GPL-3. Fetch/package verify
notice-file hashes and the exception terms. Unapproved plain GPL evidence or
additional glslang C/C++ GPL sources without verified exception evidence fail.
The other four pinned shader component archives' C/C++ GPL-notice scan found no
matches; this bounded text scan is not a substitute for final artifact review.

Compatibility rationale recorded in metadata and DISTRIBUTION.md:
- BSD/MIT permit this use while retaining notices and BSD endorsement conditions.
- Apache-2.0 notices and patent conditions remain; the combined LGPL library keeps
  the LGPL-3.0-or-later election already used for Apache shader dependencies.
- The retained Bison exception permits this generated parser in a larger work
  under chosen terms; this rendering/shader compiler is not a parser generator
  using the skeleton. No exception is removed, and plain GPL shader code without
  an applicable exception is not an approved dependency.
- The separate MIT application still must meet LGPL source/replacement obligations;
  no final product distribution clearance is claimed from this source review.

Primary references consulted:
[Bison exception](https://spdx.org/licenses/Bison-exception-2.2.html),
[Apache compatibility](https://www.apache.org/licenses/GPL-compatibility.html),
[LGPLv3](https://spdx.org/licenses/LGPL-3.0-or-later.html),
[MIT](https://spdx.org/licenses/MIT.html),
[BSD](https://spdx.org/licenses/BSD-3-Clause.html).
Direct GNU documentation requests timed out; the pinned original notices and
SPDX licence texts supplied the exception evidence. One initial source-inspection
command used an absent archive member and raised StopIteration; corrected paths
were read successfully. Neither issue was a compile/test failure.

## Validation

Dot-sourced local-env.ps1 before each validation shell. Tests use mode-0755
scratch directories and remove their own synthetic files.

| Check | Result | Actual |
| --- | --- | --- |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | Initial 49 tests, 0.471 s; final 49 tests, 0.452 s; exit 0 |
| ruff check / ruff format --check spikes/mpv/ci-build | PASS | Final exit 0 |
| actionlint 1.7.12 -shellcheck= dedicated workflow | PASS | Exit 0; external shellcheck unavailable, not run |
| shfmt 3.14.1 Bash parse/format, six shell scripts | PASS | All exit 0 |
| Static cross-tool, source-lock, ten-round and YAML assertions | PASS | Expected prefixed keys/preflight, 14 sources, workflow security/trigger constraints preserved |
| Actual cached glslang archive/evidence audit | PASS | Archive SHA, three notice/evidence hashes, both parser exception texts and bounded GPL C/C++ scan |
| Other four shader archive GPL C/C++ scans | PASS | No GNU GPL notice matches in inspected C/C++ files |
| bash -n | NOT_RUN | No permitted Bash found; MSYS2 excluded |
| Actual Linux executable paths/toolchain/library build | NOT_RUN | Mocked availability and apt orchestration only |
| Real packaging/import/manifest/source-offer output | NOT_RUN | No new binary; implemented pipeline requires next CI |
| DLL runtime/GPU/playback/size and reproducibility | NOT_RUN | Requires green artifact and prescribed later checks |
| Product tests/build and accepted Part B/C reruns | NOT_RUN | No product/B1 changes |

New tests check all requested prefixed binutils, present and absent windmc,
missing required dlltool before configure, hash/exception rejection paths,
unapproved GPL source rejection and explicit SPIRV-Cross/shaderc DLL imports.
Existing 43 tests still pass. No test was skipped, loosened or waived; no failed
test run occurred. Actual Linux paths have not been measured on Windows. No GUI
operation was performed.

Evidence outside Git: evidence/VE-P1e-3c1/ci-round5 contains initial/final unit
logs, Ruff/actionlint/shfmt logs, results.json, shader-licence-audit.json,
other-shader-gpl-scan.json, static-checks.json and disk.json. No tool/source archive
was downloaded; source inspection used retained caches. Web documentation reads
were not saved as repository payload. Unit-test receipts are mocks and were
removed; they are not production manifests.

## Disk and cleanup

Decimal GB; overlapping rows are not summed. Snapshot after checks, before report
rewrite/bookkeeping. Zero access errors recorded. Logical lengths are not disk
allocation measurements.

| Area | Bytes | Decimal GB |
| --- | ---: | ---: |
| repo | 3,528,183,977 | 3.528183977 |
| package | 5,764,162 | 0.005764162 |
| evidence/VE-P1e-3c1 (includes accepted earlier work) | 45,860,194 | 0.045860194 |
| evidence/VE-P1e-3c1/ci-round5 (before disk.json itself) | 57,167 | 0.000057167 |
| scratch | 0 | 0 |
| cache, total | 8,902,796,139 | 8.902796139 |
| MSYS2 toolchain, cache/msys2 (untouched) | 856,811,931 | 0.856811931 |
| Historical source/build tree, cache/mpv-lgpl/source-build (untouched) | 36,575,903 | 0.036575903 |
| Cached review sources, cache/mpv-lgpl/ci-round1-sources (read-only reuse) | 64,181,348 | 0.064181348 |
| New Linux source/build trees and built DLL output | 0 | 0 |
| Dependency restore / new tool downloads | 0 | 0 |

| Drive free | Start bytes / GB | End snapshot bytes / GB |
| --- | ---: | ---: |
| C | 354,808,823,808 / 354.808823808 | 354,806,910,976 / 354.806910976 |
| D | 980,062,707,712 / 980.062707712 | 980,062,310,400 / 980.062310400 |

D remains above 200 GB free; cache below 40 GB; cycle evidence below 300 MB.
No initial full-directory baseline was taken; drive-wide changes are not assigned
to this task. New text edits/logs are below 0.001 GB, with no restore/download or
compiled output; attributable persistent growth is below the 1 GB limit.

Cleanup candidate: only this continuation's empty scratch/tmp, 0 bytes. Tests
removed fixtures; the initial log was moved to evidence. Remove only that verified
empty directory after recording it here. No historical evidence/cache, MSYS2,
package, media, queues or owner data was deleted; no GPG agent/dirmngr started.

## Questions for the designer

Defaults selected under 11.7: keep the separate SPIRV-Cross C API DLL and shaderc;
retain all shader notices and verified Bison exception; treat windmc as optional
and every other cross-file binary as required. No additional design decision is
needed before this CI round. Final artifact/licence and runtime review remain
required; this continuation does not replace LICENSES.md acceptance on the PC.

## Remaining / intentionally deferred

Await operator commit/push and CI round 5. Four rounds used; ten-round cap now
applies. Further compiler/linker/packaging failures cannot be excluded by static
checks. Designer should append the next failure step/logs before resuming Codex.
On success the operator downloads and checks SHA256SUMS, then Windows DLL
properties/D3D11VA/H.264/size proof, LICENSES.md update and a second successful
build comparison can proceed. No CI dispatch, artifact download, new-DLL runtime
proof, product integration, distribution approval, paid resources or Git mutation
was performed.

Cleanup result: PASS. Removed only verified empty scratch/tmp (0 bytes); scratch is empty. Nothing from this continuation remains for the owner to delete.

Final scope/whitespace check: PASS. Read-only git status lists exactly the nine changed files above; git diff --check exited 0. Git warned about future LF-to-CRLF conversion for the report, shell recipe, Python helpers and cross file; no whitespace errors were reported.
