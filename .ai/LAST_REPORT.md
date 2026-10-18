# VE-P1f revision 3 implementation and validation

- Task ID / Cycle: VE-P1f, revision 3.
- Status: PARTIAL (work in progress).
- Branch p1f-links starts at reviewed P1t cb085bc. No owner data is test data.
- Complete designer instructions are preserved in CURRENT_TASK.md.
- P1t cold-start, warm-History, AV1 and repeat-memory failures remain historical FAIL; M1 1 MiB and Low memory target stay. HEVC remains the default.

| Part | Status | Evidence |
| --- | --- | --- |
| P | PARTIAL | P1 implemented and locally checked. P2 measured; warm History PASS, cold start FAIL. P3 measured; P4 source cleanup complete. Cold gate remains FAIL. |
| T | PARTIAL | Verified optional tool manager implemented. Stable installation and version execution PASS; remaining lifecycle/GUI integration checks follow. |
| R | PARTIAL | Admission, legacy queue and default migration implemented; new size and mixed-batch tests PASS. Regression checks follow. |
| L | PARTIAL | Link checking, selection, downloads, durable network queue and UI implemented; acceptance continues. |
| M | NOT RUN | Deferred by designer. |
| G | PARTIAL | Local media and GUI checks running; Archive real job PASS, Commons VP9 processing FAIL under review. |

## Start and constraints

Git tree was clean at cb085bc; fetched p1t-tauri, created p1f-links, saved the complete attachment and committed it as 1be11c5. Scratch was empty at cycle start. The existing Electron package was retained for P2. All test homes use work/scratch. The protected owner AppData and VE-check directories are not test data.

## P1 implementation and local validation

- Storage Move, verification and Remove share an RAII busy guard. Both buttons disable during either mutation. Status polling is serialized and cheap; full checks occur on opening Storage, after Move and inside Remove.
- Confirmation excludes protected, damaged-manifest and currently inaccessible entries. Locked, changed and protected files remain in the pointer manifest with reason counts; the pointer is read again before writing. The legacy pointer explanation is explicit.
- Run-key sync skips debug/e2e builds and unchanged values. External links pass a normalized parsed URL. HEAD reports full file size; capped GET without Range uses 206 with its explicit Content-Range.
- A CDP-only feature permits release CI inspection without compiling desktop_test. The owner build still has no diagnostic features.
- Changed files: Rust storage/media/window/commands/main and Cargo features; Storage.tsx, desktop.ts, types.ts; GUI storage-card, packaged and storage-restart tests; Windows CI; performance fixture first-health timestamp.

| Check | Actual result | Evidence under work/evidence/P1f |
| --- | --- | --- |
| Rust formatting, default and e2e clippy | PASS | p1-clippy.log, p1-clippy-e2e.log |
| Rust unit tests | PASS, 18 tests | p1-rust-tests2.log |
| GUI typecheck and lint | PASS after correcting unsupported test matchers | p1-typecheck2.log, p1-lint2.log |
| GUI unit suite | PASS, 50 tests / 11 files | p1-gui-unit.log |
| GUI production build | PASS; existing bundle-size warning | p1-gui-build.log |
| Debug e2e build | PASS | p1-debug-build2.log |
| Storage restart GUI | Initial FAIL due to test arming confirmation before cancellation completed; serialized test rerun PASS, 24.9 s | p1-storage-e2e.log, p1-storage-e2e2.log |
| Release CDP build | PASS, 69 s | p1-release-build2.log |
| Release packaged isolation, engine lifecycle, absent desktop_test | PASS, 5.7 s | p1-release-check.log |

GUI storage checks cover cancellation, relaunch on the moved home, live log changes, History removal, retained old changed files, failed probe and damaged core records. All use isolated synthetic homes. Final CI and final package are NOT RUN yet.

## P2 measurements

