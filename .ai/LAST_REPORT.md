# VE-P1t implementation and validation

- Task ID / Cycle: VE-P1t, P1t.
- Status: PARTIAL. Implementation and local validation complete; final CI pending. Cold start, History switching, AV1 and repeat-memory gates failed; cleanup was refused.
- Branch: p1t-tauri, base p1d-ui-v2 at 40755c0. Draft PR #6.
- Owner instruction resumed A1 after installing Build Tools. Designer M1, size-limit, S1/S9 and revised M2 decisions are preserved in CURRENT_TASK.md.
- All media is synthetic and all application homes/profiles are isolated under work/scratch. The owner queue was not used. Product source/output limits are deferred to P1f Part R as instructed; no new product limit is introduced here.
- External evidence root: work/evidence/P1t. No media, weights, packages, screenshots, caches or owner logs belong in Git.

## Implementation and changed files

Added the Windows Tauri shell in gui/src-tauri, split into engine, media, storage, window and command modules. Added the desktop.ts renderer bridge and a CDP test harness. Preserved the existing React screens with native title bar, native file-drop events, pointer/keyboard queue reordering, HEVC compatibility messages and the specified Storage fixes. Updated six project documents and the Windows/Ubuntu workflow. Electron source and dependencies remain while acceptance is incomplete; they are not presented as removed.

The M1 protocol bounds every response, limits simultaneous upstream fetches to two, uses a 10-second engine-fetch timeout and checks the exact returned body length. Cancellation notification is unavailable and the designer waived engine cancellation. M3 is not in the production engine; the private prototype requires VE_DEV_M3_MEDIA=1.

Storage uses one canonical roaming pointer, migrates a legacy pointer atomically, verifies the active engine home and writable/readable probe, and checks startup core records before enabling Remove. Only matching manifest-listed OLD files may be removed; the live NEW folder is never compared with the manifest. Malformed non-core JSON/JSONL bytes are retained. Damaged job manifests conservatively protect all old files because their source/output paths cannot be established.

## Part status

| Part | Status | Evidence / limitation |
| --- | --- | --- |
| A | PARTIAL | Baseline and feasibility measured; historical renderer budgets failed. |
| T | PARTIAL | Final enabled E2E cases passed across full and targeted runs. Native confirmation, missing-folder recovery/Quit, Explorer selection, default player and browser checked; tray and physical checks remain NOT RUN. |
| M | PARTIAL | All 96 production measurements complete. Designer selects 1 MiB M1; AV1 growth/residual FAIL remains. Follow-ups complete: M1 and M3 repeat FAIL; M1 retained per designer. Low-target trial reduces residual, timing PASS. |
| D | PARTIAL | Pointer/keyboard and trusted wheel tests passed; physical pinch/native OS drops NOT RUN. |
| U | PARTIAL | Read-only pointer/cache checks and two stale-default isolation tests passed, including final10 E2E. Owner cache deletion intentionally not attempted. |
| S | PARTIAL | Expanded S9 and exact S5 UI refusal PASS. Startup damage safely fails Move; recovery deferred to P1e-3 by designer. |
| X | PARTIAL | Final local checks PASS; remote CI pending. |
| G | PARTIAL | Package/visuals/local checks complete; cold start, renderer and media gates FAIL. Old package and scratch cleanup refused; CI pending. |

## Baseline and feasibility

| Measure | Electron A1 | Tauri final |
| --- | --- | --- |
| Package logical bytes | 428,412,636 (74 files) | 5,749,307 (2 files); PASS <=50 MB |
| Five cold starts, ms | 1267.2931, 499.346, 574.3591, 431.2788, 487.5167; median 499.346 | 736.5263, 668.9520, 679.2962, 660.3506, 681.8362; median 679.2962; FAIL limit 549.2806 |
| Five-minute app private working set | 130,490,368 bytes | 101,498,880 bytes |
| Renderer interaction p98, ms | Runs 2/3/4: 259.36 / 243.36 / 211.36; FAIL against 200 | 72 observed; suite FAIL warm History 134.65 >100 ms |
| Real CUDA progress | PASS; backend median .957652% of one core; renderer .93326 Hz | PASS final14; backend1.00806%, renderer.96657 Hz, job done |

A1 renderer run 1 aborted because the environment was loaded from the wrong directory. Runs 2/3 had concurrent resource activity; serial run 4 still failed. All failures remain reported. The baseline idle fixture has 1,000 History records and a Node fixture server; separate Python engine memory was NOT RUN in that baseline. Production M2 records Python-engine memory separately and excludes it from app-process totals.

Build environment: Build Tools 18.11.12306.390, SDK 10.0.26100.0, Rust 1.99.1 and WebView2 155.0.4283.45. The native DWM caption/text calls returned HRESULT 0 for dark/light; Snap Layouts were observed. The actual app origin is http://tauri.localhost. AV1 extension 2.0.35.0 and VP9 extension 1.2.20.0 were present; HEVC extension absent.

| Codec | 1080 exact string | 1440 exact string | MSE / canPlayType, both sizes | Actual playback/seek |
| --- | --- | --- | --- | --- |
| H.264 | avc1.640028 | avc1.640032 | true / probably | PASS both |
| AV1 | av01.0.08M.10 | av01.0.12M.10 | true / probably | PASS both |
| HEVC | hev1.2.4.L120.90 | hev1.2.4.L150.90 | false / empty | FAIL both; error 4 |

