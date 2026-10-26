Task ID: VE-P1e-3c2 / Windows implementation and validation cycle
Status: PARTIAL

The implementation and local checks below are reviewable. Acceptance is incomplete:
cold startup misses the target, the paired-decoder CPU target was missed, visual
acceptance was unavailable, and final Windows/Ubuntu CI belongs to the operator. One resumed full CPU run also
failed an existing HTTP history-removal test; its single-test rerun passed, and
the failure remains explicitly recorded rather than being relabelled.
No commit, push, merge, branch change or other Git mutation was performed.
Initial branch: `claude/project-thread-6lra47`; HEAD:
`1002e26cf26c89c254d6bcb3982f4870596a2bac`; initial worktree clean.
Read-only Git status/diff checks were run with escalation after sandbox denial.
The task and designer mockup were preserved. This report is not a merge approval.

## Part A: implementation

B1 uses an optional, separate Rust `VideoEnhancer-Player.exe`. Its D3D11 libmpv
picture and transparent WebView2 composition controller share one DirectComposition
tree. The main application never loads libmpv; only a History click starts the
helper. Closing it exits the process, releases the decoder/WebView tree and returns
focus to History. The poster uses the existing thumbnail. Device, DLL, process and
initialization errors return to the HTML5/default-player fallback.

The helper observes mpv properties and services wakeup/render events. It does not
query properties synchronously from the rendering path. Commands are asynchronous.
Seeks use `absolute+exact`; steps require pause and complete only after a changed
position and render. This completion signal is not a captured output-frame proof.

The controls implement play/pause, seeking, latest-only keyframe hover thumbnails,
speed, volume/mute, paused stepping, fullscreen, Details, shortcuts, 100–800% zoom,
pan and Before/After divider. Controls/title/cursor hide after two seconds while
playing and remain visible when paused. CSS surfaces, preview and menus are
transparent with text shadows; actual compositor transparency remains NOT_RUN.
The Details panel provides basic session metadata; exact visual/mockup parity has
not been accepted. Parent History retains its existing detail/actions.

### IPC and origin restrictions

- Version 1, request IDs and addressed success/error responses. Unknown fields,
  unknown commands, unsupported versions, nonfinite/out-of-range numbers and
  oversized messages are rejected. Commands: open/close/pause/seek/step/speed,
  volume/mute/fullscreen/transform/beforeAfter/divider/preview.
- Parent bootstrap (64 KiB maximum) contains validated existing canonical file
  paths and opaque session handles; controls requests (16 KiB maximum) contain
  handles only. Paths, arbitrary commands, JavaScript and URLs are not commands.
- Only the embedded `https://player.videoenhancer.invalid/player.html` page and
  its embedded build assets are served. Strict CSP, external requests/navigation
  and popups blocked, production DevTools/context menu disabled.
- Main session generations cancel stale opens/events. Duplicate request IDs fail;
  pending commands time out. Hover generations discard stale decoding results;
  a separate small paused decoder supplies 320×180 PNGs with a bounded cache.
- `test-faults` builds alone enable synthetic device failure and the measured
  29-second idle policy. The default release package has neither test behavior.
  The e2e main application identifier is isolated from the running owner's app.

### A5 measurement boundaries

These are synthetic-fixture measurements on this Windows RTX 4060 Ti system,
driver 617.42. The native harness measures process spawn to software `loaded`
notification, same-session reloads and mpv playback-restart acknowledgements.
They are not display-photon latency or a five-run History-click first-frame test.
The actual History click-to-loaded upper observation was 1,366 ms (one e2e run).
Same-session warm reloads do not establish warm cross-job main-app opens: production
exits the helper. Every cold median below exceeds 500 ms. No historical spike
timings are substituted for product measurements.

CPU is the process-tree CPU-seconds delta / elapsed seconds × 100 (one core = 100%).
GPU memory is sampled per-process PDH dedicated/shared, separate from Torch and
device-wide memory. Dropped counts below are the observed mpv video-output counter;
they do not independently establish decoder drop counts.

| Fixture / run | Cold median, ms (5) | Reload median, ms (5) | Seek median / worst, ms (20) | CPU % (60 s) | New / cached preview maximum, ms | Observed VO drops |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| h264-ordered | 721.094 | 41.563 | 126.066 / 233.772 | 3.689 | 46.620 / 1.012 | 0 |
| hevc-ordered | 736.688 | 33.327 | 92.660 / 189.357 | 4.952 | 70.246 / 1.063 | 0 |
| av1-ordered | 734.890 | 28.517 | 101.524 / 206.849 | 5.598 | 45.690 / 0.939 | 0 |
| vp9-ordered | 717.309 | 33.324 | 54.250 / 83.453 | 8.127 | 33.037 / 0.949 | 0 |
| rotation-ordered-resumed | 812.519 | 41.651 | 75.995 / 133.933 | 5.039 | 49.180 / 1.226 | 0 |
| pair-ordered-720 | 737.401 | 33.308 | 62.791 / 142.941 | 33.517 | 31.503 / 1.255 | 0 |

All six fixture families were measured; the five non-pair families meet the
measured seek/reload/preview/CPU boundaries above. Cold startup FAIL; paired CPU
FAIL. Rows named ordered use the final command-order fix and record the exact executable
hash. The five non-pair ordered rows were rerun concurrently with the normal-play
soak; their GPU contention condition is explicit. Earlier measurements remain in
the raw appendix and external JSON, rather than being replaced.
Exact burned-in output-frame stepping, 60-second Before/After drift (0 frames),
divider input-to-picture ≤50 ms, native alpha compositing, OS pinch/touchpad,
multiple monitors/DPI, sleep/wake and actual device removal are NOT_RUN.
Divider acknowledgements alone cannot pass a picture-latency requirement.

### Before/After method and failures

The synthetic original is 640×360 at 30 fps; its synthetic enhanced counterpart is
1280×720 at 60 fps, both with frame counters. On first activation, add the original
as a video-only track, switch to D3D11 copy-back decode, then apply one libavfilter
graph: scale the original to output size and hstack both videos into one surface.
The two composition visuals clip/offset that shared surface; divider movements
change composition geometry without rebuilding the filter graph. Enhanced audio
remains the only selected audio. A single clock is an architectural choice, not
an experimentally proven zero-frame drift result.

`pair-final` enabled in 179.544 ms; divider ACKs are in the raw appendix. Its CPU
was 29.67%, exceeding 15%. A later final-release probe used nonexistent filenames
and correctly failed. The next probe used incorrect 1920×1080 bootstrap dimensions
for the 1280×720 fixture and failed: mpv reported a disconnected `vid2`. A subsequent
ordered-command probe with those same incorrect dimensions reported the explicit
height mismatch. These are retained FAIL runs, not accepted pair evidence.
The helper now waits for video-add completion, then hwdec completion, before
submitting the filter graph; it keeps rendering throughout. A correctly sized
1280×720 probe follows below. Failed probes are not discarded or counted as passes.

### Lifecycle and fallback results

- PASS: real History → native helper → close → focus return; one helper while open,
  none ten seconds after close; main process never has a libmpv module.
- PASS: real main IPC with missing helper, missing DLL, invalid DLL and injected
  D3D creation failure; the last is a controlled test fault, not physical GPU loss.
- PASS: mocked helper failures/close handling in four component tests. HTML5 and
  default-player fallback preserve the existing HEVC guidance.
- Actual WebView runtime removal, actual GPU device loss and OS-default-player
  launch by hand: NOT_RUN. ProcessFailed/render errors have fallback handlers.

The native-product memory check before / ten seconds after close (bytes): main
private 6,623,232 / 6,492,160; main process tree private 284,028,928 / 270,143,488;
sampled dedicated GPU 56,934,400 / 54,599,680; shared 8,228,864 / 6,803,456.
All four returned within +5%; sampling errors empty, helper list empty.
The 'open' main-tree sample excludes the separate helper; use standalone helper
tree samples for its footprint rather than interpreting that row as total product.

Idle-policy experiment (test-only build): cold 755.299 ms, five reload median
36.010 ms, auto-exit 29.106 s after close, exit 0 and no children. At ten seconds
the retained helper tree is reported in `idle-policy.json`; the helper alone held
279,330,816 private bytes and 159,797,248 dedicated GPU bytes. Production defaults
to exit on close to release these resources, accepting the measured cold penalty.

## Part B: validation and flaky retry test

| Check | Status | Actual |
| --- | --- | --- |
| Earlier full CPU Python suite | PASS | 669 passed, 24 skipped, 101 deselected; 431.62 s |
| Resumed full CPU suite, first | FAIL | 668 passed, 1 failed, 24 skipped, 101 deselected; 464.07 s |
| Failed service test, diagnostic rerun | PASS | Same unchanged test; no HTTP error reproduced |
| Resumed full CPU suite, second | PASS | 669 passed, 24 skipped, 101 deselected; 426.61 s |
| Retry module | PASS | 7 passed; deterministic integer virtual clock |
| GUI unit suite, final | PASS | 17 files, 77 tests |
| Main Rust unit suite | PASS | 28 tests |
| Helper Rust unit suite | PASS | 4 tests; schema, handles, routing, hover/lifecycle |
| Full Windows Playwright suite | PASS / SKIP | Resumed: 25 passed, 14 skipped; 3.9 min (earlier: 22 / 14) |
| Focused fallback + actual native product | PASS | Resumed: 5 passed; 21.4 s (earlier: 22 s) |
| Payload test / real pinned inventory | PASS | 1 Node test; all DLL/source/licence inventory hashes |
| Python ruff check + format | PASS | 181 files formatted; check clean |
| Python pyright | PASS | 0 errors, 0 warnings, 0 informations |
| ESLint + tsc + Vite production build | PASS | Final source build |
| Rust fmt + clippy | PASS | Main/helper, `-D warnings`; test-fault helper also checked |
| Windows/Ubuntu final-commit CI | NOT_RUN | Operator must commit/push and inspect CI |
| Manual visual/alpha/physical device checks | NOT_RUN | Computer Use permission unavailable |

The historical retry failure compared independently rounded floating timestamps:
`b >= a + delay` does not imply floating subtraction `b - a >= delay`. Reproduced
locally: a=0.001, b=1.001, difference=0.9999999999999999; a=0.002, b=2.002 gives
1.9999999999999998; a=0.004, b=4.004 gives 3.9999999999999996. This Python's Windows
monotonic implementation is GetTickCount64, resolution 0.015625 s. Real-time sleeps
and scheduling made the assertion depend on the timestamp boundary. The precise
timestamps from the failing hosted CI run are unavailable, so assigning that exact
run to this reproduced numerical mechanism remains an inference.

Only the test changes: replace the link_jobs module's clock/sleep with an integer
virtual clock; sleep deliberately wakes halfway early. Attempts occur at ticks
0, 1, 3, 7. Assert exactly four attempts, minimum 1/2/4 delays, failed state,
failure detail and retry offer/pending state. No tolerance, removed assertion or
production LinkJobs behavior change. Other existing tests/specs are unchanged.
New tests cover controls, autohide/shortcuts/divider/zoom/preview placement and
accessible names, request routing/timeouts, fallback and Compare fetch reuse.
CI adds these tests and Windows fault-helper construction, without modifying the
LGPL build workflow. Optional online native smoke was deliberately not added:
reliability on hosted Windows has not been established.

