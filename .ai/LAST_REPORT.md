Task ID: VE-P1e-3c1 / Cycle: GitHub Actions round 3 preparation (2 of 6 CI rounds used)
Status: PARTIAL
Awaiting CI build

## Outcome

Implemented section 11.5. Toolchain source downloads accept apt's mirror+file:
method, resolve the actual apt-reported hosts from Get: lines, validate every
reported host and retain those hosts/lines in toolchain.sources in the generated
manifest. The planned URI remains recorded separately from resolved_hosts.
Every source file must still match its SHA-256 from the authenticated source
index. No upstream library hash, licence gate or required component was relaxed.

The local mocked regression reproduces the exact reported URI and Get: line,
and the Python plan/toolchain orchestration completes with mirrored downloads.
This is not a successful Linux toolchain or library build. Actual Linux apt,
compilation, linking and artifact packaging remain NOT_RUN in this continuation.
No new DLL, successful CI artifact or runtime/performance proof exists here.

## Start and reported failure

Read AGENTS.md, CURRENT_TASK.md completely, CLAUDE.md and docs/WORKSPACE.md.
Execution terminal: Windows / PowerShell. Initial read-only Git inspection:
- Branch: claude/project-thread-6lra47
- HEAD: 36237901f8c80978314ca8954266569c512a0297
- Working tree: clean

Section 11.5 reports CI run 40182513951 on 41efdc3 and PR run 40182515731
failing in driver.py toolchain after round 1's missing-source fix worked:

    Get:2 http://azure.archive.ubuntu.com/ubuntu noble/universe binutils-mingw-w64 11.4 (dsc) [1898 B]
    ValueError: Unexpected Ubuntu source host: mirror+file:/etc/apt/apt-mirrors.txt/pool/universe/b/binutils-mingw-w64/binutils-mingw-w64_11.4.dsc

The old host check treated a mirror-method URI as an ordinary network URL.
These CI failures are designer-supplied evidence, not newly executed locally.
CURRENT_TASK.md was preserved unchanged. No Git mutation, commit, push, fetch,
merge, workflow dispatch or paid resource usage was performed. Read-only Git
inspection used sandbox escalation. Operator owns commit/push.

## Changed files

- spikes/mpv/ci-build/driver.py: parse runner mirror-list hosts and actual apt
  Get: output; retain resolved_hosts and apt_get_lines with each source receipt;
  validate all download hosts; keep SHA-256 checks strict; cache origin receipts;
  fresh download staging for old caches without origin evidence; print captured
  apt output on success and failure.
- spikes/mpv/ci-build/env.sh: export LC_ALL=C and LANG=C for stable apt fields.
- spikes/mpv/ci-build/test_driver.py: 13 additional origin/cache regression tests.
- spikes/mpv/ci-build/README.md: describe mirror resolution, cache provenance,
  locale and round 3 validation boundaries.
- .ai/LAST_REPORT.md: this report.

Allowed hosts remain archive.ubuntu.com, security.ubuntu.com and hosts ending
in .archive.ubuntu.com. The runner mirror list may add hosts only if the hostname
is ubuntu.com or ends in .ubuntu.com; deceptive suffixes are rejected. Every host
in a multi-host download is checked. resolved_hosts is the set reported by apt
for that source-package download, not a claim to observe HTTP redirects or infer
which mirror served an individual byte range.

A mirror URI with no actual Get: evidence cannot invent a host. Cached files
are rehashed against the current authenticated metadata and use previously
recorded, revalidated download origins without requiring a new Get: line. Old
cache files lacking origin receipts are downloaded once in a fresh staging
folder. A cached hash mismatch remains fatal. Missing optional toolchain source
versions still record unavailable in deb-src under the accepted 11.4 policy.

## Review of the remaining runner assumptions

Reviewed all of driver.py and prepare.sh, toolchain.sh and build.sh, plus the
cross files and pinned zlib CMake/pkg-config declarations in the existing local
source archive (read-only, no extraction/build). Findings and actions:
- Apt field/Get parsing depended on English output: fixed in shared env.sh.
- Apt cache hits do not produce download Get: lines: added recorded origin
  reuse and fresh staging for legacy cache entries; covered by tests.
- prepare.sh uses Ubuntu 24.04's ubuntu.sources to enable source indexes; both
  reported runs already passed that setup. No new evidence justified changing it.
- toolchain.sh retains exact package pins and normal apt authentication for
  cached debs. Driver still validates installed versions and runtime ownership.
- build.sh retains fresh build/prefix/source trees, target-only pkg-config,
  pinned/hash-checked sources and recorded commands. The zlib static target and
  -lz pkg-config recipe agree with the pinned source declarations.

No further confirmed runner-format defect was found by this static review.
This does not establish that Ubuntu installation or library builds will pass.
Workflow, prepare.sh, toolchain.sh, build.sh, cross files, source lock, product,
ci.yml, existing source-manifest.json, LICENSES.md and accepted Part B/C work
remain unchanged. No PC MSYS2 tree/executable was used or modified; only aggregate
size metadata was inventoried for disk reporting.

## Validation

Dot-sourced local-env.ps1 before each validation shell. Test directories are
mode 0755 under scratch/tmp and remove their mock downloads and JSON fixtures.