M4 keeps HEVC as the default and offers the exact compatibility message, Store link and default-player action. H.264 Compare uses the existing CPU encoder. Store installation was NOT RUN. The native default-player action opened the isolated H.264 clip in Media Player; its first frame was visible, paused at 0 s (no autoplay claim).

## Historical media runs, not final qualification

Before the owner stopped the run, a 2160 file of 2,461,695,636 bytes gave start 126.35 ms, seek 2757.70 ms and sampled warm-baseline USS growth 191,807,488 bytes: FAIL seek. These are historical results only. Five own 4K/2160 files totaling 2,710,532,061 bytes were deleted after the size update; exact before/result inventories are retained. No prohibited GPU job was resumed.

The final 1440 fixtures are H.264 2,032,330,077 bytes and AV1 2,032,855,414 bytes. FFmpeg generated 1920x1080 synthetic content, scaled it to 2560x1440, encoded NVENC p4 constqp18 GOP15 samples and stream-copied repetitions; no enhancement pipeline, padding or owner media. Recipe and ffprobe results are retained.

| Run | Status and measurements |
| --- | --- |
| M1 media-run1 | SETUP FAIL: HEAD fetch to custom media scheme blocked by strict connect-src; fixture obtained size externally. |
| M1 media-run2, 2 MiB | Timing H.264 78.8/60 ms, AV1 63.75/80.7 ms. Memory INVALID: Python descendants included (1,103,085,568 / 861,855,744 bytes). |
| M1 media-run3 | Build failed from missing Emitter import; command incorrectly continued with stale 2 MiB binary. H.264 66.25/54.9 ms, AV1 61.85/76 ms; corrected app attribution USS growth 210,038,784 / 236,216,320. Not a 512 KiB qualification. |
| M1 media-run4, actual 512 KiB | H.264 74.1/75.65 ms, 298,684,416 bytes; AV1 32.85/122.25 ms, 323,600,384 bytes. Client fetch peak 2. FAIL withdrawn absolute USS gate. |
| M3 runs 1/2/3 | SETUP FAIL: token-route 404, then CSP mistakes. Private tokens redacted. |
| M3 run4, unbounded HTTP | H.264 41.85/18.4 ms, 138,612,736 USS bytes; AV1 36.95/24.2 ms, 142,442,496 bytes. Fetch peak 2. FAIL withdrawn gate. |
| M3 run5, HTTP cap 256 KiB | H.264 100.95/96.8 ms, 323,911,680 USS bytes; AV1 125.05/122.7 ms, 356,532,224 bytes. FAIL withdrawn gate. |
| Node-fixture new-gate attempt | Exploratory only, intentionally stopped to use the production Python Range handler. Completed 8 MiB H.264 timing/P/R; Electron steady completed; Tauri steady aborted. No qualification from this attempt. |

Historical M1 versus M3 simultaneous-peak attribution: H.264 shell .041/.287 MB and WebView2 298.643/138.326 MB; AV1 shell -1.270/.254 MB and WebView2 324.870/142.189 MB. The extra160-181 MB was in WebView2. Old child roles were not recorded, so renderer/GPU attribution from those old logs is inference. Historical USS is not comparable with the revised Private Bytes metric. Raw PIDs/increments remain in historical-m1-m3-attribution.json. New M2 records every PID/role.

## Revised production M2

All 96 runs completed. M2 FAIL: no chunk passes both codecs. Every timing and steady-growth gate passes; every AV1 P-growth and P/R residual comparison fails. Post-steady residuals remain observational; only the specified ten-minute growth comparison is a steady-test gate. The corrected evaluator reports H.264 at 1 and 2 MiB PASS, AV1 FAIL at every chunk.

T/E means Tauri/Electron. Timing is the median of ten; P/R growth and residual are medians of three. MB are decimal. Shell peaks are maximum individual shell Private Bytes over the three repetitions, not growth. Per-process peaks are not simultaneous.

| MiB | Codec | Start / seek ms, T | P growth MB, T/E | R growth MB, T/E |
| --- | --- | --- | --- | --- |
| 8 | h264 | 104.60 / 80.15 | 427.2/405.0 | 235.0/391.7 |
| 8 | av1 | 119.20 / 78.10 | 371.7/229.3 | 296.1/449.3 |
| 2 | h264 | 48.15 / 49.80 | 361.0/419.5 | 213.0/395.4 |
| 2 | av1 | 49.80 / 49.55 | 357.7/222.7 | 245.9/469.1 |
| 1 | h264 | 32.85 / 38.15 | 319.3/416.7 | 169.5/401.5 |
| 1 | av1 | 33.55 / 49.70 | 362.8/220.3 | 242.0/461.8 |

| MiB | Codec | P residual MB, T/E | R residual MB, T/E | Steady 2-10 min MB, T/E | Shell P/R peak MB, T | Engine P/R peak |
| --- | --- | --- | --- | --- | --- | --- |
| 8 | h264 | 235.5/276.1 | 193.5/185.3 | 11.2/71.3 | 92.6/74.7 | 1/2 |
| 8 | av1 | 271.9/27.9 | 229.4/214.0 | 10.4/109.1 | 93.1/85.5 | 1/2 |
| 2 | h264 | 228.4/286.5 | 177.9/182.5 | 6.7/63.5 | 30.1/30.7 | 1/2 |
| 2 | av1 | 270.2/30.7 | 236.4/223.7 | 15.7/142.4 | 16.4/26.2 | 2/2 |
| 1 | h264 | 233.5/274.5 | 155.5/185.2 | 16.7/76.2 | 19.6/16.4 | 2/2 |
| 1 | av1 | 279.2/24.1 | 235.7/213.5 | 16.3/100.2 | 18.8/20.5 | 2/2 |

