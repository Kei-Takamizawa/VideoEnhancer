# VE-P1b — Local service and Windows desktop

Task ID / Cycle: VE-P1b / P1b. Date: 2026-10-08 (owner timezone).
Status: PARTIAL — implementation and local checks complete; physical tray menu,
Explorer drop, fresh network weight download and extended viewer interactions
remain NOT RUN. CI verification is pending first publication.
Branch: p1b-gui. Base: origin/main 0ee24505e000927be17bf64b30465701584a89a7.
PR #2 was verified merged. Initial working tree was clean. No subagents used.
CURRENT_TASK.md matches the uploaded instruction byte-for-byte, SHA-256
f088663284f46ca0f5ddc3d06222ada52d484389b919cb836afbb362491e3499.

## Implementation

- R1: stdlib loopback/random-port HTTP, per-home service lock, current-user-private
  bearer discovery, Host/Origin checks, serialized API mutations/snapshots,
  SSE snapshots and 10-second heartbeat. Queue/estimate/plan/schedule/override,
  models/settings/trial/calibration/log/shutdown use the existing JobStore,
  scheduler and controller lease. CLI processing behavior remains unchanged.
- R2: Electron/React/TypeScript/Vite, app:// renderer/CSP, context isolation,
  sandbox/no renderer Node, narrow preload, single instance, tray, detached
  engine, graceful Quit, hidden Windows startup, retained-data Retry banner.
  Five-page navigation, permanent bottom strip, themes, visible focus/modal trap.
- R3: multiple-file picker/drop, one live per-preset estimate dialog with defaults,
  model choices and numbered warnings; reorder/actions/confirmations/log/details,
  phase/step display, engine-controlled completion cap. Adding requires already
  verified models and never silently downloads weights.
- R4: 7x96 paint grid/list, crossing midnight, exception calendar, overrides,
  unsaved preview/queue effect and validated Save using the engine schedule.
- R5b/c/d: plan table/timeline/scenarios/calibration; model licence consent and
  add/remove/verify; persistent defaults, startup/theme/log/advanced/diagnostics/
  About. Timeline positions use the engine timezone, including DST tests.
- R6b: real job-settings Trial, thumbnails/start/3-5-10-second selection,
  between-segment admission, cancel and operating-window overrun bound. Matched
  H.264 8-bit previews, WebCodecs frame-clock split/side/seek/loop/step/400% zoom/
  pointer pan; measured speed corrects the associated job estimate. Removing
  a job removes its previews, retaining finished output.
- R5/R6: blocking Smart App Control message/Retry and unsigned Windows folder.
  External Python engine required. No updater, telemetry or GUI full-quality.
  Existing presets and CLI trial defaults remain unchanged; service trial uses
  an explicit settings patch to retain the job's requested codec/fps/models.

## Acceptance

| Criterion | Result | Evidence and limits |
| --- | --- | --- |
| A1 | PASS | Real CPU HTTP/API/SSE tests: token, non-ASCII wrong token, Host/Origin/null Origin, private discovery, second lock, queue/control and endpoint docs |
| A2 | PASS | Electron CPU close/health/reopen/Quit; real Standard GPU close/second-launch focus/Quit/queued checkpoint/restart/done; packaged isolation smoke |
| A3 | PARTIAL | Actual add/estimates/SSE/completion; API reorder/pause/resume/remove; component finalizing 99.9%/errors/actions. Physical Explorer drop and every native menu action NOT RUN |
| A4 | PASS | Fake-clock saved-schedule controller test; API preview/persistence; component grid/list midnight, Save and exceptions |
| A5 | PASS | Mocked retained Queue/Retry and blocking SAC/link tests; native retained-data disconnect and reload/reconnect observed |
| A6 | PASS | Queue/Schedule component tests; Electron real CPU synthetic completion |
| A7 | PARTIAL | Local engine/GUI checks PASS; Windows/Ubuntu CI pending publication |
| A8a | PASS | Plan/scenario/timezone/DST tests; all-page Electron check; actual GPU calibration done |
| A8b | PARTIAL | Real valid/invalid hash/add/remove/queued verify/cancel and consent persistence tests; UI licence/source/explicit acceptance/validation/removal tests. Fresh download and completed UI Verify again NOT RUN |
| A8c | PASS | Settings persistence/new-job defaults; actual login-item registration/unregistration and clipboard diagnostics; advanced validation |
| A8d | PARTIAL | Actual GPU Trial wait/cancel/render/estimate update/paired playback/next-frame/400%/side toggle PASS; physical pan/arrow stepping and sustained loop/seek NOT RUN |
| A8 | PARTIAL | Native real Standard add/close/reopen and checkpoint/resume, plus automated actual app Quit/restart on RTX 4060 Ti. Native reopen used second launch and shutdown used HTTP; physical tray Open/Quit NOT RUN |