Same P1t G1 Node fixture with 1000 History records, alternating Electron/Tauri independent launches. This uses a prestarted fixture engine, not a cold Python service. Warm History is the exact switching sequence at CSS 1280x800, measured from click to two animation frames. Cold phases use five launches each; warm History uses ten. Window creation uses WinEvent/GetTickCount (OS clock granularity applies). Browser versions recorded by CDP: Electron 44.7.0 / Chromium 152.0.7977.130; WebView2 155.0.4283.62.

Final qualified run (p2-phases-run4.json/log), medians in ms:

| Phase | Electron | Tauri |
| --- | ---: | ---: |
| Process start from launch anchor | 4.849 | 1.525 |
| Window created | 118.684 | 27.677 |
| Webview ready (DOMContentLoaded) | 219.178 | 508.759 |
| First paint | 606.438 | 695.759 |
| Fixture engine healthy | 298.578 | 575.059 |
| G1 Home data plus two frames | 420.876 | 694.613 |
| Warm History | 64.150 | 64.400 |

- Warm History: PASS against 100 ms. No current Tauri-specific over-budget result. Historical P1t 134.65 ms remains FAIL.
- Cold G1: FAIL, 694.613 > 462.964 ms (Electron x 1.1). First paint separately also fails 695.759 > 667.081 ms; first paint can occur after G1 Home readiness, and is not substituted for it.
- Median window-to-navigation interval: Electron 16.772 ms, Tauri 297.604 ms. Navigation-to-DCL: 84.400 / 183.800 ms. DCL-to-fixture-health: 77.500 / 64.900 ms. WebView2 initialization dominates the difference (inference from intervals). No explicit removable wait was found; no runtime architecture change made.
- Every run retained: run1 used hidden launch, lacked first-paint observations and repeated History within a single instance (diagnostic only; cold 431.917/718.279 ms, FAIL). Run2 used 1100x700 after DPI clamping (not qualified for the 1280 fixture). The viewport probe validated 1280x800 only, not a timing gate. Run3 qualified History (64.150/64.750 ms, PASS) and cold G1 (418.419/695.260 ms, FAIL), but its paint observation followed harness controls. Run4 observes paint before controls and is the final qualified phase table. All raw observations, executable hashes and recipe versions are retained; no failed run discarded.

## P3 progress

FFmpeg generated H.264 and AV1 1440p fixtures directly from synthetic 1080p input, without the enhancement pipeline. File sizes: 2,032,330,077 and 2,032,855,414 bytes. Exact commands/probe data: p3-media-recipe.json. Dedicated GPU allocation uses PDH per PID and process role at 1 s, with separate device-wide nvidia-smi used/free values. Missing counter instances are null, not measured zero. P3 is measurement only; no memory fix or new acceptance gate is introduced.

| Playback run | Shell/WebView known dedicated MB before (10 s mean) | 2 min sampled peak MB | Closed 30 s MB | Closed 5 min MB |
| --- | ---: | ---: | ---: | ---: |
| H.264 | 36.88 | 151.57 | 116.70 | 116.69 |
| AV1 | 36.87 | 156.95 | 122.09 | 122.08 |
| AV1 job-comparison repeat | 37.34 | 158.63 | 130.29 | 130.29 |

Observed shell/WebView dedicated allocations are held by the WebView2 gpu-process.
Other shell/renderer/browser/utility PIDs had no PDH dedicated-memory instance;
they are unobserved, not asserted zero. Python engine and worker descendants are
sampled separately and retained alongside every row. Device-wide readings include
other applications and are not added to the per-process allocations. Every PID,
role, nearest 30/300 s sample, device value and collection interval is retained in
p3-{h264,av1,fresh,post-play}-gpu.jsonl and p3-summary.json. No sampling access
errors were recorded in the completed playback runs.

The GPU comparison uses the same 30-frame 720x1280 synthetic input, Standard,
1080p, 2x, HEVC; the same isolated model home and frozen engine sources (84 file
hashes in p3-source-hashes.json). Fresh app/engine first, restart, AV1 playback
for 2 min and close for 5 min, then the second job with no player open:

