# VE-P1e-2 implementation and verification report

Status: PARTIAL. The final 2160 initial-estimate gate failed; successful processing is reported separately. This report does not establish the cause of the owner's original stall.

Branch: `p1d-ui-v2`. Starting implementation: `ad6b1f7`; saved instructions: `4ba1ef1`. Draft PR: https://github.com/Kei-Takamizawa/VideoEnhancer/pull/5. No merge or push to main. No new dependencies, telemetry, automatic update or catalog entries.

## Scope and evidence rules

All processing media are synthetic. Every GPU case has an isolated engine home; GPU workloads ran sequentially except the disclosed early overlapping source-4K attempt. Owner logs were copied read-only. The owner's media, queue, settings and Recycle Bin items were not test data. Native shell tests touched and restored only their own files. Videos, weights, packages, screenshots and private logs remain outside Git.

Evidence roots:

- `C:\Users\pro\Documents\VideoEnhancer-P1e-2` (reports, logs, GUI evidence).
- `D:\VideoEnhancer-P1e-2` (large isolated homes and synthetic outputs).

Hardware/runtime: Windows 11, RTX 4060 Ti 8 GB, driver 617.42, Python 3.12.14, Torch 2.14.1+cu130, PyNvVideoCodec 2.2.3, FFmpeg 9.0.2. CPU CI is fixture integration, not GPU quality evidence. All GB below are decimal unless stated otherwise. Torch allocation/reservation, per-process PDH dedicated/shared memory and device-wide NVML samples are distinct measurements. Sampled maxima are not guaranteed high-water marks, cannot be summed across PIDs/times and do not prove physical VRAM capacity was exceeded.

## Part status

| Part | Status | Implementation and evidence |
| --- | --- | --- |
| E | DONE / PASS | Full job data shared by snapshot/packet planning; cumulative active-part rate and initial blend; named startup terms and median learning; deterministic packet/snapshot regression PASS. All long-gate attempts below. |
| F | DONE / PASS | Realistic 1/30/120-minute finalization fixtures, nonlinear built-in model, length-class learning, admission reserve, validated joined-file checkpoint and persisted step timing. |
| R | PARTIAL / estimate gate FAIL | Measured 1080/2160 component and whole-pipeline points, interpolated stages, output-size learning classes, uncalibrated +/-25% above measured maximum. Final fresh-home 30-second gate +21.18%, outside +/-15%. Processing completed. |
| P | DONE | Authenticated Range media streaming through Electron; renderer never receives the token or a whole-file Blob. Actual 4 GiB player fixture passed. |
| L | DONE | Purge paused-Undo records on restart without touching files; recover missing analysis for queued jobs and show finished details without it; log all learning exceptions while cleanup continues. |
| Q | DONE | Real-engine progress cadence and service CPU measurements passed; 5000-record result reported below. |
| O1 | DONE | Ranked lock order 10/20/30, test inversion checks, cached event publication, no shell/file I/O under service state locks; async per-file journalled removal, replay, live SSE and bounded graceful exit. |
| O2 | DONE with measured limits | Per-file errors, root/screen/dialog boundaries and real Reload; SDR BT.2020nc preserved, HDR blocked, source size never silently reduced. 4K-source Standard on 8 GB blocked with Fast guidance after measured failures. |
| O3 | DONE | Core NVDEC presentation-timestamp decoding and indexed seek; full-geometry container tests, native decoded sample equality and packet-based audio timing. |
| O4 | DONE with qualification limit | Immediate network progress, real transferred bytes, smoothed rate, weighted phases and explicit unknown ETA; unchanged verified weights avoid repeated hashing, changed files reverify. Network gates passed; these were not real GPU qualification timings. |
| O5 | DONE | Compare labels outside images, no divider handle, horizontal scroll, per-model progress and wait reason; labels remain visible below the title bar in full-window mode. CDP pinch passed. |
| O6 | DONE | Unified three-choice History removal, Select all, right-side Select, attention-only badges and actual per-file results. |
| O7 | DONE | Tutorial at right; compact Models tabs/count/actions; dismissible notices; per-file Add options; gear Settings, role-appropriate icons, no literal plus in Add videos/Add hours; Below Normal worker priority. |
| O8 | PARTIAL historical evidence | Live prediction fixed and rerun in E. Original 50% packets do not exist; reconstructed counterfactuals are not observations. |
| O9 | PARTIAL experiments | Bounded external prototypes measured below; no experimental optimization shipped. Compile failed; TensorRT unavailable. |
| G | PARTIAL | Final-source CPU/GPU, GUI, package, native and CI results below. Physical owner-only checks remain NOT RUN. R acceptance remains failed. |

