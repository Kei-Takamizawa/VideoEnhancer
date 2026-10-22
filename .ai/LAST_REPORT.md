# VE-P1f-3 implementation and verification report

- Task ID / Cycle: VE-P1f-3 / P1f-3
- Status: PARTIAL ? implementation and local verification finished. Final cleanup was blocked by automatic approval review; final-commit Windows/Ubuntu CI requires the operator.
- Start commit: `31eae7466ae0f524ac15555b72b8a5a1ac60e5c6`
- Branch: `claude/project-thread-1n4s31`
- Terminal: Windows 11 x64, PowerShell, RTX 4060 Ti, driver 617.42.
- Initial tree was clean. The complete CURRENT_TASK.md was already present and was preserved. No Git mutation, commit, push, merge or PR was performed, as required by AGENTS.md.
- Evidence paths below are relative to `work/evidence/VE-P1f-3`, except explicitly named root logs. Private evidence, media, packages and screenshots remain outside Git.

## Acceptance and before/after evidence

| Item | State | Start commit / before | Current implementation and evidence |
| --- | --- | --- | --- |
| A1 | done | The source audit guard fails on the start tree: 17 implicit text-decoding/read sites. `logs/VE-P1f-3-baseline-a1.log`. Actual Python UTF-8 mode was 0 and the subprocess default was cp1252. | All external text tool output uses UTF-8 with replacement. Own text files have explicit encodings. `test_a1_explicit_text_encodings`, Japanese tool/History/Remove/Undo and above-1080 refusal tests pass. GUI covers Japanese Add/Home/History/details/playback/Copy. `text-io-audit.json`, final CPU and GUI logs. |
| A2 | done, measurement limitations below | The owner's sample reproduces zero frames from SimpleDecoder, including an identical-byte ASCII-path copy. The streaming decoder and FFmpeg succeed. The old local preparation placeholder regression fails. | Incomplete NVDEC thumbnails trigger a per-job FFmpeg retry and recorded reason; CPU count remains strict. Unknown local dimensions/timing are null and snapshots avoid estimates on unknown data. Empty-NVDEC and preparation regressions pass. Full sample completed, 29 parts; independent output checks pass. Private sample evidence only. |
| A3 | done | Unknown-dimension 50 MB links yielded output estimates of 81.648 TB / 145.152 TB at the two selected sizes; both regression cases fail. | Queue-time check reserves download twice plus existing margin; real add_job still checks working/output space after download. Both sizes and real post-download refusal pass. |
| A4 | done for specified states | Baseline substitution of start Pages source fails the old-operation dated-text regression (`logs/VE-P1f-3-baseline-a4-a5.log`). Start-source inspection (not baseline native captures): fresh home has no saved-operation error; other-driver profile has its existing driver note without Copy. | Fresh: built-in profile text with Copy. Saved failure: dated last-attempt text, reason, Copy and Run again. Other driver: measured-profile and driver-note text with Copy. All three states pass native GUI checks in both themes. This does not identify the owner's unavailable original text. |
| A5 | done | The baseline fake-startup-status UI test finds no failure alert; original Rust ignores the startup result. | Status command/event retains the last failure, displayed beside the toggle with Copy; unchanged failure logs once. Rust injectable-writer tests and native fake-registry GUI checks pass. No real Run-key write test. |
| A6 | done; hosted cause unproven | Exact original broken-record expiry test: 0/200 failures before. Forced early timer: 200/200 failures before. Transient deletion fails before. | Exact process-isolated test: 0/200 failures after. Forced early timer: 0/200 failures after. Retries succeed after two injected errors; partial deletion losing manifest is retried from staging, including startup recovery after exhaustion. Other files remain unchanged. `history-process200.json`, `history-repeats.json`, regression tests. |
| A7 | not reproduced locally | No local reproduction of the historical hosted clipboard failure. | 50 fresh-clipboard Copy-details iterations pass. Sentinel reset prevents a stale success; real clipboard is polled with the original 5 s bound. Observed earlier targeted copy latency 67.81?86.20 ms (mean 77.83 ms). No production clipboard change attributed to A7. Final hosted-runner verification remains necessary. |
| B1 | done | Initial GUI tests fail on missing Copy/confirmation. | Shared Copy buttons wait for successful completion, then show Copied for 1.5 s and fade for 0.2 s. Rejection shows a copyable failure instead. All error/warning notices and inline reason areas are copyable. GUI timing/deferred/rejected-copy tests pass. |
| B2 | done | Initial timer/condition test fails before implementation. | Action errors remain 8 s and fade for 1 s; hover/focus holds them. Conditions and inline reasons persist. Schedule error expiry does not resubmit unchanged data. Mouse/keyboard timer tests and native fade capture pass. |
| P2 gate | done for final idle gate; loaded FAIL retained | Absolute accepted gates retained: Home-ready median <=765 ms; first-paint median <=1000 ms. | First five launches: Home 729.900 ms, first paint 732.350 ms, both PASS. `p2-five-launches.json`. Final renderer run: Home 767.543 ms (FAIL by 2.543 ms), first paint 767.462 ms (PASS). Both five-launch attempts were under concurrent GPU suite load. Final idle five launches: Home 732.481 ms and first paint 732.650 ms, both PASS (`p2-five-launches-idle.json`). Thresholds are unchanged; no claim of passing the loaded Home gate is made. |

