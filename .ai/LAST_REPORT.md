# VideoEnhancer Cycle P1a-4 Report

- **Task ID / Cycle:** VE-P1a-4
- **Status:** PARTIAL
- **Date:** 2026-10-07
- **Branch:** `p1-restoration-gui`

## Summary

The full old sample-05 outputs were scanned. There is no isolated edge-only luma spike where the center remains within 15 levels, but the old Standard output has two separate one-frame color/luma anomalies: frame 562 at 9.376033 s and frame 1327 at 22.138783 s. Neither occurs in the source or old Fast output. The updated detector flags both. A full current Standard rerun was clean at both frames and produced no detector flags. The original artifact's generating stage/root cause could not be proven from the old encoded file and the absent P1a-1 job manifest.

D3 candidates C5, C6 (half-size spatial crop), C7 and the C3 availability check were completed. Full-resolution C5 and C7 comparisons are documented below and in the benchmark document. C3 could not run because there is no existing adapter and MMagic is absent. Two owner-review videos were produced outside the repository. No preset was changed and no visual-quality conclusion is made.

## Acceptance status

| Criterion | Status | Evidence / limitation |
|---|---|---|
| A1 — 19.5–23 s edge analysis, cuts, boundaries, contact sheet | PASS | Entire old files were scanned; the requested time window has per-frame CSVs. No edge-only threshold event in that window; the full-file scan found two whole-frame anomalies. Two 3-panel sheets and ±3 PNG sequences are outside the repository. |
| A2 — root cause/fix or absence documented | PARTIAL | Edge-only spike absence is documented with the maximum edge and center deviations. The two separate whole-frame anomalies were detected and the detection gap was fixed/tested, but their original producer is unresolved. Current rerun is clean. |
| A3 — edge-band detector/tests/CI | PASS | Left/right/top/bottom bands and RGB-only isolated corruption are tested locally; Linux and Windows CI passed. |
| A4 — C5/C6/C3/C7 candidate metrics, speed, memory | PARTIAL | C5 and C7 completed full-frame. C6 completed on the required half-size crop after the full 2× input exceeded 5 GB. C3 skipped because no adapter/package exists. |
| A5 — owner-review videos | PASS | Two H.264 videos in `owner-review-2`, details below. |
| A6 — lint/types/CPU/GPU/CI/privacy | PASS | Local lint, type checks and CPU/GPU suites pass; Linux and Windows CI pass. No private media has been added to the repository. |

## Task A — old output inspection and full-duration scan

Files inspected:

- Old Standard: `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_standard.mp4`
- Old Fast: `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_fast.mp4`
- Original source: the task's sample-05 input under `Videos/` (source frame indices below are private aliases only).

All three streams were decoded across their duration: input 911 frames at 29.97 fps; outputs 1,822 frames at 59.94 fps. The full-duration scan used 160×90 grayscale frames and 16×16 RGB thumbnails to find temporal candidates. Exact full-resolution ROI luma was then computed for every frame in the requested 19.5–23.0 s window and around the two detected anomalies. The CSV dumps are outside the repository:

- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\input_region_luma.csv`
- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\fast_region_luma.csv`
- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\standard_region_luma.csv`

The full-resolution exact ROI dump around the two discovered frames is at `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\*_exact_spike_rois.csv`. These exact ROI values are integer mean luma levels, rounded by FFmpeg's 8-bit gray output.

### Threshold events and anomalies

For the edge-only rule, a region must be an isolated local high/low (more than 15 levels from both adjacent frames) while the center changes by no more than 15 levels. **No frame meets that edge-only rule in the 19.5–23.0 s window in the input, Fast or Standard files.** The largest edge departure over the full old Standard is 56 levels at frame 1327, but the center also changes 42 levels; it is a whole-frame event, not edge-only. The largest edge departure while checking frame 562 is 21 levels; the center changes 16 levels, so that event narrowly fails the specified edge-only condition.

Two other one-frame anomalies are present in old Standard. They appear as chroma/spatial corruption in the decoded PNGs and are absent from both matched source frames and Fast:

| Old Standard frame | Time (s) | Region | Previous / current / next luma | Center previous / current / next | Source / Fast |
|---:|---:|---|---|---|---|
| 562 | 9.376033 | Whole | 162 / 145 / 162 | 159 / 143 / 159 | Source 163 / 163 / 163; Fast 162 / 162 / 162 |
| 562 | 9.376033 | Left 8% | 176 / 155 / 176 | 159 / 143 / 159 | Source 176–177; Fast 176–177 |
| 562 | 9.376033 | Top 8% | 185 / 167 / 186 | 159 / 143 / 159 | Source 183–187; Fast 185–187 |
| 562 | 9.376033 | Bottom 8% | 192 / 171 / 192 | 159 / 143 / 159 | Source 193–194; Fast 192–192 |
| 1327 | 22.138783 | Whole | 118 / 77 / 118 | 119 / 77 / 118 | Input frames 663/664: whole 120/119; Fast frame 1327: 118 |
| 1327 | 22.138783 | Left 8% | 98 / 80 / 98 | 119 / 77 / 118 | Input 98/98; Fast 98 |
| 1327 | 22.138783 | Right 8% | 136 / 80 / 136 | 119 / 77 / 118 | Input 136/135; Fast 136 |

Frame 562's edge bands depart by 18–21 levels, but the center also falls 16 levels, so this does not qualify as an edge-only luma event under the requested 15-level center rule. Frame 1327 is a clear whole-frame luma event; its center also drops by over 40 levels. These observations do not support the owner's description of a white edge-only frame.

### 19.5–23.0 s cuts and reconstructed boundaries

The project scene-cut detector (`media.analyze`, 160×90 grayscale thumbnail, mean absolute delta ≥24 and histogram distance ≥0.18) found no cut in input frames 584–689, corresponding to 19.5–23.0 s. Its detected cuts for this source were at frames 44, 95, 145, 194, 246, 294, 343, 394 and 444; none is in the requested window.

The old P1a-1 job manifest was not retained, so exact historical segment boundaries cannot be recovered from the encoded output alone. Replaying the P1a-1 defaults (segment target 180 processing-seconds, 21-frame BasicVSR++ clips, overlap 3, and the detected cuts) with the current estimator/planner yields segment ranges `[0,394)`, `[394,782)`, `[782,911)`. Thus source frame 281 is in recomputed segment 0 and source frames 663/664 are in segment 1. `plan_restore_clips` yields clip `[276,294)` (owned `[279,294)`) for source frame 281, and clip `[654,675)` (owned `[657,672)`) for frames 663/664. These are reconstructed boundaries, not a claim that the missing historical manifest used the identical estimator profile.

### Rerun and detector change

The current Standard pipeline was rerun on the same source with `--preset standard --short-side 1080 --fps 2x --codec hevc --backend cuda --segment-seconds 180`. It completed 911 input / 1,822 output frames in 393 seconds across three segments, at 2.32 aggregate input fps. Exact ROI values at frames 562 and 1327 matched surrounding frames; the updated detector returned zero flags over the entire current output.

The old errors span two output positions: frame 562 is an even output frame (restoration-stage source frame 281), while frame 1327 is odd (RIFE-inserted between source frames 663/664). This narrows where to investigate but does not prove a single cause. The rerun did not reproduce either error, and the P1a-1 per-stage tensors/logs are unavailable. I did not attribute this to BasicVSR++, RIFE, FP16, NVENC or decoder state without evidence.

The detector now also flags an isolated RGB temporal outlier without requiring a large mean-luma jump, while retaining the reference-side cut guard. A synthetic chroma-only glitch test fails before this change and passes after it; the edge-only flash and natural-cut tests also pass.

Contact sheets and lossless PNG evidence:

- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\input_fast_standard_frame562_contact_sheet.png`
- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\input_fast_standard_frame1327_contact_sheet.png`
- Old Standard ±3 PNGs: `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\standard9s_*.png` and `standard_*.png`.
- Current rerun ±3 PNGs: `C:\Users\pro\Documents\VideoEnhancer-P1a-4\flash-check\current9s_*.png` and `current_*.png`.

## Task B — D3 candidate measurements

The full-frame rows use the P1a-3 D3 clips at native 720×1280 / 30000/1001 fps and the same aligned 150 central frames. Metrics are PSNR-Y dB / SSIM-Y / flicker ratio. Speed is candidate processing throughput. Delta columns are candidate minus baseline for all three numbers. The aliases A/B do not disclose source filenames.

### C5 — two consecutive C1 restoration passes

| Clip | PSNR-Y | SSIM-Y | Flicker ratio | Speed (fps) | Peak Torch reserved |
|---|---:|---:|---:|---:|---:|
| A | 34.437326 | 0.962955 | 0.922696 | 2.605 | 5,628,755,968 bytes (5.629 GB) |
| B | 36.695605 | 0.955975 | 0.947789 | 2.870 | 5,047,844,864 bytes (5.048 GB) |

| Clip | Δ vs C0 (PSNR / SSIM / flicker) | Δ vs C1 | Δ vs C2 |
|---|---:|---:|---:|
| A | +1.177703 / +0.005365 / −0.002648 | −0.013318 / −0.000912 / +0.004345 | +1.672104 / +0.010861 / −0.042905 |
| B | +0.060159 / +0.000786 / +0.021833 | −0.553497 / −0.004494 / +0.010928 | +2.347916 / +0.007825 / −0.004915 |

### C7 — fixed 0.5 blend of C1 and C2

| Clip | PSNR-Y | SSIM-Y | Flicker ratio | Blend+encode speed (fps) | Peak Torch reserved |
|---|---:|---:|---:|---:|---|
| A | 34.127440 | 0.961442 | 0.933603 | 114.287 | Not applicable; CPU FFmpeg only |
| B | 36.717819 | 0.960390 | 0.938366 | 105.325 | Not applicable; CPU FFmpeg only |

| Clip | Δ vs C0 (PSNR / SSIM / flicker) | Δ vs C1 | Δ vs C2 |
|---|---:|---:|---:|
| A | +0.867817 / +0.003852 / +0.008259 | −0.323204 / −0.002425 / +0.015252 | +1.362218 / +0.009348 / −0.031998 |
| B | +0.082373 / +0.005201 / +0.012410 | −0.531283 / −0.000079 / +0.001505 | +2.370130 / +0.012240 / −0.014338 |

### C6 — 2× internal pre-upscale, half-size spatial crop

A full 1440×2560 21-frame pilot reached 12,580,814,848 bytes Torch-reserved and 7,759,425,536 bytes process-dedicated GPU memory, so full-resolution C6 was not run. As requested for an over-budget C6, both clips were tested on a top-left 360×640 crop, upscaled to 720×1280, restored by C1, then area-downscaled back to 360×640. All values below (including C0/C1/C2 comparison values) use matching 360×640 crops; do not compare these absolute scores directly with the full-frame rows above. The B crop's 5,045,747,712-byte peak is 5.046 decimal GB (4.70 GiB): below 5 GiB but 0.046 GB above a strict decimal 5 GB cap.

| Clip | Candidate | PSNR-Y | SSIM-Y | Flicker ratio | Speed (fps) | Peak Torch reserved |
|---|---|---:|---:|---:|---:|---:|
| A | C0 | 34.185015 | 0.934847 | 0.915036 | — | — |
| A | C1 | 35.377466 | 0.939705 | 0.903788 | — | — |
| A | C2 | 33.709884 | 0.918555 | 0.963155 | — | — |
| A | C6 | 35.056472 | 0.940065 | 0.900115 | 2.797 | 4,414,504,960 bytes (4.415 GB) |
| B | C0 | 38.248151 | 0.962790 | 0.931943 | — | — |
| B | C1 | 38.880077 | 0.967779 | 0.937421 | — | — |
| B | C2 | 35.977917 | 0.957872 | 0.952398 | — | — |
| B | C6 | 39.093963 | 0.969563 | 0.928097 | 2.871 | 5,045,747,712 bytes (5.046 GB) |

| Clip | Δ C6 vs | ΔPSNR-Y | ΔSSIM-Y | Δ flicker ratio |
|---|---|---:|---:|---:|
| A | C0 | +0.871456 | +0.005218 | −0.014920 |
| A | C1 | −0.320994 | +0.000360 | −0.003672 |
| A | C2 | +1.346587 | +0.021510 | −0.063039 |
| B | C0 | +0.845812 | +0.006773 | −0.003845 |
| B | C1 | +0.213886 | +0.001784 | −0.009324 |
| B | C2 | +3.116046 | +0.011691 | −0.024301 |

### C3 and optional model

- **C3 RealBasicVSR: NOT RUN.** The source tree has no RealBasicVSR adapter and `mmagic` is absent from the active Python environment. No custom CUDA build or unpinned loader was introduced.
- **Optional extra model: NOT RUN.** No extra checkpoint was chosen or downloaded.

### Owner-review videos

Both videos are H.264, 8-bit `yuv420p`, 3600×1280, with panels labeled Degraded / C1 / C2 / C5 / C7:

- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\owner-review-2\D3_clip_A_C1_C2_C5_C7.mp4` — 300 frames, 10.010 s.
- `C:\Users\pro\Documents\VideoEnhancer-P1a-4\owner-review-2\D3_clip_B_C1_C2_C5_C7.mp4` — 150 frames, 5.005 s.

## Verification, warnings and remaining work

- `ruff check .`: PASS after formatting the detector; all checks passed.
- `ruff format --check .`: PASS, 64 files already formatted.
- `pyright src`: PASS, 0 errors, 0 warnings, 0 informations.
- CPU tests: PASS, 112 passed, 3 skipped, 15 deselected, 40.49 s.
- GPU tests: PASS, 15 passed, 115 deselected, 37.49 s.
- CI: PASS, GitHub Actions run [37551478789](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/37551478789), Linux and Windows CPU checks.
- `git diff --check`: PASS after the final report edit.
- Private media committed: NO.
- GUI test: NOT RUN; not requested.
- Commit/push: PASS, commit `595d891` pushed to `origin/p1-restoration-gui`; upstream and local HEAD matched at completion.

Known limitation: the original encoded glitches were absent in the current Standard rerun, so their generation stage and root cause remain unverified. The detector change catches the old frames in offline replay and has synthetic coverage, but it does not repair a corrupted frame already written by a past run. No model weights, videos, crops or contact sheets were added to the repository.
