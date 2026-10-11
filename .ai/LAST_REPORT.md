# VE-P1d-2 implementation and acceptance report

- Task ID / Cycle: VE-P1d-2.
- Status: PARTIAL. Implementation is complete; measured acceptance failures remain open for designer decisions.
- Branch: `p1d-ui-v2`; draft PR: https://github.com/Kei-Takamizawa/VideoEnhancer/pull/5.
- Base: `origin/main` at `efb45e3`, merged without rebase in `efbc48a`.
- Exact instructions saved and committed in `5e1cece`.
- All footage is synthetic. Engine homes, media, weights, generated packages and
  screenshots are outside Git. The owner's queue and settings were not used.
- Host: Windows 11 build 26300, RTX 4060 Ti 8 GB, NVIDIA driver 617.42,
  Python 3.12.14, Torch 2.14.1+cu130, FFmpeg 9.0.2.

## Part E — model-aware estimates

| Item | Status | Evidence |
| --- | --- | --- |
| Preserve default mode pipeline, remove single-frame 2x multiplier | done | `src/videoenhancer/estimate/model.py:160`; CPU estimate tests |
| Add each compatible reference pipeline delta once per source frame | done | Same GPU/reference dimensions/mode required; selected and category-default identities verified |
| Missing reference is uncalibrated with ±25% range | done | Estimate tests; no downloads during estimate |
| Calibrate installed verified alternatives | done | `src/videoenhancer/bench/reference.py`; actual isolated calibration profile |
| Four 30-second first estimates | PASS after independent calibration | All calibrated errors between −3.41% and −6.18%; initial misses retained below |
| Two-second non-gating checks | done | Measurements below |
| Operating-hours GPU overrun observation | PASS, zero overruns | Valid UTC 13:30–13:45 exception; two C1 segments 185.261067/198.088900 s; finalization ended 13:37:59.602009. `hours-normal/results.json` under evidence root. |

The initial estimates use the installed model references and the existing default
pipeline coefficients. The second run uses an independently measured machine
profile, copied into four fresh homes. Neither run uses a correction learned
from that job. Actual time is the sum of recorded segment `actual_seconds`;
whole-job wall time also includes analysis/finalization and is retained in JSON.
Portrait 720×1280/30 fps, 30 seconds, output 1080×1920/60 fps HEVC, CUDA.
Error is `(estimate / actual - 1) × 100`; gate is ±15%.

| Initial job | Estimate s | Actual s | Error | Gate |
| --- | ---: | ---: | ---: | --- |
| c1 | 537.953804 | 391.701669 | +37.338% | FAIL |
| scunet | 1717.964843 | 1617.092588 | +6.238% | PASS |
| span | 823.330126 | 700.614543 | +17.515% | FAIL |
| fast | 148.603520 | 60.234513 | +146.708% | FAIL |

Independent calibrated acceptance: all four first estimates PASS using the
independently measured profile (no previous correction for each fresh job).

| Calibrated job | Estimate s | Actual s | Error | Gate |
| --- | ---: | ---: | ---: | --- |
| c1 | 370.483115 | 383.546629 | -3.406% | PASS |
| scunet | 1545.512026 | 1647.320649 | -6.180% | PASS |
| span | 660.940637 | 695.037497 | -4.906% | PASS |
| fast | 56.674118 | 59.636117 | -4.967% | PASS |

Evidence:
`C:/Users/pro/Documents/VideoEnhancer-P1d-2/calibrated-acceptance/results.json`.

| Two-second non-gating job | Estimate s | Actual s | Error |
| --- | ---: | ---: | ---: |
| scunet | 115.330990 | 111.973766 | +2.998% |
| span | 56.222008 | 53.123259 | +5.833% |

Initial evidence: `C:/Users/pro/Documents/VideoEnhancer-P1d-2/estimates/results.json`.
Calibration: `calibrated-acceptance/calibration-summary.json` under the same root.
No formula was fitted to these acceptance timings.

## Part S — guarded recycling and automatic original deletion

