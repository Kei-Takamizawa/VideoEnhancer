# VE-P1e-3b / Cycle P1e-3b

Status: PARTIAL

## Outcome and scope

B1 and B2 were built and tried as an isolated Windows Rust application.
Both paths advance playback time and report `hwdec-current=d3d11va` for all
requested codec families. This is playback-log evidence, not proof of visible
transparency or a completed spike. Part A's complete dependency licence audit,
the visual/input/window checks, Part C's comparative measurements, actual hover
decoding and the two-player synchronisation probe remain incomplete.

No product, package, engine, settings, media-path or CI file was changed.
No dependency restore/install was necessary: existing cached Rust crates and
repo Python were used. Only the pinned external mpv/FFmpeg candidates were added.

## Start and Git verification

- Execution terminal: Windows PowerShell on the development PC.
- Task ID read completely from `.ai/CURRENT_TASK.md`: VE-P1e-3b.
- Initial branch: `claude/project-thread-6lra47`; HEAD `69cfac4`.
- Initial tracked/untracked status: clean.
- Normal read-only Git execution failed with `Program 'git.exe' failed to run:
  Access is denied`. The prescribed escalated read-only check succeeded.
- There is no local `main` ref: `git diff main` failed with `unknown revision`.
  The task identifies `aa107af` as the main baseline; comparison against that
  existing commit showed no differences in `gui/`, `src/`, `tests/` or `.github/`.
- `.ai/CURRENT_TASK.md` already differs from `aa107af` at initial HEAD. It was
  left intact. This pre-existing task-definition difference prevents a literal
  `diff main` allowlist assertion even after restoring a local main ref.
- No fetch, branch mutation, staging, commit, push or merge was performed.
  The repository assigns those actions to the operator.

## Part A: candidate, not cleared for distribution