| Run | Device free immediately before submit (MiB) | Submit-to-done s | Recorded job took s | Segment actual s | Segment stats fps |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fresh app | 7097 | 23.681 | 21.579 | 21.071 | 1.603 |
| After AV1 playback | 7256 | 22.596 | 20.678 | 20.114 | 1.695 |

Both jobs completed. These are one pair, not medians or proof of a causal speed
effect. Driver/kernel/cache state and device-wide activity may differ. No source
above 1080 and no output above 1440 was processed. The initial fresh-job attempt
FAILED because the measurement service lacked a Windows multiprocessing main
guard, causing a child to re-enter the service lock. The helper was corrected;
that log, failed manifest, samples and result remain as *-attempt1 files. The
successful pair uses a fresh scratch home (p3-comparison2); no failed run erased.

## Questions for the designer

T6 HTTPS downgrade and L2 direct-file metadata were raised with concrete loopback
evidence. Both were resolved by the designer on 2026-10-18; full decisions are
appended to CURRENT_TASK.md. No proxy or yt-dlp plugin is added. The selected
metadata URLs must not expose HTTP under an HTTPS input; transfer redirects use
yt-dlp defaults. Missing dimensions use the specified bounded header probe and
then the explicit download-first fallback. No open question on these points.

## T and R progress

- Optional standalone tool manager and Settings > Video links: manual release
  checks only, release versions/dates/sizes/licences, exact-plan consent, stable
  and nightly channels, checked SHA-256, determinate transfer progress/ETA,
  cancellation and scoped uninstall. No yt-dlp Python dependency was added.
- Verified stable installation in scratch: yt-dlp 2026.08.19, 17840399 bytes,
  SHA-256 66674953fe251b89f4d08c5f0e35e0728679bd67ab3d7d05c0562af101dd3e7a;
  Deno 2.9.7 ZIP 42630221 bytes, SHA-256
  a0c3101b4158d1dfb7d6a78a7bf0f3de80c96bb423c152beec8beb22786f2238.
  Both installed binaries were verified again before --version execution.
- Official Windows Deno checksums use PowerShell Get-FileHash text; parsing
  verifies its SHA256 label and exact archive basename. GNU checksum lists are
  also supported. Missing/ambiguous hashes, bad digests, altered executables,
  stale consent plans and archive path traversal are refused.
- Official latest releases checked: yt-dlp stable 2026.08.19, nightly
  2026.10.10.233141 and Deno 2.9.7. Documented minimum Deno 2.3.0 verified in
  https://github.com/yt-dlp/yt-dlp/wiki/EJS#deno. Installed yt-dlp format sorting
  was checked with local metadata only: res:1080 selects 1920x1080 and
  1080x1920 correctly (t-installed-res.json). No forbidden site accessed.
- T unit installer/security suite: PASS, 11 tests, 0.27 s. GUI manual-network and
  consent checks: PASS, 2 tests. Subsequent combined T/R suite: 23 PASS, 2.59 s.
  New source files: service/link_tools.py, gui/src/VideoLinks.tsx and their tests.
- R enforces the displayed short-side cap before analysis, engine admission,
  Compare and segment execution. Legacy unsupported work keeps its chosen
  settings, never runs, and exposes the reason plus Remove. Finished manifests
  are preserved. Saved default 2160 becomes 1440 with a log; HEVC is unchanged.
- UI/CLI choices remove 2160. The old Fast-only 4K branch is removed. Historical
  2160 calibration entries are deleted, not relabelled as measured 1440 data;
  future calibration uses the allowed 1440 geometry. The built-in profile now
  claims only its remaining measured output range.
- R new tests: 12 PASS. First run had 1 FAIL / 11 PASS because the fixture's old
  FFmpeg rotate metadata option did not create rotation on FFmpeg 9.0.2. Using
  the existing suite's -display_rotation input option fixed the fixture; rerun
  PASS. Mixed Add and tool GUI subset: 17 PASS across 2 files, 4.62 s.