| Check | Result | Actual |
| --- | --- | --- |
| python -B -m unittest discover -s spikes/mpv/ci-build -v | PASS | Initial 38 tests, 0.446 s; final 38 tests, 0.408 s; exit 0 |
| ruff check spikes/mpv/ci-build | PASS | Exit 0 |
| ruff format --check spikes/mpv/ci-build | PASS | Exit 0 after formatting the two edited helpers |
| actionlint 1.7.12 -shellcheck= .github/workflows/libmpv-lgpl.yml | PASS | Exit 0; external shellcheck unavailable, not run |
| shfmt 3.14.1 -ln bash -i 4 -d, all six shell scripts | PASS | All exit 0 |
| YAML parse / independent workflow assertions | PASS | Trigger paths, read permissions, Ubuntu runner, timeout, full action SHA/version comments, no secret references, retention 30 |
| bash -n | NOT_RUN | No permitted Bash found; MSYS2 trees excluded |
| Actual Linux apt / toolchain / library build / packaging | NOT_RUN | Windows checks exercise mocked Python orchestration only |
| New-DLL import/configuration, GUI/GPU/playback and size proof | NOT_RUN | Requires green CI artifact |
| Two-run reproducibility | NOT_RUN | Requires successful CI runs |
| Product checks and Part B/C reruns | NOT_RUN | No product/B1 implementation changes; Part B/C already accepted |

New tests cover the exact pseudo-URI and Get:2 line above, real orchestration
with mocked mirrored downloads, cached origins with no new Get: output, legacy
cache refetch, corrupt cached bytes, tampered cached hosts, missing Get: evidence,
unchanged hash enforcement, direct archive/security URLs, multi-host rejection,
deceptive hostname suffixes and ubuntu.com-only mirror-list extension. Existing
25 tests also pass, including missing source versions, package pins, runtime
licences and fail-closed DLL/FFmpeg/mpv gates. No failed test run, skipped test
or waived gate occurred in this continuation. No GUI operation was performed.

Evidence outside Git: evidence/VE-P1e-3c1/ci-round3 contains initial-unittest.log,
unittest.log, ruff.log, actionlint.log, shfmt.log, results.json,
workflow-check.json and disk.json. Tools and the zlib archive were reused from
existing caches; no new downloads or dependency restores occurred. All JSON
manifests created by unit tests were mocks and removed, not production artifacts.

## Disk and cleanup

Decimal GB; overlapping rows are not summed. Snapshot after final checks, before
this report rewrite/bookkeeping. No access errors were recorded. Logical file
lengths are not allocated disk space.

| Area | Bytes | Decimal GB |
| --- | ---: | ---: |
| repo | 3,528,069,261 | 3.528069261 |
| package | 5,764,162 | 0.005764162 |
| evidence/VE-P1e-3c1 (includes accepted previous work) | 45,229,898 | 0.045229898 |
| evidence/VE-P1e-3c1/ci-round3 (before disk.json itself) | 49,672 | 0.000049672 |
| scratch | 0 | 0 |
| cache, total | 8,902,796,139 | 8.902796139 |
| MSYS2 toolchain, cache/msys2 (untouched) | 856,811,931 | 0.856811931 |
| Historical source/build tree, cache/mpv-lgpl/source-build (untouched) | 36,575,903 | 0.036575903 |
| Prior review sources, cache/mpv-lgpl/ci-round1-sources (untouched) | 64,181,348 | 0.064181348 |
| New Linux source/build trees / built DLL output | 0 | 0 |
| Dependency restore / new tool downloads | 0 | 0 |

| Drive free space | Start bytes / GB | End snapshot bytes / GB |
| --- | ---: | ---: |
| C | 354,816,970,752 / 354.816970752 | 354,815,590,400 / 354.815590400 |
| D | 980,063,313,920 / 980.063313920 | 980,062,818,304 / 980.062818304 |

D remains above 200 GB free; cache below 40 GB; cycle evidence below 300 MB.
No initial full-directory baseline was taken; drive-wide changes are not equated
with this task's growth. Attributable new text/log content is below 0.001 GB,
with no compiled output, restore or download, below the 1 GB growth limit.

Cleanup candidate: this continuation's empty scratch/tmp, 0 bytes. Unit tests
removed their own fixture files; the initial test log was moved to evidence.
Only the verified empty tmp directory will be removed after recording it here.
No historical cache/evidence, MSYS2, package, owner media or queue cleanup was
attempted. No gpg-agent or dirmngr was started.

## Questions for the designer

No new design decision is required. Default: record all apt-reported hosts for a
source-package download and retain that evidence with each file. Reuse cached
origin evidence only after rehashing the cached bytes and revalidating hosts.
Do not guess a resolved host when a mirror download emits no usable evidence.

## Remaining and intentionally deferred

Await operator commit/push and the next CI result. Two of six CI rounds have
been used; this prepares round 3. Static/mocked checks cannot guarantee the next
run reaches or completes library builds. Designer should record any next failure
step/logs before resuming Codex. A green artifact must be downloaded and checked
by the operator before Windows DLL/property/D3D11VA/H.264/size proof, LICENSES.md
update and a second CI run's reproducibility comparison.

No CI dispatch, artifact download, new-DLL runtime proof, product integration,
distribution approval, paid resources or Git mutation was performed.

Cleanup result: PASS. Removed only verified empty scratch/tmp (0 bytes); scratch is empty. Nothing from this continuation remains for the owner to delete.

Final scope/whitespace check: PASS. Read-only git status lists exactly the five changed files above; git diff --check exited 0. Git emitted LF-to-CRLF conversion warnings for the report, Python helpers and env.sh; no whitespace errors were reported.
