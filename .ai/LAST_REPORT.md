# VE-P1e-3b / Cycle P1e-3b, section 13 completion

Status: COMPLETED

## Outcome

The section 13 implementation and measurements are complete. B1 provides
captured transparent HTML over native moving video. B2 plays the same inputs,
has verified transparent HTML surface alpha, input/focus and owner tracking,
but its final combined desktop picture is not obtainable through the capture
paths available here. Both approaches and the HTML5 baseline were measured for
all five clips. Native frame stepping matched the burned-in frame numbers;
the HTML5 exact-FPS seek attempt often displayed the preceding frame.

Part A remains OPEN after a real minimal source build failed on missing
development dependencies. The designer explicitly permits the pinned prebuilt
candidate for measurements after that failure. No candidate was packaged.
COMPLETED under section 13.3 means every requested experiment has a measured
answer or an evidenced unavailable result; it does not mean library clearance,
production readiness, or that every comparison passed.

No product source, package, engine, settings, media path or CI configuration was
changed. The operator owns committing, pushing and final-commit CI.

## Start and scope protection

- Read AGENTS.md, CLAUDE.md, WORKSPACE.md and all of CURRENT_TASK.md including
  section 13. Task: VE-P1e-3b, Windows PowerShell / development RTX 4060 Ti.
- Initial continuation branch: claude/project-thread-6lra47; HEAD 5dba5e3;
  initial working tree clean. Existing first-run evidence was preserved.
- Normal Git execution was denied; prescribed escalated read-only Git worked.
- origin/main exists at aa107af62f1d6666ed33663f9db2657a4c09b864 and is the
  comparison base. CURRENT_TASK and LAST_REPORT are expected base differences.
- No Git mutation, ref creation, commit, push, merge or fetch was performed.
- Dependency restore: 0 bytes. Cached Python/Rust/crates were reused, with all
  Cargo builds offline and at most two build jobs.
- Process-local profiles, APPDATA/LOCALAPPDATA and test homes are under scratch.
  TEMP/TMP were set by local-env.ps1. No owner media or queue was used.

## Part A: real minimal source attempt; OPEN

Pinned official mpv source commit:
0fae4695470bf2c0c06762503292ee5379f62f62; source archive SHA-256
a2cb3f3c1ad61b31c8df77aacb5ce106f6f47991df4e8b9e6975f94194fb386a.
Official Meson 1.12.1 archive SHA-256:
ab0a6ca09f8ef70c564c8241fb5a23957886a0b53fb58412b5e07eaf07dba743.

source-build.ps1 reproduces the attempted configuration:
--backend=vs2022 --vsenv --wrap-mode=nodownload --auto-features=disabled
-Dgpl=false -Dlibmpv=true -Dcplayer=false -Dgl=disabled
-Dd3d11=enabled -Dd3d-hwaccel=enabled -Dzlib=enabled.

Existing MSVC 19.51.36260 x64 and linker 14.51.36260.0 were detected.
Meson reached the real mpv dependency checks, then exited 1:

> meson.build:23:13: ERROR: Dependency lookup for libavcodec with method 'pkg-config' failed: Pkg-config for machine host machine not found. Giving up.

Both the initial attempt and recipe reproduction failed at this dependency.
The logs also contain a vswhere warning and CMake compiler/generator warnings;
they did not prevent MSVC detection. No compilation/linking of libmpv followed.
No minimal DLL exists (0 bytes). No system toolchain was installed.

source-manifest.json records the source/tool versions and licences, mandatory
FFmpeg/libplacebo/libass minimum versions, unresolved dependency versions and
licences, intended decoder subset, and the exact failure. Optional mpv features
were disabled; a minimal FFmpeg build was planned but not executed because
its development dependencies were unresolved. This is not a complete successful
dependency audit. LICENSES.md explicitly keeps source delivery, aggregate
dependency licensing and relinking obligations OPEN.