## Owner stall and additional 1440/4K checks

The original job stopped advancing, hit its watchdog, retried and later errored. A subsequent cancel was separate. Its child logs and working folder are gone, so the root cause is NOT ESTABLISHED. SSE WinError 10053 only establishes a disconnected connection. An nvlddmkm Event 153 GPUID field is not proof of CUDA error 700 or a driver fault.

Confirmed conditions: H.264 MP4, 960x540, 30000/1001 fps, Standard, 1440p output. The synthetic source uses B-frames and AAC. Reproduction 1 failed after 7.548847 seconds at frame 1: new exact timestamp validation exposed DTS-like SimpleDecoder timestamps. Native pixels matched CPU at six sampled indices. Core packet Decode/Flush now yields presentation timestamps, seeks earlier and decodes forward, validates requested PTS, and owns converted CUDA surfaces before native reuse. This corrects an observed implementation issue, not a proven cause of the owner's historical hang.

Reproduction 2 at 1080p passed in 495.8496506 seconds, 3 parts, zero fallback/OOM retries. It was not the exact owner output setting. The subsequent exact-setting and requested 4K checks:

| Output / mode | Input seconds | Total seconds | Parts | Retry/fallback counters | Video/audio validation |
| --- | ---: | ---: | ---: | --- | --- |
| 2560x1440 Standard | 60.06 | 644.7429691 | 5/5 | All seven counters 0 | PASS, 3600 frames, 60000/1001 fps, audio delta 0 s |
| 3840x2160 Standard | 120.12 | 3843.0876062 | 26/26 | All seven counters 0 | PASS, 7200 frames, 60000/1001 fps, audio delta 0 s |
| 3840x2160 Fast | 120.12 | 1075.7299257 | 7/7 | All seven counters 0 | PASS, 7200 frames, 60000/1001 fps, audio delta 0 s |

Counters: interpolation fallback, internal OOM/NaN/corruption retry, corruption fallback, parent watchdog retry and parent OOM retry. All monitoring completed without errors. Missing failed-child statistics would remain unknown rather than assumed zero.

| Case | Torch reserved peak GB | Torch allocated peak GB | Max per-PID dedicated sample GB | Max per-PID shared sample GB | Device sample max GB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1440 Standard | 6.5305 | 3.3817 | 4.0009 | 0.1338 | 7.2375 |
| 2160 Standard | 14.5542 | 7.4188 | 7.9127 | 6.4083 | 8.5277 |
| 2160 Fast | 5.3247 | 4.3260 | 5.7525 | 0.1923 | 6.3184 |

Standard completed with substantial shared-memory pressure; Fast had more headroom and was about 3.57x faster in total time. This is not a quality-equivalence comparison or a guarantee for arbitrary long real videos/concurrent GPU workloads. Evidence: each `D:\VideoEnhancer-P1e-2\{owner-1440-1,standard-2160-1,fast-2160-1}\home\measurement.json`, progress packets, NVML samples and job logs. A Japanese private summary is `C:\Users\pro\Documents\VideoEnhancer-P1e-2\4K-output-check-ja.md`.

## E/F: every gated attempt and independent fit

| Attempt | Result | Expected / actual and limitation |
| --- | --- | --- |
| gate-10min-1 | Setup FAIL; GPU NOT RUN | Invalid synthetic schedule minute 76. |
| gate-10min-2 | FAIL | Part 6/44 watchdog twice; wall 1822.031 s, completed-part sum 894.27958 s, analysis 18.86194 s. Last device sample 8.1984 GB; not a proven peak/cause. |
| gate-10min-3 | Setup FAIL; GPU NOT RUN | Midnight assertion in evidence helper. |
| gate-10min-4 | FAIL | Part 9 native 0xC0000005 during our timed faulthandler dump; WER python312.dll/PyCode_Addr2Line. Diagnostic fault suspected, not proven CUDA/RIFE failure. Removed timed native dumps, retained fatal handling and GIL-protected heartbeat diagnostics. CPU stress: five normal exits, NOT REPRODUCED. |
| gate-10min-5 | PASS before Core decoder change | 44 parts; initial 7875.2096209 s, parts 7900.474365 s, analysis 20.6653866 s, finalization 12.98598 s. Active work including analysis 7934.1257316 s, initial error -0.743%. Wall 8985.453 s with 15-minute second-half gap. |
| gate-10min-6 | Final-source result below | Fresh isolated home, final Core decoder and persisted finalization steps. |

