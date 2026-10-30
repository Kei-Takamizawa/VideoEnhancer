# CURRENT_TASK: VE-P1e-3d1 (faster Compare, a warm part worker, bit-identical speed-ups, two player fixes)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3d1
- **Date:** 2026-10-29
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`, which equals `main` c28b461 plus a merge commit. Open a new draft PR when the operator pushes.
- **Where:** `codex exec` as usual. No Computer Use is needed in this cycle; measure with scripts and your own-window capture, as in P1e-3c2.
- Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.
- Never touch the owner's normal app or its data. Use isolated homes under `work\scratch\`. Synthetic media only.
- **Every path you write must be under `work\`.** In F3 an e2e run wrote 376 MB to `D:\my-workspace\VideoEnhancer\scratch` because `[IO.Path]::GetFullPath('../../scratch/...')` resolved against the process directory, not the PowerShell location. Build paths from an absolute `work\` root, and check before any long run that the output root starts with `D:\my-workspace\VideoEnhancer\work\`.

## 2. Where this cycle sits

P1e-3d is split into two cycles:

| Cycle | Content |
| --- | --- |
| **P1e-3d1 (this one)** | Compare speed, a warm part worker, bit-identical speed-ups from P1e-2 O9, and two player fixes |
| P1e-3d2 | Calibration that keeps the long finalization curve, then the estimate gate rerun on the faster engine |

Out of scope: any change to output pixels or audio, model choice, presets, settings defaults, the GPU memory cap from P1e-3a, GPU admission or preemption between jobs, calibration and estimates (P1e-3d2), and C17 one-pass thumbnails. C17 is dropped: P1e-3a showed that it changes scene cuts and output bytes.

## 3. The rule for every speed change: bit-identical output

A speed change ships only if the output is byte-identical to `main` c28b461 (the G5 check):

- Compare: the SHA-256 of every preview file (Original and each model) is identical.
- Jobs: the final output file's SHA-256 is identical for each fixture in section 7.
- If a change is not bit-identical, do not ship it. Report the change, the differing hash, and the gain you measured.
- Run the baseline from a scratch checkout of c28b461, as in P1e-3c2 Part C. Do not overwrite the working tree.

## 4. Part A: Compare speed

### 4.1 Baseline (P1e-3c2 Part C, 2d996bc)

Fixture: a 6 s 512x288 30 fps synthetic input, a 5 s Compare, Standard (C1 cleanup + RIFE), 1080 short side, 2x fps, H.264. Idle case:

| Measure | Seconds |
| --- | ---: |
| First tile observed | 17.5 |
| Complete | 52.2 |
| Model load | 2.1 |
| Decode (wall) | 19.4 |
| Restore | 10.0 |
| RIFE | 9.1 |
| Encode | 1.4 |
| Original preview transcode | 13.7 |

The stages overlap, so do not sum them. A 19.4 s decode wall for 6 s of 512x288 is far above what NVDEC or the CPU should need. Find out what that time is (waiting, per-model re-decode, synchronous reads, a CPU path) before you optimise anything else.

### 4.2 Work

1. **Profile first.** Extend `gui/scripts/compare-profile.py` so each stage reports its own wall time and the time it waited on another stage. Report a timeline for one idle run.
2. **Remove waste that keeps the output identical.** Examples, all to be confirmed by your profile: decode the range once and share the decoded frames between the Original preview and the models; run the Original preview transcode in parallel with the model run instead of before it, or reuse the source bytes when the browser can play them as they are; keep models loaded between Compare clicks in the same engine session (section 5's worker can serve this).
3. **Second click.** When the owner runs Compare again on the same file and range with another model, reuse the cached Original preview and decoded range. Use a bounded cache: at most 2 ranges, at most 1 GB of RAM, cleared when the source file's size or modification time changes, and cleared when a processing job needs the GPU memory.

### 4.3 Targets (idle, same fixture, same PC)

| Measure | Target |
| --- | --- |
| First tile observed | ≤ 9 s |
| Complete | ≤ 30 s |
| Second click with another model: first tile | ≤ 6 s |
| Busy case (a Standard job running) | no more than 5% slower than baseline; admission policy unchanged |
| Preview hashes | identical to baseline |

Run each case 3 times and report the median. If a target cannot be met bit-identically, report the profile that shows why, and the best result you reached. The cycle is then PARTIAL for that target, and the designer decides.

## 5. Part B: a warm part worker for jobs

Today `schedule/controller.py` spawns a fresh child process for every part. The part start-up terms (child entry, decoder open, model loading, weight verification, CUDA init, first memory sample) are paid again for every part. P1e-2 measured about 7.6 s per part; part of that, the PDH sample, has since been removed.

- Keep one worker process per job and reuse it for the job's next parts. Load the models and verify the weights once per worker.
- **Keep the safety of a fresh child.** Replace the worker with a fresh one after any of these: a part fails, the watchdog fires, a CUDA OOM or its half-clip retry, a spill is detected, abort or pause, a change of model or settings, or 50 parts in one worker. The existing retry rules and their order must not change.
- One worker at a time per GPU, as today. When the job ends or is cancelled, the worker exits within 5 s, and no worker process remains.
- **Measure:** on a 2-minute 1080p synthetic Standard job, report the median start-up per part for part 1 and for parts 2 to N, before and after. Target: parts 2 to N at most 40% of the baseline median.
- **Tests:** worker reuse; replacement after each of the events above, using fakes where a real GPU event cannot be forced; no leftover process after cancel, after an error, and after engine shutdown.

## 6. Part C: bit-identical candidates from P1e-2 O9

P1e-2 measured these single-run gains: keeping C1 loaded (+3.4%), skipping the overlap frames a part does not own (+3.4%), and CUDA streams (+5.4%). Try each on top of Part B. Ship one only if section 3 holds for every fixture in section 7. Report each one's gain as the median of 3 runs on the 2-minute job, and the hashes.

## 7. Fixtures for the G5 check

Synthetic only, made by your fixture scripts:

- 30 s 1080p 30 fps landscape and 30 s 1080x1920 portrait, Standard and Fast, H.264 and HEVC, 2x fps on and off (at least 6 combinations, including both orientations and both presets);
- the 2-minute 1080p Standard job from section 5;
- one source with a hard cut, and one variable-frame-rate source.

## 8. Part D: two player fixes

### 8.1 The divider sometimes flashes (owner check item 14, △)

The owner reported that, while dragging the Before/After divider during playback, the divider line rarely appears for an instant. Hypotheses, unverified:

- The HTML divider line (WebView2) and the two DComp clips update in different frames, so for one frame the line and the picture edge disagree.
- The two clips are computed in different units: `_video` uses `w * divider` in output pixels and `before` uses `original_size.0 * divider` in original pixels. After scaling, their edges can differ by a pixel, so a thin gap or overlap shows.

Reproduce it first. Drive the divider through IPC at drag speed during playback, capture your own player window with WGC at the display rate, and count the frames where the divider line and the clip edge differ by more than 1 physical pixel, or where a gap shows. Fix the cause. Over 60 s of dragging, at most 0 such frames. Add a unit test for the edge arithmetic.

### 8.2 Esc in the fallback dialog

F3 noticed that Esc does not close the History dialog while the HTML5 `<video>` has focus. Make Esc close the dialog, except while the video is in full screen, where Esc leaves full screen first. Add a Vitest test.

## 9. Allowed files

- `src/videoenhancer/**` and `tests/**` for Parts A to C.
- `gui/scripts/compare-profile.py` and new measurement scripts under `gui/scripts/`.
- `gui/src-tauri/player/src/**`, `gui/src/player/**`, `gui/src/HistoryDetail.tsx`, and their tests, for Part D.
- `docs/` for a short note on the worker's life cycle.
- Nothing else. Do not change models, model manifests, presets, settings defaults, packaging, CI workflows or the LGPL build. If something else seems needed, explain it under "Questions for the designer" and do not change it.

## 10. Checks before the report

- The full CPU suite, the GPU suite `-m "gpu and not soak"`, ruff, ruff format, pyright, GUI lint, Vitest, the player Playwright e2e, and Rust tests and clippy for the player crate. All must pass. Do not loosen or skip tests.
- Close everything you started and report the PIDs. Delete the cycle's scratch files after recording their sizes. Evidence goes under `work\evidence\VE-P1e-3d1\`, at most 300 MB. Never commit media or captures. Persistent growth at most 1 GB. Report free space on C: and D:.

## 11. Report

- Part A: the profile timeline, what the 19.4 s decode wall was, each change and its gain, the target table, and the hashes.
- Part B: the start-up table and the replacement tests.
- Part C: each candidate, shipped or not, with its gain and hashes.
- Part D: the cause found for the flash, the frame counts before and after, and the Esc fix.
- Changed files.
- A short Japanese summary at the end for the owner (3-6 lines).
- **COMPLETED** only if every shipped change is bit-identical, the targets in 4.3 and 5 are met, the flash count is 0, the Esc test passes, and every check in section 10 passed. Otherwise PARTIAL.