Measurement fallback: official project release
[2026-10-23-0fae469547](https://github.com/zhongfly/mpv-winbuild/releases/tag/2026-10-23-0fae469547),
build [39897995385](https://github.com/zhongfly/mpv-winbuild/actions/runs/39897995385),
builder revision b120d7d8a64d17bd40b893f585429ef3845ac766.
Archive hashes match the release API digests. The source archive is pinned
locally to its immutable official GitHub commit; Meson's release digest is
published. There were no non-official or paid downloads.

Runtime versions: mpv v0.41.0-1288-g0fae46954; FFmpeg N-127952-gc569ebacc. The DLL contains -Dgpl=false.

| Candidate / tool file | Bytes | SHA-256 |
| --- | ---: | --- |
| ffmpeg/ffmpeg.exe | 91134464 | 201f7112b9b76aaec64b5dbaa56b39335e962d8b9a1d2ef0de8a5a099dabca69 |
| ffmpeg-lgpl-x86_64-git-c569ebacc.7z | 25700913 | 3ac8067c9f7d7588521651c86b4bc5d7cc43fe9e5fed3214d8d6427421a059f5 |
| include/mpv/client.h | 86136 | 3da9b8c61c3fb4e2d76bd248cebf72f3ee830331411b71a76adbd5e05660cc50 |
| include/mpv/render.h | 34869 | f2550aa29b2e9b20988bd954b4383e9fa05fd9e40d1669fbc6edf2afac603f15 |
| include/mpv/render_gl.h | 7328 | 48662c0ed9872a14dd9e1684105c97f69f94a0414709c254c5d372adc41d2e69 |
| include/mpv/stream_cb.h | 9589 | 188e58b6d14383e15a5dffdc4ecebbdfbf2e412b9c099ff21b571f747a8ce32d |
| libmpv-2.dll | 101511680 | b9f3ddd1ef2d43d6424addb835824ddb4e1e5f72c067e2816f0e09b19a6c4752 |
| libmpv.dll.a | 53308 | bef1b89f534bc86b33135e1f04fa2d5064b9d48b5de8bc9866665bbf43def793 |
| mpv-dev-lgpl-x86_64-20261023-git-0fae469547.7z | 28983807 | 81cf5b30b5729be3647eac85d70c05ea0b8dfea02dfa7c4eefed1f23a0a38a52 |

Candidate/tool files total, excluding native build cache: 247522094 bytes. Only libmpv-2.dll is a bundled DLL in this candidate archive. Its aggregate static dependency licences remain OPEN. The companion FFmpeg EXE is a fixture tool, not proposed app payload. Full configurations appear at the end.

## Part B: capture, input and window behaviour

B1 uses a hardware D3D11 composition swap chain and libmpv render API below a
WebView2 composition controller in one DirectComposition tree. B2 uses mpv wid
plus an owned transparent wry window. No Tauri fork or product integration was
made. The prototype uses pinned tao 0.37.1, wry 0.57.0, webview2-com 0.39.1.

The tests capture only their own HWNDs (WGC), or a DXGI desktop-duplication crop
of their own foreground window. No PrintWindow, BitBlt or SendInput was used.
Inputs go only to owned HWNDs or the owned WebView2 CDP instance. No Computer
Use access was requested again; section 13's self-test instructions were used.

| Check | B1 | B2 |
| --- | --- | --- |
| All five clips advance, correct codec/dimensions | PASS | PASS |
| Visible transparent HTML over video | PASS: WGC picture + control/hidden comparison | Final desktop composite NOT_AVAILABLE; WGC parent omits owned overlay, DXGI gives black |
| HTML surface alpha | Transparent padding pixel comparison PASS | Own overlay WGC alpha 0 over unpainted regions; 96.29% of visible surface alpha 0 |
| HTML pointer, wheel, Space; DOM/document focus | PASS, play button focused, yes/no/yes pause sequence | PASS, same |
| Native host wheel, double click, pointer capture/seek drag | PASS; drag reaches about 49.2 s | HTML CDP drag PASS; direct root HWND key messages are not the focused WebView child route |
| Resize, maximise, fullscreen, minimise/restore | PASS: own-window state and non-minimised captures | PASS: exact client/overlay sizes, overlay hidden/restored with owner |
| Synthetic WM_DPICHANGED 96/120/144/96 | PASS code path; real DPI remains 120 | PASS code path; real DPI remains 120 |
| Actual 125% scale | PASS, device DPI 120 | PASS |
| Real 100% / 150% and monitor move | NOT_AVAILABLE: one monitor at 125%; no system setting change | Same |

B1 blank padding band: mean absolute RGB error 0.000000 against the hidden-control frame, textured video standard deviation 117.733; 22932 pixels changed for the visible glyphs/track. The test explicitly requires visible controls as well as unchanged video; a video-only capture cannot pass.

The first B1 capture exposed reversed visual ordering: AddVisual with a null
reference and insertAbove=true places the visual below siblings. It was fixed
by explicitly placing HTML above the video visual. The first whole-bar alpha
oracle incorrectly included painted glyphs/track (about 41% exact match);
both that result and the corrected unpainted-padding test are retained.
No production test was loosened or disabled.

B2 initially acquired invisible frame margins through tao set_inner_size.
Direct own-window SetWindowPos alignment now matches client sizes at resize,
maximise/fullscreen and simulated DPI changes. Initial client 1200x675 matches
overlay rectangle [109,138,1309,813]. Minimise produces invisible overlay;
restore makes it visible again. Parent WGC cannot verify its final combined
z-order picture. Own-overlay captures preserve alpha: visible alpha-zero
fraction 0.962914, hidden-control fraction 0.996944, range 0..255.
Do not treat its video-only WGC frame as composite transparency proof.

Images inspected with the image viewer include B1 visible controls, hover,
portrait rotation with black letterboxing, and hstack's paired frame 1782.
B1 text shadows are visible; no opaque controller panel appears. The thumbnail
is above the bar with its time below. Sampled images do not establish absence
of continuous flicker or physical display tearing. B2 combined-view halo,
flicker, tearing and final z-order remain NOT_AVAILABLE for the capture reason
above. The program records the black DXGI captures instead of claiming success.

B3 was not built: B1's transparent design works, so the fallback-only condition
was not met.

Integration: B1 needs a reviewed custom composition host or Tauri/wry extension,
manual input/capture/focus, DPI and device-loss handling. Current window.rs
background/theme logic and main.rs lifetime/IPC code would need an adapter;
neither was changed. B2 needs owner/overlay placement and activation handling.
Public COM APIs reduce API-contract risk, but both need Runtime/Tauri update
regressions, especially focus, z-order, resize and lifetime tests.

## Part C: definitions and complete measurements

All clips are local synthetic 65-second files with frame numbers at the top
and beneath the control bar: H.264 8-bit 1080p30, HEVC Main10 and AV1 10-bit
1440p60, VP9 8-bit 1080p60, and HEVC encoded 1920x1080 with a 90-degree display
matrix (display 1080x1920). Generated pixel/codec flags, commands and hashes
are retained outside Git. No owner media, download service or GPU job was used.

Baseline: a minimal WebView2 HTMLVideoElement with controls, matching the product
element kind. It uses a loopback HTTP range server, not the product's media
transport. Thus the numbers describe these controlled hosts/input pipelines,
not a packaged-product end-to-end benchmark.

First-frame timings start at media load in an already initialised host; native
timing ends at MPV_EVENT_PLAYBACK_RESTART following render/present, HTML5 at
requestVideoFrameCallback. Neither is an optical measurement. Native event
polling is bounded by the render/heartbeat loop (roughly one display interval).
Five reloads per case are reported; separate one-process host-ready costs are
shown below. These are not five cold Home launches.

Twenty seeks use deterministic seed 1337 in the interval 2..58 s. Frame tests
perform forward, forward, backward after an exact seek to 6 s. Independent FFmpeg
reference images classify the burned-in digit regions. Confidence threshold
was unchanged: best error <0.25 and runner-up margin >0.003. Minimum measured
margin exceeded 0.027. HTML5's method adds/subtracts 1/fps to currentTime; it is
not a product frame-step control or a native browser frame-step API.

GPU values sum process-tree PDH dedicated/shared allocations; they are not
device-wide VRAM or Torch allocation. CPU uses process-tree CPU-time deltas,
with one fully used core =100%. There are sixty one-second playback samples per
case, then five after closing the player while the host remains. The residual
column is the last sample (about 4 s after close). B1 tears down its composition
controller with mpv; B2/HTML5 retain the HTML host. Self-capture resources and the
prototype's polling are part of this instrumented host's cost.

Eighteen full cases were run: the primary 15 plus three preserved initial/final
H.264 repeats. Each has 5 load samples, 20 seeks, 3 frame steps and 60 GPU/CPU
samples: totals 90 loads, 360 seeks, 54 frame comparisons, 1080 playback samples.
No timing or seek sample failed. All cases' raw arrays appear in the appendix;
all raw targets/properties/samples/captures remain in section13 evidence.

| Clip | Player | First frame median ms (n=5) | Seek median / worst ms (n=20) | Exact steps | Drops / 60 s |
| --- | --- | ---: | ---: | --- | ---: |
| H.264 1080p30 | B1 | 440.7 | 409.2 / 658.8 | 3/3 | 0 |
| H.264 1080p30 | B2 | 44.0 | 159.0 / 229.7 | 3/3 | 0 |
| H.264 1080p30 | HTML5 | 45.6 | 157.3 / 222.9 | 1/3 | 0 |
| HEVC Main10 1440p60 | B1 | 632.9 | 390.2 / 699.1 | 3/3 | 0 |
| HEVC Main10 1440p60 | B2 | 35.2 | 121.1 / 181.8 | 3/3 | 0 |
| HEVC Main10 1440p60 | HTML5 | 23.1 | 124.5 / 188.7 | 0/3 | 0 |
| AV1 10-bit 1440p60 | B1 | 429.4 | 345.3 / 518.9 | 3/3 | 0 |
| AV1 10-bit 1440p60 | B2 | 31.5 | 130.5 / 196.5 | 3/3 | 0 |
| AV1 10-bit 1440p60 | HTML5 | 39.7 | 125.0 / 206.6 | 0/3 | 0 |
| VP9 1080p60 | B1 | 626.2 | 258.9 / 466.7 | 3/3 | 0 |
| VP9 1080p60 | B2 | 28.8 | 29.3 / 65.6 | 3/3 | 0 |
| VP9 1080p60 | HTML5 | 37.7 | 38.8 / 92.1 | 0/3 | 0 |
| HEVC portrait / rotation | B1 | 440.1 | 464.1 / 624.6 | 3/3 | 0 |
| HEVC portrait / rotation | B2 | 45.8 | 82.3 / 117.5 | 3/3 | 0 |
| HEVC portrait / rotation | HTML5 | 47.1 | 90.4 / 146.2 | 1/3 | 0 |

| Clip | Player | Dedicated median / peak MB | Shared peak MB | CPU % (one core) | Dedicated after close MB | Host-ready ms (one start) | Decoder |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| H.264 1080p30 | B1 | 205.9 / 205.9 | 26.5 | 62.8 | 11.2 | 618.2 | d3d11va |
| H.264 1080p30 | B2 | 189.5 / 201.8 | 93.1 | 52.0 | 41.4 | 401.9 | d3d11va |
| H.264 1080p30 | HTML5 | 83.1 / 97.6 | 92.7 | 4.7 | 59.5 | 385.5 | D3D11VideoDecoder, platform=true |
| HEVC Main10 1440p60 | B1 | 492.5 / 492.5 | 25.1 | 64.2 | 11.2 | 610.6 | d3d11va |
| HEVC Main10 1440p60 | B2 | 458.9 / 463.9 | 148.4 | 54.1 | 41.4 | 396.6 | d3d11va |
| HEVC Main10 1440p60 | HTML5 | 207.0 / 215.8 | 147.8 | 4.9 | 63.2 | 383.9 | VDAVideoDecoder, platform=true |
| AV1 10-bit 1440p60 | B1 | 337.6 / 337.6 | 36.2 | 64.9 | 11.2 | 634.9 | d3d11va |
| AV1 10-bit 1440p60 | B2 | 311.5 / 315.6 | 145.8 | 56.2 | 41.4 | 391.8 | d3d11va |
| AV1 10-bit 1440p60 | HTML5 | 216.0 / 230.5 | 139.4 | 5.7 | 63.2 | 374.7 | D3D11VideoDecoder, platform=true |
| VP9 1080p60 | B1 | 179.8 / 181.6 | 23.0 | 65.0 | 11.2 | 612.7 | d3d11va |
| VP9 1080p60 | B2 | 163.5 / 176.7 | 87.3 | 53.8 | 41.4 | 391.8 | d3d11va |
| VP9 1080p60 | HTML5 | 95.0 / 109.5 | 73.9 | 5.8 | 80.8 | 372.5 | D3D11VideoDecoder, platform=true |
| HEVC portrait / rotation | B1 | 216.3 / 216.3 | 19.5 | 63.8 | 11.2 | 649.1 | d3d11va |
| HEVC portrait / rotation | B2 | 192.0 / 200.6 | 86.7 | 52.8 | 41.4 | 375.0 | d3d11va |
| HEVC portrait / rotation | HTML5 | 101.3 / 115.8 | 89.5 | 4.1 | 76.8 | 367.4 | VDAVideoDecoder, platform=true |

The native steps all matched expected IDs (30/30 for the primary matrix,
36/36 including repeats). HTML5 matched 2/15 in the primary matrix and 3/18
including repeats. Failures are confident frame-ID mismatches, not ambiguous
images: at 30 fps the second forward/backward steps often remained at 181/180
instead of 182/181; at 60 fps observed 360/361/360 instead of 361/362/361.
These baseline failures were kept, not tuned away. Three steps per case do not
establish universal frame accuracy for every file or timestamp.

All native codec cases report actual hwdec-current=d3d11va. HTML5 CDP reports
D3D11VideoDecoder for H.264/AV1/VP9 and VDAVideoDecoder with platform=true for
HEVC/portrait. The latter's internal hardware path is not exposed beyond the
platform flag here; do not infer more than those observed properties.

All 60-second drop deltas were zero. Startup/seek drop counts are present in
the raw samples and are not included in that steady-playback delta. The native
prototype's CPU/polling overhead is much higher than HTML5; the result does not
show an across-the-board speed improvement. B1's media-load/seek delay is also
substantially higher than B2/HTML5 in this implementation.

Normal desktop GPU clients were left running, as section 13.2 allows.
Observed GPU process basenames: CrossDeviceResume.exe, MouseAssistant.exe, SearchHost.exe, ShellExperienceHost.exe, ShellHost.exe, StartMenuExperienceHost.exe, SystemSettings.exe, TextInputHost.exe, claude.exe, codex-computer-use-swift.exe, explorer.exe, localsend_app.exe, mpv-embedding-spike.exe. No owner process was stopped. GPU: RTX 4060 Ti, driver 617.42.

### Additional B1 containers

| Container | Source | First frame ms (n=1) | Seek ms (n=1, 32.125 s) |
| --- | --- | ---: | ---: |
| mkv | H.264 | 627.8 | 624.4 |
| webm | VP9 | 629.0 | 218.9 |
| mov | H.264 | 439.8 | 307.8 |

### Hover preview

A second paused mpv instance uses a software render context and a 320x180
RGBA memory buffer. The actual decoded PNG is assigned to the HTML image;
it is not a placeholder. Ten hovered times were measured on H.264.

| Hover s | Latency ms | Captured frame | Expected |
| ---: | ---: | ---: | ---: |
| 0 | 603.2 | 0 | 0 |
| 4 | 497.2 | 120 | 120 |
| 10 | 473.7 | 300 | 300 |
| 20 | 498.3 | 600 | 600 |
| 40 | 528.3 | 1200 | 1200 |
| 50 | 438.4 | 1500 | 1500 |
| 3 | 479.4 | 90 | 90 |
| 30 | 513.4 | 900 | 900 |
| 15 | 541.2 | 450 | 450 |
| 55 | 512.7 | 1650 | 1650 |

Median 505.5 ms; worst 603.2 ms. All 10 returned frames match burned-in IDs. Latency includes polling, a 50 ms settling step,
PNG conversion and delivery to HTML; it is not an optical hover measurement.
This is too sluggish for a polished controller without coalescing/caching.

### Before/after options, H.264, 60 s

| Run | Drift evidence | Dedicated median / peak MB | CPU % (one core) |
| --- | --- | ---: | ---: |
| sync-two | 1 Hz max 33.333 ms | 291.1 / 293.6 | 53.2 |
| sync-stack | One output clock; paired capture check below | 301.2 / 303.7 | 66.8 |
| sync-stack-sampled | One output clock; paired capture check below | 311.2 / 319.9 | 71.9 |

Two-instance mode has paired play/seek commands and independent clocks; sampled
drift reached one 30 fps frame, with no measured cumulative runaway over 60 s.
It needs explicit correction for production synchronisation. The hstack graph
combines vid1/vid2 under one output clock, configured with d3d11va-copy; the
top-level hwdec-current is unavailable for that complex graph, so actual
per-input hardware status is not claimed.

The sampled hstack repeat captured both burned-in numbers at about 9,19,...59 s.
Their digit ROI mean RGB differences were 0.153..0.222 of 255; thresholded digit
masks differed in 0..3 of 2250 pixels, with 173..229 foreground pixels. The final
image shows frame 1782 on both sides. No whole-frame mismatch was detected at
those samples (one-frame/33.3 ms observation resolution), not a continuous
optical zero-drift guarantee. The original no-capture hstack run gives its
cleaner cost; the sampled repeat includes capture overhead.

## Part D: recommendation and next work

Recommend B1 for P1e-3c because it has captured transparent controls in one
composition tree and avoids B2's separate-window activation/tracking boundary.
This is not a performance endorsement of the current polling prototype:
its load/seek times and CPU usage must be improved and remeasured before
product adoption. Keep B2 as a comparison until its final combined desktop
capture/physical focus behaviour can be qualified.

P1e-3c needs a reviewed custom host/adapter, event-driven rendering and resource
reuse, lazy library loading on player open, device-loss recovery, deterministic
lifetime/IPC, approved transparent controls, precise stepping, preview request
coalescing/caching, and an A/B clock strategy. Do not infer a confirmed cause for
the current overhead without profiling. Product architecture remains for the
owner/designer to decide.

Candidate DLL payload alone is 101.511680 MB uncompressed / 28.983807 MB archive.
The minimal source payload is unknown because its build failed. Notices,
corresponding source and any other final dependencies are additional. No payload
was added to the current package. Host-ready samples are above; the P2 cold Home
median <=765 ms gate was NOT_RUN (product unchanged). mpv is loaded only by this
separate player process, never by product Home. Future integration must preserve
that lazy boundary rather than moving library work into Home startup.

CPU-only CI can lint these scripts, compile an isolated Windows host and later
test IPC/control-state/lazy-load contracts. Hardware decoding, real alpha/z-order,
frame presentation, real monitor transitions, GPU residuals and device loss need
a dedicated interactive GPU run. The spike was not added to product build/test
jobs; repository-wide ruff discovery still covers the new Python scripts.

## Expected / Actual

Expected: isolated hosts, transparent controls, complete comparable measurements, and a minimal LGPL payload or evidenced source-build failure. Actual: B1 transparency and both hosts' input/playback/geometry are measured, all 15 conditions plus repeats are sampled, and the minimal build is OPEN on missing dependencies. HTML5 frame-step mismatches and B2 composite-capture limits are retained as results.

## Validation and all failures

| Check | Result |
| --- | --- |
| Final isolated Cargo build, offline/locked | PASS |
| Clippy with -D warnings; Rust formatting | PASS |
| Spike Python ruff lint/format | PASS |
| Real minimal source build + recipe reproduction | FAIL, exit 1; Part A OPEN under approved fallback |
| Primary 15 media conditions, plus 3 H.264 repeats | All 18 have 5/20/60 samples and exit 0 |
| Native burned-in frame accuracy | PASS, 36/36 including repeats |
| HTML5 exact-FPS seek frame accuracy | FAIL, 15 mismatches of 18; comparison result retained |
| Preview returned-frame accuracy | PASS, 10/10 |
| B1 transparency, input/focus, window states | PASS for stated samples and simulated paths |
| B2 input/focus, alpha surface, geometry/minimise tracking | PASS; final desktop composite NOT_AVAILABLE |
| Real 100%/150% DPI and multi-monitor movement | NOT_AVAILABLE, one monitor at 125% |
| Product CPU/ruff/pyright/GUI lint/typecheck/unit/build | NOT_RUN; product-change waiver applies |
| Windows/Ubuntu CI on final commit | NOT_RUN; operator must commit/push and verify CI |
| Final tracked diff/whitespace verification | PASS: read-only origin/main comparison showed no product/CI diff; tracked whitespace check passed |

Initial failures retained: B1 reversed composition order; DXGI black captures;
whole-bar pixel oracle included intentionally painted controls; HTML5 host idle
requests initially lacked an event-loop wake; preview initially sought before
file load (libmpv -12), then accepted a black initial buffer before validation
was corrected; singular external-file option failed (-5), fixed to external-files;
B2 tao inner sizing expanded borders, corrected with direct alignment. Probe
failures and each corrected run have distinct labels, not overwritten records.
The initial HTML5 constructor timeout did not capture an exit code; its process
exited when pipes closed, and constructor cleanup now terminates only its own
Popen child on failure.

Static-check failures were corrected: missing GetDoubleClickTime import,
non-exhaustive wheel match, tao keyboard API version mismatch, clippy chunk
iteration/style warnings, and Python import/format/exception-chaining issues.
Pillow getdata deprecation warnings were removed using get_flattened_data.
All final checks listed above were actually run. Git also warned that LF will become CRLF on its next write for several spike files; no Git configuration was changed. Driver exit 0 means the
analysis finished; individual JSON failures/frame mismatches are still reported.

Earlier run history is preserved in first-run-report.md and the parent evidence
directory. The first run's playback/hwdec checks remain accepted historical
evidence, not new 60-second measurements. Its invalid initial rotation fixture
and corrected display-matrix run remain distinct. No source build/GUI check
was retroactively relabelled.

## Changed files

The cycle's allowed changes are .ai/LAST_REPORT.md and spikes/mpv/**.
CURRENT_TASK.md differs from origin/main because of the designer's task commits;
it was not changed by this continuation.

- Cargo.toml / Cargo.lock; src/main.rs, src/composition.rs, src/mpv.rs,
  src/capture.rs; controls.html / html5.js.
- download.ps1 and audit.py retained for pinned candidate verification.
- source-build.ps1 / source-manifest.json / LICENSES.md.
- smoke.py, measure.py, frame_check.py, summarize.py; README.md.
- .ai/LAST_REPORT.md. No product or CI file.

## Disk and cleanup

Decimal GB / logical file lengths, using consistent PowerShell inventory.
Overlapping subset rows must not be summed. Whole-cycle baseline is the first
run's recorded start; continuation start is separately retained in section13.
C/D first-cycle free: 299.012853760 / 1005.166419968 GB.
C/D continuation-start free: 299.227598848 / 1004.343894016 GB.
Dependency restore 0 bytes. Existing MSVC/Rust/Python reused; no system install.
Meson source tooling is reported separately, within the retained build cache.

| Path / role | Whole-cycle start GB | Continuation start GB | End GB |
| --- | ---: | ---: | ---: |
| repo / Checkout / existing venv | 3.526660963 | 3.526819078 | 3.526934723 |
| package / Current portable package | 0.005764162 | 0.005764162 | 0.005764162 |
| evidence / All retained evidence | 0.061769112 | 0.035965208 | 0.095971090 |
| evidence/VE-P1e-3b / This cycle evidence (subset) | 0.000000000 | not separately inventoried | 0.061092277 |
| scratch / Temporary homes/media/profiles | 0.000000000 | 0.000000000 | 0.000000000 |
| cache / Complete cache | 6.618668578 | 7.497296635 | 7.903006349 |
| cache/mpv-lgpl / Retained mpv/build cache exception (subset) | 0.000000000 | 0.878628057 | 1.284337771 |
| cache/mpv-lgpl/spike-target / Native prototype build (mpv subset) | 0.000000000 | not separately inventoried | 1.000690430 |
| cache/mpv-lgpl/source-build / Source build attempt (mpv subset) | 0.000000000 | not separately inventoried | 0.036125247 |
| cache/mpv-lgpl/source-build/meson-1.12.1 / New Meson source tooling (source-build subset) | 0.000000000 | not separately inventoried | 0.007991565 |


Cleanup candidates recorded before deletion, all created by this cycle:

| Work-relative path | Bytes before cleanup | Removed bytes |
| --- | ---: | ---: |
| scratch/mpv-spike | 1148052413 | 1148052413 |
| scratch/tmp | 44699 | 44699 |
| scratch/finish-report.py | 28933 | 28933 |
| .ruff_cache | 78 | 78 |
| repo/.ruff_cache | 498 | 498 |


C free 299.219681280 GB; D free 1003.874664448 GB. Whole-cycle persistent growth including the approved mpv-cache exception: 1.318813509 GB; excluding that exception: 0.034475738 GB (<=1 GB). Cache is below 40 GB and cycle evidence below 300 MB. Scratch is empty; all five recorded cleanup targets were removed. For the owner to delete: none. These are finalisation snapshots; final text/manifest writes add only small files. File-length inventory does not measure allocated blocks or attribute drive-wide free-space changes.

Earlier retention cleanup removed evidence/VE-MIG-1 (420478 bytes) and
evidence/VE-P1f-3 (26439756 bytes), after confirming their reports in Git
7990d33 and 8302964. These removals are not re-executed. The retained evidence
cycles are VE-P1f-3b, VE-P1e-3a and VE-P1e-3b. No owner data was cleaned.

## Questions for the designer and defaults chosen

1. Minimal source build is OPEN on missing FFmpeg/pkg-config development
   dependencies. Default: use the pinned candidate for measurements only, keep
   cache, never package it. Recommend a fully pinned dependency/toolchain build
   and licence/source audit before P1e-3c shipment.
2. B1 is recommended structurally, but this implementation has higher CPU and
   media-load/seek cost. Default: no product integration; request reviewed host
   work and profiling in the next task, without changing the approved design.
3. B2's final desktop composite remains unavailable to these capture paths,
   though source alpha and tracking are measured. Default: retain that limit,
   and require a suitable interactive GPU capture check before selecting B2.
4. Real 100/150% DPI and monitor moves are unavailable here. Default: preserve
   system settings; require those environments in later acceptance.
5. HTML5 fixed-FPS seeking is not exact frame stepping. Default: report the
   mismatch and keep the product unchanged; native stepping is the candidate.
6. Git/CI remain with the operator. Default: stop after this report, no commit,
   push, merge or ref changes. No GUI access question is repeated.

## Appendix: every gated load/seek run

Each label maps to its full -results.json, .jsonl and stderr log under the cycle
section13 evidence directory. Target times and all process samples are in those
JSON files. Earlier H.264 cases are retained alongside final repeats.

### bench-b1-av1

First-frame ms: [232.312, 426.278, 430.444, 431.119, 429.447]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 482.056}, {"target_s": 31.862872, "latency_ms": 424.147}, {"target_s": 22.487508, "latency_ms": 299.424}, {"target_s": 34.804092, "latency_ms": 317.15}, {"target_s": 11.278488, "latency_ms": 190.281}, {"target_s": 48.16493, "latency_ms": 400.967}, {"target_s": 23.487469, "latency_ms": 222.785}, {"target_s": 46.218318, "latency_ms": 41.655}, {"target_s": 53.616685, "latency_ms": 444.101}, {"target_s": 19.22747, "latency_ms": 222.813}, {"target_s": 57.565836, "latency_ms": 476.604}, {"target_s": 13.476976, "latency_ms": 291.742}, {"target_s": 38.751547, "latency_ms": 300.286}, {"target_s": 53.089099, "latency_ms": 391.23}, {"target_s": 8.12015, "latency_ms": 518.895}, {"target_s": 47.944507, "latency_ms": 358.231}, {"target_s": 24.329387, "latency_ms": 508.172}, {"target_s": 5.659215, "latency_ms": 332.347}, {"target_s": 41.155667, "latency_ms": 432.999}, {"target_s": 21.493709, "latency_ms": 56.162}]
```

60 s samples=60; drop delta=0; CPU=64.9%; dedicated median/peak=337.6/337.6 MB; after-close samples MB=[11.207, 11.207, 11.207, 11.207, 11.207].

### bench-b1-h264-final

First-frame ms: [449.643, 440.286, 441.404, 440.729, 439.692]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 407.093}, {"target_s": 31.862872, "latency_ms": 527.717}, {"target_s": 22.487508, "latency_ms": 322.822}, {"target_s": 34.804092, "latency_ms": 294.297}, {"target_s": 11.278488, "latency_ms": 392.735}, {"target_s": 48.16493, "latency_ms": 548.61}, {"target_s": 23.487469, "latency_ms": 409.286}, {"target_s": 46.218318, "latency_ms": 468.025}, {"target_s": 53.616685, "latency_ms": 410.562}, {"target_s": 19.22747, "latency_ms": 172.831}, {"target_s": 57.565836, "latency_ms": 617.11}, {"target_s": 13.476976, "latency_ms": 181.217}, {"target_s": 38.751547, "latency_ms": 258.316}, {"target_s": 53.089099, "latency_ms": 284.501}, {"target_s": 8.12015, "latency_ms": 658.795}, {"target_s": 47.944507, "latency_ms": 515.102}, {"target_s": 24.329387, "latency_ms": 407.635}, {"target_s": 5.659215, "latency_ms": 409.194}, {"target_s": 41.155667, "latency_ms": 624.067}, {"target_s": 21.493709, "latency_ms": 460.169}]
```