Gate 5 first finish forecast error -148.379864 s. Live errors: 25% +554.34824 s/+7.998576%; 50% +2.81601 s/+0.057279% (PASS +/-5%); 75% +164.645327 s/+8.438491%. Finalization predicted 12.2235667282 s vs actual 12.98598 s, -5.871049% (PASS +/-25%). Its old private evaluation excludes analysis and gives -0.483% initial error; that is a different denominator. Its per-step fields were lost on reload; persistence was then fixed and tested.

Independent finalization fit used real Standard planner part counts, repeated synthetic reference output, AAC and cloned real quality partials. These are finalization fixtures, not 120-minute neural inference runs, and the gate clip was not a fit point.

| Length | Parts | Output GB | Measured finalization s |
| --- | ---: | ---: | ---: |
| 1 minute | 5 | 0.241988 | 1.192158 |
| 30 minutes | 125 | 7.2666 | 32.5413765 |
| 120 minutes | 499 | 29.0662 | 324.2433134 |

Built-in nonlinear points include 15% margin; local correction is length-class specific. Admission reserves `1.5 * prediction + 60 s`. A validated joined-file checkpoint can be reused after abort.

Independent finalization-only replay PASS, no inference rerun, not used for fitting:

| Step | Seconds |
| --- | ---: |
| Checkpoint validation | 0.1044874 |
| Concat | 3.2027082 |
| Faststart | 5.4237987 |
| Audio mux | 0.9252822 |
| Validation | 0.9067354 |
| Quality aggregation | 0.0690767 |
| Measured finalization observation including surrounding overhead | 13.126557 |

Faststart dominated this replay. Final gate 6 step values are reported separately below.

## R calibration and both acceptance runs

Independent 5-second 720x1280 reference to 2160x3840: Standard 245.377396 s, Torch reserved 14.277 GB/allocated 7.5209 GB, zero OOM/fallback; Fast 48.670573 s, reserved 5.144 GB/allocated 4.2879 GB. Isolated RIFE at 2160: median 1.924308 s per 8 pairs, reserved 7.03385 GB. No unrecorded peak fields are inferred.

Encode geometry completion: three direct NVENC repeats per 1080/2160 geometry, all HEVC/H.264/AV1 measured. HEVC median coefficients: 2.5921191808379733e-9 and 2.5221693753290355e-9 seconds/pixel/frame. Timing includes encoder flush. Re-normalizing pipeline factors preserved all four original reference predictions within 1 microsecond. Calibration color axis now agrees with estimator input+2*output pixels; progress remains monotonic. Profile revision: `p1e2-stage-sizes2`.

| 30-second portrait Standard gate | Initial s | Actual s | Error | Result |
| --- | ---: | ---: | ---: | --- |
| Before final Core decoder | 1481.0422258 | 1334.0419923 | +11.019% | PASS +/-15% |
| Final Core decoder, fresh home | 1481.0422258 | 1222.1590949 run_queue wall | +21.182441% | FAIL +/-15% |

Final run completed all 8 parts: part sum 1218.317415 s, finalization 1.813458 s; using parts+finalization gives +21.383883%, also FAIL. Acceptance data was not used to refit coefficients. Further calibration policy is a designer question; conservative independent measurements remain in place.

## P, Q, O1-O8 and indexed-decode evidence

