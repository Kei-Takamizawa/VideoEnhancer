Task ID: VE-P1e-3c2 / Run 3 / sections 11.1-11.3
Status: COMPLETED

## Scope

Run 1's accepted work remains by reference to **2d996bc**. Run 2's accepted startup,
two-decoder implementation, drift/36 steps/no pause, visual proof, HTTP regression
and CI fixes remain by reference to **0fd7293**. They were not re-measured.
Initial branch: `claude/project-thread-6lra47`; clean HEAD `5100254`.
CURRENT_TASK.md and the approved mockup are unchanged. No Git mutations or supervisor
changes. The operator commits/pushes and checks final hosted CI.

This run completes the requested capture-free compositor timing proxy, mockup
layout proof, final lint/unit/e2e suites and fresh package build. The timing endpoint
is a validated OS compositor **presentation estimate**, not a hardware-observed
display time or a pixel observation. That limitation is explicit below.

## 11.1 Targets and capture-free divider timing

Measured PC logical cores: **16** (`os.cpu_count()`). Accepted 20.735% of one core
is approximately 1.296% of aggregate CPU capacity and passes the revised <=25% gate.
Accepted cold-poster median70.1ms passes the revised <=100ms median gate; the
first-ever165.8ms open remains recorded and accepted. Neither benchmark was repeated.

Twenty own-page slider input events alternate25%/75% during1440p60 Before/After.
The real React slider handler and private WebView2 IPC are used; no global input,
Computer Use or WGC session starts in this timing run. Page performance.now() is
mapped to native QPC using20 round-trip clock samples. Minimum RTT/2 plus0.2ms
clock-quantization allowance is0.250ms.

Each event records input, WebMessage receipt, clip Commit begin/end, Commit completion,
and GetFrameStatistics. The first next-frame estimate is sampled immediately after
Commit; WaitForCommitCompletion then associates the submitted clip batch. A later
assigned batch frame is retained, and a prediction missed by completion is never
used. All20 final predictions were after confirmed completion; no later-frame
fallback was needed. The thresholds stay34ms median/50ms worst, including allowance.

| Hop / endpoint | Median ms | Worst ms | Result |
| --- | ---: | ---: | --- |
| Page input -> native IPC receipt | 0.197 | 1.451 | No slow input queue found |
| IPC receipt -> clip Commit begin | 0.025 | 0.038 | No10Hz state-update blockage found |
| Commit call | 0.042 | 0.062 | PASS |
| Commit end -> confirmed batch completion | 10.954 | 16.148 | Recorded separately |
| Input -> validated first presentation estimate | **26.697** | **32.647** | **PASS** |
| Same, plus clock allowance | **26.947** | **32.897** | **PASS <=34 /<=50** |

Raw20 values(ms):32.647,22.014,29.580,19.747,26.714,27.980,22.847,29.814,
21.080,27.947,31.514,26.680,21.247,24.814,31.680,21.947,29.514,21.980,
29.147,21.614. None discarded. Raw QPC/calibration/phase data:
`work/evidence/VE-P1e-3c2/run3/divider-timing.json`, `timing-summary.json`,
`divider-timing.ndjson`, `timing-first-frame-final.log`.