The resumed CPU failure was `test_cpu_queue_sse_controls_and_completed_output`,
at `DELETE /v1/queue/<id>` after the SSE rows were both done. HTTP 400 was observed,
but its body was not captured by that test. A read-only diagnostic wrapper on the
unchanged test reproduced no error. The precise cause is unresolved; no service
or test assertion was changed to conceal it. See resumed CPU logs for every run.

## Part C: Compare profile and bit-identical changes

Measured actual CUDA engine: six-second 512×288@30 synthetic input, a five-second
Compare, default Standard C1 cleanup + RIFE path, 1080p short side, 2× fps/H.264.
One trial per state/version. Busy trials confirmed a disposable Standard segment
was running when Compare was requested. Baseline executes a saved original Compare
module from a scratch overlay with measurement-only result statistics, without
overwriting the checkout. Builds and other validation overlapped portions of this
cycle; these are observations, not statistically isolated speedup claims.

| Run | First tile observed, s | Complete, s | GPU admission wait, s | Index, s | Range analysis, s | Original preview, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| compare-before-idle-three | 17.729 | 52.785 | 0.236 | baseline not instrumented | baseline not instrumented | baseline not instrumented |
| compare-before-busy | 46.288 | 84.134 | 29.735 | baseline not instrumented | baseline not instrumented | baseline not instrumented |
| compare-after-idle | 17.491 | 52.229 | 0.230 | 0.277 | 0.239 | 13.720 |
| compare-after-busy | 47.337 | 81.629 | 31.080 | 0.006 | 0.242 | 13.684 |

Per-model stage wall seconds (these can overlap; inference stage timings are not GPU kernel timings):

| Run / C1 | Load | Decode | Restore | Resize | RIFE | Encode | Preview transcode |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| compare-before-idle-three | 2.061 | 19.748 | 10.300 | 0.008 | 9.126 | 1.469 | not collected |
| compare-before-busy | 1.983 | 22.686 | 12.868 | 0.012 | 9.512 | 1.560 | not collected |
| compare-after-idle | 2.094 | 19.415 | 9.996 | 0.028 | 9.119 | 1.432 | 10.652 |
| compare-after-busy | 2.017 | 19.435 | 10.007 | 0.007 | 9.106 | 1.435 | 10.239 |

The baseline model instrumentation is in the `profile` item, including original
engine stats; raw JSON retains all counters. Index/range/Original are explicitly
instrumented only after the change. An earlier 256×144 input failed the model's
minimum dimension gate; it is not a successful baseline. Another trial hit an
atomic progress-file replacement read race; bounded read retry fixed the harness.
All failed-run JSON is retained. Busy Standard fixtures were intentionally stopped
after Compare completed; no owner queue was loaded.

Changes stay in Compare: enqueue/admission timing, per-stage timing, publish each
ready tile before the optional whole-file estimate, and reuse the Original/model
fetch+demux promise within the current UI operation. Baseline already shared the
index/range/Original between models. No settings, processing models, calibration,
media paths, output pixels, job scheduling policy or other engine pipeline changed.

All four successful runs have identical complete preview-file SHA-256:

- Original: `74090eaf6d8823ec8feaf16fac04987276967c5d83f553ebc072252e7cace9a4`
- C1: `74e506bb83bce8f504a88c351d0781620fec53c65bd4b09102ff7e436b869715`

P1e-3d proposals only (not implemented): a warm model worker could remove up to
the measured roughly two-second load per identical session, less retained-state
and validation costs. Caching immutable decoded ranges across operations could
save part of the measured decode wall time, requiring a bounded invalidation and
memory policy. Cooperative GPU admission/preemption could reduce the busy wait
shown above but needs designer approval and output-identity validation. None of
these estimates can promise that entire overlapping stage time is recoverable.

## Packaging and licences

Baseline current package: 5,764,162 bytes. Successful package without the optional
payload: 8,575,041 bytes (534 files), no helper or three DLLs; its recorded exe hash
is in `package-without.json`. It was inventoried and removed before building the
native candidate. The native candidate and source archive sizes follow in disk
results. The current owner's running package is untouched; the new candidate is
separate because a production single-instance smoke would hand off to that app.
The e2e application uses its own test identifier and isolated profiles instead.
Default-production main launch smoke is consequently NOT_RUN; actual helper and
equivalent e2e main were tested. Do not promote the candidate before owner review.

Packaging verifies the CI 40202006764 / commit b65a4cc payload against the pinned
manifest, file lengths and SHA-256 before copying. The three DLLs total 36,556,818
bytes; no zhongfly DLL is packaged. `sources.tar.zst` (70,739,309 bytes),
`SHA256SUMS` and source manifest are beside the package, not inside it. Each supplied
licence text is validated. LGPL licence notices, at least three-year source offer,
compatible DLL replacement/debugging rights and the FreeType acknowledgement are
included; runtime deliberately does not hash-pin user-replaced compatible DLLs.
Settings exposes Open-source licences. The OS action itself is NOT_RUN manually.

App Rust/frontend licence texts and notices are included. Six crates omit their
root licence text from published archives: alloc-stdlib, clipboard-win, three
webview2 crates and selectors. Pinned official upstream texts/provenance are in
`gui/licences/provenance.json`; official GitHub commit/blob checks and SHA-256 were
verified. The MPL 2.0 text and complete unmodified published selectors source are
shipped with its source notice. No binary/model/tool downloads or installs occurred;
only those official licence texts were fetched. Node dependencies were restored
offline (191,884,396 bytes initially). No paid services or system settings changed.

An initial package attempt correctly refused the missing alloc-stdlib licence;
its partial 5,881,080-byte candidate was inventoried then removed. A final release
copy command initially named the Cargo package rather than `VideoEnhancer.exe`;
the copy failed, was corrected, and the copied executable was hashed. Node reports
DEP0190 for the existing shell-spawn packaging path; no untrusted argument is added.

## Errors, access boundaries and intentional omissions

- Restricted-token WebView2 navigation timed out / reported 0x8007139F; isolated
  normal-token native checks ran with approved execution escalation. The same
  distinction applies to system FFmpeg/ffprobe lookup. No security setting changed.
- Computer Use reported that Edge and the player were not approved; browser
  providers were unavailable. No input/capture workaround was attempted. Mockup
  HTML was read, but opening it in a browser and own-window visual self-capture are
  NOT_RUN, including transparent controls and burned-in frame/drift verification.
- The first native warm test misclassified the previous file's stop event as an
  error. End-file reason handling was corrected; later runs distinguish errors.
- One synthetic generation requested an unavailable eq filter; its cosmetic
  transform was removed. It never changed the product's filter/encoder pipeline.
- An accidental local text encoding rewrite in two TSX files was repaired; diff
  confirms the original strings are retained. The CSS test loader was corrected.
  Earlier GUI failures remain in logs; final existing assertions pass unchanged.
- Initial Rust compile/clippy errors were corrected; no warning suppression.
- A profile cleanup sharing violation is preserved under For the owner to delete.
  Later tests wait for their own WebView children before removing their profiles.
- No owner media, queue, AppData, VE-check or Recycle Bin was inspected or cleaned.
  The owner's running normal application was not stopped. No Git mutation.

## Questions for the designer

1. Cold startup misses 500 ms. Default: ship no acceptance claim; retain the
   exit-on-close policy and provide idle-policy measurements for review.
2. Before/After CPU exceeded 15%. Default: retain the approved B1/shared graph,
   report the miss; do not introduce an unapproved dual-decoder architecture.
3. Visual/physical checks and hosted final CI are unavailable here. Default:
   PARTIAL, leave these explicitly pending for operator/owner acceptance.
4. Existing current package is running. Default: preserve it and leave a separate
   candidate; no automatic promotion or owner-process termination.
5. Exact hosted retry timestamps are unavailable. Default: report reproduced
   floating-boundary mechanism and deterministic fix, with CI attribution qualified.
6. An existing HTTP DELETE test failed once during resumed full-suite execution.
   Default: retain failure evidence and qualify the final test status; no unrelated
   engine removal behavior or assertion changes without a reproduced cause.

## Owner check (pending; plain English)

1. Close your current VideoEnhancer, then launch the candidate with a disposable home.
2. Open a finished History video. Confirm the poster appears immediately and playback starts.
3. Move the mouse, then leave it still for two seconds. Check the controls and cursor hide.
4. Pause. Confirm controls stay visible and each step moves one numbered output frame.
5. Hover and seek near the beginning, middle and end. Check the preview stays above the bar.
6. Turn on Before / After. Move the divider and watch numbered frames for at least 60 seconds.
7. Try Ctrl+wheel zoom, touchpad pan/divider, fullscreen, Esc, Details and the shortcut sheet.
8. Check controls, title and menus are transparent over video with black letterboxing.
9. Close the player, check History focus, then reopen a different video; try DPI/monitor and sleep/wake.
10. Try the no-DLL package and Settings licences. Confirm fallback and readable source/replacement notices.

## Changed files

The exact file list below comes from final read-only Git status, including every
untracked source/licence/test file. Designer-owned CURRENT_TASK and mockup differ
from origin/main but were not changed by this implementation. No spike build
files or LGPL workflow changed.

- `.ai/LAST_REPORT.md`
- `.github/workflows/ci.yml`
- `README.md`
- `gui/package.json`
- `gui/scripts/package-tauri.mjs`
- `gui/src-tauri/Cargo.lock`
- `gui/src-tauri/Cargo.toml`
- `gui/src-tauri/src/commands.rs`
- `gui/src-tauri/src/main.rs`
- `gui/src-tauri/src/media.rs`
- `gui/src/HistoryDetail.tsx`
- `gui/src/Home.tsx`
- `gui/src/Pages.tsx`
- `gui/src/Trial.tsx`
- `gui/src/desktop.ts`
- `gui/src/types.ts`
- `gui/vite.config.ts`
- `src/videoenhancer/service/compare.py`
- `src/videoenhancer/service/engine.py`
- `tests/test_link_jobs.py`
- `docs/PLAYER.md`
- `gui/THIRD_PARTY_NOTICES.md`
- `gui/licences/alloc-stdlib-0.3.0/LICENSE`
- `gui/licences/clipboard-win-5.4.1/LICENSE`
- `gui/licences/provenance.json`
- `gui/licences/selectors-0.38.0/LICENSE`
- `gui/licences/webview2-com-0.39.1/LICENSE`
- `gui/licences/webview2-com-macros-0.8.1/LICENSE`
- `gui/licences/webview2-com-sys-0.39.1/LICENSE`
- `gui/player.html`
- `gui/scripts/application-licences.mjs`
- `gui/scripts/compare-profile.py`
- `gui/scripts/player-acceptance.py`
- `gui/scripts/player-fixtures.py`
- `gui/scripts/player-idle-probe.py`
- `gui/scripts/player-memory.py`
- `gui/scripts/player-payload.mjs`
- `gui/scripts/player-payload.test.mjs`
- `gui/scripts/player-smoke.py`
- `gui/src-tauri/libmpv.lock.json`
- `gui/src-tauri/player/Cargo.lock`
- `gui/src-tauri/player/Cargo.toml`
- `gui/src-tauri/player/build.rs`
- `gui/src-tauri/player/src/composition.rs`
- `gui/src-tauri/player/src/host.rs`
- `gui/src-tauri/player/src/lib.rs`
- `gui/src-tauri/player/src/main.rs`
- `gui/src-tauri/player/src/mpv.rs`
- `gui/src-tauri/src/player.rs`
- `gui/src/player/Controls.tsx`
- `gui/src/player/ipc.ts`
- `gui/src/player/main.tsx`
- `gui/src/player/math.ts`
- `gui/src/player/player.css`
- `gui/tests/compare-cache.test.tsx`
- `gui/tests/e2e/native-player-fallback.spec.ts`
- `gui/tests/e2e/native-player-product.spec.ts`
- `gui/tests/player-controls.test.tsx`
- `gui/tests/player-fallback.test.tsx`
- `gui/tests/player-ipc.test.tsx`

