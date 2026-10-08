# CURRENT_TASK: Cycle P1a-7 (finalization in the estimate, quality metrics without a second full pass)

- **Task ID:** VE-P1a-7
- **Date:** 2026-10-08
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Continue on `p1-restoration-gui`; PR #2 stays a draft. Do not push to `main`. This is the last engine cycle before the GUI (P1b); after it, the owner merges PR #2.

## Background (P1a-6 result)

Everything in P1a-6 passed except one criterion: the completed 2-hour `fast` soak took 17,658.9 active seconds, while the estimate at 10% progress was 13,965.0 s (−20.9%, target ±15%). The initial estimate was −23.0% (passes ±30%). The `standard` 15-minute completed run passed (−10.9% / −9.3%).

Your diagnosis: `estimate/model.py` sums only pending segment predictions; the final assembly, validation and the quality pass (`pipeline/quality.py`, full PSNR/SSIM and difference passes after all segments) are not predicted. The gap is 3,694 s (about 21% of the `fast` job). The thresholds and the actual-total reference stay as they are.

## Design decisions (designer, 2026-10-08)

1. **No second full decode for quality metrics in normal jobs.** The fidelity/flicker metrics are diagnostics; a second pass over a 2-hour output costs the owner close to an hour of extra work per `fast` job. Compute them **inline during segment processing**, on frames that are already in memory (GPU), using a fixed stride (for example every 10th output frame for PSNR/SSIM, every frame for the cheap flicker and outlier summaries; you choose the stride, report it, and keep the inline overhead ≤ 2% of segment time). Store per-segment partial sums in the segment record and aggregate them at the end. The seam metric already uses joint frames; keep it inline too.
   - Keep the full post-hoc pass available for development only: `ve report --full-quality <job>` (or a flag with the same effect), never run by default, not part of the job's time.
2. **Finalization is a predicted stage.** After this change, finalization = assembly (concat/mux) + validation (exact frame count, audio presence, container checks) + aggregation of the inline metrics. Model it explicitly:
   - `finalize_seconds = a + b × output_bytes + c × output_frames` (or an equivalent you justify), with coefficients per machine profile.
   - `ve bench --calibrate` measures it on a short generated job (assemble and validate a few segments) and stores the coefficients.
   - After each completed job, store the observed finalization time and use the ratio observed/predicted as a correction for the next job, the same way segment observations are used.
   - The initial estimate, the remaining-time estimate, and the **day planner** include finalization. Because assembly is aborted outside operating hours, the planner must place finalization inside a window (if the remaining window is shorter than the predicted finalization, plan it in the next window).
   - Progress reporting: a `phase` field (`processing` / `finalizing`) with the step name (assembling, validating, aggregating) and its own percent; the overall percent is weighted by predicted time, so the job never shows 100% while it is still finalizing.
3. Validation should stay exact but cheap: for the frame count prefer a packet/frame count that does not decode every frame, if it is exact for our own outputs (prove it with a test that compares it with a decoded count on a short file); otherwise keep the decoded count and model its cost.

## Tasks

### Task A. Breakdown of the P1a-6 `fast` soak (no rerun needed)

From the existing logs of `fast-soak-fixed`, report: total segment time, assembly time, validation time, quality-pass time, and any idle/wait time inside the active total. Show that these sum to 17,658.9 s. Also report the measured `fast` input fps (15.76) per stage and whether the slowdown against the earlier 17.4 fps comes from the host-input NVENC copy introduced in P1a-5 (report only; do not change it in this cycle unless it costs more than 10%, in which case report the numbers and a proposal).

Also, for `standard-stability-retry`, report the dedicated-memory growth **within each process** (before and after the stop/restart separately), because the 255.9 MB figure spans a restart.

### Task B. Implement decisions 1–3

With tests: inline metrics equal the full post-hoc metrics on the sampled frames (exactly, or within a stated tolerance) on a short CPU job; finalization prediction and planner placement with a fake clock (finalization does not start when it cannot fit in the remaining window, and it starts in the next window); progress never reports 100% before the output is valid; `ve report --full-quality` works.

### Task C. Verification

1. Run `ve bench --calibrate` again (fresh profile).
2. A **fresh completed `fast` run on the same 2-hour synthetic input** with two scheduled pauses (overnight is fine). Report the initial and 10% estimates against the actual active wall time (targets ±30% / ±15%), the finalization prediction against the actual, frame count, detector counts and memory growth (same limits as P1a-6).
3. Re-run the `standard` 15-minute completed accuracy run **only if** the inline metrics add more than 2% to `standard` segment time on sample-04/05; otherwise report the measured overhead and keep the P1a-6 result.

## Out of scope

GUI/API, training, face processing, new models, changes to presets or thresholds.

## Acceptance criteria

- **A1** Task A breakdown reported and sums to the actual total; within-process memory growth reported.
- **A2** Inline metrics replace the default full pass; overhead ≤ 2%; equality test passes; `ve report --full-quality` exists.
- **A3** Finalization is calibrated, predicted, corrected from observations, placed inside operating windows by the planner, and shown as its own phase.
- **A4** Fresh completed `fast` 2-hour run: initial within ±30%, 10% within ±15%, exact frame count, detector 0 final flags, memory limits pass.
- **A5** `standard` overhead reported; 15-minute run repeated if required and within targets.
- **A6** `ruff`, `ruff format --check`, `pyright`, CPU and GPU suites pass; CI green on Windows and Ubuntu; nothing private committed.

## Report (`.ai/LAST_REPORT.md`, English)

Summary; A1–A6 with PASS / FAIL / NOT RUN and numbers; the breakdown table; estimate table (initial, 10%, actual, finalization predicted vs actual); memory table; output paths outside the repository; known issues and questions; exact reproduction steps. Never report a test as passed if it did not run.
