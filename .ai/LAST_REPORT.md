# VE-P1d-3 implementation and acceptance report

- Task ID / Cycle: VE-P1d-3.
- Status: PARTIAL. Implemented changes and isolated acceptance are complete locally. The additional 5,000-record real progress cadence FAIL remains a designer question; Source CI is verified; final exact-head evidence is referenced below.
- Branch: p1d-ui-v2; Draft PR #5. Start clean fbaf4d3, origin/main efb45e3 unchanged and already an ancestor.
- Exact task saved without omission and committed in 02b128a. No owner queue/settings/media used.
- Evidence root: `C:/Users/pro/Documents/VideoEnhancer-P1d-3`; media, models, previews, packages and screenshots stay outside Git.
- Host logs use America/Los_Angeles; user-facing completion uses Asia/Tokyo. Measurement timestamps are UTC where recorded.

## Part S

| Finding | Status | Implementation and evidence |
| --- | --- | --- |
| S-C1 returned Bin identity | done | `service/deletion.py:381,471`: repeat samefile immediately before shell; journal psiNewlyCreated filesystem path; remove guard only for matching Bin file. Fake replacement and occupied replacement tests; real NTFS race restores SHA-256. |
| S-C2 process coordination | done | `deletion.py:288,323,463`: nonblocking OS home lock, PID/start time every journal append, live-owner skip, retry at next deletion/60 s. Spawned-process held deletion test. |
| S-M1 identities | done | Recorded source identity checked; mux publishes output identity. Legacy output bytes/time guard retained. Identity mismatch test. |
| S-M2 read-only attributes | done | FileDispositionInfoEx/IGNORE_READONLY removes only the guard link. No HIDDEN attribute. Fake attributes test and real read-only recycle/restore: attributes 33 before/after. |
| S-M3 latest fields/background | done | Shared per-process deletion object, latest-job owned-field patch under root lock; no removed-job recreation. Stale field/removal tests. Automatic decode/shell runs on a separate thread. |
| S-M4 prompt suppression/limits | done | Native silent/no-confirmation/no-error flags behind identity guard. Read-only volume/policy queries. Fake off/size cases make no shell call. No owner Bin settings changed. |
| S-M5 notices | done | Retained results include full guard path; matching History details/orphan Home notices offer Show in folder. Packaged screenshots exercise both. |
| Minor exception/aliases/output verification | done | RuntimeError passes through finish; unfinished hardlink alias keeps source. Five real FFmpeg CPU fixtures: pass, short count, wrong duration, missing audio, no video; nonempty reasons and mux audio tolerances. |
| NTFS acceptance | PASS | Native recycle/restore, read-only, actual replacement B race, forced-permanent fake. Four cases, zero remaining guards; original/restored SHA-256 `2be8374271de213e71a7661f42ba36842e1c44772e32c29f8f9bf00e1a6939fb`. `deletion-real/results.json`. |
| Automatic GPU success/failure | PASS | automatic-retry/auto-delete/results.json: real Fast output passes independent decode/frame/duration/audio checks. Success recycles/restores exact item; forced verification failure keeps original. Both SHA-256 values e36555e29cf375f98a552e807a1ff005ba60df289b260cb242256544dfeba76a before/after. |

Latest changed-screen test including Compare: 1 PASS / 6.7 s (.tmp/p1d3-compare-owner-visible.log). The final 12 full-window changed-state captures plus two gear-button crops are listed in G1.

Related integration: 82 PASS / 3 SKIP / 1 deselected (29.59 s); final full CPU coverage described in G. Real size/off cases use fakes rather than altering Windows settings.

## Part E

