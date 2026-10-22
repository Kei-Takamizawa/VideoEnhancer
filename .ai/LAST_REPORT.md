# VE-P1e-3a implementation and verification report

- Task ID / Cycle: VE-P1e-3a / P1e-3a.
- **Status: BLOCKED. This is an incomplete implementation, not a release candidate.**
- Branch: `claude/project-thread-6lra47`; unchanged HEAD: `57850df8f8e6c3c0f50a18936fc1202a4be03025`.
- Terminal: Windows x64, PowerShell. Session: 2026-10-22.
- Initial working tree was clean. Read-only Git confirmed that HEAD differs from `c84ce1a` only in CURRENT_TASK.md; the initial product-code reproductions therefore used the requested baseline product code.
- CURRENT_TASK.md was read completely and left unchanged. No Git mutation, commit, push, merge, system setting change, owner data, or owner sample use.

## Questions for the designer

1. **C3: confirm the intended 12-bit admission policy.** MIGRATION_HANDOFF.md section 3 describes the verified specification as 8/10-bit SDR input. The current implementation explicitly accepts `yuv420p12le` in `media/decode.py:validate_pixel_format`, detects depth 12 in `media/probe.py`, and has no admission check against that depth. A synthetic 12-bit HEVC source completed CPU analysis successfully: `{'bit_depth': 12, 'pixel_format': 'yuv420p12le', 'frames': 3, 'admission': 'accepted'}`. Meanwhile C3 says to retain refusal if the specification refuses 12-bit and only make the refusal reason exact. There is no current refusal reason to refine. Decide between retaining current admission and correcting conversion to p016le, or introducing the specification's 12-bit refusal. **Default chosen: neither; leave admission and conversion unchanged and stop under the AGENTS.md design-decision rule.** Analysis success is demonstrated; a complete 12-bit enhancement/export was NOT RUN.
2. **D: provide the original failure trace/error context if available.** The exact failed Windows job log was retrieved, but the run's artifacts API returned an empty list. The log proves that `DesktopApp.command` tried `page.evaluate` after the target was closed during the clipboard poll. It does not identify what closed the target. **Default chosen: report the cause as unknown, without claiming that clipboard access caused the closure.** Source: [attempt 1 Windows job](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/39737098567/job/119685243353). The relevant log excerpt is retained outside Git.

New feature implementation stopped at question 1. Closing checks found two regressions introduced by the partial startup changes; those simple mistakes were corrected and the same focused suite was rerun. No new scope was implemented after the stop.

## Item status

| Item | Status | Work and evidence |
| --- | --- | --- |
| A1 | partial | Five configurations, 30-frame parts from a synthetic 120-second 1920x1080 30-fps source. Whole-part peaks measured; complete per-stage attribution remains missing. Ten runs recorded below. |
| A2 | NOT RUN | No allocator or tensor-lifetime option tried or kept; no before/after peak claim. |
| A3 | NOT RUN | No production cap, budget reserve, or uncapped rerun implemented. |
| A4 | NOT RUN | Existing external ctypes PDH profiler exercised; production sampler, detection, watchdog, learning exclusions and spill notice unchanged. |
| A5 | NOT RUN | No capped acceptance, competing-load helper, prediction gate, or G5 run. |
| B | partial | Settings/preview JSON guards, startup job enumeration, persistent Home notice, settings-save refusal and tests. Other startup reads and full runtime recovery remain unfinished. |
| C1 | NOT RUN | Decoder-retry/OOM sequencing unchanged. |
| C2 | partial | Preserve runtime FFmpeg choice and reason during re-analysis when decoder_events exist; focused regression passes. |
| C3 | BLOCKED | Specification/admission mismatch above; no production change. |
| C4 | NOT RUN | No completed reproduction/verification. |
| C5 | NOT RUN | No completed reproduction/verification. |
| C6 | NOT RUN | No completed reproduction/verification. |
| C7 | NOT RUN | No completed reproduction/verification. |
| C8 | NOT RUN | No completed reproduction/verification. |
| C9 | NOT RUN | No completed reproduction/verification. |
| C10 | NOT RUN | No completed reproduction/verification. |
| C11 | partial | Install from the same buffered bytes hashed during download; synthetic substitution regression passes. Baseline execution of the new substitution test remains NOT RUN. |
| C12 | not reproduced | Existing install/uninstall guard already refuses active link checks; both actions tested. Active-download case still NOT RUN. |
| C13 | partial | Skip insecure separate-audio alternatives and select an eligible one; do not select separate audio for a video already carrying audio. Regression passes. |
| C14 | NOT RUN | Download crash recovery/case handling unchanged. |
| C15 | NOT RUN | Analysis cancellation/resume unchanged. |
| C16 | NOT RUN | Width reuse comparison unchanged. |
| C17 | NOT RUN | Analysis thumbnail decoding unchanged. |
| C18 | NOT RUN | Unreadable details title unchanged. |
| C19 | partial | Invalidate cached link profiles when timing-observations.json changes; corrected regression passes. Corrected baseline test NOT RUN. |
| D | partial | e2e-only copy capture implemented; real clipboard unit integration passes. Repeated spec interrupted at BLOCKED stop: Copy-details test 13/50 passes, Storage test 12/50 passes. Cause of original closure unknown. |
| P2 | NOT RUN | No five-launch measurement. |