| Item | Status | Evidence |
| --- | --- | --- |
| Recorded path / regular file / fixed NTFS-ReFS / no reparse / exclusive-open / unfinished-use checks | done | `src/videoenhancer/service/deletion.py:31`; refusal tests |
| fsync journal, hidden same-folder hard link, progress-sink recycling | done | `VideoDeletion` at line 196; no `FOF_NOCONFIRMATION` |
| Confirm bin item and guard; otherwise restore without replacement | done | Shell-failure and byte-preservation tests; real NTFS result below |
| Recover planned, guarded, shell and confirmed phases, including crash after guard removal | done | 18 deletion tests PASS |
| Per-file endpoint and History detail / disabled Compare | done | `HistoryDetail.tsx`; HTTP and GUI tests |
| Automatic original deletion after four output checks; shared source waits; default off | done | `deletion.py:328,387`; real GPU success and forced-failure cases |

Expected: recycling removes the original path and permits restoration from the
bin; a fully deleted or rejected outcome retains/restores identical bytes.
Actual: all four requested real-PC checks PASS:

| Real-PC case | Actual result | SHA-256 |
| --- | --- | --- |
| Native synthetic video recycle and Shell restoration | Source gone, real PostDeleteItem bin object; exact synthetic bin entry restored | `8cb60f13d80f624194acdd1c14f094b0359b065edd0fa4cf6d466f14be4020b1` before and restored |
| Forced permanent-deletion outcome on real NTFS | Guard moved back; full bytes identical | Same `8cb60f...` full hash before and after |
| GPU job with automatic deletion | Decode, frame count, duration and source-audio checks pass; original recycled, then restored | `e36555e29cf375f98a552e807a1ff005ba60df289b260cb242256544dfeba76a` before and restored |
| GPU job with forced output-check failure | Job output done; original retained with explicit reason | Same `e36555...` full hash before and after |

Evidence: `C:/Users/pro/Documents/VideoEnhancer-P1d-2/deletion-real/results.json`
and `auto-delete/results.json`. Only exact synthetic Recycle Bin entries were
restored. No owner bin entries were removed or changed.

## Part F — First look from the actual render

| Item | Status | Evidence |
| --- | --- | --- |
| No separate 15-frame render or second model load | done | `pipeline/runner.py` observer; `service/compare.py` actual-frame callback |
| Still matches corresponding pre-encoding preview frame | PASS | CPU raw-byte frame-7 comparison and PNG decode |
| Authorized still endpoint / unpublished name rejection | PASS | `tests/test_p1d2.py` |
| C1 first look ≤25 seconds | PASS | 22.899940 seconds from GPU admission |
| Full previews no slower than task thresholds | partial | C1 and SCUNet PASS; both fresh RIFE measurements FAIL |

Fresh isolated homes, uncached source, four-second synthetic portrait input,
three-second preview range, 1080 output and doubled fps. Timers start at actual
service GPU admission, including child startup, analysis and model loading.
The matching default companion stages run; RIFE includes cleanup.

| Model | Actual model First look s | Full preview s | Target full s | Gate |
| --- | ---: | ---: | ---: | --- |
| C1 | 22.899940 | 65.426513 | 75.1 | PASS |
| SCUNet | 33.974973 | 184.148696 | 196.7 | PASS |
| RIFE 4.25 | 22.244125 | 65.157373 | 63.5 | FAIL |

Original-first-tile time is separately retained; it is not substituted for the
model First look time. P1d used render-entry timing and warm shared resources for
later models; the new cold admission measurement has a stricter boundary.
Evidence: `C:/Users/pro/Documents/VideoEnhancer-P1d-2/first-look/results.json`.
Fresh RIFE retry: First look 22.614682 s; full preview 65.164937 s
versus 63.5 s: FAIL (+2.622%). Evidence: `first-look-retry/results.json`.
Standalone Trial keeps its existing completed-preview flow.

## Part U — UI v2 gaps