A6's historical Windows CI failure is not established as an early-timer or file-lock failure. The deterministic injections establish weaknesses, not the historical event's cause. An initial concurrent-thread repetition harness was invalid because its same-ID logger state interfered during staging: 40/200 before and 19/200 after failed before timer expiry. Those results remain recorded in `history-real200.json`; only the replacement separate-process trials count.

## Implementation and changed files

Backend, under `src/videoenhancer`: `bench/external.py`, `bench/runner.py`, `jobs/gpu_memory.py`, `logging.py`, `media/analyze.py`, `media/decode.py`, `media/encode.py`, `media/probe.py`, `media/source_index.py`, `service/engine.py`, `service/link_jobs.py`, `service/server.py`.

GUI, under `gui/src`: `ActionButton.tsx`, `App.tsx`, `ErrorBoundary.tsx`, `HistoryDetail.tsx`, `Home.tsx`, `LinkPanel.tsx`, `Notice.tsx`, `Pages.tsx`, `Queue.tsx`, `ScheduleView.tsx`, `Storage.tsx`, `Trial.tsx`, `VideoLinks.tsx`, `desktop.ts`, `style.css`, `types.ts`. Native shell: `gui/src-tauri/src/{commands,main,window}.rs`.

Tests: `tests/test_p1f3_review.py`, `tests/p1f3_gui_seed.py`, `gui/tests/p1f3-review.test.tsx`, `gui/tests/home-schedule.test.tsx`, `gui/tests/e2e/p1f3-copy.spec.ts`, `gui/tests/e2e/p1f3-visual.spec.ts`. Existing `desktop.spec.ts` only gains useful page/size/theme assertion context, without a looser assertion. Docs: `docs/API.md`, `docs/GUI.md`, `docs/TROUBLESHOOTING.md`, `docs/DEVELOPMENT.md`, and this report.

The default processing pipeline, model defaults, frame-rate rules, quality gates, link scope and size limits are unchanged. History expiry stages readable records only after the existing removal guards, closes handlers, and retries boundedly (initial attempt plus 0.1/0.2/0.4 s retries). Early expiry re-reads the deadline and reschedules the remaining interval.

## A1 tool and file-I/O audit

Changed external-tool text call sites (current source line numbers before any later unrelated edit):

| File | Lines / calls |
| --- | --- |
| media/probe.py | 81 packet timeline; 124 raw probe; 177 probe |
| media/analyze.py | 179 FFmpeg diagnostic output |
| media/decode.py | 86 decode diagnostic |
| media/source_index.py | 54 source index probe |
| media/encode.py | 324 encoder diagnostic |
| jobs/gpu_memory.py | 67 PDH PowerShell output |
| logging.py | 87 GPU query; 103 FFmpeg version |
| service/server.py | 71 engine startup diagnostic |
| bench/runner.py | 198 external benchmark tool |

