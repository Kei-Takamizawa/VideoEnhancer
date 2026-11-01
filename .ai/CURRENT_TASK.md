# CURRENT_TASK: VE-P1e-3d2b (finish P1e-3d2: complete calibration data, scheduling readers, finalization curve)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3d2b
- **Date:** 2026-11-01
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47` at c6715d6 (VE-P1e-3d2, PARTIAL) plus this task commit. Keep working on top of it. The operator pushes to the same branch, so draft PR #15 continues.
- Read the P1e-3d2 task (in Git history at 69b0450, `.ai/CURRENT_TASK.md`) and your P1e-3d2 `.ai/LAST_REPORT.md` first. Every rule there still holds unless this file changes it.
- Write a new `.ai/LAST_REPORT.md` for VE-P1e-3d2b. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.
- Isolated homes under `work\scratch\`, synthetic media only, every written path under `D:\my-workspace\VideoEnhancer\work\`, TEMP redirected to `work\scratch\tmp`. Never touch the owner's normal app or its data.
- **Before any gate or long run, check the inputs.** Read the calibration report and the profile you are about to use, and stop if any coefficient is null or any benchmark section is "skipped". P1e-3d2 froze its gates on a profile with an unmeasured decode term; do not repeat that.
- Long runs: record start, home and PIDs in the evidence folder before waiting. If a run is interrupted, re-run only that run.

## 2. Answers to your P1e-3d2 questions

1. **H264 sample.** Make calibration generate its own samples. A normal user who presses "Run speed calibration" has no `VE_SAMPLES_DIR` either, so today every Settings calibration leaves decode unmeasured. When no suitable sample is found, `_bench_pynvc_samples` (and the FFmpeg path) must generate a synthetic `h264_720x1280` and `hevc_1080x1920` clip in the calibration's temporary folder with FFmpeg, decode them, and delete them afterwards. Keep `VE_SAMPLES_DIR` as an optional override. Add a test that a calibration with no samples folder produces a non-null decode coefficient (fake decoder allowed).
2. **P0 `source_pts`.** Fix the P0 helper in `bench/runner.py` so it passes `source_pts` (and anything else `media/decode.py` requires). The P0 end-to-end diagnostic must run, not skip. Add a test.
3. **Scheduling readers.** You may change `src/videoenhancer/schedule/planner.py` and `controller.unit_admission`, only so that they use the same cold/warm rule (`estimate/startup.py`) as the estimator. No other scheduling policy changes. Add tests that the planner and admission predictions match `estimate_job` for the same job within 1 s.
4. **Finalization.** See section 4.

## 3. Part A: a complete built-in profile

1. With items 1 and 2 fixed, run the full calibration 3 times on the owner's PC, as in P1e-3d2 Part C. Every component, model, reference point, start-up term and the P0 diagnostic must be measured. Report medians and spreads (flag spread > 10%).
2. Rebuild `rtx-4060-ti-8gb.json` from the medians. Keep `estimate_revision` `p1e3d2-warm1` unless you change the meaning of a field; then bump it. Update `provenance`; remove the INCOMPLETE note.
3. Report the old (main), P1e-3d2 and new values side by side.

## 4. Part B: finalization

The G-10 finalization was predicted at 12.07 s and took 19.32 s (−37.5%). Every step was slower than the curve, and aggregation was 12x slower (0.08 → 1.02 s).

1. **Find out why.** Compare the conditions of the P1e-2 curve samples with the G-10 job: part count and part sizes, output bytes, audio, quality aggregation input, disk and file-cache state (cold or warm), and anything else running (another engine, Defender scanning new files, the owner's normal app). Report what explains the gap, with measurements, not guesses.
2. **Remeasure the curve with independent data.** Produce synthetic Standard outputs of 1, 10, 30 and 120 minutes through the real part pipeline structure (real part count and part files, audio, quality aggregation), under the same conditions as a real job (in particular the same file-cache state as at the end of a real job). Measure finalization 3 times per point and use the median. Do not use the G-10 job or its files.
3. If the cause is a fixed per-job or per-part cost that the curve does not model, you may change the shape of `predict_finalization` (for example a per-part term for aggregation and checkpoint validation). Keep it simple and explain it in `docs/estimate-startup.md` or a new short doc.
4. Keep calibration keeping the curve (P1e-3d2 Part B stays as it is).

## 5. Part C: gates

Re-use the recorded P1e-3d2 gate runs where the gate depends only on the job's actual times and the profile's prediction:

- **Recompute** G-10 (first estimate, first finish time, finalization), G-1440 and G-Fast first estimates from their saved manifests with the new profile and the new finalization curve. The actual times stay as recorded. Report old and new predictions.
- **Recompute** the G-10 live finish time at 50% if the recorded progress data allows it exactly. If it does not, re-run G-10 in a fresh home.
- **New independent check, G-Fin:** a fresh-home 5-minute portrait Standard C1 job, 1080x1920/60 HEVC. Gate: first estimate ±10%, finalization prediction ±25%.
- **G-Cal:** after G-Fin, run Settings calibration in the same home and check that the finalization prediction for G-Fin is unchanged by calibration (the curve, not local learning, must carry it). Report the raw-curve number and the number with local learning separately.

| Gate | Limit |
| --- | --- |
| G-10 first estimate, first finish time | ±10% |
| G-10 live finish time at 50% | ±5% |
| G-10 finalization (raw curve, no local learning) | ±25% |
| G-1440 first estimate | ±15% |
| G-Fast first estimate | ±10% |
| G-Fin first estimate | ±10% |
| G-Fin finalization (raw curve) | ±25% |

Do not tune on a gate job's own result. If a recomputed gate fails, report the per-part and per-step data and stop that gate there; the designer decides.

## 6. Allowed files

- Everything allowed in P1e-3d2 section 7.
- `src/videoenhancer/schedule/planner.py` and `controller.unit_admission`, for item 3 only.
- Nothing else. No GUI, models, model manifests, presets, settings defaults, packaging, CI workflows or the LGPL build.

## 7. Checks before the report

- The full CPU suite (including `tests/test_p1d3.py::test_driver_change_preserves_first_estimate`, which must pass without loosening), the GPU suite `-m "gpu and not soak"` in one uninterrupted invocation if possible (if a usage stop splits it, say so and list each invocation), ruff, ruff format, pyright, GUI lint and Vitest.
- Close everything you started and report PIDs. Delete scratch after recording sizes. Evidence under `work\evidence\VE-P1e-3d2b\`, at most 300 MB. Persistent growth at most 1 GB. Report free space on C: and D:.

## 8. Report

- Items 1-3 with tests.
- Part A: the three runs, medians, spreads, and the old/P1e-3d2/new table.
- Part B: the cause of the finalization gap with data, the new points, and any change to the formula.
- Part C: the gate table with old and new predictions, the actuals, and the errors.
- Changed files.
- A short Japanese summary at the end for the owner (3-6 lines).
- **COMPLETED** only if the profile has no unmeasured term, every gate in section 5 passes, and every check in section 7 passed. Otherwise PARTIAL.