- T6 reproduction: verified official yt-dlp followed HTTPS 302 to HTTP on
  loopback and returned success. A self-signed TLS exception was used only by
  that probe. Production never disables certificate checks. Evidence:
  t-redirect-probe.json/log and t-probe-tool-verification.json.

## P4 and cleanup progress

Electron source, dependencies, dedicated unit tests and comparative shell scripts
are removed after P2. Historical recipe copies remain outside Git under
evidence/P1f/recipes/p1t-comparison. Packaging now calls package-tauri.mjs; docs
describe Tauri, and legacy pointer migration remains intact. P4 GUI typecheck,
lint and all remaining 45 unit tests PASS (p4-typecheck/lint/unit.log).

Cleanup candidates inventoried before deletion (logical file lengths):

| Exact development path | Bytes | Reason |
| --- | ---: | --- |
| D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-win32-x64 | 428412636 | P2 complete; obsolete Electron package |
| D:\my-workspace\VideoEnhancer\work\cache\electron | 0 | Empty historical shell download cache |

The single cleanup command was rejected before execution by automatic approval
review (blocked by policy). No bytes removed. Do not retry or bypass the refusal.
No owner folder is included.

## For the owner to delete

- D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-win32-x64 (428412636 bytes).
- D:\my-workspace\VideoEnhancer\work\cache\electron (empty; 0 bytes).


## L and acceptance progress (2026-10-18)

- Full L3 audio decision is appended to CURRENT_TASK.md. No mux whitelist or
  link-specific audio rule was changed. Downloaded originals use copy/remux.
  Final MP4 audio rules remain:

| Input audio codec | Final MP4 audio |
| --- | --- |
| AAC, MP3, AC-3, E-AC-3, ALAC | Stream copy |
| Opus and every other codec | AAC 256 kbps |

- l-audio-container-probe.json/log retain the earlier successful AAC/Opus packet
  hash copy experiment. It does not change the chosen compatibility rule.
- Link processing uses verified executables, argument arrays, ignore-config,
  no plugins, bounded header probes and tree cancellation. Private metadata is
  kept in the engine home; renderer cards do not receive arbitrary command args.
- Durable downloading jobs have a separate pool capped at 1-3 (default 2), pause
  and restart recovery, byte progress, readiness estimates, three retries after
  the initial attempt and normal admission after the completed download.
- Add supports URL checks, playlist selection, disabled HDR choices, reuse and
  first-download folder selection. Home shows downloading progress; Settings
  controls the folder/tools/limit. History's source command takes a job ID only.
- Targeted Python T/R/link tests: 44 PASS in 5.10 s; network pool pause/recovery
  tests: 3 PASS in 6.78 s; planner readiness: 9 PASS in 4.69 s. Pyright: 0 errors.
- GUI typecheck/lint/build and 49 unit tests PASS (7.97 s). Build warns that its
  minified JS is 543.50 kB, above Vite's 500 kB warning threshold.
- Rust: 19 PASS in 0.04 s, including normalized source URL and quote rejection.
- Real standalone downloader local MP4/HLS/DASH tests: 3 PASS in 22.27 s,
  including completed admission and unchanged-file reuse for MP4. MP4/DASH
  video and audio packet hashes match their served originals.
- Local playlist(3), 403, live, HDR and rotated portrait checks: 5 PASS in 13.26 s.
  Earlier failures are preserved: HLS duration 0.4 s generated an invalid zero
  target-duration fixture; DASH segments were initially emitted in the wrong
  working directory; sign-in test regex had the wrong case; HDR at file end
  without Range hid transfer metadata. Fixtures corrected, not product gates.