Each uses `encoding="utf-8", errors="replace"`. Existing explicit UTF-8 link-tool decoding remains. No file path is derived from probe JSON, and Python UTF-8 mode was not enabled globally.

`text-io-audit.json` inventories 111 relevant calls, including binary/archive/network calls. The AST guard covers text subprocesses, open/read_text/write_text and log handlers in application source. Binary files, ZIP/archive readers and network opener APIs are intentionally excluded from encoding requirements.

| File type | Earlier writer / current safe reader |
| --- | --- |
| Job/analysis/control/progress/cache/settings/schedule/model/storage/link-tool JSON | Writers already explicit UTF-8; readers explicit UTF-8. JSON's default ASCII escaping also protected earlier standard dumps. Invalid JSON is handled by the existing record/recovery boundaries; no silent transcoding of structured state. |
| Operation request/result JSON | Writers UTF-8, but some readers were implicit ANSI. All affected request/result/progress reads now UTF-8. |
| serve.json discovery | Writer UTF-8; old reader implicit ANSI, now UTF-8. |
| JSONL engine logs and log preferences | RotatingFileHandler already explicitly UTF-8 on the start commit; preserved. Existing log viewers use UTF-8 with replacement, retaining valid non-ASCII and tolerating invalid diagnostic bytes. |
| operation.log | Child diagnostic output can contain non-ASCII or invalid bytes; display now reads UTF-8 with replacement. |
| Benchmark download digest marker | Writer ASCII; reader now explicit UTF-8, which safely reads prior ASCII values. |
| Lock/PID/digest marker text | Explicit ASCII where the format is ASCII-only; otherwise UTF-8. |
| Native startup-errors.log | New Rust UTF-8 string writes; once per changed nonempty failure. |

No known application-owned writer in the audited start tree used an implicit ANSI text encoding. Therefore no speculative legacy-file conversion was added. Earlier tool-output decoding could fail or garble non-ASCII even though persisted JSON/log writers were already safe. Arbitrarily corrupt non-UTF-8 structured files are not silently repaired.

## A2 diagnosis and measurements

The owner's sample remains unchanged and is referred to only by that alias here. Actual codec, byte size, packet/container details and exact paths are retained only in private `owner-sample-facts-private.json`, `owner-simpledecoder-private.json`, `owner-remux-diagnosis-private.json`, `owner-container-path-control-private.json`, and `owner-output-validation-private.json`, following task section 8.

Observed cause: SimpleDecoder's indexed/scanned thumbnail path returns an empty first batch for the original container and its identical-byte ASCII-path copy; a bitstream-copy flat MP4 remux returns four frames. Timestamp verification through the streaming path and FFmpeg decoding succeed. This isolates a container-dependent SimpleDecoder failure from a filename-only explanation. The precise internal NVIDIA library defect was not determined. The fallback is per job and retains strict frame-count verification.

Full processing selected Standard, AV1, short side 1440 and 2x. All 29 parts and assembly completed. Independent ffprobe checks confirm AV1, the requested output size, packet count matching analysis and frame rate matching the existing output rule. **Selecting 2x does not activate interpolation for this input under the existing frame-rate rule.** This measurement does not demonstrate RIFE's 2x memory cost. The saved input size/mtime/edge fingerprint remained equal; that is not a full-file hash proof.

