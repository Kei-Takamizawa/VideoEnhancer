# CURRENT_TASK: Cycle P1d-2 (accurate estimates, safe deletion, finish UI v2)

- **Task ID:** VE-P1d-2
- **Date:** 2026-10-11
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** continue on branch `p1d-ui-v2` (draft PR #5, head `6a91197`). PR #4 is merged into `main` as `efb45e3`. First merge `origin/main` into `p1d-ui-v2` with a merge commit (no rebase, no force-push), so that the PR is compared with the real base. Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Update the report again after the final CI run, so it never says "pending CI". Do not push to `main`.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option that keeps existing outputs unchanged (or skip only that item), and continue. Stop early only if every remaining item is blocked.
2. **New:** an open question is not a blocker when this task already gives a fail-closed rule for it. Implement the safe parts and the guard, then ask.
3. Order: Part E (estimates) → Part S (safe deletion) → Part F (first look) → Part U (finish UI v2) → Part P (performance) → Part R (robustness) → Part G (acceptance) → Part X (optional). Long GPU measurements run whenever the GPU is free.
4. If time runs out, finish earlier items completely and mark the rest NOT RUN. Never report a test as passed if it did not run.
5. The owner's queue, settings and videos on this PC are not test data. Use synthetic footage and a separate engine home for every test.

## 0. Status after P1d (review of `6a91197`)

Accepted as done (keep, do not redo):
- **D:** the 7 design components, byte-identical, and `design/p1d/README.md`.
- **A2 to A5:**
  - A2: cancel keeps finished previews.
  - A3: the busiest part skips scene cuts.
  - A4: AV1 minimum size 130×66, a Keep-size job and a 3-segment job verified.
  - A5: docs and missing tests.
- **B1:** the global pause flag. **B2:** cancel and remove.
- **B4:** History removal with Undo. **B6:** event-stream cache and the 400 ms preview.
- **U1, U2, U4, U5:** window shell, dock, zoom and theme in code. Schedule screen mostly done.
- **G5:** the 14 GPU strict-equality and D2 tests pass. **CI:** 4 of 4 green.

Designer answers to the three P1d questions:
1. **Recycle Bin:** you were right that no shell flag guarantees recycling before deletion. Part S makes the result safe whatever the shell does, using a hard-link guard. Build it now.
2. **Estimates:** part of the miss was my instruction. I told you to scale one stage by a whole-pipeline speed ratio. Part E replaces A1.
3. **Remaining UI and measurements:** Part U lists every gap found in review. Part P adds the measurement harness that was missing.

## 1. Part E: estimates that follow the chosen models

**What went wrong:**
- `reference_speed.fps` is the speed of the whole pipeline, but the ratio multiplied only the restore term (`estimate/model.py:205-208`).
- `size_model` adds no cost at all (`model.py:295`). The SPAN estimate equals the plain C1 estimate.
- `model.py:170` doubles single-frame restore cost when fps is doubled, although restore runs once per source frame.

**New rule:**
1. Keep today's estimate for the default pipeline of each mode. It is the one that "Run speed calibration" and the per-job correction already tune.
2. For each non-default model, add a per-source-frame delta: `Δ = 1 / fps_ref(model) − 1 / fps_ref(category default)`. Both values come from `reference_speed`, measured in the same reference pipeline on the same GPU. A job with several non-default stages adds their deltas.
3. Remove the single-frame `restore_factor` 2.0. The reference speed already contains the real cost.
4. **Without a usable reference** (different GPU, or none):
   - the estimate is marked "uncalibrated" and its shown range widens to ±25%;
   - "Run speed calibration" also measures every installed, verified non-default model on the reference clip and stores the result per GPU.
5. The Add cards, the Up next times, admission control, the planner and Compare's "About X for this video" all use this one function.

**Acceptance on the RTX 4060 Ti:**
- **Clip:** synthetic, 30 s, portrait 720×1280 at 30 fps, output 1080×1920 at 60 fps, HEVC, so that it has several segments.
- **Four jobs:** Standard with C1 (the default), Standard with SCUNet, Standard with C1 + SPAN, and Fast (the default).
- **Gate:** the first estimate, before any per-job correction, is within ±15% of the actual processing time for each job.
- Also report the 2 s clips from P1d again, but they do not gate.
- Report every segment that overran the operating hours. There must be none beyond the one allowed overrun step.

## 2. Part S: safe deletion (P1d B3 and B5)

The product rule is unchanged: a user's video may go to the Recycle Bin, and must never be permanently deleted by this app. Put all of this in one module. It is the only code allowed to remove a user's video path.

**S1. Preflight.** Any failed check keeps the file and returns "Kept: <reason>":
- the path is exactly the job's recorded output or original;
- it exists and is a regular file, not a symlink, junction or other reparse point;
- it is on a local fixed drive (`GetDriveTypeW` returns `DRIVE_FIXED`) whose file system supports hard links (NTFS or ReFS);
- no unfinished job uses it;
- it is not open in another program, for example a video player. Check this with a share-deny open.

**S2. Journal.** Before any change, append the operation to `<engine home>/deletions.jsonl`: path, size, SHA-256 of the first and last 1 MiB, guard path, time.

**S3. Guard.**
- Create an NTFS hard link to the file in the same folder, named `.<name>.ve-guard-<random>` and marked hidden.
- If the link cannot be created, keep the file.

**S4. Recycle.**
- Use `IFileOperation` with `FOFX_RECYCLEONDELETE`, without `FOF_NOCONFIRMATION`, and with a progress sink.
- Record whether `PostDeleteItem` reported a Recycle Bin item. A non-NULL `psiNewlyCreated` means it went to the bin; NULL means it was fully deleted.
- Show no UI. The service runs without a window.

**S5. Confirm.** It is a success only if all three hold:
- the original path is gone;
- the shell reported a Recycle Bin item;
- the guard still exists with the same size.

Then remove the guard. The result is "Moved to the Recycle Bin".

**S6. Otherwise restore.**
- If the original path is gone without a confirmed bin item, move the guard back to the original path with `MoveFileExW`, without replacing anything. The result is "Kept: the Recycle Bin did not take the file".
- If the original path still exists, remove the guard and return "Kept: <reason>".
- Verify the restored file's size and partial hashes against the journal.

**S7. Crash recovery.**
- At service start, read the journal and finish or roll back every unfinished entry. If the original is missing and no bin item was confirmed, restore from the guard.
- Delete orphaned guards only after their entry is resolved.

**S8. Endpoint and UI (old B3).**
- Delete video files takes job ids plus `{output, original}` and returns a result per file.
- History shows "Moved to the Recycle Bin", "File not found" or "Kept: <reason>".
- "Compare again" is disabled with a reason when the original is gone.
- The History detail panel and the "Delete video files?" dialog follow the design (Part U).

**S9. Delete the original after a verified output (old B5).**
- Implement it exactly as P1d B5 described:
  - the job setting `delete_original_after`, with its default in Settings › After processing, off;
  - the Add switch "Delete the original when it is done";
  - the four output checks: it decodes to the end, the frame count is equal, the duration is within one frame, audio is present when the source had it;
  - the wait while another unfinished job uses the same original;
  - "Original kept: <reason>" in History.
- The destructive step goes only through S1 to S7.

**S10. Tests.**
- **Fake shell**, covering:
  - recycled;
  - fully deleted, where the file must be restored byte-identical;
  - refused;
  - a crash after each of S2 to S5, recovered at restart;
  - a non-fixed drive, a FAT32 or exFAT volume, a file in use, and a reparse point, all kept.
- **On the real PC:**
  - a synthetic file on the system drive goes to the Recycle Bin and the user can restore it;
  - a fake "fully deleted" outcome on the real NTFS volume is restored from the guard, with the same SHA-256;
  - one GPU job with `delete_original_after` succeeds, and one forced check failure keeps the original.

## 3. Part F: first look from the real render

Today each uncached model runs a separate 15-frame render with a second model load.
- Take the "First look" still from the **first completed clip of the actual preview render**. The pipeline already processes clips of 15 frames with overlap, so no extra run or model load is needed.
- The still must equal the matching frame of the finished preview before encoding. Test this on CPU fixtures.
- Measure from GPU admission, not from `render_compare` entry, to the first look and to the full preview, for C1, SCUNet and RIFE 4.25.
  - Target: the C1 first look within 25 s.
  - The total time per model must not be worse than in P1d (C1 75.1 s, SCUNet 196.7 s, RIFE 63.5 s).
- Add a test for the stills endpoint.

## 4. Part U: finish UI v2

The 7 components in `design/p1d/components/` stay the source of truth. Every row below is a gap found in review at `6a91197` and must be closed.

| Area | What to build or fix |
| --- | --- |
| Global | Connecting: the designed panel. Reconnecting: action buttons disabled, with "Last update HH:MM". Unreachable: "Can't reach the engine", Retry and Copy details. The Smart App Control panel as designed. Title bar: the app icon, not the text "VE". |
| Tokens | Control height 32 px and radius 9 px as in the design (today 36 px and 10 px). Check other sizes against the components. |
| Home | "Result only" in Preview result. "Waits until you resume it" for paused videos. "Pause this video. The next one starts instead." as the Pause tooltip. "Your hours this week" as the card title. The designed empty state. Cancel dialog buttons "Keep working" and "Cancel video". While cleanup runs after Cancel, the row shows "Cancelling…". |
| Add videos | The "Delete the original when it is done" switch (S9) and the "File format" label. "Bigger picture" disabled with "More choices come later." when no verified size model is installed. Per-warning fix buttons; see the warning table below. The designed busy and partial states. |
| History | The detail panel with every designed field and action: Play, Show in folder, Compare again, Copy details, Remove from history, Delete video files…. No label may be clipped at 1100×700 or 1280×800, at 100% and 110% zoom. The "Delete video files?" dialog (S8), "Select all" in select mode, the "File not found" and "Moved to the Recycle Bin" states, and the designed empty and no-match states. |
| Schedule | Tooltips anchored to their bar and flipped or clamped inside the window, not pinned at the bottom. Remove `Schedule.tsx` (the Custom dialog and drag code) and its CSS. Port its tests that still apply to `ScheduleView`. |
| Models | The remove-blocked dialog with real reasons: the default for Standard, "N videos in the queue use it, including <file>", "which is being processed now". Details: "Peak GPU memory X GB of N GB" from the detected VRAM, the source host, and "Default for Standard". The busy-install state. |
| Settings | The "After processing" section with the switch (S9), and the hint "Above 100%, small windows can scroll." |
| Compare | A visible range box with click-to-place, Left and Right 1 s, Shift 5 s, and the position slider. The designed Swipe mode with its handle, and zoom as a segmented control. The tile states Waiting ("Starts after the current step, about N min"), First look, "Making preview N%", Ready, and Problem with Try again. The Fast panel ("Fast does not clean up.", Switch to Standard, Compare smoother motion instead). Model descriptions visible. The designed labels; drop "Compare selected models", because rendering is automatic. |

The Add-dialog warnings each get the fix that actually solves them. Today `Queue.tsx:311` shows "Use Keep" for every "too small" warning, which is wrong.

| Warning | Blocks adding | Fix button |
| --- | --- | --- |
| Output too small for cleanup (under 256 px) | yes | "Use 1080" |
| Output too small for AV1 (under 130×66) | yes | "Use HEVC" |
| Not enough space | yes | "Choose a folder…" |
| HDR is not supported | yes | "Remove it", which removes that file |
| Smart App Control is blocking | yes | "Read instructions" |
| The chosen size is smaller than the source (for example 1080 for a 1440×2560 video) | **no**: a note, not a blocker, because shrinking can be intended | "Use Keep" |

GUI tests: bring back coverage for the finalization display ("Finishing: checking the file") and the Alt+Up / Alt+Down reorder, which were lost with the old pages. Add tests for the B8 fields (`waiting_count`, file states, `publisher_url`) and for the warning table.

## 5. Part P: performance harness and budgets

- Add a repeatable harness under `gui/tests/perf/`. Use Playwright for Electron with Performance marks and the Event Timing API. Fixtures:
  - a History of 1,000 records;
  - a queue of 10 videos while one Standard video is running, driven by a fake engine for the renderer budgets and by the real engine for the service budgets.
- **The event stream:**
  - cache each job's manifest by modification time, so it no longer re-reads every manifest each second;
  - cache the AV1 minimum size per GPU and driver version in the engine home, so that about 14 NVENC probes do not run at every service start.
- **Budgets.** Report every number, with how it was taken:
  - the service's event-stream work with 1,000 History records and one idle client: at most 5% of one CPU core;
  - no keystroke in a Schedule time field delayed by more than 50 ms;
  - the preview result shown at most 500 ms after the last keystroke;
  - switching screens: at most 100 ms;
  - input latency: at most 50 ms;
  - idle renderer with progress updating: at most 2% of one core;
  - opening History with 1,000 records: at most 300 ms;
  - progress text: at most once per second.

## 6. Part R: robustness

- **Clear history** either finishes completely or reports what was not removed. The GUI restores any rows it hid optimistically when the service reports an error.
- **Event snapshot:** build the cache key from copies taken under the lock, so that a live operation dict cannot raise "Snapshot unavailable".
- **Cancel:** if `remove()` fails for a hidden `remove_on_cancel` job, the job reappears in History as failed with the reason. It must not stay hidden on disk.

## 7. Part G: acceptance

- **G1:** screenshots of every board in `design/p1d/README.md` from the packaged app with synthetic data:
  - at 1280×800 and 1100×700;
  - dark and light for the 7 main screens, dark for the other states;
  - side by side with the design for the 7 main screens.
  Store them outside the repository and list their paths.
- **G2:** extend the CI e2e clipping test to the Add dialog, Compare and the History detail panel, including tooltips inside the window. It runs in CI.
- **G3:** every Part P budget, with numbers.
- **G4:** the GPU evidence for Part E (4 jobs), Part F (3 models) and Part S (the real-PC checks).
- **G5:** run **all** GPU-marked tests, not only the 14 from P1d: `test_model_registry.py`, `test_source_index.py`, `test_pipeline.py`, `test_p1a_pipeline.py`, `test_media.py`, `test_quality_trial.py` and any others. The default pipeline output must not change.
- **G6:**
  - `ruff`, `ruff format --check`, `pyright`, CPU tests and the D2 suite;
  - GUI lint, typecheck, unit tests, build and e2e;
  - Windows and Ubuntu CI green on the final commit, recorded in the report.
- **The owner's visual check:** not your job. I will write `P1d_owner_check.md` after your report.

## 8. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs are in English.
- **Never commit:**
  - media, weights, previews or generated videos;
  - `node_modules` or build output;
  - the design export or the screenshots;
  - the owner's logs or private sample names.
- **User videos:** never deleted permanently. Only Part S may remove a user's video path, and only to the Recycle Bin, behind the guard.
- No models that add skin texture, and no GAN real-world video models. No new catalog entries.
- Keep the service security model. No telemetry, no auto-update.
- Update `docs/GUI.md`, `docs/API.md` and `docs/TROUBLESHOOTING.md` for every change.

## 9. Part X: optional, only after everything above

- **X1.** Re-qualify the Real-ESRGAN blend with tile 128 and halo 16. It qualifies if the sampled process peak is at most 5.0 GB.
- **X2.** Keep the last compare model loaded for 120 s while the queue is idle. Report the gain, and turn it off if it ever delays a queued job.

## 10. Report (`.ai/LAST_REPORT.md`, English)

- A table per part (E, S, F, U, P, R, G, X): done / partial / NOT RUN / BLOCKED, with evidence (tests, numbers, file:line for key changes).
- **Part E:** for each of the 4 jobs, the estimated time, the actual time and the error.
- **Part S:** the result of each real-PC check, with SHA-256 values.
- "Questions for the designer", each with the default you chose.
- Exact reproduction steps.

Never report a test as passed if it did not run.
