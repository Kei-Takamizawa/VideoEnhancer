# CURRENT_TASK: Cycle P1a-4 (side-flash near 21 s, stronger restoration for low-resolution sources)

- **Task ID:** VE-P1a-4
- **Date:** 2026-10-07
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Continue on `p1-restoration-gui`; PR #2 stays a draft. Do not push to `main`. Two small tasks only. Finish Task A first. Memory tuning, `ve trial`, seam/fidelity metrics, calibration, soaks and the SAC mock remain deferred to P1a-5.

Principles unchanged: the target look is the original before compression; keep beauty-filtered looks; never synthesize texture the source lacks; no diffusion/generative models. No private sample names or frames in committed files (use `sample-01`…`sample-05`).

---

## Task A. The brief white flash near 21 s in the old sample-05 `standard` output

### What the owner reports (corrected)

- File: `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_standard.mp4` (the P1a-1 output). `fast` was fine.
- The owner sees a very brief whitening **at about the 21-second mark, not at 24.4 s**. In P1a-3 you only inspected frame 1463 (24.4 s), which is the wrong place.
- It looks like **white at the left and right edges of the picture**, not a fully white frame. It may be a player artifact at a scene cut, but this is unverified.
- Your mean-luma detector cannot see edge-only changes. Treat the earlier "no flash" result as not covering this.

### Do

1. Decode the old `standard` and `fast` outputs and the original sample-05 around **19.5–23.0 s** (the output is 59.94 fps, the input 29.97 fps; map by timestamp). For each output frame in the window dump: whole-frame mean luma, **mean luma of the left 8% columns, the right 8% columns, and the centre 84%**, and the same for the input at the matching timestamp.
2. List scene cuts of the input in that window (use the project's scene-cut detector) and the segment and clip boundaries the old pipeline would have used there (recompute with the P1a-1 settings; state how you derived them).
3. Report every frame where an edge-region luma jumps by more than 15 levels (0–255) against both neighbours while the centre does not, in the output and in the input. Report the frame index, timestamp, and values. Also save as lossless PNG (outside the repository, folder `flash-check`) the frames ±3 around the largest such jump, and a 3-panel contact sheet (input / fast / standard).
4. If an isolated edge-region spike exists in `standard` but not in the input: find the cause (suspects: BasicVSR++ zero or replicate padding at clip edges, deformable-offset behaviour near cuts, RIFE border handling, FP16 clamp at the borders, the crop/resize step) and fix it with a regression test that fails before the fix. Then re-run the current code on sample-05 `standard` and show the same table is clean.
5. If no spike exists in any file: say so, and state the maximum edge-region deviation found, so that the owner can look at the exact contact sheet.
6. Extend the permanent detector: besides whole-frame luma, check the left and right 8% column bands and the top and bottom 8% row bands, with the same isolated-outlier rule. Unit tests: synthetic edge-only flash must be flagged; a natural scene cut must not.

## Task B. Stronger restoration for low-resolution (D3-type) sources

### What the owner reports

Looking at the side-by-side videos: for D2 (heavy compression, full size) both C1 and C2 look good and natural, no melted hair. For **D3 (downscaled to 480×854 then upscaled, plus compression) the owner wants clearly stronger restoration**; C1 and C2 look almost the same. The metrics agree: C1 gains only +0.6 to +1.2 dB PSNR-Y on D3 versus +1.6 dB on D2.

### Goal

Find, among a few candidates, one that restores D3 visibly more without hallucinating texture, melting hair, or removing the beauty-filtered look. Do not change the default preset; deliver measurements and videos.

### Do

Use the same material and method as P1a-3 (sample-04 and sample-05, D3, 150 middle frames, source resolution/fps, PSNR-Y, SSIM-Y, flicker ratio, speed). Candidates, in this order (skip with a stated reason if one cannot run without custom CUDA builds):

1. **C5: C1 applied twice** (second pass on the first output). Cheap test of "more of the same".
2. **C6: C1 with an internal 2× pre-upscale** (bicubic/Lanczos to 1440×2560 or the largest size that fits 5 GB), then BasicVSR++, then downscale to the source size (area). Tests whether giving the restorer more pixels helps on blurry sources. If memory does not fit, use a half-size test crop and say so.
3. **C3: RealBasicVSR** (Apache-2.0, pinned MMagic) at 4× then downscale, if it loads with the existing adapter.
4. **C7: Real-ESRGAN `realesr-general-x4v3` blended with C1** at a fixed ratio 0.5 (state the constant), as a middle path between the two looks.
5. Optionally one more spandrel-supported model that fits 5 GB and has a licence acceptable for non-commercial use (state the licence and checkpoint hash). Prefer video or real-world-degradation models. Report why chosen.

For each candidate and each of the two D3 clips: the metric table (also the gain versus C0, C1, C2), speed in fps, and peak Torch reserved memory.

Produce, outside the repository in `owner-review-2`, **side-by-side videos for sample-04 D3**, 10 seconds from the same window as before, H.264 8-bit: left Degraded, then the candidates side by side in order (C1, C2, and the best two new ones by your judgement from the metrics), same labels in the frame. If the frame becomes too wide, make two videos. Also one video with the same layout for sample-05 D3.

Write the tables into `docs/BENCHMARK_DEGRADED.md` (no sample names, no faces) and the report. Do not write conclusions about visual quality.

## Acceptance criteria

- **A1** The owner's file (old `standard`) was analysed in 19.5–23.0 s with edge-region luma; table, scene cuts, boundaries and contact sheet reported.
- **A2** Cause identified and fixed with a failing-before regression test, or the absence of a spike is clearly documented with maxima.
- **A3** Edge-band detector exists with unit tests (edge-only flash flagged, natural cut not flagged); CI green.
- **A4** Candidate table for D3 (C5, C6, C3 or reason, C7, optional extra) with speeds and memory.
- **A5** Side-by-side videos in `owner-review-2`, paths in the report.
- **A6** `ruff`, `pyright`, CPU and GPU suites pass; nothing private committed.

## Report (`.ai/LAST_REPORT.md`, English)

Summary per task; A1–A6 with PASS / FAIL / NOT RUN; the edge-region table and contact-sheet path; the root-cause write-up or the maxima; benchmark tables; output paths outside the repository; known issues and questions; exact reproduction steps.