60 s samples=60; drop delta=0; CPU=62.8%; dedicated median/peak=205.9/205.9 MB; after-close samples MB=[39.182, 11.207, 11.207, 11.207, 11.207].

### bench-b1-h264

First-frame ms: [628.049, 440.652, 440.004, 435.17, 442.646]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 407.121}, {"target_s": 31.862872, "latency_ms": 374.649}, {"target_s": 22.487508, "latency_ms": 215.466}, {"target_s": 34.804092, "latency_ms": 276.038}, {"target_s": 11.278488, "latency_ms": 408.345}, {"target_s": 48.16493, "latency_ms": 532.393}, {"target_s": 23.487469, "latency_ms": 422.814}, {"target_s": 46.218318, "latency_ms": 492.994}, {"target_s": 53.616685, "latency_ms": 333.345}, {"target_s": 19.22747, "latency_ms": 356.279}, {"target_s": 57.565836, "latency_ms": 625.536}, {"target_s": 13.476976, "latency_ms": 400.005}, {"target_s": 38.751547, "latency_ms": 524.161}, {"target_s": 53.089099, "latency_ms": 407.833}, {"target_s": 8.12015, "latency_ms": 642.789}, {"target_s": 47.944507, "latency_ms": 389.357}, {"target_s": 24.329387, "latency_ms": 625.365}, {"target_s": 5.659215, "latency_ms": 523.677}, {"target_s": 41.155667, "latency_ms": 607.44}, {"target_s": 21.493709, "latency_ms": 474.743}]
```

60 s samples=60; drop delta=0; CPU=64.0%; dedicated median/peak=205.9/205.9 MB; after-close samples MB=[39.178, 11.207, 11.207, 11.207, 11.207].

### bench-b1-hevc

First-frame ms: [630.463, 634.393, 632.948, 632.193, 634.306]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 618.285}, {"target_s": 31.862872, "latency_ms": 532.727}, {"target_s": 22.487508, "latency_ms": 158.044}, {"target_s": 34.804092, "latency_ms": 165.652}, {"target_s": 11.278488, "latency_ms": 266.337}, {"target_s": 48.16493, "latency_ms": 360.38}, {"target_s": 23.487469, "latency_ms": 499.713}, {"target_s": 46.218318, "latency_ms": 258.041}, {"target_s": 53.616685, "latency_ms": 624.245}, {"target_s": 19.22747, "latency_ms": 420.042}, {"target_s": 57.565836, "latency_ms": 608.725}, {"target_s": 13.476976, "latency_ms": 316.459}, {"target_s": 38.751547, "latency_ms": 91.346}, {"target_s": 53.089099, "latency_ms": 425.498}, {"target_s": 8.12015, "latency_ms": 699.054}, {"target_s": 47.944507, "latency_ms": 457.721}, {"target_s": 24.329387, "latency_ms": 625.484}, {"target_s": 5.659215, "latency_ms": 299.247}, {"target_s": 41.155667, "latency_ms": 347.7}, {"target_s": 21.493709, "latency_ms": 249.355}]
```

