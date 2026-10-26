Task ID: VE-P1e-3c2 / Run 2 / sections 10.1-10.4 and 10.7
Status: PARTIAL

## Scope

Run 1's accepted architecture, IPC/security, fallbacks, memory return, seek/reload/
preview measurements, packaging/licences, Compare hashes/proposals and retry fix
remain accepted by reference to **2d996bc**; they were not repeated as new proof.
The supervisor was not changed. No Git mutation, commit, push or merge was run.

Run 2 began on branch `claude/project-thread-6lra47`, clean at `a04bcf0`.
The operator's task-only commit `9e1b716` was present at resumption; all uncommitted
implementation changes were preserved. CURRENT_TASK.md was not edited by Codex.
Execution: Windows GPU PC, synthetic isolated homes under work/scratch.
No owner media, queue, AppData, VE-check or Recycle Bin was accessed. The running
owner app and its current package were preserved; only the separate candidate is updated.

First-frame medians and burned-frame drift pass. CPU, first cold poster and observed
divider latency miss targets. Common exact-seek targets pass; this is not proof
of identical decoded PTS for 30 fps source versus 60 fps output.

## 10.1 Startup

DLL/mpv initialization overlaps native-device creation. Initial file open/render
overlaps WebView2/controller/page setup. A WIC/GDI poster paints before committing
the video composition tree; the first video commit follows a decoded/restarted
frame. Controls attach without reopening the file. History thumbnail pointer entry
starts a hidden file-free helper. Unused prewarm expires after 30 seconds;
activated helper exits on close.

Five runs each, milliseconds. Phases overlap: do not sum these columns. Page is
asynchronous navigation completion; it may finish after the first picture.
Before uses instrumented Run 1 native source with the same current controls assets,
a controlled phase baseline rather than an exact old-package reproduction.
DLL+init includes load, configuration and mpv_initialize.

| Build/run | Spawn | Window | D3D+DComp | WV env | WV controller | Page | DLL+init | File/frame | Harness total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before 1 | 69.07 | 26.59 | 192.16 | 2.38 | 228.77 | 415.77 | 5.04 | 158.58 | 1136.85 |
| Before 2 | 2.64 | 25.17 | 194.27 | 2.67 | 230.94 | 75.89 | 5.57 | 169.19 | 741.89 |
| Before 3 | 2.67 | 25.26 | 184.89 | 2.76 | 215.73 | 78.45 | 5.37 | 169.92 | 721.63 |
| Before 4 | 2.52 | 24.27 | 184.76 | 2.68 | 227.31 | 75.08 | 4.55 | 167.97 | 726.32 |
| Before 5 | 2.64 | 24.72 | 183.92 | 2.79 | 216.77 | 84.06 | 4.71 | 166.51 | 724.41 |
| After 1 | 70.94 | 35.02 | 185.76 | 2.42 | 242.84 | 72.46 | 4.44 | 223.20 | 546.27 |
| After 2 | 2.60 | 33.62 | 189.25 | 2.36 | 224.49 | 74.36 | 4.35 | 192.10 | 443.03 |
| After 3 | 2.57 | 33.87 | 184.99 | 2.43 | 227.75 | 72.10 | 4.29 | 202.64 | 449.76 |
| After 4 | 2.66 | 34.05 | 185.33 | 2.59 | 222.63 | 73.75 | 4.20 | 195.64 | 443.04 |
| After 5 | 2.50 | 33.52 | 184.27 | 2.35 | 228.29 | 74.97 | 4.31 | 192.13 | 443.94 |

Harness median: **726.32 ->443.94 ms**. Raw records:
`work/evidence/VE-P1e-3c2/run2/cold-{before,after}-complete.json`.

Real History DOM clicks, production release helper, e2e main shell, capture off:

| Metric | Five measured values (ms) | Result |
| --- | --- | --- |
| Cold first frame | 581.1, 453.7, 463.2, 454.9, 471.5 | PASS median 463.2 <=500 |
| Prewarmed first frame | 188.3, 191.5, 189.6, 192.9, 185.9 | PASS median 189.6 <=300 |
| Cold poster | 165.8, 68.8, 70.1, 68.9, 71.8 | FAIL first >100; four pass |
| Prewarmed poster | 10.0, 10.6, 14.8, 10.1, 10.5 | PASS all <=100 |
| Unused prewarm | No helper at 31-second check | PASS |

