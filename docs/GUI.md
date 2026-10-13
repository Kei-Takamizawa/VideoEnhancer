# Desktop development app

## P1e owner-check update

The P1e update follows the owner-check instructions while retaining the cafe
palette and dock. See `.ai/LAST_REPORT.md` for measured acceptance results.

The five-screen floating dock supports Ctrl+1 through Ctrl+5. The Windows title
bar supports native window controls. Settings offers System, Dark and Light
themes and six zoom levels from 80% to 150%. The first close explains the tray.

Home separates global pause from a job's individual pause. Cancel removes an
unstarted job; a job with completed segments stays in History as Cancelled.
Cancellation discards intermediate work and preserves recorded source/output
videos. History uses grouped virtual rows, file search, selection, removal and
a ten-second Undo. Clear history requires confirmation. Remove and Clear share a ten-second Undo. Their optional file choices are off
by default; a refused file keeps its record visible. Undo restores records only.
Video details also offers a separate guarded Recycle Bin action.
Settings > After processing and Add offer automatic original deletion, off by
default, after output verification and completion of other dependent jobs.

Add requests shared Standard/Fast finish estimates for all selected files.
Estimates add whole-pipeline per-frame deltas for non-default models. Missing
or different-GPU references show uncalibrated with a 25% range. Speed calibration
measures verified installed alternatives. The P1d-2 acceptance report records
remaining accuracy failures; estimated times are not guarantees. AV1 choices use the actual encoder's minimum dimensions.
Models shows the qualified catalog, licence consent, download cancellation,
details and defaults. Active downloads show their reported progress and Cancel
in place of Install. Settings saves edits automatically.

Schedule uses numeric time fields, fifteen-minute arrow increments, quick fill,
exceptions, autosave and eight-second Undo. Its timeline is read-only. Unsaved
previews request the expected scenario after a 400 ms debounce.

Compare selects a range, renders automatically after an 800 ms debounce and
allows installation followed by selection. Up to three models share the
existing synchronized viewer. Early stills are labelled First look; completed
preview files survive cancellation for reuse. The range box supports click placement and Left/Right (Shift: five seconds).
Swipe has a draggable handle and zoom uses segmented buttons. First look comes
from the actual preview render before encoding, without a second model run.
Standalone Trial still uses the existing completed-video preview path.

For isolated packaging while another package is open, set `VE_GUI_PACKAGE_OUT`
to a fresh output folder before `npm run package`. Automated Electron tests use
an isolated `--user-data-dir`; they do not close an existing owner instance.

This unsigned Windows 11 development app uses the existing Python engine. It is
not a self-contained engine installer. No auto-update or telemetry is included.

## Prerequisites and start

Follow [DEVELOPMENT.md](DEVELOPMENT.md) to install Python 3.12, the locked engine
environment including GPU/model extras, FFmpeg and ffprobe, and NVIDIA drivers.
Use Node.js 24 with npm. The desktop requires the repository and its Python
environment to remain installed. A CUDA-capable NVIDIA RTX GPU is required for
the production presets; CPU fixtures are used only in automated engine checks.

From the repository:

```powershell
uv sync --locked --extra gpu --extra models
cd gui
npm ci
npm run dev
```

For the production renderer and unsigned Windows folder:

```powershell
npm run build
npm run package
.\release\VideoEnhancer-win32-x64\VideoEnhancer.exe
```

The packaged app stores the current repository path in
`resources/engine-location.json`. If the repository moves, update its `root` or
set `VE_ENGINE_ROOT` to its absolute path. `VE_PYTHON` overrides the default
`<repository>/.venv/Scripts/python.exe`. `VE_HOME` overrides the default
`%LOCALAPPDATA%/VideoEnhancer`. `VE_FFMPEG_DIR` may point to the folder containing
ffmpeg.exe and ffprobe.exe. Set these variables before launching the app; it
passes them to the detached engine. Do not point test runs at the owner's queue.

The main process attaches to an authenticated existing service, or starts
`pythonw.exe -m videoenhancer.cli serve` on Windows, using the sibling of the
configured Python executable. If that sibling is missing, it logs a fallback to
console Python with hidden-window spawning. Connection discovery remains user-private;
the renderer receives only the connection and a narrow preload bridge. Remote
pages and renderer Node.js access are disabled. See [API.md](API.md).