| Item | Status | Evidence |
| --- | --- | --- |
| Selection | PASS | `jobs/store.py:164`: measured exact, newest same GPU/other driver, built-in GPU, defaults. Unit order tests. Changed driver estimate identical (0% difference, within 0.1%); Settings note. |
| Unknown model | PASS | Per-file and aggregate unknown_models propagate; individual/combined Add cards suppress numeric time. Compare projection returns unknown; Home suppresses unknown time. Internal scheduler placeholder preserved; see questions. First estimates use correction 1.0 in fresh homes; normal subsequent segment correction remains unchanged and is visible in the saved segment predictions. |
| Manual calibration | PASS | No automatic calibration; wall/duration/Cancel recorded. Actual running child cancelled in 0.140477 s; exit 1, worker stopped, no profiles published. calibration-cancel/results.json. |
| Reference provenance | done | `estimate/profiles/rtx-4060-ti-8gb.json` derives from P1d-2 `calibrated-acceptance/calibration-summary.json`: independent synthetic 150-frame/5-second 720x1280 reference. No acceptance clip fitting. Numbers/model identities/GPU metadata only. Built-in data is immutable; finalization observation stays local. |

| Fresh-home 30-second job | Initial estimate s | Actual segment work s | Error % | Status |
| --- | ---: | ---: | ---: | --- |
| c1 | 370.483 | 382.529 | -3.149 | PASS: done, within +/-15% |
| scunet | 1545.512 | 1602.696 | -3.568 | PASS: done, within +/-15% |
| span | 660.941 | 699.205 | -5.473 | PASS: done, within +/-15% |
| fast | 56.674 | 59.598 | -4.907 | PASS: done, within +/-15% |
| landscape-c1 | 370.483 | 381.395 | -2.861 | PASS: done, within +/-15% |

Each uses source=builtin, no measured profiles, initial correction=1.0. First estimate is compared with the sum of actual_seconds, not wall time/finalization. Raw segment predictions, actuals and wall boundaries are retained in estimates-final/results.json.

| Calibration scope | Installed models | Wall seconds |
| --- | --- | ---: |
| Defaults only | C1, RIFE 4.25 | 110.955565 |
| Every model in isolated four-model fixture | C1, RIFE 4.25, SCUNet real PSNR, SPAN LiveAction 2x | 504.169211 |

This does not mean every archived alias/weight on the PC was calibrated. No owner model home was modified.

First failed C1 attempt is retained in estimates/results.json: estimate 370.483115 s, actual 382.448009 s, error -3.128502%, finalization FAIL after rendering because code tried to write the package built-in profile. Fixed by skipping measured-profile writes for built-in data; all five jobs reran in fresh homes.

## Part L

| Item | Status | Evidence |
| --- | --- | --- |
| Separate compact progress/structural events | done | `engine.py:647,745`, server events; measured rate extrapolation between reports. Structural wire rebuilt only on changed revisions. |
| Terminal projection/cache | done | Compact per-manifest projection, row/wire cache; full diagnostics via authenticated queue/id/json, 404 after removal. No unchanged one-second stat/deep-copy pass. |
| Background/file/health caches | done | Terminal files every 60 s/on History/after owned deletion; native Windows home notifications; schedule mtime; registry/model/profile cache 60 s. |
| Desktop throttle/memoisation | PASS (fake) | Text updates <=1 Hz and >=900 ms; stable History grouping on history_revision. Ten-repeat results below. |
| Real Fast/Standard progress | PASS (dedicated fixtures) | Standard uses 1,000 diagnostic-rich terminal rows/ten queued; each 30-second observation from real CUDA controller/SSE/renderer. Raw event/paint times retained in progress-fast and progress-standard. See extra 5,000-row FAIL below. |

| Job | Event gaps | Gap range s | Gaps in 0.9ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“2.1 s | Paint Hz | Minimum paint gap ms | Status |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| Real fast | 29 | 1.000600ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“1.015300 | 100.0% | 0.833111 | 1000.800 | PASS |
| Real standard | 28 | 1.001400ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“1.573200 | 100.0% | 0.466458 | 1005.400 | PASS |

## Part A

| Item | Status | Evidence |
| --- | --- | --- |
| Mixed PQ/HLG request | PASS | Real authenticated API tests generate actual PQ/HLG-tagged clips alongside normal SDR. Own HDR warning; normal estimate survives; HDR addition HTTP 400. |
| API/CLI enforcement | PASS | HDR, space, SAC, cleanup minimum 256 px, detected AV1 minimum checked before creation. Rule names in errors; real probe/geometry with mocked environment restrictions where appropriate. Downscale remains nonblocking. |
| Regression | PASS | tests/test_p1d3.py: 13 PASS (5.83 s), including aggregate unknown status. |