| Area | Status | Implemented / verified |
| --- | --- | --- |
| Global | done | App icon; Connecting; disabled reconnecting actions and Last update; Retry / Copy details; Smart App Control |
| Tokens | done | Base control minimum 32 px and radius 9 px; accepted dock/handle sizes retained |
| Home | done | Result-only preview; paused wait copy; Pause tooltip; weekly-hours title; empty state; cancel cleanup; exact unstarted-removal dialog |
| Add | done | Delete-original switch; File format; unverified size disabled; six warning-specific fixes; busy / partial states |
| History | done | Designed detail fields/actions, per-file deletion, Select all, missing/recycled labels, empty/no-match |
| Schedule | done | Anchored/clamped bar tooltips; obsolete Schedule.tsx and weekly-grid rule removed; overnight/off-day tests ported |
| Models | done | Default/unfinished-use/current-job reasons; GPU memory capacity; source host; default labels; operation busy display |
| Settings | done | After processing preference; above-100% scrolling hint |
| Compare | done | Visible range, click/keyboard placement, slider, swipe handle, segmented zoom, Fast choices, auto render, descriptions and tile state labels |
| Regression tests | PASS | Finalization and both valid Alt reorder directions; B8 waiting count / file states / publisher URL; all six warning fixes |

Actual packaged-board inventory contains 61 successful states and 122 images.
Screenshots show real packaged UI using an authenticated synthetic API fixture;
fixture preview clips do not claim model quality. The owner's visual approval
remains the designer's responsibility.

## Part P — repeatable performance harness

| Item | Status | Evidence |
| --- | --- | --- |
| Playwright / marks / Event Timing / 1,000 History + 10 queued + running Standard | done | `gui/tests/perf/renderer.spec.ts`, fake-engine.cjs |
| Cached manifests by modification identity and immutable revision | done | `jobs/store.py:357` |
| Cached AV1 minimum by exact GPU/driver/schema | done | `service/av1_cache.py:10`; invalidation tests |
| Real service CPU harness and synthetic fixture preparation | done | `service.py`, `prepare_service.py`; separate idle client/controller processes |
| All measured budgets | partial | Measurements and failed gate below |

Renderer run: two animation frames after heading visibility; Schedule key-to-
paint marks; actual preview-painted mark; Event Timing input delay is
`processingStart - startTime`; CDP TaskDuration / 30 seconds gives one-core CPU.
The fixture publishes progress once per second. No hidden history expansion.

| Budget | Latest observation | Required | Result |
| --- | ---: | ---: | --- |
| Screen switch / open History | History 100.6; Schedule 42.4; Models 30.2; Settings 30.1; Home 46.7 ms | ≤100 ms | FAIL for History |
| Open History, 1,000 records | 100.6 ms, 9 DOM cards | ≤300 ms | PASS |
| Schedule key-to-paint, five keys | max 31.9 ms | ≤50 ms | PASS |
| Last key to preview paint | 448.5 ms | ≤500 ms | PASS |
| Event Timing input processing delay | max 2.1 ms | ≤50 ms | PASS under stated input-delay metric |
| Event Timing full interaction duration | max 128 ms | No separate duration threshold specified | Observed, not hidden |
| Idle renderer with progress | 0.623190% of one core | ≤2% | PASS |
| Progress text average frequency | 29 changes / 30.010 s = 0.966345 Hz | ≤1 Hz | PASS average only |
| Progress text strict spacing | Minimum observed gap 999.5 ms | ≥1,000 ms between updates | FAIL |
| Real service SSE work, prescribed fixture | 4.477952% (1.390625 CPU s / 31.054933 wall s), 7 SSE events | ≤5% of one core | PASS |
| Real service, diagnostic-rich terminal records | 10.027181% (3.140625 CPU s / 31.321116 wall s), 7 SSE events | ≤5% of one core | FAIL |

The earlier service result (7.147264% over 31.043348 s) included an idle client's
buffered reads in the same measured process. It cannot establish service-only
CPU and is retained only as a superseded diagnostic. An earlier renderer run
passed screen switching at 66.6 ms for History; the later 127.7 ms miss remains
reported. No failed measurement is replaced with a selected favorable result.
Latest evidence: `C:/Users/pro/Documents/VideoEnhancer-P1d-2/perf-strict-final/renderer-perf.json`.
Post-grouping first run was 94.9 ms/PASS; the fresh strict-harness rerun
was 100.6 ms/FAIL. Both are retained, with no favorable result selection.
Earlier failed run retained: `perf-final/renderer-perf.json` under the same root.
Separate-client service evidence: `service-perf-final/results.json` and
`service-perf-isolated-client/results-fps-only.json` under the same root.
Both service measurements warmed the complete first snapshot before timing.
The realistic diagnostic-rich fixture still misses the CPU budget; it is not
hidden by the prescribed minimal-history pass. A repeat renderer run before
the History grouping fix measured 110.7 ms (FAIL), CPU 0.616928%, input delay
1.7 ms, full interaction duration 176 ms, key paint 32.3 ms and preview 449.2 ms.
Grouping now reuses one month/year formatter and appends to group arrays without
repeated copying; this does not change grouping or displayed labels.

