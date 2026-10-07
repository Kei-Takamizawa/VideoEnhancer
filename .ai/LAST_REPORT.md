# VideoEnhancer Cycle P1a-5 Report

- **Task ID / Cycle:** VE-P1a-5
- **Status:** COMPLETED
- **Validation date:** 2026-10-07 UTC (2026-10-06 local PDT)
- **Branch:** `p1-restoration-gui`
- **PR:** [#2](https://github.com/Kei-Takamizawa/VideoEnhancer/pull/2) remains a draft.
- **Continuation:** Completes the previously partial P1a-5 cycle; implementation/model/preset defaults remain within the supplied task.

## Summary and acceptance

Task B is complete: every requested D2 candidate was evaluated, speed and memory were measured, and two labeled five-panel review videos were produced outside the repository. No new candidate improved both PSNR-Y and SSIM-Y over C1 in both clips. This objective comparison does not establish visual quality. No default preset was changed.

During completion, the external frame-model helper's RGB-to-YUV output was found to lack explicit BT.709 conversion and matching color metadata, whereas original/C1 use limited-range BT.709. C2/C8/C10 were regenerated with `scale=in_range=pc:out_range=tv:out_color_matrix=bt709` and matching color tags, followed by new metrics and review ranking. Earlier draft numbers from that helper are invalid for the matched-color comparison and were replaced. A no-model single-frame roundtrip confirms that the two conversion settings produce different Y samples; its evidence is outside Git.

Task A includes the existing host-buffer NVENC safety path and handoff retry/fallback, plus two corrections made during this continuation: the NVENC benchmark still selected GPU-input mode while passing a host NumPy buffer; and the handoff detector could miss an in-range white frame at a clip endpoint. The benchmark now selects host-input mode, and the detector uses aligned source summaries where an output neighbor is unavailable. Actual encoder-input pixel assertions fail with historical code and pass with the corrections.

| Criterion | Result | Evidence |
|---|---|---|
| A1 | PASS | Three identical Standard runs and queue 1/16 plus 20-second processing-target stress; native 10-bit hashes and detector results below. |
| A2 | PASS (review completed; internal SDK cause unexplained) | Historical comparison and ordering/ownership review below. |
| A3 | PASS | Retry/fallback pixel regressions pass; every completed final run has less than 2% measured check overhead. |
| A4 | PASS for deterministic handoff/input-contract regressions | Failing-before and passing-after logs; the specific nondeterministic SDK mosaic is not reproducible on demand. |
| A5 | PASS | Complete C2/C5/C8/C9/C10/C11 tables, deltas, chain speed and memory below. |
| A6 | PASS | Two external labeled review videos, frame count/probe and layout check. |
| A7 | PASS | Local lint/type/CPU/GPU checks pass; all four source-commit CI checks passed at `32d965e`. |

## A1: Final Standard repeatability and stress

Settings: sample-05, `standard`, CUDA, short side 1080, 2x fps, HEVC Main10, batch 2. The final external runner reuses the previously produced CLI manifest/segment plan and calls the production `process_segment` and `assemble` paths. It changes only queue size, output paths and job identifier. Every output frame is hashed after native `yuv420p10le` decoding, including all Y/U/V 10-bit samples; these are not 8-bit proxy hashes.

| Run | Queue | Processing target s | Segments | Frames | Detector flags | Retries / fallbacks | Check overhead |
|---|---:|---:|---:|---:|---|---:|---:|
| repeat-01 | 2 | 180 | 2 | 1822 | [189, 289, 387, 491, 587, 685, 787, 887, 1575] | 1 / 1 | 1.6357% |
| repeat-02 | 2 | 180 | 2 | 1822 | [189, 289, 387, 491, 587, 685, 787, 887, 1575] | 1 / 1 | 1.6235% |
| repeat-03 | 2 | 180 | 2 | 1822 | [189, 289, 387, 491, 587, 685, 787, 887, 1575] | 1 / 1 | 1.6207% |
| queue-01 | 1 | 180 | 2 | 1822 | [189, 289, 387, 491, 587, 685, 787, 887, 1575] | 1 / 1 | 1.6229% |
| queue-16 | 16 | 180 | 2 | 1822 | [189, 289, 387, 491, 587, 685, 787, 887, 1575] | 1 / 1 | 1.9154% |
| segments-20 | 2 | 20 | 12 | 1822 | [189, 289, 387, 491, 587, 685, 787, 887, 1575] | 1 / 1 | 1.4417% |

Repeat pair differing-frame counts: `{"1-2": 0, "1-3": 0, "2-3": 0}`. All three pairs have zero differing frames, so maximum per-frame MAE is exactly zero. All three complete encoded files also have identical SHA-256.

The normal runs contain 1,822 output frames each. The known detector indices are 189, 289, 387, 491, 587, 685, 787, 887 and 1575: eight previously reviewed source-cut signals and the known RIFE repair location. They are reported as raw detector signals, not silently counted as zero. Unexpected severe encoded corruption was not observed in the completed final runs. Detailed summaries, stage/frame events and manifests are in `completion/standard` outside the repository.

`--segment-seconds` is a **target processing duration** in the existing planner, not a literal media duration. The 20-second target plan creates 12 segments across the approximately 30.4-second source. This continuation preserves that planner behavior. The queue bounds are 1 and 16. No OOM occurred in these completed final runs.

Before the host-input change, one of three earlier direct-GPU-surface runs contained an encoded green/mosaic frame at output index 895. Run 1 vs run 2 differed in 621/1,822 decoded frames; mean of per-frame MAE 0.16182, maximum per-frame MAE 65.8279, maximum pixel difference 239. This is observational evidence of corruption, not a demonstrated driver/codec mechanism. Earlier post-host runs also matched, but the table above uses the latest endpoint guard and native 10-bit hashes.

Forced-restorer-FP32 comparison: **NOT RUN** because the pipeline has no force-FP32 option. The supplied task makes this conditional on an existing option. No new precision option was invented.

## A2: Historical code-path and ordering review

P1a-1 baseline `0ca2ba3` was verified from Git history. `media/decode.py` and `media/color.py` are unchanged from that baseline. The baseline encoder already called `torch.cuda.current_stream().synchronize()` before encoding, and queue handoffs already synchronized CUDA. Therefore an assertion that a newly added synchronization alone explains the disappearance would be incorrect.

The BasicVSR++ and RIFE stage files were imported but untracked at `0ca2ba3`; their exact historical bytes cannot be recovered from that commit. Their earliest tracked versions at `d0ecf9e` are byte-identical to the current tracked versions (BasicVSR++ blob `e172109633bb259ff0e74f89d12a909b24c368ec`; RIFE blob `65b2e20434e626152d18fbec96887d00e1c27e83`). No unsupported claim is made about the previously untracked copies.

| Place | Ordering / ownership evidence and limitation |
|---|---|
| NVDEC and color conversion | Conversion allocates RGB storage independent of the decoder's DLPack view; stacked batches synchronize before queue handoff. No application-managed decoder/output reuse pool was found. This does not prove undocumented SDK internals. |
| BasicVSR++ | Model outputs are new tensors. `.to(dtype)` can alias when the dtype already matches, but the model does not mutate that input. In-place activations apply to newly computed intermediates; features are local to each forward call, mirror-extension state resets and cache decisions are recomputed per clip. No output pool, `out=` write, or nonblocking copy was found in the reviewed application path. |
| RIFE | Concatenation/padding/model output and stacked frames own their computed data. In-place activations use new intermediates. The FP16 warp grid is constructed per call rather than reading the upstream shared FP32 grid cache. No shared-frame mutation was found. |
| Compute-to-encode queue | Advanced indexing selects owned frame storage; CUDA synchronizes before queue insertion. The producer does not mutate frames after enqueue. The queue holds tensor references until the consumer receives them. |
| Historical NVENC input | CUDA Array Interface plane views referenced the GPU surface; metadata included a fixed stream marker. Although the Torch stream synchronized first, the reviewed published API does not specify when an asynchronous GPU input may be rewritten safely. The specific low-level cause remains unknown. |
| Current NVENC input | Packed NV12/P010 conversion synchronizes and copies to a contiguous, owned CPU buffer; `CreateEncoder(..., True, ...)` selects host-input mode and Encode receives a contiguous uint8 NumPy representation. Models and color conversion still use CUDA; encoding still uses hardware NVENC. `EndEncode()` flushes before teardown. The benchmark helper now follows the same input contract. |

The host-buffer change removes direct application GPU-surface reuse from this interface and correlates with repeatable clean outputs. It does not prove a particular race, driver bug, FP16 overflow or SDK defect. The public [NVIDIA encoder API](https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-reference/encoder.html) confirms the CPU/GPU input-mode distinction and end-of-stream flush; its reviewed description does not establish GPU-buffer read-completion lifetime. The new summary guard and endpoint correction can prevent **detected compute-stage outliers** from reaching NVENC. They cannot detect arbitrary corruption introduced internally after that handoff.

## A3/A4: Guard, failing-before regressions and expected/actual behavior

Expected: an injected all-white frame must not be passed to `Encoder.write`; a transient bad result is recomputed once, and a persistent result is replaced with the nearest valid frame and reported. Actual: all seven focused safety regressions pass. The four injected-white cases assert 12 delivered frames and reject a maximum encoded-input mean of 0.95 or higher. Persistent corruption is tested at first, middle and last positions. The guard retains per-channel downscaled summary, source/neighbor comparison, NaN/Inf and range checks, retry/fallback counts and stage/frame events.

| Historical implementation | Expected fail-before result | Actual |
|---|---|---|
| Handoff before guard (`3280518`) | Transient/persistent injected-white input reaches encoder | 2 FAIL; actual maximum mean 1.0 |
| Handoff before endpoint fix (`eb72d75`) | Endpoint or later-clip endpoint white input escapes | 3 FAIL; actual maximum mean 1.0 |
| Encoder before host-buffer change (`3280518`) | Wrong GPU surface/input-mode contract | 2 FAIL |
| NVENC benchmark before host-mode correction (`eb72d75`) | NumPy input with GPU-input mode | 1 FAIL |
| Current implementation | Owned host input; injected corruption recovered | 7 PASS, 45 deselected, 9.40 s |

These are deterministic regressions of the actual handoff and input contract. They do not reproduce the original nondeterministic encoded mosaic inside NVENC. All-white tensor defects and endpoint blind spots are demonstrated causes; the original SDK-level artifact remains unexplained. Check overhead includes summaries, validation, retry checks and repair operations; final aggregate check seconds divided by segment processing seconds is reported per run above. A cheap summary cannot prove detection of every spatial corruption.

The 2% acceptance is evaluated over each complete Standard job. Individual-segment timing varies: the largest completed segment value is 2.1158% (queue-16, segment 0). This per-segment value is disclosed separately from the aggregate run values; a per-segment guarantee below 2% is not claimed.

## A5: Complete D2 results

## P1a-5: D2 candidate comparison

All rows use the same native 720x1280, 30000/1001 fps inputs and 150 aligned middle frames per clip. A uses frames 75–224 of a 300-frame window; B uses all 150 frames. Metrics use original Y samples, global PSNR-Y, FFmpeg local SSIM-Y, and the same temporal absolute-luma flicker ratio as the earlier cycle. Final image/model/filter outputs are encoded losslessly. The frame-model RGB-to-YUV conversion explicitly uses limited-range BT.709, matching the original and C1, and writes matching color metadata.

C5 applies C1 twice. C8 applies `realesr-general-x4v3` to **C1 output**, area-downscales to native size, then averages that result 50/50 with C1. C2 applies that Real-ESRGAN model directly to D2. C9 evaluates BasicVSR++ NTIRE Track 1 and its 50/50 average with C1. C10 evaluates color FBCNN (blind, predicted quality factor) and its 50/50 average with C1. C11 applies the light luma-only FFmpeg guard `deblock=filter=weak:block=8:alpha=0.098:beta=0.05:gamma=0.05:delta=0.05:planes=1` to C1.

These final rows supersede the earlier partial P1a-5 table: its C8 used the wrong input, C9 shortened the A inference window and discarded B scene cuts, C11 included additional output compression, and C5 B reused the wrong job statistics. During completion, missing BT.709 conversion settings in the frame-model measurement helper were also found; C2/C8/C10 were regenerated with explicit matching conversion and color metadata. All quality metrics were recomputed after these corrections.

| Clip | Candidate | PSNR-Y dB | SSIM-Y | Flicker ratio | Chain fps | Peak Torch reserved GB |
|---|---|---:|---:|---:|---:|---:|
| A | C0 | 30.422189 | 0.922811 | 0.878194 | N/A | N/A |
| A | C1 | 32.019490 | 0.941709 | 0.873134 | 2.693 | 4.438 |
| A | C2 | 30.177524 | 0.925506 | 0.904326 | 4.965 | 0.503 |
| A | C5 | 32.045918 | 0.942190 | 0.876662 | 1.377 | 5.518 |
| A | C8 | 31.683392 | 0.940269 | 0.894556 | 1.673 | 4.438 |
| A | C9 | 31.488161 | 0.937058 | 0.856883 | 2.814 | 5.646 |
| A | C9 + C1 (50/50) | 32.001280 | 0.940946 | 0.860422 | 1.332 | 5.646 |
| A | C10 | 30.395485 | 0.922887 | 0.874609 | 3.580 | 1.262 |
| A | C10 + C1 (50/50) | 31.586037 | 0.936610 | 0.863983 | 1.481 | 4.438 |
| A | C11 | 32.009161 | 0.941571 | 0.872710 | 2.553 | 4.438 |
| B | C0 | 31.719808 | 0.880273 | 0.827707 | N/A | N/A |
| B | C1 | 33.298938 | 0.911173 | 0.850196 | 2.884 | 5.069 |
| B | C2 | 31.368086 | 0.881302 | 0.842582 | 4.962 | 0.503 |
| B | C5 | 33.236867 | 0.910927 | 0.857712 | 1.446 | 5.069 |
| B | C8 | 32.803035 | 0.907104 | 0.866976 | 1.731 | 5.069 |
| B | C9 | 32.702202 | 0.901821 | 0.820138 | 2.976 | 4.901 |
| B | C9 + C1 (50/50) | 33.333362 | 0.910564 | 0.829191 | 1.403 | 5.069 |
| B | C10 | 31.722564 | 0.880653 | 0.827887 | 3.582 | 1.262 |
| B | C10 + C1 (50/50) | 33.035329 | 0.904903 | 0.827311 | 1.520 | 5.069 |
| B | C11 | 33.255236 | 0.910572 | 0.849084 | 2.680 | 5.069 |

Chain fps is frame count divided by the **sum of measured sequential step times**, including the measured C1 pass for multi-pass candidates and CPU blend/filter time. It is not an isolated CPU blending speed or a throughput prediction for a future combined pipeline. The standalone image-model timer includes decoding, inference and lossless encoding, and excludes model loading. C1/C5/C9 timers include their stage setup. Peak memory is the maximum measured Torch reservation of each sequential step, not the sum; it does not measure device-wide or NVENC memory. C10 alone fits the strict decimal 5 GB Torch-reservation limit in both clips; a C10+C1 blend also needs the C1 memory budget.

| Clip | Candidate | Δ vs C0 (PSNR / SSIM / flicker) | Δ vs C1 (PSNR / SSIM / flicker) |
|---|---|---:|---:|
| A | C2 | -0.244666 / +0.002695 / +0.026132 | -1.841966 / -0.016203 / +0.031193 |
| A | C5 | +1.623729 / +0.019379 / -0.001532 | +0.026428 / +0.000481 / +0.003528 |
| A | C8 | +1.261202 / +0.017458 / +0.016362 | -0.336098 / -0.001440 / +0.021423 |
| A | C9 | +1.065971 / +0.014247 / -0.021311 | -0.531329 / -0.004651 / -0.016251 |
| A | C9 + C1 (50/50) | +1.579090 / +0.018135 / -0.017772 | -0.018210 / -0.000763 / -0.012712 |
| A | C10 | -0.026704 / +0.000076 / -0.003585 | -1.624005 / -0.018822 / +0.001475 |
| A | C10 + C1 (50/50) | +1.163847 / +0.013799 / -0.014211 | -0.433453 / -0.005099 / -0.009150 |
| A | C11 | +1.586972 / +0.018760 / -0.005484 | -0.010329 / -0.000138 / -0.000423 |
| B | C2 | -0.351722 / +0.001029 / +0.014875 | -1.930852 / -0.029871 / -0.007614 |
| B | C5 | +1.517059 / +0.030654 / +0.030004 | -0.062071 / -0.000246 / +0.007516 |
| B | C8 | +1.083228 / +0.026831 / +0.039269 | -0.495903 / -0.004069 / +0.016780 |
| B | C9 | +0.982395 / +0.021548 / -0.007570 | -0.596736 / -0.009352 / -0.030058 |
| B | C9 + C1 (50/50) | +1.613555 / +0.030291 / +0.001483 | +0.034424 / -0.000609 / -0.021005 |
| B | C10 | +0.002756 / +0.000380 / +0.000179 | -1.576374 / -0.030520 / -0.022309 |
| B | C10 + C1 (50/50) | +1.315521 / +0.024630 / -0.000396 | -0.263609 / -0.006270 / -0.022885 |
| B | C11 | +1.535429 / +0.030299 / +0.021377 | -0.043702 / -0.000601 / -0.001111 |

### Models and metric-only selection

- C9 uses [MMagic BasicVSR++ compressed-video Track 1](https://github.com/open-mmlab/mmagic/blob/main/configs/basicvsr_pp/README.md), Apache-2.0 source. Checkpoint SHA-256: `7b2eba02a24989bfbf8b2ed4a06c8e6fd5dbeb193b1178ef7171cd1c455ddb0f`. It is an alternate challenge-track checkpoint with the same c128/n25 architecture, not a proven universally stronger setting. The existing pinned torchvision deformable-convolution adapter was reused; no custom CUDA extension was built.
- C10 uses [FBCNN](https://github.com/jiaxi-jiang/FBCNN), whose current official repository declares Apache-2.0. The external source is pinned at `2cd940856798e258beaa8f9181a1ffc32c9931f9`. Color-checkpoint SHA-256: `8b0e4ef23d59cf7ac934a342cb31a17619e4fa4a0b3374a9d78c5174312387e8`. It was chosen as a frame decompression candidate with a prebuilt-PyTorch implementation that fits the strict decimal 5 GB limit. Its JPEG training domain differs from D2 video compression; results including any regressions are reported.
- C11 lowers SSIM-Y versus C1 on both clips and is not recommended under the explicit task rule.
- For the review panels, candidates were ranked by mean SSIM-Y across A/B, then mean PSNR-Y. C2 is a reference baseline; C11 is excluded because it fails its non-regression rule. The top two new candidates are C5 and C9 + C1 (50/50).
- No new candidate improves both PSNR-Y and SSIM-Y over C1 on both clips. No visual-quality conclusion or default-preset change is made.

The external `owner-review-3` videos show Original / Degraded / C1 / C5 / C9 + C1 (50/50), using the same full 10.010 s and 5.005 s windows. Exact paths and reproduction commands are in `.ai/LAST_REPORT.md`.


## A6: External review evidence

- `C:\Users\pro\Documents\VideoEnhancer-P1a-5\owner-review-3\clip-A-D2.mp4`: 300 frames, 10.010 s.
- `C:\Users\pro\Documents\VideoEnhancer-P1a-5\owner-review-3\clip-B-D2.mp4`: 150 frames, 5.005 s.
- Both: 3600x1344, 30000/1001 fps, H.264 review encoding. Five panels are Original / Degraded / C1 / C5 / C9 + C1 (50/50); 64-pixel label strip above native-size panels.
- Probe output: `completion/review-videos.json`. Frame previews were viewed to check the five labels, frame alignment and composition only. No visual-restoration conclusion is claimed. App GUI interaction was **NOT RUN**; this cycle changes no GUI flow.

## A7: Executed validation and build

| Check | Actual result |
|---|---|
| `ruff check src tests` | PASS |
| `ruff format --check src tests` | PASS |
| `pyright` | PASS, 0 errors / 0 warnings |
| CPU suite, `-m "not gpu and not soak"` | PASS after CI polling-test correction: 121 passed, 3 skipped, 15 deselected, 46.98 s |
| GPU suite, `-m "gpu and not soak"` | PASS: 15 passed, 123 deselected, 38.72 s; executed before the later CPU-only polling-test correction, with unchanged production/GPU test code |
| Focused pixel/input safety regressions | PASS: 7 passed, 45 deselected, 9.40 s |
| `git diff --check` | PASS |
| Final benchmark color metadata | PASS: all 16 generated candidate files declare limited-range BT.709 |
| Source-commit GitHub CI | PASS: 4/4 at `32d965e5a6fe81739eedf2e32979deaa6469b83b`; [push workflow](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/37569076036) and [PR workflow](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/37569080364), Windows and Ubuntu CPU jobs |
| Build | NOT RUN: Python source/test/benchmark changes; no native build was required |

The executed suites cover 136 passing tests and 3 skipped tests, including the added CPU polling regression; deselected tests are reported separately. The three CPU skips are two optional private-sample checks without `VE_SAMPLES_DIR`, and the Linux-only parent-death signal test on Windows. GPU execution used the local RTX 4060 Ti (8 GB), Python 3.12.14, Torch 2.14.1+cu130, PyNvVideoCodec 2.2.3 and FFmpeg 9.0.2. CI only supplies CPU jobs, not GPU validation.

The initial implementation push `e2118e5` produced 3 PASS / 1 FAIL CI checks. One Linux job failed because its parent-death polling test observed an existing PID, then the correctly exiting process disappeared before `Process.status()`: `psutil.NoSuchProcess`. The other Linux job and both Windows jobs passed. This was a test-side race, not evidence that the worker survived. The test helper now treats a disappearing process as inactive; an injected disappearance test fails with the historical helper (1 FAIL) and passes in the corrected full CPU suite. No controller/production behavior was changed. Initial failure log: external `completion/evidence/ci-e2118e5-linux-fail.log`; deterministic fail-before log: `fail-before-pid-poll.log`; passing full CPU log: `final-cpu-ci-fix.log`. Fresh CI for `32d965e` passed all four checks. The exact source-head status response is retained as external `completion/evidence/ci-32d965e.json`.

## Changed files in this continuation

- `.ai/CURRENT_TASK.md`: retained the complete supplied specification and verbatim owner continuation.
- `.ai/LAST_REPORT.md`: replaced the partial report with final evidence and limitations.
- `docs/BENCHMARK_DEGRADED.md`: corrected/superseded partial candidate measurements; complete tables and model provenance.
- `src/videoenhancer/bench/runner.py`: host-input NVENC mode matches NumPy buffer.
- `src/videoenhancer/pipeline/runner.py`: source-aligned endpoint neighbor comparisons.
- `tests/test_bench.py`: host-input mode/buffer contract regression.
- `tests/test_p1a_pipeline.py`: actual encoder pixel assertions and persistent first/middle/last frame cases.
- `tests/test_controller.py`: fixes a test-side PID disappearance race exposed by Linux CI and adds a deterministic regression.

The prior partial cycle already contained the production host-buffer path, queue controls and the main retry/fallback guard. This continuation does not present those files as newly changed. No private source filename, frame, generated video, model weight, cache or build artifact is staged.

## Logs and exact reproduction

External evidence root: `C:\Users\pro\Documents\VideoEnhancer-P1a-5`.

- `completion/standard/results.json`, `repeatability.json`, six outputs and six per-frame `.hashes.jsonl` files; each run's `manifest.json` records settings, segmentation and guard events.
- `completion/metrics.json`, `candidate-speed.json`, candidate inference statistics and `review-videos.json`.
- `complete_p1a5.py`, `review_and_tables_p1a5.py`, `standard_p1a5_final.py`, `scan_encoded.py`: exact benchmark, render, repeat and detection scripts outside Git.
- Regression/historical logs are retained in external `completion/evidence` (fail-before logs, pass-after log, historical diff and injection plugin/source snapshots).
- Existing C0/C1/C5 inputs and outputs remain under `VideoEnhancer-P1a-3` / external P1a-5 directories. No media was copied into the repository.

PowerShell from the repository root, with the existing environment/models installed:

```powershell
$env:VE_FFMPEG_DIR='C:/Users/pro/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build-shared/bin'
$env:VE_HOME='C:/Users/pro/Documents/VideoEnhancer-P1a-3/home'
.venv/Scripts/python.exe -m pytest -m 'not gpu and not soak' -p no:cacheprovider --basetemp=.tmp/repro-cpu
.venv/Scripts/python.exe -m pytest -m 'gpu and not soak' -p no:cacheprovider --basetemp=.tmp/repro-gpu
.venv/Scripts/ruff.exe check src tests
.venv/Scripts/ruff.exe format --check src tests
.venv/Scripts/pyright.exe
.venv/Scripts/python.exe -u C:/Users/pro/Documents/VideoEnhancer-P1a-5/complete_p1a5.py learned
.venv/Scripts/python.exe -u C:/Users/pro/Documents/VideoEnhancer-P1a-5/complete_p1a5.py metrics
.venv/Scripts/python.exe -u C:/Users/pro/Documents/VideoEnhancer-P1a-5/review_and_tables_p1a5.py
.venv/Scripts/python.exe -u C:/Users/pro/Documents/VideoEnhancer-P1a-5/standard_p1a5_final.py
```

To reproduce failing-before results, copy the external evidence plugin and its historical modules into `.tmp`, add `.tmp` and `src` to `PYTHONPATH`, set `P1A5_BEFORE` to `bench`, `encode`, `handoff` or `boundary`, and run the corresponding focused pytest selection with `-p p1a5_before_plugin`. The plugin replaces only the targeted imported historical implementation; current source files are not overwritten. Historical revisions and exact failure locations are recorded in the logs.

## Errors, warnings, unresolved matters and deliberate omissions

- Initial restricted FFmpeg/pytest temporary-directory access failures were environmental; reruns with approved local access and unique temporary directories passed. Historical-code test failures are intentional fail-before evidence, not current failures.
- The exact internal cause of the earlier NVENC encoded artifact is unknown. Finite runs and a summary guard cannot prove all future outputs corruption-free. No inference of universal race freedom or model accuracy is made.
- C10 fits the requested 5 GB Torch-reservation limit alone; sequential blends also need C1 memory. C9/C5 can exceed decimal 5 GB, and were not represented as 5 GB models.
- C11 loses SSIM-Y and is not recommended. No default change was authorized or made.
- Earlier D3/frame-model benchmarks were not re-evaluated in this D2-only cycle; the corrected D2 results do not validate earlier frame-model color-conversion conditions.
- Claude/owner visual review of the new panels remains a product decision. No design/UI/preset change was independently made.
- Forced FP32 option, native builds, app GUI flow, long soaks, memory tuning, trial/seam/fidelity/calibration/SAC work remain intentionally unimplemented as specified.
- Git records: implementation and measurements `e2118e5`, CPU polling-test correction `32d965e`; both were pushed to `origin/p1-restoration-gui`. Source-head CI passed 4/4. This final report is recorded in a subsequent documentation-only commit. PR #2 remains a draft; no merge or main push was performed.
- Existing GitHub actions emitted a Node.js 20 deprecation warning; GitHub ran them under Node.js 24. No action-version migration was made in this cycle.