## Part P

Renderer method: fresh Electron launch per repeat, 1,000 terminal fixture records, cold History first visit separated from warm second visits. Linear interpolated quantiles. Every gated renderer run is listed, not selected by outcome. Raw per-event/per-key data remains external. All three complete ten-repeat runs PASS the specified budgets.

### renderer-perf (10 repeats)

| Metric | Every sample (repeat order) | Median | p90 |
| --- | --- | ---: | ---: |
| warm_History_ms | 47.100, 62.500, 47.500, 46.900, 63.600, 62.700, 47.100, 47.000, 62.800, 63.200 | 55.000 | 63.240 |
| warm_Schedule_ms | 42.000, 28.500, 28.300, 29.300, 28.900, 30.000, 29.700, 28.900, 28.100, 29.800 | 29.100 | 31.200 |
| warm_Models_ms | 29.900, 30.100, 29.000, 29.100, 27.700, 29.800, 29.300, 29.600, 30.000, 29.600 | 29.600 | 30.010 |
| warm_Settings_ms | 30.100, 29.800, 29.700, 29.600, 30.300, 29.600, 29.400, 29.900, 30.600, 30.100 | 29.850 | 30.330 |
| warm_Home_ms | 47.100, 46.700, 46.500, 46.600, 47.000, 46.500, 46.700, 46.800, 47.200, 46.700 | 46.700 | 47.110 |
| cold_history_open_ms | 149.300, 93.500, 149.900, 113.700, 152.500, 106.700, 113.700, 155.000, 107.700, 91.800 | 113.700 | 152.750 |
| preview_after_key_ms | 455.600, 452.200, 439.100, 461.000, 465.400, 450.300, 451.600, 444.000, 441.900, 450.900 | 451.250 | 461.440 |
| idle_renderer_one_core_percent | 0.428, 0.439, 0.444, 0.439, 0.460, 0.475, 0.445, 0.453, 0.474, 0.455 | 0.449 | 0.474 |
| progress_updates_per_second | 1.000, 1.000, 0.966, 0.967, 1.000, 1.000, 0.966, 0.966, 0.967, 0.967 | 0.967 | 1.000 |
| minimum_progress_gap_ms | 999.800, 1000.100, 999.300, 999.400, 1000.100, 1000.000, 998.600, 999.100, 998.900, 999.800 | 999.600 | 1000.100 |
| keystroke_paint_max_ms (derived from saved raw keys) | 31.400, 32.000, 32.500, 31.600, 32.000, 31.100, 35.000, 31.600, 29.400, 29.400 | 31.600 | 32.750 |

Input delay max 2.500 ms; interaction p98 168.000 ms. Maximum interaction: {"repeat": 4, "duration": 184, "event": "pointerdown", "target": "unknown"}. First run could not identify its target; the second instruments DOM event context and identifies History.

Per-repeat input/interaction summaries (all saved observations retained; gates still use global input max / interaction p98):

| Metric | All 10 samples | Median | p90 |
| --- | --- | ---: | ---: |
| input_delay_max_ms | 1.200, 2.500, 2.300, 1.400, 1.400, 1.800, 1.900, 1.400, 1.600, 1.500 | 1.550 | 2.320 |
| interaction_p98_ms | 129.600, 91.520, 129.600, 140.480, 124.480, 107.840, 140.480, 140.480, 91.520, 91.520 | 127.040 | 140.480 |
| interaction_max_ms | 168.000, 112.000, 168.000, 184.000, 168.000, 136.000, 184.000, 184.000, 112.000, 112.000 | 168.000 | 184.000 |

### renderer-perf-context (10 repeats)

