Task ID: VE-P1e-3c1 / Cycle P1e-3c1
Status: PARTIAL

## Outcome and acceptance

Part A, the main goal, remains OPEN. Both portable build routes encountered
an official-package signing-key initialization/import failure before source
compilation. No minimal LGPL DLL, complete resolved dependency manifest,
successful rebuild recipe, embedded FFmpeg configuration proof or two clean
reproduction hashes exists. These are prerequisite attempts, not completed
source-build attempts that reached compilation. Do not ship the prebuilt DLL.

Part B's single-player B1 performance targets are met for all five fixtures.
The independent frame-step and transparency checks pass. Hover uses nearby
keyframes and a bounded cache; its timing methods and every attempt are below.
A/B remains an experiment: graph rebuilding is too slow for a smooth divider,
and a single output clock does not prove physical display synchrony.
Part C is a recommendation for the designer, not a product architecture change.

No product, package or CI file changed. No commit, push, merge or Git mutation
was performed; those belong to the operator. Final-commit CI is NOT_RUN.

## Start, environment and scope

- Read AGENTS.md, CLAUDE.md, docs/WORKSPACE.md, all of CURRENT_TASK.md,
  spikes/mpv/README.md and the P1e-3b report from origin/main's Git history.
- Task instructions were already saved by the designer; CURRENT_TASK.md was
  not edited. Read-only Git verified an initially clean working tree on
  claude/project-thread-6lra47, HEAD 4f15fc5377f2a57e38c5996ea46a2f2706402a69.
  Diff base origin/main: ed00b0388d320e1426ff6a6e66a01e371cf2ac76.
- Windows PowerShell; live GPU query: NVIDIA GeForce RTX 4060 Ti,
  driver 617.42. No driver, registry, display or persistent environment changes.
- Dot-sourced local-env.ps1 before installing/building/testing. Tests isolated
  VE_HOME, TEMP/TMP, APPDATA/LOCALAPPDATA and WebView2 profiles under scratch.
  Cargo was offline/locked, with at most two build jobs and existing caches.
- Dependency restore: 0 bytes. Existing Rust/Python/FFmpeg/mpv caches were present.
  Newly downloaded portable tooling is reported separately below.
- Normal Git was denied (Access is denied); prescribed read-only escalation
  succeeded. CIM disk query was denied; .NET DriveInfo supplied free-space data.
  Official downloads required escalation after the sandbox network failed.
- No delegation, B2 experiment, product test suite or owner-media access occurred.

## Part A: exact attempts and remaining obligations

Official portable bases, downloaded from repo.msys2.org/distrib/x86_64/ and
verified against the matching official MSYS2 GitHub release API digest:

| Archive | SHA-256 | Result |
| --- | --- | --- |
| msys2-base-x86_64-20260927.tar.xz | ea2f31a0b6ade63914ce441ffb022f0f6aa96982bfefa2326460a26d5fb01322 | PASS checksum and extraction |
| msys2-base-x86_64-20260611.tar.xz | a2d047e8ee213c3c6a49a8de427eb1069df12207c0422ff1b3cbb5c905c34221 | PASS checksum and extraction |

The first archive is 42860696 bytes. Both are portable extractions under
cache/msys2, not installer runs. No system PATH or registry change was made.
Build-tool packages only were requested; no prebuilt dependency library was
substituted into a proposed libmpv payload.

Both first-start sequences stopped at:

```text
gpg: starting migration from earlier GnuPG versions
```

The initial sandbox attempt left a lock held by MSYS PID 695. A separate
normal-session initialization waited on that lock. Only cycle-created MSYS2
processes were identified and stopped. The incomplete new keyring (1536 bytes,
11 files) was inventoried in the checkpoint report, removed after validating
its absolute cache path, and initialized again with normal signature checks.
The same migration stall recurred. The older official base also stalled.
No SigLevel change, arbitrary key trust or authentication bypass was used.

Native UCRT64 prerequisite command (20260927 base):

```sh
export PATH=/usr/bin
timeout 60 pacman -Sy --noconfirm --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-meson mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-nasm mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-python
```

Alternative mpv-winbuild-cmake prerequisite command (20260611 base, MSYS):

```sh
export PATH=/usr/bin
timeout 30 pacman -Sy --noconfirm --needed cmake ninja gcc git meson python
```

Both exited 124 after the same diagnostic and stalled import:

```text
error: clangarm64: key "5F944B027F7FE2091985AA2EFA11531AA0AA7F57" is unknown
:: Import PGP key 5F944B027F7FE2091985AA2EFA11531AA0AA7F57? [Y/n]
```

Logs: evidence/VE-P1e-3c1/native-toolchain.log and winbuild-toolchain.log.
The public signing-key fingerprint is diagnostic data, not a credential.
The downloaded alternative builder is the official shinchiro project at
1f8d2e76255abc48f0456d9be99b4cab9c6566e6; archive SHA-256 recorded locally:
0d2018d2dbc17c5ba97a791113adaa2833d1e8624df71645f0d816af87d86d38.
No separately published digest was verified for that immutable-source archive.
Its README explicitly supports MSYS2/MSYS and requires those build tools.
CMake configure and all library compilation are NOT_RUN. WSL availability
probe reported: "The Windows Subsystem for Linux is not installed."
No system installation was attempted. Cycle-created agents were stopped.

source-manifest.json distinguishes current prerequisite failures from the
historical MSVC failure, and lists every unresolved library version/checksum,
executed flag set, patch inventory and transitive audit. Its planned SPDX
entries are not a resolved inventory of a linked binary. toolchain-probe.ps1
captures the bounded prerequisite operation; it is syntax-checked, not a
successful rebuild recipe. source-build.ps1 remains the historical MSVC
diagnostic with its output redirected to this cycle's evidence path.

Output under cache/mpv-lgpl/source-build/out: 0 bytes / no DLL. Clean source
reproduction runs: 0. Source-built output SHA-256 values: unavailable.
Source-built mpv/gpl/embedded FFmpeg configuration and codec/hwdec proof:
NOT_RUN. A separate ffmpeg.exe is never used as embedded-configuration proof.
LICENSES.md keeps all these obligations explicitly OPEN and lists the licence
texts, exact-source release archive, replacement rights and relinking review
needed before distribution. No LGPL clearance or package-size promise is made.

The unchanged measurement-only fallback is 101511680 bytes, SHA-256
b9f3ddd1ef2d43d6424addb835824ddb4e1e5f72c067e2816f0e09b19a6c4752
(rechecked this cycle). Runtime property queries report mpv
v0.41.0-1288-g0fae46954, FFmpeg N-127952-gc569ebacc, and -Dgpl=false.
The full mpv configuration still enables many optional features; it is not
the requested minimal configuration and does not audit the embedded FFmpeg.
The >40 MB size is explained by the existing broad prebuilt candidate; it is
not a new minimal-build result and must never ship.

## Part B: profiling and implementation

The unchanged H.264 baseline was rerun, not taken from the prior report:
first-frame median about 444 ms and CPU about 60.6% of one core. A separately
instrumented baseline recorded 50-76 draws per second on 30 fps material;
render+Present accumulated 0.36-0.58 seconds per second in representative
playback intervals. Typical Present-inclusive draw maxima were about 8.1 ms.
One initialization draw reached 135.8 ms. Raw profile counters remain in
p1e3c1-profile-baseline.jsonl. The old host rendered on every main-loop turn,
used a 2 ms deadline and a separate 8 ms heartbeat, and never consulted
mpv_render_context_update / MPV_RENDER_UPDATE_FRAME.

Event-driven rendering alone reduced CPU to about 5.5% but retained a roughly
244 ms first-frame median. Async commands alone did not remove that penalty.
Deferring periodic telemetry while a command was pending also did not remove
it. Inspection found the step-completion branch still synchronously queried
time-pos for every pending load/seek, even when it was not a frame step.
Short-circuiting that query to actual step requests reduced the next measured
five-load median to 36.6 ms. This controlled sequence supports a render-thread
starvation cause for the 200 ms steps. The pinned upstream vo_libmpv.c flip_page
waits up to 200 ms for next_frame to be consumed, then increments its drop count.
No independent profiler attribution to a driver or WebView2 bottleneck is claimed.

Implementation:

- Both mpv wakeup and render-update callbacks wake the UI loop without calling
  mpv from the callback. Boxed callback state lives through native teardown.
- On the UI/render thread, render-context update flags gate every B1 draw.
  The mpv event queue drains to NONE. Commands use mpv_command_async.
- The heartbeat is removed. The remaining 100 ms deadline is for time display
  and bounded command timeouts. Control telemetry is deferred during a tracked
  load/seek. Native main-player exact seeks and frame steps remain exact.
- The existing flip-sequential swap chain and Present(1) were already flip
  model. A latency-waitable object was not added: the measured targets were
  met without it. Device-loss recovery remains future product work.
