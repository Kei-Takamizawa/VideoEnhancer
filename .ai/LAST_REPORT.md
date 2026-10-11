# VE-P1d implementation and verification report

- Task ID / Cycle: VE-P1d
- Status: PARTIAL. B3 is BLOCKED; B5 depends on B3. P1d acceptance is not complete.
- Branch: p1d-ui-v2; draft PR: https://github.com/Kei-Takamizawa/VideoEnhancer/pull/5
- Starting HEAD: fe2b509, under the explicit unmerged-PR fallback. Full instructions
  saved unchanged and committed as 379b8c6. PR #4 subsequently merged at
  2026-10-11T05:53:16Z; fetched main efb45e307d65a9a6e0af4b37f95dd786acdd32c6
  contains the starting commit. No rebase/merge/main push performed.
- No subagents, owner queue/settings changes or owner-video deletion.
- Evidence and synthetic media/model caches/package stay outside Git.

## Part D

| Item | Status | Evidence |
| --- | --- | --- |
| Seven extracted components | done | design/p1d/components/*.dc.html, byte-preserving .gitattributes |
| 61-board inventory / four derived states | done | design/p1d/README.md |
| Export/runtime excluded | done | Ignored .tmp only; temporary GUI render helper removed |

The owner renamed the export to .tmp/design/VideoEnhancer_Desktop.html.
Size: 7,153,595 bytes. SHA-256:
f19cd6ed307e71e35ef319f4025b70e6e6a72b9d2e6a87cff165cd3e15d7a642.
The initial exact-filename check missed the previous spaced filename; corrected
before extraction. The temporary seven-design render used headless Edge.

## Part A

| Item | Status | Evidence |
| --- | --- | --- |
| A1 model-aware estimates | partial / FAIL accuracy | Restoration/motion reference ratios, DRUNet strength and exact calibration precedence; SCUNet +31.24%, SPAN -27.37% |
| A2 cancellation/cache reuse | done | Preserve committed MP4s, clean incomplete files, immediately reuse same key without rerender; tests/test_p1d.py:277 |
| A3 suggested range | done | CFR/source mapping and cut-neighbour exclusion; real calm hard-cut and duplicate-frame regressions at lines 328 and 341 |
| A4 AV1 minimum | done | Production encoder binary probes, pre-queue rejection; three real output cases below |
| A5 validation/docs | done | Correct scale documentation, removed blend qualification claim/dead selector, strengths/progress-history tests |

A1 lacks a measured learned-size category baseline. Learned-size estimates stay
uncalibrated. Compare uses the shared whole-file estimator rather than preview-fps
extrapolation, but its single-segment approximation differs from Add partitioning.
Preview machine-profile loading does not fully enforce selected model identities.
These limitations remain unresolved, with no accuracy guarantee.

## Part B

| Item | Status | Evidence / limitations |
| --- | --- | --- |
| B1 global/individual pause | done | Independent global flag and controller admission/abort callbacks; paused jobs retained; tests/test_p1d.py:170 |
| B2 Cancel | partial verification | Completed-segment predicate, unstarted removal, delayed running cleanup, terminal resume refusal, source/output path guards; unit tests lines 42/58. Real running GPU cleanup NOT RUN |
| B3 Recycle Bin deletion | BLOCKED / NOT RUN | No destructive probe or video-delete endpoint; see designer questions |
| B4 History remove/Clear/Undo | partial verification | Durable ten-second hide/Undo, expiry/recovery timers, multi-select and Clear confirmation; unit test line 78. Restart integration and 1,000-entry removal NOT RUN |
| B5 automatic original deletion | BLOCKED / NOT RUN | Depends on B3; no switch or auto-delete added |
| B6 responsiveness | partial | Shared structural event-plan cache, five-second progress-plan refresh, 400 ms abortable preview; CPU 2.79%. Key-to-paint/500 ms preview budget NOT RUN |
| B7 first look | partial | Compare 15-frame runs and authenticated labelled stills; timings below. Standalone trials and admission-to-first-look measurement NOT RUN |
| B8 screen data | partial | Waiting count, driver, job metadata, file present/missing state and publisher URLs; Recycle Bin state absent |

History/cancellation protect recorded original/output paths even if paths overlap
the work directory. Cancellation removes resumable intermediates after execution
stops. History uses one timer per entry; no large-batch scalability claim is made.

## Part U

| Item | Status | Evidence / limitations |
| --- | --- | --- |
| U1 shell | done in implementation | Native 32 px caption overlay, min 1100x700, persisted first tray explanation; close/hide E2E |
| U2 dock | done | Five items, waiting/failure indicators, focus/hover tooltips, Ctrl+1..5, hidden in Compare |
| U3 tokens/type | partial | Exact named dark/light tokens and 13 px Segoe UI Variable Text; obsolete aliases/blur/animations removed. Full-board geometry not verified |
| U4 zoom | done in implementation | Six native levels, intercepted keys, saved before paint, toast; zoom screenshots |
| U5 theme | done in implementation | Forced theme or live native System theme/overlay. Actual OS theme switch NOT RUN |
| U6 all screens/states | partial | Core implementations below; all 61 boards/derived states not implemented/verified |
| U7 accessibility | partial | Safe-action focus, Tab/Escape, menu closure and tooltips. Full hit-area/keyboard audit NOT RUN |
| U8 performance | NOT RUN | Renderer CPU, navigation paint, 1,000-history open and input paint measurements absent |
| U9 cleanup | partial | Dead QueuePage/PlanPage removed; unused legacy SchedulePage/CSS still present |

Home: real log paths, formatted failure times, outside/Escape menus and plural drop.
Add: batch finish estimates, warning actions and verified size gating.
History: grouped virtual rows, cropped thumbnails, search/select/remove/Undo/folder
opening; complete details/file-delete dialogs missing.
Schedule: active numeric editor with fifteen-minute arrows, quick fill, exceptions,
overlap notes, autosave/Undo, read-only timeline and override preview.
Models: per-card cancellation, plain titles, licence/publisher/SHA details and
consent; complete busy/removal dialogs and memory text remain incomplete.
Settings: two-column autosave with native theme/zoom; deletion UI absent.
Designed Reconnecting disabled actions/last update, Smart App Control and several
unreachable/error states remain incomplete. No owner visual acceptance is claimed.

## Part C

| Item | Status | Evidence / limitations |
| --- | --- | --- |
| Range editing | partial | Suggested range, thumbnails, 3/5/10 s and keyboard adjustment; visible draggable range box absent |
| Select/install/automatic render | done in implementation | Category filtering, max three, install then select, 800 ms debounce and stale-request abort |
| Synchronized viewer | done for existing output rules | Four-stream seek/play E2E and GPU equality/D2; compact full-window layout |
| First-look UI | done for Compare | Authenticated blob stills, matching frame, label and URL cleanup |
| Use this/default/Fast | partial | Existing Use this/default retained; Fast explanation/Switch to Standard missing |

Catalog refreshes alone no longer trigger repeated automatic compares. Virtual
History reobserves newly mounted failed cards as its scroll window changes.

## Part G

| Item | Status | Expected / Actual |
| --- | --- | --- |
| G1 screenshots | partial | Seven main screens at both sizes/themes and seven pairs. Other states NOT RUN; empty/synthetic captures do not reproduce every board |
| G2 clipping | partial PASS | Five dock screens at two sizes/themes, dock/tooltip bounds PASS. Add/Compare and planned timeline tooltip full assertions incomplete |
| G3 budgets | partial | Event snapshot CPU 2.79% <=5%; other service/renderer budgets NOT RUN |
| G4 GPU | partial | Two estimates FAIL accuracy; AV1 PASS; Compare timings measured with limits below; B3/B5 NOT RUN |
| G5 defaults | PASS | 14 GPU strict C1/RIFE equality and D2 tests; default output policy unchanged |
| G6 checks | partial pending final CI | Local results below; final Windows/Ubuntu CI will be checked after push |

### Builds and tests

| Command | Result |
| --- | --- |
| ruff check . | PASS |
| ruff format --check . | PASS, 103 files already formatted |
| pyright | PASS, zero errors/warnings |
| CPU suite, not gpu and not soak, isolated home | PASS: 275 passed, 3 skipped, 30 deselected, 325.11 s; .tmp/p1d-cpu-last.log |
| GPU registry/source-index suite | PASS: 14 passed, 45 deselected, 105.11 s; .tmp/p1d-gpu-equality.log |
| GUI lint/typecheck | PASS |
| GUI unit tests | PASS: 27 passed, five files |
| Production build/package | PASS: Electron 44.7.0 win32-x64; JS 480.21 kB, CSS 23.10 kB |
| Earlier serial Electron E2E | PASS: 2 passed, 3 owner GPU opt-in flows skipped; .tmp/p1d-e2e-checked.log |
| Latest packaged smoke alone | PASS: 1 passed, 2.6 s test; .tmp/p1d-packaged-final.log |

Final serial E2E results will be appended. The obsolete QueuePage/PlanPage test
removal explains the GUI count change. Skipped owner flows are not PASS evidence.

Exact local commands (PowerShell, root unless noted):

```powershell
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/pyright.exe
$env:VE_HOME='C:\Users\pro\Documents\VideoEnhancer-P1d\cpu-final-home'
.venv/Scripts/python.exe -m pytest -m 'not gpu and not soak' --basetemp=.tmp/p1d-cpu-final
$env:VE_HOME='C:\Users\pro\Documents\VideoEnhancer-P1d\model-evidence\home'
.venv/Scripts/python.exe -m pytest tests/test_model_registry.py tests/test_source_index.py -m gpu --basetemp=.tmp/p1d-gpu-equality
.venv/Scripts/python.exe .tmp/p1d_models.py
.venv/Scripts/python.exe .tmp/p1d_av1_guarded.py
.venv/Scripts/python.exe .tmp/p1d_first_look.py
# Run these in separate terminals concurrently, with the synthetic job active:
.venv/Scripts/python.exe .tmp/p1d_event_job.py
.venv/Scripts/python.exe .tmp/p1d_event_cpu.py
# In gui/:
$env:PATH='C:\Users\pro\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
node ../.tmp/npm-bootstrap/package/bin/npm-cli.js run lint
node ../.tmp/npm-bootstrap/package/bin/npm-cli.js run typecheck
node ../.tmp/npm-bootstrap/package/bin/npm-cli.js test
$env:VE_GUI_PACKAGE_OUT='C:\Users\pro\Documents\VideoEnhancer-P1d\package'
node ../.tmp/npm-bootstrap/package/bin/npm-cli.js run package
$env:VE_GUI_EVIDENCE='C:\Users\pro\Documents\VideoEnhancer-P1d\screenshots-final'
$env:VE_GUI_PACKAGE_EXE='C:\Users\pro\Documents\VideoEnhancer-P1d\package\VideoEnhancer-win32-x64\VideoEnhancer.exe'
node ../.tmp/npm-bootstrap/package/bin/npm-cli.js run test:e2e
```

The diagnostic scripts remain local/ignored and need verified model/adapter
caches. Use a new isolated home/output when reproducing rather than appending
jobs to an owner's queue. CPU/GPU suites require installed locked dependencies.

### Estimate accuracy

Synthetic 2 s portrait 720x1280 at 30 fps, Standard CUDA, 1080 short side,
2x fps, HEVC. Error = (estimated processing / actual processing - 1) * 100.

| Model | Estimated processing s | Actual processing s | Error | Expected / Actual |
| --- | ---: | ---: | ---: | --- |
| SCUNet | 160.729679 | 122.470528 | +31.239476% | +/-15% / FAIL |
| SPAN | 37.463587 | 51.582810 | -27.371954% | +/-15% / FAIL |

Total estimates 161.846960/38.580868 s and end-to-end 123.085314/52.111028 s
are reported separately because their stage accounting differs.
External evidence: model-evidence/results.json under the evidence root below.

### AV1 evidence

Exact probe command:

```text
ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=codec_name,width,height,nb_read_frames,duration:format=duration -of json <synthetic-output>
```

Exact selected output fields (full objects in av1-verified/results.json):

```json
{"minimum_output":{"codec_name":"av1","width":130,"height":66,"duration":"1.000000","nb_read_frames":"30","format_duration":"1.000000","bytes":1727},
"portrait-keep":{"codec_name":"av1","width":720,"height":1280,"duration":"1.000000","nb_read_frames":"30","format_duration":"1.000000","bytes":1359009,"segments":1},
"three-segments":{"codec_name":"av1","width":720,"height":1280,"duration":"7.000000","nb_read_frames":"210","format_duration":"7.000000","bytes":9793166,"segments":3}}
```

130x66 encoded; 128x66 and 130x64 failed with NvEncoder initialization error 8.
Rounded capability metadata was 192x128, not the actual minimum 130x66.

### First-look evidence

Synthetic 4 s portrait 720x1280@30; selected 3 s, Standard CUDA, 1080 short side,
2x HEVC with default companion stages. Sequential runs reused Original/warm
shared adapters for later models. RIFE includes cleanup, not isolated RIFE fps.

| Model | First look s | Full preview ready s |
| --- | ---: | ---: |
| C1 | 23.359254 | 75.139592 |
| SCUNet | 32.051912 | 196.726908 |
| RIFE 4.25 | 11.624265 | 63.482598 |

Timer starts at render_compare entry, including analysis, not service GPU
admission. The C1 number is below 25 s under this scope, but required admission
acceptance remains unverified. Evidence: first-look/results.json.

### Event CPU evidence

One idle-client-equivalent caller invoked Engine.event_snapshot once per second
with one Standard SCUNet synthetic job running in a separate process and ten
queued records. 31 calls: 31.973081 wall s, 0.890625 CPU s, 2.785546% of one core;
maximum snapshot 73.872600 ms. This excludes network SSE/renderer cost.
Earlier attempts without an active job across the window were excluded.
Evidence: model-evidence/event-cpu.json and .tmp/p1d-event-cpu-valid.log.

### GUI actions and screenshots

Automation starts a real isolated CPU service, adds synthetic footage, observes
Preparing/progress/completion, opens the five dock screens, changes theme/zoom,
opens Add and four-stream Compare, seeks/plays synchronized media, acknowledges
the tray explanation and hides/restores. Package smoke verifies engine location
and renderer isolation. Native Computer Use is unavailable; no manual native
operation or complete visual acceptance is claimed.

External evidence root: C:\Users\pro\Documents\VideoEnhancer-P1d.
Screenshot folder: C:\Users\pro\Documents\VideoEnhancer-P1d\screenshots-final.

| Component | Design/app pair at 1280x800 dark |
| --- | --- |
| Main | home-design-versus-app.png |
| AddVideos | add-design-versus-app.png |
| History | history-design-versus-app.png |
| Schedule | schedule-design-versus-app.png |
| Models | models-design-versus-app.png |
| Compare | compare-design-versus-app.png |
| Settings | settings-design-versus-app.png |

For each home/add/history/schedule/models/compare/settings, app screenshots are
<screen>-dark-1280x800.png, <screen>-dark-1100x700.png,
<screen>-light-1280x800.png, <screen>-light-1100x700.png.
Design files are <Component>-design.png. Captures contain available empty or
synthetic states; remaining board states were NOT RUN.

## Part X

| Item | Status | Reason |
| --- | --- | --- |
| X1 blend requalification | NOT RUN | Required earlier work remains incomplete |
| X2 keep model loaded 120 s | NOT RUN | Required earlier work remains incomplete |

## Errors and warnings

- A1 accuracy FAIL; no tuning of acceptance/defaults to these two observations.
- Initial GPU helper lacked Windows main guard; fixed and rerun in a fresh home.
- Legacy schedule assertion requested implicit bounds; now explicitly requests
  include_range. Old SSE mock hung after snapshot interface change; fixed/reran.
- GUI completion type error fixed and build rerun; old-bundle runs excluded.
- Clipping assertion originally counted offscreen scroll-container descendants;
  fixed to evaluate painted intersections.
- Latest parallel Playwright invocations shared the output folder and one failed
  with missing trace artifacts/completion timeout; rerun serially. No PASS
  inferred from that failed attempt.
- Node NO_COLOR/FORCE_COLOR warning and Git LF/CRLF warnings; design uses -text.
- Unresolved missing states/budgets appear above. Do not merge this draft based
  solely on passing regression tests.

## Questions for the designer

1. B3 requires keeping originals if recycling would fall back to permanent
   deletion. Reviewed Microsoft APIs say recycle if possible; post-delete
   callback proves recycling only after deletion. Pre-delete can abort, but
   the reviewed docs do not establish a guaranteed recycle decision before
   deletion. An approved fail-closed preflight/refusal strategy is needed.
   Default: no destructive endpoint and no B5. Sources:
   [flags](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifileoperation-setoperationflags),
   [transfer](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/ne-shobjidl_core-_transfer_source_flags),
   [pre-delete](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifileoperationprogresssink-predeleteitem),
   [post-delete](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifileoperationprogresssink-postdeleteitem).
2. A1's two jobs fail +/-15% and learned-size baseline is absent. Supply the
   approved reference/calibration plan. Default: keep uncalibrated and report
   measured failures without changing the formula's product policy.
3. Remaining UI states, range box, Fast panel, trial first look and acceptance
   measurements require further implementation. Default: keep the PR draft and
   report PARTIAL; the supplied spec remains authoritative.

## Reproduction / changed files / intentional omissions

Use the exact commands above with a fresh synthetic home. For accuracy compare
predicted processing seconds to sum of actual segment seconds for the two
model choices. For History remove a synthetic terminal record, Undo before
ten seconds, repeat without Undo, and verify original/output bytes. Cancel
an unstarted job versus a job with completed segments; the latter cannot resume.
There is deliberately no B3 video-delete action to execute.

Changed: engine estimate/model, jobs/store, media/encode, models/registry,
schedule/controller, service compare/engine/server/settings; GUI electron
main/preload, App/Home/Pages/Queue/Schedule/ScheduleView/Trial, api/focus/types,
style.css; tests test_p1d/test_p1c3/test_reliability and GUI add-models/
home-schedule/pages/setup/e2e desktop; docs ADDING_MODELS/API/GUI/
THIRD_PARTY_MODELS/TROUBLESHOOTING; .gitattributes; seven design components and
README; .ai/CURRENT_TASK.md and .ai/LAST_REPORT.md. Paths are relative to repo.

Intentional omissions: owner-video deletion, owner jobs/settings, full soak,
optional X, owner visual check, all-state screenshot sweep, unsupported accuracy
claims, merge/main push. Final Git/CI and serial E2E results appended below.

## Final local rerun

- Final serial Electron E2E: PASS, 2 passed, 3 explicitly skipped (1.2 min); .tmp/p1d-e2e-final-serial.log. This includes the final compact Compare CSS and automatic-render/History observer fixes.
- Packaged smoke included in the same serial run: PASS, 2.5 s.
- Seven design/app pairs regenerated from the final screenshots.
- Commit/push is performed on p1d-ui-v2 only; final remote equality and CI are checked after push.
