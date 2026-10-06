# CURRENT_TASK: Cycle P1a-2 (Fix the white frame, prove the gain objectively, finish P1a)

- **Task ID:** VE-P1a-2
- **Date:** 2026-10-07
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end (format in §9). Continue on branch `p1-restoration-gui`; PR #2 stays a draft until all acceptance criteria are PASS or have a justified exception. Do not push to `main`.

This cycle continues P1a (the earlier instruction text is in your current `.ai/CURRENT_TASK.md`; keep its principles and its unfinished items, restated below). The GUI and local API remain postponed (P1b).

---

## 1. What the owner saw on the P1a outputs (RTX 4060 Ti, five private samples)

1. Faces, hair, the beauty-filtered look, and `fast` vs plain resize: no complaints. Seams and cuts: fine **except one defect**:
   - **A single white frame flashes for an instant about 6 seconds before the end of sample-05** (the clip with 9 scene cuts, 30.5 s long). Which preset it appears in is not known; check both `fast` and `standard`.
2. **The `standard` improvement is not clearly visible.** The owner thinks this is partly because the source is already fairly clean (720×1280, 1.5–2.8 Mbps). So we cannot yet tell whether the restoration works well, or does little, or does little on good input only.

## 2. Product principles (unchanged)

- The target look is the original video before compression. Remove compression damage; keep the source look, including beauty filters. Never synthesize texture the source does not have. No diffusion or generative models.
- Temporal stability first. Bounded memory. Peak VRAM for `standard` ≤ 5 GB (Torch reserved and process dedicated memory), RAM ≤ 6 GB. Reference machine: Windows 11, RTX 4060 Ti 8 GB.

## 3. Requirements

### R1. Find and fix the white frame (highest priority)

- Reproduce it: re-run `fast` and `standard` on sample-05 and find the frame(s) with an abnormal luminance jump (for example, compute per-frame mean luma of the output and of the input, and flag outputs whose mean luma deviates strongly from both neighbours while the input does not). Report the output frame index, timestamp, preset, segment index and clip index.
- Determine the root cause. Likely suspects, to check and not to assume: scene-cut handling at clip or segment edges (edge-frame replication, context frames from the other side of a cut), RIFE at a cut or at padding/crop, a segment or clip boundary, FP16 overflow or NaN/Inf that was clamped, a wrongly owned or duplicated frame, color conversion on a frame with unusual values, or decoder frame ordering.
- Fix it. Add a regression test that fails without the fix (CPU with a fake model when possible; a GPU test if only the GPU reproduces it).
- Add a **permanent detector** to the pipeline: per output segment, check each frame's mean luma (and, cheaply, a downscaled-frame difference) against the neighbours and against the input; flag isolated outliers in the job report with the frame index. Make it a unit-tested function. For a flagged frame in the real pipeline, retry the clip once; if it persists, record it in the report without failing the job.
- Verify on all five samples and both presets that no flagged frames remain.

### R2. Measure the real gain objectively (degraded-input benchmark)

We do not have clean-vs-compressed pairs, so create them. The owner's samples are the "clean" side, and we degrade them ourselves. Then the restored output can be compared with the known original.

1. Script `scripts/make_degraded.py` (committed; it creates files outside the repo and never stores samples in git). For each of the five samples produce degraded versions with FFmpeg and libx264:
   - **D1:** same size, `-crf 30`, `-preset veryfast`.
   - **D2:** same size, `-crf 36`, `-preset veryfast`.
   - **D3:** downscale to 480×854 (Lanczos), `-crf 28`, then upscale back to 720×1280 with bicubic (a low-resolution plus compression case).
   - **D4:** same size, `-b:v 400k`, two-pass or `-maxrate/-bufsize` capped, `-preset veryfast`.
   Record each file's bitrate and size.