- Player: actual Electron with dense 4 GiB free atom before high-offset mdat, not 4 GiB of video essence. Play 320 ms, 90% seek 116.8 ms, renderer private-memory increase 30.875648 MB: PASS (1 s/1 s/200 MB gates). Fullscreen 105 ms/111.3 ms/22.55 MB: PASS. First fullscreen fixture click was occluded and failed; corrected fixture passed. Own media server authenticated shutdown returned 200.
- Q: real GPU job plus 1000 rich records, service CPU in one-core units median 1.6128896723%, p90 1.9757789909%: PASS <=5%. 5000 records median 3.3265805174%, initial projection 0.0001184 s. Renderer 0.9664959 Hz over 30.0053 s, >=95% cadence target and >=1000 ms paint gaps: PASS. These were before Core; service/renderer cadence code is unchanged by Core.
- O1: HTTP three-record slow shell fixtures (2 s/file), POST <1 s and live SSE gaps <=2 s: PASS for remove/clear. Native NTFS sequential and bulk recycle/restore SHA-256: PASS; bulk used three shell calls, not a single COM batch. Journal replay preserves each completed outcome. Graceful exit waits up to 20 s; no force-exit of an active shell operation.
- O2 source-4K: Standard both orientations FAIL around 602.9 s, watchdog twice, sampled Torch reserved about 22 GB/shared about 15 GB, no OOM exception. First attempt overlapped another GPU workload and is not clean attribution evidence. Fast both orientations PASS 94.61/94.87 s, reserved 6.0985 GB, zero fallback/OOM. The explicit specified 8 GB source-4K Standard guard guides users to Fast. This is separate from successful smaller-input 4K output above.
- O3: 35 CPU container variants and 70 full-geometry GPU Standard/Fast variants; H.264/VP9/AV1, MP4/WebM/MKV, rotation/rates/VFR/audio offset/short/no-audio. Native NV12 samples and indexed seeks match; packet audio deltas within +/-20 ms, waveform tests PASS. GPU tests use real full-HD geometry. Unsupported software encoder availability reports a plain error.
- Core source-index regressions: 13 PASS 97.97 s; fake Core ownership/PTS contract 2 PASS 1.47 s. Initial absent-basetemp invocation: 13 setup ERRORS, GPU NOT RUN. Final Core 2-hour source cost: 6.931183767 GB, 216000 frames/1440 keyframes; prior metadata analysis 15.1887 s, decoder open 0.1473437 s, last-frame seek/decode 0.1357776 s. Old SimpleDecoder measurements (0.159914 vs 11.698669 s open modes) do not describe final Core.
- O4: all three local 100 MiB download paths at 2 MiB/s PASS. Max progress gaps 0.515/0.500/0.266 s; first positive 0.562/0.531/0.437 s; monotonic. ETA errors at 10 SECONDS +11.458/+10.938/+11.299%. Private JSON key incorrectly says 10_percent; helper actually samples at 10 s. Predicted GPU allowance 4.4917327 s, not actual GPU qualification. Contrast 11.3853:1 filled/14.5843:1 unfilled both themes. Unchanged verified weights avoid repeated hashes; changed weights and explicit Verify rehash; executable source archives still reverify.
- O5-O7 actual visual coverage: both sizes/themes, Add per-row failures/settings, screen error/Reload, Models, Schedule, History removal, Settings gear, Compare normal/full labels. Final visual-9 PASS, 92 PNGs at `C:\Users\pro\Documents\VideoEnhancer-P1e-2\gui-evidence\visual-9`. Visual-6 initially failed 476<480 portrait height; spacing corrected. Visual-7 passed automated checks but inspection caught title overlap; reserved title-bar area and added assertion; visual-8/9 passed. No unsupported claim of physical touchpad or Windows scaling checks.
- O8 historical copied metadata: initial 4605.684584 s, first finish about 8m15s late, parts 3118.499047 s, wall 4076.937614 s. Historical 50% packets unavailable. Uniform-within-part remaining-time counterfactual old 1555.8924/new 1547.13471 s uses final profile; not an observed result or acceptance evidence.

## Verification, failures and intentional omissions

| Check | Result |
| --- | --- |
| Final CPU all-8, fresh NTFS home, CUDA hidden | PASS: 421 passed, 3 skipped, 101 GPU deselected, 696.38 s |
| After measured profile write: bench/estimate/P1e2 | PASS: 40 passed, 30.87 s |
| Ruff / format / Pyright | PASS: all checks, 124 files formatted, 0 errors/warnings |
| GUI lint/typecheck/build | PASS; build warns main chunk about 522 KB exceeds 500 KB |
| GUI unit tests | PASS: 42 tests, 6.34 s |
| Normal Electron final e2e | PASS: 6 passed, 7 opt-in cases skipped, about 1.3 min |
| Visual final | PASS: visual-9, 25.5 s, 92 screenshots |
| Packaged Electron final smoke | PASS: actual executable, external engine discovered without override, sandbox/contextIsolation true, nodeIntegration false, renderer require undefined, app origin, graceful service shutdown |
| D2 CPU | PASS: 3 hard crashes, all 10800 frame hashes identical, no temporary files, 159.109 s |
| D2 CUDA | PASS: 3 hard crashes, all 10800 ten-bit frame hashes identical, no temporary files, 146.937 s |
| Final GPU retry | PASS: 35/35, 1747.71 s, explicit file log and JUnit XML, no skips |
| Prior GPU container recovery | 66 completed cases with output and no entry in completed pytest failure cache; combined coverage 101 GPU cases, not a captured single-run 101-PASS terminal summary |
| Corrected-source Windows/Ubuntu CI | PASS: 4/4 push/PR matrix jobs on d1d54ad; final report/test-only head verified separately |

Earlier test runs are not silently replaced by passes:

