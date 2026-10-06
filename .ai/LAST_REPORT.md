# VideoEnhancer Cycle P1a-3 Report

- **Task ID / Cycle:** VE-P1a-3
- **Status:** PARTIAL
- **Date:** 2026-10-07
- **Branch:** `p1-restoration-gui`

## Summary

Task A found no flagged flash in either existing P1a-1 output. Near 24.4 seconds, both files have steady mean luma; three new Fast runs were bit-identical frame-by-frame. The reported old flash therefore remains unlocated, and its cause cannot be inferred from these two files.

Task B completed the requested C0/C1, C2, and C4 metrics for D2/D3 on the two longest clips using aligned middle frames. C1 improved PSNR-Y and SSIM-Y over the degraded input and bicubic baseline in all four conditions. Four owner-review videos were created outside the repository. The expanded five-source D1–D4 sweep (B5) and optional C3 were not run. This cycle does not make a visual-quality or default-preset recommendation.

## A1–A6 acceptance status

| Criterion | Status | Evidence |
|---|---|---|
| A1 — Old outputs analyzed; determinism checked | PASS | Both old outputs decoded to 1,822 frames; no detector flags; three fresh Fast outputs were bit-identical. The old reported flash is not present in either named file. |
| A2 — Regression/retry if old defect exists | NOT TRIGGERED | No old flagged frame was found, so the conditional regression/retry change was not made. Existing detector was retained unchanged. |
| A3 — B1 metrics and gains | PASS | C0/C1/bicubic metrics and C1 gains are in the table below. |
| A4 — Side-by-side videos | PASS | Four videos (C1/C2 for D2/D3) are in the external `owner-review` folder; paths below. |
| A5 — C2/C4, B5/C3 status | PARTIAL | C2 and C4 tables completed. B5 and C3 are explicitly NOT RUN. |
| A6 — lint, type check, CPU/GPU tests, CI, privacy | PARTIAL | Local checks passed; remote CI will be checked after push. No media was added to the repository. |

## Task A: old output flash investigation

The old output files were `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_fast.mp4` and `sample-05_standard.mp4`. Each decoded to 1,822 frames at 59.94 fps. Mean luma was extracted for every decoded frame and the existing outlier detector was run against input-aligned low-resolution summaries.

| Old output | Flagged frames | Frame 1463 (24.407741 s) | Previous / next luma | Frames 1457–1469 |
|---|---:|---:|---:|---|
| Fast | 0 | 124 | 125 / 124 | Values 124–125; no isolated spike |
| Standard | 0 | 124 | 124 / 124 | All 124 |

There is no flagged-frame index or flagged-frame neighbor comparison to report: neither old file contains a detector-flagged frame. The detector's strongest ordinary scene transitions were not isolated flashes and were not flagged. Full luma dumps are outside the repository at `C:\Users\pro\Documents\VideoEnhancer-P1a-3\sample-05_fast_luma.txt` and `...\sample-05_standard_luma.txt`.

### Three-run determinism