2. Run these through candidate restoration pipelines **at the sample's own resolution and frame rate (no resize, no interpolation)** so that the output can be compared pixel by pixel with the original sample. Metrics per pipeline, per degradation, per sample, over all frames (or at least 150 frames from the middle of each, to save time):
   - PSNR (Y channel), SSIM, and **LPIPS** if you can install it without friction (optional; if you cannot, say so).
   - Flicker ratio (mean absolute consecutive-frame difference of the output divided by that of the original).
   - The difference of each metric against the **degraded input itself** (that is the real gain), and against plain bicubic (null baseline).
3. Candidates (report any that cannot be made to run, with the reason):
   - **C0:** the degraded input itself (reference).
   - **C1:** current `standard` restoration (BasicVSR++ NTIRE 2021 decompression), with the current clip settings.
   - **C2:** Real-ESRGAN `realesr-general-x4v3` (already benchmarked in P0; BSD-3-Clause) applied to the degraded frame, then downscaled by 4× with an area/Lanczos filter back to the original size. Use batch sizes that fit in 5 GB. This tests whether a learned model that was trained for real-world degradations does better, even though it hallucinates detail. Report speed too.
   - **C3 (optional, if it loads without custom CUDA builds):** RealBasicVSR (Apache-2.0, through the pinned MMagic source and your existing torchvision adapter) at 4×, then downscale, or at 1× if the checkpoint supports it.
   - **C4:** C1 followed by a mild, fixed unsharp mask (strength a single constant you pick, report it). This tests whether the visible gain is mostly sharpness.
4. Write the results into `.ai/LAST_REPORT.md` as tables and also to `docs/BENCHMARK_DEGRADED.md` (no sample names, no frames of people). State plainly which candidate wins on each metric and on which degradation, and whether the gain is positive at all on D1–D4.
5. **Do not change the default preset based on this benchmark.** Report. The designer and the owner decide, after looking at the pictures.
6. For the owner's visual check, also produce, outside the repository, a **side-by-side comparison video for two degraded cases** (D2 and D3) of one sample: left original, middle degraded input, right C1 output (and one more video with C2 instead of C1 in the right panel). H.264 8-bit, same resolution per panel, labels "Original / Degraded / Restored". List the paths.

### R3. Reduce `standard` memory (it exceeded the 5 GB cap)

Measured: Torch reserved peak 5.641 GB (sample-04) and process dedicated memory sampled at 5.186 GB, on the default clip 21 / overlap 3.

- Find where the reserved memory goes (BasicVSR++ activations, RIFE at 1088×1920, intermediate full-resolution tensors, decode and encode surfaces, allocator fragmentation) and bring both numbers under **5.0 GB** without slowing `standard` by more than 5%.
- Things to consider: smaller clip length, `torch.cuda.empty_cache()` between stages only if it does not hurt speed, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (check that it works on Windows), releasing the restoration activations before RIFE runs, running RIFE on fewer simultaneous frames, sequencing stages inside the compute worker.
- Report the table (clip, overlap, speed, Torch reserved peak, process dedicated peak) for the final default and for two alternatives. Run it on the longest sample (sample-04 and sample-05).
- The default clip/overlap must now be justified by the seam metric (R4), not only by memory.

### R4. Metrics, trial command, calibration (unfinished from P1a)

1. **Seam / fidelity / flicker metrics** exactly as specified before: seam ratio at clip and segment joints (target ≤ 1.3), PSNR/SSIM of the output downscaled to input size against the input, and the flicker ratio. Reported per job and per sample for both presets; add the seam sweep for all nine clip/overlap combinations on a real sample (including sample-05, which has cuts), not only a 30-frame excerpt.
2. **`ve trial`** as specified before: `ve trial <input> [--start S] [--seconds N] [--preset fast|standard] [--out DIR]`, writing `original.mp4`, `enhanced.mp4`, `comparison_split.mp4` (original on the left half, enhanced on the right half, thin divider, labels), and `report.json`; print the measured speed and the projected total time. Must work on CPU too.
3. **Calibration:** make `ve bench --calibrate` measure the restore and RIFE stages and store real coefficients; verify the estimator's accuracy (initial within ±30%, within ±15% at 10% progress) on the 60-minute run below.

### R5. Long-run verification