## Raw A5 arrays (milliseconds)

These retain all successful matrix cold/reload/seek/step/preview/divider runs.
Full per-second memory/handle/CPU rows, hashes and logs stay outside Git in
`work/evidence/VE-P1e-3c2`; native image evidence contains synthetic media only.
Failed and superseded measurements are listed separately below.

```json
[
  {
    "label": "h264-ordered",
    "cold_ms": [
      730.4221999947913,
      741.4750999887474,
      711.6470000182744,
      716.9529000238981,
      721.0938999778591
    ],
    "warm_ms": [
      41.66829999303445,
      35.440600011497736,
      41.86590001336299,
      40.95609998330474,
      41.56340000918135
    ],
    "seeks_ms": [
      33.04879998904653,
      182.7116000058595,
      78.45139998244122,
      61.91899999976158,
      33.1022999889683,
      188.10709999524988,
      216.31519999937154,
      33.17039998364635,
      33.022600022377446,
      169.67689999728464,
      156.94729998358525,
      60.35899999551475,
      125.25019998429343,
      48.080100008519366,
      115.98349999985658,
      226.89229997922666,
      171.14039999432862,
      188.01949999760836,
      233.77169997547753,
      126.88240001443774
    ],
    "steps": [
      [
        8.619400003226474,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 8.319
          },
          "version": 1
        }
      ],
      [
        48.898200009716675,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 48.7394
          },
          "version": 1
        }
      ],
      [
        74.86679998692125,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 74.6178
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      46.62000000826083,
      27.798600000096485,
      27.321800007484853,
      27.763400023104623,
      28.31360002164729
    ],
    "cached_preview_ms": [
      0.9581999911461025,
      1.0115000186488032,
      0.9253000025637448,
      0.8414000039920211,
      0.8831999730318785
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.633333,
      "version": 1
    }
  },
  {
    "label": "hevc-ordered",
    "cold_ms": [
      736.6879000037443,
      750.7034000009298,
      721.7330999847036,
      834.8624000209384,
      726.1390000057872
    ],
    "warm_ms": [
      41.65790000115521,
      33.32739998586476,
      33.29009999288246,
      33.357600012095645,
      33.31420000176877
    ],
    "seeks_ms": [
      18.131399992853403,
      85.92649997444823,
      127.15040001785383,
      91.0571999847889,
      16.68709999648854,
      117.06700001377612,
      133.99269999354146,
      30.500699998810887,
      30.395700014196336,
      95.04939999897033,
      44.75619998993352,
      94.26240000175312,
      189.35660002171062,
      75.50400000764057,
      174.44880001130514,
      170.2313999994658,
      65.06779999472201,
      108.31049998523667,
      186.804500001017,
      16.63990001543425
    ],
    "steps": [
      [
        0.8537000103387982,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 0.6534000000000001
          },
          "version": 1
        }
      ],
      [
        44.36940001323819,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 44.1902
          },
          "version": 1
        }
      ],
      [
        98.14180000103079,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 97.92190000000001
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      70.24550001369789,
      34.624199994141236,
      36.22350000659935,
      31.961500004399568,
      30.967599974246696
    ],
    "cached_preview_ms": [
      0.9494999831076711,
      1.0628000018186867,
      0.8570000063627958,
      0.836199993500486,
      0.9867000044323504
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.633333,
      "version": 1
    }
  },
  {
    "label": "av1-ordered",
    "cold_ms": [
      723.5649999929592,
      734.8902999947313,
      720.5451999907382,
      739.8603999754414,
      755.2276000205893
    ],
    "warm_ms": [
      33.33040000870824,
      26.536800025496632,
      28.36399999796413,
      31.967599992640316,
      28.517200000351295
    ],
    "seeks_ms": [
      16.535400005523115,
      86.16050001000986,
      139.48929999605753,
      94.34549999423325,
      16.607900004601106,
      123.5166999977082,
      156.7636000108905,
      16.6456000006292,
      30.019600002560765,
      108.83290000492707,
      45.49300001235679,
      108.70330000761896,
      206.84909998090006,
      75.28179997461848,
      188.46590002067387,
      187.63999998918734,
      79.17020001332276,
      117.14759998722002,
      194.4268000079319,
      16.64409998920746
    ],
    "steps": [
      [
        0.8270000107586384,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 0.6419
          },
          "version": 1
        }
      ],
      [
        39.81210000347346,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 39.6311
          },
          "version": 1
        }
      ],
      [
        115.6704000022728,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 115.4507
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      45.69009999977425,
      29.339100001379848,
      29.813999979523942,
      29.79959998629056,
      29.70039998763241
    ],
    "cached_preview_ms": [
      0.7505999819841236,
      0.8129000198096037,
      0.9390000195708126,
      0.7662000134587288,
      0.8277999877464026
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.616667,
      "version": 1
    }
  },
  {
    "label": "vp9-ordered",
    "cold_ms": [
      717.7814999886323,
      703.3837000199128,
      709.9238999944646,
      717.3094000027049,
      728.970299998764
    ],
    "warm_ms": [
      41.5946000139229,
      33.32139999838546,
      33.32399998907931,
      33.32129999762401,
      33.35290000541136
    ],
    "seeks_ms": [
      83.45330000156537,
      32.553099998040125,
      77.76990000274964,
      61.016199993900955,
      63.87909999466501,
      62.81420000595972,
      16.641099995467812,
      60.29550000675954,
      61.36970000807196,
      65.043099981267,
      62.82190000638366,
      78.96710000932217,
      29.667099996004254,
      45.51540000829846,
      32.44700000504963,
      45.371799991698936,
      48.20370001834817,
      45.786900009261444,
      16.639399982523173,
      47.39329998847097
    ],
    "steps": [
      [
        0.7661999843548983,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 0.5928
          },
          "version": 1
        }
      ],
      [
        43.14289998728782,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 42.9024
          },
          "version": 1
        }
      ],
      [
        35.36419998272322,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 35.1423
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      33.03669998422265,
      22.60200001182966,
      21.287000010488555,
      21.402399986982346,
      21.877899998798966
    ],
    "cached_preview_ms": [
      0.8061999978963286,
      0.9487999777775258,
      0.7719999994151294,
      0.8054000209085643,
      0.8719000034034252
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.616667,
      "version": 1
    }
  },
  {
    "label": "rotation-ordered-resumed",
    "cold_ms": [
      812.5185000244528,
      869.9173999775667,
      933.2137999881525,
      807.7596000221092,
      793.2276999927126
    ],
    "warm_ms": [
      41.65130000910722,
      35.37139997933991,
      42.491900007007644,
      41.165699978591874,
      42.847300006542355
    ],
    "seeks_ms": [
      31.819499999983236,
      110.18700001295656,
      55.223300005309284,
      33.20320000057109,
      34.17140000965446,
      113.02690001321025,
      122.52790000638925,
      29.673899989575148,
      33.2666999893263,
      110.05679998197593,
      85.11189999990165,
      35.74510000180453,
      73.82699998561293,
      34.168100013630465,
      62.12270000833087,
      123.81680001271889,
      94.89060001214966,
      114.08460000529885,
      133.9330000046175,
      78.16219999222085
    ],
    "steps": [
      [
        8.330200013006106,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 8.094199999999999
          },
          "version": 1
        }
      ],
      [
        30.50769999390468,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 30.211399999999998
          },
          "version": 1
        }
      ],
      [
        41.43300000578165,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 41.1609
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      49.179699999513105,
      24.827700020978227,
      30.980500014266,
      27.581100002862513,
      27.518299990333617
    ],
    "cached_preview_ms": [
      0.8814000175334513,
      1.0067000112030655,
      0.988799991318956,
      1.2147999950684607,
      1.225699990754947
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.833333,
      "version": 1
    }
  },
  {
    "label": "pair-ordered-720",
    "cold_ms": [
      739.8931999923661,
      713.1405999825802,
      737.4010999919847,
      729.2929999821354,
      748.8355000095908
    ],
    "warm_ms": [
      41.63909997441806,
      33.30819998518564,
      33.268699975451455,
      33.56290000374429,
      33.14820001833141
    ],
    "seeks_ms": [
      22.44770000106655,
      52.900000009685755,
      92.51679998124018,
      61.890500015579164,
      16.679399996064603,
      91.6406000033021,
      96.82740000425838,
      17.801000009058043,
      28.555500000948086,
      63.690599985420704,
      30.16419999767095,
      76.03029999881983,
      142.94140000129119,
      47.70949998055585,
      125.01600000541657,
      121.83980000554584,
      50.905700016301125,
      77.0098999782931,
      126.92810001317412,
      17.658299999311566
    ],
    "steps": [
      [
        2.0560999982990324,
        {
          "event": "stepDone",
          "reply": 1000034,
          "result": {
            "latency_ms": 1.8276
          },
          "version": 1
        }
      ],
      [
        44.934799982002005,
        {
          "event": "stepDone",
          "reply": 1000035,
          "result": {
            "latency_ms": 44.7735
          },
          "version": 1
        }
      ],
      [
        223.22200000053272,
        {
          "event": "stepDone",
          "reply": 1000036,
          "result": {
            "latency_ms": 223.00539999999998
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      31.50340000865981,
      20.6639000098221,
      20.726799994008616,
      18.408200005069375,
      19.446699996478856
    ],
    "cached_preview_ms": [
      0.8546000171918422,
      1.2552000116556883,
      1.205699983984232,
      1.0063000081572682,
      1.0852999985218048
    ],
    "divider_ack_ms": [
      0.31519998447038233,
      8.207400009268895,
      0.19240000983700156,
      0.12660000356845558,
      0.2693000133149326
    ],
    "enable_pair_ms": 248.48319997545332,
    "last_state": {
      "decoder": "",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.716667,
      "version": 1
    }
  }
]
```

### Additional pair run: pair-final