- Per-process PDH dedicated peak: **7,912,325,120 bytes (7.912 GB)**.
- Per-process PDH shared peak: **2,010,406,912 bytes (2.010 GB)**.
- 6,202 samples (non-null dedicated: 6,202; non-null shared: 6,202); observed interval median 1.000 s, maximum 1.031 s. The sampling window covers part processing and assembly, starting after add_job/analysis; analysis memory was not sampled. These are sampled per-process peaks, not Torch allocated/reserved or device-wide peaks. Separate log samples of Torch/NVML are not substituted for them.
- Predictions come from the isolated job's available default profile, not the owner's calibration/settings home. Predicted part total: **5,384.815 s**. Actual part total: **6,197.719 s**, **1.151x prediction (+15.10%)**.
- The isolated harness calls production add_job/process_segment/assemble in one process. It does not exercise production ProcessExecutor child startup per part. Part times exclude child launch and final assembly; other CPU/GUI/build verification overlapped portions of this run, so this is not an exclusive performance benchmark.
- Python completed and saved a completed record. The PowerShell wrapper reported exit 1 because its redirected native stderr (memory diagnostic text) was a NativeCommandError. Decoded UTF-16 wrapper log contains no Python traceback. Independent saved output validation passes; wrapper status is recorded separately, not labelled a clean shell exit.

| Part | Predicted s | Actual s | Actual / predicted |
| --- | --- | --- | --- |
| 1 | 182.84 | 174.23 | 0.953 |
| 2 | 182.84 | 174.21 | 0.953 |
| 3 | 182.84 | 196.79 | 1.076 |
| 4 | 182.84 | 173.91 | 0.951 |
| 5 | 182.84 | 174.46 | 0.954 |
| 6 | 182.84 | 175.85 | 0.962 |
| 7 | 182.84 | 302.96 | 1.657 |
| 8 | 182.84 | 176.41 | 0.965 |
| 9 | 182.84 | 173.75 | 0.950 |
| 10 | 182.84 | 173.60 | 0.949 |
| 11 | 182.84 | 175.66 | 0.961 |
| 12 | 182.84 | 192.87 | 1.055 |
| 13 | 182.84 | 280.72 | 1.535 |
| 14 | 182.84 | 196.62 | 1.075 |
| 15 | 182.84 | 215.55 | 1.179 |
| 16 | 182.84 | 174.44 | 0.954 |
| 17 | 182.84 | 174.49 | 0.954 |
| 18 | 182.84 | 180.86 | 0.989 |
| 19 | 182.84 | 174.13 | 0.952 |
| 20 | 182.84 | 201.33 | 1.101 |
| 21 | 182.84 | 176.11 | 0.963 |
| 22 | 182.84 | 181.43 | 0.992 |
| 23 | 182.84 | 447.13 | 2.445 |
| 24 | 182.84 | 267.31 | 1.462 |
| 25 | 182.84 | 173.89 | 0.951 |
| 26 | 182.84 | 173.40 | 0.948 |
| 27 | 182.84 | 181.69 | 0.994 |
| 28 | 182.84 | 202.01 | 1.105 |
| 29 | 265.23 | 531.90 | 2.005 |

## B2 Notice classification

All `Notice` uses have Copy and retain their existing manual dismissal behavior. "Condition" means no automatic timeout; inline reasons also persist.

| Location (`gui/src`) | Classification | Lifetime |
| --- | --- | --- |
| App.tsx:38 connection; :52 Smart App Control; :501 stalled; :512 persisted last error | Condition | Persists until recovery/manual action |
| App.tsx:524 actionError | Action | 8 s + 1 s fade |
| LinkPanel.tsx:95 conditionError / :96 error | Condition / action | Persistent fetch state / timed action |
| Pages.tsx:41 OperationStatus | Nonfailed operation status; failed action | Nonfailed status persists; failed current operation timed |
| Pages.tsx:140 and :310 model removal errors | Condition for default/in-use/queued guards; otherwise action | Guard persists; other action timed |
| Pages.tsx:223 model install failure | Action | Timed |
| Pages.tsx:416 Settings save/open error | Action | Timed |
| Queue.tsx:354 preview failure; :369 speed unknown; :379 source warning | Condition | Persists while relevant |
| Queue.tsx:394 add error | Action | Timed |
| Storage.tsx:52 conditionError / :53 error | Condition / action | Persistent fetch state / timed action |
| ScheduleView.tsx:232 save/action error | Action | Timed; fading does not trigger resubmission |
| Trial.tsx:524 and :886 compare/trial action errors | Action | Timed |
| VideoLinks.tsx:78 conditionError / :79 error | Condition / action | Persistent fetch state / timed action |
| HistoryDetail, Home, ErrorBoundary, link-card reasons, Storage remove_reason, Settings AV1/profile/driver/startup/old calibration, model-use warning | Inline condition | Persistent, with CopyMessage |
| ActionButton clipboard failure | Action | 8 s + 1 s fade, hover/focus hold; Copy message |

