# Optional Windows native player

The History player uses a separate `VideoEnhancer-Player.exe` helper when the
optional native payload is present. Tauri and wry are not patched. The helper
hosts a WebView2 composition controller above libmpv's D3D11 surface in one
DirectComposition tree. Native render and wakeup callbacks drive the event
loop; observed properties supply the controls at approximately 10 Hz. The
render path does not synchronously query mpv properties.

The main application loads no libmpv DLL. The helper loads the compatible DLLs
beside its executable when opened and exits on close. Its WebView profile is
separate from the main application. No model, job, settings format, or engine
output path is changed by the player.

## Trust boundaries

The main app resolves a History job ID through the authenticated engine and
checks the original/output files in Rust. It gives the helper a session-only
map of opaque handles to absolute files through inherited stdin. HTML receives
handles, never file paths. Unknown handles and paths supplied in page commands
are rejected.

Controls are compiled by Vite's `player.html` entry and embedded into the helper.
An intercepted private HTTPS origin serves only embedded assets. There is no
file URL or remote page. Navigation, popups and remote resources are blocked;
the page has a strict CSP and release DevTools are disabled.

Both command channels accept version 1 JSON requests with a nonzero numeric
request ID and a tagged command. The allowlist covers open/close, pause, exact
seek, forward/backward step, speed, volume/mute, fullscreen, transform,
Before/After, divider and generation-numbered previews. There is no arbitrary
mpv command/property interface. Numeric arguments are finite and bounded.
Replies contain the matching ID and a result/error. Native failures go to the
application log; the UI receives plain English errors. Pending requests have
bounded timeouts.

Hover uses a separate paused software decoder and a bounded 32-picture cache.
Only the latest generation may publish a picture. It is a nearby keyframe;
main playback seeks and steps use exact native operations.

## Before / After

On first activation, the helper configures a single-clock hstack containing
the output and the original scaled to output dimensions. Two visuals share
the resulting surface. Their clips and offsets produce the split view.
Divider changes affect DirectComposition only, with no filter command or
decode-graph rebuild. The enhanced output provides audio. The comparison graph
is kept after activation so subsequent divider moves do not reconfigure it.
The original must still exist. Different-rate pairing and visible frame
identity require the synthetic acceptance checks; a shared clock alone is not
proof of zero drift.

## Fallback and packaging

Missing helper/DLLs, initialization failures, playback errors or device loss
return to the existing HTML5 History player and its default-player action.
HEVC retains its existing Windows codec notice. Compare models keeps its
existing browser/WebCodecs views.

`VE_LIBMPV_DIR` selects the accepted source-built payload for packaging.
`gui/src-tauri/libmpv.lock.json` authenticates DLL sizes/hashes, the source
archive, the CI artifact manifest and checksum inventory. Packaging refuses
mismatches before copying the payload. Without the variable, the package has
no helper or DLLs and uses HTML5. Runtime DLL hashes are deliberately not pinned:
compatible user replacements are supported under the LGPL.

The package includes `THIRD_PARTY_NOTICES.md`, the complete artifact `LICENSES/`
and `DISTRIBUTION.md`. `sources.tar.zst`, the source manifest and `SHA256SUMS`
are supplied next to the package. Settings has an Open-source licences action.
See `spikes/mpv/LICENSES.md` for the full distribution and replacement terms.

Build from `work` after loading `repo/local-env.ps1`:

```powershell
npm run build --prefix repo/gui
cargo build --locked --manifest-path repo/gui/src-tauri/player/Cargo.toml
cargo test --locked --manifest-path repo/gui/src-tauri/player/Cargo.toml
```

Measurements and synthetic media remain outside Git. `gui/scripts/player-fixtures.py`
generates the fixture recipes, and `player-acceptance.py` measures only its own
helper processes. Its close path waits for WebView children before deleting its
own profile. A failed deletion is reported and never retried through another path.
