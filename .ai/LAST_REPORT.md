# VE-P1f revision 3 implementation and validation

- Task ID / Cycle: VE-P1f, revision 3.
- Status: PARTIAL (implementation/local acceptance complete; P2 cold-start gate FAIL).
- Branch p1f-links starts at reviewed P1t cb085bc. No owner data is test data.
- Complete designer instructions are preserved in CURRENT_TASK.md.
- Earlier checkpoint sections retain interim statuses; the final results below supersede their pending statements.
- P1t cold-start, warm-History, AV1 and repeat-memory failures remain historical FAIL; M1 1 MiB and Low memory target stay. HEVC remains the default.

| Part | Status | Evidence |
| --- | --- | --- |
| P | PARTIAL | P1 implemented and locally checked. P2 measured; warm History PASS, cold start FAIL. P3 measured; P4 source cleanup complete. Cold gate remains FAIL. |
| T | COMPLETED | Verified stable/nightly install, check, update, uninstall and local tool integrations PASS. |
| R | COMPLETED | Source/output limits, legacy queue guard, migration, mixed batch and refusal tests PASS. |
| L | COMPLETED | Link queue/reuse, strict decoder selection and approved refusal acceptance PASS. |
| M | NOT RUN | Deferred by designer. |
| G | PARTIAL | CPU 532 PASS/17 SKIP; GPU 101 PASS; links 54 PASS; GUI 52 units and 14 E2E PASS/13 SKIP. Final new-head CI pending. |

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

None after the owner's explicit retry authorization: the old Electron package
and empty Electron cache were successfully removed with the other listed artifacts.

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

### Superseded design checkpoint

Generic reuse and the oversized direct-file test initially awaited designer
instructions. The first fixture generation was refused before execution under
the old source limit. The later explicit approval and PASS are recorded below.

## Additional completed checks

| Check | Actual | Result / evidence |
| --- | --- | --- |
| D2 plus size boundaries | 25 tests, 4.51 s | PASS; g6-d2-sizes.log |
| Rust default/e2e clippy | Both, -D warnings | PASS |
| Release command isolation | 1 test, 5.7 s | PASS; g6-release-isolation.log |

Latest full link, GUI, static and package results are recorded below. Earlier
successful repeats remain in g1-link-acceptance.log, g6-gui-e2e.log and
g6-package.log; no measured P2/P3 gate or failed attempt was removed.

An initial smoke FAILED because it explicitly set the SDK debugging argument
while expecting no debugging. The SDK honors that override; the corrected
normal startup smoke removes it and passes. No shipping behavior changed.

The current package is work/package/VideoEnhancer. Latest compiled executable
hash before the last label-only update is recorded in g6-featurefree-smoke.json;
the final package will be refreshed after the remaining checks. Node reports
DEP0190 for npm.cmd's fixed shell invocation during packaging; no user URL or
media metadata is passed through that shell. yt-dlp and ffprobe always use argv.

The 13 GUI skips are opt-in fixture/physical-owner flows. The legacy 2160 speed
calibration test is specifically NOT RUN (designer decision). Media memory and
historical P1t timing gates are not relabelled by these GUI results.

### L1 browser link drop (resolved by designer)

Tauri 2.12.4 webview_window.rs:1096 states that Windows HTML5 drag/drop requires
disabling its native drop handler. The app retains dragDropEnabled=true for its
existing native file drop; that notification contains paths, not browser text.
Paste and Home Ctrl+V are implemented. Browser link drop was removed by the
designer (revision 2), not a failure. Native file drop stays enabled. The inert
DOM URL handlers were removed; no native URL-drop or COM handling was added.


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


## Candidate CI correction

Push CI 39103967329 on 1c41f38: Ubuntu CPU tests had 509 PASS, 1 FAIL, 16 SKIP,
101 deselected in 349.22 s. The failure was the new real HTTPS redirect fixture
running against Ubuntu's FFmpeg 6.1.1, which returned the generic header fallback
rather than the Windows 9.0.2 whitelist refusal. The real transport integration
is now Windows-only, matching the product and standalone downloader target.
Portable URL, whitelist arguments and refusal-propagation unit tests still run
on both platforms. This does not change application behavior or relabel that
failed run. Local Windows real TLS remains PASS. Evidence:
ci-39103967329-ubuntu.log and g1-https-redirect2.log. Older Linux FFmpeg behavior
is not evidence of the Windows package's refusal gate.

Published draft PR: https://github.com/Kei-Takamizawa/VideoEnhancer/pull/7,
base p1t-tauri. Candidate 1c41f3886489ceb9a901ffcfaf3440266d78eb18 was pushed and
verified by ls-remote. This is still the same unfinished P1f cycle.
Final feature-free package startup PASS; executable SHA-256
b9bc65eea6a326706789af9393760006d847701675cb557ec9a13e298bd407f0.