Errors: `[]`; full result: `pair-final.json`.
```json
[
  {
    "cold_ms": 776.5070000023115,
    "warm_ms": [
      41.58800000732299,
      33.31889999390114,
      33.31080000498332,
      33.353799997712485,
      33.35359999618959
    ],
    "seeks_ms": [
      21.59439999377355,
      60.75370000326075,
      94.71430000849068,
      62.11600000096951,
      16.641000009258278,
      91.80420001212042,
      95.55250000266824,
      18.68069999909494,
      27.679999999236315,
      63.43650000053458,
      30.50329998950474,
      76.6622999944957,
      141.17229999101255,
      47.786199997062795,
      124.84330000006594,
      123.67329999688081,
      63.54550000105519,
      78.78189999610186,
      125.11990001075901,
      16.623199990135618
    ],
    "enable_pair_ms": 179.54379999719094,
    "divider_ack_ms": [
      0.23780000628903508,
      0.1379000023007393,
      7.923199998913333,
      0.1821999903768301,
      0.11590000940486789
    ],
    "steps": [
      [
        3.2691000087652355,
        {
          "event": "stepDone",
          "reply": 1000034,
          "result": {
            "latency_ms": 2.6976
          },
          "version": 1
        }
      ],
      [
        37.98599999572616,
        {
          "event": "stepDone",
          "reply": 1000035,
          "result": {
            "latency_ms": 37.7505
          },
          "version": 1
        }
      ],
      [
        211.36879999539815,
        {
          "event": "stepDone",
          "reply": 1000036,
          "result": {
            "latency_ms": 211.08599999999998
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      73.27920000534505,
      68.92760000482667,
      71.79850000829902,
      63.896600011503324,
      66.47879999945872
    ],
    "cached_preview_ms": [
      3.625199999078177,
      5.589699998381548,
      6.2215000070864335,
      4.848700002185069,
      5.21889999799896
    ],
    "last_state": {
      "decoder": "",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.666667,
      "version": 1
    }
  },
  {
    "cold_ms": 720.5763999954797
  },
  {
    "cold_ms": 720.1038999919547
  },
  {
    "cold_ms": 707.8197000082582
  },
  {
    "cold_ms": 698.1291999982204
  }
]
```

### Additional pair run: h264-bench-three

Errors: `[]`; full result: `h264-bench-three.json`.
```json
[
  {
    "cold_ms": 1128.5894000029657,
    "warm_ms": [
      41.75730000133626,
      34.16290000313893,
      41.80360000464134,
      40.91419999895152,
      41.609199994127266
    ],
    "seeks_ms": [
      31.896400003461167,
      175.51390000153333,
      79.69810000213329,
      60.9118000138551,
      33.13789999810979,
      185.8009999996284,
      203.53320000867825,
      32.64839999610558,
      32.905800006119534,
      167.4812999990536,
      155.67259999806993,
      63.95820000034291,
      118.18859999766573,
      38.03450000123121,
      116.89340000157245,
      211.50329998636153,
      171.2925999891013,
      187.34190000395756,
      220.78309999778867,
      138.16119999682996
    ],
    "steps": [
      [
        6.792300002416596,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 6.531000000000001
          },
          "version": 1
        }
      ],
      [
        50.42039998807013,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 50.1922
          },
          "version": 1
        }
      ],
      [
        65.26730000041425,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 64.9939
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      74.40389999828767,
      64.36590000521392,
      65.22240000776947,
      64.6612999989884,
      66.16519999806769
    ],
    "cached_preview_ms": [
      3.227799999876879,
      4.101400001673028,
      4.094099989742972,
      3.436999992118217,
      4.7224000009009615
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.6,
      "version": 1
    }
  },
  {
    "cold_ms": 723.1192999897758
  },
  {
    "cold_ms": 721.5589999977965
  },
  {
    "cold_ms": 752.2983999951975
  },
  {
    "cold_ms": 771.9100999966031
  }
]
```

### Additional pair run: hevc-final

Errors: `[]`; full result: `hevc-final.json`.
```json
[
  {
    "cold_ms": 892.2363000019686,
    "warm_ms": [
      41.60579999734182,
      33.33339998789597,
      33.30390001065098,
      33.34470000118017,
      33.32760000193957
    ],
    "seeks_ms": [
      23.031800010357983,
      80.47990000341088,
      125.30270000570454,
      90.9481999988202,
      16.628400000627153,
      117.99089999112766,
      132.29959999443963,
      16.624000010779127,
      31.493899994529784,
      93.24159999960102,
      47.19310000655241,
      93.29030000662897,
      185.5193999945186,
      64.5959999965271,
      171.25359999772627,
      170.5294999992475,
      65.87260001106188,
      115.15650000364985,
      179.5494999969378,
      16.644300005282275
    ],
    "steps": [
      [
        8.338800005731173,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 8.135
          },
          "version": 1
        }
      ],
      [
        25.910099997418,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 25.715
          },
          "version": 1
        }
      ],
      [
        109.54820000915788,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 109.2809
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      100.78040001098998,
      68.88909998815507,
      70.79309999244288,
      64.50839999888558,
      66.18840000010096
    ],
    "cached_preview_ms": [
      2.8962999931536615,
      2.9707999929087237,
      3.4967999963555485,
      2.8140999929746613,
      3.2377999887103215
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.566667,
      "version": 1
    }
  },
  {
    "cold_ms": 722.2958000056678
  },
  {
    "cold_ms": 720.0310999905923
  },
  {
    "cold_ms": 736.8590999976732
  },
  {
    "cold_ms": 712.8075000073295
  }
]
```

### Additional pair run: av1-final

Errors: `[]`; full result: `av1-final.json`.
```json
[
  {
    "cold_ms": 714.6548000018811,
    "warm_ms": [
      33.22850000404287,
      26.29950000846293,
      28.711199993267655,
      31.66649999911897,
      28.507499999250285
    ],
    "seeks_ms": [
      16.537800009245984,
      81.16570000129286,
      140.81219999934547,
      91.6923000040697,
      16.627300006803125,
      124.95559999661054,
      140.76520000526216,
      29.266400000778958,
      31.810999993467703,
      94.40869999525603,
      47.778100008144975,
      115.55889999726787,
      197.0005999901332,
      77.31910000438802,
      173.49309999553952,
      184.5173000037903,
      79.92750000266824,
      117.71009999210946,
      194.92399999580812,
      16.632700004265644
    ],
    "steps": [
      [
        1.0008999961428344,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 0.7419
          },
          "version": 1
        }
      ],
      [
        45.71320000104606,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 45.498999999999995
          },
          "version": 1
        }
      ],
      [
        118.97569999564439,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 118.70840000000001
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      79.68169999367092,
      67.92750000022352,
      71.14430000365246,
      67.48840000363998,
      67.95830000191927
    ],
    "cached_preview_ms": [
      2.5110999995376915,
      3.126299998257309,
      3.3924999879673123,
      2.896799996960908,
      3.1747000030009076
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.6,
      "version": 1
    }
  },
  {
    "cold_ms": 738.2533999916632
  },
  {
    "cold_ms": 709.6970999991754
  },
  {
    "cold_ms": 706.921400007559
  },
  {
    "cold_ms": 811.8441999977222
  }
]
```

### Additional pair run: vp9-final

Errors: `[]`; full result: `vp9-final.json`.
```json
[
  {
    "cold_ms": 727.1021000051405,
    "warm_ms": [
      42.61060000862926,
      33.31870000693016,
      33.283400000073016,
      33.317000008537434,
      33.343600007356144
    ],
    "seeks_ms": [
      78.39720000629313,
      32.87090000230819,
      75.69929999590386,
      62.660000010509975,
      61.8936999962898,
      63.16730000253301,
      17.176400011521764,
      63.41089999477845,
      59.65280000236817,
      63.90079999982845,
      62.63570000010077,
      78.0434000043897,
      32.222099995124154,
      43.81809999176767,
      32.29849999479484,
      48.27910001040436,
      47.73560000467114,
      46.51980000198819,
      16.610699996817857,
      45.71590000705328
    ],
    "steps": [
      [
        0.7985000120243058,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 0.5698
          },
          "version": 1
        }
      ],
      [
        44.480600001406856,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 44.2662
          },
          "version": 1
        }
      ],
      [
        33.69949999614619,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 33.43320000000001
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      69.2200000048615,
      61.793199987732805,
      54.606200006674044,
      59.94160000409465,
      57.08849999064114
    ],
    "cached_preview_ms": [
      8.967000001575798,
      3.9533000090159476,
      3.242899998440407,
      3.5604000004241243,
      3.2396000024164096
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.583333,
      "version": 1
    }
  },
  {
    "cold_ms": 721.4004999987083
  },
  {
    "cold_ms": 708.9867999893613
  },
  {
    "cold_ms": 699.9087000003783
  },
  {
    "cold_ms": 736.4783999946667
  }
]
```

### Additional pair run: rotation-final

Errors: `[]`; full result: `rotation-final.json`.
```json
[
  {
    "cold_ms": 735.9844999882625,
    "warm_ms": [
      41.59649999928661,
      37.240299992845394,
      42.69400000339374,
      40.72059999452904,
      41.80079999787267
    ],
    "seeks_ms": [
      32.04219999315683,
      96.72469999350142,
      46.83149998891167,
      44.790500003728084,
      32.146300000022165,
      117.43119999300689,
      117.32150000170805,
      31.895399995846674,
      32.50310001021717,
      113.79350000061095,
      85.3763000050094,
      46.20490000525024,
      64.5725000067614,
      33.04739999293815,
      61.36170000536367,
      124.38130000373349,
      92.8536000137683,
      117.26269999053329,
      131.37509999796748,
      79.06930000171997
    ],
    "steps": [
      [
        14.05460000387393,
        {
          "event": "stepDone",
          "reply": 1000028,
          "result": {
            "latency_ms": 13.5687
          },
          "version": 1
        }
      ],
      [
        48.34219999611378,
        {
          "event": "stepDone",
          "reply": 1000029,
          "result": {
            "latency_ms": 48.1655
          },
          "version": 1
        }
      ],
      [
        41.647699996246956,
        {
          "event": "stepDone",
          "reply": 1000030,
          "result": {
            "latency_ms": 41.3692
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      77.23420001275372,
      60.15520000073593,
      59.370100003434345,
      56.8630000052508,
      59.92530001094565
    ],
    "cached_preview_ms": [
      3.2479000074090436,
      3.554199996870011,
      3.378800000064075,
      3.4983000077772886,
      3.9244000072358176
    ],
    "last_state": {
      "decoder": "d3d11va",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.6,
      "version": 1
    }
  },
  {
    "cold_ms": 733.4301999944728
  },
  {
    "cold_ms": 733.4716000041226
  },
  {
    "cold_ms": 721.1648000084097
  },
  {
    "cold_ms": 726.0863999981666
  }
]
```

### Additional pair run: pair-release-final

Errors: `["RuntimeError('Helper reported playback error')"]`; full result: `pair-release-final.json`.
```json
[
  {
    "error": "RuntimeError('Helper reported playback error')"
  }
]
```

### Additional pair run: pair-release-corrected

Errors: `["RuntimeError('The player did not respond.')"]`; full result: `pair-release-corrected.json`.
```json
[
  {
    "cold_ms": 761.256300000241,
    "executable_sha256": "6d24bb5e85526f8ccff1f7d5abf4ad0954a214d0791614b323a46ae4efdfe54a",
    "warm_ms": [
      41.648599988548085,
      33.27429998898879,
      33.3595999982208,
      24.999500019475818,
      33.305699995253235
    ],
    "seeks_ms": [
      22.596499999053776,
      63.290500023867935,
      95.55689999251626,
      63.20969999069348,
      16.695300000719726,
      92.00430000782944,
      94.44070002064109,
      18.541799974627793,
      27.525599987711757,
      79.09830001881346,
      30.559000006178394,
      74.68160000280477,
      126.98970001656562,
      49.91650002193637,
      137.60139999794774,
      124.46829999680631,
      62.40840000100434,
      77.80659999116324,
      127.29300002683885,
      16.90940000116825
    ],
    "enable_pair_ms": 73.39080001111142,
    "divider_ack_ms": [
      0.16009999671950936,
      0.14289998216554523,
      0.13719999697059393,
      0.12549999519251287,
      0.13359999866224825
    ],
    "error": "RuntimeError('The player did not respond.')",
    "exit_code": 0,
    "remaining_child_pids": []
  }
]
```

