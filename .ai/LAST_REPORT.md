# VE-P1e - Owner fixes, clearer controls and long-video estimates

Status: PARTIAL
Date: 2026-10-13 (Asia/Tokyo)
Branch: p1d-ui-v2. Draft PR: https://github.com/Kei-Takamizawa/VideoEnhancer/pull/5
Start: 2e8eb50. Task instructions recorded in 32ae6a3. origin/main was unchanged
at efb45e3 and already an ancestor; no merge or main push was performed.

The requested UI and engine fixes are implemented. The prescribed full 10-minute
GPU job completed, but its 50% live finish forecast failed the +/-5% gate.
The subsequent correction is regression-tested; another full 10-minute gated
run after that correction is NOT RUN. This report does not declare P1e accepted.

## Part B

| Item | Status | Implementation and evidence |
| --- | --- | --- |
| B1 completion and deletion | DONE | controller.py:948 persists output identity/bytes. Legacy deletion fails closed on identity/time/duration. Real NTFS new and legacy jobs: original and output recycled through History, restored SHA-256 identical in both cases. b1-native-results.json. |
| B2 modal drop and stale result | DONE | App.tsx ignores a drop during an aria-modal dialog and shows a short notice. Detail result state dies on close. P1e e2e. |
| B2 HDR and per-file errors | DONE | Correctly tagged bt2020nc PQ/HLG reach per-file HDR warnings; valid files remain addable. Five 4K fixtures below. |
| B2 space and timeout | DONE | Chosen output geometry/fps/codec determine estimated bytes. Working space accounts for segments, joined copy and output temporary, with the existing 10% reserve: same volume 3.3x; separate volumes home 2.2x/output 1.1x. Estimate requests have no fixed client timeout and cancel on dialog disposal. Source bytes remain a heuristic, not a guaranteed output size. preflight-final: 38 PASS. |
| B2 new-home AV1 | DONE | Qualified new home chooses AV1; existing HEVC preference stays HEVC. Three isolated mocked qualification cases PASS. |
| B3 pause ordering | DONE | Store projections and plans sort by position. Paused current work remains on the main card; text explains full current-part restart using its prediction. Global pause respects ready/running state. P1e e2e and CPU contracts. |
| B4 hours | DONE | Visible positioned hours blocks; edited draft bands update immediately. Schedule e2e and screenshots. |

Final 4K run: 4k-3/results.json. Sources are synthetic, 3840x2160 at 30 fps.

| File | Expected | Actual |
| --- | --- | --- |
| H.264 8-bit SDR BT.709 | Addable | PASS, addable |
| HEVC 10-bit SDR BT.709 | Addable | PASS, addable |
| HEVC 10-bit PQ BT.2020/bt2020nc | HDR warning, blocked | PASS |
| HEVC 10-bit HLG/bt2020nc | HDR warning, blocked | PASS |
| Unspecified colour | Documented SDR fallback | PASS, addable |

The final 10-minute 4K estimate took 0.572771 s (18,000 frames, 600 s).
Earlier corrected run: 0.706554 s. The first run used an incorrectly tagged
H.264 fixture and failed that fixture's intended classification; retained in
4k/results.json. These low-bitrate synthetic files do not prove throughput on
an arbitrary high-bitrate owner file. No owner media was opened.

## Part Q

