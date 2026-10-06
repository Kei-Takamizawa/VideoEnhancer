# CURRENT_TASK: Cycle P1a (Real enhancement pipeline, validated on the GPU)

- **Task ID:** VE-P1a
- **Date:** 2026-10-06
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) when you finish; the format is in §12.

**Branch:** continue on `p1-restoration-gui` (it already contains your P1 groundwork). Commit and push your work regularly. Open a **draft** pull request to `main` right away, titled "P1a: real enhancement pipeline". Never push to `main`.

This cycle replaces the earlier, larger P1 instruction. The service/API, the Electron GUI and the trial viewer are **postponed to P1b** and must not be built now. What was already done for P1 (privacy hygiene, Smart App Control guidance, process GPU-memory sampler, model stages, presets, cost-model groundwork) stays, but the items below must be completed and verified.

---

## 1. Purpose

Make the `fast` and `standard` presets produce correct, seamless, bounded-memory output on the real GPU, measure them honestly, and let the owner judge the picture quality with his own eyes from the command line.

Quality is still unverified: nobody has yet looked at what BasicVSR++ does to the owner's sample videos. Everything in this cycle exists to answer that question reliably.

---

## 2. Product principles (they decide every quality trade-off)

- The target look is **the original video before compression**. Remove compression damage: blocking, ringing/mosquito noise, banding, smeared hair, eyelash and fabric detail.
- Keep the source look: beauty filters, makeup and color grading. **Never synthesize texture the source does not have** (for example pores on a beauty-filtered face). No generative or diffusion models.
- Temporal stability first: no flicker, no visible seams between clips or segments.
- Long jobs must be reliable and memory must stay bounded.

Decisions already made: NVIDIA only; offline file conversion only; non-commercial project (non-commercial model licenses are allowed, code is MIT); web/SNS videos up to about 2 hours; the UI language is English.

Reference machine: Windows 11, RTX 4060 Ti **8 GB**. Peak VRAM for `standard` must stay at or below **5 GB**, and peak RAM at or below **6 GB**.

---

## 3. Known facts from your reports

- P0 bench (FP16): BasicVSR++ NTIRE decompression: 15 frames of 720×1280 in 4.82 s (about 3.1 fps), 1.03 GB. RIFE 4.25: 46.2 ms per 1080×1920 pair, 1.16 GB. NVDEC H.264 720×1280: 1,850 fps. NVENC HEVC Main10: 191 fps.
- Rough `standard` budget: about 0.32 s/frame restoration + 0.046 s RIFE + overlap overhead, which is about 2.2–2.7 input fps (22–27 GPU-hours for a 2-hour video).

## 4. Problems found in the current branch (from reading `pipeline/runner.py`, `presets.py`, `stages.py`)

1. **Unbounded memory in the restoration path.** `process_segment` has a special branch for `restore` that decodes the **whole segment** into a Python list, runs all stages on the whole tensor, and only then encodes. A 450-frame segment is about 2.5 GB at 720×1280 FP16 for the input alone, and the processed output at 1080×1920 (about 12.4 MB per frame, 900 frames) is about 11 GB. This violates the 5 GB VRAM / 6 GB RAM limits and the "bounded independent of video duration" rule that the P0 streaming path satisfied.
2. **No clip scheduler.** BasicVSR++ is a bidirectional recurrent model over a clip. Clips need a designed overlap, and they must **never cross a hard scene cut**; the runner does neither.
3. **Segment boundaries.** Context frames from the neighbouring segment must be used at segment edges, except where a scene cut separates them.
4. **Two code paths.** `fast`/`p0-test` use the streaming path, `standard` uses a different path. This hides bugs. There must be one streaming path.
5. RIFE and BasicVSR stages are untested on the GPU, and the process GPU-memory counter is unverified on WDDM.
6. `README.md` links to ten translations in `docs/readme/`. The owner wants English only.

---

## 5. Requirements

### R1. README: English only

- Delete every translated README: the ten files under `docs/readme/` (ar, es, fr, hi, id, ja, ko, pt, ru, zh) and the folder if it becomes empty.
- Remove the language-selector line at the top of `README.md` (the line that starts with "English ·" and links to the translations). Remove any other reference to the translations from the repository (docs, tests, CI, `pyproject.toml`, `.gitignore`). Search for `docs/readme`.
- Keep the README in plain English for non-technical readers, as it is now. Keep the "Windows Smart App Control" section. Update the second paragraph to match the product state at the end of this cycle: say that restoring compression damage and smoother motion are now available from the command line, and that a graphical interface is planned. Do not use technical terms other than "NVIDIA RTX graphics card". Do not add screenshots of real people.
- If any test or tool checks the translated files, remove that check.

### R2. One streaming pipeline with a clip scheduler