| Metric | Every sample (repeat order) | Median | p90 |
| --- | --- | ---: | ---: |
| warm_History_ms | 48.200, 63.400, 62.400, 46.900, 62.900, 46.800, 63.900, 47.400, 64.000, 63.500 | 62.650 | 63.910 |
| warm_Schedule_ms | 27.100, 28.800, 28.700, 29.600, 29.500, 29.500, 30.200, 29.200, 28.700, 30.000 | 29.350 | 30.020 |
| warm_Models_ms | 30.100, 29.700, 30.600, 30.200, 29.600, 30.000, 30.000, 29.600, 30.000, 30.000 | 30.000 | 30.240 |
| warm_Settings_ms | 29.600, 29.900, 30.600, 30.300, 30.100, 29.500, 30.600, 30.600, 30.000, 30.000 | 30.050 | 30.600 |
| warm_Home_ms | 47.400, 46.900, 47.000, 46.500, 46.400, 46.600, 47.100, 46.300, 47.000, 47.200 | 46.950 | 47.220 |
| cold_history_open_ms | 123.600, 92.900, 95.600, 151.800, 95.500, 155.500, 96.200, 154.700, 91.200, 90.500 | 95.900 | 154.780 |
| preview_after_key_ms | 442.300, 447.500, 436.700, 454.100, 446.500, 453.800, 456.400, 441.400, 456.200, 438.800 | 447.000 | 456.220 |
| idle_renderer_one_core_percent | 0.442, 0.450, 0.450, 0.465, 0.446, 0.448, 0.457, 0.438, 0.458, 0.454 | 0.450 | 0.459 |
| progress_updates_per_second | 1.000, 0.999, 0.967, 0.967, 1.000, 0.967, 1.000, 0.966, 0.966, 0.966 | 0.967 | 1.000 |
| minimum_progress_gap_ms | 999.700, 999.600, 999.700, 1001.000, 1000.300, 999.200, 999.600, 1000.100, 998.600, 999.800 | 999.700 | 1000.370 |
| keystroke_paint_max_ms (derived from saved raw keys) | 33.100, 32.000, 30.500, 32.200, 32.700, 29.500, 32.600, 27.800, 29.000, 33.400 | 32.100 | 33.130 |

Input delay max 2.300 ms; interaction p98 126.880 ms. Maximum interaction: {"repeat": 6, "duration": 184, "event": "pointerdown", "target": "History"}. First run could not identify its target; the second instruments DOM event context and identifies History.

Per-repeat input/interaction summaries (all saved observations retained; gates still use global input max / interaction p98):

| Metric | All 10 samples | Median | p90 |
| --- | --- | ---: | ---: |
| input_delay_max_ms | 2.200, 2.300, 1.900, 2.100, 1.700, 1.200, 1.500, 1.200, 1.600, 1.600 | 1.650 | 2.210 |
| interaction_p98_ms | 107.840, 86.400, 91.520, 129.600, 91.520, 140.480, 91.520, 129.600, 91.520, 91.520 | 91.520 | 130.688 |
| interaction_max_ms | 136.000, 112.000, 112.000, 168.000, 112.000, 184.000, 112.000, 168.000, 112.000, 112.000 | 112.000 | 169.600 |

The keystroke summary was added after the second measurement module loaded; the table derives the median/p90 from saved raw observations without claiming another measurement. Its earlier all-key maximum <=50 ms assertion was stricter and passed.

### renderer-perf-gear (10 repeats, owner gear follow-up)

| Metric | Every sample (repeat order) | Median | p90 |
| --- | --- | ---: | ---: |
| warm_History_ms | 45.800, 63.400, 46.400, 47.300, 47.300, 47.400, 47.400, 47.800, 47.600, 47.200 | 47.350 | 49.360 |
| warm_Schedule_ms | 27.100, 29.100, 29.200, 30.500, 30.500, 30.800, 30.700, 30.200, 31.000, 31.200 | 30.500 | 31.020 |
| warm_Models_ms | 31.100, 30.100, 30.000, 30.500, 30.500, 29.000, 29.400, 29.800, 30.000, 30.200 | 30.050 | 30.560 |
| warm_Settings_ms | 30.900, 30.300, 30.500, 30.200, 30.700, 30.400, 30.500, 30.700, 30.200, 30.200 | 30.450 | 30.720 |
| warm_Home_ms | 46.900, 45.900, 46.900, 46.200, 30.800, 30.500, 30.500, 30.800, 31.000, 31.100 | 31.050 | 46.900 |
| cold_history_open_ms | 147.900, 111.900, 102.200, 95.800, 153.300, 153.200, 99.300, 158.800, 94.000, 154.900 | 129.900 | 155.290 |
| preview_after_key_ms | 464.000, 454.500, 437.400, 446.500, 447.500, 441.100, 448.800, 442.400, 452.900, 441.400 | 447.000 | 455.450 |
| idle_renderer_one_core_percent | 0.507, 0.466, 0.447, 0.419, 0.426, 0.432, 0.429, 0.427, 0.420, 0.430 | 0.429 | 0.470 |
| progress_updates_per_second | 1.000, 0.966, 0.966, 0.966, 0.967, 0.966, 0.966, 0.967, 0.966, 0.966 | 0.966 | 0.970 |
| minimum_progress_gap_ms | 1000.000, 1000.900, 1000.600, 999.500, 999.800, 999.500, 1000.000, 999.400, 1000.000, 999.800 | 999.900 | 1000.630 |
| keystroke_paint_max_ms | 32.300, 32.000, 31.200, 30.000, 31.200, 34.100, 32.300, 29.800, 32.400, 30.300 | 31.600 | 32.570 |