Timing ends at UI receipt of the native paint/render+Present+Commit notification,
not a photodiode measurement. Poster includes thumbnail retrieval. No outlier was
discarded. `history-startup.json` and `history-startup-final.log` retain all clicks.
Warm idle helper root private: 78,860,288 bytes; helper/WebView tree private:
248,479,744; sampled tree GPU dedicated/shared: 43,679,744 /2,818,048 bytes.
Unavailable per-process GPU counters are null, not proof of zero allocation.

## 10.2 Before/After

Baseline CPU exceeded 15%, so the retained implementation uses two zero-copy
d3d11va mpv instances in one helper. The original renders at native dimensions;
DComp scales/clips it. Enhanced output is clock/audio master; silent original
follows with small bounded speed corrections and exact reseeks for large errors.
Divider changes update clips without rebuilding the graph.

CPU is process-tree CPU, one logical core=100%, for 60 seconds, capture off.
GPU columns are peak sampled process-tree dedicated/shared decimal MB, not
total-board VRAM. Drop counters are VO counters, not every pipeline stage.

| Original ->output | Renderer | CPU % | GPU dedicated/shared MB | Measured interval VO drops enhanced/original |
| --- | --- | ---: | ---: | --- |
| 1080p30 ->1440p60 | hstack | 80.784 | 739.234 /104.083 | End counter 0; one renderer |
| 720p30 ->1080p60 | hstack | 47.922 | 431.251 /78.709 | End counter 0; one renderer |
| 1080p30 ->1440p60 | Two mpv final | 20.735 | 450.535 /38.433 | 0 /0 |
| 720p30 ->1080p60 | Two mpv final | 21.143 | 253.944 /30.945 | 0 /0 |

**Two mpv ships because it is better; CPU <=15% still FAILS.** Following a one-second
settle, both 60-second intervals added zero VO drops. Enhanced counters already
contained 7 startup drops in each final run: whole-open "no drops" is not proven.
Raw samples/start/end counters: `hstack-before.json`, `two-mpv-final.json`, NDJSON.

Paired seek/step completion waits for both renderers. Time properties use doubles
to prevent six-decimal rounding at frame boundaries. Early exact seeks queue until
the original's initial playback restart, preventing its start option overwriting
them. All 36 final steps (24 forward,12 back) show the expected output picture and
ceil(output/2) original picture; both receive identical exact-seek target times.
Odd 60 fps positions necessarily repeat a 30 fps picture: identical decoded PTS
is not claimed. Sixty seconds/61 burned-number captures: absolute drift median
**0**, worst **2 output frames: PASS**. No interpolation was added.

## 10.3 Own-window visual proof

Test-only selfCapture uses Windows.Graphics.Capture and validates HWND ownership
against the current PID. Fixed IPC commands drive only the helper's own page.
The mockup runs in another own helper/WebView2 test window. No Computer Use,
desktop capture, or input to another window was used. Capture/mockup hooks are
absent from production; the default protocol rejects those commands. All captures
are synthetic, external under `work/evidence/VE-P1e-3c2/run2`.

| Proof | Actual / evidence | Result |
| --- | --- | --- |
| Transparent controls, no panel | controls-clean-reference.png versus controls-paused.png: padding max RGB delta 0; header 4,548 changed pixels; paused captures | PASS sampled pixels and visual review |
| Black bars | RGB maximum 0; black-letterbox.png | PASS |
| Preview above bar, time beneath | preview-above.png | PASS visual |
| Autohide / paused reveal | Glyph white pixels visible30 /hidden0 after2.5s /paused79; playing/paused captures | PASS |
| Exact stepping | step-00..35.png, visual-proof-final.json; 36/36 output and source mappings | PASS pictures/common requested targets; PTS limit above |
| Playing drift | drift-00..60.png; 61 samples, median0 /worst2 | PASS |
| Divider input-to-picture <=50ms | 20 moves; WGC frame QPC median97.804 /worst114.143ms; ui-proof.json, ui-divider-*.png | FAIL observed bound |
| Divider no pause | All20 states paused=false; position2.283 ->5.500s | PASS state/progress; pacing limitation below |
| Transparent overlays | shortcut-sheet.png, speed-menu.png | PASS visual |
| Own-window mockup parity | mockup-landscape.png versus product captures | Reviewed, differences below |

Divider measurement is input-send to captured matching pixel's WGC timestamp,
not the IPC ACK. Test-only readback/PNG synchronously occupies the render thread;
it can affect pacing and miss the earliest changed frame. This is an observed
upper bound, not proof of intrinsic production latency or uninterrupted pacing.
No subtraction or gate relaxation was used.