Rebuild `process_segment` so that **every** preset uses the same bounded, three-worker streaming design (decode → compute → encode, bounded queues). Delete the special `restore` branch.

Design rules (you choose the internals):

1. **Restoration clips.**
   - The compute stage assembles clips of `clip_length` source frames (default to be decided by the sweep in R3) and passes each clip through the restoration model once. Clips overlap by `clip_overlap` frames on each side.
   - Frames in the overlap are used as model context but are **not output twice**. Each output frame is taken from the clip where it is farthest from the clip edge (the centre-most clip). State the ownership rule in the code and in `docs/ARCHITECTURE.md`.
   - A clip must never contain frames from both sides of a hard scene cut. When a cut falls inside the planned clip, end the clip at the cut and start the next clip right after it. The first and last frames of a cut-bounded clip have no neighbouring context on the cut side; handle them by running the model with fewer context frames (for example replicate the edge frame, or let the clip be shorter). Document the choice and measure that it does not create visible artifacts at cuts (R5, seam metric on a cut).
   - At segment boundaries, read `clip_overlap` extra source frames before the segment start and after the segment end (the existing `context_before`/`context_after` mechanism), unless a scene cut separates them from the segment. The segment's output must be identical, within FP16 tolerance, to what a single uninterrupted run of the whole video would produce for the same frames (R5 test).
2. **Bounded memory.** The number of full-resolution frames resident at any time is bounded by a function of `clip_length`, `clip_overlap`, the batch sizes and the queue sizes, and does not depend on the segment length. Keep decoded frames on the GPU only as long as needed; keep the queues small. Prove the bound with a unit test that counts live frames with a fake model, and with the GPU memory measurements in R6.
3. **Stage order.** restore (at source resolution) → resize → interpolate (RIFE) → encode. For `fast`, restore is skipped.
4. **Frame ownership and timestamps** remain rational and exact, as in P0. For 2× interpolation, interpolated frames belong to the left source frame. N input frames produce exactly 2N output frames per segment, and the segment totals are unchanged from P0.
5. **Abort.** The abort check must be honored within the existing 10 s budget even in the middle of a long clip. Make the clip size small enough, or add checks between model sub-steps.
6. **Failure handling.** If a clip's output contains NaN/Inf, retry that clip once in FP32; if it still fails, fail the segment with a clear message. On CUDA out-of-memory, retry once with a smaller clip length; log it.

### R3. BasicVSR++ restoration: validate on the GPU

- Verify that the model loaded by `BasicVSRRestoreStage` is identical to what the P0 bench measured (same weights file SHA-256, same adapter). Re-use the code; do not create a second loader.
- Input and output are RGB float16, nominal [0,1]; do not clip between stages.
- **Clip sweep** on the reference GPU, input 720×1280, `clip_length` in {15, 21, 30}, `clip_overlap` in {2, 3, 4}, measuring for each combination: seconds per owned frame (including overlap cost), peak VRAM (Torch reserved and process dedicated memory), and the seam metric (R5). Pick a default and put the whole table in the report. The default must keep peak VRAM of the whole `standard` pipeline at or below 5 GB.
- Add a regression test (CPU, with a fake or tiny model) for the clip scheduler: output frame count and order, ownership (an identity model reproduces the input exactly), that no clip crosses an injected scene cut, and the live-frame bound.

### R4. RIFE interpolation: validate on the GPU

- Run the real Practical-RIFE 4.25 stage on GPU frames at 1080×1920: verify the padding to the stride (1088) and the exact crop back, that the output frame count is exactly 2N, and that the original frames pass through bit-exact when the stage only inserts frames.
- Scene cuts: no interpolation across a hard cut (duplicate instead). Test with the 9-cut sample and with a synthetic two-scene clip.
- Failure fallback: implement the mean-flow and difference-from-average checks described earlier (the interpolated frame falls back to plain blending or duplication when motion is extreme). Defaults must be sensible and configurable. Count fallbacks per job and write them to the job report. Test with injected extreme motion.
- NaN/Inf in a pair: fall back for that pair and count it.

### R5. Seam and fidelity metrics (built in, reported per job)

- **Seam metric:** the mean absolute difference between consecutive output frames at clip joints and at segment joints, divided by the same quantity measured at non-joint positions. Report it for the five samples and for a 60-second synthetic panning clip. Target: at most 1.3.
- **Fidelity guard:** for each segment, downscale the output to the input size and compute PSNR and SSIM against the **input** frames; write the mean and the minimum to the job report. There is no pass/fail threshold yet. The designer will set one from your numbers.
- **Flicker metric (new):** the mean absolute difference between consecutive frames of the output divided by the same value for the input (both at the same resolution), per sample. A value far above 1 means added flicker; far below 1 means over-smoothing. Report it.

### R6. GPU memory measurement: verify on hardware