- Detailed draw counters are opt-in through VE_MPV_PROFILE; capture is disabled
  for timing runs. The small stdin request protocol remains for measurement.
- STACK now runs through the B1 composition host, with one lavfi output clock.
- Hover has latest-request coalescing, keyframe seeks, a 320-pixel scale filter
  and a 32-entry FIFO thumbnail cache keyed to 100 ms request bins. One obsolete
  in-flight decode may finish, but is discarded before only the newest queued
  seek is sent. Its pixels cannot be cached under a newer request's key.
  This is semantic cancellation/discard, not a separate decode worker.

### Methods and limits

Identical P1e-3b generation recipes produced local 65-second numbered fixtures.
Five reloads per clip use an initialized host, not cold product startup.
Twenty deterministic exact seeks use seed 1337 and the same 2..58 s range.
Native timing ends at PLAYBACK_RESTART after render/present, not physical light.
Each final playback run has sixty one-second process-tree CPU/PDH samples.
CPU uses cumulative CPU-time differences (one core =100%); GPU allocations are
process-scoped dedicated/shared bytes, not device-wide VRAM. Drop deltas use
start/end native counters. No other spike or GPU benchmark ran concurrently.

Step captures run separately (bench-p1e3c1-step-* with zero playback seconds);
their load/seek arrays are retained but are not the final performance matrix.
FFmpeg reference comparisons retain the prior digit confidence thresholds:
best error <0.25 and margin >0.003. All 15 main-player steps match the burned-in
numbers. The final timing properties identify d3d11va for all five clips,
including HEVC Main10, AV1 10-bit and VP9. This is fallback-DLL proof only.

Transparency recheck: PASS; blank-padding RGB error 0, 22932 changed control
pixels, visible controls and textured video. The own-window GUI routine also
exercised input/focus, resize, maximize/fullscreen, minimize/restore and synthetic
DPI messages. Real monitor moves and changed display scales are NOT_RUN.
Saved B1 transparency and hstack pictures were inspected with the image viewer.
The hstack sample shows frame 1778 on both inputs. Window titles retain the
historical spike name. Black DXGI crops were retained; WGC own-HWND fallback
supplied the valid composed pictures. No other application's window was driven.

### Hover

The first keyframe/cached run retained the old 50 ms settling delay and missed
the new-position target. Its results are retained. The measurement was changed
to wait for the actual HTMLImageElement.decode() promise, recording real image
readiness and saved pixels, instead of an arbitrary 50 ms grace period. This
is a method difference from P1e-3b's exact-frame preview and is explicitly
reported; it is not an optical display measurement. Cached measurements also
wait for decode completion. The intermediate burst-result summarizer failed
on a boolean response (AttributeError); that failed label is preserved.

The race-safe run sends 100 rapidly changing positions spanning the clip,
then checks the final request key. Separate burned-in image comparisons check
that returned pixels match their reported keyframe times. Keyframe output can
be seconds earlier than the pointer with these long-GOP fixtures: 4 s shows
0 s, 10 s shows 8.333 s, and 40 s shows 33.333 s. The main player's seeks remain
exact. No preview strip or full-resolution decode optimization was added.

### A/B feasibility and recommendation

hstack and vstack both render through B1. Crop plus hstack implements a split
view; changing the split from 50% to 25% and then 75% rebuilds lavfi-complex.
Those accepted graph changes have measured PLAYBACK_RESTART costs below.
This demonstrates a movable split experiment, not smooth pointer-rate dragging.
Both inputs use the same synthetic source; that cannot establish behavior for
arbitrary unequal media, mismatched frame rates, colour pipelines or durations.
Top-level hwdec-current is unavailable for the complex graph, so actual per-input
hardware decoding is not claimed.

The capture-on runs include six WGC captures that stall the UI and cause frame
drops. They are retained and labeled separately from capture-off CPU/GPU timing
runs. hstack digit-pair ROI RGB errors are 0.163..0.209 of 255 across six samples;
no whole-frame pair mismatch was detected, at 33.3 ms frame resolution. This
is a sampled same-clock result, not continuous optical zero drift. vstack's
half-pixel scaled pair comparison has 6.47..6.96 RGB error and is inconclusive
as an independent exact-frame oracle. A single filter output still has one
clock by construction. Split-view graph output likewise has one output clock;
independent numerical drift proof for the cropped halves is NOT_AVAILABLE.

Recommend a single-mpv hstack as the first P1e-3c2 before/after implementation,
subject to Part A clearance and designer approval. Keep the crop/divider path
experimental until graph changes avoid the measured several-hundred-ms rebuild
pause. No two-instance synchronization strategy was substituted. CPU/GPU costs
and capture effects are quantified in the tables below.

### Lazy load

The lazy test starts an empty B1 host with VE_MPV_DEFER_OPEN. Module-map evidence
shows no libmpv before open, libmpv after open, and no libmpv after close while
the same host remains alive. libloading uses Windows dynamic loading; dropping
all render contexts and mpv instances releases its DLL handle. Five post-close
samples are retained. The DLL+mpv initialization time excludes WebView2 creation;
the separately reported composition-open time includes it. RAM does not return
to the pre-open level; this is disclosed below rather than claiming zero residue.

## Part C: proposed P1e-3c2 product boundary

Recommend a custom WebView2 composition host for the player window only,
keeping the existing product Home under Tauri. Current main.rs builds the main
WebviewWindow from configuration, navigation restrictions and popup denial;
window.rs uses tauri::WebviewWindow for theme, zoom, memory targets and lifecycle
helpers. A native player HWND needs an explicit adapter for those behaviours,
its own lifetime, input/focus, DPI, accessibility and device-loss handling.
Nothing in those product files was modified this cycle.

The cached pinned wry 0.57.0 Windows source creates a normal
CreateCoreWebView2Controller[WithOptions], and its public WebViewExtWindows
exposes that controller/environment/webview. The product's existing
with_webview hook operates on that already-created normal controller; it is
not a factory for a composition controller/RootVisualTarget. Do not assume
it can convert the existing controller into B1. A wry/Tauri extension route
would need a composition-controller creation option in wry, RootVisualTarget
and input/lifetime access, plus plumbing through tauri-runtime-wry/window
construction. That increases upgrade and Runtime regression risk. A narrowly
wrapped native player avoids maintaining that broader fork, at the cost of
implementing an explicit product IPC adapter. These are code-based proposals,
not a tested integration or an assertion about future upstream APIs.

Recommended IPC: versioned allowlisted commands for open/close, play/pause,
absolute exact seek, frame step/back, volume, fullscreen and hover with request
IDs/generations; events for loaded/error/EOF, pause/duration/position, seek and
frame completion, decoder stats and preview readiness. Rate-limit position
updates to about 10 Hz; render callbacks are not HTML messages. Validate media
through the existing Rust media layer and use opaque handles in HTML. Enforce
origin/navigation restrictions and never expose arbitrary native mpv commands
to untrusted pages. Cache keys in the product must include media identity.
The spike currently logs asynchronous mpv errors on stderr and has one pending
tracked request; product IPC needs proper per-request completion/error routing.

CPU-only Windows CI can build/lint the isolated host and later test command
validation, latest-request/cache state, lifecycle and lazy-load contracts with
controlled fixtures. Ubuntu CI can lint Python/formatting and validate manifest
schema/source hashes; it cannot exercise this Windows-native spike as a GUI.
The GPU PC must verify D3D11VA for each codec, composed transparency, true display
DPI/focus, frame-number accuracy, performance, PDH residuals and device loss.
Do not infer those from CPU CI. Existing CI was not modified or bypassed.

Package increase this cycle: 0 bytes. A future minimal DLL's size, licence-text
bundle and exact corresponding-source archive size are UNKNOWN because Part A
failed. The existing 101.511680 MB DLL is not a deliverable estimate. Exact
source/build archives should accompany every release; the replacement and
relinking arrangement must be reviewed before packaging.

## Questions for the designer (defaults chosen; no question stopped work)

1. Portable package-key initialization failed in both environments. Default:
   retain signature checks, keep portable caches, stop retrying that failure,
   measure only the unchanged prebuilt candidate, and leave Part A OPEN/PARTIAL.
   The operator needs a working official-key initialization before source work
   can resume. No system install or trust bypass is recommended.
2. B1 already meets single-player timing targets with the existing flip model.
   Default: do not add a latency-waitable-object path in this spike.
3. Product integration route. Default recommendation: player-only custom B1
   wrapper and explicit restricted IPC; await approved P1e-3c2 design before any
   product change. No product architecture decision was implemented here.
4. Compare method. Default recommendation: one-clock hstack first; keep movable
   crop-divider experimental because graph changes pause. Source clearance is
   a prerequisite to packaging, regardless of performance.

