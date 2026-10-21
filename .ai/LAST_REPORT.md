# VE-MIG-1 — PARTIAL

Task ID / Cycle: VE-MIG-1 / Migration check run. Date: 2026-10-21. Execution host: Windows task host.

All requested checks completed on the elevated retry. Scratch cleanup was refused and the persistent-growth measurement is incomplete. No product, test, configuration or documentation file was changed. Only `.ai/LAST_REPORT.md` is intentionally changed. No Git mutation, commit, push, package replacement or GUI launch was performed.

Initial branch: `claude/project-thread-1n4s31`. HEAD: `13ecc13479823e9da85f8e9b61a357edc72bd084`. Initial working tree was clean; final read-only Git status showed only this report modified. The existing task was read completely and preserved unchanged.

## Steps 1–8

Durations are measured wall seconds unless explicitly marked unmeasured. Evidence names are relative to `work/evidence/VE-MIG-1` and remain outside Git.

| Step | Result | Duration (s) | Evidence / result |
| --- | --- | ---: | --- |
| 1. Disk at start | PASS, with timing limitation | Not recorded | disk-start.json; initial C/D free readings below; CIM failed, DriveInfo succeeded |
| 2. Restore dependencies | PASS on retry | uv wall time not recorded; npm 16.02; Cargo 150.65 | uv-sync.log, npm-ci-escalated.log, cargo-build-escalated.log, restored-inventory.json |
| 3. Python checks | PASS on retry; initial run incomplete with failures | ruff 0.44; format 0.05; pyright 8.83; CPU 727.76 | results.jsonl, ruff-check.log, ruff-format.log, pyright.log, pytest-cpu-escalated.log |
| 4. Flaky diagnostic, five runs | PASS | 23.10 / 22.94 / 22.95 / 22.86 / 22.91 | diagnostic-1.log through diagnostic-5.log; diagnostic-summary.json |
| 5. GPU smoke | PASS on retry; initial GPU coverage NOT RUN | initial 2.15; retry 51.50 | gpu-independent.log: 13 skipped; gpu-escalated.log: 13 passed, 41 deselected |
| 6. GUI and Rust | PASS | See table below | gui-*.log, cargo-fmt.log, cargo-clippy.log, cargo-test.log |
| 7. Cleanup | FAIL / PARTIAL | dependency removals 13.76 total; other wall times not recorded | cleanup.jsonl, scratch-inventory.json, owner-delete-inventory.json; scratch refused |
| 8. Disk at end / growth | PARTIAL | Not recorded | disk-end.json, drives-end.json; scratch enumeration incomplete |

Restored-size inventory: **2.329173787 GB**, excluding the retained `.venv` (**3.519404733 GB**). This is the measured post-check footprint of the six cleanup targets, not a precisely measured install delta. `uv sync --locked --all-extras` reported 58 resolved / 53 checked packages; the virtual environment already existed and no Python dependency download was reported. Restoration is the task's growth exception, and the six inventoried targets were subsequently removed.

## Checks and expected / actual

Expected: execute the supplied checks without changing their assertions or product code. Actual: all requested commands were eventually run successfully, with skipped cases and warnings explicitly retained.

| Command | Result | Seconds | Actual |
| --- | --- | ---: | --- |
| `ruff check .` | PASS | 0.44 | Exit 0 |
| `ruff format --check .` | PASS | 0.05 | Exit 0 |
| `pyright` | PASS | 8.83 | Exit 0 |
| `pytest -m "not gpu and not soak"` (elevated retry, verbose / short tracebacks) | PASS | 727.76 | 582 passed, 24 skipped, 101 deselected; 1 cache warning |
| GPU command from task, elevated retry | PASS | 51.50 | 13 passed, 41 deselected; 1 cache warning |
| `npm run lint` | PASS | 5.80 | Exit 0 |
| `npm run typecheck` | PASS | 3.71 | Exit 0 |
| `npm test` | PASS | 7.96 | 11 files / 56 tests passed |
| `npm run build` | PASS | 4.15 | Exit 0 |
| `cargo fmt --check` | PASS | 2.50 | Exit 0 |
| `cargo clippy -- -D warnings` | PASS | 67.16 | Exit 0 |
| `cargo test` | PASS | 2.92 | 20 passed |

Python executables were invoked directly from `.venv/Scripts`. Every install/build/test shell dot-sourced `repo/local-env.ps1`, then overrode `TEMP`, `TMP`, `VE_HOME` and pytest basetemp under `scratch/VE-MIG-1`. GPU model home remained `cache/gpu-home`. Rust build jobs remained two. The elevated CPU retry added the installed Git directory to that shell's PATH; it did not change user/system environment variables.

GUI operations: NOT RUN; this task requested GUI command-line checks, not an interactive application acceptance flow. No owner package was rebuilt or replaced.

### Flaky diagnostic

Each row was exercised once per run, for five runs. Failure text: none in these five diagnostic runs. This does not establish that the historical flake is fixed. The full CPU retry also passed these cases; the initial incomplete full-suite run was separate from the five diagnostics.