Every PID/role/baseline/peak/growth is in m2-production/per-process.csv; raw JSONL holds 1 s observations and concurrent totals. The role table is the median of three per-PID peak-growth aggregates (P/R MB, absent roles zero). Role peaks need not coincide; do not sum them into a total.

| MiB / codec | Role | P growth MB | R growth MB |
| --- | --- | --- | --- |
| 8 / h264 | browser-helper | 2.1 | 1.0 |
| 8 / h264 | crashpad-handler | 0.9 | 0.9 |
| 8 / h264 | gpu-process | 85.0 | 97.9 |
| 8 / h264 | renderer | 276.9 | 236.3 |
| 8 / h264 | shell | 84.8 | 9.1 |
| 8 / h264 | utility:network.mojom.NetworkService | 0.0 | 0.0 |
| 8 / h264 | utility:storage.mojom.StorageService | 0.0 | 0.0 |
| 8 / av1 | browser-helper | 8.5 | 25.7 |
| 8 / av1 | crashpad-handler | 0.9 | 0.9 |
| 8 / av1 | gpu-process | 63.4 | 82.0 |
| 8 / av1 | renderer | 307.2 | 267.0 |
| 8 / av1 | shell | 67.3 | 69.0 |
| 8 / av1 | utility:network.mojom.NetworkService | 0.0 | 0.0 |
| 8 / av1 | utility:storage.mojom.StorageService | 0.0 | 0.0 |
| 2 / h264 | browser-helper | 5.0 | 1.2 |
| 2 / h264 | crashpad-handler | 0.9 | 0.9 |
| 2 / h264 | gpu-process | 81.2 | 86.9 |
| 2 / h264 | renderer | 277.2 | 223.2 |
| 2 / h264 | shell | 20.3 | 20.5 |
| 2 / h264 | utility:network.mojom.NetworkService | 0.0 | 0.0 |
| 2 / h264 | utility:storage.mojom.StorageService | 0.0 | 0.0 |
| 2 / h264 | utility:unzip.mojom.Unzipper | 0.0 | 0.0 |
| 2 / av1 | browser-helper | 2.1 | 1.1 |
| 2 / av1 | crashpad-handler | 0.9 | 0.9 |
| 2 / av1 | gpu-process | 46.4 | 61.6 |
| 2 / av1 | renderer | 308.8 | 270.0 |
| 2 / av1 | shell | 4.1 | 14.0 |
| 2 / av1 | utility:network.mojom.NetworkService | 0.0 | 0.0 |
| 2 / av1 | utility:storage.mojom.StorageService | 0.0 | 0.0 |
| 1 / h264 | browser-helper | 5.7 | 0.8 |
| 1 / h264 | crashpad-handler | 0.9 | 0.9 |
| 1 / h264 | gpu-process | 39.6 | 57.3 |
| 1 / h264 | renderer | 281.9 | 207.5 |
| 1 / h264 | shell | 3.6 | 4.6 |
| 1 / h264 | utility:network.mojom.NetworkService | 0.0 | 0.0 |
| 1 / h264 | utility:storage.mojom.StorageService | 0.0 | 0.0 |
| 1 / h264 | utility:unzip.mojom.Unzipper | 0.0 | 0.0 |
| 1 / av1 | browser-helper | 6.2 | 1.1 |
| 1 / av1 | crashpad-handler | 0.9 | 0.9 |
| 1 / av1 | gpu-process | 48.4 | 29.9 |
| 1 / av1 | renderer | 311.9 | 262.0 |
| 1 / av1 | shell | 11.2 | 11.5 |
| 1 / av1 | utility:network.mojom.NetworkService | 0.1 | 0.0 |
| 1 / av1 | utility:storage.mojom.StorageService | 0.0 | 0.0 |

Designer-selected P1t path: 1 MiB M1 (decision 2026-10-17). AV1 gates 1 and 2 remain FAIL. It reduces the maximum shell P/R peak from 93.1 MB at 8 MiB to 20.5 MB, gives the lowest H.264 P/R growth and fast starts/seeks. The requested repeat, idle, decoder and M3 follow-ups are complete below; M1 remains the selected path. This is parameter tuning, not a switch to M3. Native fetch permits and actual engine logs both observed a maximum of two concurrent fetches. The largest new-run playback growth is in WebView2 renderer/GPU processes; the exact historical renderer/GPU attribution remains inferred because those old roles were not captured.

Method: 1 s Private Bytes sampling of all app descendants; 10 s pre-Play baseline, concurrent peak and 30 s residual. Alternate T/E three times with seed0x51eecafe; ten-minute stability seeks every30 s. The actual paused Python Engine/LocalServer serves Range; only the comparison service permits the legacy Origin. Production policy is unchanged. Frozen binary SHA-256 1a4f803c7739933e55c416ae2a0befe820641dc2ece925cad51f04b882989ce9; source/build provenance and complete PID exports are retained in m2-production-source.json, m2-production-build.json and the matrix output.

## Tests already executed, before final edits