Visible mockup differences: compact one-row text controls versus two icon rows,
large amber play button and separate 10-second buttons; different slider spacing,
preview size and native title-bar frame. The mockup's demo toolbar is not product UI.
Product Details shows metadata; file actions remain in History. Binding visible
points are retained: transparent floating controls/shadows, black bars, undrawn
split, preview/time placement, transparent overlays, playing autohide/paused reveal.
Full gesture/DPI/accessibility and human owner interaction were not newly repeated.

## 10.4 HTTP 400

**20/20 separate invocations PASS**, assertions unchanged:
`service-results.txt`, `service-1.log` through `service-20.log`.
No 400 reproduced; the prior cause is unconfirmed. The test API fixture prints
failure method/path/status/body and restores the response stream before rethrowing.
No engine queue/deletion logic changed. Full CPU results are separate below.

## 10.7 CI

Only the optional-tools setup step receives GITHUB_TOKEN from github.token.
A script-only handler adds a Bearer unredirected header to HTTPS api.github.com
when the variable is nonempty. Asset requests and cross-host redirects receive no
token. Product link_tools.py is unchanged and reads no token. Seven tests exercise
API/assets, no-token, redirect stripping and product requests with the variable set.

The packaged step has an ID and shares the existing bounded failure collector/
artifact condition with the GUI suite. Startup diagnostics are appended to the
launch log, so app-*.log preserves them even when launch throws before CDP attaches.
No retry was added.

Local packaged.spec.ts: **1 PASS (5.7s)**, failure not reproduced. To protect the
running owner instance, only this reproduction used a build-time test identifier.
The first launch request was auto-review rejected over identifier isolation.
Local tauri-codegen/tauri-build 2.7.3 source proved TAURI_CONFIG merging and rebuild
tracking; single-instance 2.5.4 keys on config.identifier. The isolated identifier
was confirmed in the executable before the separately approved launch. No rejected
action was bypassed. The final candidate is rebuilt with normal production config.
Hosted Windows/Ubuntu final CI is NOT_RUN here; operator commits/pushes/checks it.

## Final checks

| Check | Result / evidence under run2 |
| --- | --- |
| Ruff lint / format | PASS;185 files; ruff-final.log, format-final.log |
| Pyright configured src scope | PASS;0 errors/warnings; pyright-final.log |
| ESLint / tsc / Vite | PASS; *-final-resume.log; diagnostics-only helper edit additionally linted/typed |
| Vitest | PASS;17 files/78 tests |
| Payload policy | PASS;1 test |
| Rust helper fmt/default tests/all-feature tests/clippy -D warnings | PASS;6 tests each configuration; helper-final-*.log |
| Rust main fmt/tests/clippy -D warnings | PASS;28 tests; main-final-*-resume.log |
| Full Playwright | PASS25; SKIP15 explicit opt-in GPU/media/visual/package/startup cases; e2e-final.log |
| Real History native startup | PASS test; numerical gates above; history-startup-final.log |
| Packaged CDP spec | PASS1; packaged-final.log |
| Final CPU suite | PASS676 /SKIP24 /deselected101; 482.65s; pytest-final-resume.log |
| Production builds/candidate | PASS; helper-final-release.log, main-production-final.log; default features/no test hooks |
| Final hosted CI | NOT_RUN; operator responsibility |

Earlier interrupted CPU log is NOT a pass. The diagnostics-only desktop test helper
edit followed the full e2e suite; the packaged spec and lint/types ran afterward.
Accepted GPU soaks, full A5, packaging/licence checks and Compare were intentionally
not rerun. No system/user settings, drivers, runtime installs or environment changes.

### Earlier attempts and warnings

All measurement failures remain external, not relabeled. Initial cold median
771.926ms; parallel trial438.118ms preceded the final first-commit guarantee.
First History attempt missed the metrics binding; second completed five cold clicks
but failed the memory sampler guard. Final cold/warm/expiry test passed.
Intermediate two-mpv CPU pairs (1440/1080):17.97/19.55,20.267/23.619,20.423/20.084%;
final values above retain the target miss.

First WGC resize crashed; cleanup was refused. Later trials exposed stale capture,
resize and shutdown errors, corrected before final proof. Visual trial3 drift median1/worst5 and trial4 median2/worst2 also remain recorded.
Visual trial5 drift
median1/worst3 and paused reveal failed; trial6 passed drift but needed source
rounding correction. Trial8 exposed the initial original-seek race. Final trial9
passes36 mappings and drift. Raw visual-proof*.log/NDJSON and visual-* snapshots
retain failed attempts. Earlier divider trials also exceeded50ms. PowerShell wraps
native stderr as NativeCommandError; actual exit codes determine check results.