## Expected / Actual and intentional omissions

Expected: a reproducible minimal source DLL plus complete audit, and fast B1.
Actual: source prerequisites failed; fast single-player B1 and separate preview,
A/B, alpha, stepping and lazy-load evidence are delivered. This is PARTIAL,
not completion of Part A. No source reproduction or embedded-library proof was
fabricated. The operator still owns final commit, push and Windows/Ubuntu CI.
Product tests/builds were intentionally NOT_RUN under the explicit unchanged-
product waiver. No B2 work, owner check, paid tool, product deployment, physical
monitor change or arbitrary-window automation occurred. No test was disabled
or weakened. The stronger hover image-decode readiness method is documented.

## Validation failures retained

- First sandbox baseline: Prototype response timeout; driver exit 0 does not
  make that a successful performance run. A new-label normal-session run passed.
- All portable initialization/import failures above remain failures.
- Ad-hoc editing/report commands had PowerShell quoting/redirection parse errors;
  no source edit occurred through it; apply_patch supplied the actual change.
- First static run: clippy possible_missing_else at two compact statement
  boundaries, ruff E501 and formatting. Corrected with newlines/formatting,
  without allowing, disabling or relaxing any check.
- preview-p1e3c1-decode-ready: AttributeError in burst-result aggregation;
  corrected to handle boolean and dictionary responses. All labels retained.
- Capture-on A/B dropped frames; capture-off repeats measure the cleaner cost.
- Git warned about future LF-to-CRLF conversion; Git configuration was unchanged.

## Changed files

- .ai/LAST_REPORT.md
- spikes/mpv/src/main.rs, src/mpv.rs, src/composition.rs
- spikes/mpv/measure.py, frame_check.py, smoke.py
- spikes/mpv/source-manifest.json, LICENSES.md, source-build.ps1
- spikes/mpv/toolchain-probe.ps1 (new prerequisite diagnostic)
- spikes/mpv/README.md

CURRENT_TASK.md's base difference is designer-owned and was not edited.
No product, CI, dependency lockfile, binary or build-output change is included.

## Cleanup inventory before deletion

- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-results.json: 79783 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-step-0-wgc.png: 506624 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-step-0.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-step-1-wgc.png: 510673 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-step-1.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-step-2-wgc.png: 506624 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated-step-2.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated.jsonl: 174644 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-escalated.stderr.log: 0 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264-results.json: 153 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264.jsonl: 32710 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-baseline-h264.stderr.log: 0 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-results.json: 79616 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-step-0-wgc.png: 506624 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-step-0.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-step-1-wgc.png: 510673 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-step-1.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-step-2-wgc.png: 506624 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1-step-2.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1.jsonl: 173512 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-event-h264-run1.stderr.log: 0 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-results.json: 61551 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-step-0-wgc.png: 506624 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-step-0.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-step-1-wgc.png: 510673 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-step-1.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-step-2-wgc.png: 506624 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline-step-2.png: 5047 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline.jsonl: 93541 bytes; Duplicate of verified cycle evidence.
- evidence\VE-P1e-3b\section13\p1e3c1-profile-baseline.stderr.log: 0 bytes; Duplicate of verified cycle evidence.
- scratch\mpv-spike: 500618294 bytes; Cycle temporary artifacts.
- scratch\tmp: 16903 bytes; Cycle temporary artifacts.
- evidence\VE-P1f-3b: 11151809 bytes; Older fourth evidence cycle; retain last three.

## Cleanup rejection / For the owner to delete

The batch deletion was rejected before process creation; none of its commands
ran. No deletion from that batch occurred and no workaround or narrower retry
was attempted. The exact automatic approval-review reason was:

```text
This action was rejected due to unacceptable risk.
Reason: The command irreversibly deletes hundreds of MB of scratch data plus prior-cycle evidence, exceeding the retained authorization to clean temporary scratch artifacts; explicit approval is absent for deleting historical evidence.
Do not bypass this rejection through a workaround or indirect execution.
```

**For the owner to delete:** every exact path and logical byte size in the
"Cleanup inventory before deletion" section above, also recorded separately
in evidence/VE-P1e-3c1/cleanup-candidates.json. The copied baseline evidence was
hash-compared before it was proposed for removal from the legacy directory;
the current-cycle copies remain available. The older fourth evidence cycle
also remains because deletion was rejected. This is a failed retention/scratch
cleanup gate, not a successful cleanup. A read-only process check found no
cycle spike or scratch-profile WebView2 process still running.

The original fixture helper wrote regenerated fixture logs to its legacy
P1e-3b evidence path before it was updated. Current-generation logs were copied
to this cycle's fixtures folder; the old-path logs are not historical proof.
The historical tracked P1e-3b report was read from Git and was not rewritten.
The existing MSYS2 source/tool caches are intentionally retained, including
the failed initialization state. No intermediate source build exceeded 5 GB.

## Measured result tables

### Final B1 matrix (capture and detailed profile off)

| Clip | First median ms (5) | Seek median / worst ms (20) | CPU % | Drops / 60 s | Exact steps | Actual hwdec | Targets |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| av1-10bit-1440p60.mp4 | 34.5 | 131.5 / 197.5 | 7.9 | 0 | 3/3 PASS | d3d11va | PASS |
| h264-1080p30.mp4 | 39.8 | 160.6 / 231.3 | 6.3 | 0 | 3/3 PASS | d3d11va | PASS |
| hevc-main10-1440p60.mp4 | 37.2 | 119.0 / 181.1 | 8.2 | 0 | 3/3 PASS | d3d11va | PASS |
| hevc-rotation-display.mp4 | 38.8 | 83.0 / 123.0 | 5.0 | 0 | 3/3 PASS | d3d11va | PASS |
| vp9-1080p60.mp4 | 25.0 | 30.6 / 72.4 | 10.6 | 0 | 3/3 PASS | d3d11va | PASS |

Each CPU estimate spans the first-to-last of sixty 1 Hz samples (about 59 s
within a 60 s playback). Timing raw arrays and full process samples follow.

### Every other benchmark attempt

| Label | Load / seek count | First median ms | Seek median / worst ms | CPU % | Playback samples | Failure / purpose |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| bench-p1e3c1-step-av1-10bit-1440p60 | 5 / 20 | 29.6 | 133.3 / 197.3 | N/A | 0 | Capture/frame validation, not a performance run |
| bench-p1e3c1-step-h264-1080p30 | 5 / 20 | 39.7 | 159.5 / 231.3 | N/A | 0 | Capture/frame validation, not a performance run |
| bench-p1e3c1-step-hevc-main10-1440p60 | 5 / 20 | 30.8 | 120.9 / 184.0 | N/A | 0 | Capture/frame validation, not a performance run |
| bench-p1e3c1-step-hevc-rotation-display | 5 / 20 | 39.3 | 85.4 / 123.0 | N/A | 0 | Capture/frame validation, not a performance run |
| bench-p1e3c1-step-vp9-1080p60 | 5 / 20 | 30.6 | 30.1 / 71.7 | N/A | 0 | Capture/frame validation, not a performance run |
| p1e3c1-async-h264-run1 | 5 / 20 | 244.4 | 163.8 / 426.5 | 6.0 | 60 | Diagnostic or baseline; not final matrix |
| p1e3c1-baseline-h264 | 0 / 0 | N/A | N/A / N/A | N/A | 0 | TimeoutError('Prototype response timeout') |
| p1e3c1-baseline-h264-escalated | 5 / 20 | 443.7 | 386.3 / 657.9 | 60.6 | 60 | Diagnostic or baseline; not final matrix |
| p1e3c1-event-h264-run1 | 5 / 20 | 244.0 | 165.6 / 426.1 | 5.5 | 60 | Diagnostic or baseline; not final matrix |
| p1e3c1-no-poll-h264 | 5 / 20 | 245.5 | 163.1 / 239.7 | 10.5 | 5 | Diagnostic or baseline; not final matrix |
| p1e3c1-poll-fix-h264 | 5 / 20 | 36.6 | 165.4 / 237.8 | 5.5 | 5 | Diagnostic or baseline; not final matrix |
| p1e3c1-profile-baseline | 5 / 20 | 442.3 | 419.3 / 651.7 | 63.3 | 5 | Diagnostic or baseline; not final matrix |
| p1e3c1-profile-final | 5 / 20 | 40.0 | 159.8 / 233.0 | 4.3 | 5 | Diagnostic or baseline; not final matrix |

### Every hover attempt

