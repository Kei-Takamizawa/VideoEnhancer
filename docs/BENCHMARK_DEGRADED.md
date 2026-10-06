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

## Reproduction artifacts

Measured data and comparison videos were generated in external working folders and are not committed. The task report records exact paths and reproduction commands for this run.