Global input delay max 1.700 ms; interaction p98 172.960 ms. Maximum: {"repeat": 8, "duration": 184, "event": "pointerdown", "target": "History"}. All revised budgets PASS.

| Per-repeat metric | All 10 samples | Median | p90 |
| --- | --- | ---: | ---: |
| input_delay_max_ms | 1.500, 1.200, 1.500, 1.600, 1.100, 1.300, 1.700, 1.200, 1.300, 1.200 | 1.300 | 1.610 |
| interaction_p98_ms | 129.600, 135.040, 96.960, 91.520, 135.040, 129.600, 96.960, 140.480, 96.960, 135.040 | 129.600 | 135.584 |
| interaction_max_ms | 168.000, 176.000, 120.000, 112.000, 176.000, 168.000, 120.000, 184.000, 120.000, 176.000 | 168.000 | 176.800 |

### Service CPU, every attempt

| Attempt | Three one-core CPU samples % | Median % | p90 % | Status |
| --- | --- | ---: | ---: | --- |
| service-live | 0.353, 1.411, 0.403 | 0.403 | 1.210 | 1,000-record gate PASS |
| service-live-retry | 0.353, 0.958, 1.109 | 0.958 | 1.079 | 1,000-record gate PASS |

The first attempt timed out before the initial 5,000-row snapshot and interrupted the fixture job; scaling/renderer evidence is FAIL/NOT RUN for that attempt. Cold diagnostic-only projection on that saved home took 20.462075 s. The second explicitly warmed the new projection before the steady-state scaling client: 62.987584 s initial projection, then 1.310482% one core over 31.000044 s; actual Standard still running. These cold costs are limitations, not hidden inside the <=5% gate.

Each gated sample includes all service/controller/HTTP threads; one idle client and CUDA renderer child are separate processes. Initial complete snapshot and two-second warm-up excluded. Diagnostics originate from the genuinely finished synthetic estimates-final/c1 manifest. The fixture has 1,000 terminal, ten queued and one actual Standard job. 5,000 is ungated.

### Cold full Compare totals

| Attempt/model | Total from cold admission s | Limit s | Result |
| --- | ---: | ---: | --- |
| initial / basicvsrpp-ntire21-decompress | 63.2317113999743 | 68.67 | PASS |
| initial / scunet-real-psnr | operation failed | 193.305 | FAIL |
| initial / rife-4.25 | 114.98470900001121 | 68.46 | FAIL |
| retry / scunet-real-psnr | 175.7828781999997 | 193.305 | PASS |
| retry / rife-4.25 | 63.2274682999996 | 68.46 | PASS |

Every cold run is retained. Initial SCUNet failed on progress sharing; initial RIFE was contaminated by its orphan child (114.984709 s). Fresh retries after advisory read/child cleanup fix PASS. No render math/settings were changed to satisfy these gates.

## Part G