## Build and test results

| Check | Result | Evidence / limits |
| --- | --- | --- |
| Python Ruff / format / Pyright, final backend source | PASS | All checks passed; 121 formatted files; zero type errors/warnings |
| Final CPU suite including real-tool/TLS local fixtures | PASS | 616 passed, 3 skipped, 101 deselected; 934.45 s. `logs/VE-P1f-3-final-cpu.log` |
| Initial real-tool link bundle | PASS with TLS NOT RUN in that attempt | 71 passed, 3 TLS skips. Final CPU run enables pinned real tools and ephemeral local TLS fixture and covers these cases. |
| CPU skips | NOT RUN | Linux parent-death-only check; two private sample-clip checks requiring VE_SAMPLES_DIR. The owner's sample is not repurposed for those fixtures. |
| GUI lint / typecheck / unit / build | PASS | Final small visual-correction rerun: 64 tests in 12 files; build passes. Vite retains its over-500-kB chunk warning. |
| Rust fmt / Clippy default and e2e / unit default and e2e | PASS | 21 tests each configuration; no Rust source changed after these results. |
| Full native GUI e2e before final CSS/text correction | PASS | 20 passed, 13 existing opt-in skips, 3.9 min; no new skips. `logs/VE-P1f-3-gui-acceptance.log`. Final CSS/text renderer native three-state/two-theme rerun: 3 passed in 54.5 s (`logs/VE-P1f-3-visual-final.log`); representative final PNGs visually inspected. |
| Release-cdp packaged isolation before final correction | PASS | Existing packaged.spec: 1 passed, including a final-renderer repeat. Renderer cannot invoke desktop_test; external engine discovery and shutdown verified. |
| Feature-free final owner package | PASS | Final candidate smoke PASS in 2.313 s; visible window and authenticated isolated home. Previous candidate also passed in 3.359 s. A rerun harness initially hit an existing-home FileExistsError before launch; unique test home naming corrected it. |
| GPU `-m "gpu and not soak"` | PASS | 101 passed, 619 deselected in 15,584.86 s (4:19:44), exit 0. No skips, shortened fixtures or loosened gates. `logs/VE-P1f-3-gpu.log`. |
| P2 five launches | PASS idle; loaded Home FAIL retained | All three five-launch attempts are listed above; the final idle run follows GPU completion (0% GPU use observed before measurement). Node 1000-History fixture is prestarted; this does not measure a cold Python engine. GPU suite was concurrent; same thresholds retained. |
| Windows/Ubuntu CI on final commit | NOT RUN | Operator must commit/push; Codex cannot mutate Git under AGENTS.md. |

Environment/setup failures: default-sandbox npm ci encountered EACCES, and initial Cargo fetch was network-restricted; approved escalated executions restored the dependencies. An initial Rust regression build failed with E0425 before the new fake-writer/status helpers existed; the implemented helpers subsequently pass the unit suites. No unsafe authentication or approval bypass was used.

Earlier runs are retained, not replaced by the final totals: initial CPU 589 passed/24 skipped; later real-tool CPU 614 passed/3 skipped. An intermediate current-source CPU check exposed a broken-record-isolation regression when recognizing null placeholders too broadly; the complete null sentinel now excludes malformed width/height records and final CPU passes.