60 s samples=60; drop delta=0; CPU=64.2%; dedicated median/peak=492.5/492.5 MB; after-close samples MB=[39.182, 11.207, 11.207, 11.207, 11.207].

### bench-b1-rotation

First-frame ms: [627.813, 441.937, 434.749, 440.058, 438.923]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 316.689}, {"target_s": 31.862872, "latency_ms": 565.413}, {"target_s": 22.487508, "latency_ms": 322.762}, {"target_s": 34.804092, "latency_ms": 294.103}, {"target_s": 11.278488, "latency_ms": 249.517}, {"target_s": 48.16493, "latency_ms": 533.209}, {"target_s": 23.487469, "latency_ms": 376.829}, {"target_s": 46.218318, "latency_ms": 443.269}, {"target_s": 53.616685, "latency_ms": 73.7}, {"target_s": 19.22747, "latency_ms": 300.394}, {"target_s": 57.565836, "latency_ms": 624.606}, {"target_s": 13.476976, "latency_ms": 508.901}, {"target_s": 38.751547, "latency_ms": 484.97}, {"target_s": 53.089099, "latency_ms": 391.48}, {"target_s": 8.12015, "latency_ms": 560.952}, {"target_s": 47.944507, "latency_ms": 557.501}, {"target_s": 24.329387, "latency_ms": 550.531}, {"target_s": 5.659215, "latency_ms": 516.781}, {"target_s": 41.155667, "latency_ms": 541.627}, {"target_s": 21.493709, "latency_ms": 289.491}]
```

60 s samples=60; drop delta=0; CPU=63.8%; dedicated median/peak=216.3/216.3 MB; after-close samples MB=[11.207, 11.207, 11.207, 11.207, 11.207].

### bench-b1-vp9

First-frame ms: [627.517, 425.465, 626.644, 626.18, 622.198]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 217.894}, {"target_s": 31.862872, "latency_ms": 449.803}, {"target_s": 22.487508, "latency_ms": 335.053}, {"target_s": 34.804092, "latency_ms": 258.688}, {"target_s": 11.278488, "latency_ms": 299.661}, {"target_s": 48.16493, "latency_ms": 366.209}, {"target_s": 23.487469, "latency_ms": 214.184}, {"target_s": 46.218318, "latency_ms": 165.96}, {"target_s": 53.616685, "latency_ms": 234.793}, {"target_s": 19.22747, "latency_ms": 212.929}, {"target_s": 57.565836, "latency_ms": 466.687}, {"target_s": 13.476976, "latency_ms": 232.408}, {"target_s": 38.751547, "latency_ms": 259.163}, {"target_s": 53.089099, "latency_ms": 249.649}, {"target_s": 8.12015, "latency_ms": 302.746}, {"target_s": 47.944507, "latency_ms": 139.438}, {"target_s": 24.329387, "latency_ms": 317.513}, {"target_s": 5.659215, "latency_ms": 390.809}, {"target_s": 41.155667, "latency_ms": 281.959}, {"target_s": 21.493709, "latency_ms": 218.556}]
```