## Changed files

29 files relative to resumed HEAD 9e1b716 (including this report and eight new source/test files). No binaries, captures, fixtures or caches are included. CURRENT_TASK.md, product link_tools.py and supervisor are unchanged.

- `.ai/LAST_REPORT.md`
- `.github/workflows/ci.yml`
- `gui/scripts/player-acceptance.py`
- `gui/scripts/player-memory.py`
- `gui/src-tauri/player/Cargo.toml`
- `gui/src-tauri/player/src/composition.rs`
- `gui/src-tauri/player/src/host.rs`
- `gui/src-tauri/player/src/lib.rs`
- `gui/src-tauri/player/src/main.rs`
- `gui/src-tauri/player/src/mpv.rs`
- `gui/src-tauri/src/commands.rs`
- `gui/src-tauri/src/player.rs`
- `gui/src/Home.tsx`
- `gui/src/desktop.ts`
- `gui/src/player/Controls.tsx`
- `gui/src/player/player.css`
- `gui/src/types.ts`
- `gui/tests/desktop.ts`
- `gui/tests/player-controls.test.tsx`
- `scripts/prepare_link_test_tools.py`
- `tests/test_service.py`
- `gui/scripts/player-review.py`
- `gui/scripts/player-ui-proof.py`
- `gui/scripts/player-visual-proof.py`
- `gui/src-tauri/player/src/capture.rs`
- `gui/src-tauri/player/src/follower.rs`
- `gui/src-tauri/player/src/startup.rs`
- `gui/tests/e2e/native-player-startup.spec.ts`
- `tests/test_prepare_link_test_tools.py`

## Disk and cleanup

Final inventory in decimal GB (logical file lengths, not allocation). Restored node dependencies offline:191,884,396 bytes at
restore (191,885,715 bytes before removal); no new model/tool/binary download. Existing Python/Rust/WebView2 and LGPL
DLLs reused. Start C/D free space and exact start folder sizes: NOT_MEASURED.
Do not infer them from Run1. First live checkpoint12:20:39: cache10.451GB,
run2 evidence0.120GB, scratch0.355GB, D free977.290GB; not a start baseline.


| Item | Start | Final GB |
| --- | --- | ---: |
| C free | NOT_MEASURED | 351.319945 |
| D free | NOT_MEASURED | 978.771890 |
| Current running package | NOT_MEASURED | 0.005764 |
| Separate candidate | NOT_MEASURED | 0.048290 |
| All package files, including accepted source offer | NOT_MEASURED | 0.125265 |
| This whole cycle's evidence, including Run1 | NOT_MEASURED | 0.178931 |
| Run2 evidence (subset, do not sum) | NOT_MEASURED | 0.140053 |
| Complete cache | NOT_MEASURED | 9.505053 |
| Scratch retained refused profiles | NOT_MEASURED | 0.008649 |

All 315 inventoried cleanup candidates below were removed successfully:
**3,031,885,218 logical bytes**, independently measured before deletion.
Exact per-item outcomes are in cleanup-results.json; no refusal was retried.
Node_modules, dist, repository Python caches and isolated test homes are removed;
.venv and local-env.ps1 remain. The empty scratch/tmp can be recreated by local-env.
The two explicitly refused profiles are the only nonempty scratch items.

Exact net growth cannot be reconstructed without a start inventory. A conservative
retained-file upper estimate is **0.554680 GB**: all cache files modified since
this run's restore (241,508,678 bytes), the entire package
(including the pre-existing source offer), entire cycle evidence, all retained
scratch, and all repository files modified since restore (327,200 bytes, including
.venv runtime caches). This deliberately counts overwrites/pre-existing content
and is not a measured net delta. No unreported downloads were made. Retained work
is below the 1GB gate under this accounting; cache <40GB, cycle evidence <300MB,
D free >200GB. The source scripts listed above regenerate the synthetic fixtures/proof;
baseline-instrumentation.zip preserves the temporary instrumented baseline source.

Candidate binaries (default production config; no cdp/e2e/test-faults):

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| VideoEnhancer-Player.exe | 1589760 | `cc6fd57e3f25af6ddb12a25f74c921008f53240ad1a71a4f165bfff4eba9f8c1` |
| VideoEnhancer.exe | 5867008 | `ad75ebeb94a5fa8602c26cdf1b00317de9b7c6675f546728b6db2c5080b59518` |