| Check | Result | Evidence |
| --- | --- | --- |
| Ruff/format | PASS | Full repository check; 114 Python files already formatted. |
| Pyright | PASS | Windows and Linux targets, 0 errors / warnings. |
| Full CPU | PASS | 331 PASS / 3 SKIP / 30 deselected, 352.02 s, .tmp/p1d3-cpu-final2.log. Later aggregate fix: related 13 PASS. Final CI reruns the full suite. |
| D2 CPU | PASS | Included in full suite; explicit tests/test_degraded.py: 1 PASS, 1.80 s. |
| GUI lint/typecheck/unit | PASS | 37 unit tests, 5.64 s. |
| GUI build/package | PASS | .tmp/p1d3-package-gear.log; package-gear/VideoEnhancer-win32-x64/VideoEnhancer.exe. |
| Final-package e2e/clipping | PASS | 4 PASS, 1.4 min; actual CPU service/Add/completion/SSE/window lifecycle, frame viewer and clipping, Schedule tooltip, changed screens and package isolation. |
| GPU markers | PASS | 30 PASS / 336 deselected, 166.16 s; gpu-suite/pytest.log. Existing strict equivalence checks passed. |
| Windows + Ubuntu CI | PASS (implementation source) | 1595b83c714d05b47a57e48dc48f13ef4000f313: push and pull_request each have Windows/Ubuntu success, 4/4 jobs. Exact final-head evidence is referenced below. |
| Owner visual check | NOT RUN (owner task) | P1d_owner_check.md; package supplied below. |

The first broad opt-in package e2e unintentionally repeated the already accepted board inventory (the task said keep/do not redo); no new design acceptance is claimed from that repeat: 4 PASS / 3 SKIP / 1 FAIL (board 28 fixture mutated preview_ready without a structural event). Fixed the fixture to explicitly publish a snapshot, reran only board 28: 1 PASS (2.6 s). Existing 60 captures are retained, not regenerated as a new acceptance claim. GPU/resume/windows-flow opt-ins remain skipped in this CPU fixture run; required GPU markers/progress/deletion are separate.

### G1 changed-screen evidence

Only newly changed state captures are claimed (the latest Home fixture also shows an unknown-speed Up next row): isolated synthetic API visual fixtures; real HDR behavior is separately proven through the actual API. Package used: `C:/Users/pro/Documents/VideoEnhancer-P1d-3/package-gear/VideoEnhancer-win32-x64/VideoEnhancer.exe`.

- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Home-progress-retained-guard-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Home-progress-retained-guard-1100x700.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Settings-builtin-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Settings-gear-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Settings-builtin-1100x700.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Settings-gear-1100x700.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Settings-driver-note-cancel-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Settings-driver-note-cancel-1100x700.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/History-retained-guard-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/History-retained-guard-1100x700.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Add-HDR-and-unknown-speed-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Add-HDR-and-unknown-speed-1100x700.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Compare-unknown-whole-video-speed-1280x800.png`
- `C:/Users/pro/Documents/VideoEnhancer-P1d-3/gui-gear/Compare-unknown-whole-video-speed-1100x700.png`

Images reviewed for visibility at both sizes; Settings profile/note/Cancel, Add HDR/aggregate Speed unknown, Home unknown Up next and Compare unknown whole-video speed are visible. Compare fixture uses actual synthetic decoded paired footage and an isolated API unknown projection, not real restoration quality. Owner design approval is NOT RUN.

## Part X

| Item | Status | Reason |
| --- | --- | --- |
| X1 Real-ESRGAN tile 128/halo 16 | NOT RUN | Optional; the additional large-History live cadence finding remains open. No qualification/catalog change. |
| X2 120-second persistent Compare model | NOT RUN | Optional and requires a worker-lifetime design decision; existing isolated child lifetime preserved. |

## Questions for the designer

1. Unknown-speed scheduling: labels and numeric time suppression are implemented, but partition/admission still require a finite placeholder. Default: retain the existing conservative scheduler value and output pipeline, expose unknown_models, suppress displayed numeric times. Please define admission policy if an unmeasured model must alter scheduling.
2. All-installed calibration scope: measured every installed model in the isolated four-model test home, not all archived aliases on this PC. Default: do not activate or calibrate archived/unqualified weights.
3. 5,000-record startup/live progress: the ungated scaling CPU passes as recorded, but cold projection and later renderer progress have a material limitation. Default: preserve output math and report every failure; do not change architecture to hide it. Possible design responses include building structural snapshots in the background or specifying an explicit supported History size; neither is adopted in this cycle.

## Errors, warnings and deliberately unrun scope

- First C1 built-in finalization failure and first scaling-client failure are retained above.
- Real Standard renderer initial launch queried progress before queue arrival: FAIL before any timing sample. Harness now waits for .now-percent. The next 5,000-record Standard sample recorded six gaps, 0% in 0.9ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ2.1 s (3.126ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ4.290 s), paint rate 0.233308 Hz, minimum 2645.6 ms: FAIL. All evidence retained in standard-progress-retry/real-progress.json. Dedicated Fast and 1,000-history Standard checks subsequently PASS as listed; the 5,000-row additional condition remains unresolved.
- One broad edit accidentally removed estimate implementation; static checks exposed it, and the body was restored before API validation.
- Initial full CPU attempt: 2 FAIL / 327 PASS / 3 SKIP / 30 deselected. Fixed empty auto-delete background scans contending under a no-sleep mock, and updated an SSE exception injection to the new event_message boundary. Full rerun PASS above.
- Cold SCUNet first attempt FAIL at 22.828581 s: transient PermissionError reading progress.json. Fixed advisory-file retry on next poll, plus child-tree cleanup on any operation failure (the old finally forgot a live child). RIFE then took 114.984709 s with the leftover SCUNet process competing: FAIL/contaminated, retained. Both are rerun independently after the fix. Related regression: 48 PASS / 35.04 s. New cleanup regressions separately 19 PASS / 8.41 s.
- Initial automatic success recycled the correct source and independently verified output, but the private restoration helper failed to match a non-normalized BinPath in Windows PowerShell. Restored the exact item with normalized Path and pwsh; full SHA-256 e36555e29cf375f98a552e807a1ff005ba60df289b260cb242256544dfeba76a matches the journal first_sha256, which covers this entire 918259-byte file. No owner Bin entries touched. Both automatic cases subsequently reran in fresh homes and PASS as recorded.
- Expected Electron NO_COLOR/FORCE_COLOR warning and CRLF normalization notices; no missing checks inferred as success. Closed measurement clients can produce WinError 10053 connection-aborted logs.
- Physical drag/drop, network model-download/security/reboot checks and owner subjective visual quality are not newly verified. No telemetry/download/catalog/default pipeline changes.

## Reproduction

From repository root (PowerShell):
```powershell
.venv/Scripts/ruff.exe check src tests gui/tests/perf
.venv/Scripts/ruff.exe format --check src tests gui/tests/perf
.venv/Scripts/pyright.exe
.venv/Scripts/pyright.exe --pythonplatform Linux
.venv/Scripts/python.exe -m pytest -m "not gpu" --basetemp=.tmp/fresh-cpu
.venv/Scripts/python.exe -m pytest -m gpu --basetemp=.tmp/fresh-gpu
.venv/Scripts/python.exe -m pytest tests/test_degraded.py --basetemp=.tmp/fresh-d2
```
GPU suite requires fresh VE_HOME with verified weights/adapters, never the owner home.

From gui: npm run lint; npm run typecheck; npm test; npm run build; npm run package. Set external VE_GUI_PACKAGE_OUT for packaging. Set VE_GUI_PACKAGE_EXE and VE_GUI_EVIDENCE, then run test:e2e for desktop.spec.ts, packaged.spec.ts and p1d3-changed.spec.ts. Renderer: playwright test --config=playwright.perf.config.ts tests/perf/renderer.spec.ts. Real progress: VE_REAL_ENGINE_HOME points to isolated active CUDA service with serve.json, run real-progress.spec.ts using the perf config.

Service: run gui/tests/perf/prepare_service.py with fresh --root, --model-home, --history-template pointing to a finished synthetic diagnostic manifest, and --renderer. Every sample/projection time/log is stored externally. Private reproduction helpers are .tmp/p1d3-estimates-final.py, p1d3-calibration.py, p1d3-native.py, p1d3-gpu-sequence.py and p1d3-standard-extra.py; none are public media paths. Windows native recovery uses exact BinPath+free Target via p1d3-restore-native.ps1, never all Bin items.

## Changed files

- `.ai/LAST_REPORT.md`
- `.ai/CURRENT_TASK.md`
- `docs/API.md`
- `docs/GUI.md`
- `docs/TROUBLESHOOTING.md`
- `gui/src/App.tsx`
- `gui/src/HistoryDetail.tsx`
- `gui/src/Home.tsx`
- `gui/src/Pages.tsx`
- `gui/src/Queue.tsx`
- `gui/src/Trial.tsx`
- `gui/src/api.ts`
- `gui/src/types.ts`
- `gui/tests/add-models.test.tsx`
- `gui/tests/e2e/p1d3-changed.spec.ts`
- `gui/tests/e2e/visual-states.spec.ts`
- `gui/tests/perf/fake-engine.cjs`
- `gui/tests/perf/prepare_service.py`
- `gui/tests/perf/real-progress.spec.ts`
- `gui/tests/perf/renderer.spec.ts`
- `gui/tests/perf/service.py`
- `src/videoenhancer/bench/runner.py`
- `src/videoenhancer/cli.py`
- `src/videoenhancer/estimate/model.py`
- `src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json`
- `src/videoenhancer/jobs/checks.py`
- `src/videoenhancer/jobs/store.py`
- `src/videoenhancer/media/mux.py`
- `src/videoenhancer/media/probe.py`
- `src/videoenhancer/schedule/controller.py`
- `src/videoenhancer/service/compare.py`
- `src/videoenhancer/service/deletion.py`
- `src/videoenhancer/service/engine.py`
- `src/videoenhancer/service/events.py`
- `src/videoenhancer/service/server.py`
- `tests/test_deletion.py`
- `tests/test_jobs.py`
- `tests/test_p1d.py`
- `tests/test_p1d2.py`
- `tests/test_p1d3.py`
- `tests/test_reliability.py`
- `tests/test_service.py`

## Owner follow-up: Settings gear

- Owner instruction saved in CURRENT_TASK.md and committed in 0166aa4.
- Settings icon replaced with an eight-tooth vector gear and center hole; existing Settings action/accessibility name retained.
- Gear package build, lint and typecheck PASS; 37 unit tests PASS (5.64 s), packaged e2e 4 PASS (1.4 min), ten-repeat renderer PASS (5.4 min). Logs: .tmp/p1d3-package-gear.log, p1d3-unit-gear.log, p1d3-e2e-gear.log and p1d3-renderer-gear.log. Actual Settings button crops confirm the gear at both requested window sizes.
- Final owner package: C:/Users/pro/Documents/VideoEnhancer-P1d-3/package-gear/VideoEnhancer-win32-x64/VideoEnhancer.exe.

## Git and CI completion

- Task instructions committed in 02b128a; implementation in 1595b83c714d05b47a57e48dc48f13ef4000f313 (41 changed files). Branch pushed and origin head verified by ls-remote. PR #5 remains draft and mergeable; no merge performed.
- Implementation CI: [push run](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38190449013) and [pull_request run](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38190452148): completed/success, Windows and Ubuntu in each, four successful jobs. Checked UTC 2026-10-12T01:15:43.462028+00:00. Structured evidence: ci-1595b83c.json; full log .tmp/p1d3-ci-source-complete.log.
- Final evidence/report update adds the Compare unknown-speed screenshot fixture, completes every per-repeat input/interaction summary, and records verified CI. Processing implementation is identical to the validated source commit. The subsequent owner follow-up changes only the Settings navigation SVG to an eight-tooth gear in the existing 22-pixel outline style.
- Exact-head CI evidence for the final commit containing this report is recorded externally at `C:/Users/pro/Documents/VideoEnhancer-P1d-3/final-ci.json`: head_sha, checked_utc, both runs and all four job conclusions. This avoids trying to embed a commit's own hash inside a file that contributes to that hash. Match head_sha with git rev-parse HEAD.
- Final package: `C:/Users/pro/Documents/VideoEnhancer-P1d-3/package-gear/VideoEnhancer-win32-x64/VideoEnhancer.exe`. It uses this external Python engine; preserve the configured engine/FFmpeg/model paths. Owner runs P1d_owner_check.md next.
- Completion status stays PARTIAL because the additional 5,000-record real cadence failure is unresolved; optional X is NOT RUN. No subsequent implementation cycle is started.