- CPU all-4: 415 PASS/3 SKIP, 698.53 s, before additional regressions. All-5 on exFAT: 399 PASS/21 FAIL/3 SKIP, 737.94 s; unsupported hardlinks, epoch timestamp operation, cache mtime and a missing CUDA device-properties mock. Repeated on NTFS. All-6: 419 PASS/1 FAIL/3 SKIP, 730.33 s; explicit 8 GiB mock corrected, targeted rerun PASS 1.88 s. All-7: 420 PASS/3 SKIP, 699.25 s. Final all-8 above includes added benchmark case.
- GPU suite 1 interrupted to repair timestamp regression. Suite 2 ended exit 1 but Windows inherited child stdout was lost: original traceback/summary NOT AVAILABLE. Four landscape60 AV1 fixtures were incomplete (WebM 385/600 and 408/600 frames; MP4 missing moov). The incomplete fixtures and the controlled 83-second run support a fixture-generation timeout diagnosis; original exception text cannot be confirmed. Optional fixture timeout 180 s; controlled generation PASS 600/600 in 83.4346584 s. Application watchdog unchanged. Recovered 66 cases from outputs/cache; all other 31 GPU cases plus the four incomplete cases explicitly reran as 35 PASS with XML. Logs: `logs/gpu-tests-2-recovery.json`, `logs/gpu-tests-3.log`, `D:\VideoEnhancer-P1e-2\gpu-tests-3\home\results.xml`.
- Earlier GUI e2e failed stale selectors/competing trace directory; corrected serialized run passed. GUI visual failures and correction are listed above.
- Physical touchpad gestures, actual Windows display scaling, reboot/tray behavior and owner media verification: NOT RUN. CDP gesture/actual Electron evidence is not a substitute for those physical checks. Full optional Settings calibration UI operation: NOT RUN. Long finalization fixtures are not long neural-inference stability tests. No optimization candidate shipped.

## Package and reproduction

Launch: `D:\VideoEnhancer-P1e-2\packages\p1e2-final\VideoEnhancer-win32-x64\VideoEnhancer.exe`.

Unsigned folder package, rebuilt after final GUI changes. It depends on the external Python engine checkout, not a standalone bundled engine. Engine/home/Python/FFmpeg overrides remain documented. Never point verification at the owner's normal home.

Reproduce CPU/static checks with `.venv/Scripts/ruff.exe check .`, `.venv/Scripts/ruff.exe format --check .`, `.venv/Scripts/pyright.exe`, then an isolated NTFS `VE_HOME`, `CUDA_VISIBLE_DEVICES=-1`, and `.venv/Scripts/python.exe -m pytest -m "not gpu" --basetemp=<fresh-home>/tests`. GPU tests need a fresh qualified model fixture via `VE_GPU_TEST_MODEL_HOME`; run `pytest -m gpu` sequentially with explicit stdout/JUnit paths. Native shell cases are opt-in and use only test-created guarded files. GUI scripts: lint, typecheck, test, build, test:e2e and package in `gui`.

Additional synthetic owner/4K jobs use CUDA, HEVC, 2x fps, short_side 1440/2160, Standard/Fast and the sources described above. External benchmark/evidence drivers are preserved under the evidence directory, not shipped as public application code. All source changes are recorded in the file list below.

## Questions for the designer and defaults used

1. Final built-in 2160 initial estimate is conservative by 21.18%, failing +/-15%. Keep independently measured coefficients and report FAIL; do not fit the acceptance clip. Decide further calibration/review.
2. Optional speed calibration still has the existing small linear finalization calibrator and can replace the improved built-in long-duration curve. No new calibration policy invented. Decide whether/how that flow should use realistic long-duration points.
3. The original owner's stall cannot be attributed without child logs. No speculative global GPU lease/admission architecture shipped. Keep current limits and the measured safeguards; retain original-cause uncertainty.
4. O9 isolated gains are single runs; compile failed and TensorRT unavailable. No quality/performance policy chosen and no candidate shipped. Designer can select a follow-up based on evidence.


## Final-source E/F gate 6

Signed error is prediction minus actual; positive means a late/long prediction. Live percentages use actual remaining wall time, including the scheduled gap. Initial work includes analysis, completed-part times and finalization. Wall time also includes admission waits and control overhead.

| Measurement | Value | Gate | Result |
| --- | ---: | --- | --- |
| Initial work prediction | 7875.209621 s | +/-10% | PASS |
| Actual active work | 7769.417035 s | Report | PASS |
| Initial work error | +1.361654% | +/-10% | PASS |
| First finish error | +55.904472 s / +0.636751% | +/-10% | PASS |
| Finalization error | -1.015840% | +/-25% | PASS |

