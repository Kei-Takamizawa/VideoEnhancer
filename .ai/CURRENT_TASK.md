# CURRENT_TASK: Cycle P1a-5 (Standard-preset determinism and corrupted frames, stronger restoration for heavily compressed sources)

- **Task ID:** VE-P1a-5
- **Date:** 2026-10-07
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Continue on `p1-restoration-gui`; PR #2 stays a draft. Do not push to `main`. Two tasks. Do Task A first. Memory tuning, `ve trial`, seam/fidelity metrics, calibration, soaks and the SAC mock remain deferred to P1a-6.

Principles unchanged: the target look is the original before compression; keep beauty-filtered looks; never synthesize texture the source lacks; no diffusion/generative models. No private names or frames in committed files (`sample-01`…`sample-05` only).

---

## What we learned from P1a-4

- The owner's "brief white at the edges near 21 s" matches **old Standard frame 1327 (22.14 s)**: whole-frame luma 118 / 77 / 118 with chroma/spatial corruption, absent from the source and from old Fast. A second corrupted frame exists at old Standard frame 562 (9.38 s). Both are one-frame defects written by the P1a-1 Standard pipeline. The current rerun is clean, but **nobody has shown that the cause is gone**. Frame 562 is an even output frame (restoration output); frame 1327 is an odd frame (RIFE-inserted between source frames 663 and 664), so the corruption appeared in both the restorer path and the interpolator path, which suggests a shared cause (FP16 overflow, uninitialised or reused GPU buffer, a stale tensor from a pool, a race between the decode/compute/encode threads, or NVENC surface reuse), not a model quirk.
- The owner viewed the P1a-3/4 benchmark videos. **D2 (heavy compression, full size, CRF 36)** is where the owner wants a clearly stronger restoration. For **D3** the owner sees C1, C2, C5, C6, C7 as almost the same; so those candidates are not worth pursuing further.

## Task A. Prove the Standard pipeline cannot write corrupted frames

1. **Repeatability test.** Run the current `standard` pipeline on sample-05 **three times** with identical settings. Decode each output and hash each frame. Report whether the three outputs are bit-identical. FP16 GPU kernels may legitimately differ slightly; if not identical, report the number of differing frames per pair and the maximum per-frame mean-absolute difference, and run the detector over every output. Also run once more with the compute stage forced to FP32 for the restorer (if the pipeline has such an option) and compare.
2. **Stress for races.** Run Standard on sample-05 with: (a) the decode/compute/encode queues set to their smallest sizes, (b) the largest sizes, (c) a segment length of 20 s so that many segment boundaries occur. Run the detector over all outputs. If any flagged frame appears, record the frame index, the stage and the segment/clip, and fix the cause with a test that fails before the fix.
3. **Inspect the code for the usual causes** and report your findings plainly: buffer or tensor reuse across frames in the restore stage and RIFE stage (in-place ops on shared tensors, `out=` arguments, preallocated pools, CUDA stream usage without synchronisation, a `non_blocking` copy that is read before it completes), the hand-off from the compute thread to the encoder thread (is a tensor handed over by reference while the compute thread still writes into it?), and NVENC input surface reuse (is an input surface rewritten before the encoder is done with it?). For every such place state what guarantees ordering, or add the missing synchronisation and a test. Compare the code of these paths between the P1a-1 commit and now, and list the changes that may explain why the corruption vanished.
4. **Make the corruption harmless even if it recurs.** The detector already flags isolated outliers. Add a **post-encode-independent check at the hand-off**: after the compute stage produces each frame and before it is handed to the encoder, compute a cheap summary (per-channel mean on a downscaled copy, plus a NaN/Inf and out-of-range check). Compare it with the two neighbouring frames and with the input frame at the same timestamp, and if it is an isolated outlier, recompute that clip once (restorer) or that frame pair once (RIFE); if it persists, fall back to the nearest valid frame for that position and record it in the job report. Unit-test with an injected corrupted tensor. Keep the overhead below 2% of Standard time and report the measured overhead.
5. Report exactly what you could prove and what remains unexplained. Do not claim a cause that you did not demonstrate.

## Task B. Stronger restoration for heavily compressed, full-size sources (D2)

### Owner's goal

On D2 the current C1 already looks natural (no melted hair) but the owner wants **clearly stronger restoration of the compression damage** (blockiness, mosquito noise, smeared detail). Candidates must not smooth skin, not remove beauty-filter look, not invent texture.

### Candidates (same method as P1a-3: sample-04 and sample-05, D2, 150 middle frames, source resolution and fps, PSNR-Y, SSIM-Y, flicker ratio, speed, peak Torch reserved)

Run these in order; skip with a stated reason if one cannot run without custom CUDA builds:

1. **C5** C1 applied twice (already implemented): D2 numbers.
2. **C8** C1 followed by a pass of Real-ESRGAN `realesr-general-x4v3` (as in C2) and area downscale, blended 50/50 with the C1 output (already implemented as C7 on D3): D2 numbers.
3. **C2** on D2 for reference.
4. **C9** C1 on the degraded input where the degraded input is first passed through the **same restorer at a stronger setting if the checkpoint family offers one**. Check the MMagic/BasicVSR++ model zoo for another compressed-video-enhancement checkpoint (for example, a different QP or a larger variant; state licence and SHA-256); if there is one, evaluate it as C9 and also test an average of its output and C1.
5. **C10** a **second learned decompression model with video or frame inputs** that fits 5 GB and has a licence acceptable for non-commercial use (search the current literature and model zoos: for example, models from the NTIRE and AIM compressed-video-enhancement and quality-enhancement challenges, or an FBCNN-type blind JPEG/video-frame restorer through spandrel). Pick **one** and state licence, checkpoint hash and why. Evaluate alone and as 50/50 with C1.
6. **C11** one **non-learned guard**: C1 followed by a light edge-preserving deblocking/deringing filter (state the filter and constants). Include only to test whether the remaining damage is high-frequency blockiness; never recommend it if it lowers SSIM-Y.

For each candidate and each D2 clip: the metrics table with gains over C0 and C1, speed (fps), and peak Torch reserved memory.

Produce, outside the repository in `owner-review-3`, side-by-side videos of sample-04 D2 and sample-05 D2 (10 s from the same windows; 5 s for the shorter one): panels labeled Original / Degraded / C1 / and the best two new candidates by your metric judgement (not a visual one). If the frame is too wide, make two videos.

Write the tables into `docs/BENCHMARK_DEGRADED.md` (no sample names, no faces) and the report. Do not write conclusions about visual quality and do not change the default preset.

## Acceptance criteria

- **A1** Three-run repeatability result and the stress-run table (detector flags per run) are reported.
- **A2** Code-path review of the hand-offs is reported, with the missing synchronisation fixed or each place shown safe.
- **A3** The hand-off outlier check with recompute and fallback exists, unit-tested with an injected corruption, overhead measured and below 2%.
- **A4** If Task A found any corruption: a failing-before regression test; otherwise a plain statement that none occurred in N output frames.
- **A5** D2 candidate tables (C5, C8, C2, C9 or reason, C10 or reason, C11) with speed and memory.
- **A6** Side-by-side videos in `owner-review-3`, paths in the report.
- **A7** `ruff`, `pyright`, CPU and GPU suites pass; CI green; nothing private committed.

## Report (`.ai/LAST_REPORT.md`, English)

Summary per task; A1–A7 with PASS / FAIL / NOT RUN; tables; what is proven vs unexplained; paths outside the repository; known issues and questions; exact reproduction steps.