60 s samples=60; drop delta=0; CPU=65.0%; dedicated median/peak=179.8/181.6 MB; after-close samples MB=[39.182, 11.207, 11.207, 11.207, 11.207].

### bench-b2-av1

First-frame ms: [56.805, 33.29, 31.406, 31.512, 30.12]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 160.914}, {"target_s": 31.862872, "latency_ms": 141.843}, {"target_s": 22.487508, "latency_ms": 86.862}, {"target_s": 34.804092, "latency_ms": 75.874}, {"target_s": 11.278488, "latency_ms": 146.31}, {"target_s": 48.16493, "latency_ms": 122.266}, {"target_s": 23.487469, "latency_ms": 131.505}, {"target_s": 46.218318, "latency_ms": 23.253}, {"target_s": 53.616685, "latency_ms": 180.803}, {"target_s": 19.22747, "latency_ms": 129.448}, {"target_s": 57.565836, "latency_ms": 173.457}, {"target_s": 13.476976, "latency_ms": 48.263}, {"target_s": 38.751547, "latency_ms": 65.793}, {"target_s": 53.089099, "latency_ms": 158.933}, {"target_s": 8.12015, "latency_ms": 196.452}, {"target_s": 47.944507, "latency_ms": 109.909}, {"target_s": 24.329387, "latency_ms": 175.359}, {"target_s": 5.659215, "latency_ms": 76.969}, {"target_s": 41.155667, "latency_ms": 182.349}, {"target_s": 21.493709, "latency_ms": 35.409}]
```

60 s samples=60; drop delta=0; CPU=56.2%; dedicated median/peak=311.5/315.6 MB; after-close samples MB=[41.415, 41.415, 41.415, 41.415, 41.415].

### bench-b2-h264-final

First-frame ms: [67.337, 44.371, 42.488, 43.075, 43.977]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 80.167}, {"target_s": 31.862872, "latency_ms": 206.497}, {"target_s": 22.487508, "latency_ms": 168.416}, {"target_s": 34.804092, "latency_ms": 45.968}, {"target_s": 11.278488, "latency_ms": 87.536}, {"target_s": 48.16493, "latency_ms": 183.563}, {"target_s": 23.487469, "latency_ms": 197.462}, {"target_s": 46.218318, "latency_ms": 131.182}, {"target_s": 53.616685, "latency_ms": 105.238}, {"target_s": 19.22747, "latency_ms": 74.668}, {"target_s": 57.565836, "latency_ms": 217.84}, {"target_s": 13.476976, "latency_ms": 145.883}, {"target_s": 38.751547, "latency_ms": 156.07}, {"target_s": 53.089099, "latency_ms": 91.812}, {"target_s": 8.12015, "latency_ms": 229.746}, {"target_s": 47.944507, "latency_ms": 179.979}, {"target_s": 24.329387, "latency_ms": 218.08}, {"target_s": 5.659215, "latency_ms": 161.873}, {"target_s": 41.155667, "latency_ms": 223.534}, {"target_s": 21.493709, "latency_ms": 138.403}]
```