44/44 parts; segment sum 7737.482328 s, analysis 19.585694 s, wall 8779.639844 s. All seven retry/fallback counters zero. The gap 2026-10-15T21:15:00+09:00 to 2026-10-15T21:30:00+09:00 occurred at 56.737196% progress and resumed automatically. Final output finished 2026-10-15T13:26:15.890191+00:00.

| Nominal milestone | Packet percent | Actual remaining s | Finish error s | Error % | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| 25% | 24.994444% | 6809.153202 | -24.605038 | -0.361352% | Report only |
| 50% | 49.988889% | 4869.876785 | -24.232983 | -0.497610% | PASS +/-5% |
| 75% | 74.983333% | 1949.139831 | -4.144499 | -0.212632% | Report only |

The service wire packet and snapshot are sampled asynchronously; table values use the preserved wire packet, whose percent may be about one heartbeat below the nominal snapshot crossing. Deterministic same-data packet/snapshot tests pass within 1 s; this does not assert every asynchronously sampled forecast is identical.

| Finalization step | Actual seconds |
| --- | ---: |
| checkpoint_validation_seconds | 0.2260843 |
| concat_seconds | 3.4059004 |
| faststart_seconds | 3.0183264 |
| mux_seconds | 2.5927270 |
| validation_seconds | 0.8929823 |
| quality_aggregation_seconds | 0.0388409 |

Finalization predicted 12.2235667 s; observed 12.3490130 s including surrounding control overhead. Concat was the largest named step, followed by faststart and mux. Step sums are not substituted for the measured observation. Evidence: `D:\VideoEnhancer-P1e-2\gate-10min-6\home\result.json`, `C:\Users\pro\Documents\VideoEnhancer-P1e-2\final-gate-evaluation.json`.


## O9 measured candidates (pre-Core decoder, external-only prototypes)

| Case | Wall s | Input fps | Speedup | Torch reserved GB | Max RGB8 difference | PSNR dB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| busy-standard-5 | 72.554 | 2.0674 | reference | 4.1104 | reference | reference |
| busy-fast-5 | 15.678 | 9.5677 | reference | 1.5896 | reference | reference |
| busy-standard-60 | 781.268 | 2.3039 | reference | 4.4585 | reference | reference |
| baseline | 66.324 | 2.2616 | reference | 3.8839 | reference | reference |
| keep-c1 | 64.161 | 2.3379 | 1.033720x | 4.6284 | 0 | infinity |
| fewer-rife-syncs | 66.262 | 2.2637 | 1.000941x | 3.9615 | 0 | infinity |
| unowned-overlap | 64.159 | 2.3380 | 1.033757x | 4.0999 | 0 | infinity |
| cudnn-benchmark | 72.980 | 2.0553 | 0.908800x | 5.9286 | 255 | 41.8587 |
| channels-last | 61.693 | 2.4314 | 1.075071x | 3.5735 | 255 | 42.5968 |
| priority-normal | 66.305 | 2.2623 | 1.000295x | 4.0014 | 0 | infinity |
| clip-21 | 60.573 | 2.4763 | 1.094949x | 5.2345 | 255 | 35.8418 |
| clip-30 | 57.191 | 2.6228 | 1.159709x | 7.1010 | 255 | 35.8742 |
| torch-compile | failed | | | | | |
| streams baseline (final Core) | 69.524 | 2.1575 | reference | 3.9909 | reference | reference |
| separate-cuda-streams (final Core) | 65.957 | 2.2742 | 1.054070x | 4.1649 | 0 | infinity |
| torch-tensorrt | NOT RUN | | | | | |

All comparisons cover all 300 output frames. Single runs, not a statistical throughput claim.
GPU utilisation is device-wide; mean utilisation is not the same as nonzero-sample busy share.
The original results contain both metrics and phase-labelled zero-utilisation samples.
Threaded inclusive stage timers cannot uniquely attribute idle intervals to decode/sync/encode.
Warm-worker saving bound: 4.3946036 s/part, 528-part 2 h Standard planner =2320.3507 s.
This is a theoretical reusable-startup bound, not a measured warm-worker implementation.
Default Compare one-preview bound 4.3946 s; three previews sharing one worker bound8.8331 s.
First memory sample3.1819377 s is separately measured, not included in that reusable bound.
Torch compile failed (TritonMissing); TensorRT unavailable, deformable-convolution support not tested.
Streams experiment completed after the GPU suite using final Core; its speedup uses its own 69.524 s baseline. Other rows predate Core. No candidate ships.

### O9 utilization and interpretation

| Workload | Mean device GPU utilization | Nonzero sample share | Share >=50% | Share >=90% |
| --- | ---: | ---: | ---: | ---: |
| Standard 5 s | 75.4547% | 100% | 77.1353% | 70.5650% |
| Fast 5 s | 45.1927% | 100% | 46.354% | 46.354% |
| Standard 60 s | 90.3584% | 100% | 92.549% | 85.787% |

