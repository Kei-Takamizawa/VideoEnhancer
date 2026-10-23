# Embedded mpv spike (VE-P1e-3b)

This Windows-only Rust application evaluates native mpv beneath HTML controls.
It is independent of the product's Tauri crate, player and package. It is not
included in the product build, pytest, or GUI jobs. The repository-wide Python
format/lint checks still apply to its scripts.

## Hosts and probes

- **B1:** a custom WebView2 composition controller above a libmpv D3D11 render
  API swap chain in one DirectComposition tree. No Tauri fork is included.
- **B2:** mpv `wid` and an owned transparent wry/WebView2 window over the video.
- **HTML5:** a minimal local WebView2 page with the product's kind of `<video
  controls>` element; it is not the product's media transport. A local HTTP
  range server supplies the identical synthetic files.
- **AB:** two native child windows, each with an independent mpv instance;
  paired playback/seek commands and sampled time positions measure drift.
- **STACK:** one mpv, two video inputs and `lavfi-complex` hstack. The filter
  graph shares an output clock; capture pairs can check visible frame equality.

Play/pause, seek, time and fullscreen controls use transparent CSS with shadows.
B1 forwards wheel, double-click and captured pointer drags, and routes keyboard
events to the HTML layer. The hover preview uses a second paused libmpv software
render context, renders a 320x180 frame into memory and delivers a PNG data URI
to the image above the bar. It is no longer a placeholder.

The DLL candidate is **not cleared for distribution**. A real minimal source
build attempt and its failure are recorded in [source-manifest.json](source-manifest.json).
See [LICENSES.md](LICENSES.md) for unresolved obligations. Only a checked source
build and complete dependency audit can clear a future product payload.

## Build and run

From `work`, in PowerShell:

```powershell
. .\repo\local-env.ps1
.\repo\spikes\mpv\download.ps1
$env:CARGO_TARGET_DIR = "$PWD\cache\mpv-lgpl\spike-target"
cargo build --offline --locked --manifest-path .\repo\spikes\mpv\Cargo.toml
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\smoke.py --generate-only
```

The existing repository Python, Rust cache, system Consolas font and RTX NVENC
encoder generate the five numbered local fixtures. They have a frame number at
the top and another beneath the transparent bar. Fixtures and profiles are
temporary and stay under `work/scratch`.

Examples of bounded self-tests (each closes its own process):

```powershell
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\measure.py --mode B1 --phase gui --label gui-b1-new
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\measure.py --mode B2 --phase bench --clip hevc-main10-1440p60.mp4 --label hevc-b2-new --seconds 60
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\measure.py --mode HTML5 --phase bench --clip h264-1080p30.mp4 --label html5-new --seconds 60
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\measure.py --mode B1 --phase preview --label hover-new
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\measure.py --mode AB --phase sync --label two-new --seconds 60
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\measure.py --mode STACK --phase sync --label stack-new --seconds 60
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\frame_check.py
```

Use a new label per run to retain all samples. The measurement runner records
five load samples, twenty deterministic random seeks, forward/forward/backward
steps, sixty one-second process-tree GPU/CPU samples, and five samples after
closing the player. Raw NDJSON, errors, JSON results and captures go to
`work/evidence/VE-P1e-3c1` by default. FFmpeg reference frames and profiles remain
scratch artifacts until the cycle's recorded cleanup.

Driver exit 0 means analysis finished. Inspect individual JSON status/failure
fields and frame comparisons; a completed comparison can correctly report a
baseline FAIL. The overlay phase can capture B2's own HTML surface including
its alpha channel; it is distinct from capturing the final desktop composite.

## Measurement and capture boundaries

Native timing ends at `MPV_EVENT_PLAYBACK_RESTART`, after the render/present
loop has run; HTML5 timing uses `requestVideoFrameCallback`. These measure
different software presentation signals, not physical display photons. Raw
samples, capture checks and sampling limitations must accompany comparisons.
HTML5 frame stepping is an exact-FPS seek attempt, independently checked
against burned-in numbers; the product has no new frame-step UI.

The process tree's Windows PDH dedicated/shared allocations and CPU time are
sampled through the existing read-only PDH helper. The sum is process-scoped,
not a device-wide VRAM number. HTML5's actual decoder name is collected via
WebView2's CDP Media domain. Unsupported media produces an evidenced unavailable
result rather than fabricated timings or a Runtime/codec installation.

The test mode accepts JSON requests on its own stdin. Input targets are only
its own HWNDs or its own WebView2 instance. No `SendInput` is used. State tests
use own-window messages/APIs and synthetic `WM_DPICHANGED`; they never change
display settings. A synthetic DPI message is not a real monitor move.

Capture uses DXGI duplication cropped to the own window, refusing a foreign
foreground, or Windows.Graphics.Capture for the own HWND. Only the crop/window
is saved. No PrintWindow or BitBlt is used. Black DXGI output is retained as
failure evidence. WGC includes B1's composed video/HTML but may omit B2's owned
overlay: a video-only WGC image does not prove B2 transparency. The alpha test
requires visible controls plus matching textured video in the control bar's
unpainted padding; painted glyphs/track are excluded.

The prototype isolates process-local APPDATA/LOCALAPPDATA and the WebView2
profile beneath scratch before native libraries start. It loads libmpv only
when this separate player program starts. The product's Home never imports it.

## Integration risks and CI

B1 needs a reviewed custom composition host or a Tauri/wry extension in the real
player. B2 needs exact owner/overlay placement, focus and lifecycle coordination.
Both need device-loss recovery, proper event-driven scheduling and broader DPI,
input and Runtime-update testing before product integration. No UI polish or
production-readiness claim follows from this spike.

CPU CI can lint the scripts and build an isolated Windows host. It cannot prove
hardware decoding, alpha/z-order, real DPI moves, display timing or GPU memory.
The measured recommendation, failures and remaining product decisions are in
`.ai/LAST_REPORT.md`; final commit and CI publication belong to the operator.

At cycle end, close only cycle-owned processes, inventory cleanup paths/sizes
in the report, validate their absolute paths and remove the generated scratch
files. Keep the verified library/source/build cache for P1e-3c. Never clean owner
data or work around a rejected deletion.


## P1e-3c1 event-driven B1

The current B1 host registers both `mpv_set_wakeup_callback` and
`mpv_render_context_set_update_callback`. Callbacks only mark pending work and
wake the Tao event loop. Rendering and `mpv_render_context_update` stay on the
UI/render thread; rendering requires `MPV_RENDER_UPDATE_FRAME`. There is no
8 ms heartbeat or 2 ms polling loop. A 100 ms deadline serves time display and
bounded command timeouts. The existing flip-sequential composition swap chain
is retained. No latency-waitable-object change was needed to meet the measured
single-player targets. Commands use mpv's async API so the UI can service
render requests while mpv processes a load or seek.

The old step-completion path queried `time-pos` even for load/seek requests.
Suppressing that synchronous query for non-step commands removed a reproducible
~200 ms first-frame penalty. Synchronous control telemetry is also deferred
while a tracked command is pending. The pinned upstream `vo_libmpv.c` has a
200 ms timeout while waiting for the application to render the next frame.
The report separates the baseline, profiling and each intermediate experiment.

`STACK` now uses the same composition host as B1. For comparison experiments,
set `VE_MPV_GRAPH` to a reviewed `lavfi-complex` graph; the runner provides the
second input through `VE_MPV_EXTERNAL`. The default graph is hstack. A single
filter output has one output clock; visual pairing still needs capture checks.
The product has not adopted any of these experiments.

Hover requests drained in one UI iteration are coalesced to the newest request;
older test requests receive `cancelled:true`. Preview uses a separate paused
software decoder, `hr-seek=no`, keyframe seeks, 320-pixel filter output and an
FIFO cache bounded to 32 thumbnails (request positions quantized to
100 ms). It shows a nearby keyframe, not an exact target frame. The main
player continues to use exact seeks and native frame steps. New requests
supersede queued seeks; an old in-flight decode finishes and is discarded
before the newest position is sought; this is not a separate worker or a pre-generated
strip. Software decoding still happens at the source resolution before scale.

Example measurements (PowerShell, after the environment setup above):

```powershell
$env:VE_MPV_CAPTURE = '0' # timing only: skip frame-step captures
python .\repo\spikes\mpv\measure.py --mode B1 --phase bench --label timing-new --seconds 60
Remove-Item Env:VE_MPV_CAPTURE
python .\repo\spikes\mpv\measure.py --mode B1 --phase gui --label alpha-new
python .\repo\spikes\mpv\measure.py --mode B1 --phase preview --label preview-new
python .\repo\spikes\mpv\measure.py --mode B1 --phase lazy --label lazy-new
```

New evidence defaults to `work/evidence/VE-P1e-3c1`; `VE_MPV_CYCLE` overrides
this in both host and runner. `VE_MPV_DLL` selects another DLL in the runner.
Detailed render counters are off unless `VE_MPV_PROFILE` is set. The stdin
command protocol remains enabled for measurements. Capture runs are separate
from timing runs. Always use a fresh label and retain failed runs.

`--phase lazy` starts B1 with `VE_MPV_DEFER_OPEN`: the host remains alive without
loading libmpv until the `open-player` command. It records loaded module maps
before/open/after close, DLL loading plus mpv initialization, full composition
open time and five post-close CPU/RSS/PDH samples. libloading owns the native
module handle; all mpv instances and render contexts are dropped at close.
Callbacks are unregistered before their boxed contexts and DLL are released.

## P1e-3c1 source-build limitation

Part A remains OPEN. The official portable MSYS2 archives passed checksum
verification, but both native UCRT64 and mpv-winbuild-cmake prerequisite routes
stopped at GnuPG key initialization/import. WSL is absent. Neither source
compilation nor a second clean reproduction happened. `toolchain-probe.ps1`
reproduces the bounded prerequisite probe; `source-build.ps1` remains the
historical MSVC diagnostic. Neither is a complete successful source-build
recipe. See the manifest for exact versions, hashes, commands and missing proof.
The prebuilt DLL is measurement-only and must never ship.