Earlier GUI e2e had 15 passed/2 failures/13 existing skips. Null cfr_fps reached job_progress and produced a global error banner/layout overflow; preparing/unknown failed snapshots now avoid that calculation. Other failed diagnostic attempts were harness errors: corrupting the only record before engine startup, an ambiguous Copy selector, an incorrect Theme exact-label selector, Cancel versus Close, and a concurrent GUI launch colliding with the app singleton. Corrected suites run serially. No assertions or timeouts were relaxed. A command used the nonexistent `release-cdp` Cargo feature; it failed before compilation and was corrected to the existing `cdp` feature.

## Native GUI verification

Playwright operates the actual Tauri/WebView2 app through the test bridge/CDP with isolated roaming/local app data. Captures are outside Git at 1280x800 in dark and light themes. Verified operations: Japanese file selection/Add/refusal, Home and History, details/playback and clipboard content; action-error Copy, Copied and fade; condition Copy; all three calibration states; fake startup failure and unchanged-error log count. Representative PNGs were also inspected directly; the first light-theme Copy background defect was corrected to existing theme colors. No manual real registry, reboot, tray hardware or owner-library checks were performed in this cycle.

## Reproduction

From `work`, dot-source `.\repo\local-env.ps1` in every test/build shell. Use isolated homes and temporary folders under scratch.

1. Python static checks: `.\repo\.venv\Scripts\python.exe -m ruff check repo/src repo/tests`; same executable `-m ruff format --check repo/src repo/tests`; run `pyright` from repo.
2. CPU: pytest `repo/tests -m "not gpu and not soak" -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp <work>/scratch/<fresh-name>`. For real tools set VE_LINK_TEST_TOOLS_HOME to the pinned recipe cache. Generate ephemeral cert/key with the retained TLS recipe, then set VE_LINK_TEST_TLS_CERT and VE_LINK_TEST_TLS_KEY; never change the certificate store.
3. GPU: same pytest command with `-m "gpu and not soak"`, isolated basetemp and VE_GPU_TEST_MODEL_HOME pointing to cache/gpu-home.
4. From repo/gui: `npm run lint`, `npm run typecheck`, `npm run test -- --run`, `npm run build`; Rust fmt/clippy/test with default and e2e features via src-tauri/Cargo.toml. Native e2e uses an e2e build, VE_GUI_TEST_ROOT/VE_GUI_EVIDENCE, then `npx playwright test`.
5. Release measurement uses `cargo build --release --features cdp --locked`, copied outside Cargo targets before feature-free rebuild. Retained `recipes/p2-five-launches.mjs` and `window-phases.py` reproduce the exact 5-launch measurement with VE_P2_OUTPUT, VE_P2_SCRATCH and VE_P2_TAURI. Do not ship this cdp-enabled test exe.
6. Build the owner exe with default features (`cargo build --release --locked`), pair engine-location.json with this checkout, then run retained isolated package smoke. Owner package must have no e2e/cdp features. Copy retained Python recipes into work/scratch before running them (their root is resolved relative to scratch). The private sample recipe uses only the approved sample copy; no owner queue/home is reused.

## Workspace and disk

Decimal GB, logical lengths rather than allocated bytes. C/D start-free queries were unavailable; no reconstructed start value is claimed. A later pre-cleanup free-space observation was C 296.414736384 GB / D 1003.393617920 GB, not the start measurement. End observation: C **301.563277312 GB**, D **1001.980694528 GB** (`end-free-space.json`). These are drive-wide observations, not bytes attributed to this cycle. Final logical inventory and blocked cleanup outcome follow below.

| Item | Start GB | Pre-cleanup GB | Final GB |
| --- | --- | --- | --- |
| repo/.venv | 3.519404733 | 3.519404733 | 3.519404733 |
| repo/gui/node_modules | 0 | 0.191885377 | 0.191885377 (cleanup blocked) |
| package, all candidates | 0.005771327 | 0.011546748 | 0.005775421 (one real package, plus empty candidate parent) |
| all evidence | 0.015247910 | 0.043688097 | 0.028760272 |
| scratch | 0 | >=4.030391309 (7 access errors) | >=3.582153461; same 7 unreadable paths, cleanup blocked |
| complete cache | 2.302192484 | 6.586073269 | 6.596187894 |