60 s samples=60; drop delta=0; CPU=52.0%; dedicated median/peak=189.5/201.8 MB; after-close samples MB=[41.415, 41.415, 41.415, 41.415, 41.415].

### bench-b2-h264

First-frame ms: [72.597, 44.388, 43.744, 41.78, 42.79]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 84.283}, {"target_s": 31.862872, "latency_ms": 206.578}, {"target_s": 22.487508, "latency_ms": 168.176}, {"target_s": 34.804092, "latency_ms": 46.026}, {"target_s": 11.278488, "latency_ms": 85.743}, {"target_s": 48.16493, "latency_ms": 184.781}, {"target_s": 23.487469, "latency_ms": 197.193}, {"target_s": 46.218318, "latency_ms": 131.302}, {"target_s": 53.616685, "latency_ms": 105.451}, {"target_s": 19.22747, "latency_ms": 75.188}, {"target_s": 57.565836, "latency_ms": 219.432}, {"target_s": 13.476976, "latency_ms": 144.751}, {"target_s": 38.751547, "latency_ms": 158.055}, {"target_s": 53.089099, "latency_ms": 90.103}, {"target_s": 8.12015, "latency_ms": 230.622}, {"target_s": 47.944507, "latency_ms": 179.874}, {"target_s": 24.329387, "latency_ms": 217.841}, {"target_s": 5.659215, "latency_ms": 162.748}, {"target_s": 41.155667, "latency_ms": 225.273}, {"target_s": 21.493709, "latency_ms": 136.834}]
```

60 s samples=60; drop delta=0; CPU=51.9%; dedicated median/peak=189.5/201.8 MB; after-close samples MB=[41.415, 41.415, 41.415, 41.415, 41.415].

### bench-b2-hevc

First-frame ms: [57.427, 35.154, 33.715, 36.248, 33.088]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 147.111}, {"target_s": 31.862872, "latency_ms": 130.974}, {"target_s": 22.487508, "latency_ms": 79.908}, {"target_s": 34.804092, "latency_ms": 69.224}, {"target_s": 11.278488, "latency_ms": 136.279}, {"target_s": 48.16493, "latency_ms": 109.231}, {"target_s": 23.487469, "latency_ms": 123.606}, {"target_s": 46.218318, "latency_ms": 24.121}, {"target_s": 53.616685, "latency_ms": 164.809}, {"target_s": 19.22747, "latency_ms": 118.499}, {"target_s": 57.565836, "latency_ms": 153.591}, {"target_s": 13.476976, "latency_ms": 49.507}, {"target_s": 38.751547, "latency_ms": 58.064}, {"target_s": 53.089099, "latency_ms": 141.906}, {"target_s": 8.12015, "latency_ms": 181.85}, {"target_s": 47.944507, "latency_ms": 97.76}, {"target_s": 24.329387, "latency_ms": 161.296}, {"target_s": 5.659215, "latency_ms": 70.001}, {"target_s": 41.155667, "latency_ms": 168.575}, {"target_s": 21.493709, "latency_ms": 31.279}]
```