- GUI CDP acceptance: 1 PASS in 8.3 s for both sizes/themes, link cards, playlist,
  Home downloading and Settings. This uses synthetic UI metadata. Screenshots:
  work/evidence/P1f/gui/links-{home,playlist,quality,settings}-{dark,light}-{1280,1100}.png.
  A final refreshed build/screenshot pass follows recent minor fixes.
- Full CPU run: 501 PASS, 1 FAIL, 4 SKIP, 101 deselected, 729.70 s. The failure
  was test_p1d's invalid Keep+Standard 96x64 fixture. Changed only that fixture
  to 512x288; targeted rerun PASS in 1.96 s. Final CI reruns the full suite.
- Tool lifecycle PASS: Stable check, Nightly 2026.10.10.233141 update, version
  execution and uninstall in isolated home. Nightly exe 17842237 bytes, SHA-256
  e7cafc44db8aa433da8dd78303b9157f2c1dd509c4cbfcd8418081b7e1d26a7a.
  Deno 2.9.7 remains verified. t-update-uninstall.json/log contain all values.
- Real network uses only allowed Commons/Archive. Archive CC0 9sec test video
  (640x360, 9.74 s) completed Fast, 1080p, 2x, HEVC. Commons 320x240 VP9 download
  completed but GPU processing failed at the last frame. Initial attempts with
  an incorrect fixture VE_HOME failed to locate weights; retained as attempt1.
  Corrected environment and retried the same jobs; no re-download needed.
- Commons diagnostic: 131 NVDEC frames have PTS [0,0,33,67,...,4300] ms; analysed
  PTS are [0,33,67,100,...,4333] ms. The installed PyNvVideoCodec 2.2.3 also lacks
  Flush() despite public docs describing it. Its demuxer supplies a zero-length
  EOF packet. No timestamp correction or decoder switch was added. Designer
  question pending; g3-real-jobs.json/log and g3-vp9-timestamps.log retain FAIL.
- G5 GPU suite is running in scratch/P1f/gpu-suite2 with isolated model home.
  Sources/output sizes were statically checked: no forbidden size is executed.
  An earlier collection/start was interrupted before any completed result was
  recorded; it is not a PASS.

### Remaining decisions and rejected test

- Generic extractor IDs may be only a basename. Safe default: reuse additionally
  requires the same stored source URL for generic; other extractors use ID.
  Designer decision pending; a different URL is downloaded normally.
- The requested 1440p direct-file fixture generation was rejected before any
  execution by automatic approval review, citing the prior no-source-above-1080
  instruction. It was removed from the executable test parameters. That real
  fixture is NOT RUN; metadata-only oversized rejection tests remain PASS.
  Do not retry or bypass the rejected generation without resolving the conflict.
- Final e2e, package, D2, remaining G1 checks, GPU results, disk cleanup and final
  Windows/Ubuntu CI are still pending. No final success claim, commit or push.


## Latest completed checks

| Check | Actual | Result / evidence |
| --- | --- | --- |
| Link acceptance (real local tools plus units) | 55 tests, 98.30 s | PASS; g1-link-acceptance.log |
| Server disconnect and Range retry | 1 test, 13.53 s | PASS; g1-server-disconnect.log |
| No-Range stalled tail-header fallback and post-download probe | 1 test, 48.69 s | PASS; g1-header-fallback2.log |
| Trusted local TLS redirect to HTTP | 1 test, 2.07 s | PASS; g1-https-redirect2.log |
| D2 plus current size boundaries | 25 tests, 4.51 s | PASS; g6-d2-sizes.log |
| Rust default/e2e clippy | Both, -D warnings | PASS |
| Release command isolation | 1 test, 5.7 s | PASS; g6-release-isolation.log |
| GUI E2E full default selection | 14 PASS, 13 SKIP, 2.2 min | g6-gui-e2e.log |
| GUI units current | 49 tests, 7.74 s | PASS; g6-gui-unit.log |
| Python static checks | Ruff, format (140 files), Pyright 0 errors | PASS |
| Feature-free package | 1 min 17 s release compile | PASS; g6-package.log |
| Feature-free normal startup | Healthy external engine, expected isolated home, no remote-debugging arg | PASS; g6-featurefree-smoke2.json/log |