Dependency restoration is an approved separate exception: Python uv checked 53 existing packages and installed none; npm restored 194 packages, node_modules 0.191885377 GB. Cargo restored dependencies/compiled targets; current target 3.473449383 GB, Cargo cache 0.853745586 GB. These are present-size measurements, not additive growth attribution (start subfolder inventory was unavailable). Cache remains below 40 GB. Scratch inventory is incomplete where access errors occurred. Final growth is recorded below; it is not certified within budget while scratch remains.

## Questions for the designer

- Historical hosted A6/A7 causes: not established. Default: preserve original gates and await final Windows/Ubuntu CI; do not claim a hosted fix solely from local repetitions.
- Owner's original Settings error text: unavailable. Default: implement only the three specified state clarifications; ask owner to Copy any remaining message during the next owner check.
- Sample performance scope: default uses the unchanged frame-rate rule and direct production function harness; no new interpolation or queue architecture is introduced to enlarge this measurement.
- No new product or architecture decision was required.

## Package / cleanup / owner handoff

Final feature-free owner package rebuilt at `work/package/VideoEnhancer`, replaced only after its candidate passed isolated smoke. SHA-256 of VideoEnhancer.exe: `38e90b3b400a14cc95747d15b9d4042cd24542b566df00cc0123b552d4e8b848`. Hash was rechecked after replacement. Inventoried old package removed: 5,771,327 bytes. Final cleanup was requested but blocked before execution by automatic approval review. Final inventory is retained in end-disk.json; the residual list follows. The owner's sample copy remains for the owner to delete; it is excluded from cycle growth and will never be deleted by Codex.

## Intentionally not performed

No link-service expansion or third-party-site download; no above-limit processing; no real Run-key write test; no telemetry/update check, system configuration change, unsafe authentication workaround or Git mutation. Existing opt-in physical/owner checks and final-commit hosted CI are NOT RUN. CI and cleanup remain incomplete; this report does not assert overall acceptance.


### Cleanup ledger (recorded before deletion)

| Exact development path under work | Measured bytes | Outcome |
| --- | --- | --- |
| package/p1f3-replaced-old (current package before replacement) | 5771327 | REMOVED after successful final candidate smoke |
| evidence/P1f | 12831880 | REMOVED oldest cycle evidence; its final report is retained in Git commit 05dbf72 |
| repo/gui/test-results | 940420 | REMOVED ignored early harness output after preserving it in external early-harness-traces |
| repo/gui/dist | 581770 | REMOVED generated renderer output after successful native builds |


### Final cleanup candidates (inventory before deletion)

| Exact path under work | Readable bytes | Inventory errors |
| --- | --- | --- |
| scratch | 3582153461 | 7 |
| repo\gui\node_modules | 191885377 | 0 |
| repo\scripts\__pycache__ | 27896 | 0 |
| repo\tests\__pycache__ | 1687919 | 0 |
| repo\gui\tests\perf\__pycache__ | 5040 | 0 |
| repo\src\videoenhancer\__pycache__ | 60309 | 0 |
| repo\src\videoenhancer\bench\__pycache__ | 115731 | 0 |
| repo\src\videoenhancer\estimate\__pycache__ | 52772 | 0 |
| repo\src\videoenhancer\jobs\__pycache__ | 71901 | 0 |
| repo\src\videoenhancer\media\__pycache__ | 100838 | 0 |
| repo\src\videoenhancer\models\__pycache__ | 70084 | 0 |
| repo\src\videoenhancer\pipeline\__pycache__ | 96873 | 0 |
| repo\src\videoenhancer\schedule\__pycache__ | 109104 | 0 |
| repo\src\videoenhancer\service\__pycache__ | 429130 | 0 |
| .ruff_cache | 78 | 0 |
| repo\.ruff_cache | 9106 | 0 |
| repo\.pytest_cache | 0 | 1 |
| package\p1f3-candidate-d5b95bc823f94070891919927504c634 | 0 | 0 |