- Validate the Windows `GPU Process Memory(pid_*)\Dedicated Usage` sampler on the real machine. Show that it returns a plausible non-zero value for the engine process, that it moves when you allocate and free a known amount (for example 1 GB through PyTorch), and compare it with Torch's reserved memory. If the counter does not work on WDDM, document exactly what happens and implement the best alternative that measures **this process only** (for example PDH with the correct instance names, or `torch.cuda.mem_get_info` before/after with other GPU programs closed). Never substitute the device-wide NVML value for a process value.
- Sample every 60 s during jobs and write the series into the job log and report. Report which source produced each number.
- Soak criterion: between minute 10 and the end, the engine's dedicated GPU memory grows by at most **150 MB** and Torch's reserved memory by at most **100 MB**, RSS by at most 200 MB.

### R7. Estimates for the real stages

- Extend the cost model with the restore stage (including the overlap overhead) and RIFE at output resolution. Run `ve bench --calibrate` so the profile contains the new stages, and store it.
- `ve add` prints estimates for `fast` and `standard` side by side, with the calibrated flag and the range.
- Accuracy: verify the same targets as before (initial calibrated estimate within ±30%, within ±15% after 10% progress) on the 60-minute `standard` run in R9.

### R8. Command-line trial with a side-by-side comparison (so the owner can judge quality without the GUI)

Add `ve trial <input> [--start SECONDS] [--seconds N] [--preset fast|standard] [other output options] [--out DIR]`:

- Defaults: start at the middle of the video, `N = 5`.
- Run the real pipeline on that excerpt (with proper context frames before and after, and without scene-cut crossing) and write, in `--out`:
  1. `original.mp4`: the source excerpt resized with the **same resize filter and output size** as the enhanced output (so the two are directly comparable), no interpolation, encoded H.264 8-bit high quality.
  2. `enhanced.mp4`: the pipeline output at the full output frame rate, encoded H.264 8-bit high quality, same size.
  3. `comparison_split.mp4`: a single video that shows the original on the left half and the enhanced result on the right half of the same frame, with a thin vertical divider and the labels "Original" and "Enhanced" in a corner. To keep the frame rates equal, show the original at the enhanced frame rate by frame duplication.
  4. `report.json`: preset, measured fps, per-stage times, peak VRAM, seam/fidelity/flicker metrics for the excerpt.
- Print the measured speed and the estimated total time for the whole video at that speed ("At this speed the whole video would take about 21 h 40 m").
- Do not write into the repository. Print the output paths. This feature must work on the CPU backend too (slowly) so that it can be tested.

### R9. Verification runs on the reference machine