| Item | Status | Evidence |
| --- | --- | --- |
| Q1 immediate theme | DONE with protocol limit | DOM appearance applies immediately, native theme/WCO through validated IPC; persistence runs in background. Ten repeats below. Theme timing starts at select change, ends at two animation frames, and asserts nativeTheme.themeSource. Physical mouse-click timing NOT RUN. |
| Q1 cached verification | DONE | SHA-256 cache keyed by size/mtime_ns; explicit verify bypasses cache. File mutation invalidation contract PASS. |
| Q2 independent Add requests | DONE | Timing key excludes codec/folder/delete-original. Separate space check refreshes codec geometry warnings; deduplicated per-file warnings. Refresh 30 s/focus keeps existing values. E2e delete-original contract and codec switch unit regression PASS. |
| Q3 durations | DONE | Shared M:SS/H:MM:SS formatter; tabular live numeric fields. |
| Q4 progress | DONE | Byte transfer/hash callbacks, frames for previews; no extra indeterminate bar. Calibration emits six named stages and per-model/reference fractions, retains measured stage seconds, uses previous stage times or the installed-profile total as a fallback. Real isolated minimal C1/RIFE calibration PASS, 134.836681 s. All six stages captured in progress.jsonl. |
| Q5 pause all | DONE | Enabled for running/ready work or Resume all while globally paused; waiting-hours-only state disabled. |