Verified standalone test tools are cached once after use. Move inventory: D:\my-workspace\VideoEnhancer\work\scratch\P1f\verified-test-tools -> D:\my-workspace\VideoEnhancer\work\cache\link-tools\yt-2026.08.19-66674953-deno-2.9.7-e020f3e2; 115303731 logical bytes. Both resolved paths are inside development work. No bytes are deleted and no owner installation is changed. The recipe records the full published hashes in t-stable-installed.json and t-update-uninstall.json.


## G4 visual QA correction

The first screenshot script wrote the root theme directly, which could be reset
by the app's actual preference. Functional assertions passed, but visual QA found
that a dark-named screenshot was light: G4 theme evidence was not accepted.
The corrected test selects Theme through Settings, waits for Saved, asserts the
actual root theme, and separately captures a single-card quality picker and the
three-entry playlist. Its first rerun timed out because getByLabel exact-match
was wrong; trace/context are retained as g4-theme-timeout-* outside Git. Correct
accessible-role targeting then PASSed in 10.8 s; dark output was visually checked.
One diagnostic before-image is retained as g4-theme-race-before.png. Final images
are evidence/P1f/gui-links-final/links-{home,quality,playlist,settings}-
{dark,light}-{1280,1100}.png. Only the final set is acceptance evidence.

Visual QA found and fixed the stale local-file Preparing label in link-only Add;
the checked card keeps its current processing estimate.


The NVIDIA public reference describes Flush, while the installed 2.2.3 binding
has no such method. Reference for the designer:
https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-reference/decoder.html
That checkpoint predates the approved decoder fix below. The original failure
remains recorded; the current implementation selects FFmpeg without changing PTS.


## Designer decisions and decoder acceptance, 2026-10-18

The four complete decisions are appended to CURRENT_TASK.md. No pending design
question remains from the previous checkpoint. Browser link drop is removed by
the designer (revision 2). Paste, Home Ctrl+V and native file drop remain.

- Generic reuse now normalizes scheme/host case and drops the fragment only;
  path/query remain exact. It checks known pre-download dimensions and duration
  (0.5 s tolerance), and Last-Modified when both timestamps exist. Completed
  downloads save source.timestamp. Site extractors use extractor_key plus id.
  Unknown-size generic links offer no reuse. The offer includes date, resolution
  and fps, with Download again. Known limit: a file replaced at the same link
  with the same resolution/duration and unchanged Last-Modified is still offered.
- Strict native decoding validates every label, including frames before a seek
  target. Whole-file analysis uses the same CreateDemuxer/CreateDecoder/Decode
  calls, including the demuxer's empty EOF packet and Flush only when available.
  A mismatch selects FFmpeg for the job; samples move to CUDA before the same
  nv12_to_rgb conversion. Models remain CUDA. Decoder/reason are persisted and
  included in Copy details. Runtime mismatch switches the job and retries that
  segment once; a second failure is not retried. No timestamp is corrected.

| Check | Expected | Actual / evidence |
| --- | --- | --- |
| H.264 converted frames | Maximum difference 0 | PASS, all 292 Archive frames, maximum 0; l3-h264-converted-equality.json/log. PSNR infinite (JSON null for exact equality). |
| Commons VP9 | Fast 1080p completes, 131 output frames | PASS, FFmpeg selected at repeated stamp 0 on frame 1; 131 HEVC frames, 1440x1080, 30 fps, 7.684 s controller wall time; l3-decoder-acceptance.json/log. |
| Commons pictures | Compare every native/FFmpeg frame hash | PASS, 131/131 SHA-256 hashes identical at corresponding ordinals. Labels are shifted; pictures are neither repeated nor missing in this file. Both decode the final picture. |
| Archive H.264 | Keep NVDEC | PASS, all 292 labels match, including the last frame. |
| Local VP9 alt-ref / AV1 | Report labels and selection | PASS, 640x360, 60 frames each; both whole timelines match and NVDEC is selected. |
| Fast 1080 speed | FFmpeg no more than 10% slower | PASS for one paired run: NVDEC 24.9216 s, FFmpeg 24.7368 s, ratio 0.99258. This is one pair, not a statistical performance claim. |
| Fake repeated/missing/unknown label and seek | First bad frame errors | PASS; duplicate [0,0,33,...] fails at frame 1, including before requested frame 2. |
| Runtime retry | Switch once, persist reason; second failure stops | PASS; controller/sequence/reuse bundle 36 PASS, 1 SKIP, 4.73 s; l3-controller.log. |
| Generic real hosts and duration replacement | Different video.mp4 hosts or changed duration: no offer; unchanged: offer | PASS; 4 real local tests including MP4/HLS/DASH and packet-copy regression, 30.52 s; l2-reuse-real.log. |
| Generic fallback | Unknown pre-download dimensions: no offer | PASS, real no-Range tail-header fallback, post-download check, 47.51 s; l2-reuse-fallback.log. |
| Approved 1440p refusal | Header rejection, no downloads/jobs, delete fixture | PASS, two CPU-encoded 2560x1440 H.264 frames with faststart. yt-dlp -J plus ffprobe only, 0 downloaded files, 0 jobs; fixture deleted in finally. l2b-1440-refusal-final.log (4.00 s). |
| Pre-change GPU suite | Record actual completed run | PASS, 101 tests, 517 deselected, 16434.42 s. This does not validate the new decoder; g5-gpu-suite2.log. |
| b38f03c CI | Windows and Ubuntu | PASS, push 39104573096 and PR 39104576929. New-head CI remains pending. |