1. **`fast` soak:** a 2-hour synthetic 720×1280 30000/1001 fps input with audio and a schedule forcing at least 2 pauses. Memory criteria: between minute 10 and the end, the engine's dedicated GPU memory grows ≤ 150 MB, Torch reserved ≤ 100 MB, RSS ≤ 200 MB. Exact expected frame count, zero crashes. Run the new luma-outlier detector over the whole output and report the count.
2. **`standard` run:** ≥ 60 minutes of wall time on a 2-hour input derived from the samples (for example the five samples concatenated and looped, so that it contains real content and many scene cuts), with one forced pause and resume, then a clean stop and a verified resume. Report memory trends, fps, the per-stage table, the estimate error at 10%, and the outlier-detector count.
3. A job created by P0 still resumes.

### R6. Remaining housekeeping

- Smart App Control mock test (simulate a blocked PyNvVideoCodec import; `ve probe` and `ve enhance` must print the specific message).
- Keep the sample names out of every committed file and test names; the hash-based test must keep passing. `docs/BENCHMARK_DEGRADED.md` and the report must refer to samples only as `sample-01`…`sample-05` (same order as before).
- CI green on Windows and Ubuntu.

## 4. Constraints

- Windows 11, no WSL, no custom CUDA compilation, prebuilt wheels fine. No non-commercial source code copied into this MIT repository. No network at processing time except explicit model downloads. Do not commit media, weights, generated videos, or any frame or crop of the private samples. All code, comments, docs and the report are in English. Do not rewrite git history.

## 5. Out of scope

GUI, local API, trial viewer, face detection/restoration, installer, diffusion/generative models, changing the default preset based on the benchmark.

## 6. Acceptance criteria

- **A1** The white-frame root cause is explained in the report with the frame index and cause; a regression test fails without the fix; the detector is unit-tested; zero flagged frames on all five samples for both presets.
- **A2** `make_degraded.py` and the degraded benchmark exist; tables for C0–C4 (C3 optional) over D1–D4 for all five samples are in the report and in `docs/BENCHMARK_DEGRADED.md`; a plain statement of which candidate wins and whether C1 gains over the degraded input.
- **A3** Side-by-side videos for D2 and D3 exist outside the repository; paths listed.
- **A4** `standard` peaks (Torch reserved and process dedicated) are both < 5.0 GB on sample-04 and sample-05, with speed loss ≤ 5%.
- **A5** Seam metric ≤ 1.3 for the chosen default on all samples and on the 60-second synthetic pan; the nine-combination seam sweep table is in the report.
- **A6** `ve trial` works (GPU and CPU) and produces the four files and the speed line.
- **A7** Calibration populates restore/RIFE coefficients; estimate accuracy within ±30% initially and ±15% at 10%.
- **A8** `fast` soak passes; `standard` 60-minute run passes with resume.
- **A9** Smart App Control mock test passes; P0 jobs resume; CI is green; nothing private is committed.

## 7. Builds and tests

`ruff check .`, `ruff format --check`, `pyright src`, `pytest -m "not gpu and not soak"`, `pytest -m gpu`, the degraded benchmark, the seam sweep, `ve trial`, `ve bench --calibrate`, the `fast` soak and the 60-minute `standard` run. Anything that cannot run is marked NOT RUN with the exact command. Never report a test as passed if it did not run.

## 8. Checks for the owner after the PR

1. Watch the side-by-side D2 and D3 videos: does "Restored" look closer to "Original" than "Degraded" does, and does it keep the beauty-filtered look?
2. Watch sample-05 `fast` and `standard` around 6 seconds before the end: no white frame.
3. Open a `ve trial` `comparison_split.mp4` on any sample.

## 9. Report (`.ai/LAST_REPORT.md`, English)

Summary by requirement; environment; A1–A9 with PASS / FAIL / NOT RUN and numbers; the white-frame root-cause write-up; the degraded benchmark tables and the plain-language verdict; the memory table; seam/fidelity/flicker tables; per-stage times; output paths outside the repository; known issues and questions for the designer; exact reproduction steps for anything the owner must run.