Calibration evidence: calibration-progress-final/home/profiles and
calibration-progress-final/home/previews/*/progress.jsonl. Stage seconds:
decode/encode 19.098353, tensors 5.170037, end-to-end 8.733745,
installed models 20.292261, references 78.902074, finalization 2.580371.
These are measured on the minimal installed fixture, not every catalog model.

## Part V

| Item | Status | Evidence |
| --- | --- | --- |
| Role icons | DONE | ActionButton.tsx uses local Lucide icons; History/video/clock/document/verification shield differ. Generic ChevronRight fallback removed. Arrows remain for directional actions. Explicit model/day selection icons; glyph drag/menu/divider/selection marks replaced. Dock and Settings gear preserved. |
| Home Add label | DONE | Plus icon followed by Add videos; no literal plus in the label. Latest owner request recorded in CURRENT_TASK.md. |
| Hierarchy/hit areas | DONE, designer question | Primary 40 px/18 px icon, secondary 36 px, quiet 32 px; filled danger confirmation. Models Install follows the explicit per-card action requirement, which conflicts with at-most-one primary per screen. |
| Fit | PARTIAL | Actual Electron screenshot inventory at both sizes/themes and dialog bounds; real CPU desktop e2e exercises zoom through 150%. Full every-button text audit in every popup at 150%, physical Windows scaling and accessibility devices NOT RUN. |

New dependency: lucide-react 1.55.0, ISC, pinned in package-lock.json, bundled
locally. License: https://lucide.dev/license. No icon CDN.

## Part H

| Item | Status | Evidence |
| --- | --- | --- |
| Thumbnail cards | DONE | Justified virtual rows, entire portrait/landscape frame, soft filename/status scrim; existing date/month groups retained. |
| Select mode | DONE | Toolbar Select/Select all/count/Remove/Delete files/Cancel; whole card toggle with round marker. |
| Guarded removal and Clear | DONE | Shared choices default off; kept file keeps its record. Clear uses soft hiding and Undo. Delete-files keeps records. API counts/reasons and e2e fake deletion PASS. |
| Undo | DONE | Ten-second tint drains right edge toward left, pauses server/client on hover/focus, reduced-motion one-second steps. Undo restores records only. |
| Detail player | DONE with limit | Authenticated terminal video blob in native video element; external player fallback, Compare/actions. Full file is fetched before native playback. Large owner-file memory behaviour NOT RUN; no private media used. |

## Part M

| Item | Status | Evidence |
| --- | --- | --- |
| Compact cards/popup | DONE | Three-column 1280 px fixture, <=120 px card-height assertion; full details popup, Installed check and Install/Uninstall action. No old card menu. |
| State feedback | DONE | Determinate download percent/remaining time on card, failure details in operation; current default/unfinished job guard reason on disabled Uninstall. |
| Supported controls | DONE | DRUNet strength choices preserved; default, verify and license facts in popup. Catalog/default processing choices unchanged. |

## Part C

| Item | Status | Evidence |
| --- | --- | --- |
| Larger tiles | DONE | Available-space grid, folded model/range controls and use-model controls, full-window mode and solo pane. Measured dimensions below. |
| Zoom/pan/divider | DONE | Ctrl+wheel pointer-anchored 1x-8x, scroll pan, 1x horizontal divider; visible zoom buttons, F/Esc, double-click solo. Two-pointer logic uses captured gesture values. Synthetic wheel/pan/divider e2e PASS. Physical touchpad/touchscreen NOT RUN. |
| Steady counters | DONE | Tabular fixed 39ch counters and fixed Play/Pause width. Actual sibling movement 0 px over playback in final e2e. |

At 1280x800: portrait one-model tiles 335.25x596; portrait three-model
314x558.21875; landscape one-model 628x353.25; landscape three-model
529.77344x297.99219. At 1100x700: portrait one-model 279x496;
portrait three-model 269x478.21875; landscape one-model 538x302.625;
landscape three-model 440.88281x247.99219. Both themes measured.
Full window hides Compare controls; it does not claim to hide native window chrome.

## Part S

| Item | Status | Evidence |
| --- | --- | --- |
| Always-editable hours | DONE | Clear switch, dim saved hours when off, note and Turn on; live edited bands. |
| Overnight/equal endpoint | DONE | Previous-day carry handles equal endpoints consistently with 24-hour schedule semantics. |
| GUI validation | DONE | On/off screenshots, numeric editing while off and tooltip bounds at both sizes/zoom. |

## Part O

| Item | Status | Evidence |
| --- | --- | --- |
| First-run tour | DONE | Five one-sentence steps pointing to real controls, Skip/Done and Settings replay. Validated tour_completed flag/default/full-PUT exclusion. Synthetic UI screenshots; test fixtures explicitly skip tour when testing unrelated actions. |

## Part E

| Item | Status | Evidence |
| --- | --- | --- |
| Cost measurement | DONE with protocol limits | Synthetic portrait 720x1280 30 fps at 5/30/120 minutes, before and after data below. Before child-only entry time was not instrumented; before parent startup/IPC overhead is a separately labelled measurement. |
| Growing decoder/manifest costs | DONE | Indexed decoder disables full metadata scan on every part. Write-once analysis.json sidecar; metadata projection avoids per-frame arrays. D2 strict equality and all GPU tests PASS. |
| Real costs/local learning | DONE | Analysis, measured child/decoder startup, byte/frame finalization model with 15% safety margin, bounded local completed-job observations even for built-in profiles. Interrupted active part forecast includes lost time/full restart. |
| Live planner and recent correction | DONE, acceptance failed | Hours-aware live plan/Up next, recent same-mode correction, initial fields persisted. Failed measurement exposed instantaneous inference FPS applied to future parts; corrected to active part only, pending parts retain corrected end-to-end prediction. CPU contract PASS. |
| Owner metadata audit | DONE | Read-only copies of 34 completed manifests/optional job logs; only copies analysed, anonymised results below. No media access or owner-home writes. |
| RTX 4060 Ti full acceptance | PARTIAL | One prescribed 10-minute Standard C1 job done across a scheduled gap. First two gates PASS, live-at-half gate FAIL. Full rerun after corrective change NOT RUN. |

Before measurement uses 2e8eb50 in the external detached before-code worktree.
After uses this checkout. Timing values are individual samples, not a claimed
distribution; cache state and concurrent local verification differed. Finalization
was measured with a retained synthetic full-length passthrough segment and actual
assemble/validation, not by fully enhancing each long source.

| Minutes | Decoder open before start/middle/end (s) | Decoder open after start/middle/end (s) |
| --- | --- | --- |
| 5 | .076458/.062561/.061806 | .069514/.001401/.001386 |
| 30 | .382208/.465565/.363895 | .003077/.004247/.004267 |
| 120 | 1.456065/1.497135/1.441063 | .012138/.010798/.015032 |

| Minutes | Parent startup + IPC before start/middle/end (s) | Child entry after start/middle/end (s) | Model load before / after start/middle/end (s) |
| --- | --- | --- | --- |
| 5 | 2.311475/2.256398/2.502507 | 1.418946/1.398018/1.389255 | 1.791820/1.997078/2.656126 / 2.013706/1.710199/1.671810 |
| 30 | 2.318897/2.157413/2.327722 | 1.400187/1.405732/1.409784 | 1.645813/1.722623/1.663978 / 2.045709/1.783549/1.634740 |
| 120 | 2.660173/3.151544/2.556972 | 1.474160/1.492450/1.507922 | 1.931972/1.786778/1.607750 / 1.777024/1.912319/2.027552 |

The before/after startup columns have different endpoints; subtracting them is
not a valid isolated child-startup speedup claim.

| Minutes | Manifest before/after bytes | Before full-load median / after metadata-load median (s) | Before save / after load+save (s) | Analysis before/after (s) | Finalization before/after (s) |
| --- | --- | --- | --- | --- | --- |
| 5 | 726663/2081 | .004354/.000476 | .042786/.016479 | 9.413065/9.764158 | .772707/.799305 |
| 30 | 4498737/2088 | .030276/.000630 | .185249/.048295 | 55.670349/56.535226 | 9.998753/13.348006 |
| 120 | 18424742/2093 | .128026/.000711 | .712583/.158643 | 227.710138/224.799098 | 77.988126/102.180633 |

Arrays remain in the sidecar; full hydration still scales with frame count.
The after save column includes a preceding full sidecar load and is conservative.
Finalization output bytes are identical before/after: 272143014, 1632853810,
6531438078. No finalization speed improvement is claimed.
Raw files: baseline.json, before-additional/result.json, after-measurements.json,
after-analysis.json and after-finalization/result.json.

Owner-copy aggregates (actual segment time / reconstructed first estimate):

| Length bucket | Mode | Jobs | Median ratio | Analysis total (s) | Wasted total (s) |
| --- | --- | --- | --- | --- | --- |
| <1 min | Standard | 22 | .782573 | 20.999589 | 134.544867 |
| <1 min | Fast | 5 | .529884 | 3.981607 | 0 |
| <1 min | p0-test | 6 | .723474 | 4.435478 | 0 |
| 1-10 min | Any | 0 | Not available | Not available | Not available |
| 10-60 min | Standard | 1 | 1.960963 | 19.988328 | 0 |
| >60 min | Any | 0 | Not available | Not available | Not available |

The one longer Standard job contains 70 parts, actual segment sum 24789.684734 s,
median part 352.420951 s, source duration 658.024 s and 2160 short-side output.
This supports an underprediction on that configuration; one job is not an accuracy
distribution or proof across lengths. Old first estimates are reconstructed,
not previously stored exact UI values. Full per-job anonymised segment/observation,
analysis/waste/wait/finalization comparison: owner-analysis-anonymized.json.
Scheduler wait events in old and test records are throttled samples, not a complete
wait-time total. Missing finalization observations are labelled missing, not zero.

Full gate: gate-10min-2/result.json and gates.json. Standard C1, CUDA, 1080p60
HEVC, RTX 4060 Ti 8 GB, synthetic 600 s source, 42 parts, no calibrated profile
copied into this isolated home. Test hours had a 15-minute off gap. Actual
analysis 19.088339 s, segment sum 7603.891040 s, finalization 19.088490 s;
total processing 7642.067869 s. No aborted/wasted part time.

| Gate | Predicted/actual | Error | Limit | Result |
| --- | --- | --- | --- | --- |
| Initial processing | 7436.687301 / 7642.067869 s | -2.687500% | +/-10% | PASS |
| Initial finish, gaps included | 236.371878 s early; actual add-to-done 8759.963468 s | -2.698320% | +/-10% | PASS |
| Half-progress live finish | 662.271807 s early; remaining observed elapsed 3832.781000 s | -17.279146% | +/-5% | FAIL |

Half was first sampled at 50.00556%. Remaining elapsed includes the polling tail
(<=2 s); this cannot explain a 662 s miss. Initial finalization itself predicted
4.225926 s versus 19.088490 s actual. The 90.002202 s sum of throttled wait
events is not the full scheduled-gap duration. The controller completed without
changing default pixel output. The failed full gate remains evidence after the
active-only live-FPS correction; a second full gate is NOT RUN.

## Part G and validation

| Item | Status | Evidence |
| --- | --- | --- |
| G1 screenshots | PASS with stated fit limits | visual-final-3/inventory.json: 80 actual capturePage PNGs +16 dimension records, both themes and sizes; side-by-side/comparison.html contains unchanged P1d-3 before and final P1e after screens. Synthetic UI fixtures, no image editing. |
| G2 e2e regressions | PASS | Required ten behaviours grouped in four CI tests. Full local e2e: 7 PASS, 6 opt-in SKIP. Final changed-screen run: 5 PASS (includes visual inventory). Final packaged/regression run below. |
| G3 timing | PASS final repeat | Ten fresh cold launches, all original renderer budget assertions and three themes; full data and prior failures retained below. |
| G4 native B1/4K/long | PARTIAL | Native recycling and 4K PASS; E live finish gate FAIL. |
| G5 GPU/D2 | PASS | All GPU tests 30 PASS, 349 deselected, 165.26 s. Independent D2 strict decode equality 12 PASS, 14 deselected, 100.63 s. Output-producing pipeline was not changed after these runs. |
| G6 local checks | PASS | ruff, format, pyright; full CPU 347 PASS, 3 SKIP, 30 deselected (439.39 s) before the last small preflight additions; final affected preflight subset 38 PASS. GUI lint/typecheck, 38 unit PASS, build, package, e2e and packaged smoke. Final implementation CI executed the full CPU suite on both operating systems. |
| G6 CI | PASS on final implementation commit b89e278 | Windows/Ubuntu push and PR checks: 4/4 green. Runs 38358814562 and 38358819486. Exact report-only final-head verification is retained externally in final-head-ci.json. |

GPU evidence: gpu-suite/pytest.log; D2 and local logs in logs/. Final package:
C:\Users\pro\Documents\VideoEnhancer-P1e\package-owner\VideoEnhancer-win32-x64\VideoEnhancer.exe
Unsigned development folder; it requires this external engine checkout and Python.
Do not distribute the EXE alone. Owner execution with real queue/settings is NOT RUN.

Renderer results, final ten-run batch: renderer-perf-4/renderer-perf.json.

| Measurement | Median | p90 |
| --- | --- | --- |
| warm_History_ms | 71.500 | 80.460 |
| warm_Schedule_ms | 29.550 | 30.410 |
| warm_Models_ms | 30.250 | 30.510 |
| warm_Settings_ms | 30.600 | 30.710 |
| warm_Home_ms | 47.100 | 47.510 |
| cold_history_open_ms | 137.850 | 158.600 |
| preview_after_key_ms | 448.100 | 450.840 |
| idle_renderer_one_core_percent | 0.519 | 0.530 |
| progress_updates_per_second | 1.000 | 1.000 |
| minimum_progress_gap_ms | 999.850 | 1000.370 |
| keystroke_paint_max_ms | 31.300 | 32.910 |
| theme_light_ms | 38.550 | 39.110 |
| theme_dark_ms | 27.150 | 27.330 |
| theme_system_ms | 27.800 | 28.110 |

Input delay maximum 1.8 ms (<=50). Interaction p98 152 ms (<=200); maximum
individual interaction 216 ms, so this is not an every-interaction <=200 claim.
Theme timing uses the select change event and two animation frames, not a physical
mouse click. Warm screens <=100 ms, cold History <=300, key-to-preview <=500,
key paint <=50, idle renderer <=2% one-core, positive cadence <=1 Hz; all PASS.
The cadence assertion permits >=900 ms per interval, as in the original harness;
the observed minimum is reported in the raw file. Real GPU-to-renderer cadence
and repeated service CPU/5,000-record measurements this cycle are NOT RUN.

Every gated renderer attempt is retained:
- renderer-perf-1: failed native-label locator before a complete batch.
- renderer-perf-2: 10 repeats, FAIL interaction p98 203.36 ms >200; theme medians
  Light 38.15, Dark 27.05, System 27.55 ms PASS. Invalid JSON-thumbnail blobs were
  then rejected before creating image URLs.
- renderer-perf-3: interrupted after 3 reported repeats by Schedule locator failure
  during overlapping GUI automation; one observed gap 174.7 ms. Not a valid complete
  ten-run batch and not omitted from evidence.
- renderer-perf-4: 10 repeats, PASS. GUI automation was serialized; no long GPU or
  full CPU benchmark ran during this batch. Small targeted contracts did run.

## Errors, failed attempts and limitations

Raw logs in the external logs/ directory include every p1e-* attempt, not just
the favourable run. Significant retained failures and their correction:
- First pytest temp location: 4 PASS, 1 SKIP, 53 errors (permissions); isolated
  external basetemp run: 57 PASS, 1 SKIP.
- First full CPU: 10 FAIL, 334 PASS, 3 SKIP, 30 deselected. Mock assemblers did not
  create output; Clear tests assumed immediate removal; timer mocks and forecast
  build count were stale; cancel cleanup genuinely deleted the sidecar. Fixtures
  and contracts updated, cleanup preserved analysis.json. Later full CPU: 346
  PASS, then 347 PASS; final-head CI executes the final suite.
- Initial GUI unit suite: 7 FAIL/30 PASS, then 3 FAIL/34 PASS. Old menus/labels
  updated to the supplied UI contract. Last space-warning change exposed duplicate
  warnings: 3 FAIL/35 PASS; deduplication fixed this. Final: 38 PASS.
- P1e e2e attempts: first 4 FAIL (wrong Electron cwd), then 2 PASS/2 FAIL,
  3 PASS/1 FAIL and 3 PASS/1 FAIL (fixture readiness/divider timing); fifth 4 PASS.
  Final full run first: 2 FAIL/5 PASS/6 SKIP (stale History selector and real 9 px
  Play/Pause width movement). Fixed selector and button width; full rerun 7 PASS,
  6 SKIP. Latest changed-screen run 5 PASS.
- Visual attempts: initial unsupported dynamic import; portrait-height gates
  460/458 px failed; after control compaction passed. Inspection caught stretched
  model cards, and 124 px failed the 120 px gate. Final card layout and inventory
  PASS. All attempts retained in logs/ and visual-* folders.
- First after-position benchmark used output outside job_dir, FAILED; corrected
  isolated job_dir output completed all nine positions. A stray one-byte lock
  remains at C:\Users\pro\Documents\jobs\synthetic-5\manifest.lock. Automatic
  approval review rejected its verified-path cleanup with the generic reason
  "blocked by policy". No bypass or deletion was attempted after rejection.
- gate-10min first failed before queueing because its schedule was not on 15-minute
  boundaries. gate-10min-2 completed but failed the half-progress accuracy gate.
- Newly added contracts initially had stale finalization expectations, a non-15-minute
  schedule and incomplete mocked AV1 limits. Corrected test assumptions; final
  affected preflight contracts PASS. No product schedule rule was changed.
- Initial package command used a wrong npm path and did not run packaging; corrected
  package runs completed. Final executable path above. Vite warns about a minified
  chunk >500 kB; this is retained, not suppressed. Npm dependency install reported
  no vulnerabilities at installation time; this is not a lasting security guarantee.

## Questions for the designer

1. E acceptance is not achieved: -17.279146% at half progress. The obvious runtime
   calculation error has been corrected without changing output. Default chosen:
   keep the failed gate, mark PARTIAL, do not claim a full corrected-run PASS.
2. Part V says one primary per screen while Part M explicitly asks Install on each
   card. Default chosen: retain the explicit per-card Install action; no independent
   redesign of card navigation or install policy.
3. History native player fetches the entire authenticated file first. Default chosen:
   retain the prescribed native player and external fallback; no unapproved streaming
   architecture or arbitrary file-size cutoff. Long-owner-file memory validation NOT RUN.
4. Sparse historical long-job evidence, especially 2160 output, cannot establish an
   accuracy bound across geometry/length. Default chosen: bounded same-mode local
   correction as requested; no new catalog or independently chosen calibration policy.
5. Physical touch/Windows scaling/full every-button 150% audit and literal human-click
   theme measurement are not established by synthetic events. Default chosen: report
   those limits explicitly; leave owner acceptance to the next checklist.

## Reproduction and logs

Evidence root: C:\Users\pro\Documents\VideoEnhancer-P1e
All private footage, model copies, package, logs, before-code checkout and screenshots
are external. Public report contains no owner file names, titles, paths or job IDs.

Run from repository root unless noted. Use a NEW external folder/VE_HOME each time.
1. .venv/Scripts/ruff.exe check .
2. .venv/Scripts/ruff.exe format --check .
3. .venv/Scripts/pyright.exe
4. .venv/Scripts/python.exe -m pytest -m "not gpu and not soak" -q --basetemp=C:/private/new-cpu
5. .venv/Scripts/python.exe -m pytest -m gpu -q --basetemp=C:/private/new-gpu
   with isolated VE_HOME containing verified test-only C1/RIFE and adapter sources.
6. In gui: npm run lint; npm run typecheck; npm test; npm run build; npm run test:e2e.
7. Set VE_P1E_VISUAL_EVIDENCE to a NEW external folder, then in gui run
   node node_modules/@playwright/test/cli.js test tests/e2e/p1e-visual.spec.ts.
8. Set VE_GUI_EVIDENCE to a NEW external folder, then in gui run
   node node_modules/@playwright/test/cli.js test tests/perf/renderer.spec.ts --config=playwright.perf.config.ts.
9. Set VE_GUI_PACKAGE_OUT to a separate external output and run npm run package in gui.
   Set VE_GUI_PACKAGE_EXE to its EXE and run tests/e2e/packaged.spec.ts.
10. External reproduce/ retains exact p1e-*.py scripts and logs/ every execution log.
    Adapt their hardcoded external output paths to NEW folders before rerunning.
    p1e-before-final.py under PYTHONPATH=before-code/src reproduces old startup and
    assemble samples; without that override it measures new assemble samples.
    p1e-analysis-after.py, p1e-4k-final.py, p1e-cal-final.py reproduce their named data.
    p1e-gate.py reproduces the long isolated job with actual current-time hours and
    polling, and p1e-gate-summary.py computes accuracy from recorded timestamps.
    p1e-gpu-gap.py includes real Recycle Bin/restore tests for its own synthetic paths;
    it must not target owner paths or bin items. The original native restore helper
    used is retained externally with the reproduction scripts.
11. Owner audit is already authorised read-only and uses only the saved metadata
    copies; do not repeat copying or open any recorded video to reproduce the aggregates.

Deferred intentionally: URL import, remote browser control, face/hair restoration,
automatic rerender/install interactions beyond this cycle, physical owner checklist,
optional X1/X2, owner queue/settings mutation, owner media processing, installer
signing/self-contained runtime distribution, a full corrected 10-minute gate repeat.

## Changed files

- .ai/CURRENT_TASK.md
- .ai/LAST_REPORT.md
- docs/API.md
- docs/GUI.md
- docs/TROUBLESHOOTING.md
- gui/electron/main.cjs
- gui/electron/preload.cjs
- gui/package-lock.json
- gui/package.json
- gui/src/ActionButton.tsx
- gui/src/App.tsx
- gui/src/HistoryDetail.tsx
- gui/src/HistoryRemoval.tsx
- gui/src/Home.tsx
- gui/src/Pages.tsx
- gui/src/Queue.tsx
- gui/src/ScheduleView.tsx
- gui/src/Tour.tsx
- gui/src/Trial.tsx
- gui/src/UndoToast.tsx
- gui/src/VideoFilesDialog.tsx
- gui/src/api.ts
- gui/src/style.css
- gui/src/types.ts
- gui/tests/add-models.test.tsx
- gui/tests/e2e/desktop.spec.ts
- gui/tests/e2e/gpu.spec.ts
- gui/tests/e2e/p1d3-changed.spec.ts
- gui/tests/e2e/p1e-visual.spec.ts
- gui/tests/e2e/p1e.spec.ts
- gui/tests/e2e/resume.spec.ts
- gui/tests/e2e/visual-states.spec.ts
- gui/tests/e2e/windows-flows.spec.ts
- gui/tests/home-schedule.test.tsx
- gui/tests/pages.test.tsx
- gui/tests/perf/fake-engine.cjs
- gui/tests/perf/renderer.spec.ts
- src/videoenhancer/bench/basicvsr.py
- src/videoenhancer/bench/calibration.py
- src/videoenhancer/bench/reference.py
- src/videoenhancer/bench/runner.py
- src/videoenhancer/estimate/local.py
- src/videoenhancer/estimate/model.py
- src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json
- src/videoenhancer/jobs/store.py
- src/videoenhancer/media/decode.py
- src/videoenhancer/media/probe.py
- src/videoenhancer/models/registry.py
- src/videoenhancer/pipeline/runner.py
- src/videoenhancer/schedule/controller.py
- src/videoenhancer/schedule/planner.py
- src/videoenhancer/service/deletion.py
- src/videoenhancer/service/engine.py
- src/videoenhancer/service/operation.py
- src/videoenhancer/service/server.py
- src/videoenhancer/service/settings.py
- tests/test_controller.py
- tests/test_finalization.py
- tests/test_jobs.py
- tests/test_p1c2_reliability.py
- tests/test_p1d.py
- tests/test_p1d2.py
- tests/test_p1d3.py
- tests/test_p1e.py
- tests/test_reliability.py

## Final package smoke and last regressions

Final package + changed-screen sequence: four P1e regressions PASS, packaged discovery check FAIL at its former 5 s poll limit. Discovery waiting now matches the 40 s startup bound; separate rerun PASS (2.6 s). The failed trace is retained at final-package-and-regressions, and the passing trace/log at packaged-smoke-final-2 / logs/p1e-packaged-smoke-final-2.log. Final local GUI units: 38 PASS. Final targeted preflight: 38 PASS.

## Verified implementation CI and final Git record

Implementation commit: b89e27843b6f24827ed56d3b3a1b33a7499b00c4.
All four matrix checks passed: push and PR, Windows and Ubuntu.
- Push: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38358814562
- PR: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38358819486
- Windows CPU: 352 PASS, 4 SKIP, 30 deselected, one cudaGetDeviceCount warning
  on the CPU runner. GUI units 38 PASS; Electron e2e 6 PASS, 7 opt-in SKIP.
- Ubuntu CPU: 351 PASS, 5 SKIP, 30 deselected. GUI units 38 PASS.
- Both ran ruff, format, pyright, GUI lint/typecheck/build successfully.

This report was updated after those completed implementation CI runs. The next
commit changes only this report. To avoid an endless report-update/CI loop, its
exact HEAD, push/PR IDs and four final conclusions are verified separately and
saved after completion at C:/Users/pro/Documents/VideoEnhancer-P1e/final-head-ci.json.
The final response is issued only after that final-head verification is complete.
Public PR remains draft; main is unchanged. The overall cycle remains PARTIAL
because E's full live-at-half gate failed and its full corrected repeat is NOT RUN.
The source snapshot task and all implementation changes have been committed and
pushed. Final remote-HEAD equality and clean status are part of the external proof.