| Check | Result | Evidence |
| --- | --- | --- |
| GPU-marked Python | PASS 101, 449 deselected, 15707.09 s; strict equality included | gpu-final.log |
| CPU Python final | PASS 458, SKIP 3, deselected 101, 754.02 s | cpu-final3.log |
| Targeted storage/service | PASS 35, 29.47 s | storage-service-final.log |
| Rust unit | PASS 12 after native Explorer fix | rust-test-final12.log |
| Rust clippy default / e2e | PASS default final12 and e2e final13 | clippy-default-final12.log / clippy-e2e-final13.log |
| GUI unit | PASS 47 across 10 files, 6.48 s; HEVC disabled-play and Low/Normal player lifecycle | gui-test-final13.log |
| GUI lint/typecheck/build | PASS final13 lint/typecheck, final10 frontend build; Vite chunk-size warning | gui-*-final13.log / package-build-final12.log |
| Initial default E2E | 5 PASS, 9 SKIP, 1 FAIL pinch test; corrected p1e run 4 PASS | e2e-all-run1.log / e2e-p1e-run3.log |
| Expanded default E2E | 6 PASS, 11 SKIP, 1 FAIL S9 profile locked inside moved home | e2e-final.log |
| S9 corrected profile location | PASS 1, 20.3 s | e2e-s9-run2.log |
| Current default E2E | 10 PASS, 11 SKIP, 1 FAIL Esc fullscreen | e2e-current.log |
| Esc/fullscreen restoration fix | PASS 1 | parity-run2.log |
| Pointer folder versus stale History | PASS 2 | u3-run1.log |
| Visual suites | PASS 4, 2.1 min; first attempt 3 PASS, 1 timeout from obsolete title-bar locator | visual-final.log / visual-run1.log |
| First unsigned package smoke | PASS 1, 9.3 s; test-only command rejected, require undefined, external engine found | package-smoke-run1.log |

Final enabled E2E coverage: final10 ran 20 PASS, 1 FAIL, 5 SKIP (6.8 min). The failure was an ambiguous Standard button in the Windows-flow test. The targeted final11 completed the flows but failed a window-monitor assertion: two internal layered helper windows have a 14x14 outer rectangle and 0x0 client area. The monitor now records them as non-display windows by geometry/style, without class-name whitelisting. Targeted final12 PASS (1.7 min): 1,012 polls, 101.188 s, unexpected=[]. Thus all 21 enabled cases passed across the full and targeted runs; a single full 21-pass rerun is not claimed. See e2e-final10.log, windows-flows-final11.log, windows-flows-final12.log and native-window-geometry. Earlier final9: 17 PASS, 4 FAIL, 5 SKIP (stale labels, a fixture outside scratch and required HTTPS validation); all were corrected without relaxing production validation. Earlier final8: 14 PASS, 12 SKIP. Historical aborted/setup runs remain in evidence.

GPU GUI trial and resume passed on allowed synthetic inputs. The trial's before/after estimate was unchanged at 51.6347; no speed-gain claim. Windows flows exercised all seven flows with local HTTPS weights, session-only CA trust and no system certificate-store change. Temporary test-environment dependencies: cryptography 50.0.2 (Apache-2.0 OR BSD-3-Clause), cffi 2.1.1 (MIT-0), pycparser 3.11 (BSD-3-Clause); not product dependencies.

Physical touchpad pinch, real Explorer drops of 1/50 files, cross-volume C-D-C move, actual tray-menu interaction, native video/folder picker selection, Store installation and reboot remain NOT RUN. The legacy GPU GUI speed-calibration test with 2160 output is NOT RUN (designer decision). CPU-only legacy 2160/3840 metadata or tiny synthetic tests were allowed. No prohibited GPU processing was resumed.

## Storage findings

| Finding | Implementation and evidence |
| --- | --- |
| S1 | Healthy resolved active home, write/read/remove probe and startup records gate Remove. Original expanded core/probe unit cases passed; expanded S9 probe/core negative checks PASS (e2e-final8). Native confirmation inspected at both sizes/themes. Enter/Esc cancel preserved the old file; explicit Remove deleted the matching old file and retained the active folder/pointer (native-final/remove-result.json). |
| S2 | Old-only size/hash manifest deletion, no links/root/active ancestor, unknown/changed/video files retained. Rust matching/protection tests passed; expanded S9 changed-size/hash/unknown-file cases PASS (e2e-final8). |
| S3 | VE_HOME disables Move and Remove with the specified message; storage visual and final10 E2E coverage PASS. |
| S4 | Shared canonical roaming pointer; two pointer locations beat stale-default History in U3 (2 PASS). |
| S5 | Designer narrowing implemented: preflight refuses damaged startup records with the exact relative-path message, retains current pointer/home, and keeps the new-folder start guard. Non-core damaged bytes/record counts retained. All eight new CPU cases and expanded S9 PASS, including the exact displayed refusal message; recovery functions unchanged. |
| S6 | Preparation errors reset moving/previous pause state; test_prepare_failure_restores_normal_operation passed in targeted suite. |
| S7 | Status scan skips disappearing/locked files; concurrent-churn test passed. |
| S8 | Cleanup rows use filename/state/date/size; id remains tooltip/detail. Final Storage visual comparison completed; evidence retained. |
| S9 | Actual Move/Quit/relaunch passed with profiles outside home. Final expanded sequence includes live log append, History deletion, probe/core failures, cancellation and matching-old-file removal, plus S5 preflight refusal; PASS 20.8 s in e2e-final8. Cross-volume C-D-C remains NOT RUN. |

## T parity evidence