Failed attempts are retained: sandbox loopback denial on the first refusal run;
its first unsandboxed test incorrectly expected a Lavf User-Agent even though
format http_headers intentionally forward the browser User-Agent. The corrected
assertion checks ffprobe's Range request. One yt-dlp metadata GET also occurs;
there is no transfer-mode yt-dlp invocation. The first diagnostic job admission
was sandbox-denied while resolving the scratch source; the escalated isolated
run completed. No protected owner folder was used. Ruff and Pyright pass after
fixing ordinary annotation/format issues. Full current CPU/GPU suites are running.


### Current regression checkpoint

- Full CPU suite: 532 PASS, 17 SKIP, 101 deselected, 781.00 s;
  g5-cpu-suite-final.log. Link tools were not enabled in that general suite;
  the separate final real-tool bundle runs those integrations explicitly.
- Decoder/controller/reuse bundle after the retry-order audit: 40 PASS, 1 SKIP,
  4.74 s; l3-final-unit.log. Native missing-timeline guard: 7 PASS, 4.27 s;
  l3-strict-timeline-final.log. No ordinal timestamp guessing remains on NVDEC.
- GUI lint/typecheck and 52 units PASS (8.53 s), including full reuse label,
  selecting the earlier file and Download again. Default E2E: 14 PASS, 13 SKIP,
  2.3 min; g6-gui-e2e-final.log. S9 move/relaunch/live-data test PASS (26.0 s).
- G4 final screenshots: 1 PASS, 10.9 s, g4-links-final3.log. Settings controls
  were scrolled into view before capture; no product layout changed. Visually
  inspected the 1100 dark Add card and light Settings images. The 16 final PNGs
  total 1129583 bytes before the final Settings recapture.
- Feature-free package refreshed and isolated-copy smoke PASS. SHA-256:
  30df88b7b340295dfe379069b21ebf17c8da999183c5b6598d09cd2acba00de4.
  External engine healthy, expected scratch home, no default debugging argument;
  g6-featurefree-smoke-decoder-final.json/log. Package path remains
  D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer.
- source.timestamp persistence and unchanged-file reuse: PASS, real local direct
  transfer, 11.46 s; l2-timestamp-persist.log.
- Current new files: tests/test_decoder_selection.py and tests/test_link_reuse.py.
  Decoder, analysis, manifest store, controller, link service/jobs, LinkPanel,
  App, HistoryDetail, Queue, tests, docs/GUI and both .ai files changed.
- Final real-tool acceptance: 54 PASS, 127.73 s, including the trusted TLS
  redirect refusal, interruption/resume, unknown header fallback, two-server
  reuse checks, timestamp persistence and approved CPU 1440p refusal;
  g1-link-acceptance-final.log. No third-party video site was used.
- Final controller/strict-label/reuse bundle: 41 PASS, 1 SKIP, 4.80 s;
  l3-final-unit2.log. An earlier OOM reduction to batch 1 remains in effect
  during the one-time decoder retry. Ruff and Pyright PASS.
- Original Archive output and both decoder speed-run outputs are byte-identical:
  39152863 bytes, SHA-256
  f724b96e32b316dca2289826775e79ca447f5c831d13203835850a993e2418af.
  Commons output is 2331180 bytes, SHA-256
  1cfa5192bdac29efc2e009c523432538194b151b2e3304e9519606bd4461c368.
  l3-output-inventory.json preserves these before scratch cleanup.
- Full GPU suite remains in progress. No GPU result is inferred from the
  earlier 101-PASS run.


## Final GPU result and cleanup inventory

