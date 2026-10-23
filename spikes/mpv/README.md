# Embedded mpv spike (VE-P1e-3b)

This separate Windows Rust application probes two ways to put HTML controls
over native video. The product player and package are unchanged. The spike is
**partial**: playback logs exist for both paths, but visual transparency and
input have not been verified. Do not adopt either path yet.

- **B1:** raw WebView2 composition controller and a transparent HTML visual above
  a libmpv D3D11 render-API swap chain in one DirectComposition tree. Uses tao
  for the host window. No Tauri fork was made; product integration would need a
  custom WebView2 host or an extension to Tauri/wry, not just a standard Tauri
  window option.
- **B2:** libmpv `wid` in the native owner window, plus an owned, undecorated,
  transparent wry WebView2 window over its client area. Position and size
  follow owner events; Windows owns the z-order/minimise relationship.
- **B3:** not built. Neither transparent approach has been shown to fail, so
  the task's fallback condition has not been established.

The HTML contains play/pause, seek, time and fullscreen controls. Keyboard
handlers cover space, arrows and F; wheel adjusts volume. The video area has
click and double-click handlers. The hover box sits above the seek bar with
the timestamp below the image. **The thumbnail is a placeholder**, not an
implemented preview decoder. B1 currently forwards basic left-pointer events;
wheel, double-click classification, capture during dragging and full keyboard
integration need implementation/verification before this is usable.

## Run

From `work`, using PowerShell:

```powershell
. .\repo\local-env.ps1
.\repo\spikes\mpv\download.ps1
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\audit.py --output .\evidence\VE-P1e-3b\binary-audit.json
$env:CARGO_TARGET_DIR = "$PWD\cache\mpv-lgpl\spike-target"
cargo build --offline --locked --manifest-path .\repo\spikes\mpv\Cargo.toml
& .\repo\.venv\Scripts\python.exe .\repo\spikes\mpv\smoke.py
```

The scripts require the existing repo Python, cached Rust crates, Windows tar,
RTX NVENC support and the installed Consolas font. No package-manager restore,
driver or Runtime installation is performed. The binary candidate is not
cleared for distribution; see [LICENSES.md](LICENSES.md).

To open a generated file for manual checks (replace `B1` with `B2` to compare):

```powershell
Remove-Item Env:VE_MPV_SPIKE_AUTOCLOSE_MS -ErrorAction SilentlyContinue
& .\cache\mpv-lgpl\spike-target\debug\mpv-embedding-spike.exe B1 "$PWD\cache\mpv-lgpl\libmpv-2.dll" "$PWD\scratch\mpv-spike\h264-1080p30.mp4" "$PWD\scratch\mpv-spike\profile-B1"
```

The profile directory must already exist under `work/scratch`. The prototype
sets process-local APPDATA and LOCALAPPDATA inside that profile before starting
native libraries. The DLL loads
only when this separate prototype starts; it is never loaded by product Home.
`VE_MPV_SPIKE_AUTOCLOSE_MS` supports bounded automated playback smoke tests.
NDJSON telemetry reports decoder, playback time, source dimensions and the
current mpv frame-drop counter. These are not first-frame timings, visible
frame verification or 60-second measurements.

## Remaining work

1. Complete the dependency/source/licence audit before shipping any binary.
2. Obtain GUI tool access, visually verify both paths, implement missing B1
   input forwarding, then verify focus, drag capture, resize, maximise,
   fullscreen, minimise/restore and real 100/125/150% monitor transitions.
3. Verify all four codecs, 10-bit SDR and rotation in the displayed picture.
4. Implement a real hover decoder and two-instance synchronisation probe.
5. Measure both approaches against the unchanged product HTML5 player with
   raw five-load/20-seek samples, burnt-in frame steps, 60-second drops,
   per-process GPU/CPU samples, close residuals and preview/sync costs.

Do not infer visual success from a successful DirectComposition call or
`d3d11va` log. The initial GPU inventory contained other desktop clients;
the task's exclusive GPU measurement condition was not established.

CPU-only CI could build the isolated Windows crate, check pinned hashes and
validate state/IPC logic once tests exist. It cannot establish hardware decode,
real desktop alpha/z-order, DPI, frame presentation or GPU memory behaviour.
The spike is deliberately not added to product CI.

The retained native build cache, fixture files and WebView2 profiles belong
outside Git. At cycle end close spike processes, record each scratch item's
size, and remove only the cycle-created scratch directories after validating
their absolute paths against `work/scratch`. The runner leaves its files for
the cycle's recorded cleanup, including on failure.
