# CURRENT_TASK: Cycle P1a-3 (two small things: locate the flash, run the degraded benchmark)

- **Task ID:** VE-P1a-3
- **Date:** 2026-10-07
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Continue on `p1-restoration-gui`; PR #2 stays a draft. Do not push to `main`.

This cycle is **deliberately small**: two tasks only. Everything else from P1a-2 (memory tuning, `ve trial`, seam/fidelity metrics, calibration, soaks, SAC mock) moves to the next cycle P1a-4. Finish both tasks completely rather than touching many things. If you run short of time, finish Task A first, then Task B in the order given.

Principles (unchanged): the target look is the original video before compression; keep beauty-filtered looks; never synthesize texture the source lacks; no generative/diffusion models. Reference machine: Windows 11, RTX 4060 Ti 8 GB. No private sample names, frames or crops in committed files; samples are referred to as `sample-01`…`sample-05`.

---

## Task A. Find the white frame in the **old** output

The owner saw a white frame for an instant about 6 seconds before the end of the **P1a-1 `fast` output of sample-05**. The new outputs do not show it, so a re-run cannot reproduce it. But the old file still exists:

- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_fast.mp4` (and, for comparison, `sample-05_standard.mp4` in the same folder).

Your P1a-2 report says the detector was run on "eight prior-cycle outputs" (samples 01–04); it does not say that the old sample-05 files were analyzed. Do this:

1. Run the outlier detector (and a plain per-frame mean-luma dump) on the **old** `sample-05_fast.mp4` and `sample-05_standard.mp4`. Report the exact frame index and timestamp of every flagged frame, and the frame's mean luma versus its neighbours. Also check the **old** `sample-05_standard.mp4`.
2. If the old file contains the white frame: that is a real defect that the current code may or may not still have. Determine which of the old file's segment and clip contained it. Then answer:
   - Was the segment/clip layout the same in the fresh run? Which code changed between the P1a-1 commit and the P1a-2 commit in `pipeline/runner.py` and the stages? Could one of those changes have removed it, or is the pipeline nondeterministic (threads, decoder, NVENC, FP16)?
   - **Determinism test:** run `fast` on sample-05 **three times** with the same settings; compare the three outputs by per-frame hash (decode to raw frames and hash). Report whether they are bit-identical. If they are not, find the source of the difference (thread ordering, non-deterministic CUDA kernels, encoder state) and report it.
3. If the old file has no flagged frame either, say so clearly, and report the luma statistics of frames near 24.4 s (output frame ≈ 1463) of that file. Ask the owner to name the exact file and a timestamp.
4. Keep the detector. If the old file proved a real flash, add a regression test that reproduces its cause, and implement the retry-once for a flagged clip (retry the clip once; if it persists, record it in the report without failing the job).

## Task B. Degraded benchmark and the owner's side-by-side videos

The owner could not find a "restored" video because the benchmark in P1a-2 was not run (only the degraded inputs exist). Run it now, exactly as specified in P1a-2 R2, but do the following in this order so that useful results appear early:

1. **Stage B1 (do first): C0 and C1 on degraded D2 and D3 of sample-04 and sample-05** (the two longest). Use the middle 150 frames. For each: PSNR-Y, SSIM, flicker ratio, and the speed. Compute the **gain against the degraded input itself** (C1 minus C0), and against plain bicubic. Write the table into the report as soon as it exists (commit early).
2. **Stage B2: side-by-side videos** (outside the repository), for sample-04 D2 and D3, 10 seconds each (middle of the video): three panels in one frame, left to right "Original", "Degraded", "Restored". Restored = C1 output at the sample's own resolution, no interpolation. H.264 8-bit, same resolution per panel (so the frame is 3×720 wide; if that is too wide for the encoder, make two videos, or stack the panels vertically; your choice). Also produce the same with C2 in the Restored panel. List the paths in the report and also copy them to one folder named `owner-review`.
3. **Stage B3: C2** (Real-ESRGAN `realesr-general-x4v3` through spandrel, then downscale 4× back to the degraded size with an area or Lanczos filter), on the same material as B1. Report quality and speed. Use batch sizes that fit in 5 GB.
4. **Stage B4: C4** (C1 plus a mild fixed unsharp mask; state the constant) on the same material.
5. **Stage B5: all five samples × D1–D4 × C0/C1** (150 middle frames each), then C2 on the same. If time is short, skip and say so; B1–B3 are the priority.
6. **C3** (RealBasicVSR) only if it loads without custom CUDA builds; otherwise report the reason and move on.

Rules:
- Compare **at the sample's own resolution and frame rate**: no resize, no interpolation, so pixels line up with the original.
- Align frames exactly (same frame count and order); verify by checking that C0 metrics against the original are plausible (for example, D1 PSNR-Y should be lower than the original-vs-original infinity and above 25 dB).
- Report plainly: on which degradation each candidate improves or hurts each metric, and whether C1 improves on the degraded input at all. Do not change the default preset. Do not write conclusions about visual quality; the designer and the owner decide after looking at the videos.
- Put the numbers into `docs/BENCHMARK_DEGRADED.md` (no sample names, no frames of people), and into the report.

## Acceptance criteria

- **A1** The old sample-05 `fast` and `standard` outputs were analyzed, with frame indices and luma values reported; the three-run determinism result is reported; the cause is identified or the absence of a defect in the old file is documented.
- **A2** If a real defect was found: a regression test and retry-once exist and pass.
- **A3** Stage B1 table (C0 and C1 on D2 and D3 of sample-04 and sample-05) is in the report, with gains.
- **A4** The side-by-side videos for sample-04 D2 and D3 (C1 and C2 versions) exist in `owner-review`, with their paths in the report.
- **A5** B3 (C2) and B4 (C4) tables exist. B5 and C3 are done or marked NOT RUN with the reason.
- **A6** `ruff`, `pyright`, CPU and GPU suites pass; CI green; nothing private committed.

## Out of scope

Memory tuning, `ve trial`, seam/fidelity metrics, calibration, soaks, SAC mock, GUI/API, face processing.

## Report (`.ai/LAST_REPORT.md`, English)

Summary by task (A, B), A1–A6 with PASS / FAIL / NOT RUN and numbers, the flagged-frame table for the old outputs, the determinism result, the benchmark tables (B1, B3, B4, B5), output paths (outside the repository), known issues and questions, and exact reproduction steps.