No item marked partial satisfies the cycle's complete before/after, documentation and acceptance requirements.

## A: preliminary measurements

All GPU measurements used synthetic footage and individual scratch homes with development-model hard links. No cap was active. Clip length 15, overlap 2, HEVC output. These are 30-frame parts, not complete two-minute jobs. The first five runs used the unchanged production pipeline. Its original PowerShell sampler remained active; a separate external PDH sampler recorded process memory every second.

| Configuration | Torch allocated peak GB | Torch reserved peak GB | Process dedicated peak GB | Process shared peak GB | Part seconds |
| --- | --- | --- | --- | --- | --- |
| Standard 1080 Keep | 5.749 | 7.126 | 7.394 | 0.126 | 32.939 |
| Standard 1080 2x | 5.947 | 7.086 | 7.355 | 0.126 | 36.037 |
| Standard 1440 Keep | 5.875 | 7.147 | 7.476 | 0.146 | 32.458 |
| Standard 1440 2x | 6.198 | 7.554 | 7.816 | 0.213 | 37.928 |
| Fast 1440 2x | 2.057 | 2.863 | 3.177 | 0.146 | 7.193 |

Values are decimal GB and sampled process peaks; sampled peaks are not guaranteed continuous maxima. Raw JSON is authoritative if rounding differs. All ten processing calls completed and reported zero BasicVSR OOM retries. G5 and predictions were not compared.

A second instrumentation pass reset global Torch peaks at compute-stage boundaries and added simultaneous Torch reserve to each external PDH sample. This affects the meaning of the returned aggregate Torch peak: the v2 stats' final peak must not be interpreted as a whole-part peak. Stage entry/exit records are retained. Decode and encode windows were not separately instrumented, and overlapping workers prevent interpreting the recorded stage windows as exclusive stage allocations. Consequently A1's required complete per-stage table is **NOT AVAILABLE**.

| Additional run | Processing result | Part seconds | Maximum external direct-PDH sample cost ms |
| --- | --- | --- | --- |
| Standard 1080 Keep v2 | PASS | 32.537 | 0.734 |
| Standard 1080 2x v2 | PASS | 36.087 | 9.078 |
| Standard 1440 Keep v2 | PASS | See raw JSON | 1.003 |
| Standard 1440 2x v2 | PASS | See raw JSON | 1.291 |
| Fast 1440 2x v2 | PASS | 7.255 | 0.667 |

The last four v2 runs overlapped the CPU GUI e2e run, whose engine can probe GPU hardware. They are unsuitable as isolated GPU performance/reserve evidence and must be rerun before choosing a reserve. No reserve was chosen. The external direct query ran through ctypes PDH, not a PowerShell fallback. Its measured samples were below 50 ms; this is not a production-sampler acceptance result. The original production sampler still took about 3 seconds in the retained logs. The multi-run PowerShell wrapper returned exit 1 despite each JSON recording processing completion; do not relabel that wrapper exit as zero.

Evidence under `work/evidence/VE-P1e-3a`: `profile_baseline.py`, ten `*-baseline*.json` files, corresponding logs, and `measurement-summary.json`. Original manifest evidence filenames were reused by the second instrumentation pass; original processing stats/logs remain intact. Output media and model links were cleanup candidates, not Git content.

## B: partial recovery behavior