| Label | New median / max ms | Cached median / max ms | Samples | Outcome |
| --- | ---: | ---: | ---: | --- |
| preview-p1e3c1-decode-ready | N/A / N/A | N/A / N/A | 0 | AttributeError("'bool' object has no attribute 'get'") |
| preview-p1e3c1-final | 115.8 / 147.1 | 9.4 / 12.7 | 10 | PASS targets |
| preview-p1e3c1-hover | 164.9 / 182.6 | 4.6 / 7.2 | 10 | FAIL new-position target; retained |
| preview-p1e3c1-race-safe | 118.0 / 140.1 | 9.4 / 13.5 | 10 | PASS targets |

Final race-safe burst: 100 requests, 92 cancelled in drained batches, final key 411, displayed time 33.333333, status PASS. One obsolete in-flight decode can finish and is discarded. Final ten new-position pixels passed independent burned-in keyframe identification; 30/30 across the three completed hover runs.

### A/B, H.264, sixty samples per run

| Label | Capture | CPU % | Dedicated median / peak MB | Shared peak MB | Drop counter start / end / max sampled |
| --- | --- | ---: | ---: | ---: | --- |
| p1e3c1-divider | on | 31.6 | 294.3 / 303.7 | 61.7 | 0 / 37 / 41 |
| p1e3c1-divider-timing | off | 20.8 | 286.2 / 287.5 | 64.8 | 0 / 0 / 0 |
| p1e3c1-hstack | on | 29.3 | 342.4 / 351.1 | 68.0 | 0 / 137 / 137 |
| p1e3c1-hstack-timing | off | 22.9 | 333.7 / 335.0 | 67.9 | 0 / 0 / 0 |
| p1e3c1-vstack | on | 30.4 | 337.4 / 346.1 | 67.9 | 0 / 157 / 157 |
| p1e3c1-vstack-timing | off | 24.3 | 328.6 / 329.9 | 68.1 | 0 / 0 / 0 |

Divider changes for p1e3c1-divider: [{"fraction": 0.25, "native_restart_ms": 422.308, "request_wall_ms": 429.963}, {"fraction": 0.75, "native_restart_ms": 698.471, "request_wall_ms": 706.11}].

Divider changes for p1e3c1-divider-timing: [{"fraction": 0.25, "native_restart_ms": 403.601, "request_wall_ms": 411.348}, {"fraction": 0.75, "native_restart_ms": 694.161, "request_wall_ms": 702.203}].

Graph rebuilds can reset counters; start/end are raw counter observations,
not summed lifetime drops across resets. Capture-off runs sampled only zeros.
The pair ROI checks are in ab-pair-checks.json; no continuous optical drift
or per-input decoder claim is made.

### Lazy load, one open/close cycle

DLL+mpv initialization: 18.6055 ms; full composition open: 678.9538 ms. Module presence before/open/after: False/True/False. Host alive after close: True.

| Phase | RSS MB | Dedicated MB | Shared MB |
| --- | ---: | ---: | ---: |
| Before open | 28.541 | 0.000 | 0.000 |
| Playing | 492.442 | 185.541 | 26.468 |
| After close 1 s | 100.073 | 0.000 | 0.000 |
| After close 2 s | 100.073 | 0.000 | 0.000 |
| After close 3 s | 100.024 | 0.000 | 0.000 |
| After close 4 s | 100.024 | 0.000 | 0.000 |
| After close 5 s | 100.024 | 0.000 | 0.000 |

Final RSS is 71.483 MB above before-open RSS. GPU allocation returns to 0/0 and the DLL unloads; the host retains native heap/runtime pages. This one-cycle result does not prove absence of long-run leaks.

## Validation summary

| Check | Status |
| --- | --- |
| Final cargo fmt --check | PASS |
| Final offline/locked cargo clippy -- -D warnings | PASS |
| Final offline/locked cargo build | PASS |
| Final spike ruff check and ruff format --check | PASS, 7 Python files |
| New PowerShell diagnostic parse | PASS; diagnostic invocation NOT_RUN |
| Final source-manifest JSON parse | PASS; resolved dependency/source-build acceptance NOT_MET |
| Final read-only Git diff --check origin/main and scope review | PASS; only allowed paths, plus the new spike diagnostic; designer CURRENT_TASK base difference preserved |
| Source-build routes | FAIL prerequisite setup, exit 124; compilation NOT_RUN |
| Clean source reproduction | NOT_RUN, zero successful builds |
| B1 five-clip timing matrix | PASS all stated targets |
| Burned-in main-player frame steps | PASS 15/15 |
| Completed hover returned-frame comparisons | PASS 30/30; final ten are from race-safe run |
| Final transparency self-check | PASS |
| Latest-request burst and thumbnail cache | PASS stated samples; obsolete in-flight work is discarded |
| Lazy DLL boundary and post-close GPU | PASS stated one-cycle module/PDH checks; RSS residual disclosed |
| A/B hstack/vstack/split | Feasible experiment, measured; divider not smooth, drift limits stated |
| Scratch / historical evidence cleanup | NOT_RUN: automatic approval review rejected deletion before launch |
| Product build/test/lint | NOT_RUN, unchanged-product waiver |
| Windows / Ubuntu CI on final commit | NOT_RUN, operator must commit/push and verify |

The final render profile records about 30-31 draws/s during steady 30 fps
playback, with 12.1-12.9 ms total draw/Present time per approximately one-second
interval and maxima about 0.44-0.55 ms. It records zero draws after close.
Initialization and load/seek intervals are separately present in the raw profile.

## Appendix: all numeric timing arrays

All labels refer to evidence/VE-P1e-3c1/<label>-results.json and adjacent
NDJSON/stderr/capture files. Raw targets, properties, all 1 Hz CPU/GPU samples
and timestamps remain there. Arrays below round milliseconds to three decimals;
the JSON evidence retains original precision. Failed runs are not omitted.

### bench-p1e3c1-step-av1-10bit-1440p60

Failure: None

First-frame ms: [28.066, 35.66, 26.88, 34.293, 29.608]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 159.964}, {"target_s": 31.862872, "ms": 144.972}, {"target_s": 22.487508, "ms": 84.423}, {"target_s": 34.804092, "ms": 78.198}, {"target_s": 11.278488, "ms": 149.626}, {"target_s": 48.16493, "ms": 120.294}, {"target_s": 23.487469, "ms": 135.875}, {"target_s": 46.218318, "ms": 24.066}, {"target_s": 53.616685, "ms": 184.194}, {"target_s": 19.22747, "ms": 130.806}, {"target_s": 57.565836, "ms": 174.804}, {"target_s": 13.476976, "ms": 51.18}, {"target_s": 38.751547, "ms": 67.535}, {"target_s": 53.089099, "ms": 159.485}, {"target_s": 8.12015, "ms": 197.264}, {"target_s": 47.944507, "ms": 119.325}, {"target_s": 24.329387, "ms": 171.932}, {"target_s": 5.659215, "ms": 78.292}, {"target_s": 41.155667, "ms": 184.771}, {"target_s": 21.493709, "ms": 38.758}]
```

### bench-p1e3c1-step-h264-1080p30

Failure: None

First-frame ms: [39.065, 40.078, 38.372, 46.225, 39.731]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 85.935}, {"target_s": 31.862872, "ms": 207.81}, {"target_s": 22.487508, "ms": 166.427}, {"target_s": 34.804092, "ms": 46.661}, {"target_s": 11.278488, "ms": 88.655}, {"target_s": 48.16493, "ms": 186.04}, {"target_s": 23.487469, "ms": 196.913}, {"target_s": 46.218318, "ms": 130.575}, {"target_s": 53.616685, "ms": 110.726}, {"target_s": 19.22747, "ms": 74.737}, {"target_s": 57.565836, "ms": 216.673}, {"target_s": 13.476976, "ms": 148.817}, {"target_s": 38.751547, "ms": 155.839}, {"target_s": 53.089099, "ms": 91.941}, {"target_s": 8.12015, "ms": 231.345}, {"target_s": 47.944507, "ms": 183.795}, {"target_s": 24.329387, "ms": 220.325}, {"target_s": 5.659215, "ms": 163.155}, {"target_s": 41.155667, "ms": 223.935}, {"target_s": 21.493709, "ms": 141.556}]
```

### bench-p1e3c1-step-hevc-main10-1440p60

Failure: None