| Parameter: raw / outcome | Pass | Fail |
| --- | ---: | ---: |
| torn record / undo | 5 | 0 |
| torn record / expire | 5 | 0 |
| torn record / restart | 5 | 0 |
| invalid UTF-8 / undo | 5 | 0 |
| invalid UTF-8 / expire | 5 | 0 |
| invalid UTF-8 / restart | 5 | 0 |

### Initial attempts and limitations

- Initial `uv sync --locked --all-extras`: exit 0. PowerShell decorated native stderr as `NativeCommandError`; the actual exit code was successful.
- Initial sandbox `npm ci`: registry retries returned `EACCES`; interrupted rather than continuing network retries. The surrounding shell also attempted Cargo before it stopped. Its `cargo-build.log` has network failures. No wall duration was recorded for this attempt.
- Separate sandbox `cargo build --manifest-path gui/src-tauri/Cargo.toml`: could not connect to `index.crates.io:443`, with lock waiting and retries. Interrupted; no complete wall duration recorded. Elevated build passed.
- Initial sandbox CPU suite: 707 collected / 606 selected; progress reached 96%. Seven failure markers appeared (three in test_p1c4, three in test_p1f2_review, one in test_privacy_hygiene). Progress stopped, so the run was interrupted. No final summary or failure traceback was produced. Its individual failure causes and exact pass count are unknown; do not infer them from the successful retry. Evidence: pytest-cpu.log. Subsequent commands in that interrupted shell (its planned flaky/GPU loops) did not run; the independent diagnostic/GPU commands did run.
- Initial GPU command exited 0 but all 13 selected tests skipped with: `Install FFmpeg and ffprobe, then set VE_FFMPEG_DIR or add them to PATH (ffmpeg missing).` This is NOT RUN GPU coverage, not a passing smoke result. Elevated retry provided the actual passing GPU evidence.
- Both elevated pytest runs warned: `PytestCacheWarning: could not create cache path ... .pytest_cache/v/cache/nodeids: [WinError 5] Access is denied`. Test results still exited 0. No test/cache permission setting was changed.
- Final Git diff warned that LF will be replaced by CRLF the next time Git touches this report.

## Escalations

Every request below was **approved** by the automatic reviewer. There were **no automatic-review refusals**, hence no refusal text to quote. OS access failures are listed separately below. No elevated deletion was attempted.

| Elevated command(s) | Purpose / result |
| --- | --- |
| Installed `git.exe -C repo status --short`; `rev-parse HEAD`; DriveInfo C/D reads | Initial clean-tree / HEAD verification and capacity reads; approved, succeeded |
| `npm ci` in repo/gui | Locked dependency restore; approved, exit 0 |
| `cargo build --manifest-path gui/src-tauri/Cargo.toml` | Dependency restore / normal build; approved, exit 0 |
| `.venv/Scripts/pytest.exe -m "not gpu and not soak" -v --tb=short -o faulthandler_timeout=60 --basetemp <cycle>/cpu-retry` | Same CPU selection with diagnostic output; approved, exit 0 |
| `.venv/Scripts/pytest.exe tests/test_media.py tests/test_pipeline.py -m "gpu and not soak" -rs --basetemp <cycle>/gpu-retry` | GPU retry; approved, exit 0 |
| Installed `git.exe -C repo log -8 --format="%h %s" -- .ai/LAST_REPORT.md` | Verify retained historical reports; approved, succeeded |
| Installed `git.exe -C repo show ac3375d:.ai/LAST_REPORT.md`, selecting first 18 lines | Verify P1t report retention; approved, required content read; pipeline returned 1 after early output truncation |
| Same `git show`, filtering refusal / evidence records | Verify prior refused deletion targets; approved, succeeded |
| Read-only scratch size inventory; installed `git.exe -C repo status --short` and `diff --stat`; final `status --short` and `diff --check` | Owner-deletion inventory and final scope verification; approved, only report changed; inventory errors retained |

### Sandbox / environment failures

- `git -C repo status --short`, `branch --show-current`, `rev-parse HEAD`: `The term 'git' is not recognized` on the original PATH, including after dot-sourcing local-env.
- Installed Git executable invoked directly for `status --short` / `rev-parse HEAD`: `Program 'git.exe' failed to run: Access is denied`. Elevated read-only invocation succeeded.
- `Get-Command ... python`: `The term 'python' is not recognized`. The project's `.venv` executables were available and used directly.
- `Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:' OR DeviceID='D:'"`: `Access denied`, `HRESULT 0x80041003`. DriveInfo succeeded.
- `Get-PSDrive C,D`: free-space fields were empty in this sandbox.
- `npm ci`: npm's registry-fetch diagnostic log recorded `attempt 2 failed with EACCES`.
- Sandbox Cargo build: `[7] Could not connect to server (Failed to connect to index.crates.io:443 ... Could not connect to server)`.
- Sandbox GPU command: FFmpeg/ffprobe missing message quoted above; elevated tests could access them.
- `Remove-Item -LiteralPath D:\my-workspace\VideoEnhancer\work\scratch\VE-MIG-1 -Recurse -Force -ErrorAction Stop`: `Access to the path 'D:\my-workspace\VideoEnhancer\work\scratch\VE-MIG-1\cpu-retry' is denied.` No retry or workaround was attempted.