- `damaged_json.py` reads object-shaped JSON, records path/error once in a session registry, and logs the first detection. It never rewrites the input file.
- Damaged settings fall back to session defaults. save_settings first validates the existing file and refuses with a copyable error until it has been fixed or removed. Logger setup also tolerates damaged settings, avoiding a recursive failure while reporting them.
- Preview state/request parse errors and wrong top-level types are skipped in startup recovery.
- Startup job enumeration can skip damaged manifests/analysis, while ordinary JobStore enumeration remains strict by default. This preserves the P1f-2 broken-record contract. Storage protection/core-record verification also remain strict.
- Health publishes damaged_file_notices; Home displays one non-fading condition message with Copy containing all paths/errors.
- Tests cover truncated JSON, non-JSON and a list at top level for settings, preview state, preview request, manifest and analysis; damaged bytes are checked unchanged and a valid second record is retained.
- **Still missing:** guards/notices for every other startup JSON path, schema-field validation beyond object shape, complete runtime operation despite damaged jobs, duplicate-log audit, Home notice-specific GUI tests, and the required docs. Reads additionally identified include logging preferences, schedule.json, machine profiles, timing-observations.json, model/tool metadata and the native/Python storage pointer. These are not claimed fixed.

## Before/after evidence and checks

| Check | Result |
| --- | --- |
| Dependency restore | PASS: npm ci, 194 packages. |
| Initial settings/preview regression on baseline product code | Expected FAIL: 9 failed; `startup-before.log`. |
| First startup fix | FAIL: 1 failed, 8 passed; logger still assumed object-shaped settings; `startup-after.log`. |
| Settings/preview correction | PASS: 9 passed; `startup-after2.log`. |
| Added actual engine-start tests | Two attempts interrupted, not PASS. Fixtures initially failed to suppress the already-bound environment thread target, causing concurrent native AV1 probes; faulthandler evidence in `startup-debug.log`. Test injection was moved before Engine construction. |
| Corrected startup tests | PASS: 15 passed; `startup-after4.log`. |
| Initial minor tests | FAIL: 3 failed, 1 passed. C2/C13 reproduced; C19 was a fixture KeyError, not a valid cache reproduction; `minor-before.log`. |
| First minor implementation check | FAIL: 1 failed, 14 passed; C19 fixture still missing cfr_fps; `minor-after.log`. |
| Corrected minor/tool tests | PASS: 16 passed; `minor-after2.log`. |
| Focused Python closing suite | FAIL: 2 failed, 116 passed; introduced strict-enumeration and Storage settings validation regressions; `focused-final.log`. |
| Same focused suite after correcting regressions | PASS: 118 passed in 28.37 s; `focused-final2.log`. Includes new startup/minor/tool cases and existing jobs, Storage and P1f-2 review tests. |
| ruff check / format check | PASS: all checks passed; 155 files formatted at that check. Earlier lint attempt reported four long lines, then formatter corrected them. Final strict-enumeration correction was later; final-tree rerun NOT RUN. |
| pyright | PASS: 0 errors/warnings on the partial tree before closing strict-enumeration corrections; final-tree rerun NOT RUN. |
| Complete CPU suite | NOT RUN. |
| GPU suite / A5 / G5 | NOT RUN. Preliminary measurements are not substitute GPU-suite acceptance. |
| GUI lint / typecheck / unit / build | PASS on the modified GUI: 12 unit files, 64 tests. Build warns of a minified chunk over 500 kB. |
| Full GUI e2e | NOT RUN. |
| D repeated spec | PARTIAL/INTERRUPTED: 25 completed test executions, no reported failure before interruption. Copy details 13 passes, Storage 12 passes; remaining repetitions NOT RUN. Not retry-wrapped or skipped. |
| Rust changed? | YES: e2e copy capture and native clipboard integration test. |
| Initial Rust e2e clippy | FAIL: frontendDist missing after prior cleanup. |
| Rust e2e debug build after GUI build | PASS. |
| Rust fmt / clippy default / clippy e2e | PASS after GUI build. |
| Rust default unit | PASS: 22 tests, including real clipboard copy round trip. |
| Rust e2e-feature unit | NOT RUN. |
| P2 / package rebuild and smoke / package SHA | NOT RUN; existing package retained unchanged. |
| Final Windows/Ubuntu CI | NOT RUN; no final commit or push by Codex. |
| Read-only Git diff check | PASS; Git also warns about normal LF-to-CRLF conversion. |

The real clipboard test saves/restores prior text when available and exercises the same native copy helper used by the non-e2e build. e2e builds capture text in State through the normal copy command; their clipboard test command reads that captured text. The unreadable-record spec asserts the visible Copied flow before checking the captured details. The e2e hook is compile-time feature gated.