| Row | Evidence and present limit |
| --- | --- |
| T1 | Single-instance/focus E2E PASS in final10; isolated GPU resume also PASS. |
| T2 | Hidden-startup E2E PASS final10. Client-area screenshots at both sizes/themes PASS; white-flash absence is not established by still images. |
| T3 | Close-to-tray and reopen E2E PASS final10. |
| T4 | Implemented native menu, 3-second pause refresh and double-click; native interaction NOT RUN. |
| T5 | Graceful Quit/relaunch S9 and refused-shutdown Retry Quit E2E PASS final10. Native missing-folder Quit exited and preserved the pointer. |
| T6 | Real-service desktop and package smoke passed; serve.json/health parsing Rust tests passed. |
| T7 | Fake-registry migration unit passed; owner Run key writes intentionally NOT RUN. |
| T8 | Keyboard/numpad, saved zoom and trusted Ctrl+wheel no-page-zoom passed in parity-run2. Physical pinch NOT RUN. |
| T9 | Final size/theme inventory and comparison completed. DWM calls HRESULT 0, Snap observed; native confirmation screenshots captured at all four size/theme combinations. |
| T10 | Dialog seam E2E PASS. Real three-button missing-folder dialog inspected; Use previous recovered the healthy home, Quit preserved the pointer. Native video/folder chooser selection NOT RUN. |
| T11 | Path validation PASS. Native Open folder and Media Player PASS. Explorer reveal initially opened Desktop; corrected Windows command-line quoting and feature-free package retest selected clip space 日本語,one.mp4 correctly (native-final/reveal-fixed.jpg). |
| T12 | Clipboard limits/readback passed in parity-run2. |
| T13 | URL allowlist unit PASS. Native allowed documentation link opened in Brave; app stayed on http://tauri.localhost/. Only the newly opened tab was closed. |
| T14 | 64,000-character error-log boundary passed in parity-run2. |
| T15 | Reload/error recovery and restart real-service E2E PASS final10. |
| T16 | Compare fullscreen/Esc restores bounds PASS. Actual H.264 History fullscreen/Esc test PASS with eight screenshots at both sizes/themes. |
| T17 | Release strict CSP configured and enforced by initial blocked custom-scheme fetch; owner smoke has no require/test command. Full security audit not claimed. |
| T18 | Actual CDP origin http://tauri.localhost; service tests reject old origin and retain auth/Host/Sec-Fetch checks. |
| T19 | Local-main capability only, no FS/shell/HTTP scope; command validation Rust tests and release test-command denial passed. |
| T20 | Non-Windows refusal stub implemented; execution in Ubuntu final CI pending. |
| T21 | Expanded S9 Move/Quit/relaunch, live log append, History removal, probe/core failures, cancellation, old-only matching removal and exact S5 refusal PASS final10. |
| T22 | Browser accelerators, zoom/pinch controls and context-menu interception implemented; native menu/text editing interaction not fully verified. |

## X2 old-to-new test map

All original filenames remain and now import tests/desktop.ts instead of Electron. No existing spec was silently removed. The old main-process app.evaluate calls became renderer checks or feature-gated desktop_test queries/stubs.

| Old file | New file / validation |
| --- | --- |
| e2e/desktop.spec.ts | Same filename; real CPU service, close/restart, zoom and schedule tooltips. |
| e2e/gpu.spec.ts | Same filename; trial/paired-frames/estimate/startup preference, opt-in GPU. |
| e2e/p1d3-changed.spec.ts | Same filename; visual and interaction acceptance. |
| e2e/p1e-visual.spec.ts | Same filename; matching two-size/two-theme screenshot inventory. |
| e2e/p1e.spec.ts | Same filename; retained P1e checks plus new P1t parity and queue-reorder cases. |
| e2e/packaged.spec.ts | Same filename; owner feature-free package isolation smoke. |
| e2e/resume.spec.ts | Same filename; isolated synthetic GPU resume/single instance. |
| e2e/storage-visual.spec.ts | Same filename; Storage progress/result screenshots. |
| e2e/storage.spec.ts | Same filename; original cross-volume C-D-C test retained, opt-in. |
| e2e/visual-states.spec.ts | Same filename; design board inventory. |
| e2e/windows-flows.spec.ts | Same filename; isolated packaged GPU/console-window checks. |
| e2e/clipping.ts | Same helper filename; client-area top boundary replaces removed HTML title-bar boundary. |
| perf/renderer.spec.ts | Same filename; ten independent cold launches and unchanged budgets. |
| perf/real-progress.spec.ts | Same filename; actual CUDA backend/renderer cadence. |

New coverage: pointer.spec.ts (both pointer locations), storage-restart.spec.ts (S9 and S5), media.spec.ts (bounded timing), history-player.spec.ts (real H.264 video fullscreen). Full Private Bytes qualification is the separately opt-in scripts/media-matrix.mjs, not CPU CI.

## Added exact dependencies and licenses

| Dependency | Version | License |
| --- | --- | --- |
| tauri | 2.12.4 | MIT OR Apache-2.0 |
| tauri-build | 2.7.3 | MIT OR Apache-2.0 |
| tauri-plugin-single-instance | 2.5.4 | MIT OR Apache-2.0 |
| serde | 1.0.229 | MIT OR Apache-2.0 |
| serde_json | 1.0.154 | MIT OR Apache-2.0 |
| reqwest | 0.13.5 | MIT OR Apache-2.0 |
| rfd | 0.17.2 | MIT |
| arboard | 3.7.0 | MIT OR Apache-2.0 |
| winreg | 0.56.0 | MIT |
| sha2 | 0.10.9 | MIT OR Apache-2.0 |
| webview2-com | 0.39.1 | MIT |
| windows | 0.62.2 | MIT OR Apache-2.0 |
| @tauri-apps/api | 2.12.4 | MIT OR Apache-2.0 |
| @tauri-apps/cli | 2.12.3 | MIT OR Apache-2.0 |