The initial feature-free smoke deliberately supplied WebView2's external debug
argument and incorrectly expected the SDK to ignore it. That expectation FAILED;
the SDK honors the explicit environment setting independently of our Cargo
feature. No shipping behavior was changed to satisfy that experiment. The normal
smoke removes that test-only argument and verifies actual default child args.

The current package is work/package/VideoEnhancer. Latest compiled executable
hash before the last label-only update is recorded in g6-featurefree-smoke.json;
the final package will be refreshed after the remaining checks. Node reports
DEP0190 for npm.cmd's fixed shell invocation during packaging; no user URL or
media metadata is passed through that shell. yt-dlp and ffprobe always use argv.

The 13 GUI skips are opt-in fixture/physical-owner flows. The legacy 2160 speed
calibration test is specifically NOT RUN (designer decision). Media memory and
historical P1t timing gates are not relabelled by these GUI results.

### L1 browser link drop

Tauri 2.12.4 webview_window.rs:1096 states that Windows HTML5 drag/drop requires
disabling its native drop handler. The app retains dragDropEnabled=true for its
existing native file drop; that notification contains paths, not browser text.
Paste and Home Ctrl+V are implemented. Browser text/uri-list drop is BLOCKED on
this documented conflict, not claimed as a physical PASS. Designer question
pending; no native URL-drop implementation or disabling of file drop was chosen.


## Candidate validation checkpoint

- Latest GUI units: 51 PASS, 7.71 s. First-folder selection and cancellation are
  verified; cancelling creates no link job and saves no implicit folder.
- The selected-format server check now retains a header-probe transport refusal,
  so a renderer cannot request a disabled format ID to bypass it. HTTP best-audio
  under an HTTPS source is also disabled before queueing. Both regressions PASS.
- Automatic backoff: initial attempt plus 3 retries, measured delays at least
  1/2/4 s, then failed with Retry available: PASS, 12.18 s.
- Refreshed link GUI screenshots PASS in 8.5 s under evidence/P1f/gui-links-final,
  at actual 1280x800 and 1100x700 CSS screenshot dimensions, both themes.
- The 1440p actual direct-file fixture remains NOT RUN after auto-review refusal;
  approval was requested explicitly, naming the conflicting prior size rule and
  the latest L2b requirement. Only a two-frame CPU fixture/header test is proposed.
- Current GPU run and final CI remain pending. This commit is a draft checkpoint,
  not completion of the requested implementation/verification cycle.

## Reproduction commands

From work/repo, dot-source local-env.ps1 before commands. All VE_HOME and GUI
profiles must be isolated under scratch; never use owner AppData or VE-check.

1. `.venv/Scripts/python.exe -m ruff check .`, `-m ruff format --check .`,
   and `-m pyright`.
2. `.venv/Scripts/python.exe -m pytest -m "not gpu and not soak"` with a fresh
   scratch basetemp. D2: `tests/test_p1d2.py`; new sizes: `tests/test_p1f_sizes.py`.
3. Run `scripts/prepare_link_test_tools.py <scratch home>` explicitly to install
   verified tools, then set VE_LINK_TEST_TOOLS_HOME to that home and run
   `tests/test_link_download.py`. Media requests use localhost only. TLS uses
   OpenSSL-generated fixture certificates, or explicit VE_LINK_TEST_TLS_CERT/KEY.
4. Set VE_HOME to an isolated verified-model fixture and VE_GPU_TEST_MODEL_HOME
   to cache/gpu-home, then pytest `-m "gpu and not soak"`; never opt into the
   legacy 2160 GUI calibration test.