1. `pytest -m gpu` and the CPU suite.
2. **Quality outputs:** run `ve enhance` for `fast` and `standard` on all five samples, and `ve trial --seconds 5` at three positions for each sample with `standard`. Keep all outputs **outside** the repository (a folder next to the samples) and list the paths in the report. The owner will look at them.
3. **Seam and cut tests** from R2 and R5 on the samples and on synthetic clips.
4. **Speed:** report `standard` and `fast` input fps end to end on the five samples, with a per-stage time table (decode, restore, resize, RIFE, encode, other). Requirement: `standard` at least 2.0 input fps, with a goal of 2.5. If you cannot reach 2.0, do not hide it: report where the time goes and what you tried (for example `channels_last`, `torch.compile`, CUDA graphs, larger clips, fewer overlap frames). TensorRT is allowed but optional and must not make installation hard on Windows.
5. **`fast` soak:** a 2-hour synthetic 720×1280 30000/1001 fps input with audio, a schedule forcing at least 2 pauses. Pass conditions: the job completes with the exact expected frame count, zero crashes, memory criteria in R6.
6. **`standard` run:** at least 60 minutes of wall time on a 2-hour synthetic input (it will not finish; that is fine), with one forced pause and resume, then a clean stop and a verified resume. Report memory trends, fps, the per-stage table, and the estimate error at 10% of the planned segments within the run window. For this run use a synthetic input that has natural-looking content (for example derived from the samples' pixel statistics or a long loop of public-domain footage you generate), not a pure test pattern, because the model's speed does not depend on content but the artefacts do.
7. **Resume compatibility:** a job created by P0 must still resume.

### R10. Housekeeping from the earlier plan, still open

- A3: a test that simulates the PyNvVideoCodec import being blocked and checks that `ve probe` and `ve enhance` print the specific Smart App Control message.
- A4: test the FFmpeg fallback question concretely: check the Authenticode signature of the `ffmpeg.exe` you use (PowerShell `Get-AuthenticodeSignature`), and whether it runs with Smart App Control on, if you can verify that safely. If you cannot test it, say so. Do not turn Smart App Control on or off yourself.
- G2: update `docs/THIRD_PARTY_MODELS.md` (BasicVSR++ and RIFE as product models, with license and source), `docs/ARCHITECTURE.md` (the one streaming pipeline, clip ownership, presets), and `docs/DEVELOPMENT.md` (`ve trial`).
- G1: push and make CI green on Windows and Ubuntu.
- Keep sample names out of every committed file; keep the hash-based test passing.

---

## 6. UI/UX

No GUI in this cycle. CLI output is concise English with consistent units (h/m/s, %, fps, GB), local times with weekday, and clear error messages that say what failed, which job and segment, and what to do next. `ve run` shows the job, segment k/n, fps, ETA and the next pause time.

---

## 7. Technical constraints

- Windows 11 first; no WSL; no custom CUDA compilation; prebuilt wheels are fine.
- No non-commercial source code copied into this MIT repository. BasicVSR++/MMagic (Apache-2.0) and RIFE (MIT) are fine and are fetched at runtime from pinned sources, as in P0.
- No network access at processing time, except explicit model downloads.
- Peak VRAM ≤ 5 GB and peak RAM ≤ 6 GB for `standard`.
- All code, comments, docs and the report are in English.
- Do not commit media, weights, generated videos or private sample content. Do not rewrite git history.

---

## 8. Out of scope

- Service/API, Electron GUI, trial viewer, tray, schedule editor UI (P1b).
- Face detection or face restoration (P2). Learned upscalers, diffusion or generative models.
- Installer, code signing, auto-update, wake from sleep.

---

## 9. Acceptance criteria

- **A1** README is English only: no translation files, no language line, no remaining references; README still plain-language, with the Smart App Control section.
- **A2** One streaming path for all presets. The live-frame bound test passes (CPU). Measured peak VRAM ≤ 5 GB and RAM ≤ 6 GB on `standard`.
- **A3** Clip scheduler tests pass: identity-model ownership is exact, no clip crosses a cut, segment boundaries are equal to an uninterrupted run (within FP16 tolerance on the GPU, exact on the CPU).
- **A4** Clip sweep table is in the report and the default is justified.
- **A5** RIFE: exact 2N frames, bit-exact pass-through of original frames, no interpolation across cuts, fallback counters and injected-failure tests pass.
- **A6** NaN/Inf and CUDA out-of-memory retry paths are covered by tests (injected).
- **A7** Seam metric ≤ 1.3 on the five samples and the synthetic pan; fidelity and flicker numbers reported per sample and preset.
- **A8** Process GPU memory counter verified on hardware (or the alternative documented and implemented); the `fast` 2-hour soak passes the memory criteria in R6.
- **A9** `standard` ≥ 2.0 input fps end to end, or a justified shortfall report with the per-stage table.
- **A10** The 60-minute `standard` run: no crash, memory trends flat, pause/resume and clean-stop resume work, estimate accuracy within ±15% at 10% of planned segments and ±30% initially.
- **A11** `ve trial` produces the four files and the speed line; outputs for the five samples exist outside the repository, and the paths are listed.
- **A12** The Smart App Control mock test passes; the FFmpeg signature question is answered or marked untested.
- **A13** P0 jobs still resume. CI is green on Windows and Ubuntu. No media or weights are committed.

---

## 10. Builds and tests

`uv sync --locked`, `ruff check .`, `ruff format --check`, `pyright src`, `pytest -m "not gpu and not soak"`, `pytest -m gpu`, `ve bench --calibrate`, the sweep, the speed and quality runs, the `fast` soak, the 60-minute `standard` run. Anything that cannot run in your environment is marked NOT RUN with the exact command for the owner. Never report a test as passed if it did not run.

---

## 11. Checks for the owner (visual, after the PR)

The owner will open the files from `ve trial` (`comparison_split.mp4` first) and the five full outputs. He judges, with his own eyes:
1. Does `standard` remove compression damage (blocks, haze around edges, banding, smeared hair) on faces and hair?
2. Does it keep the beauty-filtered look (no new pores, no waxy or over-smoothed look, no flicker)?
3. Does `fast` look different from a plain resize?
4. Are there visible seams every few seconds (clip boundaries) or at scene cuts?

---

## 12. Report to write in `.ai/LAST_REPORT.md` (English)

- Summary by requirement (R1–R10), deviations and reasons.
- Environment: OS, GPU, driver, and Python, torch, CUDA, PyNvVideoCodec, FFmpeg versions.
- Results for A1–A13: PASS / FAIL / NOT RUN with commands and numbers.
- The clip sweep table; the per-stage time table; seam, fidelity and flicker tables per sample; fallback counts; memory trends from each source.
- Paths of the quality outputs (outside the repository).
- Known issues, risks, and questions for the designer. State clearly anything you could not verify.
- Exact reproduction steps for anything the owner must run.