Versions are locked; installed crate/npm license evidence is in dependency-licenses.json. No updater or telemetry added.

## Completed M2 follow-ups

All figures below are decimal MB of Private Bytes. The 1 MiB M1 is retained under the designer's both-fail rule. M3 is not shipped. Original AV1 gates 1/2 remain FAIL; no timing or steady-growth result was relabelled.

| Repeat test | Cycle 1 after close | Cycle 10 after close | Growth | Gate <=50 MB | Five minutes after close |
| --- | ---: | ---: | ---: | --- | ---: |
| M1 Tauri AV1 | 646.0 | 703.6 | 57.7 | FAIL | 704.4 |
| Electron AV1 | 417.8 | 571.9 | 154.2 | FAIL | 413.6 |
| M1 Tauri H264 | 552.2 | 643.0 | 90.8 | FAIL | NOT RUN (not requested) |
| M3 Tauri AV1 | 485.7 | 630.8 | 145.1 | FAIL | 609.4 |

Each cycle plays 30 s with seeks at 5/15/25 s, then closes for 30 s. The same instance remains alive for ten cycles; every PID and role is recorded at 1 s. Per-cycle role totals are in media-followup-roles.csv; raw cycles and baseline role means are in media-followup-summary.json. All three requested M1/Electron repeat runs and the M3 repeat completed; baseline sample counts are verified >=9.

| Cycle | M1 Tauri AV1 | Electron AV1 | M1 Tauri H.264 | M3 Tauri AV1 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 646.0 | 417.8 | 552.2 | 485.7 |
| 2 | 676.5 | 449.4 | 622.3 | 505.3 |
| 3 | 692.0 | 490.7 | 634.8 | 559.4 |
| 4 | 691.5 | 501.4 | 635.1 | 582.0 |
| 5 | 696.7 | 512.1 | 639.5 | 600.1 |
| 6 | 697.2 | 527.4 | 640.4 | 629.3 |
| 7 | 699.8 | 534.3 | 640.0 | 634.9 |
| 8 | 697.4 | 547.1 | 645.3 | 629.1 |
| 9 | 703.9 | 559.2 | 644.4 | 627.1 |
| 10 | 703.6 | 571.9 | 643.0 | 630.8 |

AV1 residual detail (absolute per-role totals at five minutes; these are not growth):

| Role | M1 Tauri | Electron | M3 Tauri |
| --- | ---: | ---: | ---: |
| browser-helper | 44.7 | 0.0 | 43.9 |
| crashpad-handler | 3.1 | 0.0 | 3.1 |
| gpu-process | 238.7 | 124.4 | 239.9 |
| renderer | 387.1 | 182.4 | 294.5 |
| shell | 9.3 | 94.0 | 7.0 |
| utility:network.mojom.NetworkService | 13.4 | 12.8 | 12.7 |
| utility:storage.mojom.StorageService | 8.0 | 0.0 | 8.2 |

The sampler labels descendants without a --type argument as browser-helper; named renderer/GPU/utility roles come from the process command line. The app root is shell. The Electron shell also contains its browser process, while WebView2 has a separate browser/helper process.

CDP Media.playerPropertiesChanged reports kVideoDecoderName=D3D11VideoDecoder and kIsPlatformVideoDecoder=true for both H.264 and AV1 in both Tauri and Electron. These are exact reported names/flags, not an independent hardware-decoder audit.

M3 uses the same production Engine/LocalServer/Range implementation and measurement harness, with a developer-only 128-bit, per-open, 10-minute media capability. A separate local CSP build permits loopback media. No M1 native fetch occurred in any M3 run (asserted counters=0). It streams the requested HTTP Range without the M1 response cap; the historical filename's 1MiB component is not an M3 cap.

| M3 AV1 P run | Peak growth | Residual after 30 s | Shell peak | Peak engine fetches |
| --- | ---: | ---: | ---: | ---: |
| 1 | 199.1 | 85.4 | 7.4 | 2 |
| 2 | 206.3 | 87.5 | 7.5 | 2 |
| 3 | 209.2 | 100.6 | 7.1 | 2 |

M3 P median growth/residual: 206.3/87.5 MB. Its P growth passes the Electron+100 MB comparison, but its residual exceeds 50 MB and its repeat test fails. New comparable P growth is 362.8 MB for M1 versus 206.3 MB for M3. The renderer's median per-process peak growth is 311.9 versus 154.0 MB; the shell is 11.2 versus 0.1 MB, GPU 48.4 versus 55.2 MB. Thus the measured extra is chiefly in the WebView2 renderer. Per-process peaks need not coincide, so these role peaks are not summed into the concurrent total. A custom-scheme retention mechanism is inferred; WebView2's internal allocation cause is not established.

Optional single Low-target trial: start 33.25 ms, seek 49.80 ms (both PASS); P residual 248.1 MB versus the normal M1 P median 279.2 MB, a 31.1 MB reduction. Keep Low while no player is open and Normal while one is, as explicitly authorized. This one trial does not turn the original memory failures into PASS. The implemented lifecycle has separate bridge/GUI validation; the complete 96-run matrix was not repeated after this optional optimization.