## Part R — robustness

| Item | Status | Evidence |
| --- | --- | --- |
| Clear history reports each failed removal and restores failed-record visibility | done / PASS | Partial-failure test; GUI does not hide before API success |
| Event key and queue operation snapshots copied under lock | done / PASS | Concurrent live-operation test; no Snapshot unavailable exception |
| Failed hidden cancel cleanup reappears as failed History record | done / PASS | Failure-injection test with retained error |

## Part G — acceptance

| Item | Status | Evidence |
| --- | --- | --- |
| G1 all 61 packaged boards / both sizes / main dark+light / comparisons | PASS | 122 screenshots, 7 side-by-side images; full inventory below |
| G2 CI clipping tests | PASS locally | Add, Compare and History detail at both sizes/100%/110%; Schedule tooltip edges at both sizes/zooms |
| G3 performance | partial | Part P includes numerical FAIL |
| G4 E/F/S GPU evidence | partial | Part S PASS; timing gates as documented |
| G5 all GPU-marked Python tests | PASS | 30 passed, 301 deselected, 162.12 s |
| G6 local static/CPU/GUI checks | PASS with explicitly skipped optional tests | Results below |
| G6 final Windows/Ubuntu CI | RUNNING | Earlier Ubuntu failures and fixes retained in Errors below; new final-source run follows scan fix |
| Owner visual check | NOT RUN | Explicitly outside implementer scope; no owner-check file fabricated |

### Executed checks and logs

| Check | Result | Log |
| --- | --- | --- |
| Ruff check + format check of repository | PASS | 111 Python files formatted |
| Pyright, Windows and Linux targets after CI fix | PASS, 0 errors / 0 warnings for each | `.tmp/p1d2-pyright-windows2.log`, linux.log |
| Deletion/First-look/cache/robustness tests after ctypes fix | PASS, 28 tests, 6.32 s | `.tmp/p1d2-ci-fix-tests2.log` |
| Job scan/service/metadata regression suite after POSIX fix | PASS, 26 tests, 22.06 s | `.tmp/p1d2-ci-scan-tests.log` |
| Full CPU including soak, excluding GPU | PASS, 303 passed / 3 skipped / 30 deselected, 315.69 s | `.tmp/p1d2-cpu-finalhead.log` |
| Added deletion/B8 tests | PASS, 25 tests, 3.24 s | `.tmp/p1d2-new-tests.log` |
| Live-operation and P1d regression set after lock change | PASS, 26 tests, 13.16 s | `.tmp/p1d2-lock-final.log` |
| All GPU markers | PASS, 30 tests, 162.12 s | `.tmp/p1d2-gpu-all.log` |
| GUI lint/typecheck | PASS | `.tmp/p1d2-gui-lint-final.log`, typecheck-final.log |
| GUI unit tests | PASS, 35 tests, 5.58 s | `.tmp/p1d2-gui-unit-final.log` |
| GUI build and Windows folder package | PASS | `.tmp/p1d2-gui-package-final.log` |
| GUI e2e including package smoke and complete board inventory | PASS, 4 passed / 3 skipped, 2.2 min | `.tmp/p1d2-e2e-finalhead.log` |
| Renderer performance test after grouping fix | Latest FAIL, History 100.6 ms and minimum progress gap 999.5 ms; prior run 94.9 ms PASS under average-frequency check | `.tmp/p1d2-perf-strict.log`, grouping.log |

GUI actions included actual Electron opening/closing, synthetic video addition,
CPU processing completion through SSE, paired frame seeking/playback (100 random
seeks), tray explanation/hide/show, navigation, themes, 100–150% zoom, Add/Compare/
History detail deletion dialogs, range/swipe controls and bar tooltip hover.
Optional GPU GUI resume and visible-console flow tests were not enabled; SKIP
is not a pass. Native external-player, accessibility and physical reboot checks
were not claimed. Logs under `.tmp` are ignored local reproduction evidence.