## Builds and tests executed

| Check | Result | Actual |
| --- | --- | --- |
| ruff check . | PASS | All checks passed |
| ruff format --check . | PASS | 86 files formatted |
| pyright | PASS | 0 errors, 0 warnings |
| pytest -m "not gpu and not soak" | PASS | 192 passed, 3 skipped, 18 deselected; 95.13 seconds; task-owned basetemp |
| Focused API tests | PASS | 10 passed in 17.33 seconds |
| GUI lint/typecheck | PASS | ESLint/TypeScript exit 0 |
| GUI unit tests | PASS | 12 passed: Queue, Schedule, recovery/SAC, Models, Settings, Plan/DST |
| GUI build/package | PASS | TypeScript/Vite and unsigned win32 x64 folder |
| Electron CPU e2e | PASS | Actual service/CPU fixture/five pages/close/reopen/Quit; 12.1 seconds |
| Scaling | PASS | 1100x700 window, Electron zoom 1.25/1.5, five-page navigation and footer bounds; physical Windows DPI switching NOT RUN |
| GPU Trial/settings/calibrate e2e | PASS | One real-pipeline test, 2.3 minutes |
| GPU Standard restart e2e | PASS | One test, 2.0 minutes; close/second launch/Quit/checkpoint/restart/done |
| Packaged executable smoke | PASS | One test, 4.1 seconds; external engine, sandbox/isolation/no Node, graceful Quit |
| Windows/Ubuntu CI | NOT RUN | Pending first publication; verify before stopping |

CPU e2e's queue network fixture selects the existing CPU passthrough preset,
with a Fast metadata estimate; CI has no production restoration weights. It
tests desktop/API/SSE integration, not GPU restoration quality. Owner GPU and
generated-package checks are opt-in/skipped on CPU CI. Skips are not passes.

## Measured GPU evidence

NVIDIA GeForce RTX 4060 Ti, driver 617.42. Isolated homes; normal owner queue
untouched. No new quality/long-job stability/ETA-accuracy claims.

- Synthetic Trial: 512x288, Standard/Keep/2x/HEVC, 5 seconds/150 input frames,
  300 preview frames at 60 fps. Pipeline 17.4491877 seconds, 8.5963887 input fps.
  Twenty paired playback observations: max timestamp delta 0 microseconds;
  allowed one frame = 16666.7 microseconds. Not proof for all media/seeks.
- Associated job estimate: 50.1198287 to 54.0591085 seconds after Trial.
- Authorized generic 8-second excerpt: 240 input frames, Standard/1080/2x/HEVC,
  one segment. Quit saved queued with no running segment; restart reached
  Done/100%. Resumed pipeline 103.0871554 seconds, 2.3281271 input fps.
- Calibration completed and measured both production models and finalization.
  Results remain external in the operation result and machine profile.

WebCodecs uses one integer frame clock because independent video clocks do not
enforce pair synchronization. The canvas draws pairs within one output frame;
decoded look-ahead is bounded and seeking resets at a keyframe.

## GUI actions, screenshots and logs

Native Computer Use opened the real file dialog, added authorized generic
3-second and 8-second excerpts with Standard defaults, observed Running,
closed the window, checked detached processing, reopened by second launch,
observed retained data after shutdown, reloaded and observed resumed Done/100%.
No screenshot contains real people.

External root: C:\Users\pro\Documents\VideoEnhancer-P1b-evidence.
Synthetic screenshots:

