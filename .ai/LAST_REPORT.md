Task ID: VE-P1e-3c1 / Cycle: GitHub Actions round 2 preparation (1 of 6 CI rounds used)
Status: PARTIAL
Awaiting CI build

## Outcome

Implemented section 11.4. Unavailable exact compiler/binutils sources, including
Built-Using entries, no longer abort toolchain provenance collection. Each missing
source package/version is recorded as `unavailable in deb-src`, with an exact
Launchpad reference. Available sources are still fetched and SHA-256 checked.
The fourteen required upstream library sources and their gates are unchanged.

DLL runtime inputs are tracked separately: MinGW CRT/headers (ZPL/public domain),
winpthreads (MIT), and static libgcc/libstdc++ (GPL-3.0-or-later WITH
GCC-exception-3.1). Compiler lookup and dpkg ownership determine the exact installed
package/version for each input. Source URLs remain available even when deb-src
has dropped the version. Runtime-owner notices are included even for packages
installed transitively. This is provenance collection, not new DLL proof.

The real Linux build has NOT_RUN in this continuation. No new DLL, successful CI
artifact, performance result or distribution clearance is claimed. Part B/C remain
accepted from earlier work and were not rerun.

## Start and instructions

Read AGENTS.md, CURRENT_TASK.md in full, CLAUDE.md and docs/WORKSPACE.md.
Terminal: Windows / PowerShell. Initial read-only Git inspection:
- Branch: claude/project-thread-6lra47
- HEAD: 78a5641891b42f729000f42039d3789cd2da8eb0
- Working tree: clean

Read-only Git was run with sandbox escalation. No Git mutation, commit, push,
fetch, merge or workflow dispatch was performed. Operator owns commit/push.
CURRENT_TASK.md remains unchanged and contains the complete designer instruction.
The date in designer section 11.4 is preserved as supplied.

## Reported CI failure (not rerun locally)

Section 11.4 reports run 40167238004 failing in driver.py toolchain, with PR run
40167239065 at the same commit:

    ValueError: No authenticated source metadata for binutils=2.41.90.20240122-1ubuntu1

The installed binutils-mingw-w64-x86-64 version was
2.41.90.20240122-1ubuntu1+11.4. Its Built-Using source version was absent from the
runner's deb-src index. The former implementation treated this as fatal before
any library compilation. The new regression fixture uses those exact versions.

## Changed files

- spikes/mpv/ci-build/driver.py: optional missing toolchain source handling;
  toolchain.source_packages status records; runtime_components ownership,
  versions, licence identifiers and source URLs; transitive runtime notices.
  Source-index errors, download failures, unexpected hosts, checksum failures,
  missing runtime ownership and installed-version mismatches remain fatal.
  Captured command stderr is printed on failure for CI diagnosis.
- spikes/mpv/ci-build/test_driver.py: 13 added mocked apt/toolchain tests.
- spikes/mpv/ci-build/README.md: missing-source policy and regression boundaries.
- spikes/mpv/ci-build/DISTRIBUTION.md: distinguish optional toolchain sources from
  the LGPL library source offer; runtime licence/source-reference handling.
- .ai/LAST_REPORT.md: this round's report.

No workflow, shell recipe, cross file, source lock, product, ci.yml, existing
source-manifest.json, LICENSES.md or accepted B1 implementation changed.
No PC MSYS2 tree or executable was used or modified. Only aggregate file-size
metadata was inventoried for the required disk table.

## Validation

Dot-sourced local-env.ps1 before each test/check shell. New test directories use
mode 0755, live only under scratch/tmp and clean up their own mock files.

| Check / command | Result | Actual |
| --- | --- | --- |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | Final run: 25 tests, 0.094 s, exit 0 |
| ruff check spikes/mpv/ci-build | PASS | Final exit 0 |
| ruff format --check spikes/mpv/ci-build | PASS | Final exit 0 |
| actionlint 1.7.12 -shellcheck= .github/workflows/libmpv-lgpl.yml | PASS | Exit 0; shellcheck unavailable, not executed |
| shfmt 3.14.1 -ln bash -i 4 -d, all six shell scripts | PASS | All exit 0; scripts unchanged |
| YAML parse and workflow assertions | PASS | Exact trigger/path filters, read permissions, ubuntu-24.04, timeout <=330, no secret references |
| bash -n | NOT_RUN | No permitted Bash found; MSYS2 trees excluded |
| Real apt installation / Linux plan/toolchain/build | NOT_RUN | Only Python orchestration with mocked apt/dpkg/compiler/downloads ran locally |
| Real source archives / DLL configuration and imports | NOT_RUN | No upstream re-download or new binary in this round |
| New-DLL PC playback, five D3D11VA fixtures, H.264 timing, size | NOT_RUN | Requires green CI artifact |
| Two CI build reproducibility comparison | NOT_RUN | Requires successful runs |
| Product build/tests and Part B/C reruns | NOT_RUN | No product or B1 implementation changes |

