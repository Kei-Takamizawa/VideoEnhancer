# Degraded-input restoration benchmark

## Scope and status

The owner selected C1 for the first release in P1a-6. Candidate evaluation stops
here; the existing results and evaluation scripts are retained for future owner-led
fine-tuning comparisons. No additional candidate is introduced by P1a-6.

This report covers two anonymized source clips at their native 720×1280 resolution and 30000/1001 fps. The reported quality metrics use 150 aligned middle frames for each degradation. All source videos, frames, derived clips, and comparison videos remain outside the repository.

## Method

- **C0:** degraded input without restoration.
- **C1:** the standard BasicVSR pipeline at native size and frame rate, with no interpolation or resizing.
- **C2:** Real-ESRGAN `realesr-general-x4v3` through spandrel, batch size 1 in FP16, followed by 4× area downscaling.
- **C4:** C1 followed by FFmpeg `unsharp=5:5:0.20:5:5:0.0`.
- **Bicubic baseline:** degraded input downscaled to one quarter in each dimension using area filtering and enlarged back to native size using bicubic filtering.
- **PSNR-Y:** full-resolution 8-bit luma PSNR against the aligned original. **SSIM-Y:** FFmpeg SSIM luma component. **Flicker ratio:** candidate mean absolute luma change between adjacent frames divided by the original's corresponding value; 1 is the reference ratio. Speeds are measured over the processed frames; C0 speed is decode-only.

The input identifiers below intentionally do not disclose source filenames.

## B1 and B3: C0, C1, C2 and bicubic metrics

Each cell is `PSNR-Y dB / SSIM-Y / flicker ratio`. Positive C1 gains against both C0 and bicubic are shown in the last columns as `ΔPSNR / ΔSSIM`.

| Clip | Degradation | C0 | Bicubic | C1 | C1 speed (fps) | C1 gain vs C0 | C1 gain vs bicubic | C2 | C2 speed (fps) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | D2 | 30.422189 / 0.922811 / 0.878194 | 27.903576 / 0.900284 / 0.807769 | 32.019490 / 0.941709 / 0.873134 | 2.6 | +1.597301 / +0.018898 | +4.115914 / +0.041425 | 29.968913 / 0.923556 / 0.905831 | 5.090 |
| A | D3 | 33.259623 / 0.957590 / 0.925344 | 28.569671 / 0.918598 / 0.848171 | 34.450644 / 0.963867 / 0.918351 | 2.7 | +1.191021 / +0.006277 | +5.880972 / +0.045269 | 32.765222 / 0.952094 / 0.965601 | 5.083 |
| B | D2 | 31.719808 / 0.880273 / 0.827707 | 30.556435 / 0.860657 / 0.779768 | 33.298938 / 0.911173 / 0.850196 | 2.8 | +1.579130 / +0.030900 | +2.742503 / +0.050516 | 31.084645 / 0.879882 / 0.843311 | 5.059 |
| B | D3 | 36.635446 / 0.955189 / 0.925956 | 32.481183 / 0.908587 / 0.844329 | 37.249102 / 0.960469 / 0.936861 | 2.8 | +0.613655 / +0.005280 | +4.767919 / +0.051882 | 34.347689 / 0.948150 / 0.952704 | 5.067 |

C1 improves PSNR-Y and SSIM-Y over C0 and bicubic in all four measured conditions. Its flicker ratio moves closer to 1 for A/D2, B/D2, and B/D3, and slightly farther from 1 for A/D3. C2 has lower PSNR-Y than C0 and C1 for all four conditions; its SSIM-Y is higher than C0 only for A/D2, and lower for the other three. C2's flicker ratio is closer to 1 than C0 for all four conditions. These are metric comparisons only, not visual-quality conclusions.

## B4: C4 metrics

| Clip | Degradation | C4 PSNR-Y (dB) | C4 SSIM-Y | C4 flicker ratio | C4 speed |
|---|---|---:|---:|---:|---|
| A | D2 | 31.876129 | 0.941359 | 0.896071 | Not measured |
| A | D3 | 34.650034 | 0.964399 | 0.940218 | Not measured |
| B | D2 | 33.219053 | 0.910751 | 0.863740 | Not measured |
| B | D3 | 37.117593 | 0.959624 | 0.954892 | Not measured |

Against C1, C4 changes PSNR-Y/SSIM-Y by −0.143361/−0.000350 (A/D2), +0.199391/+0.000532 (A/D3), −0.079885/−0.000422 (B/D2), and −0.131509/−0.000845 (B/D3). C4's flicker ratio is farther from 1 than C1 in all four cases. Speed was not measured for this post-processing pass.

## B5 and C3

- **B5: NOT RUN.** The requested full five-source × D1–D4 sweep was outside this cycle's completed benchmark scope; only the two longest sources and D2/D3 were measured.
- **C3: NOT RUN.** RealBasicVSR was not attempted in this cycle.

## P1a-4: D3 candidate comparison