Both M1 and M3 fail the repeat gate. The designer explicitly directs retaining M1 and reporting a known issue, so no new M1/M3 choice is requested in this cycle. Owner check must include repeated opening/closing of H.264 and AV1 and retained memory. M3 remains absent from the default package and its developer flag is explicitly off in CI.

## Questions for the designer

1. S5 resolved by designer decision 2026-10-17: malformed startup core records must fail Move, preserve the pointer/current folder, and use the specified relative-path message. Preflight before copying plus post-copy record validation are implemented; engine corruption recovery is unchanged and deferred to P1e-3. New CPU and S9 GUI tests PASS (cpu-final3 and e2e-final8). Evidence s5-core-repro.json records the original source/target JSONDecodeError and preserved bytes. Non-core damaged records remain copyable and reported.
2. Designer selected 1 MiB M1 on 2026-10-17; M3 stays out of the default build. AV1 gates 1 and 2 remain FAIL. All follow-ups completed. M1 and M3 repeat FAIL, so retain M1 with a known issue under the designer's rule; no further media choice is required here.
3. HEVC extensions are absent. The output default remains unchanged as required; any default-codec product decision belongs to the designer/owner.

## Cleanup and disk

Both automatic approval reviews rejected deletion as "blocked by policy". Neither command was bypassed or retried. Zero bytes were removed by these two attempts; the one-package and empty-scratch gates are unmet.

For the owner to delete (two development folders):

- D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-win32-x64: 428,412,636 logical / 428,572,856 allocated bytes, 74 files.
- D:\my-workspace\VideoEnhancer\work\scratch: 69,884,762,259 logical bytes, 112,348 files. Includes generated 1440p media and temporary profiles/binaries; all owned jobs/apps were stopped before the rejected attempt.

For the owner to delete later (read-only U5 inventory under %APPDATA%/VideoEnhancer): Cache856,456 bytes/7 files; Code Cache13,636/9; GPUCache1,642,864/5. Only these three cache subfolders were inspected; no owner app-data/pointer folder is a deletion candidate.

Owner package: D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer, exactly VideoEnhancer.exe and engine-location.json. Logical5,749,307 / allocated5,750,848 bytes, two files. Feature-free final12 build and isolated byte-identical copy smoke PASS (5.9 s); hashes in owner-release-final12-hashes.json. External engine checkout/.venv are not bundled.

| Disk item | Start GB | Final GB |
| --- | ---: | ---: |
| C free | 332.084830208 | 308.739457024 |
| D free | 1010.481532928 | 934.244171776 |
| Cache logical | 4.193152357 | 10.640700339 |
| Scratch logical | not inventoried | 69.884762259 |
| P1t evidence logical | not inventoried | 0.166048749 |
| Tauri / old package logical | 0 / .428413 | .005749 / .428413 |

Rust target 4.240587854 GB (debug/release recorded separately in disk-final16.json), cargo .853716 GB, rustup1.314835 GB are the explicit one-time bootstrap exception. CARGO_BUILD_JOBS=2, session-only paths, complete cache 10.640700339 GB <40 GB. Cache increase is 6.447547982 GB; drive-free deltas are not attributed to this project. Evidence retains exactly P1e-2/P1e-2b/P1t at .009139/.015587/0.166048749 GB, each below300 MB. Inventory errors: none. Full persistent-growth <=1 GB cannot be claimed with scratch cleanup blocked and incomplete starting root inventories. See disk-final16.json; logical lengths are not allocated sizes or drive-wide free changes.

## Visual comparison and native checks

Compared the existing P1e-2 visual reference with current Home/Add/History/player/Compare/Models/Schedule/Settings images at 1280x800 and 1100x700 in both themes. Intentional changes: removing the HTML title bar moves content up about 32 CSS pixels and gives Compare more height; Settings contains the specified Storage card; unsupported HEVC player shows its compatibility notice/actions with Play disabled. Native caption/dialog styling, font antialiasing and native checkbox rendering differ from Electron. Time/progress/path differences follow the synthetic fixtures and clocks. No other layout change was observed; pixel identity is not claimed. Evidence: visual-p1e-final10, visual-player-final10, visual-storage-final10, visual-comparison-final10, native-final.

Native custom labels initially fell back to standard labels: rfd lacked common-controls-v6. Enabled it using Tauri's existing manifest, rebuilt, and verified Cancel/Remove and recovery dialogs. The interactive launcher used Normal visibility to expose the startup modal. All homes were isolated; no owner Run registration was changed.

## D and U evidence

| Item | Result / evidence |
| --- | --- |
| D1 | Native Tauri path events replace HTML5 file drops and webUtils. Drop/Add seam E2E PASS; actual OS 1/50-file drops including long/non-ASCII paths NOT RUN after Computer Use rejected the drag endpoints. No workaround attempted. |
| D2 | Pointer capture and Alt+Arrow queue reorder PASS final10. |
| D3 | Compare wheel/pinch-event behavior and page-zoom prevention PASS; physical touchpad pinch NOT RUN. |
| U1 | Read-only: canonical VideoEnhancer pointer exists and active folder exists; legacy videoenhancer-desktop pointer absent. No owner names/contents reported (owner-pointer-readonly.json). |
| U2/U3 | Atomic legacy migration and both pointer locations beat stale default History: Rust unit and two final10 E2E cases PASS. Missing active folder uses explicit recovery, never silent fallback. |
| U4 | Fake-registry migration and unrelated-entry preservation unit PASS; real owner Run writes intentionally NOT RUN. |
| U5 | Three exact cache folders inventoried read-only below; no deletion attempted. |