5. In gui: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
   Build `gui/src-tauri/Cargo.toml --features e2e`; run `npm run test:e2e` with
   VE_TAURI_EXE and VE_GUI_TEST_ROOT under scratch. Release command isolation
   uses a release/cdp build without e2e and tests/e2e/packaged.spec.ts.
6. Set VE_TAURI_PACKAGE_OUT to work/package/VideoEnhancer and `npm run package`
   from gui. The shipping package uses no e2e/cdp Cargo features.
7. Real-network recipes, source metadata, hashes and diagnostic failures are
   outside Git in evidence/P1f/recipes and g3-*.json/log. The source Commons file
   is https://commons.wikimedia.org/wiki/File:320x240.ogv (public domain); Archive
   is https://archive.org/details/2026-02-16-public-short-video (CC0).

## Changed files at candidate checkpoint

```text
.ai/CURRENT_TASK.md
.ai/LAST_REPORT.md
.github/workflows/ci.yml
docs/API.md
docs/DEVELOPMENT.md
docs/GUI.md
docs/TROUBLESHOOTING.md
docs/WORKSPACE.md
gui/electron/icon.png
gui/electron/main.cjs
gui/electron/permissions.cjs
gui/electron/preload.cjs
gui/electron/python.cjs
gui/electron/storage.cjs
gui/eslint.config.mjs
gui/package-lock.json
gui/package.json
gui/scripts/desktop-baseline.mjs
gui/scripts/dev.mjs
gui/scripts/media-matrix.mjs
gui/scripts/media-service.py
gui/scripts/package.mjs
gui/scripts/summarize-media-followup.mjs
gui/scripts/summarize-media-matrix.mjs
gui/src-tauri/Cargo.toml
gui/src-tauri/src/commands.rs
gui/src-tauri/src/main.rs
gui/src-tauri/src/media.rs
gui/src-tauri/src/storage.rs
gui/src-tauri/src/window.rs
gui/src/App.tsx
gui/src/HistoryDetail.tsx
gui/src/Home.tsx
gui/src/LinkPanel.tsx
gui/src/Pages.tsx
gui/src/Queue.tsx
gui/src/Storage.tsx
gui/src/VideoLinks.tsx
gui/src/desktop.ts
gui/src/types.ts
gui/tests/add-models.test.tsx
gui/tests/e2e/desktop.spec.ts
gui/tests/e2e/gpu.spec.ts
gui/tests/e2e/links.spec.ts
gui/tests/e2e/media.spec.ts
gui/tests/e2e/packaged.spec.ts
gui/tests/e2e/resume.spec.ts
gui/tests/e2e/storage-restart.spec.ts
gui/tests/link-panel.test.tsx
gui/tests/perf/fake-engine.cjs
gui/tests/permissions.test.tsx
gui/tests/python.test.tsx
gui/tests/storage-card.test.tsx
gui/tests/storage.test.tsx
gui/tests/video-links.test.tsx
scripts/prepare_link_test_tools.py
src/videoenhancer/bench/reference.py
src/videoenhancer/bench/runner.py
src/videoenhancer/cli.py
src/videoenhancer/estimate/classes.py
src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json
src/videoenhancer/jobs/checks.py
src/videoenhancer/jobs/store.py
src/videoenhancer/pipeline/runner.py
src/videoenhancer/schedule/controller.py
src/videoenhancer/schedule/planner.py
src/videoenhancer/service/compare.py
src/videoenhancer/service/engine.py
src/videoenhancer/service/link_jobs.py
src/videoenhancer/service/link_tools.py
src/videoenhancer/service/server.py
src/videoenhancer/service/settings.py
src/videoenhancer/service/video_links.py
src/videoenhancer/trial.py
tests/test_bench.py
tests/test_estimate.py
tests/test_link_download.py
tests/test_link_jobs.py
tests/test_link_tools.py
tests/test_p1d.py
tests/test_p1e.py
tests/test_p1e2.py
tests/test_p1f_sizes.py
tests/test_planner.py
tests/test_video_links.py
```