Fast was run three times on the same private input with identical settings: `--preset fast --short-side 1080 --fps 2x --codec hevc --backend cuda --segment-seconds 180`. Each output contained 1,822 frames. Decoded raw per-frame hashes matched for every frame: run 1 vs run 2 **identical**, run 1 vs run 3 **identical**, zero differing frames. Outputs are under `C:\Users\pro\Documents\VideoEnhancer-P1a-3\determinism\`. This establishes repeatability for these three runs only; it does not establish the cause of a flash in some other file.

Because the named old Fast and Standard files contain no flagged frame, the conditional old-segment/clip comparison and retry-once implementation were not triggered. **Owner input needed:** provide the exact output filename and approximate timestamp (or identify the exact frame) where the flash is visible; the two specified old files do not contain it.

## Task B: degraded benchmark

Metrics are on 150 aligned middle frames at the source resolution (720×1280) and source frame rate (30000/1001), without restoration-stage resize or interpolation. For the first long clip, a centered 300-frame material window was prepared for the requested 10-second review videos; its middle 150 frames were used for metrics. For the second, the centered 150 frames were used for both. C0 speed is FFmpeg decode-only throughput. C1 speed is end-to-end measured restoration throughput. C2 speed is measured model-plus-downscale processing throughput.

Metric cells are `PSNR-Y dB / SSIM-Y / flicker ratio`. Flicker ratio is candidate/original mean absolute consecutive-frame luma change; 1 is the original reference ratio. C1 gains are `ΔPSNR-Y / ΔSSIM`.

| Clip | Degrade | C0 | Bicubic | C1 | C0 speed (fps) | C1 speed (fps) | C1 gain vs C0 | C1 gain vs bicubic |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | D2 | 30.422189 / 0.922811 / 0.878194 | 27.903576 / 0.900284 / 0.807769 | 32.019490 / 0.941709 / 0.873134 | 1610.66 | 2.6 | +1.597301 / +0.018898 | +4.115914 / +0.041425 |
| A | D3 | 33.259623 / 0.957590 / 0.925344 | 28.569671 / 0.918598 / 0.848171 | 34.450644 / 0.963867 / 0.918351 | 1537.02 | 2.7 | +1.191021 / +0.006277 | +5.880972 / +0.045269 |
| B | D2 | 31.719808 / 0.880273 / 0.827707 | 30.556435 / 0.860657 / 0.779768 | 33.298938 / 0.911173 / 0.850196 | 1035.53 | 2.8 | +1.579130 / +0.030900 | +2.742503 / +0.050516 |
| B | D3 | 36.635446 / 0.955189 / 0.925956 | 32.481183 / 0.908587 / 0.844329 | 37.249102 / 0.960469 / 0.936861 | 961.64 | 2.8 | +0.613655 / +0.005280 | +4.767919 / +0.051882 |

C1 increases PSNR-Y and SSIM over C0 and bicubic in all four conditions. Against C0, C1 flicker ratio is closer to 1 for A/D2, B/D2 and B/D3, and slightly farther from 1 for A/D3. No visual-quality conclusion is made.

### B3: C2 Real-ESRGAN

Real-ESRGAN `realesr-general-x4v3` ran through spandrel with batch size 1 and FP16, then 4× area downscaling. The reported PyTorch reserved-memory peak was 507,510,784 bytes (0.473 GiB); this is framework telemetry, not total process-dedicated GPU memory.

| Clip | Degrade | C2 PSNR-Y (dB) | C2 SSIM-Y | C2 flicker ratio | Speed (fps) | ΔPSNR vs C0 | ΔSSIM vs C0 |
|---|---|---:|---:|---:|---:|---:|---:|
| A | D2 | 29.968913 | 0.923556 | 0.905831 | 5.090 | −0.453277 | +0.000745 |
| A | D3 | 32.765222 | 0.952094 | 0.965601 | 5.083 | −0.494401 | −0.005496 |
| B | D2 | 31.084645 | 0.879882 | 0.843311 | 5.059 | −0.635163 | −0.000391 |
| B | D3 | 34.347689 | 0.948150 | 0.952704 | 5.067 | −2.287758 | −0.007039 |

C2 PSNR-Y and SSIM-Y are below C1 in all four conditions. C2 PSNR-Y is below C0 in all four; SSIM-Y is above C0 only for A/D2. C2 flicker ratio is closer to 1 than C0 in all four. These are metric results, not a visual ranking.

### B4: C4 fixed unsharp mask

C4 is C1 followed by FFmpeg `unsharp=5:5:0.20:5:5:0.0` (fixed amount 0.20). Speed for this post-processing pass was not measured.

| Clip | Degrade | C4 PSNR-Y (dB) | C4 SSIM-Y | C4 flicker ratio | ΔPSNR vs C1 | ΔSSIM vs C1 |
|---|---|---:|---:|---:|---:|---:|
| A | D2 | 31.876129 | 0.941359 | 0.896071 | −0.143361 | −0.000350 |
| A | D3 | 34.650034 | 0.964399 | 0.940218 | +0.199391 | +0.000532 |
| B | D2 | 33.219053 | 0.910751 | 0.863740 | −0.079885 | −0.000422 |
| B | D3 | 37.117593 | 0.959624 | 0.954892 | −0.131509 | −0.000845 |

C4 flicker ratio is farther from 1 than C1 in all four conditions. No preset was changed.

### B5 and C3

- **B5: NOT RUN.** The full five-source × D1–D4 × C0/C1 sweep and the C2 extension were not run. This cycle completed the higher-priority two-source D2/D3 benchmark only.
- **C3: NOT RUN.** RealBasicVSR was not attempted; no load/build result is claimed.

### Owner-review videos

All four H.264 8-bit side-by-side files are in `C:\Users\pro\Documents\VideoEnhancer-P1a-3\owner-review\`. Each is 2160×1280, 300 frames at 30000/1001 fps, with Original / Degraded / Restored panels left-to-right and duration 10.01 seconds.

- `C:\Users\pro\Documents\VideoEnhancer-P1a-3\owner-review\sample-04_D2_C1_side-by-side.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a-3\owner-review\sample-04_D3_C1_side-by-side.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a-3\owner-review\sample-04_D2_C2_side-by-side.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a-3\owner-review\sample-04_D3_C2_side-by-side.mp4`

### Reproduction and execution notes

The private source clips were cropped to the centered matching windows outside the repository, then encoded losslessly as H.264 for reliable GPU decode. C1 was run using the project's CLI with `--short-side keep --fps off --codec h264 --backend cuda --lossless`. C2 used the stated spandrel model, batch size 1 and area downscale. C0 and candidate outputs were compared against the aligned original using the external `C:\Users\pro\Documents\VideoEnhancer-P1a-3\measure_metrics.py` script. The four review videos were assembled with FFmpeg using the same 300-frame middle window. Detailed intermediate media and scripts remain in `C:\Users\pro\Documents\VideoEnhancer-P1a-3\`.

An initial FFV1/Matroska material clip was unsupported by the GPU decoder (decode error code 300); it was replaced with lossless H.264. An initial drawtext attempt could not resolve the font through fontconfig; specifying the Windows Arial font file fixed it. All final review videos were probed successfully. These attempts did not alter repository code.

## Verification and Git

- `ruff check .`: PASS, all checks passed.
- `ruff format --check .`: PASS, 64 files already formatted.
- `pyright src`: PASS, 0 errors, 0 warnings, 0 informations.
- CPU test suite: PASS, 110 passed, 3 skipped, 15 deselected, 41.87 s.
- GPU test suite: PASS, 15 passed, 113 deselected, 38.28 s.
- Remote CI: PASS on push run `37543189206` for commit `72413e9` (Windows and Ubuntu). A duplicate PR-triggered run also passed Ubuntu; its Windows job was still running at report finalization.
- `git diff --check`: PASS.
- Private media committed: NO.
- GUI test: NOT RUN; not required by this task.
- Commit: `72413e9` (`Complete P1a-3 flash and degradation benchmark`). This report's CI status update will be committed and pushed separately to the same branch.

## Remaining question and intentionally omitted work

Please provide the exact old output filename and timestamp (or frame index) where the white flash is visible. Neither specified P1a-1 output contains a flagged frame. The full B5 sweep and C3 were intentionally omitted; no default-preset change, visual-quality conclusion, or architecture change was made.
