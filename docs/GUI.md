# Desktop development app

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
`python -m videoenhancer.cli serve`. Connection discovery remains user-private;
the renderer receives only the connection and a narrow preload bridge. Remote
pages and renderer Node.js access are disabled. See [API.md](API.md).

## Workflow

1. Add videos or drop multiple files on Queue. One dialog shows estimates for
   both presets, output choices, warnings, and Trial.
2. Download missing built-in weights on Models after reviewing the licence;
   adding a job never silently downloads missing model weights.
3. Paint Schedule or edit its list, then Save. Exceptions and temporary overrides
   use the same engine schedule as CLI processing. Plan shows engine projections.
4. Close hides the window in the system tray. Open restores it; Pause/Resume
   affects the durable queue. Quit requests a graceful engine shutdown. Reopen
   resumes queued work from validated segments. Closing/crashing the GUI alone
   does not stop the detached engine.
5. Settings apply to new jobs. Start with Windows is off by default; when enabled
   Electron registers the app to start hidden in the tray. Keep the installed
   folder and repository available for that startup entry.

Trial runs between segments under the existing controller's worker lease. It
may wait for an active segment or allowed hours; it is cancellable. If it reaches
the operating-window deadline plus its own excerpt length, it aborts. Its
previews are H.264 8-bit and stay outside Git, under the engine home. Removing a
job removes its associated previews while keeping the finished output.

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
