# Degraded-input restoration benchmark

## Scope and status

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

## P1a-5 D2 extension (partial)

This extension uses 150 full-resolution frames per clip: the middle 150 frames of clip A and all 150 frames of clip B. Values below are PSNR-Y / SSIM-Y / flicker ratio. Speed and peak Torch-reserved VRAM are included where measured; `N/A` means a CPU FFmpeg operation, and `Not run` means no measurement was made. Candidate deltas are omitted here until the full requested candidate set, including C10, has been evaluated consistently.

| Clip | Candidate | PSNR-Y (dB) | SSIM-Y | Flicker ratio | Speed (fps) | Peak Torch reserved (GB, decimal) |
|---|---|---:|---:|---:|---:|---:|
| A | C1 | 32.019490 | 0.941709 | 0.873134 | 2.6 | 4.438 |
| A | C2 | 29.968913 | 0.923556 | 0.905831 | 5.090 | Not recorded |
| A | C5 | 32.045918 | 0.942190 | 0.876662 | 2.817 | 5.518 |
| A | C8 | 31.274292 | 0.935033 | 0.876585 | 68.0 | N/A |
| A | C9 (Track 1) | 31.480616 | 0.937026 | 0.856733 | 2.755 | 5.599 |
| A | C9 + C1 (50/50) | 31.997449 | 0.940930 | 0.860363 | Not measured | N/A |
| A | C11 | 31.875005 | 0.939550 | 0.872605 | 160.4 | N/A |
| B | C1 | 33.298938 | 0.911173 | 0.850196 | 2.8 | 5.069 |
| B | C2 | 31.084645 | 0.879882 | 0.843311 | 5.059 | Not recorded |
| B | C5 | 33.236867 | 0.910927 | 0.857712 | 2.884 | 5.069 |
| B | C8 | 32.654047 | 0.900408 | 0.837832 | 92.0 | N/A |
| B | C9 (Track 1) | 32.694482 | 0.901530 | 0.821007 | 2.850 | 5.629 |
| B | C9 + C1 (50/50) | 33.335030 | 0.910541 | 0.829304 | Not measured | N/A |
| B | C11 | 33.134549 | 0.907302 | 0.847772 | 128.2 | N/A |

Candidate deltas are PSNR-Y / SSIM-Y / flicker ratio, calculated as candidate minus baseline:

| Clip | Candidate | Δ vs C0 | Δ vs C1 |
|---|---|---:|---:|
| A | C2 | −0.453276 / +0.000745 / +0.027637 | −2.050577 / −0.018153 / +0.032697 |
| A | C5 | +1.623729 / +0.019379 / −0.001532 | +0.026428 / +0.000481 / +0.003528 |
| A | C8 | +0.852103 / +0.012222 / −0.001609 | −0.745198 / −0.006676 / +0.003451 |
| A | C9 | +1.058427 / +0.014215 / −0.021461 | −0.538874 / −0.004683 / −0.016401 |
| A | C9 + C1 | +1.575260 / +0.018119 / −0.017831 | −0.022041 / −0.000779 / −0.012771 |
| A | C11 | +1.452816 / +0.016739 / −0.005589 | −0.144485 / −0.002159 / −0.000529 |
| B | C2 | −0.635163 / −0.000391 / +0.015604 | −2.214293 / −0.031291 / −0.006885 |
| B | C5 | +1.517059 / +0.030654 / +0.030005 | −0.062071 / −0.000246 / +0.007516 |
| B | C8 | +0.934239 / +0.020135 / +0.010125 | −0.644891 / −0.010765 / −0.012364 |
| B | C9 | +0.974674 / +0.021257 / −0.006700 | −0.604456 / −0.009643 / −0.029189 |
| B | C9 + C1 | +1.615222 / +0.030268 / +0.001597 | +0.036092 / −0.000632 / −0.020892 |
| B | C11 | +1.414741 / +0.027029 / +0.020065 | −0.164389 / −0.003871 / −0.002424 |

This is a partial comparison: C10 and the requested owner-review-3 videos were not completed. C11's SSIM-Y is below C1 for both clips, so it does not satisfy the explicit non-regression condition for recommendation. No default preset was changed. See `.ai/LAST_REPORT.md` for provenance, limitations, and external paths.
