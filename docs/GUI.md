# Desktop development app

## P1c-3 screens

Home offers Change mode for prepared jobs that have not started. Problem opens
details before anything is copied. The attention banner and rail dot count only
unseen failures; displaying a History card or dismissing the banner records it
as seen. History uses Today, Yesterday, or a weekday and date.

The Add dialog shows its output summary beside More options. Its Cleanup and
Smoother motion selectors contain installed models; Bigger picture currently
offers Standard resize. Try models first preserves dialog choices, and Use this
returns a model selection to the dialog.

Schedule previews expected, best and worst finish times. Work bars expose progress
and finish-time tooltips. Exceptions can be edited directly, including multiple
time windows. Add a day opens the one-day editor. Right-click, the block's menu
button, Menu, or Shift+F10 opens Only on this date. Every save restarts the eight
second Undo timer. Settings groups Defaults, App, Advanced, Diagnostics and About.

Models uses category cards, explicit licence consent, Verify again, Details,
Make it my default and Remove. Unknown speed is shown as not measured. The
optional publisher catalog is not qualified yet; existing built-ins and your
own compatible models remain available. Defaults affect new jobs only.

Compare renders Original and up to three installed models of one category, with
one synchronized frame clock. Its initial view is side by side; uncheck Side by
side for a swipe view and choose Left/Right. Zoom and panning apply to every
picture. Arrow keys step, Space toggles playback, and Loop can be switched off.
Use this is disabled for a job that has started. Back returns to the opener and
leaves admitted work running; Cancel explicitly stops it. There is no learned
size comparison yet. The range control uses the middle when no motion ranking
is available. Thumbnail-box dragging and rendering only missing selections are
still outstanding.

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
GPU worker lease. The current viewer compares Original and Enhanced; the proposed
multi-model catalog and multi-model Compare workflow are not implemented yet.

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

## P1c partial reliability update

Queue adds return immediately as **Preparing…**, then become ready or show a
preparation error. The current segment reports its step and frame-based progress.
Copy details includes the tail of the segment diagnostics. Controller errors
are visible with their timestamp. Interrupted previews become retryable after
service restart.

If no event or heartbeat arrives for 30 seconds, the client keeps its last
snapshot, shows **Reconnecting…**, and retries after 1, 2, 5 and 10 seconds.
Retries refresh the service discovery; restoring/focusing the window also
reconnects. This cycle retains the P1b Queue/Plan/Schedule/Models/Settings screens.
Home, History, redesigned hours editing and multi-model Compare are not shipped.
Console-free Electron cold start is not established; the Electron launch still
needs the planned pythonw selection. Do not treat this draft as P1c completion.