Environment warnings: Git and FFmpeg were initially unavailable through the sandbox environment; read-only Git and existing FFmpeg execution succeeded with reviewed escalation. The first focused Python suite could not write the repository pytest cache (WinError 5); the corrected rerun disabled that cache and passed. The later scratch deletion errors were OS Access denied results, not automatic approval-review rejections. No refused deletion was retried.

GUI operations executed: both-theme Home/History, damaged-record details and Copy, guarded record removal/Undo, local mocked link reuse/nested lists; Storage verification/removal with synthetic video playback and tray Quit. No separate visual screenshot review was completed in this cycle. Expected: the Copy path remains usable and captures Parse error details. Actual: all 13 completed iterations passed. This does not identify the original CI closure cause or satisfy the 50-run gate.

## Changed files

- `src/videoenhancer/damaged_json.py`
- `src/videoenhancer/jobs/store.py`
- `src/videoenhancer/logging.py`
- `src/videoenhancer/service/engine.py`
- `src/videoenhancer/service/settings.py`
- `src/videoenhancer/service/storage.py`
- `src/videoenhancer/service/link_tools.py`
- `src/videoenhancer/service/video_links.py`
- `gui/src/Home.tsx`, `gui/src/types.ts`
- `gui/src-tauri/src/commands.rs`, `gui/src-tauri/src/main.rs`
- `gui/tests/e2e/p1f2-review.spec.ts`
- `tests/test_p1e3a_startup.py`, `tests/test_p1e3a_minor.py`, `tests/test_link_tools.py`
- `.ai/LAST_REPORT.md`

API.md, GUI.md and TROUBLESHOOTING.md updates remain NOT RUN. Do not publish this partial behavior as complete.

## Disk and cleanup

Decimal GB; file-length inventories are logical sizes, not allocated space. Model hard links can repeat lengths across different paths. Folder rows below do not overlap.

| Measurement | GB |
| --- | --- |
| C free near start, before dependency restore/measurements | 294.829 |
| D free near start | 1005.791 |
| C free at final inventory | 294.874 |
| D free at final inventory | 1003.032 |
| Dependency restore, separate authorized exception | 0.192 (191,885,340 bytes at final inventory) |
| Current package, unchanged | 0.005775 |
| Cycle evidence at final inventory | 0.003694, below 0.300 GB; the active operator log may still grow |
| Complete cache | 6.682081, below 40 GB |
| Scratch remaining | **4.577918; NOT EMPTY** |

The first detailed folder baseline was taken after restore and initial profiling, not at the very start. Cache then measured 6.596231 GB; subsequent cache growth is 0.085850 GB. A complete start-to-end persistent-growth attribution is unavailable. The 1 GB cycle gate is **NOT established**, and retained scratch exceeds that limit in logical lengths. Do not infer allocated growth from hard-link lengths or drive free-space differences.

Before deletion, exact target sizes were recorded in final-cleanup-candidates.json. Deletion was attempted once inside the sandbox. There was no escalation/retry/workaround after denial.

| Cleanup target | Before bytes | Result |
| --- | --- | --- |
| work/scratch/VE-P1e-3a | 5,130,148,743 | Partial; 4,577,917,713 bytes remain. 552,231,030 logical bytes removed. |
| work/scratch/tmp | 9,496,969 | Files removed; denied directories remain at 0 logical bytes. |
| repo/gui/dist | 582,055 | Removed. |
| repo/gui/test-results | 0 | Removed. |

### For the owner to delete

- `work/scratch/VE-P1e-3a` — 4,577,917,713 logical bytes. Deletion stopped at `focused-final` with `[WinError 5] Access is denied`. Remaining development fixtures include hard-linked model copies and synthetic GUI fixtures. Do not treat logical bytes as additional allocated model storage.
- `work/scratch/tmp` — 0 logical bytes in remaining directories. Deletion stopped at `ve-av1-probe-ctoah85f` with `[WinError 5] Access is denied`.

No process with this cycle's isolated VE_HOME/test-home environment was found in the final process inventory. Evidence retains cleanup-inventory.json, final-cleanup-candidates.json, cleanup-results.json and final-inventory.json. No owner AppData, VE-check, Recycle Bin or owner sample was accessed or cleaned. No earlier evidence retention pruning was performed; this blocked cycle does not claim the workspace-wide retention audit complete.

## Handoff

Resolve the C3 input-policy question before continuing implementation. Supply D trace/error-context evidence if it still exists. Resume from this partial working tree; do not mark the cycle completed based on this report's existence. Full A, remaining B/C/D work, corrected before/after evidence, docs, all required gates, package and CI remain outstanding. The operator retains responsibility for Git recording and publication after review.
