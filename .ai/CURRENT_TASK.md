# CURRENT_TASK: VE-P1e-3d2 (estimates for the faster engine, calibration that keeps the finalization curve, estimate gate rerun)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3d2
- **Date:** 2026-10-30
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`, which equals `main` 38b41ae (P1e-3d1 merged) plus this task commit. Open a new draft PR when the operator pushes.
- **Where:** `codex exec` as usual. No Computer Use is needed.
- Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.
- Never touch the owner's normal app or its data. Use isolated homes under `work\scratch\`. Synthetic media only.
- **Every path you write must be under `work\`.** Build paths from an absolute `work\` root, and check before any long run that the output root starts with `D:\my-workspace\VideoEnhancer\work\`. Redirect TEMP to `work\scratch\tmp`, as in P1e-3d1.
- **Long runs.** The gate jobs in section 6 take hours. Record each run's start, its isolated home and its process IDs in the evidence folder before you start waiting, so a resume after an interruption can find and check it. If a run is interrupted (usage limit, app update, capacity stop), re-run only that run, and report the interrupted one as interrupted. Never use a partial run as a gate result.

## 2. Where this cycle sits

P1e-3d1 made the engine faster without changing output bytes: a warm part worker (start-up of parts 2..N fell from 4.542 s to 0.149 s), C1 kept on the GPU (+0.755%), and faster Compare. The estimator and the built-in RTX 4060 Ti profile still describe the old engine:

- `predict_segment` (`estimate/model.py`) adds one per-part start-up, `startup_by_preset` (standard 4.49 s, fast 2.55 s), to **every** part. With the warm worker only the first part, and the first part after each worker replacement, pays the cold start.
- Local learning (`estimate/local.py`) takes the median of recent `startup_samples` without telling cold and warm parts apart, so it will settle on a mix that fits neither.
- The built-in profile (`estimate/profiles/rtx-4060-ti-8gb.json`, revision `p1e2-stage-sizes2`) was measured before the VRAM cap (P1e-3a), the warm worker and C1 residency.
- **Settings > Run speed calibration throws away the long finalization curve.** `bench/runner.py` (around line 1316) sets `profile["finalization"] = calibrate_finalization(target)`. That is a linear fit (`a`, `b`, `c`) on four tiny clips (at most 900 frames). The built-in profile has a measured piecewise curve (`points` from 1, 30 and 120 minute outputs, P1e-2 Part F), and `predict_finalization` uses `points` when they exist. After a calibration the curve is gone, and the 120-minute prediction falls back to the tiny-clip line. P1e-2 showed what that line does: 4.2 s predicted against 19.1 s actual on the 10-minute job.
- Calibration also writes a fixed `segment_overhead_seconds = 2.0` and no `startup_by_preset`, so a measured profile predicts start-up worse than the built-in one.
- `service/downloads.py` `gpu_test_prediction` uses the same per-part start-up for a model's qualification run, which always starts a fresh worker.

Out of scope: any change to output pixels or audio, models, presets, settings defaults, the GPU memory cap, GPU admission or preemption, the player, Compare speed, and C17.

## 3. Part A: start-up in the estimator

1. **Two start-up terms per preset:** a cold start (a fresh worker: child entry, CUDA, model loading, weight verification, decoder open, parent IPC) and a warm start (a reused worker). Store them in the profile as `startup_by_preset: {preset: {"cold": s, "warm": s}}`. Keep reading the old flat form as cold = warm = the old value, so older profiles and the owner's existing local data still load.
2. **Which parts are cold.** Follow the worker rules in `docs/part-worker-lifecycle.md`. In the first estimate, the first part of a job and every 50th part after it are cold, and the rest are warm. While a job runs, a part that will start in a fresh worker (after a failure, a retry, a pause or a resume) counts as cold. Put this rule in one function that both the estimator and its tests use, not in two copies.
3. **Local learning.** Record whether each part's start-up was cold or warm (the controller knows whether it reused the worker), and learn cold and warm medians separately, each over the last 20 samples, per preset. Exclude spilled parts, as today.
4. **Old local data.** Bump `estimate_revision` (for example `p1e3d2-warm1`), so timing observations learned on the old engine are not mixed into the new profile. The existing revision check in `local.py` `_key` already does this. Do not delete or rewrite any existing observation file.
5. `gpu_test_prediction` uses the cold term.
6. **Tests:** cold/warm assignment for 1, 2, 50, 51 and 120 parts; a resumed job; a failed part followed by a retry; old flat profile still loads; local learning keeps cold and warm apart; the revision bump ignores old observations.

## 4. Part B: calibration keeps the finalization curve

1. Settings calibration must never replace a measured `points` curve with the tiny-clip line.
   - Keep the built-in `points` (they come from real 1, 30 and 120 minute outputs on this PC's class of disk).
   - Still run the tiny-clip measurement, but store it as a diagnostic (`finalization.tiny_clip_fit`) and use it only when there is no curve at all (an unknown GPU without a built-in profile).
   - If you think the tiny clips should scale the curve for a slower or faster disk, report the ratio you measured and what scaling it would give, but do not apply it in this cycle. Write it under "Questions for the designer".
2. Calibration measures `startup_by_preset` cold and warm. Use the real `ProcessExecutor` with `reuse=True` on a short synthetic job with at least 3 parts, per preset (Standard and Fast), at the reference size. Cold = part 1; warm = the median of the later parts. Stop writing the fixed `segment_overhead_seconds = 2.0` when a measured value exists.
3. Calibration time: report the old and new wall time. The added time is at most 90 s. Update the "about N min" shown in Settings only through the existing `calibration_minutes` value, not by changing the GUI.
4. **Tests:** after a simulated calibration over a profile that has `points`, the `points` are unchanged and `predict_finalization` for 1, 10, 30 and 120 minute jobs is unchanged; with no curve, the tiny-clip fit is used; startup terms are written in the new form.

## 5. Part C: a new built-in profile for the faster engine

1. On the owner's PC (RTX 4060 Ti 8 GB), in an isolated home, run the full calibration on `main` 38b41ae plus your Part A and B changes. Build the new `rtx-4060-ti-8gb.json` from it:
   - stage and model coefficients, size points up to 1440 output, `max_measured_output_pixels`, cold and warm start-up per preset;
   - keep the finalization `points` and `samples` from the current built-in profile unchanged (P1e-3d1 did not change finalization);
   - the new `estimate_revision`, and a `provenance` line that names the commit, the date and the method.
2. Run the calibration 3 times. Report each coefficient's median and spread. Use the median. If any coefficient's spread is above 10%, report it and say which runs differ and why, as far as you can tell.
3. Report a table of the old and new values for each term.

## 6. Part D: estimate gate rerun

Every gate job runs in a **fresh** isolated home with the new built-in profile and no local observations, the way a new user starts. Run each one once. If a run is interrupted, re-run it in a new fresh home.

| Job | Gate |
| --- | --- |
| G-10: the P1e gate job: 10-minute portrait Standard C1, 1080x1920/60 HEVC, test hours with a 15-minute gap placed in the second half of the job | first estimate within ±10% of the actual processing time; first finish time within ±10% of the elapsed time from adding to done, gap included; live finish time at 50% within ±5%; finalization prediction within ±25%. Also report the live finish time at 25% and 75% (no gate). |
| G-1440: 30-second portrait Standard C1, 1440x2560/60 output | first estimate within ±15% |
| G-Fast: 2-minute 1080p landscape Fast, 2x fps, H.264 | first estimate within ±10% (new) |
| G-Cal: after G-10, run Settings calibration in that same home, then recompute G-10's finalization prediction from its manifest | within ±25% of G-10's actual finalization (this proves Part B) |

- Report each job's predicted and actual totals, the per-part predicted and actual times for cold and warm parts, and the error in percent.
- Do not tune the profile on a gate job's own result and then re-run the same job. If a gate fails, report why from the per-part data, and say what change would fix it. The cycle is then PARTIAL for that gate, and the designer decides.

## 7. Allowed files

- `src/videoenhancer/estimate/**` (including the built-in profile JSON) and `src/videoenhancer/bench/**`.
- `src/videoenhancer/schedule/controller.py`, only to record whether a part started cold or warm.
- `src/videoenhancer/service/engine.py` and `src/videoenhancer/service/downloads.py`, only where they read start-up terms or estimates.
- `tests/**`.
- New measurement scripts under `gui/scripts/`.
- `docs/` for a short note on the estimate terms.
- Nothing else. Do not change the GUI, models, model manifests, presets, settings defaults, packaging, CI workflows or the LGPL build. If something else seems needed, explain it under "Questions for the designer" and do not change it.

## 8. Checks before the report

- The full CPU suite, the GPU suite `-m "gpu and not soak"`, ruff, ruff format, pyright, GUI lint and Vitest. All must pass. Do not loosen or skip tests.
- Close everything you started and report the PIDs. Delete the cycle's scratch files after recording their sizes. Evidence goes under `work\evidence\VE-P1e-3d2\`, at most 300 MB. Never commit media or captures. Persistent growth at most 1 GB. Report free space on C: and D:.

## 9. Report

- Part A: the start-up model, the cold/warm rule, and the tests.
- Part B: what calibration now writes, the old and new calibration wall time, and the tiny-clip ratio if you measured one.
- Part C: the three calibration runs, medians and spreads, and the old/new table.
- Part D: the gate table with every number, and the per-part cold/warm data.
- Changed files.
- A short Japanese summary at the end for the owner (3-6 lines).
- **COMPLETED** only if every gate in section 6 passes and every check in section 8 passed. Otherwise PARTIAL.
