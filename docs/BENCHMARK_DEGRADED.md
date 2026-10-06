# Degraded-input restoration benchmark

## Status

The benchmark harness and the 20 degraded inputs were generated for this cycle. Degradation size and bitrate are measured below, but restoration candidates and image-quality metrics have not yet been run. No candidate winner or restoration gain is claimed. The owner's original videos and all generated media remain outside the repository.

## Degradations

The committed script `scripts/make_degraded.py` creates four H.264 variants for each private source, assigns aliases `sample-01` through `sample-05` in sorted input order, and writes a manifest with output size and bitrate:

| ID | Operation |
|---|---|
| D1 | Same resolution, CRF 30, `veryfast` |
| D2 | Same resolution, CRF 36, `veryfast` |
| D3 | Lanczos downscale to 480×854, CRF 28, then bicubic upscale to 720×1280 |
| D4 | Same resolution, 400 kbit/s target and maximum rate, 800 kbit buffer |

Measured output size and average bitrate (MB and kbit/s; aliases follow sorted private-input order):

| Sample | D1 | D2 | D3 | D4 |
|---|---:|---:|---:|---:|
| sample-01 | 1.43 / 676 | 0.63 / 298 | 1.60 / 756 | 0.74 / 351 |
| sample-02 | 1.06 / 815 | 0.56 / 434 | 1.27 / 980 | 0.48 / 369 |
| sample-03 | 1.23 / 827 | 0.65 / 436 | 1.44 / 969 | 0.59 / 399 |
| sample-04 | 2.89 / 1296 | 1.40 / 626 | 3.12 / 1397 | 0.90 / 403 |
| sample-05 | 3.16 / 872 | 1.56 / 431 | 3.75 / 1036 | 1.29 / 356 |

Reproduce outside the repository:

```powershell
python scripts/make_degraded.py `
  --input-dir "C:\path\to\private\Videos" `
  --output-dir "C:\path\outside\VideoEnhancer\degraded"
```

The script requires FFmpeg with `libx264` and `ffprobe` available on `PATH`; explicit executable paths can be supplied with `--ffmpeg` and `--ffprobe`.

## Results

No C0–C4 restoration results, PSNR-Y, SSIM, LPIPS, flicker ratios, or candidate speeds are available yet. All five samples across D1–D4 are therefore **NOT RUN** for restoration. C3 (RealBasicVSR) is optional and was also not run. D2/D3 side-by-side owner-review videos have not been generated.