## Disk and cleanup

All GB are decimal logical file lengths unless identified as drive free space. Do not sum overlapping rows or equate logical lengths to physical allocation. Initial folder inventory had zero enumeration errors. Initial drive readings were taken shortly after dependency work started, after CIM failed; they are not a strict pre-install drive baseline.

| Item | Start GB | End GB | Qualification |
| --- | ---: | ---: | --- |
| C free | 303.803097088 | 303.657271296 | DriveInfo, not project-attributed allocation |
| D free | 1009.605779456 | 1009.160540160 | DriveInfo, not project-attributed allocation |
| work/cache | 2.302190682 | 2.302190682 | Zero enumeration errors; below 40 GB |
| work/package | 0.005771327 | 0.005771327 | Unchanged; not replaced |
| work/scratch | 0 | at least 0.459853211 | Incomplete; see owner-deletion inventory |
| work/repo | 3.528542153 | 3.528521100 | End reading preceded final report rewrite; zero enumeration errors |
| this cycle's evidence | 0.000011609 | 0.000390972 | End snapshot before final inventory/report additions; well below 300 MB |

The sandbox end scan saw only 0.179192292 GB of scratch and two access errors. A separate approved read-only elevated scan saw 0.459853211 GB and seven errors. These are different permission views, not additive totals. The complete scratch size is unknown. Persistent growth cannot be certified against the 1 GB gate because that inventory is incomplete. The visible net increase for non-overlapping cache/package/repo/current-cycle-evidence rows is approximately 0.00036 GB before the final report rewrite, excluding residual scratch. Historical evidence retention removed another 0.182309792 GB; drive-wide free-space changes are not used as removed-byte measurements.

### Cleanup inventory and independently measured removals

These exact candidates and sizes were recorded before deletion. `cleanup.jsonl` records each outcome. Each successful path was confirmed absent by the successful recursive removal; bytes are logical pre-removal file lengths, not allocation or drive deltas.

| Path relative to work | Before bytes | Result / removed bytes |
| --- | ---: | --- |
| cache/uv | 1802 | Removed / 1802 |
| cache/npm | 45036540 | Removed / 45036540 |
| cache/cargo/registry | 354980320 | Removed / 354980320 |
| cache/tauri-target | 1736693136 | Removed / 1736693136 |
| repo/gui/node_modules | 191885291 | Removed / 191885291 |
| repo/gui/dist | 576698 | Removed / 576698 |
| evidence/P1t | 182309792 | Removed / 182309792 |
| scratch/tmp | 0 | Removed / 0 |
| scratch/VE-MIG-1 | 179192292 visible before attempt | Refused; removed-byte total unknown |

`.venv`, toolchains and GPU model cache were retained. The oldest P1t evidence report is preserved in Git at `ac3375d:.ai/LAST_REPORT.md`; historical refused targets were package/scratch rather than that evidence directory. Evidence now contains P1f, P1f-2 and VE-MIG-1, satisfying three-cycle retention. No owner folders, queue, settings, media, models or Recycle Bin were inspected or cleaned.

### For the owner to delete

Deletion was refused; no elevated deletion or alternate removal method was attempted.

| Exact path | Measured logical size | Qualification |
| --- | ---: | --- |
| `D:\my-workspace\VideoEnhancer\work\scratch\VE-MIG-1` | at least 459853211 bytes | Elevated scan had seven errors; parent total incomplete |
| `D:\my-workspace\VideoEnhancer\work\scratch\VE-MIG-1\cpu-retry` | 445939934 bytes | Read-only elevated scan, zero errors; included in parent |
| `D:\my-workspace\VideoEnhancer\work\scratch\VE-MIG-1\gpu-retry` | 4532319 bytes | Read-only elevated scan, zero errors; included in parent |

Do not sum the parent and child rows. Evidence: owner-delete-inventory.json. The parent also contains sandbox-visible remnants; delete the parent after verifying it is still this cycle's temporary data. Scratch is NOT empty.

## Questions for the designer

- Can the operator remove the refused cycle scratch and remeasure growth? Default chosen: retain it, report PARTIAL, stop; no deletion bypass.
- Is pre-existing `.venv` reuse acceptable for this migration route check? Default chosen: execute the exact locked sync, report that it checked an existing environment, and do not delete/recreate it without instruction.
- How should a future migration isolate files created by elevated test runs so the sandbox can clean them? Default chosen: make no environment/security/configuration changes; report the observed permission boundary.

## Unresolved / intentionally not performed

Scratch removal and a complete persistent-growth gate remain unresolved. The initial interrupted CPU failures have no individual tracebacks and are not attributed to a proven cause. No flake fix, product change, physical GUI check, soak run, CI run, release package replacement, external media download, Git mutation, commit or push was performed. Final `git diff --check` passed; only this report was modified. A report-editing Set-Content attempt rejected its Encoding parameter; the final edit used File.WriteAllText. The task did not request those actions. The operator owns the next Git step; this cycle stops here.