## Workflow

1. Add videos or drop multiple files on any page. One dialog offers Standard and
   Fast, incremental estimates, more output options, warnings, and Trial. Home
   shows current work and the next videos; completed and failed work moves to History.
2. Download missing built-in weights on Models after reviewing the licence;
   adding a job never silently downloads missing model weights.
3. On Schedule, use a preset or drag a time block and its edges in 15-minute
   increments. Edits save automatically, with an eight-second Undo. Custom opens
   the exact list editor, which has an explicit Save button. Exceptions and
   temporary overrides use the same engine schedule as CLI processing. Planned
   work includes partly processed steps and steps that finish after allowed hours.
4. Close hides the window in the system tray. Open restores it; Pause/Resume
   affects the durable queue. Quit requests a graceful engine shutdown. Reopen
   resumes queued work from validated segments. Closing/crashing the GUI alone
   does not stop the detached engine.
5. Settings apply to new jobs. Start with Windows is off by default; when enabled
   Electron registers the app to start hidden in the tray. Keep the installed
   folder and repository available for that startup entry.

Trial runs between segments under the existing controller's worker lease. It
may wait for an active segment; allowed hours do not delay owner-requested Trials.
It is cancellable, with a hard timeout of at least ten minutes (four times the
estimated render duration when longer). Its
previews are H.264 8-bit and stay outside Git, under the engine home. Removing a
job removes its associated previews while keeping the finished output.

Trial builds a demux-only source index on first use and decodes scene analysis
only near the selected range. Index progress is reported at completed demux
milestones. A matching job manifest takes precedence over the 1 GB oldest-first
index cache. A count mismatch falls back to whole-file analysis and records why.
Full-job analysis still checks the entire video's decoded frame count.

Home's Preview result reads a completed segment or finished output and produces
a short CPU-encoded comparison. It does not run restoration again or acquire the
GPU worker lease. This result viewer compares Original and Enhanced; the separate
Compare workflow can show Original plus three models from the same category.

The comparison canvas uses WebCodecs and one integer frame clock. It draws only
matching frame pairs, rather than trusting two independent video clocks. Arrow
keys step frames, seek selects a frame, Play loops, and zoom allows nearest-neighbour
pan up to 400%. Decoded look-ahead is bounded; seeking resets at a keyframe. If
Chromium cannot decode H.264 using WebCodecs, the viewer shows an error.

## Checks

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Electron e2e launches the actual service and adds synthetic footage through the
GUI. Its network fixture selects the existing CPU passthrough preset, without
production restoration weights. This verifies desktop/API/SSE integration, not
GPU restoration quality. `VE_GUI_EVIDENCE` selects an external screenshot folder;
otherwise ignored `gui/test-results/evidence` is used. Engine regression checks
are listed in DEVELOPMENT.md. GPU acceptance requires separate owner-hardware
checks; measured results and remaining limitations are in `.ai/LAST_REPORT.md`.

Owner-only GPU checks are opt-in. Set `VE_GUI_GPU_HOME` to a fresh isolated home
with verified built-in models and adapter sources, and `VE_GUI_EVIDENCE` to an
external evidence folder; run `npm run test:e2e -- tests/e2e/gpu.spec.ts`.
The separate restart check uses `VE_GUI_RESUME_HOME` (another fresh home with
verified models) and `VE_GUI_OWNER_CLIP` (an authorized short owner excerpt):
`npm run test:e2e -- tests/e2e/resume.spec.ts`. It records no owner screenshots.
To smoke-test the generated owner folder, set `VE_GUI_PACKAGE_EXE` to its absolute
executable path and run `npm run test:e2e -- tests/e2e/packaged.spec.ts`.
These tests remain skipped on CPU-only CI.

If the engine is unreachable, Retry re-reads discovery and starts a service when
needed, while the last snapshot remains visible. Startup diagnostics are in
`%VE_HOME%/service-start.log`; job logs remain in their job folders. Smart App
Control failures show troubleshooting instructions. The app never changes
Windows security settings. Reports and screenshots must use synthetic footage
and exclude private sample names.