60 s samples=60; drop delta=0; CPU=54.1%; dedicated median/peak=458.9/463.9 MB; after-close samples MB=[41.415, 41.415, 41.415, 41.415, 41.415].

### bench-b2-rotation

First-frame ms: [71.193, 46.393, 45.756, 43.084, 44.492]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 43.538}, {"target_s": 31.862872, "latency_ms": 106.233}, {"target_s": 22.487508, "latency_ms": 88.411}, {"target_s": 34.804092, "latency_ms": 38.531}, {"target_s": 11.278488, "latency_ms": 41.949}, {"target_s": 48.16493, "latency_ms": 89.619}, {"target_s": 23.487469, "latency_ms": 106.586}, {"target_s": 46.218318, "latency_ms": 66.826}, {"target_s": 53.616685, "latency_ms": 57.591}, {"target_s": 19.22747, "latency_ms": 40.912}, {"target_s": 57.565836, "latency_ms": 107.428}, {"target_s": 13.476976, "latency_ms": 75.409}, {"target_s": 38.751547, "latency_ms": 78.673}, {"target_s": 53.089099, "latency_ms": 47.572}, {"target_s": 8.12015, "latency_ms": 117.477}, {"target_s": 47.944507, "latency_ms": 92.786}, {"target_s": 24.329387, "latency_ms": 112.293}, {"target_s": 5.659215, "latency_ms": 85.836}, {"target_s": 41.155667, "latency_ms": 116.012}, {"target_s": 21.493709, "latency_ms": 72.055}]
```

60 s samples=60; drop delta=0; CPU=52.8%; dedicated median/peak=192.0/200.6 MB; after-close samples MB=[41.415, 41.415, 41.415, 41.415, 41.415].

### bench-b2-vp9

First-frame ms: [50.581, 27.088, 29.055, 26.959, 28.756]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 21.044}, {"target_s": 31.862872, "latency_ms": 65.585}, {"target_s": 22.487508, "latency_ms": 41.315}, {"target_s": 34.804092, "latency_ms": 27.646}, {"target_s": 11.278488, "latency_ms": 24.256}, {"target_s": 48.16493, "latency_ms": 51.807}, {"target_s": 23.487469, "latency_ms": 21.934}, {"target_s": 46.218318, "latency_ms": 43.457}, {"target_s": 53.616685, "latency_ms": 20.12}, {"target_s": 19.22747, "latency_ms": 22.276}, {"target_s": 57.565836, "latency_ms": 62.222}, {"target_s": 13.476976, "latency_ms": 26.02}, {"target_s": 38.751547, "latency_ms": 22.159}, {"target_s": 53.089099, "latency_ms": 61.957}, {"target_s": 8.12015, "latency_ms": 63.978}, {"target_s": 47.944507, "latency_ms": 37.687}, {"target_s": 24.329387, "latency_ms": 31.015}, {"target_s": 5.659215, "latency_ms": 49.563}, {"target_s": 41.155667, "latency_ms": 25.425}, {"target_s": 21.493709, "latency_ms": 20.802}]
```

60 s samples=60; drop delta=0; CPU=53.8%; dedicated median/peak=163.5/176.7 MB; after-close samples MB=[41.419, 41.419, 41.419, 41.419, 41.419].

### bench-html5-av1

First-frame ms: [95.4, 56.7, 39.6, 23.1, 39.7]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 173.7}, {"target_s": 31.862872, "latency_ms": 123.4}, {"target_s": 22.487508, "latency_ms": 91.7}, {"target_s": 34.804092, "latency_ms": 81.3}, {"target_s": 11.278488, "latency_ms": 139.9}, {"target_s": 48.16493, "latency_ms": 129.9}, {"target_s": 23.487469, "latency_ms": 123}, {"target_s": 46.218318, "latency_ms": 22}, {"target_s": 53.616685, "latency_ms": 180.5}, {"target_s": 19.22747, "latency_ms": 126.7}, {"target_s": 57.565836, "latency_ms": 171.6}, {"target_s": 13.476976, "latency_ms": 57}, {"target_s": 38.751547, "latency_ms": 56.6}, {"target_s": 53.089099, "latency_ms": 158.1}, {"target_s": 8.12015, "latency_ms": 189.3}, {"target_s": 47.944507, "latency_ms": 114.2}, {"target_s": 24.329387, "latency_ms": 174.2}, {"target_s": 5.659215, "latency_ms": 72.9}, {"target_s": 41.155667, "latency_ms": 206.6}, {"target_s": 21.493709, "latency_ms": 38.5}]
```

60 s samples=60; drop delta=0; CPU=5.7%; dedicated median/peak=216.0/230.5 MB; after-close samples MB=[227.299, 63.242, 63.242, 63.242, 63.242].

### bench-html5-h264-final

First-frame ms: [66.3, 55, 25.4, 44.3, 45.6]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 86.5}, {"target_s": 31.862872, "latency_ms": 188.6}, {"target_s": 22.487508, "latency_ms": 175.9}, {"target_s": 34.804092, "latency_ms": 42.1}, {"target_s": 11.278488, "latency_ms": 74.9}, {"target_s": 48.16493, "latency_ms": 189.9}, {"target_s": 23.487469, "latency_ms": 179.9}, {"target_s": 46.218318, "latency_ms": 142.9}, {"target_s": 53.616685, "latency_ms": 86.7}, {"target_s": 19.22747, "latency_ms": 75.8}, {"target_s": 57.565836, "latency_ms": 211.1}, {"target_s": 13.476976, "latency_ms": 142.9}, {"target_s": 38.751547, "latency_ms": 155.9}, {"target_s": 53.089099, "latency_ms": 95.8}, {"target_s": 8.12015, "latency_ms": 222.9}, {"target_s": 47.944507, "latency_ms": 179.4}, {"target_s": 24.329387, "latency_ms": 210.1}, {"target_s": 5.659215, "latency_ms": 158.7}, {"target_s": 41.155667, "latency_ms": 221.6}, {"target_s": 21.493709, "latency_ms": 119.6}]
```

60 s samples=60; drop delta=0; CPU=4.7%; dedicated median/peak=83.1/97.6 MB; after-close samples MB=[90.3, 59.531, 59.531, 59.531, 59.531].

### bench-html5-h264