Official project release:
[2026-10-23-0fae469547](https://github.com/zhongfly/mpv-winbuild/releases/tag/2026-10-23-0fae469547).
Build run: [39897995385](https://github.com/zhongfly/mpv-winbuild/actions/runs/39897995385).
Builder workflow revision: `b120d7d8a64d17bd40b893f585429ef3845ac766`.
mpv revision: `0fae4695470bf2c0c06762503292ee5379f62f62`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| mpv-dev-lgpl-x86_64-20261023-git-0fae469547.7z | 28983807 | 81cf5b30b5729be3647eac85d70c05ea0b8dfea02dfa7c4eefed1f23a0a38a52 |
| libmpv-2.dll | 101511680 | b9f3ddd1ef2d43d6424addb835824ddb4e1e5f72c067e2816f0e09b19a6c4752 |
| ffmpeg-lgpl-x86_64-git-c569ebacc.7z | 25700913 | 3ac8067c9f7d7588521651c86b4bc5d7cc43fe9e5fed3214d8d6427421a059f5 |
| ffmpeg/ffmpeg.exe | 91134464 | 201f7112b9b76aaec64b5dbaa56b39335e962d8b9a1d2ef0de8a5a099dabca69 |

Both archive hashes match the official release API's digests. `download.ps1`
pins these versions/hashes, verifies cached downloads too, and rejects archive
path traversal. The DLL version is `mpv v0.41.0-1288-g0fae46954`; the DLL reports
FFmpeg `N-127952-gc569ebacc`. Its embedded mpv configuration contains `-Dgpl=false`.
The companion FFmpeg configuration contains `--enable-version3`, with no
`--enable-gpl` or `--enable-nonfree`.

Only one DLL is in the mpv archive. Its mpv portion is configured LGPL, but
licensing of the complete statically linked dependency aggregate is **OPEN**.
There are no dependency/version/licence manifests or licence texts in the
archive. The companion EXE configuration does not prove the exact embedded
FFmpeg configuration. No source build was attempted; this cycle did not produce
a fully audited alternative. Accordingly Part A's accepted-binary condition
has not been met, and the candidate must not be bundled in the product.

`spikes/mpv/LICENSES.md` records the shipping obligations and missing proof.
`evidence/VE-P1e-3b/binary-audit.json` contains every extracted file's hash,
size, version and the full configurations. The complete configurations are
also reproduced below under Configuration evidence.

## Part B: embedding evidence

| Check | B1 composition | B2 owned overlay |
| --- | --- | --- |
| Build and window initialisation | PASS | PASS |
| Moving playback time, 5 codec fixtures | PASS, log evidence | PASS, log evidence |
| Actual transparent HTML over moving picture | NOT_RUN | NOT_RUN |
| Halo, flicker, tearing, z-order screenshots | NOT_RUN | NOT_RUN |
| Pointer, wheel, keyboard, focus | NOT_RUN | NOT_RUN |
| Click-to-pause, double-click fullscreen | NOT_RUN | NOT_RUN |
| Resize, maximise, fullscreen, minimise/restore | NOT_RUN | NOT_RUN |
| Real DPI 100/125/150%, multi-monitor move | NOT_RUN | NOT_RUN |

B1 creates a hardware D3D11 device, a composition swap chain, and a
DirectComposition visual tree. mpv renders to its D3D11 texture through render
parameters 21/22; WebView2 uses `ICoreWebView2CompositionController` with alpha
zero above the video visual. Initialisation and recurring render/present calls
returned without logged errors. The archive omits `render_d3d11.h` even though
`render.h` declares the D3D11 constants; the upstream
[D3D11 API documentation](https://github.com/mpv-player/mpv/blob/0fae4695470bf2c0c06762503292ee5379f62f62/include/mpv/render_d3d11.h)
describes the device/texture pointer structures used here.

B1 uses a custom WebView2 host, not the product's normal Tauri/wry controller.
No fork was made. Product integration needs a reviewed composition-host
extension or custom host. The current `window.rs` theme/background handling
would need to distinguish the player, and `main.rs` would need lazy creation
and teardown. These are proposals only; neither product file changed.
Its risks include focus/input forwarding, UI-thread rendering stalls, device
loss, Runtime updates, DPI translation and the cost of maintaining the host.
Basic left-pointer forwarding exists; wheel forwarding, double-click
classification and reliable drag capture are still missing from B1.

B2 uses mpv `wid`, `vo=gpu-next`, `gpu-api=d3d11`, and an owned transparent wry
window. Owner movement/size/DPI events update overlay bounds; Windows provides
the owned-window relationship. This is not proof that all transitions work.
It needs less renderer integration but adds focus, activation, z-order,
multi-monitor and lifecycle risks across Tauri/wry/Runtime updates. A product
implementation would need explicit owner and player-window lifetime handling.

Both prototypes have transparent CSS controls, a seek bar, time, and a preview
position above the bar with its time below. The preview image is a placeholder.
No thumbnail decoder or before/after synchronisation implementation exists.
B3 was intentionally not built: neither B1 nor B2 has been demonstrated to
fail transparency, so the fallback-only condition has not been established.

### GUI access limitation

Computer Use listed the B1 window. The attempted window-state/screenshot call
was rejected with the exact text:

> Computer Use was not approved to use mpv-embedding-spike

No screenshot or input was obtained. No alternate capture or UI automation
was used to bypass the rejection. A user-access question was issued; absent
approval, all dependent visual and interaction checks remain NOT_RUN.
Subsequent automatic smoke launches only collected application telemetry and
exited after five seconds; they did not capture or manipulate the desktop.

## Part C: runs and measurement gaps

All media were generated locally with frame numbers burnt in. The fixture
commands and FFmpeg metadata are retained outside Git. All clips are 65 seconds.
Metadata confirmed H.264 8-bit 1080p30, HEVC Main10 1440p60, AV1 10-bit 1440p60,
and VP9 8-bit 1080p60. The initial HEVC rotation remux using `rotate=90` did not
write a display matrix: that initial smoke is not a valid rotation test.
It was corrected to input `-display_rotation 90` and only rotation was rerun.
Displayed orientation still needs GUI verification. MKV/WebM/MOV were not tried.

Five-second smoke observations, **not** the requested 60-second benchmarks:

| Fixture/run | B1 last time / drop counter | B2 last time / drop counter | hwdec, both | Exit, both |
| --- | --- | --- | --- | --- |
| H.264 initial bounded smoke | 3.966667 / 5 | 3.633333 / 0 | d3d11va | Autoexit observed; returncode not captured |
| H.264 numbered runner | 4.966667 / 6 | 3.666667 / 0 | d3d11va | 0 / 0 |
| HEVC Main10 runner | 4.000000 / 12 | 3.650000 / 0 | d3d11va | 0 / 0 |
| AV1 10-bit runner | 3.983333 / 12 | 3.633333 / 0 | d3d11va | 0 / 0 |
| VP9 runner | 3.983333 / 12 | 3.650000 / 0 | d3d11va | 0 / 0 |
| HEVC initial invalid rotation fixture | 3.966667 / 5 | 3.633333 / 0 | d3d11va | 0 / 0 |
| HEVC corrected display-matrix fixture | 3.966667 / 5 | 3.633333 / 0 | d3d11va | 0 / 0 |

The B1 counters include startup drops. Differing last sample timestamps and
short run lengths make these unsuitable for a performance comparison. Earlier
exploratory B1 launches confirmed initialisation only; one failed scratch-path
validation, and sandbox-launched windows were not visible to Computer Use.
They were not gated measurement runs. Their logs have not been promoted to
first-frame, seek or performance results.

NR = NOT_RUN for each individual requested metric: first-frame time (5 samples,
median), seek latency (20 samples, median/worst), exact forward/back frame
accuracy, 60-second dropped frames, per-process dedicated GPU memory, CPU,
and memory remaining after closing.

| Fixture | Player | First frame | Seek | Frame step | 60s drops | GPU/CPU/close |
| --- | --- | --- | --- | --- | --- | --- |
| H.264 1080p30 | B1 | NR | NR | NR | NR | NR |
| H.264 1080p30 | B2 | NR | NR | NR | NR | NR |
| H.264 1080p30 | Product HTML5 | NR | NR | NR | NR | NR |
| HEVC Main10 1440p60 | B1 | NR | NR | NR | NR | NR |
| HEVC Main10 1440p60 | B2 | NR | NR | NR | NR | NR |
| HEVC Main10 1440p60 | Product HTML5 | NR | NR | NR | NR | NR |
| AV1 10-bit 1440p60 | B1 | NR | NR | NR | NR | NR |
| AV1 10-bit 1440p60 | B2 | NR | NR | NR | NR | NR |
| AV1 10-bit 1440p60 | Product HTML5 | NR | NR | NR | NR | NR |
| VP9 1080p60 | B1 | NR | NR | NR | NR | NR |
| VP9 1080p60 | B2 | NR | NR | NR | NR | NR |
| VP9 1080p60 | Product HTML5 | NR | NR | NR | NR | NR |
| HEVC rotated portrait | B1 | NR | NR | NR | NR | NR |
| HEVC rotated portrait | B2 | NR | NR | NR | NR | NR |
| HEVC rotated portrait | Product HTML5 | NR | NR | NR | NR | NR |

Reason: the best visually working approach has not been established because GUI
access was denied. The GPU inventory also showed other desktop clients; the
exclusive GPU condition was not established. No owner processes were stopped.
No gated measurement samples were collected. Hover preview latency and both
before/after approaches' 60-second drift/cost are NOT_RUN and not implemented.
The historical 80-90 MB HTML5 residual is not new evidence from this cycle.

### Final isolated playback repeat

After explicitly isolating APPDATA/LOCALAPPDATA, all ten playback runs again returned 0. Original logs were retained in pre-isolation/; corrected intermediate rotation logs remain in rotation-fixed/. Final per-run logs are at the cycle evidence root.

| Run | Last time (s) | Last frame-drop counter | Decoder |
| --- | ---: | ---: | --- |
| av1-10bit-1440p60-B1.jsonl | 3.966667 | 12 | d3d11va |
| av1-10bit-1440p60-B2.jsonl | 3.650000 | 0 | d3d11va |
| h264-1080p30-B1.jsonl | 3.966667 | 5 | d3d11va |
| h264-1080p30-B2.jsonl | 3.633333 | 0 | d3d11va |
| hevc-main10-1440p60-B1.jsonl | 3.983333 | 12 | d3d11va |
| hevc-main10-1440p60-B2.jsonl | 3.650000 | 0 | d3d11va |
| hevc-rotation-B1.jsonl | 4.000000 | 6 | d3d11va |
| hevc-rotation-B2.jsonl | 3.633333 | 0 | d3d11va |
| vp9-1080p60-B1.jsonl | 3.983333 | 12 | d3d11va |
| vp9-1080p60-B2.jsonl | 3.633333 | 0 | d3d11va |

## Part D: provisional recommendation

Continue evaluating **B1** first because a single composition tree avoids the
second-window tracking inherent in B2 and matches the required transparent
layout in structure. This is a candidate for the next spike, not an approved
P1e-3c implementation choice: visual/input verification could change it.

Before P1e-3c, finish the licence audit, B1 input/capture/focus implementation,
real hover decoder, synchronisation probe and all measurements. P1e-3c would
then need lazy DLL loading, D3D device-loss recovery, playback lifecycle/error
handling, approved transparent controls, exact stepping, preview scheduling,
before/after synchronisation, and the corresponding host integration.

Provisional uncompressed payload is 101.511680 MB for the candidate DLL alone;
its archive is 28.983807 MB. Licence/source materials and any final dependency
layout are additional and unmeasured. No DLL was added to the package.
Player-open startup cost and the P2 Home-ready median <=765 ms gate were NOT_RUN.
Future loading must occur only when opening the player, never during Home.

Keep the spike outside product CI. An isolated Windows CPU job could build it,
check hashes and later test IPC/state handling. GPU decoding, alpha/z-order,
presentation/seek timings, real DPI moves and GPU residuals need a dedicated
interactive GPU runner; a Linux runner cannot exercise this Windows host.
No claim is made that Windows/Ubuntu CI passed on a final commit: there is no
new commit, and CI publication belongs to the operator.

## Validation, failures and intentionally unrun work

| Check | Result |
| --- | --- |
| Isolated Rust build, final locked/offline build | PASS |
| Clippy with `-D warnings`, final run | PASS |
| Rust formatting check | PASS |
| Git tracked whitespace check | PASS after removing one final blank line |
| Spike Python ruff lint/format, final runs | PASS |
| Cached download verification/extraction script | PASS |
| DLL hash/configuration/version inventory script | PASS, limited audit scope above |
| Playback runner, initial five fixtures x two approaches | PASS for advancing playback/hwdec/exit only; rotation fixture invalid |
| Corrected rotation x two approaches | PASS for playback logs/exit only |
| GUI visual/input/window/DPI checks | NOT_RUN: tool access rejected |
| Product CPU/ruff/pyright/GUI lint/typecheck/unit/build | NOT_RUN, task waives reruns when product files unchanged |
| Windows and Ubuntu final-commit CI | NOT_RUN, no new commit |

Failures encountered and corrected: initial Rust build had an HMODULE argument
type mismatch and omitted non-exhaustive event fields; initial clippy found
suspicious assignment spacing; initial Python lint found import/line-length
issues; initial FFmpeg filter quoting failed; canonical path prefix comparison
initially rejected the scratch profile; first metadata-inspection subprocess
used an unresolved relative executable path; the first rotation remux lacked
rotation metadata. Final checks above succeeded after correction.

Earlier exploratory runs set explicit WebView2 profiles and scratch TEMP/TMP,
but did not explicitly override roaming/local AppData for native dependencies.
The final prototype now sets both process-local data roots inside its scratch
profile before creating native-library threads. The final isolated playback
repeat is recorded separately below. Incidental external writes from the
earlier runs were not audited; no owner directories were inspected or cleaned.

A rebuild once failed because an exploratory prototype held the EXE open.
`Stop-Process` raised an internal NullReferenceException; targeted `taskkill`
terminated the cycle-owned process and child. Another targeted PID had already
exited. No owner application was terminated. Official GitHub requests needed
network escalation; an initial request for the builder's `master` tree returned
404, then the release's actual workflow revision on `main` was retrieved.

## Changed files

- `.ai/LAST_REPORT.md`
- `spikes/mpv/Cargo.toml`, `spikes/mpv/Cargo.lock`
- `spikes/mpv/src/main.rs`, `spikes/mpv/src/composition.rs`, `spikes/mpv/src/mpv.rs`
- `spikes/mpv/controls.html`
- `spikes/mpv/download.ps1`, `spikes/mpv/audit.py`, `spikes/mpv/smoke.py`
- `spikes/mpv/README.md`, `spikes/mpv/LICENSES.md`

## Disk and cleanup

Decimal GB; logical file lengths, not allocated sizes. Overlapping rows must
not be summed. Dependency restore: 0 bytes. Installed toolchains: 0 bytes.
Existing cached Rust/Python tools were reused. The mpv cache is retained for
the next cycle; its native prototype build is reported separately within it.

Start: C free 299.012853760 GB; D free 1005.166419968 GB.

| Workspace folder / role | Start GB | End GB |
| --- | ---: | ---: |
| repo: checkout and existing .venv | 3.526660963 | 3.526756592 |
| package: current portable candidate | 0.005764162 | 0.005764162 |
| evidence: all existing cycle evidence | 0.061769112 | 0.035077202 |
| evidence/VE-P1e-3b: this cycle, subset | 0 | 0.000198389 |
| scratch: temporary homes, profiles, media | 0 | 0.000000000 |
| cache: reusable tools/fixtures, total | 6.618668578 | 7.497296635 |
| cache/mpv-lgpl: retained candidate and build, subset | 0 | 0.878628057 |
| cache/mpv-lgpl/spike-target: native build, subset of mpv cache | 0 | 0.631105963 |

Cleanup candidates recorded before deletion, all created in this cycle:

| Exact work-relative path | Measured bytes before cleanup | Removed bytes |
| --- | ---: | ---: |
| scratch/mpv-spike | 234380237 | 234380237 |
| scratch/tmp | 9495 | 9495 |
| scratch/mpv-spike, final isolated repeat | 213939702 | 213939702 |
| scratch/tmp, final isolated repeat | 0 | 0 |
| .ruff_cache, created by spike lint | 78 | 78 |
| repo/.ruff_cache, created by spike lint | 282 | 282 |

Final free C/D, persistent growth and remaining deletion work: C free 299.230621696 GB; D free 1004.343996416 GB. Measured persistent growth 0.852031776 GB (below 1 GB, including mpv cache and after retention cleanup). Start/end file lengths use the same PowerShell inventory method; earlier Python inventory snapshots differed and are not used for this growth calculation. These are finalization snapshots; report/evidence writes add small text files. Scratch is empty. For the owner to delete: none.
Retention cleanup: evidence/VE-MIG-1 (420478 bytes) and evidence/VE-P1f-3 (26439756 bytes) are confirmed development evidence. Their reports are preserved at Git commits 7990d33 and 8302964 respectively. Both were recorded before deletion and removed successfully (420478 and 26439756 bytes respectively). Keep VE-P1f-3b, VE-P1e-3a and this cycle. No existing cache, package or owner data is cleaned.

## Questions for the designer

1. Can GUI access to the prototype be approved for the missing checks?
   Default chosen: retain PARTIAL; do not claim transparency or input success.
   Computer Use access was explicitly requested and has not been granted.
2. Is the prebuilt candidate acceptable only after a complete corresponding
   source/dependency audit, or should the next cycle build a smaller DLL from
   source? Recommendation: obtain a fully pinned minimal source build and
   dependency manifest. Default: keep the candidate in cache, never package it.
3. Should B1 custom hosting proceed after visual validation? Recommendation:
   evaluate B1 first, retain B2 as a comparison. Default: no product integration.
4. The local main ref is absent and the task-definition commit changes
   CURRENT_TASK relative to the baseline. Recommendation: operator verifies
   the remote base and accounts for this pre-existing task file in review.
   Default: compare product files to aa107af; do not mutate Git refs or task.

## Configuration evidence

Full mpv configuration extracted from the DLL:

```text
-Dprefix=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/install/x86_64-w64-mingw32 -Dlibdir=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/install/x86_64-w64-mingw32/lib -Ddefault_library=shared -Dprefer_static=true -Dgpl=false -Ddebug=true -Db_ndebug=true -Doptimization=3 -Db_lto=true -Db_lto_mode=thin -Dcplayer=false -Dlibmpv=true -Dpdf-build=disabled -Dlua=enabled -Djavascript=enabled -Dsdl2-gamepad=enabled -Dlibarchive=enabled -Dlibbluray=enabled -Ddvdnav=disabled -Duchardet=enabled -Drubberband=disabled -Dlcms2=enabled -Dopenal=disabled -Dspirv-cross=enabled -Dvulkan=enabled -Dvapoursynth=enabled -Dsubrandr=enabled -Dsixel=enabled -Dgl=enabled -Degl-angle=enabled -Dlibcurl=enabled -Dc_args=-Wno-error=int-conversion --cross-file=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/meson_cross.txt
```

Full companion FFmpeg configuration (scope limitation above):

```text

  configuration:
    --cross-prefix=x86_64-w64-mingw32-
    --prefix=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/install/x86_64-w64-mingw32
    --arch=x86_64
    --target-os=mingw32
    --pkg-config-flags=--static
    --enable-cross-compile
    --enable-runtime-cpudetect
    --enable-version3
    --enable-vapoursynth
    --enable-libass
    --enable-libbluray
    --enable-libfreetype
    --enable-libfribidi
    --enable-libfontconfig
    --enable-libharfbuzz
    --enable-libmodplug
    --enable-libopenmpt
    --enable-libmp3lame
    --enable-lcms2
    --enable-libopus
    --enable-libsoxr
    --enable-libspeex
    --enable-libvorbis
    --enable-libbs2b
    --enable-libvpx
    --enable-libwebp
    --enable-libaom
    --enable-libsvtav1
    --enable-libdav1d
    --enable-libuavs3d
    --enable-libzimg
    --enable-openssl
    --enable-libxml2
    --enable-libmysofa
    --enable-libvpl
    --enable-libjxl
    --enable-libplacebo
    --enable-libaribcaption
    --enable-cuda-llvm
    --enable-cuvid
    --enable-nvdec
    --enable-nvenc
    --enable-amf
    --enable-openal
    --disable-doc
    --disable-ffplay
    --disable-ffprobe
    --enable-vaapi
    --disable-vdpau
    --disable-videotoolbox
    --disable-decoder=libaom_av1
    --enable-lto=thin
    --extra-cflags='-Wno-error=int-conversion'
    --extra-libs=-lc++

Exiting with exit code 0
```