Scratch is one aggregate row to avoid publishing the owner sample derivative sizes. Access-denied subpaths and precise private inventory are in external final-cleanup-candidates.json; error rows are lower bounds, not complete size claims. The final batch deletion request was rejected before process creation by automatic approval review. **None of these final candidates was deleted.** No retry, narrower delete command, ACL workaround or elevated deletion was attempted.


## Final disk acceptance and cleanup outcome

- Final cycle evidence: **0.026435573 GB**, below 0.300 GB. Three cycle folders remain: P1f-2, VE-MIG-1 and VE-P1f-3. Completed root logs were consolidated into this cycle's `logs/` folder.
- Complete cache: **6.596187894 GB**, below 40 GB. Cache subrows overlap the complete-cache row and are not summed again.
- Dependency restore exception, separately quantified: Node dependencies **0.191885377 GB**; restored/rebuilt Rust target **3.483563772 GB** (absent at start); combined **3.675449149 GB**. Python restore added zero packages/bytes to the existing venv. Cargo cache is **0.853745586 GB** present size; its precise restored delta cannot be reconstructed from the initial aggregate inventory, so it is not silently subtracted.
- Known principal-root retained growth is **>=8.081550704 GB** before the restore exception; **>=4.406101555 GB** remains after excluding only the quantified Node/Rust-target restoration. That remainder still includes unallocated Cargo restoration and temporary scratch. Tracked-source and other small-cache initial sizes were not inventoried, and inaccessible contents remain unattributed. These figures are not a complete allocated-space audit.
- **Scratch-empty / growth acceptance: NOT MET.** Scratch alone retains **>=3.582153461 GB**, so the 1 GB condition cannot be certified while cleanup is blocked. The seven inaccessible subpaths have unknown sizes, not zero sizes. No owner sample size is included in the growth calculation; scratch derivatives are included as cycle artifacts.
- Successful earlier deletions, independently inventoried: **20,125,397 bytes** total (the four REMOVED rows above). Preserved trace copies are counted in evidence. Drive free-space changes are not used as deletion measurements.
- `repo/gui/dist` and `repo/gui/test-results` are absent. Their FileNotFoundError entries in end-disk.json confirm absence, not a permission error.

### Automatic approval rejection

The final recursive cleanup batch was rejected **before execution**. The reviewer identified "incomplete inventory and access errors" and "a broad irreversible cleanup scope" when deleting the entire scratch tree and other generated paths. AGENTS.md / docs/WORKSPACE.md make an automatic cleanup rejection final for this cycle. No refused target was retried through a separate command or indirect execution.

The final-candidate table above is the owner's reviewable residual list; every row remains present. node_modules and generated bytecode/cache folders therefore remain in the checkout, contrary to the desired final-cleanup state, because deletion authorization was blocked. They remain ignored and must not be staged.

## For the owner to delete

- All paths in **Final cleanup candidates**, with their recorded readable sizes. `repo/.pytest_cache` has **unknown** total size (0 readable bytes, PermissionError), rather than a confirmed empty size.
- Unreadable scratch subpaths (each size unknown):
  - `scratch/p1f3-after`
  - `scratch/p1f3-before`
  - `scratch/p1f3-history-final`
  - `scratch/p1f3-null-isolation`
  - `scratch/p1f3-partial-delete-after`
  - `scratch/p1f3-partial-delete-before`
  - `scratch/p1f3-placeholder-before`
- The owner's sample, kept unchanged and excluded from growth. Its original name/path/metadata remain outside Git.

Owner-side cleanup requires explicit approval after reviewing the residual inventory; Codex has stopped cleanup in this cycle. The remaining operator work is commit/push on the permitted branch, final Windows/Ubuntu CI, and designer review of the disclosed limits and loaded P2 failure. No extra product changes or acceptance relaxations were made.