First-frame ms: [40.011, 29.277, 28.649, 30.807, 31.096]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 150.562}, {"target_s": 31.862872, "ms": 133.426}, {"target_s": 22.487508, "ms": 82.798}, {"target_s": 34.804092, "ms": 72.162}, {"target_s": 11.278488, "ms": 140.18}, {"target_s": 48.16493, "ms": 112.208}, {"target_s": 23.487469, "ms": 122.128}, {"target_s": 46.218318, "ms": 22.103}, {"target_s": 53.616685, "ms": 167.199}, {"target_s": 19.22747, "ms": 119.663}, {"target_s": 57.565836, "ms": 158.161}, {"target_s": 13.476976, "ms": 50.866}, {"target_s": 38.751547, "ms": 63.168}, {"target_s": 53.089099, "ms": 145.498}, {"target_s": 8.12015, "ms": 184.008}, {"target_s": 47.944507, "ms": 101.293}, {"target_s": 24.329387, "ms": 162.369}, {"target_s": 5.659215, "ms": 74.324}, {"target_s": 41.155667, "ms": 170.676}, {"target_s": 21.493709, "ms": 34.974}]
```

### bench-p1e3c1-step-hevc-rotation-display

Failure: None

First-frame ms: [33.693, 47.002, 38.512, 44.812, 39.258]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 48.548}, {"target_s": 31.862872, "ms": 109.607}, {"target_s": 22.487508, "ms": 86.589}, {"target_s": 34.804092, "ms": 30.318}, {"target_s": 11.278488, "ms": 42.636}, {"target_s": 48.16493, "ms": 99.231}, {"target_s": 23.487469, "ms": 99.275}, {"target_s": 46.218318, "ms": 70.754}, {"target_s": 53.616685, "ms": 53.939}, {"target_s": 19.22747, "ms": 41.905}, {"target_s": 57.565836, "ms": 113.673}, {"target_s": 13.476976, "ms": 78.253}, {"target_s": 38.751547, "ms": 84.232}, {"target_s": 53.089099, "ms": 48.975}, {"target_s": 8.12015, "ms": 123.017}, {"target_s": 47.944507, "ms": 95.113}, {"target_s": 24.329387, "ms": 116.158}, {"target_s": 5.659215, "ms": 87.417}, {"target_s": 41.155667, "ms": 114.903}, {"target_s": 21.493709, "ms": 74.561}]
```

### bench-p1e3c1-step-vp9-1080p60

Failure: None

First-frame ms: [30.554, 25.114, 32.579, 32.702, 24.983]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 16.938}, {"target_s": 31.862872, "ms": 64.482}, {"target_s": 22.487508, "ms": 48.057}, {"target_s": 34.804092, "ms": 27.217}, {"target_s": 11.278488, "ms": 24.964}, {"target_s": 48.16493, "ms": 49.358}, {"target_s": 23.487469, "ms": 16.322}, {"target_s": 46.218318, "ms": 50.971}, {"target_s": 53.616685, "ms": 16.154}, {"target_s": 19.22747, "ms": 16.341}, {"target_s": 57.565836, "ms": 71.198}, {"target_s": 13.476976, "ms": 25.364}, {"target_s": 38.751547, "ms": 16.846}, {"target_s": 53.089099, "ms": 71.721}, {"target_s": 8.12015, "ms": 61.069}, {"target_s": 47.944507, "ms": 38.821}, {"target_s": 24.329387, "ms": 32.98}, {"target_s": 5.659215, "ms": 52.803}, {"target_s": 41.155667, "ms": 26.011}, {"target_s": 21.493709, "ms": 16.187}]
```

### p1e3c1-async-h264-run1

Failure: None

First-frame ms: [235.567, 243.687, 244.788, 443.303, 244.399]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 82.163}, {"target_s": 31.862872, "ms": 202.91}, {"target_s": 22.487508, "ms": 167.879}, {"target_s": 34.804092, "ms": 44.455}, {"target_s": 11.278488, "ms": 88.194}, {"target_s": 48.16493, "ms": 188.513}, {"target_s": 23.487469, "ms": 196.533}, {"target_s": 46.218318, "ms": 135.535}, {"target_s": 53.616685, "ms": 307.806}, {"target_s": 19.22747, "ms": 57.933}, {"target_s": 57.565836, "ms": 216.538}, {"target_s": 13.476976, "ms": 151.646}, {"target_s": 38.751547, "ms": 159.678}, {"target_s": 53.089099, "ms": 92.645}, {"target_s": 8.12015, "ms": 236.178}, {"target_s": 47.944507, "ms": 176.005}, {"target_s": 24.329387, "ms": 418.544}, {"target_s": 5.659215, "ms": 144.808}, {"target_s": 41.155667, "ms": 426.523}, {"target_s": 21.493709, "ms": 125.389}]
```

CPU cumulative seconds: [3.5, 3.53125, 3.546875, 3.625, 3.671875, 3.6875, 3.703125, 3.78125, 3.84375, 3.890625, 3.9375, 4.0, 4.046875, 4.171875, 4.25, 4.28125, 4.375, 4.46875, 4.484375, 4.515625, 4.578125, 4.671875, 4.734375, 4.796875, 4.921875, 4.984375, 5.09375, 5.125, 5.171875, 5.234375, 5.3125, 5.328125, 5.46875, 5.53125, 5.546875, 5.671875, 5.6875, 5.734375, 5.8125, 5.875, 5.890625, 5.890625, 5.96875, 5.984375, 6.015625, 6.046875, 6.0625, 6.09375, 6.15625, 6.203125, 6.28125, 6.328125, 6.34375, 6.546875, 6.640625, 6.703125, 6.734375, 6.859375, 6.9375, 7.0625]

Dedicated MB: [196.084, 195.944, 195.94, 195.94, 195.936, 195.936, 195.936, 195.928, 195.928, 195.928, 195.936, 195.932, 195.936, 195.932, 195.936, 195.936, 195.936, 195.928, 195.936, 195.928, 195.936, 195.928, 195.936, 195.936, 195.936, 195.932, 194.687, 194.691, 194.691, 194.691, 194.691, 194.691, 194.687, 194.691, 194.687, 194.691, 194.666, 194.666, 194.671, 194.671, 194.675, 194.675, 194.675, 194.671, 194.671, 194.671, 194.671, 194.675, 194.666, 194.675, 194.671, 194.675, 194.671, 194.666, 194.675, 194.675, 194.666, 194.675, 194.666, 194.666]

### p1e3c1-baseline-h264

Failure: TimeoutError('Prototype response timeout')

First-frame ms: []

Seek {target_s, ms}:
```json
[]
```

### p1e3c1-baseline-h264-escalated

Failure: None

First-frame ms: [633.096, 443.664, 444.177, 438.08, 441.467]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 408.26}, {"target_s": 31.862872, "ms": 381.159}, {"target_s": 22.487508, "ms": 526.274}, {"target_s": 34.804092, "ms": 299.194}, {"target_s": 11.278488, "ms": 191.258}, {"target_s": 48.16493, "ms": 441.335}, {"target_s": 23.487469, "ms": 575.625}, {"target_s": 46.218318, "ms": 391.385}, {"target_s": 53.616685, "ms": 197.808}, {"target_s": 19.22747, "ms": 319.395}, {"target_s": 57.565836, "ms": 422.791}, {"target_s": 13.476976, "ms": 199.306}, {"target_s": 38.751547, "ms": 291.292}, {"target_s": 53.089099, "ms": 326.03}, {"target_s": 8.12015, "ms": 657.93}, {"target_s": 47.944507, "ms": 372.808}, {"target_s": 24.329387, "ms": 642.311}, {"target_s": 5.659215, "ms": 297.72}, {"target_s": 41.155667, "ms": 459.12}, {"target_s": 21.493709, "ms": 483.189}]
```

CPU cumulative seconds: [10.4375, 10.953125, 11.453125, 12.078125, 12.6875, 13.28125, 13.921875, 14.5, 15.21875, 15.921875, 16.5, 17.140625, 17.796875, 18.5, 19.25, 19.875, 20.59375, 21.203125, 21.84375, 22.46875, 23.015625, 23.53125, 24.03125, 24.609375, 25.21875, 25.8125, 26.40625, 26.921875, 27.484375, 28.015625, 28.625, 29.15625, 29.703125, 30.28125, 31.0, 31.734375, 32.34375, 32.921875, 33.5, 34.15625, 34.890625, 35.515625, 36.171875, 36.875, 37.546875, 38.234375, 38.796875, 39.46875, 40.046875, 40.609375, 41.171875, 41.71875, 42.21875, 42.765625, 43.3125, 43.859375, 44.390625, 44.921875, 45.578125, 46.171875]

Dedicated MB: [205.898, 205.898, 205.898, 205.89, 205.898, 205.898, 205.89, 205.898, 205.873, 205.881, 205.881, 205.881, 205.873, 205.873, 205.873, 205.873, 205.881, 205.873, 205.873, 205.881, 205.873, 205.873, 205.881, 205.881, 205.881, 205.881, 205.881, 205.881, 205.881, 205.873, 205.881, 205.881, 205.881, 205.873, 205.873, 205.881, 205.881, 205.881, 205.881, 205.881, 205.881, 205.881, 205.873, 205.881, 205.873, 205.881, 205.881, 205.873, 205.873, 205.873, 205.881, 205.881, 205.881, 205.873, 205.881, 205.881, 205.873, 205.881, 205.881, 205.881]

### p1e3c1-event-h264-run1

Failure: None

First-frame ms: [229.445, 243.576, 245.895, 244.048, 442.966]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 79.976}, {"target_s": 31.862872, "ms": 205.372}, {"target_s": 22.487508, "ms": 166.744}, {"target_s": 34.804092, "ms": 47.454}, {"target_s": 11.278488, "ms": 86.799}, {"target_s": 48.16493, "ms": 185.738}, {"target_s": 23.487469, "ms": 194.662}, {"target_s": 46.218318, "ms": 130.812}, {"target_s": 53.616685, "ms": 306.219}, {"target_s": 19.22747, "ms": 56.439}, {"target_s": 57.565836, "ms": 215.234}, {"target_s": 13.476976, "ms": 150.039}, {"target_s": 38.751547, "ms": 160.052}, {"target_s": 53.089099, "ms": 92.739}, {"target_s": 8.12015, "ms": 231.771}, {"target_s": 47.944507, "ms": 175.476}, {"target_s": 24.329387, "ms": 217.614}, {"target_s": 5.659215, "ms": 164.391}, {"target_s": 41.155667, "ms": 426.084}, {"target_s": 21.493709, "ms": 123.841}]
```