Nominal 10 Hz NVML samples are device-wide. Nonzero samples include background GPU activity and cannot establish exclusive neural-inference busy time. Exact exclusive idle attribution by decode/synchronization/encode is NOT MEASURED; inclusive overlapping thread timers cannot provide it. No dominant idle cause is invented.

Startup terms sum 7.5799984 s: parent/IPC 0.849644, child entry 1.325694, decoder 0.003457, model loading 2.073262, weight verification 0.120757, CUDA initialization 0.025247, first PDH memory sample 3.181938. The proposed reusable bound excludes first PDH sampling and decoder creation. It is not an implemented or measured warm worker. Clip-21 minimum frame PSNR 31.4098 dB; clip-30 31.2323 dB; channels-last 37.4905 dB; cuDNN benchmark 34.6969 dB. Changed-output gains do not establish acceptable quality. Normal-priority improvement is only about 0.03% in one run and is not evidence to change priority. Streams/keep-C1/ownership variants justify possible follow-up measurements, not automatic adoption.

Evidence: `D:\VideoEnhancer-P1e-2\speed-1\results.json`, `D:\VideoEnhancer-P1e-2\speed-streams-1\results.json`, `C:\Users\pro\Documents\VideoEnhancer-P1e-2\o9-compact.json`, `o9-utilisation-distribution.json`. O9 experiments were bounded within the authorized 2-hour active-measurement budget; queue waiting and other acceptance jobs are not claimed as O9 experiment time.

## Changed files

- `.ai/CURRENT_TASK.md`
- `.ai/LAST_REPORT.md`
- `docs/API.md`
- `docs/GUI.md`
- `docs/TROUBLESHOOTING.md`
- `gui/electron/main.cjs`
- `gui/electron/permissions.cjs`
- `gui/electron/preload.cjs`
- `gui/src/ActionButton.tsx`
- `gui/src/App.tsx`
- `gui/src/ErrorBoundary.tsx`
- `gui/src/HistoryDetail.tsx`
- `gui/src/HistoryRemoval.tsx`
- `gui/src/Home.tsx`
- `gui/src/Notice.tsx`
- `gui/src/Pages.tsx`
- `gui/src/Queue.tsx`
- `gui/src/ScheduleView.tsx`
- `gui/src/Tour.tsx`
- `gui/src/Trial.tsx`
- `gui/src/VideoFilesDialog.tsx`
- `gui/src/api.ts`
- `gui/src/focus.ts`
- `gui/src/history.ts`
- `gui/src/main.tsx`
- `gui/src/style.css`
- `gui/src/types.ts`
- `gui/tests/add-models.test.tsx`
- `gui/tests/e2e/desktop.spec.ts`
- `gui/tests/e2e/p1e-visual.spec.ts`
- `gui/tests/e2e/p1e.spec.ts`
- `gui/tests/error-boundary.test.tsx`
- `gui/tests/events.test.tsx`
- `gui/tests/home-schedule.test.tsx`
- `gui/tests/notice.test.tsx`
- `gui/tests/perf/prepare_service.py`
- `gui/tests/perf/real-progress.spec.ts`
- `gui/tests/permissions.test.tsx`
- `scripts/verify_resume.py`
- `src/videoenhancer/bench/basicvsr.py`
- `src/videoenhancer/bench/calibration.py`
- `src/videoenhancer/bench/reference.py`
- `src/videoenhancer/bench/rife.py`
- `src/videoenhancer/bench/runner.py`
- `src/videoenhancer/estimate/classes.py`
- `src/videoenhancer/estimate/live.py`
- `src/videoenhancer/estimate/local.py`
- `src/videoenhancer/estimate/model.py`
- `src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json`
- `src/videoenhancer/jobs/checks.py`
- `src/videoenhancer/jobs/gpu_memory.py`
- `src/videoenhancer/jobs/store.py`
- `src/videoenhancer/media/analyze.py`
- `src/videoenhancer/media/color.py`
- `src/videoenhancer/media/decode.py`
- `src/videoenhancer/media/encode.py`
- `src/videoenhancer/media/mux.py`
- `src/videoenhancer/media/probe.py`
- `src/videoenhancer/models/download.py`
- `src/videoenhancer/models/manifests/basicvsrpp-denoise.json`
- `src/videoenhancer/models/manifests/basicvsrpp-ntire21-decompress.json`
- `src/videoenhancer/models/manifests/basicvsrpp-track1.json`
- `src/videoenhancer/models/manifests/basicvsrpp-track2.json`
- `src/videoenhancer/models/manifests/drunet-deblock.json`
- `src/videoenhancer/models/manifests/fbcnn-color.json`
- `src/videoenhancer/models/manifests/rife-4.25-lite.json`
- `src/videoenhancer/models/manifests/rife-4.25.json`
- `src/videoenhancer/models/manifests/rife-4.26.json`
- `src/videoenhancer/models/manifests/scunet-real-psnr.json`
- `src/videoenhancer/models/manifests/span-liveaction-2x.json`
- `src/videoenhancer/models/registry.py`
- `src/videoenhancer/models/rife_variants.py`
- `src/videoenhancer/pipeline/runner.py`
- `src/videoenhancer/proc.py`
- `src/videoenhancer/schedule/admission.py`
- `src/videoenhancer/schedule/controller.py`
- `src/videoenhancer/service/compare.py`
- `src/videoenhancer/service/deletion.py`
- `src/videoenhancer/service/downloads.py`
- `src/videoenhancer/service/engine.py`
- `src/videoenhancer/service/locks.py`
- `src/videoenhancer/service/media.py`
- `src/videoenhancer/service/operation.py`
- `src/videoenhancer/service/server.py`
- `tests/conftest.py`
- `tests/test_bench.py`
- `tests/test_controller.py`
- `tests/test_media.py`
- `tests/test_p1c4.py`
- `tests/test_p1d3.py`
- `tests/test_p1e.py`
- `tests/test_p1e2.py`
- `tests/test_p1e2_containers.py`
- `tests/test_pipeline.py`
- `tests/test_reliability.py`
- `tests/test_service.py`