## Service reliability

Queue additions return immediately as Preparing, then become ready or show a
preparation error. Active work reports frame progress. Copy details includes
segment diagnostics. Interrupted previews become retryable after restart.

If no event or heartbeat arrives for thirty seconds, the client retains the
last snapshot and reconnects after 1, 2, 5 and 10 seconds. Restore/focus refreshes
service discovery. Windows launches use pythonw and hidden subprocess settings.
Structural queue plans change with their revisions. A separate small progress
stream counts down between processing reports; the desktop limits progress-text
changes to once per second. History grouping is reused across progress updates.

Settings identifies the active speed profile. An RTX 4060 Ti can use the built-in
reference profile without running calibration. A profile measured with another
driver remains usable, with both driver versions shown. Run speed calibration
stays manual, shows an approximate duration, and offers Cancel while running.
The gear in the navigation dock opens Settings.
Tray status refreshes use cached compact job metadata, including with a large History.
Models without a reference show Speed unknown in Add; adding remains allowed.
PQ/HLG warnings apply to each file separately. The service enforces the same
blocking rules as the dialog, including additions from the CLI.

Unresolved deletion recovery appears on the matching History detail or Home.
The notice includes the full retained guard path and Show in folder. Original
and output presence refresh when History opens and in a 60-second background
pass. Do not manually remove retained guards.

The performance generator `tests/perf/prepare_service.py` accepts `--root`,
`--model-home`, `--history-template` and optional `--renderer`. Use fresh external
directories and a genuinely finished synthetic Standard manifest. It measures
three service CPU samples with 1,000 diagnostic-rich terminal rows, ten queued
jobs and one real CUDA Standard job; 5,000 rows are an ungated scaling sample.
`playwright.perf.config.ts` runs ten renderer repeats. Real progress checks use
`VE_REAL_ENGINE_HOME` and `VE_GUI_EVIDENCE` with an isolated running GPU fixture.

## Owner-check changes

- Global pause preserves queue order. A paused card explains that completed parts
  are kept and the current part restarts, with its predicted time.
- Add shows errors and HDR warnings on individual rows. Valid files remain
  addable. The time request has no fixed client timeout and can be cancelled by
  closing the dialog. Folder and codec changes re-check disk space separately;
  the original-deletion switch sends no time request. Finish times refresh every
  30 seconds and on focus, retaining existing values during the refresh.
- Theme choices apply immediately in the renderer and Windows title bar; saving
  runs in the background. Remaining-time values use M:SS or H:MM:SS.
- Action buttons use locally bundled Lucide outline icons. Dock icons, including
  the Settings gear, retain their original shapes.
  Icons describe their actions: History, video preview, hours, logs and verification
  use distinct symbols. Arrows are reserved for directional navigation. Add videos
  shows a plus icon without a second plus in its label.
- History uses uncropped, justified thumbnails and a toolbar Select mode. Its
  detail popup has an in-app player and an external-player fallback. The Undo
  tint shrinks for ten seconds and pauses on hover or keyboard focus. Reduced
  motion uses one-second steps.
- Model cards keep their summary and main Install/Uninstall action. Open the
  card for details, defaults, supported strength choices and verification.
  Default models and models used by unfinished videos cannot be uninstalled.
- Compare fits the largest tiles into the available space. Ctrl+wheel pinches
  from 1x to 8x around the pointer; scroll pans while zoomed, or moves the swipe
  divider at 1x. Zoom buttons remain available. Double-click isolates a pane;
  Full window or F hides controls; Esc returns. Counters have fixed widths.
- Schedule hours remain editable when its large switch is off. Saved hours stay
  visible and dimmed; plan bands remain separate.
- A five-step tour appears on first start. Skip closes it; Settings can replay it.
- Jobs store their first estimate and finish time. Long-video timestamp arrays
  live in a write-once analysis sidecar. Local timing observations supplement
  the built-in profile; live finish times use the operating-hours planner.

The unsigned package still uses the external engine checkout. Only guarded
Recycle Bin operations may remove a recorded user video. URL imports, remote
browser control and face/hair restoration remain outside this cycle.