Mocked coverage runs the real plan() and toolchain() functions, including JSON
receipt writing and hashing actual small mock download files. It verifies:
- Exact reported missing Built-Using source is recorded and skipped; other
  available source archives are fetched and hash-verified.
- Missing compiler and runtime source versions retain exact package versions,
  licence identifiers and Launchpad URLs; no newer version is substituted.
- All seven planned compiler packages are represented; five runtime input
  categories are recorded using owning packages.
- Plan pins, deterministic cache key and GITHUB_OUTPUT artifact naming.
- Missing apt candidates, installed-version mismatches, missing runtime ownership,
  source-index errors, absent SHA-256 metadata, download errors, bad source hashes
  and untrusted source hosts still fail.

First test attempt: 22 tests, 2 errors in the new mock fixture because the fake
C++ compiler handled --version as -print-file-name. Fixed the fixture's dispatch;
no production gate was disabled. Initial Ruff lint and formatting checks also
failed on the unformatted edits; formatted the helpers and reran successfully.
Final run includes three additional boundary tests (25 total). No tests were
skipped or loosened. No GUI operation was performed.

Evidence (outside Git): evidence/VE-P1e-3c1/ci-round2 contains unittest.log,
ruff.log, actionlint.log, shfmt.log, results.json and disk.json. The initial failed
attempt was observed in the tool transcript; these local log files hold final
runs. Validation tools were reused from round 1; no downloads or installations
were performed. Mock-generated toolchain.json files are test fixtures only and
were deleted; no production source-manifest.json was generated.

## Disk and cleanup

Decimal GB below; overlapping rows are not summed. Snapshot taken after checks,
before report rewrite/final bookkeeping. All inventory traversals reported zero
access errors. Directory sizes are logical file lengths, not allocated storage.

| Area | Bytes | Decimal GB |
| --- | ---: | ---: |
| repo | 3,528,019,170 | 3.528019170 |
| package | 5,764,162 | 0.005764162 |
| evidence/VE-P1e-3c1 (includes accepted earlier work) | 44,977,707 | 0.044977707 |
| evidence/VE-P1e-3c1/ci-round2 (before disk.json itself) | 11,023 | 0.000011023 |
| scratch | 0 | 0 |
| cache, total | 8,902,796,139 | 8.902796139 |
| MSYS2 toolchain, cache/msys2 (untouched) | 856,811,931 | 0.856811931 |
| Historical source/build tree, cache/mpv-lgpl/source-build (untouched) | 36,575,903 | 0.036575903 |
| Prior upstream review sources, cache/mpv-lgpl/ci-round1-sources (untouched) | 64,181,348 | 0.064181348 |
| New Linux source/build trees and built DLL output | 0 | 0 |
| Dependency restore / new tool downloads | 0 | 0 |

| Drive free space | Start bytes / GB | End snapshot bytes / GB |
| --- | ---: | ---: |
| C | 354,814,136,320 / 354.814136320 | 354,811,547,648 / 354.811547648 |
| D | 980,063,645,696 / 980.063645696 | 980,063,289,344 / 980.063289344 |

D remains above the 200 GB floor; cache is below 40 GB; cycle evidence below
300 MB. No initial full-directory baseline was taken, so exact drive-wide changes
are not attributed to this task. This round adds only small text edits/logs,
with no downloads, restores or compiled output; attributable persistent growth
is below 0.001 GB and below the 1 GB budget. Earlier cache/evidence differences
from the previous report are not claimed as this round's activity.

Cleanup candidate: only this continuation's scratch/tmp, now empty, 0 bytes.
Unit tests already removed their mock source/receipt files. Remove only this
verified empty directory after this report records it. No historical evidence,
MSYS2, package, source cache or owner data deletion was attempted.

## Questions for the designer

None requiring a new design decision. Default: use exact version-specific
Launchpad source URLs when Vcs fields are unavailable, as permitted by 11.4.
Do not treat missing optional compiler sources as missing LGPL library sources.
Runtime licence identifiers summarize the component category; full package
copyright notices remain included and need final artifact review.

## Remaining / intentionally not performed

Await operator commit/push and the next Linux CI result. One CI round has been
used; this prepares round 2, with a maximum of six total. Further actual apt,
compiler, linker or packaging incompatibilities cannot be ruled out by mocks.
On failure, the designer appends the failing step and logs before resuming Codex.
On success, the operator downloads and checks SHA256SUMS, then the prescribed PC
proof, LICENSES.md update and second-run comparison can proceed.

No CI dispatch, artifact download, production integration, paid resource usage,
new DLL performance claim, distribution approval or Git mutation was performed.

Cleanup result: PASS. Removed only the verified empty scratch/tmp (0 bytes). Scratch is empty; nothing remains for the owner to delete from this round.

Final scope/whitespace check: PASS. git status lists exactly the five changed files above; git diff --check exited 0. Git emitted LF-to-CRLF conversion warnings for the report and Python helpers, with no whitespace errors.