## Part X — optional

| Item | Status | Reason |
| --- | --- | --- |
| X1 tiled blend qualification | NOT RUN | Required acceptance gates have failures; optional work cannot begin |
| X2 120-second idle compare-model cache | NOT RUN | Same ordering constraint; no queue-delay behavior introduced |

## Questions for the designer

1. Default estimate coefficients without calibration miss C1, SPAN and Fast.
   Default chosen: preserve the mandated existing default formulas and report
   results; do not fit coefficients to the acceptance clip.
2. Cold-admission RIFE full preview is 65.157 s versus the 63.5 s target. P1d's
   warm/render-entry boundary differs. Default: retain actual-render First look
   and unchanged output settings; report the failed threshold.
3. The diagnostic-rich service fixture fails the 5% one-core CPU budget.
   History switching improved from 127.7/110.7 ms to 94.9 ms after eliminating
   repeated date formatter construction and array copies. Latest rerun is
   100.6 ms and remains FAIL; all observations
   are retained. No UI or architecture redesign was made.
   Diagnostic-rich service event-stream work remains 10.027% >5%; further
   architecture/cadence changes require a designer decision. Default: preserve
   the existing output and five-second structural refresh behavior.
4. A hard-link guard protects bytes even if Windows does not recycle; shell UI
   flags cannot guarantee suppression in every OS condition without the
   prohibited confirmation flag. Default: fail closed and keep/restore bytes.
5. Standalone Trial still waits for its completed preview. Default: implement
   the explicitly specified Compare actual-render still; no Trial flow redesign.
6. Nominal one-Hz progress delivery has observed minimum 989 ms and latest
   999.5 ms paint intervals.
   Default: report strict spacing as FAIL and retain current progress delivery;
   a different rendering/delivery policy requires designer review.
7. Input delay and complete interaction duration differ. Both are reported.
   Default: use Event Timing input processing delay for the input-delay gate,
   and separately apply the screen/preview paint budgets.

## Reproduction

From the repository root, use a fresh isolated `VE_HOME` and evidence directory.
Verified local weights are prerequisites; no automatic downloads are performed.

```powershell
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/pyright.exe
.venv/Scripts/python.exe -m pytest -m 'not gpu' --basetemp=.tmp/new-cpu-test-home
.venv/Scripts/python.exe -m pytest -m gpu --basetemp=.tmp/new-gpu-test-home
.venv/Scripts/python.exe gui/tests/perf/prepare_service.py --root C:/private/new-perf --model-home C:/private/verified-model-home
```