- cpu-gui\add-synthetic.png
- cpu-gui\queue-synthetic.png
- cpu-gui\plan-synthetic.png
- cpu-gui\schedule-synthetic.png
- cpu-gui\models-synthetic.png
- cpu-gui\settings-synthetic.png
- cpu-gui\settings-125-percent.png
- cpu-gui\settings-150-percent.png
- gpu-gui\trial-synthetic.png
- gpu-gui\queue-gpu-synthetic.png
- gpu-gui\plan-gpu-synthetic.png
- gpu-gui\schedule-gpu-synthetic.png
- gpu-gui\models-gpu-synthetic.png
- gpu-gui\settings-gpu-synthetic.png

Related evidence: engine-home\service-start.log and jobs\*\job.jsonl;
gpu-engine-home2\previews\*\{operation.log,result.json};
resume-engine-home\jobs\8240800ddda54e6686627c8e7dc39944\{manifest.json,job.jsonl}.
Failed test traces are ignored under gui/test-results. No media/weights/cache/
node_modules/release/logs are staged.

## Expected, actual, errors and limitations

Expected: detached work persists after close, Quit checkpoints consistently,
next start resumes, Trial compares real frames. Actual: short passing runs above
demonstrate those boundaries.

Initial failures corrected: open Windows log handle blocked removal; startup/
Quit race; non-ASCII bearer; unsupported small BasicVSR++ output; old renderer
footer clipping at zoom; output collision in restart fixture; test/type/import/
packager mistakes. Shared pytest temp denied access: task basetemp resolved it.
Sandbox npm DNS failed; authorized host registry commands succeeded. Final
checks supersede these failed attempts, which were not counted as passes.
API/UI now rejects Standard output below 256 pixels on either side before
processing, without padding/changing the preset. Choose 1080 instead of Keep.
Initial GPU 320x180 fixture hit that existing constraint; successful fixture
is 512x288.

Unresolved / intentionally not run:

- Short checks do not establish long-job stability, quality, ETA accuracy or
  complete WCAG AA compliance. No new soak or full-quality pass.
- Processing fps/percent come from persisted segment statistics; first segment
  can lack measured fps until completion. Finalization has separate step/cap.
- Auxiliary state is session-local; resubmit after service restart. Saved
  job-associated previews are still deleted when that job is removed.
- Download/calibration progress is indeterminate where CLI gives no percentage.
  Disk-required bytes are estimates, not reserved storage.
- Physical tray/drop, fresh download, full pan/loop/seek/accessibility audit and
  login/reboot NOT RUN. Login registration/unregistration actually checked and
  left off. Designer decisions required: none for implemented scope; owner
  acceptance remains for NOT RUN physical interactions and broader media.
- No OS security changes, GUI full-quality, self-contained engine installer,
  merge, main push or next cycle.

## Files and reproduction

Changed: .ai/CURRENT_TASK.md, this report, .github/workflows/ci.yml, .gitignore,
README.md, docs/API.md, docs/GUI.md, new gui/ sources/lockfile/scripts/tests,
src/videoenhancer/service/, cli.py, logging.py, schedule/controller.py, trial.py,
tests/test_service.py, tests/test_service_models.py.

Follow docs/GUI.md prerequisites. From gui/: npm ci; npm run build; npm run dev,
or npm run package then release\VideoEnhancer-win32-x64\VideoEnhancer.exe.
Package references repository .venv\Scripts\python.exe; VE_ENGINE_ROOT/VE_PYTHON
override it. Node 24 used; this machine used ignored .tmp/npm-bootstrap and
equivalent node .../npm-cli.js run ... commands because npm was not on PATH.

Reproduce engine ruff/format/pyright/CPU pytest above; GUI lint/typecheck/test/
build and npm run test:e2e. GPU Trial uses VE_GUI_GPU_HOME and VE_GUI_EVIDENCE;
restart uses VE_GUI_RESUME_HOME and VE_GUI_OWNER_CLIP; package smoke uses
VE_GUI_PACKAGE_EXE. Commands are in docs/GUI.md. Use fresh isolated homes with
verified model/adapter copies and external screenshots, never the owner queue.