### Additional pair run: pair-ordered-release

Errors: `["RuntimeError('The player did not respond.')"]`; full result: `pair-ordered-release.json`.
```json
[
  {
    "cold_ms": 983.7830000033136,
    "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba",
    "warm_ms": [
      41.64469998795539,
      33.31129997968674,
      33.29370002029464,
      33.345700008794665,
      33.31929998239502
    ],
    "seeks_ms": [
      20.78829999663867,
      69.92800001171418,
      94.438900006935,
      64.35780000174418,
      16.65599999250844,
      91.50830001453869,
      93.82280000136234,
      18.103100010193884,
      27.77580000110902,
      63.128800014965236,
      33.77340000588447,
      75.19460000912659,
      140.34859999082983,
      49.315899988869205,
      123.77229999401607,
      123.73249998199753,
      63.15190001623705,
      78.54529999895021,
      129.43430000450462,
      17.003199987811968
    ],
    "enable_pair_ms": 367.421100003412,
    "divider_ack_ms": [
      0.16540000797249377,
      0.13770000077784061,
      0.1331999956164509,
      0.13230001786723733,
      0.12740000966005027
    ],
    "error": "RuntimeError('The player did not respond.')",
    "exit_code": 0,
    "remaining_child_pids": []
  }
]
```

### Additional pair run: pair-ordered-720

Errors: `[]`; full result: `pair-ordered-720.json`.
```json
[
  {
    "cold_ms": 739.8931999923661,
    "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba",
    "warm_ms": [
      41.63909997441806,
      33.30819998518564,
      33.268699975451455,
      33.56290000374429,
      33.14820001833141
    ],
    "seeks_ms": [
      22.44770000106655,
      52.900000009685755,
      92.51679998124018,
      61.890500015579164,
      16.679399996064603,
      91.6406000033021,
      96.82740000425838,
      17.801000009058043,
      28.555500000948086,
      63.690599985420704,
      30.16419999767095,
      76.03029999881983,
      142.94140000129119,
      47.70949998055585,
      125.01600000541657,
      121.83980000554584,
      50.905700016301125,
      77.0098999782931,
      126.92810001317412,
      17.658299999311566
    ],
    "enable_pair_ms": 248.48319997545332,
    "divider_ack_ms": [
      0.31519998447038233,
      8.207400009268895,
      0.19240000983700156,
      0.12660000356845558,
      0.2693000133149326
    ],
    "steps": [
      [
        2.0560999982990324,
        {
          "event": "stepDone",
          "reply": 1000034,
          "result": {
            "latency_ms": 1.8276
          },
          "version": 1
        }
      ],
      [
        44.934799982002005,
        {
          "event": "stepDone",
          "reply": 1000035,
          "result": {
            "latency_ms": 44.7735
          },
          "version": 1
        }
      ],
      [
        223.22200000053272,
        {
          "event": "stepDone",
          "reply": 1000036,
          "result": {
            "latency_ms": 223.00539999999998
          },
          "version": 1
        }
      ]
    ],
    "new_preview_ms": [
      31.50340000865981,
      20.6639000098221,
      20.726799994008616,
      18.408200005069375,
      19.446699996478856
    ],
    "cached_preview_ms": [
      0.8546000171918422,
      1.2552000116556883,
      1.205699983984232,
      1.0063000081572682,
      1.0852999985218048
    ],
    "last_state": {
      "decoder": "",
      "dropped": "0",
      "duration": 65.0,
      "event": "state",
      "paused": true,
      "position": 60.716667,
      "version": 1
    },
    "exit_code": 0,
    "remaining_child_pids": []
  },
  {
    "cold_ms": 713.1405999825802,
    "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba",
    "exit_code": 0,
    "remaining_child_pids": []
  },
  {
    "cold_ms": 737.4010999919847,
    "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba",
    "exit_code": 0,
    "remaining_child_pids": []
  },
  {
    "cold_ms": 729.2929999821354,
    "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba",
    "exit_code": 0,
    "remaining_child_pids": []
  },
  {
    "cold_ms": 748.8355000095908,
    "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba",
    "exit_code": 0,
    "remaining_child_pids": []
  }
]
```

## Soak results

- `soak-30min-final`: 86 completed cycles (30-minute coverage recorded); errors `[]`; executable hashes `['not recorded']`.
  Sample maxima (bytes except handles): `{"open_private_max": 471879680, "open_handles_max": 3512, "open_dedicated_max": 186269696, "open_shared_max": 25202688, "after_play_private_max": 472715264, "after_play_handles_max": 3669, "after_play_dedicated_max": 187379712, "after_play_shared_max": 19476480}`.
- `release-soak-30min`: 86 completed cycles (30-minute coverage recorded); errors `[]`; executable hashes `['b0c02f8a9bd354f015a98bb2847458eddc5710ea0b5b8b14c6e750d29c48c6c3']`.
  Sample maxima (bytes except handles): `{"open_private_max": 471654400, "open_handles_max": 3519, "open_dedicated_max": 186249216, "open_shared_max": 24879104, "after_play_private_max": 474689536, "after_play_handles_max": 3680, "after_play_dedicated_max": 190009344, "after_play_shared_max": 19533824}`.
- `final-helper-soak`: 86 completed cycles (30-minute coverage recorded); errors `[]`; executable hashes `['6d24bb5e85526f8ccff1f7d5abf4ad0954a214d0791614b323a46ae4efdfe54a']`.
  Sample maxima (bytes except handles): `{"open_private_max": 469872640, "open_handles_max": 3520, "open_dedicated_max": 188932096, "open_shared_max": 26521600, "after_play_private_max": 472485888, "after_play_handles_max": 3682, "after_play_dedicated_max": 190115840, "after_play_shared_max": 18726912}`.
- `ordered-helper-soak`: 24 completed cycles (NOT a completed 30-minute run; interrupted or still in progress); errors `[]`; executable hashes `['99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba']`.
  Sample maxima (bytes except handles): `{"open_private_max": 467288064, "open_handles_max": 3516, "open_dedicated_max": 185982976, "open_shared_max": 23924736, "after_play_private_max": 475369472, "after_play_handles_max": 3731, "after_play_dedicated_max": 189054976, "after_play_shared_max": 18726912}`.
- `resumed-helper-soak`: 86 completed cycles (30-minute coverage recorded); errors `[]`; executable hashes `['99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba']`.
  Sample maxima (bytes except handles): `{"open_private_max": 467906560, "open_handles_max": 3518, "open_dedicated_max": 186056704, "open_shared_max": 25083904, "after_play_private_max": 471658496, "after_play_handles_max": 3704, "after_play_dedicated_max": 189001728, "after_play_shared_max": 18714624}`.

## Failed / superseded measurement inventory

Every retained JSON is listed with its errors and completed-run count. A successful earlier soak does not certify a subsequently changed helper.

- `av1-final.json`: 5 runs; errors `[]`.
- `av1-ordered.json`: 5 runs; errors `[]`.
- `final-helper-soak.json`: 86 runs; errors `[]`.
- `h264-bench-one.json`: 1 runs; errors `["RuntimeError('Helper reported playback error')", "RuntimeError('Helper exited 0')"]`.
- `h264-bench-three.json`: 5 runs; errors `[]`.
- `h264-bench-two.json`: 1 runs; errors `["PermissionError(13, 'The process cannot access the file because it is being used by another process')"]`.
- `h264-ordered.json`: 5 runs; errors `[]`.
- `hevc-final.json`: 5 runs; errors `[]`.
- `hevc-ordered.json`: 5 runs; errors `[]`.
- `ordered-helper-soak.json`: 24 runs; errors `[]`.
- `pair-final.json`: 5 runs; errors `[]`.
- `pair-ordered-720.json`: 5 runs; errors `[]`.
- `pair-ordered-release.json`: 1 runs; errors `["RuntimeError('The player did not respond.')"]`.
- `pair-release-corrected.json`: 1 runs; errors `["RuntimeError('The player did not respond.')"]`.
- `pair-release-final.json`: 1 runs; errors `["RuntimeError('Helper reported playback error')"]`.
- `release-soak-30min.json`: 86 runs; errors `[]`.
- `resumed-helper-soak.json`: 86 runs; errors `[]`.
- `rotation-final.json`: 5 runs; errors `[]`.
- `rotation-ordered-resumed.json`: 5 runs; errors `[]`.
- `soak-30min-final.json`: 86 runs; errors `[]`.
- `vp9-final.json`: 5 runs; errors `[]`.
- `vp9-ordered.json`: 5 runs; errors `[]`.

## Cleanup inventory (recorded before deletion)

Only cycle-created compiler metadata under the Cargo target and confirmed test/dependency/build artifacts are eligible. Executables, model/tool caches and the current package are preserved. Each exact metadata candidate and logical size follows; deletion results are appended separately.