### For the owner to delete (never retried)

- work/scratch/p1e3c2-native/h264-bench-two-0: inherited Run1 refusal; last known1,712 bytes.
- work/scratch/p1e3c2-native/visual-proof: sharing-violation refusal on
  webview/EBWebView/Default/Extension Rules/000003.log; checkpoint8,647,268 bytes.
  Neither refused root nor its parent is recursively deleted.

## Questions for the designer (defaults applied)

1. CPU still20.735% at1440p60. Keep the better two-decoder method and PARTIAL;
   further performance design needs review.
2. First poster165.8ms. Keep the early native poster/approved hover prewarm; retain miss.
3. Divider WGC exceeds50ms and capture affects pacing. Keep clip-only updates;
   do not claim target passed or change the measurement to an ACK.
4. 30fps source lacks a picture for every60fps PTS. Use common exact target times
   and corresponding source pictures; no new interpolation or identical-PTS claim.
5. Compact layout differs from nonbinding mockup styling. Preserve binding behavior;
   broader visual redesign remains for the designer.

## Owner check (human checks not newly executed)

1. Use the candidate with disposable home and synthetic footage.
2. Click History without hovering; observe poster and playback.
3. Close, hover, then click; compare warm opening.
4. Hover without clicking; wait over30s and confirm helper exit.
5. Pause, seek and step forward/back; compare burned output numbers.
6. Enable Before/After; compare source/output numbers while playing and paused.
7. Move the split during playback; check for stalls and an undrawn divider.
8. Hover timeline; check preview above and time below.
9. Let controls hide, pause to reveal, inspect overlays, black bars and Details.
10. Close; confirm History focus and helper exit. Record the known CPU/poster/divider
    limitations. Keep owner media out of development evidence.

## Cleanup inventory (recorded before deletion)

Logical bytes, independent of drive free-space deltas. Exact candidates follow; rejected roots above are excluded.