First-frame ms: [79.2, 51.4, 52.8, 50.2, 42.2]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 92.7}, {"target_s": 31.862872, "latency_ms": 190.2}, {"target_s": 22.487508, "latency_ms": 174.5}, {"target_s": 34.804092, "latency_ms": 44}, {"target_s": 11.278488, "latency_ms": 80.5}, {"target_s": 48.16493, "latency_ms": 173.6}, {"target_s": 23.487469, "latency_ms": 188.9}, {"target_s": 46.218318, "latency_ms": 138.5}, {"target_s": 53.616685, "latency_ms": 90.4}, {"target_s": 19.22747, "latency_ms": 78.6}, {"target_s": 57.565836, "latency_ms": 205.2}, {"target_s": 13.476976, "latency_ms": 138.6}, {"target_s": 38.751547, "latency_ms": 155.3}, {"target_s": 53.089099, "latency_ms": 91.4}, {"target_s": 8.12015, "latency_ms": 261.8}, {"target_s": 47.944507, "latency_ms": 161.5}, {"target_s": 24.329387, "latency_ms": 207.7}, {"target_s": 5.659215, "latency_ms": 154.8}, {"target_s": 41.155667, "latency_ms": 229}, {"target_s": 21.493709, "latency_ms": 144.9}]
```

60 s samples=60; drop delta=0; CPU=4.7%; dedicated median/peak=82.2/96.7 MB; after-close samples MB=[94.294, 91.222, 59.822, 59.822, 59.822].

### bench-html5-hevc

First-frame ms: [258.8, 22.8, 22.8, 23.1, 39.1]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 158.4}, {"target_s": 31.862872, "latency_ms": 122.6}, {"target_s": 22.487508, "latency_ms": 93.5}, {"target_s": 34.804092, "latency_ms": 72.9}, {"target_s": 11.278488, "latency_ms": 139.8}, {"target_s": 48.16493, "latency_ms": 129.7}, {"target_s": 23.487469, "latency_ms": 124.5}, {"target_s": 46.218318, "latency_ms": 13.3}, {"target_s": 53.616685, "latency_ms": 180.6}, {"target_s": 19.22747, "latency_ms": 124.6}, {"target_s": 57.565836, "latency_ms": 158}, {"target_s": 13.476976, "latency_ms": 59.3}, {"target_s": 38.751547, "latency_ms": 52.4}, {"target_s": 53.089099, "latency_ms": 173.5}, {"target_s": 8.12015, "latency_ms": 185.8}, {"target_s": 47.944507, "latency_ms": 104.6}, {"target_s": 24.329387, "latency_ms": 157.1}, {"target_s": 5.659215, "latency_ms": 71.1}, {"target_s": 41.155667, "latency_ms": 188.7}, {"target_s": 21.493709, "latency_ms": 55.9}]
```

60 s samples=60; drop delta=0; CPU=4.9%; dedicated median/peak=207.0/215.8 MB; after-close samples MB=[218.317, 63.218, 63.218, 63.218, 63.218].

### bench-html5-rotation

First-frame ms: [216.6, 26.1, 28.4, 47.1, 55]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 55.9}, {"target_s": 31.862872, "latency_ms": 141.8}, {"target_s": 22.487508, "latency_ms": 86.4}, {"target_s": 34.804092, "latency_ms": 23.9}, {"target_s": 11.278488, "latency_ms": 42.1}, {"target_s": 48.16493, "latency_ms": 128.3}, {"target_s": 23.487469, "latency_ms": 139.6}, {"target_s": 46.218318, "latency_ms": 77.4}, {"target_s": 53.616685, "latency_ms": 71.6}, {"target_s": 19.22747, "latency_ms": 60.1}, {"target_s": 57.565836, "latency_ms": 146.2}, {"target_s": 13.476976, "latency_ms": 76.1}, {"target_s": 38.751547, "latency_ms": 78.9}, {"target_s": 53.089099, "latency_ms": 38.8}, {"target_s": 8.12015, "latency_ms": 121.8}, {"target_s": 47.944507, "latency_ms": 95.4}, {"target_s": 24.329387, "latency_ms": 123}, {"target_s": 5.659215, "latency_ms": 94.5}, {"target_s": 41.155667, "latency_ms": 123.3}, {"target_s": 21.493709, "latency_ms": 107}]
```

60 s samples=60; drop delta=0; CPU=4.1%; dedicated median/peak=101.3/115.8 MB; after-close samples MB=[101.323, 89.395, 76.796, 76.796, 76.796].

### bench-html5-vp9

First-frame ms: [46.2, 37.7, 42.6, 27.5, 26.9]

Twenty seek samples:

```json
[{"target_s": 36.59416, "latency_ms": 27.1}, {"target_s": 31.862872, "latency_ms": 69.4}, {"target_s": 22.487508, "latency_ms": 59.2}, {"target_s": 34.804092, "latency_ms": 27.3}, {"target_s": 11.278488, "latency_ms": 27.2}, {"target_s": 48.16493, "latency_ms": 52.4}, {"target_s": 23.487469, "latency_ms": 6.9}, {"target_s": 46.218318, "latency_ms": 42.1}, {"target_s": 53.616685, "latency_ms": 9.8}, {"target_s": 19.22747, "latency_ms": 19.8}, {"target_s": 57.565836, "latency_ms": 78.1}, {"target_s": 13.476976, "latency_ms": 37.5}, {"target_s": 38.751547, "latency_ms": 9.2}, {"target_s": 53.089099, "latency_ms": 92.1}, {"target_s": 8.12015, "latency_ms": 80.7}, {"target_s": 47.944507, "latency_ms": 55.3}, {"target_s": 24.329387, "latency_ms": 43.9}, {"target_s": 5.659215, "latency_ms": 40.1}, {"target_s": 41.155667, "latency_ms": 31.8}, {"target_s": 21.493709, "latency_ms": 6.7}]
```

60 s samples=60; drop delta=0; CPU=5.8%; dedicated median/peak=95.0/109.5 MB; after-close samples MB=[102.47, 93.356, 93.356, 80.757, 80.757].

## Appendix: earlier preview and A/B attempts

- preview-b1: failure=RuntimeError('libmpv error -12'); samples=[]. The initial fixed run included a black first buffer; only verified frames are used in the final preview conclusion.
- preview-b1-fixed: failure=None; samples=[230.261, 396.947, 233.012, 253.002, 295.95, 211.749, 254.738, 273.98, 294.75, 275.045]. The initial fixed run included a black first buffer; only verified frames are used in the final preview conclusion.
- preview-final: failure=None; samples=[431.741, 265.796, 231.534, 253.367, 294.825, 210.945, 250.637, 274.292, 296.412, 273.783]. The initial fixed run included a black first buffer; only verified frames are used in the final preview conclusion.
- preview-verified: failure=None; samples=[603.156, 497.157, 473.724, 498.298, 528.334, 438.392, 479.408, 513.417, 541.249, 512.668]. The initial fixed run included a black first buffer; only verified frames are used in the final preview conclusion.

- probe-stack failed with libmpv -5 on external-file; plural-option probe and both 60-second stack runs succeeded. Two-instance sync was run for 60 s; all three sync cost/drift sets are reported above.

## Full configuration evidence

mpv configuration extracted from the pinned DLL:

```text
-Dprefix=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/install/x86_64-w64-mingw32 -Dlibdir=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/install/x86_64-w64-mingw32/lib -Ddefault_library=shared -Dprefer_static=true -Dgpl=false -Ddebug=true -Db_ndebug=true -Doptimization=3 -Db_lto=true -Db_lto_mode=thin -Dcplayer=false -Dlibmpv=true -Dpdf-build=disabled -Dlua=enabled -Djavascript=enabled -Dsdl2-gamepad=enabled -Dlibarchive=enabled -Dlibbluray=enabled -Ddvdnav=disabled -Duchardet=enabled -Drubberband=disabled -Dlcms2=enabled -Dopenal=disabled -Dspirv-cross=enabled -Dvulkan=enabled -Dvapoursynth=enabled -Dsubrandr=enabled -Dsixel=enabled -Dgl=enabled -Degl-angle=enabled -Dlibcurl=enabled -Dc_args=-Wno-error=int-conversion --cross-file=/__w/mpv-winbuild/mpv-winbuild/mpv-winbuild-cmake/build64/meson_cross.txt
```

Companion FFmpeg configure output (same release, not proof of the exact statically embedded FFmpeg configuration):

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