| Path relative to work | Bytes |
| --- | ---: |
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
| `cache/tauri-target/debug/deps/libtao-18243a6a4c408c98.rmeta` | 3677692 |
| `cache/tauri-target/debug/deps/libtao-219e116e950b2410.rmeta` | 3670582 |
| `cache/tauri-target/debug/deps/libtao-b7ba331b53c191e3.rlib` | 7594128 |
| `cache/tauri-target/debug/deps/libtao-b7ba331b53c191e3.rmeta` | 4340105 |
| `cache/tauri-target/debug/deps/libtao-cdafe5e88c2e7a47.rlib` | 7603776 |
| `cache/tauri-target/debug/deps/libtao-cdafe5e88c2e7a47.rmeta` | 4353181 |
| `cache/tauri-target/debug/deps/libtauri-3915be4fddc8ab53.rlib` | 15967694 |
| `cache/tauri-target/debug/deps/libtauri-3915be4fddc8ab53.rmeta` | 7192534 |
| `cache/tauri-target/debug/deps/libtauri-b5b132ab5a51f501.rmeta` | 4646210 |
| `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-bb30f3589f6944cf.rmeta` | 39941 |
| `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-ecb0641924eaf533.rlib` | 72542 |
| `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-ecb0641924eaf533.rmeta` | 66832 |
| `cache/tauri-target/debug/deps/libtauri_runtime-4cacf81aa0b96cd0.rmeta` | 393976 |
| `cache/tauri-target/debug/deps/libtauri_runtime-d79b62fe80341cf0.rlib` | 665684 |
| `cache/tauri-target/debug/deps/libtauri_runtime-d79b62fe80341cf0.rmeta` | 540695 |
| `cache/tauri-target/debug/deps/libtauri_runtime_wry-5cc538b24ffd1419.rlib` | 2651990 |
| `cache/tauri-target/debug/deps/libtauri_runtime_wry-5cc538b24ffd1419.rmeta` | 1965350 |
| `cache/tauri-target/debug/deps/libtauri_runtime_wry-ecd6c804f96809f6.rmeta` | 1545059 |
| `cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rlib` | 32268 |
| `cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rmeta` | 31224 |
| `cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rlib` | 356970 |
| `cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rmeta` | 314228 |
| `cache/tauri-target/debug/deps/libtinystr-9c819ba187e7ac7d.rmeta` | 258492 |
| `cache/tauri-target/debug/deps/liburl-3d042123386f1d5a.rmeta` | 297701 |
| `cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rlib` | 1332532 |
| `cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rmeta` | 369846 |
| `cache/tauri-target/debug/deps/libVideoEnhancer-980883247dc4735b.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer-ae93b56b28a85809.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-129b7aa23743a2d4.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-258e89d060c74d6e.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-574e045a60361f97.rlib` | 2019196 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-574e045a60361f97.rmeta` | 374150 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-5ccb80a815c1716f.rmeta` | 130751 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-834c6b4cb2117f6a.rlib` | 2019196 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-834c6b4cb2117f6a.rmeta` | 374150 |
| `cache/tauri-target/debug/deps/libVideoEnhancer_Player-8c47b424786ddb19.rmeta` | 0 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-8e68a18c94e84779.rlib` | 2018490 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-8e68a18c94e84779.rmeta` | 374198 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-8fa7cf094003bf65.rmeta` | 130751 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-e54de1e4ae1043ab.rmeta` | 129884 |
| `cache/tauri-target/debug/deps/libvideoenhancer_player-ec28d61016664bce.rmeta` | 129944 |
| `cache/tauri-target/debug/deps/libwebview2_com-28d6f8afb9e78498.rlib` | 10148222 |
| `cache/tauri-target/debug/deps/libwebview2_com-28d6f8afb9e78498.rmeta` | 1976493 |
| `cache/tauri-target/debug/deps/libwebview2_com-b74c5e584bc5f4fe.rlib` | 10142804 |
| `cache/tauri-target/debug/deps/libwebview2_com-b74c5e584bc5f4fe.rmeta` | 1976493 |
| `cache/tauri-target/debug/deps/libwebview2_com-d99e6bf1b3c402e6.rmeta` | 1538420 |
| `cache/tauri-target/debug/deps/libwebview2_com-fb1878c37b54ce0b.rmeta` | 1538420 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-078edee1cd8f9108.rmeta` | 4924081 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-5c42e150abc044a8.rlib` | 20333774 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-5c42e150abc044a8.rmeta` | 6432627 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-bcb41dd7fcc5dc37.rmeta` | 4924081 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-d31602443fffcef7.rlib` | 20333774 |
| `cache/tauri-target/debug/deps/libwebview2_com_sys-d31602443fffcef7.rmeta` | 6432627 |
| `cache/tauri-target/debug/deps/libwindows-10b74a9ac671a4f6.rlib` | 117969478 |
| `cache/tauri-target/debug/deps/libwindows-10b74a9ac671a4f6.rmeta` | 96269917 |
| `cache/tauri-target/debug/deps/libwindows-5e843205393cdda5.rlib` | 117969480 |
| `cache/tauri-target/debug/deps/libwindows-5e843205393cdda5.rmeta` | 96269917 |
| `cache/tauri-target/debug/deps/libwindows-9896c8c6e905bf89.rmeta` | 76620269 |
| `cache/tauri-target/debug/deps/libwindows-dc20d237a0d4be95.rmeta` | 76620269 |
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
| `cache/tauri-target/debug/deps/libwry-e5cb0f4100670583.rlib` | 3205642 |
| `cache/tauri-target/debug/deps/libwry-e5cb0f4100670583.rmeta` | 1900303 |
| `cache/tauri-target/debug/deps/libwry-eb2e463c43a37f0e.rmeta` | 1657760 |
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
| `cache/tauri-target/release/deps/libtao-a5f6ad5bba0e7c37.rlib` | 5620642 |
| `cache/tauri-target/release/deps/libtao-a5f6ad5bba0e7c37.rmeta` | 4766880 |
| `cache/tauri-target/release/deps/libtao-e9e221a665d18e7d.rlib` | 5605958 |
| `cache/tauri-target/release/deps/libtao-e9e221a665d18e7d.rmeta` | 4752116 |
| `cache/tauri-target/release/deps/libtauri-1d39701f0a9abafb.rlib` | 12008442 |
| `cache/tauri-target/release/deps/libtauri-1d39701f0a9abafb.rmeta` | 9092726 |
| `cache/tauri-target/release/deps/libtauri_plugin_single_instance-1914a668d4274426.rlib` | 111494 |
| `cache/tauri-target/release/deps/libtauri_plugin_single_instance-1914a668d4274426.rmeta` | 102989 |
| `cache/tauri-target/release/deps/libtauri_runtime-d5240f98e374ec38.rlib` | 674482 |
| `cache/tauri-target/release/deps/libtauri_runtime-d5240f98e374ec38.rmeta` | 628622 |
| `cache/tauri-target/release/deps/libtauri_runtime_wry-16eea66cff55e9a4.rlib` | 2562304 |
| `cache/tauri-target/release/deps/libtauri_runtime_wry-16eea66cff55e9a4.rmeta` | 2262611 |
| `cache/tauri-target/release/deps/libthiserror-c3d1b6c3d1d4606a.rlib` | 32272 |
| `cache/tauri-target/release/deps/libthiserror-c3d1b6c3d1d4606a.rmeta` | 31228 |
| `cache/tauri-target/release/deps/libtinystr-ae0d10cfb311f63e.rlib` | 361190 |
| `cache/tauri-target/release/deps/libtinystr-ae0d10cfb311f63e.rmeta` | 355315 |
| `cache/tauri-target/release/deps/liburl-84679487a2fc9e0f.rlib` | 758090 |
| `cache/tauri-target/release/deps/liburl-84679487a2fc9e0f.rmeta` | 419744 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-06cba4d5752ba2bd.rlib` | 1185948 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-06cba4d5752ba2bd.rmeta` | 462305 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-5fa6d0a4e43966c4.rlib` | 1184524 |
| `cache/tauri-target/release/deps/libvideoenhancer_player-5fa6d0a4e43966c4.rmeta` | 462305 |
| `cache/tauri-target/release/deps/libwebview2_com-6f66bd1415490225.rlib` | 3831228 |
| `cache/tauri-target/release/deps/libwebview2_com-6f66bd1415490225.rmeta` | 2479871 |
| `cache/tauri-target/release/deps/libwebview2_com-fc8affbdbc590f64.rlib` | 3831272 |
| `cache/tauri-target/release/deps/libwebview2_com-fc8affbdbc590f64.rmeta` | 2479871 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-262a3a5d14a454e7.rlib` | 19214048 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-262a3a5d14a454e7.rmeta` | 7865095 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-fadd49560fc7e534.rlib` | 19214076 |
| `cache/tauri-target/release/deps/libwebview2_com_sys-fadd49560fc7e534.rmeta` | 7865095 |
| `cache/tauri-target/release/deps/libwindows-49b43d93c935f391.rlib` | 119158296 |
| `cache/tauri-target/release/deps/libwindows-49b43d93c935f391.rmeta` | 112702843 |
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
| `cache/tauri-target/release/deps/libwry-196b886b6d15a8ea.rlib` | 2350822 |
| `cache/tauri-target/release/deps/libwry-196b886b6d15a8ea.rmeta` | 2048411 |
| `cache/tauri-target/release/deps/libyoke-64fae51615e04096.rlib` | 264710 |
| `cache/tauri-target/release/deps/libyoke-64fae51615e04096.rmeta` | 260980 |
| `cache/tauri-target/release/deps/libzerofrom-b9a189f78ade812d.rlib` | 85176 |
| `cache/tauri-target/release/deps/libzerofrom-b9a189f78ade812d.rmeta` | 81964 |
| `cache/tauri-target/release/deps/libzerotrie-502a9c1ffd14593b.rlib` | 518156 |
| `cache/tauri-target/release/deps/libzerotrie-502a9c1ffd14593b.rmeta` | 491798 |
| `cache/tauri-target/release/deps/libzerovec-935b60deb1cd5ab4.rlib` | 1359420 |
| `cache/tauri-target/release/deps/libzerovec-935b60deb1cd5ab4.rmeta` | 1351244 |

### Additional cleanup inventory: final-artifact-cleanup

- `repo/gui/node_modules`: 191885734 bytes.
- `repo/gui/dist`: 596635 bytes.
- `repo/gui/test-results`: 45 bytes.
- `evidence/VE-P1e-3a`: 23727004 bytes.

### Additional cleanup inventory: scratch-completed

- `scratch/p1e3c2-compare`: 1743304200 bytes.
- `scratch/p1e3c2-cpu`: 0 bytes.
- `scratch/p1e3c2-e2e`: 111722900 bytes.
- `scratch/p1e3c2-e2e-shell`: 18417221 bytes.
- `scratch/p1e3c2-final-fallback`: 149525217 bytes.
- `scratch/p1e3c2-full-e2e`: 440226219 bytes.
- `scratch/p1e3c2-pytest`: 0 bytes.

### Additional cleanup inventory: python-cache

- `repo/src/videoenhancer/__pycache__`: 54595 bytes.
- `repo/src/videoenhancer/estimate/__pycache__`: 53295 bytes.
- `repo/src/videoenhancer/jobs/__pycache__`: 65901 bytes.
- `repo/src/videoenhancer/media/__pycache__`: 61782 bytes.
- `repo/src/videoenhancer/models/__pycache__`: 36235 bytes.
- `repo/src/videoenhancer/pipeline/__pycache__`: 5522 bytes.
- `repo/src/videoenhancer/schedule/__pycache__`: 111281 bytes.
- `repo/src/videoenhancer/service/__pycache__`: 393003 bytes.

### Additional cleanup inventory: resume-artifact

- `repo/gui/node_modules`: 191885699 bytes.
- `repo/gui/dist`: 596635 bytes.
- `scratch/p1e3c2-resume-bin`: 59758164 bytes.
- `scratch/p1e3c2-resume-e2e`: 703539276 bytes.
- `scratch/p1e3c2-service-diagnostic`: 0 bytes.
- `scratch/http_diagnostic.py`: 518 bytes.
- `scratch/p1e3c2-native/h264-bench-one-0`: 9644637 bytes.
- `scratch/p1e3c2-native/native-escalated`: 9771809 bytes.
- `scratch/p1e3c2-native/native-second`: 14281561 bytes.
- `scratch/p1e3c2-native/native-visual-final`: 73335303 bytes.
- `scratch/p1e3c2-native/ordered-helper-soak-24`: 9959075 bytes.
- `scratch/p1e3c2-native/profile-first`: 14313981 bytes.
- `scratch/p1e3c2-native/rotation-ordered-0`: 10001035 bytes.

### Additional cleanup inventory: resume-cache

- `cache/tauri-target/debug/deps/libbase64-ce9221534c8e2940.rlib`: 514904 bytes.
- `cache/tauri-target/debug/deps/libbase64-ce9221534c8e2940.rmeta`: 316633 bytes.
- `cache/tauri-target/debug/deps/libbase64-e4bd84f82c2d00ce.rmeta`: 227964 bytes.
- `cache/tauri-target/debug/deps/libbitflags-c924b9d8f5646d59.rmeta`: 177062 bytes.
- `cache/tauri-target/debug/deps/libdpi-5891117ef91dfd5e.rlib`: 219100 bytes.
- `cache/tauri-target/debug/deps/libdpi-5891117ef91dfd5e.rmeta`: 212136 bytes.
- `cache/tauri-target/debug/deps/libdpi-80b4cb7d03aba5f0.rmeta`: 133183 bytes.
- `cache/tauri-target/debug/deps/libform_urlencoded-f62264ffb245d8e6.rmeta`: 27557 bytes.
- `cache/tauri-target/debug/deps/libicu_collections-57b1ccf9f2539686.rlib`: 1036710 bytes.
- `cache/tauri-target/debug/deps/libicu_collections-57b1ccf9f2539686.rmeta`: 426785 bytes.
- `cache/tauri-target/debug/deps/libicu_collections-c659028211346ca3.rmeta`: 302574 bytes.
- `cache/tauri-target/debug/deps/libicu_locale_core-4a73333febbd5b05.rmeta`: 1381655 bytes.
- `cache/tauri-target/debug/deps/libicu_locale_core-9387890bfbfa04df.rlib`: 3021936 bytes.
- `cache/tauri-target/debug/deps/libicu_locale_core-9387890bfbfa04df.rmeta`: 1595439 bytes.
- `cache/tauri-target/debug/deps/libicu_normalizer-17e49cc0c46d58dc.rmeta`: 441239 bytes.
- `cache/tauri-target/debug/deps/libicu_normalizer-51bf13c2f97eed32.rlib`: 1569318 bytes.
- `cache/tauri-target/debug/deps/libicu_normalizer-51bf13c2f97eed32.rmeta`: 591267 bytes.
- `cache/tauri-target/debug/deps/libicu_properties-38e2d7a6f5930ec6.rmeta`: 2529117 bytes.
- `cache/tauri-target/debug/deps/libicu_properties-9e652eb186237a8a.rlib`: 4570336 bytes.
- `cache/tauri-target/debug/deps/libicu_properties-9e652eb186237a8a.rmeta`: 2735852 bytes.
- `cache/tauri-target/debug/deps/libicu_provider-87073197e85ce684.rmeta`: 358184 bytes.
- `cache/tauri-target/debug/deps/libicu_provider-b0eb8d818759cc1a.rlib`: 616290 bytes.
- `cache/tauri-target/debug/deps/libicu_provider-b0eb8d818759cc1a.rmeta`: 429679 bytes.
- `cache/tauri-target/debug/deps/libidna-1f235341bf6ccafa.rlib`: 1475884 bytes.
- `cache/tauri-target/debug/deps/libidna-1f235341bf6ccafa.rmeta`: 243759 bytes.
- `cache/tauri-target/debug/deps/libidna-a75f4d46d36f3972.rmeta`: 144084 bytes.
- `cache/tauri-target/debug/deps/libidna_adapter-46caf4958679e9e6.rlib`: 77246 bytes.
- `cache/tauri-target/debug/deps/libidna_adapter-46caf4958679e9e6.rmeta`: 32762 bytes.
- `cache/tauri-target/debug/deps/libidna_adapter-b790960b4ab5c135.rmeta`: 27917 bytes.
- `cache/tauri-target/debug/deps/liblibloading-21999e3592b7817a.rlib`: 283154 bytes.
- `cache/tauri-target/debug/deps/liblibloading-21999e3592b7817a.rmeta`: 145144 bytes.
- `cache/tauri-target/debug/deps/liblibloading-3936d0badfbb8987.rmeta`: 115826 bytes.
- `cache/tauri-target/debug/deps/libmemchr-38089049b4a132d8.rmeta`: 992923 bytes.
- `cache/tauri-target/debug/deps/libmemchr-44c5c68c2f6ac0c5.rlib`: 1776330 bytes.
- `cache/tauri-target/debug/deps/libmemchr-44c5c68c2f6ac0c5.rmeta`: 1311848 bytes.
- `cache/tauri-target/debug/deps/libparking_lot-ae4416f7d9de723d.rmeta`: 158387 bytes.
- `cache/tauri-target/debug/deps/libparking_lot_core-f9ed022dcf65a17c.rmeta`: 114802 bytes.
- `cache/tauri-target/debug/deps/libpercent_encoding-08cacb3d06cba4a6.rmeta`: 45711 bytes.
- `cache/tauri-target/debug/deps/libpng-045f1465d88b15fc.rmeta`: 744028 bytes.
- `cache/tauri-target/debug/deps/libpotential_utf-1c20a29bc1163643.rmeta`: 38524 bytes.
- `cache/tauri-target/debug/deps/libpotential_utf-d41965670bbbacf3.rlib`: 91972 bytes.
- `cache/tauri-target/debug/deps/libpotential_utf-d41965670bbbacf3.rmeta`: 45094 bytes.
- `cache/tauri-target/debug/deps/libproc_macro2-5b42f80bac7bc596.rlib`: 1379190 bytes.
- `cache/tauri-target/debug/deps/libproc_macro2-5b42f80bac7bc596.rmeta`: 351847 bytes.
- `cache/tauri-target/debug/deps/libquote-ed63e26db6dec0b6.rlib`: 567456 bytes.
- `cache/tauri-target/debug/deps/libquote-ed63e26db6dec0b6.rmeta`: 275893 bytes.
- `cache/tauri-target/debug/deps/libserde-378d07342e0e486d.rmeta`: 526379 bytes.
- `cache/tauri-target/debug/deps/libserde-d173d3439c6d2dc5.rlib`: 994036 bytes.
- `cache/tauri-target/debug/deps/libserde-d173d3439c6d2dc5.rmeta`: 842612 bytes.
- `cache/tauri-target/debug/deps/libserde_core-e12ff28eead84497.rlib`: 5060452 bytes.
- `cache/tauri-target/debug/deps/libserde_core-e12ff28eead84497.rmeta`: 4849747 bytes.
- `cache/tauri-target/debug/deps/libserde_core-f76f9a2a3e98b891.rmeta`: 2726536 bytes.
- `cache/tauri-target/debug/deps/libserde_json-367ad46f7538a188.rlib`: 2626924 bytes.
- `cache/tauri-target/debug/deps/libserde_json-367ad46f7538a188.rmeta`: 1455007 bytes.
- `cache/tauri-target/debug/deps/libserde_json-fe370f977207fe0d.rmeta`: 966682 bytes.
- `cache/tauri-target/debug/deps/libsmallvec-2ea9b1b53a0d3a97.rmeta`: 114305 bytes.
- `cache/tauri-target/debug/deps/libsyn-8a3c0f1b68c20174.rlib`: 10205954 bytes.
- `cache/tauri-target/debug/deps/libsyn-8a3c0f1b68c20174.rmeta`: 2810158 bytes.
- `cache/tauri-target/debug/deps/libsyn-e12850ffbe1f9970.rlib`: 8867340 bytes.
- `cache/tauri-target/debug/deps/libsyn-e12850ffbe1f9970.rmeta`: 3412031 bytes.
- `cache/tauri-target/debug/deps/libsynstructure-3eb5c573a8db6951.rlib`: 1246894 bytes.
- `cache/tauri-target/debug/deps/libsynstructure-3eb5c573a8db6951.rmeta`: 229720 bytes.
- `cache/tauri-target/debug/deps/libtao-18243a6a4c408c98.rmeta`: 3677692 bytes.
- `cache/tauri-target/debug/deps/libtao-219e116e950b2410.rmeta`: 3670582 bytes.
- `cache/tauri-target/debug/deps/libtao-b7ba331b53c191e3.rlib`: 7594128 bytes.
- `cache/tauri-target/debug/deps/libtao-b7ba331b53c191e3.rmeta`: 4340105 bytes.
- `cache/tauri-target/debug/deps/libtao-cdafe5e88c2e7a47.rlib`: 7603776 bytes.
- `cache/tauri-target/debug/deps/libtao-cdafe5e88c2e7a47.rmeta`: 4353181 bytes.
- `cache/tauri-target/debug/deps/libtauri-3915be4fddc8ab53.rlib`: 15967694 bytes.
- `cache/tauri-target/debug/deps/libtauri-3915be4fddc8ab53.rmeta`: 7192534 bytes.
- `cache/tauri-target/debug/deps/libtauri-b5b132ab5a51f501.rmeta`: 4646210 bytes.
- `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-bb30f3589f6944cf.rmeta`: 39941 bytes.
- `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-ecb0641924eaf533.rlib`: 72542 bytes.
- `cache/tauri-target/debug/deps/libtauri_plugin_single_instance-ecb0641924eaf533.rmeta`: 66832 bytes.
- `cache/tauri-target/debug/deps/libtauri_runtime-4cacf81aa0b96cd0.rmeta`: 393976 bytes.
- `cache/tauri-target/debug/deps/libtauri_runtime-d79b62fe80341cf0.rlib`: 665684 bytes.
- `cache/tauri-target/debug/deps/libtauri_runtime-d79b62fe80341cf0.rmeta`: 540695 bytes.
- `cache/tauri-target/debug/deps/libtauri_runtime_wry-5cc538b24ffd1419.rlib`: 2651990 bytes.
- `cache/tauri-target/debug/deps/libtauri_runtime_wry-5cc538b24ffd1419.rmeta`: 1965350 bytes.
- `cache/tauri-target/debug/deps/libtauri_runtime_wry-ecd6c804f96809f6.rmeta`: 1545059 bytes.
- `cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rlib`: 32268 bytes.
- `cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rmeta`: 31224 bytes.
- `cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rlib`: 356970 bytes.
- `cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rmeta`: 314228 bytes.
- `cache/tauri-target/debug/deps/libtinystr-9c819ba187e7ac7d.rmeta`: 258492 bytes.
- `cache/tauri-target/debug/deps/liburl-3d042123386f1d5a.rmeta`: 297701 bytes.
- `cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rlib`: 1332532 bytes.
- `cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rmeta`: 369846 bytes.
- `cache/tauri-target/debug/deps/libVideoEnhancer-ae93b56b28a85809.rmeta`: 0 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-574e045a60361f97.rlib`: 2019196 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-574e045a60361f97.rmeta`: 374150 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-834c6b4cb2117f6a.rlib`: 2019196 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-834c6b4cb2117f6a.rmeta`: 374150 bytes.
- `cache/tauri-target/debug/deps/libVideoEnhancer_Player-8c47b424786ddb19.rmeta`: 0 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-8e68a18c94e84779.rlib`: 2018490 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-8e68a18c94e84779.rmeta`: 374198 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-8fa7cf094003bf65.rmeta`: 130751 bytes.
- `cache/tauri-target/debug/deps/libvideoenhancer_player-ec28d61016664bce.rmeta`: 130751 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com-28d6f8afb9e78498.rlib`: 10148222 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com-28d6f8afb9e78498.rmeta`: 1976493 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com-b74c5e584bc5f4fe.rlib`: 10142804 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com-b74c5e584bc5f4fe.rmeta`: 1976493 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com-d99e6bf1b3c402e6.rmeta`: 1538420 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com-fb1878c37b54ce0b.rmeta`: 1538420 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com_sys-078edee1cd8f9108.rmeta`: 4924081 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com_sys-5c42e150abc044a8.rlib`: 20333774 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com_sys-5c42e150abc044a8.rmeta`: 6432627 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com_sys-bcb41dd7fcc5dc37.rmeta`: 4924081 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com_sys-d31602443fffcef7.rlib`: 20333774 bytes.
- `cache/tauri-target/debug/deps/libwebview2_com_sys-d31602443fffcef7.rmeta`: 6432627 bytes.
- `cache/tauri-target/debug/deps/libwindows-10b74a9ac671a4f6.rlib`: 117969478 bytes.
- `cache/tauri-target/debug/deps/libwindows-10b74a9ac671a4f6.rmeta`: 96269917 bytes.
- `cache/tauri-target/debug/deps/libwindows-5e843205393cdda5.rlib`: 117969480 bytes.
- `cache/tauri-target/debug/deps/libwindows-5e843205393cdda5.rmeta`: 96269917 bytes.
- `cache/tauri-target/debug/deps/libwindows-9896c8c6e905bf89.rmeta`: 76620269 bytes.
- `cache/tauri-target/debug/deps/libwindows-dc20d237a0d4be95.rmeta`: 76620269 bytes.
- `cache/tauri-target/debug/deps/libwindows_collections-16e61cd397ede7b6.rlib`: 535676 bytes.
- `cache/tauri-target/debug/deps/libwindows_collections-16e61cd397ede7b6.rmeta`: 534573 bytes.
- `cache/tauri-target/debug/deps/libwindows_collections-f6bf775e70b9e531.rmeta`: 328770 bytes.
- `cache/tauri-target/debug/deps/libwindows_core-a6fd93327c3eebf8.rmeta`: 544067 bytes.
- `cache/tauri-target/debug/deps/libwindows_core-d8b0e8288046add1.rlib`: 949900 bytes.
- `cache/tauri-target/debug/deps/libwindows_core-d8b0e8288046add1.rmeta`: 638400 bytes.
- `cache/tauri-target/debug/deps/libwindows_future-51be2519e37fe6bb.rlib`: 1105168 bytes.
- `cache/tauri-target/debug/deps/libwindows_future-51be2519e37fe6bb.rmeta`: 757036 bytes.
- `cache/tauri-target/debug/deps/libwindows_future-d5b3e9f8b4ec6796.rmeta`: 482503 bytes.
- `cache/tauri-target/debug/deps/libwindows_numerics-52d223e6577cd14c.rmeta`: 97591 bytes.
- `cache/tauri-target/debug/deps/libwindows_numerics-dc5a2af46e21e0b7.rlib`: 212080 bytes.
- `cache/tauri-target/debug/deps/libwindows_numerics-dc5a2af46e21e0b7.rmeta`: 112934 bytes.
- `cache/tauri-target/debug/deps/libwry-e5cb0f4100670583.rlib`: 3205642 bytes.
- `cache/tauri-target/debug/deps/libwry-e5cb0f4100670583.rmeta`: 1900303 bytes.
- `cache/tauri-target/debug/deps/libwry-eb2e463c43a37f0e.rmeta`: 1657760 bytes.
- `cache/tauri-target/debug/deps/libyoke-5598d26e8733f6ea.rlib`: 242478 bytes.
- `cache/tauri-target/debug/deps/libyoke-5598d26e8733f6ea.rmeta`: 240740 bytes.
- `cache/tauri-target/debug/deps/libyoke-9fdfce34d1aff53f.rmeta`: 192042 bytes.
- `cache/tauri-target/debug/deps/libzerofrom-5765f9eb8d92511e.rlib`: 97034 bytes.
- `cache/tauri-target/debug/deps/libzerofrom-5765f9eb8d92511e.rmeta`: 95994 bytes.
- `cache/tauri-target/debug/deps/libzerofrom-f3ecd5c88c7bb243.rmeta`: 53717 bytes.
- `cache/tauri-target/debug/deps/libzerotrie-b76ea17d16878913.rmeta`: 354065 bytes.
- `cache/tauri-target/debug/deps/libzerotrie-e3a3b0d50f0096d7.rlib`: 541260 bytes.
- `cache/tauri-target/debug/deps/libzerotrie-e3a3b0d50f0096d7.rmeta`: 454842 bytes.
- `cache/tauri-target/debug/deps/libzerovec-27d3ee8e39225a94.rlib`: 1174686 bytes.
- `cache/tauri-target/debug/deps/libzerovec-27d3ee8e39225a94.rmeta`: 1114657 bytes.
- `cache/tauri-target/debug/deps/libzerovec-e70d1292a9e90e43.rmeta`: 839587 bytes.

### Additional cleanup inventory: final-scratch

- `scratch/p1e3c2-native/av1-10bit-1440p60.mp4`: 43981710 bytes.
- `scratch/p1e3c2-native/h264-1080p30.mp4`: 24977143 bytes.
- `scratch/p1e3c2-native/hevc-main10-1440p60.mp4`: 42657322 bytes.
- `scratch/p1e3c2-native/hevc-rotation-display.mp4`: 25331635 bytes.
- `scratch/p1e3c2-native/hevc-rotation.mp4`: 25331635 bytes.
- `scratch/p1e3c2-native/pair-enhanced.mp4`: 18682190 bytes.
- `scratch/p1e3c2-native/pair-original.mp4`: 8307602 bytes.
- `scratch/p1e3c2-native/vp9-1080p60.mp4`: 25052752 bytes.
- `scratch/p1e3c2-resume-pytest`: 0 bytes.
- `scratch/p1e3c2-resume-pytest-two`: 0 bytes.
- `scratch/tmp`: 10913785 bytes.
- `scratch/videoenhancer.jsonl`: 9258 bytes.
- `scratch/write-cycle-report.py`: 28383 bytes.

`cache-cleanup-result.json`: removed 1517940326 bytes; failures [].

`final-artifact-cleanup-result.json`: removed 216209418 bytes; failures [].

`scratch-completed-result.json`: removed 2463195757 bytes; failures [].

`python-cache-result.json`: removed 781614 bytes; failures [].

`resume-artifact-result.json`: removed 1097087693 bytes; failures [].

`resume-cache-result.json`: removed 849116243 bytes; failures [].

`final-scratch-result.json`: removed 225273415 bytes; failures [].

## Final resumed verification details

The resumed checks used final unchanged source: ruff check/format (181 files), pyright (zero diagnostics), ESLint, tsc, Vite, 77 GUI tests, one payload test, Rust fmt/clippy including test-faults, 28 main and four helper tests, and fresh e2e builds. Full Windows e2e: 25 passed / 14 skipped; focused native and fallback: five passed. All commands completed with exit 0 except the explicitly retained first resumed CPU suite failure. The second full CPU suite passed 669 / 24 skipped / 101 deselected in 426.61 seconds.

First tile in the Compare table is the Original first-look tile. A model still and its complete playable clip are distinct milestones:

| Run | C1 first look, s | C1 complete preview ready, s |
| --- | ---: | ---: |
| compare-before-idle-three | 22.163 | 51.543 |
| compare-before-busy | 20.924 | 53.485 |
| compare-after-idle | 21.860 | 51.224 |
| compare-after-busy | 51.730 | 80.696 |

The main-app +5% memory gate was measured on the paired 720p History fixture only, not separately on every codec. Exact burned-in stepping and orientation/pixel correctness for each fixture remain NOT_RUN. Software reload timings do not pass the production warm cross-job requirement. PDH null means unavailable; observed GPU sums omit those readings and are not total device VRAM.

Resumed actual History memory (bytes):

| Metric | Before | Ten seconds after close |
| --- | ---: | ---: |
| main_private | 6373376 | 6488064 |
| main_tree_private | 288313344 | 272990208 |
| dedicated | 58642432 | 54587392 |
| shared | 8409088 | 6914048 |

All four sampled +5% comparisons passed; no helper or libmpv module in main after close, sampling errors empty.

Final soak completion: `{"exit_code": 0, "requested_seconds": 1800, "completed_cycles": 86, "errors": [], "remaining_children": [], "executable_sha256": "99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba", "sample_coverage_seconds": 1811.7961881000083}`.

## For the owner to delete

- `work/scratch/p1e3c2-native/h264-bench-two-0`: the earlier sharing-violation refusal. It was excluded from every later deletion, including parent deletion. Its final logical size is recorded in the disk table. No retry or bypass was attempted.

## Final disk table and growth gate (decimal GB)

Logical file lengths are reported, not allocated disk usage. Rows overlap and must not be added indiscriminately.

| Item | Start / baseline | End |
| --- | ---: | ---: |
| C free | 351.569604608 | 351.467888640 |
| D free | 979.385880576 | 978.965467136 |
| Cache after dependency restore | 9.069388152 | 9.458114172 |
| All evidence | 0.133499573 | 0.147755050 |
| Current package, preserved | 0.005764162 | 0.005764162 |
| All package files including sources | 0.005764162 | 0.125182083 |
| New native candidate | 0.000000000 | 0.048207241 |
| This cycle evidence | 0.000000000 | 0.038024040 |
| Scratch | 0.001416976 | 0.000001712 |

Persistent-growth conservative upper bound: **0.547972942 GB**, PASS ?1 GB. It counts cache delta, package delta, this entire cycle's evidence, all changed source files at gross length (804,961 bytes, not merely their net additions), plus a 1 MB reserve for final report/evidence additions. It does not subtract the old evidence removed. Baseline Python dependencies were reused with no installation; restored GUI dependencies were removed after validation. Cache is below 40 GB, cycle evidence below 300 MB, D free above 200 GB. These logical-file calculations are separate from drive-wide free-space changes.

Initial offline GUI restore was 191,884,396 bytes; cleanup measured 191,885,734 bytes including generated cache. The resumed restore/cleanup measured 191,885,699 bytes. Both cleanup rounds are independently recorded; they are not simultaneous retained dependency growth. Only VE-P1e-3b, VE-P1e-3c1 and VE-P1e-3c2 evidence remain; the prior P1e-3a report remains in Git at aa107af.

Scratch contains only `p1e3c2-native/h264-bench-two-0`, **1,712 bytes**, from the earlier sharing-violation refusal. It was never retried or included in a parent deletion. All other cleanup candidates succeeded, as recorded per item above. The original current package remains unchanged at 5,764,162 bytes; the final candidate is 48,207,241 bytes; the adjacent source archive/manifest/checksums total 71,210,680 bytes.

Final read-only Git diff check: PASS, with only LF/CRLF conversion warnings. Branch/HEAD unchanged from start. Exact Changed files: 60, verified against final status including untracked files. No commit, push, merge, fetch or Git mutation. GUI dependencies, dist, test output and generated Python caches were removed from the checkout after checks; baseline ignored local-env.ps1 and Python environment were preserved. No new source changes followed the final checks.

### Minimal reproduction commands

Run in a normal Windows shell from work/repo, using isolated scratch homes provided by local-env.ps1:

```powershell
. .\local-env.ps1
.venv\Scripts\python.exe -m pytest -m "not gpu and not soak" --basetemp=..\scratch\review-cpu -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/test_service.py::test_cpu_queue_sse_controls_and_completed_output --basetemp=..\scratch\review-service -p no:cacheprovider
```

The one HTTP 400 has not been reproduced or explained. Do not treat the later passing run as proof that this intermittent issue was fixed. Final Windows/Ubuntu CI, production-main package smoke while the owner app is closed, physical device/DPI/sleep checks and visual acceptance remain pending.

Final candidate executable SHA-256:

- `VideoEnhancer.exe`: `584392662e2de9dcb784ebfc5eda97eeb7b67ed07835906e4c8007f373f04518`
- `VideoEnhancer-Player.exe`: `99c8bb554f1628a8306397b1dc3bf61442c9109f03de0e7f4bc72c720c03c7ba`