| Candidate under work | Logical bytes |
| --- | ---: |
| `scratch/p1e3c2-baseline` | 117186 |
| `scratch/p1e3c2-native/cold-parallel-0` | 10627245 |
| `scratch/p1e3c2-native/review-original-1080.mp4` | 16857806 |
| `scratch/p1e3c2-native/review-original-720.mp4` | 16412367 |
| `scratch/p1e3c2-native/review-output-1080.mp4` | 25967452 |
| `scratch/p1e3c2-native/review-output-1440.mp4` | 63744569 |
| `scratch/p1e3c2-native/review-poster.jpg` | 9184 |
| `scratch/p1e3c2-native/visual-proof-four` | 48540317 |
| `scratch/p1e3c2-native/visual-proof-three` | 48486354 |
| `scratch/p1e3c2-native/visual-proof-two` | 11101982 |
| `scratch/p1e3c2-review-bin` | 56584788 |
| `scratch/p1e3c2-review-e2e` | 66321297 |
| `scratch/p1e3c2-review-service-1` | 0 |
| `scratch/p1e3c2-review-service-10` | 0 |
| `scratch/p1e3c2-review-service-11` | 0 |
| `scratch/p1e3c2-review-service-12` | 0 |
| `scratch/p1e3c2-review-service-13` | 0 |
| `scratch/p1e3c2-review-service-14` | 0 |
| `scratch/p1e3c2-review-service-15` | 0 |
| `scratch/p1e3c2-review-service-16` | 0 |
| `scratch/p1e3c2-review-service-17` | 0 |
| `scratch/p1e3c2-review-service-18` | 0 |
| `scratch/p1e3c2-review-service-19` | 0 |
| `scratch/p1e3c2-review-service-2` | 0 |
| `scratch/p1e3c2-review-service-20` | 0 |
| `scratch/p1e3c2-review-service-3` | 0 |
| `scratch/p1e3c2-review-service-4` | 0 |
| `scratch/p1e3c2-review-service-5` | 0 |
| `scratch/p1e3c2-review-service-6` | 0 |
| `scratch/p1e3c2-review-service-7` | 0 |
| `scratch/p1e3c2-review-service-8` | 0 |
| `scratch/p1e3c2-review-service-9` | 0 |
| `scratch/p1e3c2-run2-cpu-bin` | 18438722 |
| `scratch/p1e3c2-run2-final-pytest` | 49273 |
| `scratch/p1e3c2-run2-final-pytest-resume` | 0 |
| `scratch/p1e3c2-run2-full-e2e` | 547422675 |
| `scratch/p1e3c2-run2-packaged` | 11322137 |
| `scratch/p1e3c2-run2-release-bin` | 5844546 |
| `scratch/tmp` | 10656067 |
| `scratch/videoenhancer.jsonl` | 3138 |
| `repo/gui/node_modules` | 191885715 |
| `repo/gui/dist` | 597122 |
| `repo/.ruff_cache` | 11402 |
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
| `cache/tauri-target/debug/deps/libvideoenhancer_player-1304494e86b92893.rlib` | 2031150 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-1304494e86b92893.rmeta` | 386857 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-19cfab87fe5d3014.rmeta` | 133553 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-439d427e7144f55e.rlib` | 2031856 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-439d427e7144f55e.rmeta` | 386809 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-80726929358a9182.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-97e6c93c723bf456.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-a82fadec2d016f59.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-d09e8693a6af886f.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-dd6d29417458706f.rmeta` | 133553 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-e52895876edb27a2.rlib` | 2293098 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-e52895876edb27a2.rmeta` | 435571 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-f93eb5faca3dcf21.rmeta` | 180509 |
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
| `cache/tauri-target/release/deps/libtao-e9e221a665d18e7d.rlib` | 5605958 |
| `cache/tauri-target/release/deps/libtao-e9e221a665d18e7d.rmeta` | 4752116 |
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
| `cache/tauri-target/release/deps/libvideoenhancer_player-2cfcda8b4f7303c9.rlib` | 1203954 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-2cfcda8b4f7303c9.rmeta` | 481739 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-5fa6d0a4e43966c4.rlib` | 1184524 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-5fa6d0a4e43966c4.rmeta` | 462305 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-8b78fccc128c36a0.rlib` | 1185440 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-8b78fccc128c36a0.rmeta` | 463233 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-96fc99c16c4c3c30.rlib` | 1205390 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-96fc99c16c4c3c30.rmeta` | 481739 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-e82f8565ed08af1d.rlib` | 1334410 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-e82f8565ed08af1d.rmeta` | 538100 |
| `cache/tauri-target/release/deps/libvideoenhancer_player_baseline-52ed107400ff3164.rlib` | 1202096 |
| `cache/tauri-target/release/deps/libvideoenhancer_player_baseline-52ed107400ff3164.rmeta` | 463242 |
| `cache/tauri-target/release/deps/libwebview2_com-5dcf12f7274b37a4.rlib` | 3831406 |
| `cache/tauri-target/release/deps/libwebview2_com-5dcf12f7274b37a4.rmeta` | 2480049 |
| `cache/tauri-target/release/deps/libwebview2_com-fa6f0ceb89ea0c9a.rlib` | 3831402 |
| `cache/tauri-target/release/deps/libwebview2_com-fa6f0ceb89ea0c9a.rmeta` | 2480049 |
| `cache/tauri-target/release/deps/libwebview2_com-fc8affbdbc590f64.rlib` | 3831272 |
| `cache/tauri-target/release/deps/libwebview2_com-fc8affbdbc590f64.rmeta` | 2479871 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-262a3a5d14a454e7.rlib` | 19214048 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-262a3a5d14a454e7.rmeta` | 7865095 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-6813a2b3638d79f4.rlib` | 19214230 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-6813a2b3638d79f4.rmeta` | 7865268 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-c98f8415d1830d33.rlib` | 19214280 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-c98f8415d1830d33.rmeta` | 7865268 |
| `cache/tauri-target/release/deps/libwindows-129f7ddb30a5e658.rlib` | 128169858 |
| `cache/tauri-target/release/deps/libwindows-129f7ddb30a5e658.rmeta` | 121034647 |
| `cache/tauri-target/release/deps/libwindows-3c393d379a21c02c.rlib` | 128195586 |
| `cache/tauri-target/release/deps/libwindows-3c393d379a21c02c.rmeta` | 121034647 |
| `cache/tauri-target/release/deps/libwindows-b3a419c5329a3c3f.rlib` | 119158428 |
| `cache/tauri-target/release/deps/libwindows-b3a419c5329a3c3f.rmeta` | 112702843 |
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
| `cache/tauri-target/release/VideoEnhancer-Player-Baseline.exe` | 1533440 |
| `cache/tauri-target/release/VideoEnhancer-Player-Test.exe` | 1693184 |