The full-resolution rows use the same aligned D3 windows and metric definitions above. A and B are anonymized clip aliases. `Δ` fields are candidate minus baseline, including the signed flicker-ratio difference. A flicker ratio's distance from 1 is reported by the number itself; no perceptual conclusion is implied.

### C5: C1 applied twice, and C7: 50/50 C1–C2 blend

| Clip | Candidate | PSNR-Y dB | SSIM-Y | Flicker ratio | Speed (fps) | Peak Torch reserved (GB) |
|---|---|---:|---:|---:|---:|---:|
| A | C5 | 34.437326 | 0.962955 | 0.922696 | 2.605 | 5.629 |
| B | C5 | 36.695605 | 0.955975 | 0.947789 | 2.870 | 5.048 |
| A | C7 | 34.127440 | 0.961442 | 0.933603 | 114.287 | Not applicable (CPU FFmpeg blend) |
| B | C7 | 36.717819 | 0.960390 | 0.938366 | 105.325 | Not applicable (CPU FFmpeg blend) |

| Clip | Candidate | Δ vs C0 (PSNR / SSIM / flicker) | Δ vs C1 (PSNR / SSIM / flicker) | Δ vs C2 (PSNR / SSIM / flicker) |
|---|---|---:|---:|---:|
| A | C5 | +1.177703 / +0.005365 / −0.002648 | −0.013318 / −0.000912 / +0.004345 | +1.672104 / +0.010861 / −0.042905 |
| B | C5 | +0.060159 / +0.000786 / +0.021833 | −0.553497 / −0.004494 / +0.010928 | +2.347916 / +0.007825 / −0.004915 |
| A | C7 | +0.867817 / +0.003852 / +0.008259 | −0.323204 / −0.002425 / +0.015252 | +1.362218 / +0.009348 / −0.031998 |
| B | C7 | +0.082373 / +0.005201 / +0.012410 | −0.531283 / −0.000079 / +0.001505 | +2.370130 / +0.012240 / −0.014338 |

### C6: internal 2× upscale on a half-size spatial crop

A 21-frame full-frame pilot at 1440×2560 reached 12,580,814,848 bytes Torch-reserved and 7,759,425,536 bytes process-dedicated GPU memory. This did not fit the requested 5 GB budget, so C6 was completed only on the top-left half-size spatial crop: 360×640 input, Lanczos pre-upscale to 720×1280, C1 restoration, then area downscale back to 360×640. Metrics below compare against matching 360×640 crops of the original and C0/C1/C2; they are not directly comparable to the full-resolution rows above. The B crop peaked at 5,045,747,712 bytes (5.046 decimal GB or 4.70 GiB): it fits a 5 GiB limit and is 0.046 GB above a strict decimal 5 GB limit.

| Clip | C6 PSNR-Y dB | C6 SSIM-Y | C6 flicker ratio | Speed (fps) | Peak Torch reserved (GB, decimal) |
|---|---:|---:|---:|---:|---:|
| A | 35.056472 | 0.940065 | 0.900115 | 2.797 | 4.415 |
| B | 39.093963 | 0.969563 | 0.928097 | 2.871 | 5.046 |

| Clip | Cropped baseline | PSNR-Y dB | SSIM-Y | Flicker ratio |
|---|---|---:|---:|---:|
| A | C0 | 34.185015 | 0.934847 | 0.915036 |
| A | C1 | 35.377466 | 0.939705 | 0.903788 |
| A | C2 | 33.709884 | 0.918555 | 0.963155 |
| B | C0 | 38.248151 | 0.962790 | 0.931943 |
| B | C1 | 38.880077 | 0.967779 | 0.937421 |
| B | C2 | 35.977917 | 0.957872 | 0.952398 |

| Clip | Δ C6 vs cropped baseline | ΔPSNR-Y dB | ΔSSIM-Y | Δ flicker ratio |
|---|---|---:|---:|---:|
| A | C0 | +0.871456 | +0.005218 | −0.014920 |
| A | C1 | −0.320994 | +0.000360 | −0.003672 |
| A | C2 | +1.346587 | +0.021510 | −0.063039 |
| B | C0 | +0.845812 | +0.006773 | −0.003845 |
| B | C1 | +0.213886 | +0.001784 | −0.009324 |
| B | C2 | +3.116046 | +0.011691 | −0.024301 |

### C3 and optional extra model

- **C3: NOT RUN.** The repository contains no RealBasicVSR adapter and the active Python environment has no `mmagic` package. No custom CUDA build or unpinned loader was introduced.
- **Optional extra: NOT RUN.** C5–C7 cover the requested candidate comparison; no additional checkpoint was selected or downloaded.

### Review videos

The external folder `owner-review-2` contains two H.264 8-bit videos with panels ordered Degraded, C1, C2, C5, C7. Clip A is 300 frames (10.01 seconds); clip B is 150 frames (5.005 seconds). See `.ai/LAST_REPORT.md` for their local paths.

## Reproduction artifacts

Measured data and comparison videos were generated in external working folders and are not committed. The task report records exact paths and reproduction commands for this run.

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