CPU cumulative seconds: [7.34375, 7.375, 7.4375, 7.5, 7.5625, 7.75, 7.796875, 7.875, 7.9375, 7.9375, 7.953125, 7.96875, 8.078125, 8.09375, 8.09375, 8.125, 8.140625, 8.140625, 8.28125, 8.328125, 8.359375, 8.40625, 8.453125, 8.484375, 8.53125, 8.625, 8.703125, 8.703125, 8.71875, 8.765625, 8.84375, 8.875, 8.90625, 9.046875, 9.046875, 9.171875, 9.21875, 9.234375, 9.25, 9.359375, 9.40625, 9.484375, 9.5, 9.578125, 9.640625, 9.6875, 9.71875, 9.75, 9.8125, 9.90625, 10.09375, 10.1875, 10.265625, 10.296875, 10.359375, 10.421875, 10.4375, 10.46875, 10.515625, 10.59375]

Dedicated MB: [206.049, 205.91, 205.91, 205.91, 205.906, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.898, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.902, 205.894, 205.894, 205.894, 205.894, 205.894, 205.898, 205.898, 205.902, 205.898, 205.898, 205.898, 205.898, 205.894, 205.894, 205.894, 205.894]

### p1e3c1-final-av1-10bit-1440p60

Failure: None

First-frame ms: [35.856, 26.868, 27.505, 34.464, 35.401]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 156.827}, {"target_s": 31.862872, "ms": 143.354}, {"target_s": 22.487508, "ms": 86.909}, {"target_s": 34.804092, "ms": 78.313}, {"target_s": 11.278488, "ms": 148.821}, {"target_s": 48.16493, "ms": 121.986}, {"target_s": 23.487469, "ms": 133.431}, {"target_s": 46.218318, "ms": 23.738}, {"target_s": 53.616685, "ms": 184.017}, {"target_s": 19.22747, "ms": 129.526}, {"target_s": 57.565836, "ms": 171.881}, {"target_s": 13.476976, "ms": 49.832}, {"target_s": 38.751547, "ms": 67.908}, {"target_s": 53.089099, "ms": 157.275}, {"target_s": 8.12015, "ms": 197.479}, {"target_s": 47.944507, "ms": 117.56}, {"target_s": 24.329387, "ms": 170.213}, {"target_s": 5.659215, "ms": 78.966}, {"target_s": 41.155667, "ms": 185.526}, {"target_s": 21.493709, "ms": 34.41}]
```

CPU cumulative seconds: [3.453125, 3.5, 3.578125, 3.609375, 3.65625, 3.734375, 3.921875, 3.984375, 4.03125, 4.109375, 4.203125, 4.3125, 4.40625, 4.4375, 4.53125, 4.625, 4.71875, 4.734375, 4.8125, 4.859375, 4.90625, 5.0, 5.125, 5.234375, 5.328125, 5.453125, 5.453125, 5.46875, 5.515625, 5.5625, 5.59375, 5.640625, 5.796875, 5.890625, 5.984375, 6.125, 6.21875, 6.28125, 6.328125, 6.34375, 6.421875, 6.53125, 6.609375, 6.671875, 6.75, 6.765625, 6.875, 6.984375, 7.125, 7.1875, 7.203125, 7.296875, 7.375, 7.4375, 7.546875, 7.578125, 7.671875, 7.828125, 8.015625, 8.140625]

Dedicated MB: [327.852, 327.717, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.709, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 327.643, 326.267, 326.267, 326.267, 326.267, 326.267, 326.267, 326.267, 326.267, 326.267, 326.267]

### p1e3c1-final-h264-1080p30

Failure: None

First-frame ms: [39.794, 40.62, 37.838, 46.976, 36.659]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 86.588}, {"target_s": 31.862872, "ms": 201.416}, {"target_s": 22.487508, "ms": 166.433}, {"target_s": 34.804092, "ms": 46.945}, {"target_s": 11.278488, "ms": 89.493}, {"target_s": 48.16493, "ms": 189.182}, {"target_s": 23.487469, "ms": 194.108}, {"target_s": 46.218318, "ms": 131.646}, {"target_s": 53.616685, "ms": 111.523}, {"target_s": 19.22747, "ms": 72.075}, {"target_s": 57.565836, "ms": 220.202}, {"target_s": 13.476976, "ms": 150.914}, {"target_s": 38.751547, "ms": 157.118}, {"target_s": 53.089099, "ms": 92.234}, {"target_s": 8.12015, "ms": 231.335}, {"target_s": 47.944507, "ms": 180.321}, {"target_s": 24.329387, "ms": 218.022}, {"target_s": 5.659215, "ms": 164.005}, {"target_s": 41.155667, "ms": 222.462}, {"target_s": 21.493709, "ms": 140.33}]
```

CPU cumulative seconds: [3.96875, 4.0625, 4.171875, 4.21875, 4.28125, 4.328125, 4.484375, 4.484375, 4.5, 4.53125, 4.5625, 4.640625, 4.703125, 4.765625, 4.828125, 4.9375, 5.046875, 5.109375, 5.140625, 5.15625, 5.15625, 5.21875, 5.296875, 5.390625, 5.5, 5.53125, 5.703125, 5.796875, 5.796875, 5.890625, 5.984375, 6.0625, 6.140625, 6.203125, 6.234375, 6.328125, 6.34375, 6.359375, 6.390625, 6.4375, 6.515625, 6.609375, 6.703125, 6.84375, 6.859375, 6.921875, 7.046875, 7.125, 7.1875, 7.234375, 7.25, 7.28125, 7.328125, 7.359375, 7.359375, 7.53125, 7.5625, 7.609375, 7.625, 7.6875]

Dedicated MB: [196.08, 195.94, 195.94, 195.94, 195.944, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.932, 195.936, 195.936, 195.936, 195.936, 195.936, 195.936, 195.936, 194.626, 194.626, 194.626, 194.621, 194.621, 194.63, 194.63, 194.621, 194.621, 194.621, 194.621, 194.621, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.626, 194.621, 194.621, 194.621, 194.621, 194.621, 194.621]

### p1e3c1-final-hevc-main10-1440p60

Failure: None