GetFrameStatistics provides batch timing and a next-display estimate; it does not
prove actual scanout. Swap-chain SyncQPCTime was unavailable/zero and was not
fabricated. See Microsoft's
[frame statistics definition](https://learn.microsoft.com/en-us/windows/win32/api/dcomptypes/ns-dcomptypes-dcomposition_frame_statistics)
and [GetFrameStatistics](https://learn.microsoft.com/en-us/windows/win32/api/dcomp/nf-dcomp-idcompositiondevice-getframestatistics).
Actual hardware display latency is NOT_MEASURED. The Run2 WGC observation remains
an upper bound: median97.804/worst114.143ms, referenced to0fd7293; it is not the gate.

### Timing investigation and earlier attempts

The first two fixture attempts ran before the page had enabled its slider and
failed with Illegal invocation, zero measured moves. Waiting for configured fixes
the fixture. Provisional next-frame estimates before explicit batch association
were27.557/32.990,27.814/36.081,26.161/49.911,29.882/33.215 and29.005/33.271ms
(median/worst); raw trial JSON/logs remain.

An explicit completion wait exposed a measurement overcount: reading only the
NEXT frame estimate after waiting selected the following refresh, producing
45.857/48.473ms and a failing median assertion. The final probe snapshots the
first next-frame estimate before waiting, then validates its batch completion
and retains any later assigned frame. This removes an extra-refresh counting
error; it does not subtract IPC time, relax thresholds or drop samples.
The observed slow hop was composition scheduling/this telemetry wait, not the
product's input queue. No speculative production queue/scheduling change was made.
`divider-timing-following-frame-failed.json` and its failed log are retained.

## 11.2 Approved mockup layout

Copied the mockup's static SVG paths, CSS values and controller structure:

- Seek bar on its own row; icon groups below, including separate10-second skips.
- Accent circular48px play/pause button (44px at the mockup's narrow breakpoint).
- Matching responsive icon rows, slider gaps,84px volume slider and title/round close.
- Original/split/Enhanced xrow, zoom chip and Reset control.
- Before/After's76 CSS-pixel title/label band and corresponding native picture fit,
  scaled for the own window's DPI.
- Hover picture160x90 CSS px landscape /90x160 portrait, with320x180 /180x320
  backing pixels, time underneath and edge clamping. Portrait preview rendering
  now uses the correct portrait buffer, rather than a landscape letterbox.
- Existing names, keyboard handling, focus, autohide and playback behavior retained.
  No demo toolbar or remote content is added to the product.

### Own-window evidence

`work/evidence/VE-P1e-3c2/run3/comparison.html` shows product left/mockup right.
Twenty WGC captures cover both16:9 and9:16, each in paused, hover, Before/After,
zoom and playing states. All four own helpers exited0 with no remaining descendants.
The mockup uses its existing fakefs CSS framing to give both pages the same client
viewport; the demo toolbar stays outside that framing. Original mockup source is
unchanged. No other window was captured or driven.

| Shape | Paused | Playing | Hover | Before/After | Zoom/xrow |
| --- | --- | --- | --- | --- | --- |
| 16:9 | PASS | PASS | PASS | PASS | PASS |
| 9:16 | PASS | PASS | PASS | PASS | PASS |

Files: `product-{landscape,portrait}-{paused,playing,hover,before,zoom}.png`,
corresponding `mockup-*.png`, per-capture geometry JSON, `layout-proof.json`,
`geometry-comparison.json`. Matched controller/title/row bounding boxes differ
by at most **0.013 CSS px**; preview sizes also match. Captured Original/Enhanced
label-band RGB and round-close RGB match the reference at the compared locations.
The geometry supplements visual inspection; it is not a claim that different video
content produces identical whole-window pixels.

Raw RGBA WGC originals are retained. Their alpha channel displays poorly in some
image viewers; the gallery uses separately named `*-rgb.png` review copies.
Every RGB byte is unchanged, verified against the raw capture. No generated or
retouched picture substitutes for native capture.

Remaining differences: actual filename, duration, scene and current values replace
the demo data; the demo's sample-scene caption, transient OSD animation and toolbar
are not product UI. The existing time counter remains read-only rather than adding
the demo's elapsed/remaining toggle. Zoom percentages/pan framing follow the accepted native zoom math rather than the demo's discrete canvas zoom behavior; the zoom-chip geometry matches. Existing Details actions/metadata behavior is
retained; this round changes the requested controller layout. The normal native
window frame remains, as section11.2 permits. No requested layout item is deferred.

## Final validation and package

| Check | Result | Evidence under run3 |
| --- | --- | --- |
| Ruff lint / format | PASS;186 files formatted | ruff-final.log, format-final.log |
| Pyright configured src scope | PASS;0 errors/warnings | pyright-final.log |
| ESLint / tsc | PASS | eslint-final.log, tsc-final.log |
| Vite assets | PASS | ui-ba-final-build.log; package-final.log |
| Vitest | PASS17 files /80 tests | vitest-final.log |
| Payload policy | PASS1 | payload-final.log |
| Helper fmt / default tests / default clippy -D warnings | PASS7 tests | helper-tests.log, helper-default-clippy.log |
| Helper all-feature tests / clippy -D warnings | PASS6 tests, final telemetry checked | helper-all-tests-final.log, helper-clippy-final.log |
| Main fmt / tests / clippy -D warnings | PASS28 tests | main-tests.log, main-clippy.log |
| Full CPU suite | PASS676 /SKIP24 /deselected101;480.03s | pytest-final.log |
| Full Playwright | PASS25 /SKIP15 opt-in GPU/media/visual/native/package/startup cases | e2e-final.log |
| Fresh pinned-DLL portable package | PASS | package-final.log |
| Final default-feature helper rebuild / candidate smoke | PASS; play/pause/pair, test-hook rejection, exit0/no children | helper-production-final.log, package-final-smoke.json |
| Hosted final Windows/Ubuntu CI | NOT_RUN; operator pushes/checks | No new CI claim |
| Human owner checks / physical display timing | NOT_RUN /NOT_MEASURED | Checklist below |

Two tests cover10-second seek clamping/icon names/portrait preview and zoom reset.
A default Rust test rejects clock/report/divider telemetry commands. Existing tests
were not loosened. Final production UI suites preceded the last test-only telemetry
correction; the affected helper feature tests/clippy were rerun afterward.

A fresh package was built using the pinned official LGPL payload, checksums and
existing source offer. The previous candidate (48,290,185 logical bytes) was moved
to an inventoried scratch backup before packaging, then retained until the new
helper smoke passed. The final default helper was refreshed after the test-only
timing work and smoked again. Current running owner package was never replaced
or stopped. DLL-free packaging, accepted soaks/A5/Compare/startup/HTTP repetitions
were intentionally not repeated. No downloads beyond offline dependency restore,
system installs/settings changes, owner-data access or Git mutations.

Warnings: Node NO_COLOR/FORCE_COLOR and existing packager DEP0190 shell warning;
no build/test failure is hidden by those stderr wrappers. Initial probe compilation errors (an asset rebuild race, module declaration and DXGI binding signature) were corrected before measurements. Initial new-harness
format/global-declaration lint errors were corrected and final checks passed.

## Changed files

14 files relative to5100254, including all new source/harness files. No media, binaries, captures or cache files.

- `.ai/LAST_REPORT.md`
- `gui/scripts/player-acceptance.py`
- `gui/src-tauri/player/src/composition.rs`
- `gui/src-tauri/player/src/host.rs`
- `gui/src-tauri/player/src/lib.rs`
- `gui/src-tauri/player/src/main.rs`
- `gui/src/player/Controls.tsx`
- `gui/src/player/player.css`
- `gui/tests/player-controls.test.tsx`
- `gui/scripts/player-layout-review.py`
- `gui/src-tauri/player/src/benchmark.js`
- `gui/src-tauri/player/src/layout-inspect.js`
- `gui/src-tauri/player/src/telemetry.rs`
- `gui/src/player/Icons.tsx`

## Disk and cleanup

Decimal GB, logical file lengths rather than allocated sizes. Start inventory was taken before restore/builds. Overlapping package/evidence subsets are not summed.

| Item | Start GB | Final GB |
| --- | ---: | ---: |
| C free | 351.319257 | 351.299564 |
| D free | 978.771440 | 978.752291 |
| `cache` | 9.505053 | 9.505453 |
| `scratch` | 0.008649 | 0.008649 |
| `package` | 0.125265 | 0.125281 |
| `evidence/VE-P1e-3c2` | 0.179071 | 0.197351 |
| Candidate only (package subset) | 0.048290 | 0.048306 |
| Current running package (subset) | 0.005764 | 0.005764 |
| Run3 evidence (cycle subset) | 0 | 0.018000 |

Offline node dependency restore: 191,885,717 bytes measured before cleanup (includes small runtime cache overhead). No new tool/model/binary downloads. All269 listed cleanup candidates were removed: **2,488,474,737 independently measured logical bytes**; cleanup-results.json has each outcome. Node_modules, dist, repository Python caches, isolated media/test homes and previous candidate backup are gone. Only the inherited refused profiles are nonempty under scratch; local-env may recreate empty scratch/tmp.

Measured net change across cache/scratch/package/cycle-evidence: **0.018696 GB**. Adding all current checkout files modified since start as a conservative bound (161,729 bytes, including .venv runtime caches) gives **0.018858 GB** retained logical growth. This is not a drive-wide allocation delta. Growth <=1GB, cache <40GB, whole-cycle evidence <300MB and D free >200GB: PASS. Start/end and hashes: disk-start.json /disk-final.json.

| Candidate binary | Bytes | SHA-256 |
| --- | ---: | --- |
| VideoEnhancer-Player.exe | 1602048 | `df30aeac27f644be7f427ffab626e38e8ef7443b904408324f1fd146234cde29` |
| VideoEnhancer.exe | 5870592 | `44eb0b8896c427a6fa688545d0211b0593dbe6472101397e65b4873acbb45241` |


Inherited owner cleanup items, never retried or included in parent recursive
deletion: `scratch/p1e3c2-native/h264-bench-two-0` (1,712 bytes) and
`scratch/p1e3c2-native/visual-proof` (8,647,268 bytes). No new deletion refusal
has been concealed. .venv and local-env.ps1 are retained.

## Decisions / limits

- Use the requested capture-free compositor timing proxy with explicit clock and
  presentation-estimate limits. Do not substitute an ACK or claim physical scanout.
- Retain the allowed native frame and accepted playback/Details behavior.
- Keep the running current package intact; deliver the separately built candidate.
  Promotion, Git recording and hosted CI remain operator/owner responsibilities.

## Owner check (human checks not newly performed)

1. Open the fresh candidate with disposable home and synthetic landscape/portrait clips.
2. Click History; verify the accepted poster/playback opening behavior.
3. Inspect the round close/title and accent play/pause button.
4. Check seek on its own row and the responsive icon rows at both shapes.
5. Try10-second back/forward and paused frame steps.
6. Enable Before/After; check upper labels, split slider, black bars and no drawn divider.
7. Move the split while playing; check picture response without opening capture tools.
8. Zoom; verify zoom percentage and Reset, then restore100%.
9. Hover near both timeline edges; check preview size, placement and time underneath.
10. Check shortcuts, sound/speed/Details, autohide/paused reveal, then close and verify
    History focus and helper exit. Keep owner media out of development evidence.

## Cleanup inventory (recorded before deletion)

Logical bytes per candidate; no inherited refused profile or ancestor is included.

| Candidate under work | Logical bytes |
| --- | ---: |
| `scratch/p1e3c2-run3-cpu` | 0 |
| `scratch/p1e3c2-run3-cpu-bin` | 18442304 |
| `scratch/p1e3c2-run3-e2e` | 548457618 |
| `scratch/p1e3c2-run3-fault-bin` | 1729024 |
| `scratch/p1e3c2-run3-native` | 70931825 |
| `scratch/p1e3c2-run3-previous-candidate` | 48290185 |
| `scratch/tmp` | 10601793 |
| `scratch/videoenhancer.jsonl` | 3074 |
| `repo/gui/node_modules` | 191885717 |
| `repo/gui/dist` | 609501 |
| `repo/.ruff_cache` | 11458 |
| `cache/tauri-target/debug/deps/libbase64-ce9221534c8e2940.rlib` | 514904 |
| `cache/tauri-target/debug/deps/libbase64-ce9221534c8e2940.rmeta` | 316633 |
| `cache/tauri-target/debug/deps/libbase64-e4bd84f82c2d00ce.rmeta` | 227964 |
| `cache/tauri-target/debug/deps/libbitflags-c924b9d8f5646d59.rmeta` | 177062 |
| `cache/tauri-target/debug/deps/libdpi-5891117ef91dfd5e.rlib` | 219100 |
| `cache/tauri-target/debug/deps/libdpi-5891117ef91dfd5e.rmeta` | 212136 |
| `cache/tauri-target/debug/deps/libdpi-80b4cb7d03aba5f0.rmeta` | 133183 |
| `cache/tauri-target/debug/deps/libform_urlencoded-f62264ffb245d8e6.rmeta` | 27557 |
| `cache/tauri-target/debug/deps/libicu_collections-57b1ccf9f2539686.rlib` | 1036710 |
| `cache/tauri-target/debug/deps/libicu_collections-57b1ccf9f2539686.rmeta` | 426785 |
| `cache/tauri-target/debug/deps/libicu_collections-c659028211346ca3.rmeta` | 302574 |
| `cache/tauri-target/debug/deps/libicu_locale_core-4a73333febbd5b05.rmeta` | 1381655 |
| `cache/tauri-target/debug/deps/libicu_locale_core-9387890bfbfa04df.rlib` | 3021936 |
| `cache/tauri-target/debug/deps/libicu_locale_core-9387890bfbfa04df.rmeta` | 1595439 |
| `cache/tauri-target/debug/deps/libicu_normalizer-17e49cc0c46d58dc.rmeta` | 441239 |
| `cache/tauri-target/debug/deps/libicu_normalizer-51bf13c2f97eed32.rlib` | 1569318 |
| `cache/tauri-target/debug/deps/libicu_normalizer-51bf13c2f97eed32.rmeta` | 591267 |
| `cache/tauri-target/debug/deps/libicu_properties-38e2d7a6f5930ec6.rmeta` | 2529117 |
| `cache/tauri-target/debug/deps/libicu_properties-9e652eb186237a8a.rlib` | 4570336 |
| `cache/tauri-target/debug/deps/libicu_properties-9e652eb186237a8a.rmeta` | 2735852 |
| `cache/tauri-target/debug/deps/libicu_provider-87073197e85ce684.rmeta` | 358184 |
| `cache/tauri-target/debug/deps/libicu_provider-b0eb8d818759cc1a.rlib` | 616290 |
| `cache/tauri-target/debug/deps/libicu_provider-b0eb8d818759cc1a.rmeta` | 429679 |
| `cache/tauri-target/debug/deps/libidna-1f235341bf6ccafa.rlib` | 1475884 |
| `cache/tauri-target/debug/deps/libidna-1f235341bf6ccafa.rmeta` | 243759 |
| `cache/tauri-target/debug/deps/libidna-a75f4d46d36f3972.rmeta` | 144084 |
| `cache/tauri-target/debug/deps/libidna_adapter-46caf4958679e9e6.rlib` | 77246 |
| `cache/tauri-target/debug/deps/libidna_adapter-46caf4958679e9e6.rmeta` | 32762 |
| `cache/tauri-target/debug/deps/libidna_adapter-b790960b4ab5c135.rmeta` | 27917 |
| `cache/tauri-target/debug/deps/liblibloading-21999e3592b7817a.rlib` | 283154 |
| `cache/tauri-target/debug/deps/liblibloading-21999e3592b7817a.rmeta` | 145144 |
| `cache/tauri-target/debug/deps/liblibloading-3936d0badfbb8987.rmeta` | 115826 |
| `cache/tauri-target/debug/deps/libmemchr-38089049b4a132d8.rmeta` | 992923 |
| `cache/tauri-target/debug/deps/libmemchr-44c5c68c2f6ac0c5.rlib` | 1776330 |
| `cache/tauri-target/debug/deps/libmemchr-44c5c68c2f6ac0c5.rmeta` | 1311848 |
| `cache/tauri-target/debug/deps/libparking_lot-ae4416f7d9de723d.rmeta` | 158387 |
| `cache/tauri-target/debug/deps/libparking_lot_core-f9ed022dcf65a17c.rmeta` | 114802 |
| `cache/tauri-target/debug/deps/libpercent_encoding-08cacb3d06cba4a6.rmeta` | 45711 |
| `cache/tauri-target/debug/deps/libpng-045f1465d88b15fc.rmeta` | 744028 |
| `cache/tauri-target/debug/deps/libpotential_utf-1c20a29bc1163643.rmeta` | 38524 |
| `cache/tauri-target/debug/deps/libpotential_utf-d41965670bbbacf3.rlib` | 91972 |
| `cache/tauri-target/debug/deps/libpotential_utf-d41965670bbbacf3.rmeta` | 45094 |
| `cache/tauri-target/debug/deps/libproc_macro2-5b42f80bac7bc596.rlib` | 1379190 |
| `cache/tauri-target/debug/deps/libproc_macro2-5b42f80bac7bc596.rmeta` | 351847 |
| `cache/tauri-target/debug/deps/libquote-ed63e26db6dec0b6.rlib` | 567456 |
| `cache/tauri-target/debug/deps/libquote-ed63e26db6dec0b6.rmeta` | 275893 |
| `cache/tauri-target/debug/deps/libserde-378d07342e0e486d.rmeta` | 526379 |
| `cache/tauri-target/debug/deps/libserde-d173d3439c6d2dc5.rlib` | 994036 |
| `cache/tauri-target/debug/deps/libserde-d173d3439c6d2dc5.rmeta` | 842612 |
| `cache/tauri-target/debug/deps/libserde_core-e12ff28eead84497.rlib` | 5060452 |
| `cache/tauri-target/debug/deps/libserde_core-e12ff28eead84497.rmeta` | 4849747 |
| `cache/tauri-target/debug/deps/libserde_core-f76f9a2a3e98b891.rmeta` | 2726536 |
| `cache/tauri-target/debug/deps/libserde_json-367ad46f7538a188.rlib` | 2626924 |
| `cache/tauri-target/debug/deps/libserde_json-367ad46f7538a188.rmeta` | 1455007 |
| `cache/tauri-target/debug/deps/libserde_json-fe370f977207fe0d.rmeta` | 966682 |
| `cache/tauri-target/debug/deps/libsmallvec-2ea9b1b53a0d3a97.rmeta` | 114305 |
| `cache/tauri-target/debug/deps/libsyn-8a3c0f1b68c20174.rlib` | 10205954 |
| `cache/tauri-target/debug/deps/libsyn-8a3c0f1b68c20174.rmeta` | 2810158 |
| `cache/tauri-target/debug/deps/libsyn-e12850ffbe1f9970.rlib` | 8867340 |
| `cache/tauri-target/debug/deps/libsyn-e12850ffbe1f9970.rmeta` | 3412031 |
| `cache/tauri-target/debug/deps/libsynstructure-3eb5c573a8db6951.rlib` | 1246894 |
| `cache/tauri-target/debug/deps/libsynstructure-3eb5c573a8db6951.rmeta` | 229720 |
| `cache/tauri-target/debug/deps/libtao-0af3c24af868a158.rlib` | 7598808 |
| `cache/tauri-target/debug/deps/libtao-0af3c24af868a158.rmeta` | 4353400 |
| `cache/tauri-target/debug/deps/libtao-60b32d9fb63b1322.rmeta` | 3678045 |
| `cache/tauri-target/debug/deps/libtao-74325bc92a4352a6.rmeta` | 3670956 |
| `cache/tauri-target/debug/deps/libtao-c72c6bae0e12da59.rlib` | 7588828 |
| `cache/tauri-target/debug/deps/libtao-c72c6bae0e12da59.rmeta` | 4340347 |
| `cache/tauri-target/debug/deps/libtauri-29e5e8fbf1c6b11c.rmeta` | 4646663 |
| `cache/tauri-target/debug/deps/libtauri-fbb3505a67d5f889.rlib` | 15965982 |
| `cache/tauri-target/debug/deps/libtauri-fbb3505a67d5f889.rmeta` | 7193113 |
| `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-71cd02009475c764.rmeta` | 40117 |
| `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-b41b9134553097e6.rlib` | 72728 |
| `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-b41b9134553097e6.rmeta` | 67017 |
| `cache/tauri-target/debug/deps/libtauri_runtime-63b7ada9edf09661.rmeta` | 394214 |
| `cache/tauri-target/debug/deps/libtauri_runtime-9b5c30181555dd10.rlib` | 665948 |
| `cache/tauri-target/debug/deps/libtauri_runtime-9b5c30181555dd10.rmeta` | 540961 |
| `cache/tauri-target/debug/deps/libtauri_runtime_wry-4c0a4559382857c0.rmeta` | 1545452 |
| `cache/tauri-target/debug/deps/libtauri_runtime_wry-b919681a9e417043.rlib` | 2652312 |
| `cache/tauri-target/debug/deps/libtauri_runtime_wry-b919681a9e417043.rmeta` | 1965765 |
| `cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rlib` | 32268 |
| `cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rmeta` | 31224 |
| `cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rlib` | 356970 |
| `cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rmeta` | 314228 |
| `cache/tauri-target/debug/deps/libtinystr-9c819ba187e7ac7d.rmeta` | 258492 |
| `cache/tauri-target/debug/deps/liburl-3d042123386f1d5a.rmeta` | 297701 |
| `cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rlib` | 1332532 |
| `cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rmeta` | 369846 |
| `cache/tauri-target/debug/deps/libVideoEnhancer-0bf69eeec8dd444a.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer-a5446e76e161cb46.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-1304494e86b92893.rlib` | 2029910 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-1304494e86b92893.rmeta` | 385617 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-19cfab87fe5d3014.rmeta` | 132313 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-439d427e7144f55e.rlib` | 2030616 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-439d427e7144f55e.rmeta` | 385569 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-7eddf2ce95085949.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-80726929358a9182.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-97e6c93c723bf456.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-a82fadec2d016f59.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-d09e8693a6af886f.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-dd6d29417458706f.rmeta` | 132313 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-e52895876edb27a2.rlib` | 2532118 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-e52895876edb27a2.rmeta` | 461780 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-f93eb5faca3dcf21.rmeta` | 187936 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-fdd9da71531fcc6a.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libwebview2_com-8b682d394f73e5d6.rmeta` | 1538598 |
| `cache/tauri-target/debug/deps/libwebview2_com-8edea069f3a2800d.rlib` | 10132652 |
| `cache/tauri-target/debug/deps/libwebview2_com-8edea069f3a2800d.rmeta` | 1976501 |
| `cache/tauri-target/debug/deps/libwebview2_com-d614665bff8f16ee.rlib` | 10108162 |
| `cache/tauri-target/debug/deps/libwebview2_com-d614665bff8f16ee.rmeta` | 1976501 |
| `cache/tauri-target/debug/deps/libwebview2_com-e1e850bdf412f2fc.rmeta` | 1538598 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-06b37d7db910eb30.rmeta` | 4924254 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-6daa55be7f2aaf0a.rlib` | 20333950 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-6daa55be7f2aaf0a.rmeta` | 6432800 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-b4e59872734e6b57.rlib` | 20333950 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-b4e59872734e6b57.rmeta` | 6432800 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-c182dd13f977404b.rmeta` | 4924254 |
| `cache/tauri-target/debug/deps/libwindows-647d1e22f18ff6a7.rlib` | 127207218 |
| `cache/tauri-target/debug/deps/libwindows-647d1e22f18ff6a7.rmeta` | 103104693 |
| `cache/tauri-target/debug/deps/libwindows-9c66b4201138050c.rmeta` | 81650820 |
| `cache/tauri-target/debug/deps/libwindows-c510c69a3a15432c.rmeta` | 81650820 |
| `cache/tauri-target/debug/deps/libwindows-d0d23b0371803e71.rlib` | 127206660 |
| `cache/tauri-target/debug/deps/libwindows-d0d23b0371803e71.rmeta` | 103104693 |
| `cache/tauri-target/debug/deps/libwindows_collections-16e61cd397ede7b6.rlib` | 535676 |
| `cache/tauri-target/debug/deps/libwindows_collections-16e61cd397ede7b6.rmeta` | 534573 |
| `cache/tauri-target/debug/deps/libwindows_collections-f6bf775e70b9e531.rmeta` | 328770 |
| `cache/tauri-target/debug/deps/libwindows_core-a6fd93327c3eebf8.rmeta` | 544067 |
| `cache/tauri-target/debug/deps/libwindows_core-d8b0e8288046add1.rlib` | 949900 |
| `cache/tauri-target/debug/deps/libwindows_core-d8b0e8288046add1.rmeta` | 638400 |
| `cache/tauri-target/debug/deps/libwindows_future-51be2519e37fe6bb.rlib` | 1105168 |
| `cache/tauri-target/debug/deps/libwindows_future-51be2519e37fe6bb.rmeta` | 757036 |
| `cache/tauri-target/debug/deps/libwindows_future-d5b3e9f8b4ec6796.rmeta` | 482503 |
| `cache/tauri-target/debug/deps/libwindows_numerics-52d223e6577cd14c.rmeta` | 97591 |
| `cache/tauri-target/debug/deps/libwindows_numerics-dc5a2af46e21e0b7.rlib` | 212080 |
| `cache/tauri-target/debug/deps/libwindows_numerics-dc5a2af46e21e0b7.rmeta` | 112934 |
| `cache/tauri-target/debug/deps/libwry-3c8fb3c23e5ded05.rlib` | 3215452 |
| `cache/tauri-target/debug/deps/libwry-3c8fb3c23e5ded05.rmeta` | 1901960 |
| `cache/tauri-target/debug/deps/libwry-5eed21728cf197ab.rmeta` | 1659448 |
| `cache/tauri-target/debug/deps/libyoke-5598d26e8733f6ea.rlib` | 242478 |
| `cache/tauri-target/debug/deps/libyoke-5598d26e8733f6ea.rmeta` | 240740 |
| `cache/tauri-target/debug/deps/libyoke-9fdfce34d1aff53f.rmeta` | 192042 |
| `cache/tauri-target/debug/deps/libzerofrom-5765f9eb8d92511e.rlib` | 97034 |
| `cache/tauri-target/debug/deps/libzerofrom-5765f9eb8d92511e.rmeta` | 95994 |
| `cache/tauri-target/debug/deps/libzerofrom-f3ecd5c88c7bb243.rmeta` | 53717 |
| `cache/tauri-target/debug/deps/libzerotrie-b76ea17d16878913.rmeta` | 354065 |
| `cache/tauri-target/debug/deps/libzerotrie-e3a3b0d50f0096d7.rlib` | 541260 |
| `cache/tauri-target/debug/deps/libzerotrie-e3a3b0d50f0096d7.rmeta` | 454842 |
| `cache/tauri-target/debug/deps/libzerovec-27d3ee8e39225a94.rlib` | 1174686 |
| `cache/tauri-target/debug/deps/libzerovec-27d3ee8e39225a94.rmeta` | 1114657 |
| `cache/tauri-target/debug/deps/libzerovec-e70d1292a9e90e43.rmeta` | 839587 |
| `cache/tauri-target/release/deps/libbase64-0bf362135fc6e458.rlib` | 395600 |
| `cache/tauri-target/release/deps/libbase64-0bf362135fc6e458.rmeta` | 348057 |
| `cache/tauri-target/release/deps/libbitflags-e18c0616b3b055ee.rlib` | 265260 |
| `cache/tauri-target/release/deps/libbitflags-e18c0616b3b055ee.rmeta` | 246721 |
| `cache/tauri-target/release/deps/libdpi-4973fb67c91c6b74.rlib` | 236136 |
| `cache/tauri-target/release/deps/libdpi-4973fb67c91c6b74.rmeta` | 232952 |
| `cache/tauri-target/release/deps/libform_urlencoded-73a285ab60de02f8.rlib` | 60556 |
| `cache/tauri-target/release/deps/libform_urlencoded-73a285ab60de02f8.rmeta` | 39270 |
| `cache/tauri-target/release/deps/libicu_collections-f27a393ff3917e5e.rlib` | 583108 |
| `cache/tauri-target/release/deps/libicu_collections-f27a393ff3917e5e.rmeta` | 489390 |
| `cache/tauri-target/release/deps/libicu_locale_core-0893ad710e28a0d8.rlib` | 2287418 |
| `cache/tauri-target/release/deps/libicu_locale_core-0893ad710e28a0d8.rmeta` | 1888962 |
| `cache/tauri-target/release/deps/libicu_normalizer-c67a9fb4b42477d9.rlib` | 1026292 |
| `cache/tauri-target/release/deps/libicu_normalizer-c67a9fb4b42477d9.rmeta` | 719265 |
| `cache/tauri-target/release/deps/libicu_properties-7c29f83a20d90ec8.rlib` | 3438358 |
| `cache/tauri-target/release/deps/libicu_properties-7c29f83a20d90ec8.rmeta` | 2849199 |
| `cache/tauri-target/release/deps/libicu_provider-cd188443e6bf8962.rlib` | 572800 |
| `cache/tauri-target/release/deps/libicu_provider-cd188443e6bf8962.rmeta` | 479577 |
| `cache/tauri-target/release/deps/libidna-d961f6ef1c2f2767.rlib` | 697388 |
| `cache/tauri-target/release/deps/libidna-d961f6ef1c2f2767.rmeta` | 296346 |
| `cache/tauri-target/release/deps/libidna_adapter-0f85c41bf90e53dc.rlib` | 149290 |
| `cache/tauri-target/release/deps/libidna_adapter-0f85c41bf90e53dc.rmeta` | 36680 |
| `cache/tauri-target/release/deps/liblibloading-6b10972ad5fb083b.rlib` | 193944 |
| `cache/tauri-target/release/deps/liblibloading-6b10972ad5fb083b.rmeta` | 162133 |
| `cache/tauri-target/release/deps/libmemchr-ad8c43842df2fa8e.rlib` | 1513222 |
| `cache/tauri-target/release/deps/libmemchr-ad8c43842df2fa8e.rmeta` | 1422068 |
| `cache/tauri-target/release/deps/libparking_lot-11048444669ce65e.rlib` | 339834 |
| `cache/tauri-target/release/deps/libparking_lot-11048444669ce65e.rmeta` | 218866 |
| `cache/tauri-target/release/deps/libparking_lot_core-9c6b1f367ef11f67.rlib` | 276096 |
| `cache/tauri-target/release/deps/libparking_lot_core-9c6b1f367ef11f67.rmeta` | 250327 |
| `cache/tauri-target/release/deps/libpercent_encoding-1af1dde375691e11.rlib` | 82766 |
| `cache/tauri-target/release/deps/libpercent_encoding-1af1dde375691e11.rmeta` | 58498 |
| `cache/tauri-target/release/deps/libpng-eba37cb54496001b.rlib` | 1593944 |
| `cache/tauri-target/release/deps/libpng-eba37cb54496001b.rmeta` | 1273587 |
| `cache/tauri-target/release/deps/libpotential_utf-9d502e8c6515444e.rlib` | 71810 |
| `cache/tauri-target/release/deps/libpotential_utf-9d502e8c6515444e.rmeta` | 60883 |
| `cache/tauri-target/release/deps/libproc_macro2-8eaa15c4233423b5.rlib` | 1304268 |
| `cache/tauri-target/release/deps/libproc_macro2-8eaa15c4233423b5.rmeta` | 351835 |
| `cache/tauri-target/release/deps/libquote-2d1762e6b0edf6df.rlib` | 556788 |
| `cache/tauri-target/release/deps/libquote-2d1762e6b0edf6df.rmeta` | 275893 |
| `cache/tauri-target/release/deps/libserde-44734aec864363c6.rlib` | 994132 |
| `cache/tauri-target/release/deps/libserde-44734aec864363c6.rmeta` | 965096 |
| `cache/tauri-target/release/deps/libserde_core-161a56a6f98bc356.rlib` | 5208996 |
| `cache/tauri-target/release/deps/libserde_core-161a56a6f98bc356.rmeta` | 5114468 |
| `cache/tauri-target/release/deps/libserde_json-d70502cae188ca08.rlib` | 2087302 |
| `cache/tauri-target/release/deps/libserde_json-d70502cae188ca08.rmeta` | 1715207 |
| `cache/tauri-target/release/deps/libsmallvec-3b0d2fe5c3f39246.rlib` | 288428 |
| `cache/tauri-target/release/deps/libsmallvec-3b0d2fe5c3f39246.rmeta` | 278706 |
| `cache/tauri-target/release/deps/libsyn-0f6ddc13a6a3b2d4.rlib` | 8702612 |
| `cache/tauri-target/release/deps/libsyn-0f6ddc13a6a3b2d4.rmeta` | 3387887 |
| `cache/tauri-target/release/deps/libsyn-a25fa67b958f4cfe.rlib` | 10024508 |
| `cache/tauri-target/release/deps/libsyn-a25fa67b958f4cfe.rmeta` | 2807569 |
| `cache/tauri-target/release/deps/libsynstructure-6413c2765f158b23.rlib` | 1203264 |
| `cache/tauri-target/release/deps/libsynstructure-6413c2765f158b23.rmeta` | 229523 |
| `cache/tauri-target/release/deps/libtao-7a3e677342d039d6.rlib` | 5620884 |
| `cache/tauri-target/release/deps/libtao-7a3e677342d039d6.rmeta` | 4767238 |
| `cache/tauri-target/release/deps/libtao-c9d715a8ffebf796.rlib` | 5606352 |
| `cache/tauri-target/release/deps/libtao-c9d715a8ffebf796.rmeta` | 4752497 |
| `cache/tauri-target/release/deps/libtauri-c3024d7af6b539f7.rlib` | 12008994 |
| `cache/tauri-target/release/deps/libtauri-c3024d7af6b539f7.rmeta` | 9093397 |
| `cache/tauri-target/release/deps/libtauri_plugin_single_instance-9e41c5def3adf1bb.rlib` | 111670 |
| `cache/tauri-target/release/deps/libtauri_plugin_single_instance-9e41c5def3adf1bb.rmeta` | 103162 |
| `cache/tauri-target/release/deps/libtauri_runtime-f5001d59109c7761.rlib` | 674770 |
| `cache/tauri-target/release/deps/libtauri_runtime-f5001d59109c7761.rmeta` | 628902 |
| `cache/tauri-target/release/deps/libtauri_runtime_wry-283eca5a357b29ae.rlib` | 2562664 |
| `cache/tauri-target/release/deps/libtauri_runtime_wry-283eca5a357b29ae.rmeta` | 2263015 |
| `cache/tauri-target/release/deps/libthiserror-c3d1b6c3d1d4606a.rlib` | 32272 |
| `cache/tauri-target/release/deps/libthiserror-c3d1b6c3d1d4606a.rmeta` | 31228 |
| `cache/tauri-target/release/deps/libtinystr-ae0d10cfb311f63e.rlib` | 361190 |
| `cache/tauri-target/release/deps/libtinystr-ae0d10cfb311f63e.rmeta` | 355315 |
| `cache/tauri-target/release/deps/liburl-84679487a2fc9e0f.rlib` | 758090 |
| `cache/tauri-target/release/deps/liburl-84679487a2fc9e0f.rmeta` | 419744 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-2cfcda8b4f7303c9.rlib` | 1202714 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-2cfcda8b4f7303c9.rmeta` | 480499 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-96fc99c16c4c3c30.rlib` | 1204150 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-96fc99c16c4c3c30.rmeta` | 480499 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-e82f8565ed08af1d.rlib` | 1467146 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-e82f8565ed08af1d.rmeta` | 570567 |
| `cache/tauri-target/release/deps/libwebview2_com-5dcf12f7274b37a4.rlib` | 3831406 |
| `cache/tauri-target/release/deps/libwebview2_com-5dcf12f7274b37a4.rmeta` | 2480049 |
| `cache/tauri-target/release/deps/libwebview2_com-fa6f0ceb89ea0c9a.rlib` | 3831402 |
| `cache/tauri-target/release/deps/libwebview2_com-fa6f0ceb89ea0c9a.rmeta` | 2480049 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-6813a2b3638d79f4.rlib` | 19214230 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-6813a2b3638d79f4.rmeta` | 7865268 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-c98f8415d1830d33.rlib` | 19214280 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-c98f8415d1830d33.rmeta` | 7865268 |
| `cache/tauri-target/release/deps/libwindows-129f7ddb30a5e658.rlib` | 128169858 |
| `cache/tauri-target/release/deps/libwindows-129f7ddb30a5e658.rmeta` | 121034647 |
| `cache/tauri-target/release/deps/libwindows-3c393d379a21c02c.rlib` | 128195586 |
| `cache/tauri-target/release/deps/libwindows-3c393d379a21c02c.rmeta` | 121034647 |
| `cache/tauri-target/release/deps/libwindows_collections-d89acfec9f54c2e5.rlib` | 741454 |
| `cache/tauri-target/release/deps/libwindows_collections-d89acfec9f54c2e5.rmeta` | 738173 |
| `cache/tauri-target/release/deps/libwindows_core-6cc8cf12619250ca.rlib` | 824174 |
| `cache/tauri-target/release/deps/libwindows_core-6cc8cf12619250ca.rmeta` | 731533 |
| `cache/tauri-target/release/deps/libwindows_future-75650e056f1ce416.rlib` | 1039570 |
| `cache/tauri-target/release/deps/libwindows_future-75650e056f1ce416.rmeta` | 960422 |
| `cache/tauri-target/release/deps/libwindows_numerics-cbe17904f21ac65e.rlib` | 224976 |
| `cache/tauri-target/release/deps/libwindows_numerics-cbe17904f21ac65e.rmeta` | 193034 |
| `cache/tauri-target/release/deps/libwry-d888bc27a4a2a647.rlib` | 2352468 |
| `cache/tauri-target/release/deps/libwry-d888bc27a4a2a647.rmeta` | 2050101 |
| `cache/tauri-target/release/deps/libyoke-64fae51615e04096.rlib` | 264710 |
| `cache/tauri-target/release/deps/libyoke-64fae51615e04096.rmeta` | 260980 |
| `cache/tauri-target/release/deps/libzerofrom-b9a189f78ade812d.rlib` | 85176 |
| `cache/tauri-target/release/deps/libzerofrom-b9a189f78ade812d.rmeta` | 81964 |
| `cache/tauri-target/release/deps/libzerotrie-502a9c1ffd14593b.rlib` | 518156 |
| `cache/tauri-target/release/deps/libzerotrie-502a9c1ffd14593b.rmeta` | 491798 |
| `cache/tauri-target/release/deps/libzerovec-935b60deb1cd5ab4.rlib` | 1359420 |
| `cache/tauri-target/release/deps/libzerovec-935b60deb1cd5ab4.rmeta` | 1351244 |