## Reproduction

Load ignored local-env.ps1 from the repo root. Exact commands/environment are in external recipes/checks-final13.ps1, g-perf-final13.ps1 and native recipes. Run Python CPU checks, allowed-size GPU tests, GUI lint/typecheck/unit/build, Rust fmt/clippy/test, then e2e-feature CDP tests with isolated homes/profiles. G1 uses desktop-baseline.mjs and both unchanged-budget perf specs. M2 uses media-matrix.mjs, saved FFmpeg recipes/seed and the environment in docs/DEVELOPMENT.md; the two summarizers generate tables. Hashes distinguish historical builds; current-source reruns are not byte-identical. Build the feature-free package using package-tauri.mjs and smoke a fresh isolated copy. Never substitute USS for Private Bytes or use owner data.

## G1 final performance

The matched Electron repeat (same new CDP harness and Node 1,000-History fixture) measured 877.1665/414.1345/483.2428/587.0664/581.9381 ms, median 581.9381. Tauri's median is 36.0% slower than original A1 and 16.7% slower than this repeat. The original 549.2806 ms limit is retained: FAIL. Each launch used a fresh profile and verified every recorded app PID/creation-time pair had exited before the next launch. Five-minute app Private Working Set/Private Bytes: Electron 132,771,840/263,524,352 bytes; Tauri 101,498,880/245,747,712. Attribution is root plus recursive descendants, including all WebView2 children; raw PIDs are in g-baseline-*-final13.json. Python idle memory in this common Node fixture is NOT RUN, as in A1.

Renderer final13 completed all ten independent launches in 5.6 min. Suite FAIL at warm History median 134.65 ms (limit100). Other captured medians: Schedule28.80, Models36.40, Settings45.65, Home78.45 ms; cold History141.10; theme light/dark/system36.80/35.45/34.90; key-paint28.25; preview457.85 ms; idle renderer0.7242% of one core; progress0.99942 Hz, shortest gap997.9 ms. Interaction p98=72 ms, maximum input delay4.2 ms. These other observed values are within their stated budgets, but assertions after the first failed assertion did not run; no suite PASS is claimed. Raw samples and failure trace are in g-renderer-final13 and g-renderer-final13-failure.

## Final local checks and cleanup preflight

Final13: Ruff check/format, Pyright, Rust fmt and e2e clippy, GUI lint/typecheck and 47 unit tests PASS (6.48 s); S9 PASS (23.6 s), including cleanup against the current moved engine. Default Rust clippy and 12 unit tests PASS final12. Feature-free package final12 built and smoke PASS (5.9 s). Vite's 531.11 KB chunk warning and Node's NO_COLOR/FORCE_COLOR warning are nonfatal.

Real CUDA final13: cadence PASS, but the test teardown stopped the external fixture, leaving its job queued; completion FAIL. Fixed the test to set VE_KEEP_TEST_ENGINE=1. Fresh final14: cadence PASS, job done, all three segments complete. Backend median1.00806%, p90 1.33064% of one core; 5,000-History diagnostic retained. Display0.96657 Hz, shortest999.5 ms, good SSE-gap fraction1.0. Both runs, including the interruption, are preserved under g-real-final13/14.

## Remaining acceptance and Git

G1 FAIL cold start/History; G2 PARTIAL manual tray/pickers/physical checks; G3 codec/M4 complete; G4 S1-S9 PASS except cross-volume manual NOT RUN; G5 U checks complete with owner Run writes intentionally NOT RUN; G6 screenshots reviewed; G7 allowed GPU101 PASS, prohibited2160 GUI calibration NOT RUN (designer decision); G8 local checks PASS except perf, final CI pending; G9 smoke PASS/old package removal refused; G10 cache/evidence caps PASS, empty scratch/growth not qualified. Electron removal remains conditional on G passing and is intentionally deferred. No merge or main/base-branch push.

Changed files: six docs, .ai task/report, workflow/ignore rules; gui package/lock, src-tauri modules/config/locks/icons, desktop bridge and existing App/Home/Queue/HistoryDetail/Storage/main/style/types; desktop test harness/unit contracts and the mapped E2E/perf files above; window_monitor.py and desktop_startup_diagnostics.py; service engine/server/storage and their tests. Exact inventories: changed-tracked-files-final16.txt and added-files-final16.txt outside Git.

Questions for designer: cold-start and warm-History budgets remain unmet; current implementation retained without a design change. The media choice is already resolved by the both-fail rule. Native/physical gaps and memory failures remain on the owner check. CI and push verification follow this local report checkpoint.

Initial a710b21 CI: Ubuntu PASS; Windows push39026277983/PR39026280367 FAIL (12 CDP startup timeouts,14 SKIP). Runtime-preflight 194135c push39028150187/PR39028152936 also FAIL identically; machine Runtime154.0.4258.62 already existed, disproving the missing-runtime hypothesis. Local debug E2E with explicit runtime:13 PASS/13 SKIP,1.9 min; mixed-slash executable startup PASS2.0 s. Added e2e-only startup checkpoints and owned-process/native-window diagnostics; local capture/quit PASS. Diagnostic lint initially failed on a redundant assignment, corrected and lint/typecheck PASS. Next CI runs startup smoke before Windows CPU tests, retaining all gates. Final CI pending; product behavior/package unchanged.