First-frame ms: [40.46, 39.805, 37.233, 32.066, 32.123]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 147.651}, {"target_s": 31.862872, "ms": 133.771}, {"target_s": 22.487508, "ms": 79.961}, {"target_s": 34.804092, "ms": 64.427}, {"target_s": 11.278488, "ms": 138.318}, {"target_s": 48.16493, "ms": 117.634}, {"target_s": 23.487469, "ms": 117.674}, {"target_s": 46.218318, "ms": 22.562}, {"target_s": 53.616685, "ms": 167.363}, {"target_s": 19.22747, "ms": 120.281}, {"target_s": 57.565836, "ms": 155.993}, {"target_s": 13.476976, "ms": 48.744}, {"target_s": 38.751547, "ms": 60.713}, {"target_s": 53.089099, "ms": 144.239}, {"target_s": 8.12015, "ms": 181.086}, {"target_s": 47.944507, "ms": 99.646}, {"target_s": 24.329387, "ms": 163.248}, {"target_s": 5.659215, "ms": 70.815}, {"target_s": 41.155667, "ms": 169.741}, {"target_s": 21.493709, "ms": 33.858}]
```

CPU cumulative seconds: [3.6875, 3.75, 3.8125, 3.8125, 3.875, 3.9375, 4.109375, 4.203125, 4.28125, 4.375, 4.40625, 4.453125, 4.46875, 4.53125, 4.609375, 4.703125, 4.734375, 4.859375, 4.921875, 4.96875, 5.09375, 5.140625, 5.21875, 5.359375, 5.375, 5.453125, 5.53125, 5.640625, 5.734375, 5.828125, 5.875, 5.9375, 6.015625, 6.109375, 6.1875, 6.3125, 6.390625, 6.453125, 6.53125, 6.65625, 6.78125, 6.96875, 7.015625, 7.09375, 7.125, 7.234375, 7.328125, 7.390625, 7.4375, 7.5, 7.546875, 7.609375, 7.65625, 7.703125, 7.75, 7.890625, 8.0625, 8.234375, 8.34375, 8.5]

Dedicated MB: [482.705, 482.517, 482.517, 482.525, 482.509, 482.509, 482.521, 482.513, 482.521, 482.509, 482.509, 482.509, 482.509, 482.513, 482.513, 482.513, 482.509, 482.513, 482.521, 482.509, 482.513, 482.509, 482.513, 482.521, 482.509, 482.443, 482.443, 482.447, 482.456, 482.443, 482.443, 482.447, 482.443, 482.443, 482.443, 482.443, 482.443, 482.456, 482.443, 482.443, 482.447, 482.443, 482.447, 482.456, 482.443, 482.447, 482.443, 482.443, 482.443, 482.447, 482.447, 481.071, 481.071, 481.079, 481.067, 481.071, 481.071, 481.071, 481.071, 481.071]

### p1e3c1-final-hevc-rotation-display

Failure: None

First-frame ms: [35.708, 40.4, 38.819, 44.664, 36.645]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 46.314}, {"target_s": 31.862872, "ms": 111.674}, {"target_s": 22.487508, "ms": 87.376}, {"target_s": 34.804092, "ms": 31.509}, {"target_s": 11.278488, "ms": 44.415}, {"target_s": 48.16493, "ms": 98.38}, {"target_s": 23.487469, "ms": 109.536}, {"target_s": 46.218318, "ms": 66.534}, {"target_s": 53.616685, "ms": 55.289}, {"target_s": 19.22747, "ms": 41.227}, {"target_s": 57.565836, "ms": 112.471}, {"target_s": 13.476976, "ms": 78.273}, {"target_s": 38.751547, "ms": 80.347}, {"target_s": 53.089099, "ms": 46.051}, {"target_s": 8.12015, "ms": 122.955}, {"target_s": 47.944507, "ms": 94.404}, {"target_s": 24.329387, "ms": 115.15}, {"target_s": 5.659215, "ms": 85.603}, {"target_s": 41.155667, "ms": 113.853}, {"target_s": 21.493709, "ms": 72.889}]
```

CPU cumulative seconds: [3.796875, 3.859375, 3.984375, 4.015625, 4.046875, 4.15625, 4.171875, 4.234375, 4.28125, 4.28125, 4.359375, 4.484375, 4.515625, 4.515625, 4.546875, 4.671875, 4.734375, 4.75, 4.765625, 4.828125, 4.84375, 4.859375, 4.96875, 5.078125, 5.109375, 5.1875, 5.21875, 5.265625, 5.3125, 5.328125, 5.359375, 5.359375, 5.453125, 5.484375, 5.484375, 5.5, 5.546875, 5.71875, 5.765625, 5.765625, 5.859375, 5.90625, 5.90625, 5.90625, 5.984375, 6.0, 6.0, 6.046875, 6.046875, 6.09375, 6.109375, 6.15625, 6.15625, 6.1875, 6.296875, 6.40625, 6.5, 6.625, 6.640625, 6.734375]

Dedicated MB: [206.483, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.356, 206.225, 206.225, 206.225, 206.225, 206.225, 206.225, 206.225, 206.225, 206.213, 206.213, 206.213, 206.213, 206.213, 206.213, 206.213, 206.213, 206.213, 206.213, 206.221, 206.217, 206.217, 206.217, 206.217, 206.217, 206.217, 206.217, 206.217, 206.217, 206.217, 204.906, 204.906, 204.906, 204.898]

### p1e3c1-final-vp9-1080p60

Failure: None

First-frame ms: [25.163, 24.988, 25.009, 32.652, 24.957]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 16.293}, {"target_s": 31.862872, "ms": 72.411}, {"target_s": 22.487508, "ms": 46.576}, {"target_s": 34.804092, "ms": 27.872}, {"target_s": 11.278488, "ms": 28.039}, {"target_s": 48.16493, "ms": 49.188}, {"target_s": 23.487469, "ms": 16.271}, {"target_s": 46.218318, "ms": 52.533}, {"target_s": 53.616685, "ms": 16.164}, {"target_s": 19.22747, "ms": 16.277}, {"target_s": 57.565836, "ms": 70.526}, {"target_s": 13.476976, "ms": 28.238}, {"target_s": 38.751547, "ms": 16.13}, {"target_s": 53.089099, "ms": 72.242}, {"target_s": 8.12015, "ms": 62.498}, {"target_s": 47.944507, "ms": 39.275}, {"target_s": 24.329387, "ms": 33.032}, {"target_s": 5.659215, "ms": 52.575}, {"target_s": 41.155667, "ms": 26.663}, {"target_s": 21.493709, "ms": 16.168}]
```

CPU cumulative seconds: [3.078125, 3.234375, 3.3125, 3.40625, 3.46875, 3.53125, 3.65625, 3.8125, 3.9375, 4.015625, 4.078125, 4.1875, 4.28125, 4.4375, 4.53125, 4.65625, 4.71875, 4.796875, 4.921875, 5.03125, 5.109375, 5.234375, 5.3125, 5.40625, 5.59375, 5.78125, 5.890625, 6.015625, 6.265625, 6.3125, 6.453125, 6.53125, 6.578125, 6.625, 6.703125, 6.734375, 6.828125, 6.890625, 7.015625, 7.140625, 7.234375, 7.34375, 7.390625, 7.578125, 7.671875, 7.734375, 7.8125, 7.875, 7.984375, 8.09375, 8.234375, 8.28125, 8.34375, 8.53125, 8.640625, 8.78125, 8.875, 8.984375, 9.140625, 9.3125]

Dedicated MB: [171.721, 171.626, 171.626, 171.618, 171.618, 171.618, 171.618, 171.618, 171.614, 171.618, 171.618, 171.618, 171.614, 171.614, 171.618, 171.618, 169.841, 169.841, 169.837, 169.841, 169.841, 169.841, 169.837, 169.837, 169.837, 169.771, 169.767, 169.767, 169.771, 169.771, 169.767, 169.771, 169.771, 169.771, 169.771, 169.771, 169.771, 169.771, 169.767, 169.767, 169.771, 169.771, 169.767, 169.771, 169.767, 169.767, 169.767, 169.771, 169.767, 169.771, 169.771, 168.395, 168.399, 168.395, 168.391, 168.391, 168.391, 168.391, 168.391, 168.391]

### p1e3c1-no-poll-h264

Failure: None

First-frame ms: [425.067, 245.487, 241.266, 247.455, 239.927]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 84.511}, {"target_s": 31.862872, "ms": 211.682}, {"target_s": 22.487508, "ms": 172.379}, {"target_s": 34.804092, "ms": 46.627}, {"target_s": 11.278488, "ms": 89.105}, {"target_s": 48.16493, "ms": 190.011}, {"target_s": 23.487469, "ms": 198.443}, {"target_s": 46.218318, "ms": 137.701}, {"target_s": 53.616685, "ms": 111.351}, {"target_s": 19.22747, "ms": 77.108}, {"target_s": 57.565836, "ms": 219.241}, {"target_s": 13.476976, "ms": 154.152}, {"target_s": 38.751547, "ms": 161.886}, {"target_s": 53.089099, "ms": 92.793}, {"target_s": 8.12015, "ms": 239.736}, {"target_s": 47.944507, "ms": 183.714}, {"target_s": 24.329387, "ms": 225.84}, {"target_s": 5.659215, "ms": 164.336}, {"target_s": 41.155667, "ms": 227.729}, {"target_s": 21.493709, "ms": 144.468}]
```

CPU cumulative seconds: [4.03125, 4.125, 4.25, 4.296875, 4.453125]

Dedicated MB: [196.088, 195.953, 195.944, 195.932, 195.94]

### p1e3c1-poll-fix-h264

Failure: None