## Git and CI

Implementation commit `d51a2a6dc21e7635d48874b6c5825f606417b417` was pushed and its remote SHA verified. Initial push/PR CI failed on all four Windows/Ubuntu jobs at Pyright: the CPU environment does not install optional `gdown`, and the new Drive helper imported it directly. Logs: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38742996096 and https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38743003081 .

Corrected the optional dependency to runtime `import_module`, preserving lazy model-download behavior without adding a mandatory dependency. Ruff/format/Pyright passed; related CPU tests passed 54/54 (2 GPU deselected), 58.78 s. This import-only correction does not change inference/encoding. The preceding 421-test full CPU run and GPU measurements remain scoped to the implementation before this import correction; fresh CI on the corrected source is required below. PR remains draft; no merge. Corrected source `d1d54ad373de3af9ce640538221cb47d2f83f817`: PASS 4/4 jobs (push and pull_request x Windows and Ubuntu). Push run: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38743617701 . PR run: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38743625955 .

Push matrix results: Windows CPU 420 PASS/4 SKIP/101 GPU deselected, 948.70 s; Ubuntu CPU 419 PASS/5 SKIP/101 GPU deselected, 402.80 s; GUI units 42 PASS on both; Windows Electron 6 PASS/7 opt-in SKIP, 1.9 min. Ruff, format, Pyright, lint, typecheck and build all PASS. Windows CPU emitted one CUDA-device-count warning on its no-GPU runner; setup actions emitted Node deprecation warnings and the GUI retained the documented chunk-size warning. These are warnings, not GPU evidence.

The subsequent report-only head `dc025804daa81c3ba855fe9566fec75e4685a029` exposed a test timing assumption: Ubuntu push CI had 418 PASS/1 FAIL/5 SKIP, with `test_cpu_queue_sse_controls_and_completed_output` expecting the first cached SSE snapshot to contain newly added jobs. The Ubuntu PR job passed. Failed job log: https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38746899152/job/116462795637 .

Publication intentionally refreshes asynchronously about every 0.5 seconds, so the first snapshot may precede a completed mutation. The integration test now waits up to 5 seconds for an update containing both jobs, and requires exactly two rows before accepting all-done (avoiding vacuous truth on an empty queue). No service/runtime behavior changed. Related service/P1e2 tests: 29 PASS, 49.01 s; the affected HTTP/SSE integration then passed five fresh-home repetitions (16.10/15.04/16.02/15.02/15.13 s). Ruff/format/Pyright PASS. This is a correction of a test assumption, not a retry that hides the failed run.

The final commit contains only this report and that integration-test correction relative to the previously checked source. Its four final-head checks and exact SHA are verified in the final delivery and saved outside Git under the evidence root, avoiding a self-referential report commit. The worktree was clean after the source push; origin/main remains efb45e307d65a9a6e0af4b37f95dd786acdd32c6, already an ancestor. No merge was needed. No further implementation or optimization cycle was started.