GPU tests require CUDA and a separate model-enabled home. D2 CPU coverage is in
`tests/test_degraded.py` and ran in the full CPU suite.
From `gui`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`,
`npm run package`, `npm run test:e2e`, and
`npx playwright test --config=playwright.perf.config.ts`.
For packaged acceptance set `VE_GUI_PACKAGE_EXE` to the generated Windows EXE
and `VE_GUI_EVIDENCE` to a private output directory. Visual inventory can filter
failed rows with `VE_GUI_BOARD_IDS`; the complete acceptance run used all rows.
For E, set isolated `VE_HOME` and `VE_SAMPLES_DIR`; generate a separate
5-second 720×1280/30 fps synthetic calibration reference in that samples directory
(the reference pipeline measures 150 frames). Generate the specified separate
30-second testsrc2 portrait acceptance clip, independently
run `bench --calibrate`, copy the profile into four fresh homes, add each job
with `target_segment_seconds=180`, save its initial segment predictions, then
run the queue and sum `actual_seconds`. Save all measurements outside Git.
For native deletion use only a new synthetic file on fixed NTFS, call guarded
recycling, then restore that exact bin entry and compare its complete SHA-256.
Forced checks and crashes are reproduced by the test cases, not owner media.

## Screenshot paths

Root: `C:/Users/pro/Documents/VideoEnhancer-P1d-2/gui-evidence/boards/`.
Every basename below has both `-1280x800.png` and `-1100x700.png` suffixes.
Exact absolute paths are also listed in `inventory.json` under that root.

| Board | Name | Basename (two size suffixes) |
| ---: | --- | --- |
| 1 | Home | `01-Main-working-dark` |
| 2 | Add videos | `02-AddVideos-default-dark` |
| 3 | History | `03-History-default-dark` |
| 4 | Schedule | `04-Schedule-default-dark` |
| 5 | Models | `05-Models-default-dark` |
| 6 | Compare | `06-Compare-default-dark` |
| 7 | Settings | `07-Settings-default-dark` |
| 8 | Home · light | `08-Main-working-light` |
| 9 | Add videos · light | `09-AddVideos-default-light` |
| 10 | History · light | `10-History-default-light` |
| 11 | Schedule · light | `11-Schedule-default-light` |
| 12 | Models · light | `12-Models-default-light` |
| 13 | Compare · light | `13-Compare-default-light` |
| 14 | Settings · light | `14-Settings-default-light` |
| 15 | Home · 1100 x 700 | `15-Main-working-dark` |
| 16 | Add videos · options open · 1100 x 700 | `16-AddVideos-optionsNoAv1-dark` |
| 17 | History · 1100 x 700 | `17-History-default-dark` |
| 18 | Schedule · 1100 x 700 | `18-Schedule-default-dark` |
| 19 | Models · 1100 x 700 | `19-Models-default-dark` |
| 20 | Compare · 1100 x 700 | `20-Compare-failed-dark` |
| 21 | Settings · Advanced open · 1100 x 700 | `21-Settings-advanced-dark` |
| 22 | Home · more menu | `22-Main-menu-dark` |
| 23 | Home · waiting for your hours | `23-Main-waiting-dark` |
| 24 | Home · finishing | `24-Main-finishing-dark` |
| 25 | Home · empty queue | `25-Main-empty-dark` |
| 26 | Home · dropping files | `26-Main-drop-dark` |
| 27 | Home · zoom toast | `27-Main-zoom-dark` |
| 28 | Home · preview result | `28-Main-preview-dark` |
| 29 | Home · first close to tray | `29-Main-tray-dark` |
| 30 | Home · long queue scrolls · 1100 x 700 | `30-Main-long-dark` |
| 31 | Home · cancel job | `31-Main-confirmCancel-dark` |
| 32 | Home · remove job | `32-Main-confirmRemove-dark` |
| 33 | Home · job log | `33-Main-log-dark` |
| 34 | Home · action error | `34-Main-actionError-dark` |
| 35 | Home · problem | `35-Main-problem-dark` |
| 36 | Home · connecting | `36-Main-connecting-dark` |
| 37 | Home · reconnecting | `37-Main-reconnecting-dark` |
| 38 | Home · engine unreachable | `38-Main-unreachable-dark` |
| 39 | Home · Smart App Control | `39-Main-sac-dark` |
| 40 | Add videos · more options | `40-AddVideos-options-dark` |
| 41 | Add 1 video · estimating | `41-AddVideos-one-dark` |
| 42 | Add videos · blocking warnings | `42-AddVideos-warnings-dark` |
| 43 | Add videos · adding | `43-AddVideos-busy-dark` |
| 44 | Add videos · partly added | `44-AddVideos-partial-dark` |
| 45 | History · needs attention | `45-History-failed-dark` |
| 46 | History · file not found | `46-History-notFound-dark` |
| 47 | History · select mode | `47-History-select-dark` |
| 48 | History · delete video files | `48-History-deleteFiles-dark` |
| 49 | History · clear history | `49-History-clear-dark` |
| 50 | History · removed, undo | `50-History-toast-dark` |
| 51 | History · empty | `51-History-empty-dark` |
| 52 | History · no match | `52-History-noMatch-dark` |
| 53 | Schedule · add a special day | `53-Schedule-addDay-dark` |
| 54 | Schedule · run now until a time | `54-Schedule-runUntil-dark` |
| 55 | Schedule · working now | `55-Schedule-override-dark` |
| 56 | Schedule · work any time | `56-Schedule-off-dark` |
| 57 | Models · details | `57-Models-details-dark` |
| 58 | Models · licence before download | `58-Models-licence-dark` |
| 59 | Models · remove | `59-Models-remove-dark` |
| 60 | Compare · swipe, landscape | `60-Compare-swipe-dark` |
| 61 | Compare · Fast video | `61-Compare-fast-dark` |

Side-by-side root:
`C:/Users/pro/Documents/VideoEnhancer-P1d-2/gui-evidence/side-by-side/`:
`Main-design-versus-app.png`, `AddVideos-design-versus-app.png`,
`History-design-versus-app.png`, `Schedule-design-versus-app.png`,
`Models-design-versus-app.png`, `Compare-design-versus-app.png`,
`Settings-design-versus-app.png`. Left: unchanged design render from P1d;
right: current packaged synthetic app. Images preserve their native dimensions.

## Changed files

- `docs/API.md`
- `docs/GUI.md`
- `docs/TROUBLESHOOTING.md`
- `gui/src/App.tsx`
- `gui/src/Home.tsx`
- `gui/src/Pages.tsx`
- `gui/src/Queue.tsx`
- `gui/src/Schedule.tsx`
- `gui/src/ScheduleView.tsx`
- `gui/src/Trial.tsx`
- `gui/src/style.css`
- `gui/src/types.ts`
- `gui/tests/add-models.test.tsx`
- `gui/tests/e2e/desktop.spec.ts`
- `gui/tests/home-schedule.test.tsx`
- `gui/tests/pages.test.tsx`
- `src/videoenhancer/bench/calibration.py`
- `src/videoenhancer/bench/runner.py`
- `src/videoenhancer/estimate/model.py`
- `src/videoenhancer/jobs/store.py`
- `src/videoenhancer/pipeline/runner.py`
- `src/videoenhancer/schedule/controller.py`
- `src/videoenhancer/service/compare.py`
- `src/videoenhancer/service/engine.py`
- `src/videoenhancer/service/server.py`
- `src/videoenhancer/service/settings.py`
- `tests/test_compare.py`
- `tests/test_estimate.py`
- `tests/test_model_registry.py`
- `tests/test_p1d.py`
- `gui/playwright.perf.config.ts`
- `gui/src/HistoryDetail.tsx`
- `gui/tests/e2e/clipping.ts`
- `gui/tests/e2e/visual-states.spec.ts`
- `gui/tests/perf/`
- `src/videoenhancer/bench/reference.py`
- `src/videoenhancer/service/av1_cache.py`
- `src/videoenhancer/service/deletion.py`
- `tests/test_deletion.py`
- `tests/test_p1d2.py`

`.ai/CURRENT_TASK.md` is already recorded in the instruction commit;
`.ai/LAST_REPORT.md` is overwritten for this cycle. No generated media, weight,
screenshot, build output, owner log or node_modules is staged.

Additional derived Models downloading evidence: `gui-evidence/boards/derived-Models-downloading-dark-1280x800.png` and `derived-Models-downloading-dark-1100x700.png` under the private evidence root.

## Errors, warnings and final Git record

- An initial pytest invocation used an inaccessible default Windows temp area;
  fresh repository-local `--basetemp` reruns passed.
- Initial visual harness reload/selector/tray timing failures were corrected;
  the final complete packaged inventory passed all 61 states.
- A valid Alt+Down test expected position 2 instead of the full-queue position 3;
  the test expectation was corrected, and both directions now pass.
- The first hours fixture used invalid one-minute clock values; the existing
  15-minute schedule validator correctly rejected it before GPU admission.
  A valid quarter-hour exception fixture replaces it. The first overrun helper
  also lacked the Windows multiprocessing main guard, so its child failed
  before GPU rendering. Corrected guarded C1 schedule validation is running.
- Ubuntu CI on `3c02607` failed Pyright with 14 Windows ctypes attribute errors.
  Explicit typing of the runtime Windows API boundary corrects non-Windows
  static analysis while preserving Windows behavior.
- Ubuntu CPU CI on `8ba213f` found seven failures from a lock file being
  scanned as a job directory (POSIX raises NotADirectoryError). The scan now
  skips non-directories and handles a directory-to-file race. A regression
  test verifies that lock files are never inspected as manifest folders.
- Performance failures are retained above, not treated as syntax defects.
- Node emits NO_COLOR/FORCE_COLOR warnings; they do not change test assertions.
- Implementation and local evidence committed/pushed in `3c02607`; Windows
  ctypes typing and strict progress harness fix in `8ba213f`. The job scan
  fix is the next source commit. CI result will be recorded after verification.