GPU suite3 completed: 101 PASS, 549 deselected, 15963.56 s (4:26:03),
exit code 0. All selected GPU tests used allowed source/output dimensions.
This validates the strict decode/media path; final controller retry branches
were separately verified by the 41-PASS bundle. No GPU soak or legacy 2160
calibration was run. g5-gpu-suite3.log preserves every case and duration.

Before cleanup (logical lengths, 2026-10-19T02:27:26Z):
- D:\my-workspace\VideoEnhancer\work\scratch: 115483916442 bytes, 31669 files.
- D:\my-workspace\VideoEnhancer\work\evidence\P1e-2: 9139299 bytes, 288 files;
  older than the three retained cycles. Reports remain in Git history.
Both exact roots are ordinary directories inside work. Neither owner directory
is included. Test media/output metadata, source/output hashes and essential logs
have been retained under evidence/P1f before the cleanup attempt. The previously
rejected Electron package/cache deletion is not retried.


### Owner-authorized capacity reduction

The owner explicitly authorized retrying the old Electron package deletion and
asked to minimize remaining disk usage. The earlier refusal remains historical;
it is superseded by this new authorization. Python/Node/Rust runtimes, the venv,
verified link tools and model caches remain. These regenerable development
artifacts have been inventoried before deletion; none is Git-tracked:

| Exact path under D:\my-workspace\VideoEnhancer\work | Logical bytes |
| --- | ---: |
| D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-win32-x64 | 428412636 |
| D:\my-workspace\VideoEnhancer\work\cache\electron | 0 |
| D:\my-workspace\VideoEnhancer\work\cache\tauri-target | 4370274210 |
| D:\my-workspace\VideoEnhancer\work\cache\uv | 3480500128 |
| D:\my-workspace\VideoEnhancer\work\cache\npm | 57237453 |
| D:\my-workspace\VideoEnhancer\work\cache\cargo\registry | 675485832 |
| D:\my-workspace\VideoEnhancer\work\repo\gui\node_modules | 191885410 |
| D:\my-workspace\VideoEnhancer\work\repo\gui\dist | 575709 |
| D:\my-workspace\VideoEnhancer\work\repo\gui\test-results | 45 |

Tool/model binaries and the current package are excluded. Local Rust/UI builds
will require restoring the removed dependency caches before another rebuild.

Post-cleanup smoke created 17152762 logical bytes in D:\my-workspace\VideoEnhancer\work\scratch;
that exact temporary root is now scheduled for cleanup again.


## Final local outcome and disk budget

All inventoried cleanup candidates were removed. The first scratch attempt
stopped on a lock held by an older failed GUI fixture. Only its venv test engine
(VE_HOME under scratch/P1f, PID 29768 and child 30112) was terminated, then cleanup
succeeded. That was a file lock, not an approval rejection. The later owner
instruction authorized the previously rejected Electron cleanup; it succeeded.
The 17152762-byte post-cleanup smoke home was also removed. No owner data or
Recycle Bin was inspected or cleaned. P1e-2's report remains at Git dc02580.

The retained package passed another isolated startup after cache removal;
Python 3.12.15 / Torch 2.14.1+cu130 import, engine health and unchanged executable
SHA-256 PASS. Evidence: g6-featurefree-smoke-after-cleanup.json/log. Final Ruff,
format and Pyright PASS. GUI/Rust checks ran before their regenerable outputs
were removed. No local rebuild is claimed after removing those dependencies.

| Decimal GB | Start | End |
| --- | ---: | ---: |
| C:/ free | 309.799707 | 308.345725 |
| D:/ free | 1004.175360 | 1009.745265 |
| cache, logical | 10.641371 | 2.302191 |
| scratch, logical | 0.000000 | 0.000000 |
| package, logical | 0.434162 | 0.005771 |
| evidence, logical | 0.207036 | 0.210749 |

Persistent change across inventoried roots: -8.763859 GB (under the +1 GB gate).
Current P1f evidence: 0.012852 GB, below 0.300 GB;
retained cycles are P1e-2b, P1t and P1f. Cache is below 40 GB. Scratch has 0 files;
package has only VideoEnhancer (2 files). Per-item removed logical bytes are in
the two cleanup tables above; root rows overlap those tables and are not summed.
Hard links make logical lengths differ from allocated space. C/D free-space
changes include unrelated OS/application activity and are not attributed solely
to this cleanup. disk-final.json/log records the measured endpoint.

Local implementation/acceptance is finished. P2 cold start remains FAIL and the
accepted historical P1t failures remain FAIL. No new designer decision is open.
Only final branch publication and exact-head Windows/Ubuntu CI remain.
