# CURRENT_TASK: Cycle P1a-6 (lock C1, pluggable models, finish engine hardening)

- **Task ID:** VE-P1a-6
- **Date:** 2026-10-07
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Continue on `p1-restoration-gui`; PR #2 stays a draft. Do not push to `main`. Do the tasks in order A → B → C → D; if time runs out, finish the earlier tasks completely and mark the rest NOT RUN.

## Decisions by the owner (2026-10-07)

- **C1 (BasicVSR++ NTIRE 2021 decompression, current `standard`) is the restoration model for the first release.** The benchmark work (C2–C11) stops here; keep the scripts and `docs/BENCHMARK_DEGRADED.md`, but add no more candidates.
- The owner will later **train or fine-tune their own models** (for example, BasicVSR++ fine-tuned on beauty-filtered/made-up footage). The app must make adding such a model possible **without code changes to the pipeline**.

Principles unchanged: the target look is the original before compression; keep beauty-filtered looks; no diffusion/generative models; bounded memory; no private names or frames in committed files.

---

## Task A. Pluggable restoration models (model registry)

Goal: a new model can be added by dropping files in a folder (plus, for a new architecture, one small adapter module), and selecting it in a preset or on the command line.

1. **Model manifest.** Every model is described by a manifest file (`model.toml` or `model.json`; your choice, but one format), stored under `%VE_HOME%\models\<model-id>\`. Fields, at least:
   - `id`, `display_name`, `version`, `description`
   - `task`: `restore` | `interpolate` (later also `face`, `upscale`)
   - `architecture`: the name of a registered adapter (for example `basicvsrpp`, `rife`, `spandrel`)
   - `architecture_params`: adapter-specific (for example channel count, block count for BasicVSR++)
   - `weights`: file name, SHA-256, optional download URL
   - `licence` (free text) and `commercial_use_allowed` (bool)
   - `scale` (1 for same-size restoration), `temporal` (bool) and, for temporal models, the preferred clip length/overlap
   - `precision` (`fp16`/`fp32`) and a declared `vram_estimate_mb` per frame size class (optional, filled by calibration)
2. **Adapters.** A registry of architecture adapters. The existing BasicVSR++ and RIFE code becomes the first two adapters (`basicvsrpp`, `rife`) behind one interface (load, warm up, process a clip or frame pair, release). Add a `spandrel` adapter for single-frame models that spandrel can load (this covers most community restoration models). **A fine-tuned BasicVSR++ checkpoint with the same architecture must work just by adding a manifest that points to the new weights.**
3. **Built-in manifests.** Ship manifests for the current C1 and RIFE 4.25 models; the first-run download keeps working and verifies SHA-256 as today.
4. **Selection.** Presets refer to models by `id` (`standard` = restore `basicvsrpp-ntire21-decompress` + interpolate `rife-4.25`, or similar ids). CLI: `ve enhance … --restore-model <id>` and `--interp-model <id>` override the preset. `ve models list` shows installed models (id, task, architecture, licence, weights verified yes/no). `ve models add <folder>` validates a manifest, verifies the hash, and copies it into `%VE_HOME%\models`. `ve models remove <id>` refuses to remove a built-in model.
5. **Validation and safety.** On load: manifest schema check, hash check, adapter exists, `task` matches the stage. Clear error messages. Loading weights uses `weights_only=True` (or the safest loader available) and never executes code from the model folder; new architectures are added only as adapter modules in the repository.
6. **Job reproducibility.** The job manifest records the model ids, versions and weight hashes used, so a resumed job refuses (with a clear message) if a model changed between segments.
7. **Fine-tuning readiness (documentation only, no training code):** add `docs/ADDING_MODELS.md` (English): how to add a fine-tuned BasicVSR++ checkpoint, how to add a spandrel-supported model, how to write a new adapter, and how to compare a new model with C1 using `scripts/make_degraded.py` and the existing benchmark script. Also state that licences of third-party weights are the user's responsibility and the field must be filled.
8. Tests: manifest parsing and validation (good, missing field, wrong hash, unknown adapter, wrong task), a fake adapter registered in tests runs through the CPU pipeline, model override from the CLI, job-manifest model recording and the refusal on change. A GPU test: a copy of the C1 weights registered under a new id gives bit-identical output to the built-in C1 on a short clip.

## Task B. Detector false positives and memory

1. **Detector at scene cuts.** The P1a-5 runs report 8 raw flags at known source scene cuts on sample-05. Fix the rule so that frames at or adjacent to a detected source cut (and the RIFE frame between the two sides of a cut) are compared only against the same side of the cut. **Repair policy (decided 2026-10-07, replaces "nearest valid frame" duplication):** (a) for a flagged RIFE-inserted frame, the fallback is a plain 50/50 blend of the two adjacent output frames that come from source frames, not a copy of one side; (b) for a flagged restored frame, the fallback is the same source frame passed through the non-learned resize path of the preset (faithful, same size), not a neighbour copy; (c) the repaired frame is re-checked; report raw (pre-repair) and final (post-repair) flag counts separately. **Before repairing, find out why the frame was flagged**: for sample-05 at 26.276 s (not a scene cut), save the unrepaired frame and its neighbours as PNG, and check whether the defect is real and whether it is limited to the bottom band. Suspect first RIFE padding at the bottom/right (1080 is not a multiple of 32/64, so the frame is padded to 1088) and its pad mode/crop; fix the cause if it is in our code, with a test. A4 counts the **final** flags. Target: zero flags on all five samples for both presets, while the existing synthetic-flash, edge-flash, chroma-glitch and endpoint tests still pass.
2. **Memory under 5 GB.** Standard peaks are still above the cap (Torch reserved up to 5.6 GB). Bring both Torch reserved peak and process dedicated memory (PDH) below **5.0 GB** on sample-04 and sample-05, with at most 5% speed loss. Report the table (clip, overlap, fps, Torch reserved peak, PDH peak) for the final default and two alternatives. The default clip/overlap must also pass the seam metric in Task C.

## Task C. Trial command and quality metrics

1. **Seam / fidelity / flicker metrics** per job (stored in the job report): seam ratio at clip and segment joints (target ≤ 1.3; **joints that coincide with a detected source scene cut, within ±1 source frame, are excluded from the pass/fail value**, because the source itself changes there and the metric would measure the cut, not a pipeline seam; report the number of excluded joints, and as a diagnostic also report for every joint, cut or not, the relative seam = output joint ratio ÷ source joint ratio at the same position; if a job has no non-cut joint, the seam value is N/A, not PASS), PSNR/SSIM of the output downscaled to the input size against the input, flicker ratio. Seam sweep for the nine clip/overlap combinations on sample-05: `clip_length` in {15, 21, 30} × `clip_overlap` in {2, 3, 4} (same grid as the original P1a instruction). For each: seconds per owned frame, Torch reserved and PDH peaks, seam ratio. If clip 30 exceeds 5 GB, record the memory and mark its seam as NOT RUN rather than forcing it.
2. **`ve trial`**: `ve trial <input> [--start S] [--seconds N] [--preset fast|standard] [--restore-model ID] [--out DIR]` writes `original.mp4`, `enhanced.mp4`, `comparison_split.mp4` (original left half, enhanced right half, thin divider, labels) and `report.json` (speed, metrics, projected total time for the whole file). Works on CPU too (slow is fine).

## Task D. Calibration and long runs

1. `ve bench --calibrate` measures restore and RIFE stage speed for the installed models and stores coefficients per model id; the estimator uses them. Accuracy: initial estimate within ±30%, within ±15% at 10% progress, checked on the 60-minute run.
2. `fast` soak on a 2-hour synthetic 720×1280 input with audio and at least 2 scheduled pauses: memory growth between minute 10 and the end ≤ 150 MB dedicated, ≤ 100 MB Torch reserved, ≤ 200 MB RSS; exact frame count; detector count reported.
3. `standard` ≥ 60 minutes wall time on a 2-hour input made from the samples (concatenated/looped), one pause/resume and one stop/resume; memory trends, fps, detector count. This run does **not** need to finish; it is the stability test.
4. **Estimate accuracy (decided 2026-10-07):** measured against a **real completed total**, not a projection from the processed part (that would compare the estimator with itself). Use a separate **15-minute** input made the same way (≈ 27,000 frames, about 3 hours at 2.4 fps), run `standard` to completion with calibration applied, and compare the initial estimate and the estimate at 10% progress with the actual wall time (excluding paused time). Targets: ±30% initial, ±15% at 10%. Also do the same comparison on the completed `fast` 2-hour soak.
4. Smart App Control mock test (simulated blocked PyNvVideoCodec import gives the specific message in `ve probe` and `ve enhance`); a job created by P0 still resumes.

## Out of scope

GUI and local API (next cycle, P1b), face processing (P2), training code, new benchmark candidates, changing the C1 model.

## Acceptance criteria

- **A1** Model registry with manifests, adapters (`basicvsrpp`, `rife`, `spandrel`), CLI `models list/add/remove`, model override in `enhance` and `trial`; built-in C1 and RIFE served through it with unchanged output (bit-identical to before on a short clip).
- **A2** A re-registered copy of C1 under a new id runs and matches; invalid manifests are rejected with clear messages; job manifests record model ids/hashes and resume refuses on change.
- **A3** `docs/ADDING_MODELS.md` exists.
- **A4** Zero detector flags on all five samples, both presets; all detector tests pass.
- **A5** Standard Torch reserved and PDH peaks < 5.0 GB on sample-04/05 with ≤ 5% slowdown; memory table reported.
- **A6** Seam ≤ 1.3 for the default on all samples; nine-combination sweep reported; `ve trial` works on GPU and CPU.
- **A7** Calibration accuracy met; `fast` soak and `standard` 60-minute run pass; SAC mock and P0 resume pass.
- **A8** `ruff`, `ruff format --check`, `pyright`, CPU and GPU suites pass; CI green on Windows and Ubuntu; nothing private committed.

## Report (`.ai/LAST_REPORT.md`, English)

Summary per task; A1–A8 with PASS / FAIL / NOT RUN and numbers; memory, seam and calibration tables; soak results; the list of new CLI commands with one example each; output paths outside the repository; known issues and questions; exact reproduction steps. Never report a test as passed if it did not run.