First-frame ms: [36.632, 41.679, 43.265, 25.718, 35.146]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 88.654}, {"target_s": 31.862872, "ms": 203.594}, {"target_s": 22.487508, "ms": 174.392}, {"target_s": 34.804092, "ms": 46.177}, {"target_s": 11.278488, "ms": 89.068}, {"target_s": 48.16493, "ms": 194.206}, {"target_s": 23.487469, "ms": 203.547}, {"target_s": 46.218318, "ms": 135.773}, {"target_s": 53.616685, "ms": 111.383}, {"target_s": 19.22747, "ms": 78.717}, {"target_s": 57.565836, "ms": 224.978}, {"target_s": 13.476976, "ms": 154.424}, {"target_s": 38.751547, "ms": 161.135}, {"target_s": 53.089099, "ms": 95.316}, {"target_s": 8.12015, "ms": 237.768}, {"target_s": 47.944507, "ms": 186.779}, {"target_s": 24.329387, "ms": 227.096}, {"target_s": 5.659215, "ms": 169.634}, {"target_s": 41.155667, "ms": 232.922}, {"target_s": 21.493709, "ms": 145.31}]
```

CPU cumulative seconds: [3.53125, 3.5625, 3.703125, 3.75, 3.75]

Dedicated MB: [196.084, 195.944, 195.944, 195.944, 195.94]

### p1e3c1-profile-baseline

Failure: None

First-frame ms: [633.609, 441.854, 442.947, 441.443, 442.311]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 412.245}, {"target_s": 31.862872, "ms": 509.072}, {"target_s": 22.487508, "ms": 583.136}, {"target_s": 34.804092, "ms": 282.306}, {"target_s": 11.278488, "ms": 382.997}, {"target_s": 48.16493, "ms": 280.778}, {"target_s": 23.487469, "ms": 601.545}, {"target_s": 46.218318, "ms": 474.658}, {"target_s": 53.616685, "ms": 294.168}, {"target_s": 19.22747, "ms": 291.581}, {"target_s": 57.565836, "ms": 562.16}, {"target_s": 13.476976, "ms": 182.238}, {"target_s": 38.751547, "ms": 510.055}, {"target_s": 53.089099, "ms": 207.978}, {"target_s": 8.12015, "ms": 651.718}, {"target_s": 47.944507, "ms": 406.14}, {"target_s": 24.329387, "ms": 274.477}, {"target_s": 5.659215, "ms": 542.425}, {"target_s": 41.155667, "ms": 534.33}, {"target_s": 21.493709, "ms": 426.407}]
```

CPU cumulative seconds: [11.125, 11.671875, 12.234375, 12.828125, 13.65625]

Dedicated MB: [205.902, 205.902, 205.902, 205.894, 205.894]

### p1e3c1-profile-final

Failure: None

First-frame ms: [39.977, 41.539, 36.786, 43.878, 37.955]

Seek {target_s, ms}:
```json
[{"target_s": 36.59416, "ms": 88.361}, {"target_s": 31.862872, "ms": 202.326}, {"target_s": 22.487508, "ms": 169.519}, {"target_s": 34.804092, "ms": 47.349}, {"target_s": 11.278488, "ms": 89.724}, {"target_s": 48.16493, "ms": 187.346}, {"target_s": 23.487469, "ms": 197.14}, {"target_s": 46.218318, "ms": 134.903}, {"target_s": 53.616685, "ms": 110.654}, {"target_s": 19.22747, "ms": 75.091}, {"target_s": 57.565836, "ms": 209.141}, {"target_s": 13.476976, "ms": 149.323}, {"target_s": 38.751547, "ms": 157.886}, {"target_s": 53.089099, "ms": 90.926}, {"target_s": 8.12015, "ms": 233.047}, {"target_s": 47.944507, "ms": 178.842}, {"target_s": 24.329387, "ms": 218.854}, {"target_s": 5.659215, "ms": 161.624}, {"target_s": 41.155667, "ms": 221.522}, {"target_s": 21.493709, "ms": 139.292}]
```

CPU cumulative seconds: [4.171875, 4.203125, 4.25, 4.28125, 4.34375]

Dedicated MB: [196.096, 195.936, 195.936, 195.936, 195.936]

### preview-p1e3c1-decode-ready

Failure: AttributeError("'bool' object has no attribute 'get'")

New-position ms: []

Cached ms: []

Returned times: []

### preview-p1e3c1-final

Failure: None

New-position ms: [147.125, 110.139, 130.415, 117.699, 137.276, 113.854, 114.873, 115.451, 116.247, 112.741]

Cached ms: [5.13, 9.12, 9.925, 10.069, 12.715, 4.853, 9.204, 9.762, 5.818, 9.607]

Returned times: ["0.000000", "0.000000", "8.333333", "16.666667", "33.333333", "50.000000", "0.000000", "25.000000", "8.333333", "50.000000"]

### preview-p1e3c1-hover

Failure: None

New-position ms: [177.737, 165.023, 176.288, 164.715, 166.703, 157.122, 156.08, 157.438, 160.82, 182.551]

Cached ms: [4.322, 4.531, 4.983, 4.694, 5.309, 4.512, 4.123, 4.82, 7.219, 4.423]

Returned times: ["0.000000", "0.000000", "8.333333", "16.666667", "33.333333", "50.000000", "0.000000", "25.000000", "8.333333", "50.000000"]

### preview-p1e3c1-race-safe

Failure: None

New-position ms: [137.392, 116.541, 124.636, 140.09, 123.341, 113.343, 113.982, 113.734, 115.278, 119.453]

Cached ms: [4.957, 9.252, 9.585, 13.472, 10.063, 5.579, 9.242, 10.282, 5.217, 13.167]

Returned times: ["0.000000", "0.000000", "8.333333", "16.666667", "33.333333", "50.000000", "0.000000", "25.000000", "8.333333", "50.000000"]

## Disk and retained artifacts

Decimal GB, logical file lengths. Subset rows overlap and must not be summed.
The snapshot was taken after tests; this report text and small inventory JSON
were finalized afterward. No allocated-size or drive-wide attribution is inferred.

| Required item / role | Logical GB | Bytes |
| --- | ---: | ---: |
| Dependency restore | 0.000000000 | 0 |
| repo | 3.527029968 | 3527029968 |
| package | 0.005764162 | 5764162 |
| evidence | 0.145393259 | 145393259 |
| evidence\VE-P1e-3c1 | 0.042561520 | 42561520 |
| scratch | 0.500635197 | 500635197 |
| cache | 8.524264275 | 8524264275 |
| cache\msys2 | 0.620660838 | 620660838 |
| cache\mpv-lgpl\source-build | 0.036575903 | 36575903 |
| cache\mpv-lgpl\source-build\out | 0.000000000 | 0 |
| Newly fetched alternative builder source/archive (source/build subset) | 0.000450656 | 450656 |
| Successfully source-built output | 0.000000000 | 0 |

MSYS2 toolchain retained: cache/msys2, 0.620660838 GB (two verified portable
bases, including archives and failed keyring state). Source/build trees retained:
cache/mpv-lgpl/source-build, 0.036575903 GB, including prior source/diagnostic
trees and the new pinned alternative builder. Built output: 0 GB; none exists.
No intermediate tree exceeded 5 GB, and no library compilation succeeded.

| Drive free | Start GB | End snapshot GB |
| --- | ---: | ---: |
| C | 299.211825152 | 299.193626624 |
| D | 1003.874603008 | 1002.647515136 |

The D: 200 GB floor and 40 GB cache cap are satisfied. This cycle evidence is
about 0.043 GB, below 0.300 GB. Four evidence cycles remain because removing
the oldest fourth cycle was explicitly rejected. Scratch remains 0.500635197 GB;
its empty-at-end gate is NOT_MET, with the exact owner deletion list above.

Known non-toolchain retained new artifacts include this cycle evidence, scratch,
and the new alternative-builder sources/archive. Full cycle-wide persistent
growth is NOT_FULLY_ATTRIBUTED: an independent recursive start inventory was
not captured, and overwritten Cargo outputs lack a byte-delta baseline. The
0.620660838 GB portable-toolchain bootstrap is separately disclosed under the
task exception. No dependency restore occurred. Do not turn the prior cycle's
historical end size into a fresh start measurement or claim an exact growth PASS.

Measured bytes removed: 1536 for the incomplete newly generated portable
keyring in the earlier authorized recovery. Final cleanup batch: 0 bytes removed;
rejected before launch. No blocked path was retried or deleted indirectly.

The current package is retained at 0.005764162 GB and received no new payload.
No owner media, queues, VE-check, owner AppData or Recycle Bin was read or cleaned.

## Operator handoff / unresolved work

- Review this allowed-scope diff; commit and push only the designer's branch.
- Verify Windows and Ubuntu CI on that final commit; neither is claimed green here.
- Restore normal official MSYS2 key initialization before resuming Part A. Then
  implement/audit the actual minimal dependencies, build twice cleanly, collect
  both output hashes and embedded-FFmpeg/codec proofs. The diagnostic scripts
  delivered here do not satisfy those outstanding source-build requirements.
- Handle the exact rejected cleanup inventory with explicit authorization;
  scratch and the fourth historical evidence cycle remain untouched.
- P1e-3c2 architecture and compare decisions remain for the designer/owner.

One implementation/verification/report cycle ends here. No next cycle started.
