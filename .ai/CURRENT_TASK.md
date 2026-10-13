# CURRENT_TASK: Cycle P1e (owner check fixes, clearer screens, long-video estimates)

- **Task ID:** VE-P1e
- **Date:** 2026-10-12
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** continue on branch `p1d-ui-v2` (draft PR #5, head `2e8eb50`). If `origin/main` has moved, merge it in with a merge commit (no rebase, no force-push). Save this file as `.ai/CURRENT_TASK.md` and commit it. At the end, write `.ai/LAST_REPORT.md` in English, and update it again after the final CI run so it never says "pending CI". Do not push to `main`.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option that keeps existing outputs unchanged (or skip only that item), and continue.
2. An open question is not a blocker when this task already gives a fail-closed rule for it.
3. **Order:** Part B (bugs) → Part Q (responsiveness) → Part V (buttons and icons) → Part H (History) → Part M (Models) → Part C (Compare) → Part S (Schedule) → Part O (first-run tour) → Part E (long-video estimates) → Part G (acceptance). Long GPU runs go whenever the GPU is free.
4. If time runs out, finish earlier items completely and mark the rest NOT RUN. Never report a test as passed if it did not run.
5. The owner's queue, settings, videos and Recycle Bin are not test data. Use synthetic footage and a separate engine home for every test.
6. Report every run of a gated measurement. Never select the favourable one.
7. **New: the report file.**
   - The P1d-3 report contains double-encoded UTF-8 (mojibake): one line is about 100,000 characters, and the file is 150 KB.
   - Write `.ai/LAST_REPORT.md` as UTF-8 exactly once. Use ASCII punctuation (`-`, `x`, `<=`). Keep the file under 40 KB, with raw data in the external evidence folder.

## 0. Status

- **P1d-3 is accepted.**
  - Every required item passed, including the deletion fixes, the built-in RTX 4060 Ti profile, live progress, the cheaper event stream and HDR per-file handling. CI is 4 of 4 green.
  - Optional X1/X2 were not run.
- **The owner ran `design/P1d_owner_check.md` on the rebuilt package.**
  - Passed: 1-7, 9, 10, 12, 17 and 18.
  - Need work: 8, 13, 14 and 15.
  - Failed: 11 and 16.
  - This cycle fixes these and makes the owner's requested design changes.
- **Not in this cycle**, planned separately:
  - adding videos from a URL;
  - control from another device's browser;
  - importing models from a URL;
  - P2 face and hair restoration.

  Do not start them.

## 1. Part B: bugs from the owner check

**B1. A finished output cannot be deleted** (owner item 11: "Output: Kept: the file changed after this job used it").
- **Cause:**
  - `media/mux.py:209-210` writes `output_identity` and `output_bytes` into the dict passed to `assemble()`.
  - `schedule/controller.py:946` and `:969` then reload the manifest from the store and save "done" without them.
  - So `service/deletion.py:498` finds no identity, and the legacy check at `:505-509` compares the size with a missing `output_bytes`. It always refuses.
- **Fix:**
  - Capture the identity after `assemble()` returns, and write it into the reloaded manifest before the final save.
  - Add an end-to-end test from job completion to History deletion. No test mentioned `output_identity`.
- **Jobs already finished without any output identity:** accept the output only if both hold:
  - its modification time lies between `started_at` and `finished_at` + 60 s;
  - its probed duration matches the job's planned output duration within one output frame.

  Otherwise keep it with the existing reason.

**B2. A 4K video could not be added** (owner item 16).
- **(a) Stale text.** The History detail modal stayed open under the Add dialog after a deletion, and its result text showed through. The root drop handler (`App.tsx:376`) opens Add on top of any modal.
  - While another modal dialog is open, a drop is ignored, and a short notice says to close the dialog first.
  - The detail modal clears its results when it closes.
- **(b) Why Add was disabled.** The reason is unknown because the owner reported only the stale text. Reproduce every plausible cause with synthetic 4K files and fix each one:
  - **HDR10 and HLG** (`bt2020nc`):
    - `probe(..., allow_hdr=True)` still raises "Unsupported SDR color matrix" (`media/probe.py:155-161`), so the estimate fails with an error instead of the HDR warning.
    - The P1d-3 HDR tests passed because their clips were not tagged `bt2020nc` (inferred). Use correctly tagged PQ and HLG clips.
    - The HDR file gets its own "HDR" warning with "Remove it". The other files stay addable.
  - **Free space:**
    - The check uses about 3.1x the input size, with no credit for downscaling (`jobs/store.py:114-125`).
    - Base it on the estimated output bytes for the chosen size, fps and codec, plus the work files the pipeline really keeps.
    - Show "Needs X GB, Y GB free on D:".
  - **Slow estimate:** `ffprobe -show_packets` on a large file can pass the 30 s client timeout (`gui/src/api.ts:21`).
    - Large files must not fail by timeout. Show "Checking…" per file until it is done.
    - Report how long a 10-minute 4K file takes.
  - **Any estimate error** is shown on that file's row with its reason. It never blocks the other files.
  - **Test files:**
    - 3840x2160 H.264 8-bit SDR BT.709;
    - HEVC or VP9 10-bit SDR BT.709;
    - HEVC 10-bit PQ BT.2020;
    - HLG;
    - unspecified colour.
- **Also check** that a new engine home defaults to AV1 when the AV1 check passes, as the design says. `service/settings.py:15` defaults to HEVC. Fix it if new homes do not get AV1.

**B3. "Pause all" flips the queue** (owner item 8).
- **Cause:**
  - Since `1595b83`, `engine.queue()` and the event snapshot use `store.queue_jobs()`, which follows `os.scandir` order (`jobs/store.py:412`, `:444`). Only `list_jobs` sorts by `position`.
  - Home picks "the first queued job in array order" (`Home.tsx:246-247`), so a paused job A can drop below B.
  - Move actions send array indexes as positions (`Home.tsx:425`, `464`, `474`, `512`).
  - The planner gets the same unsorted list (`engine.py:700`).
- **Fix:**
  - Sort by (`position`, `created_at`) everywhere.
  - Home shows the paused job in the main card as "Paused".
  - Moves use real positions.
- **Test:** at least 3 jobs whose id order differs from their position.
- **Resuming restarts the current part.** This is by design: finished parts are kept, and the part in progress is redone. While paused, the card says so in plain words, for example "Paused. Finished parts are kept; the current part restarts (about 3 min of work)." Use the real predicted length of that part.

**B4. Schedule hours are invisible** (owner item 13).
- `ScheduleView.tsx:237` draws allowed hours as `.hours-block`, which has no position, height or background in CSS (`style.css:1181`). The styled class `.allowed-block` is no longer used.
- Make the hours visible in the same visual language as the design.
- See Part S for the toggle.

## 2. Part Q: responsiveness and feedback

1. **Theme switch:** about 0.7 s today.
   - The renderer waits for a 400 ms debounce, the settings PUT and a refresh of three GETs, and `GET models` hashes every weights file. The native theme follows only on a 3 s poll.
   - Apply the theme at once in the renderer, and through a new IPC to `nativeTheme` and the title-bar overlay. Save in the background.
   - Cache weight hashes by size and modification time, so `GET models` does not re-hash.
   - **Target:** a median of at most 50 ms from click to repaint over 10 runs, for Light, Dark and System.
2. **Add dialog estimate:**
   - Re-request it only when a field that changes the time changes: mode, size, fps, models, strength, or the file list. The codec counts only for bytes and space.
   - "Delete the original when it is done" and the output folder send no time request. The folder still re-checks space.
   - While the dialog is open, refresh the finish times every 30 s and when the window regains focus. Keep the old values on screen until the new ones arrive; "Preparing…" must not come back for an unchanged list.
3. **Durations show seconds.**
   - Use one formatter for every remaining-time display (Work left, Up next, Add, Compare, calibration, downloads): `H:MM:SS`, or `M:SS` under one hour.
   - Use tabular numerals. The existing `duration()` rounds up to minutes (`gui/src/api.ts:97-102`).
4. **Determinate progress, left to right, with time left:**
   - **Calibration** has no progress callback today. Report its stages (decode/encode, tensor stages, end-to-end, models, references, finalization) with fractions. Show the stage name, a bar and the time left, using the expected seconds per stage from the installed models or the last run.
   - **Model download and verify:** report bytes against the known size from `weights.bytes`, as percent and time left.
   - **Compare and preview:** they already report frames; add time left.
   - Remove the extra indeterminate `<progress>` in `OperationStatus` (`Pages.tsx:49`).
   - If a phase truly has no fraction, use elapsed against expected time, capped at 95% until it finishes. Never use a back-and-forth animation.
5. **"Pause all"** is enabled only while a job is running or waiting to run now, and as "Resume all" while paused. Otherwise it is disabled with a tooltip.

## 3. Part V: buttons and icons (applies to every screen)

The owner finds the buttons small and hard to tell apart. Keep the café palette, the dock and the layout, and add a clear hierarchy:

- **Icons:**
  - Use one open-source icon set, bundled locally with no CDN, in the existing outline style. Prefer `lucide-react` (ISC licence) in a current release.
  - Every action button gets an icon next to its label.
  - Icon-only buttons are allowed only where the design already has them (dock, small toolbar controls), with a tooltip and an `aria-label`.
  - Replace text glyphs such as ⋯, ⋮⋮ and ↔ with icons.
  - Keep the dock icons and the Settings gear as they are.
- **Button levels:**

  | Level | Use | Height | Text | Icon |
  |---|---|---|---|---|
  | Primary | at most one per screen or dialog | 40 px | 14 px, weight 600, filled accent | 18 px |
  | Secondary | normal actions | 36 px | 13 px, surface and border | 16 px |
  | Quiet | inline or in menus | 32 px | 13 px, no border | 16 px |
  | Danger | destructive actions | secondary shape | danger colour | — |

  The confirm button inside a delete dialog is filled danger.
- **Primary actions:**
  - Home: "Add videos";
  - Add: "Add to queue";
  - Models: "Install" on a card;
  - the confirm button of each dialog.
- **Hit areas** stay at least 32 px.
- **Fit:** text never truncates at 100–150% zoom, in either window size.

## 4. Part H: History

1. **The card is the thumbnail.**
   - Use a justified row layout: a fixed row height (about 200 px at 1280x800) and a card width of row height × video aspect. Portrait and landscape cards both show the whole frame, with no cropping and no letterbox bars.
   - The file name (one line, ellipsis) and a small state chip (Done, Failed, Cancelled) sit on a soft scrim at the bottom of the thumbnail.
   - Keep virtualisation and the current grouping by month.
2. **Clicking a card** opens a popup with:
   - a large player (the output, or the original when there is no output);
   - the details and actions from today's detail dialog: Play or Pause, Show in folder, Compare again, Copy details, Remove from history, and Delete video files.

   If a codec cannot play in the app, show "Open in your player".
3. **Select mode:**
   - Remove the always-visible checkbox.
   - A "Select" button in the History toolbar turns on select mode. In it, each card shows a round selection mark at top-left (24 px mark, 32 px hit area), and clicking a card toggles it.
   - The toolbar then shows "N selected", Select all, Remove from history, Delete video files… and Cancel.
4. **Remove can also delete files.** The single, selected and "Clear history" remove dialogs have two options, both off by default: "Also move the finished videos to the Recycle Bin" and "Also move the original videos to the Recycle Bin".
   - Delete the files first through the existing guarded deletion, then remove the records.
   - If any requested file is kept, keep that record and show the reason. The other records are removed.
   - The result summary counts moved, not found and kept files.
5. **Undo:**
   - "Clear history" uses the same soft hide and Undo as Remove (`engine.py:1177-1204`).
   - The toast stays 10 s and pauses while the pointer or focus is on it.
   - **Time left:** the owner asked for the remaining time to show as a light tint that recedes from right to left.
     - When the toast appears, a lighter tint of the toast surface fills its whole background.
     - Its right edge moves smoothly to the left. The tinted width is the time left divided by 10 s. Pause it together with the timer.
     - Text contrast stays at least 4.5:1 on both the tinted and untinted parts, in dark and light themes.
     - With `prefers-reduced-motion`, update the width in 1 s steps instead of smoothly.
     - The toast is announced once to screen readers, not on every step.
   - When files were also moved, the toast says "Files are in the Recycle Bin". Undo brings back only the records.
   - Change the clear dialog text: it is no longer "cannot be undone".

## 5. Part M: Models

1. **Compact cards** show only:
   - the name;
   - the one-line `summary`;
   - an "Installed" check when installed;
   - one large action button.

   Target card height: at most 120 px at 1280x800, three columns.
2. **The action button changes with the state:**
   - "Install" (primary). While downloading, the bar fills inside the card with percent, time left and Cancel.
   - "Uninstall" (secondary, danger outline) after install, with confirmation.
   - The current default model and models used by an unfinished job cannot be uninstalled. The button is disabled, and the tooltip gives the reason.
3. **Click anywhere on the card** except the button to open a popup with all details:
   - everything in today's Details;
   - Strength;
   - Make it my default;
   - Verify again;
   - licence and facts.

   Remove the ⋯ menu.
4. **After a successful install**, the download log is not shown, only "Installed". A failure shows a short reason on the card and the full log in the popup.

## 6. Part C: Compare

1. **Bigger pictures.** The video area is limited to `clamp(130px, 100vh - 460px, 340px)` (`style.css:1223`). Portrait sources get about 191x340 px per tile, and 2-3 models get about 302x170.
   - Give the video area all the height that is not needed for a compact control bar. Move the model choice into a row of chips or a side panel that can be hidden.
   - For the pane count and source aspect, choose the grid (columns x rows) that makes the tiles largest.
   - **Minimum tile sizes at 1280x800:**
     - portrait 9:16 with Original + 1 model: tile height ≥ 560 px (≥ 480 px at 1100x700);
     - landscape 16:9 with Original + 1 model: tile width ≥ 590 px;
     - Original + 2 or 3 models: tile area at least 2x today's.
   - Double-clicking a tile shows that tile alone. A "Full window" button (and F) hides all controls; Esc returns.
2. **Touchpad and touch.** No `wheel` listener exists today. Add native listeners with `{passive: false}`:
   - pinch on a precision touchpad (a wheel event with `ctrlKey`) zooms continuously from 1x to 8x around the pointer;
   - two-finger scroll pans while zoomed;
   - in swipe mode at 1x, a horizontal two-finger scroll moves the divider;
   - touch-screen pinch and pan work through Pointer Events;
   - Ctrl + wheel inside Compare zooms the video, never the whole app;
   - all panes keep the same zoom and position;
   - keep the zoom buttons as a visible alternative.
3. **Steady layout.**
   - The frame and time counters (`Trial.tsx:428-432`) use tabular numerals and a fixed width in `ch`, so nothing else moves during playback.
   - Check every other live number (Home percent, Work left, progress) the same way.

## 7. Part S: Schedule

The owner found it confusing that hours can be edited only when "Only work during my hours" is on (`ScheduleView.tsx:219-227`).
- Hours are always editable.
- The toggle becomes a large, clear switch at the top of the page: "Work only during these hours".
- When it is off, the hours are shown dimmed with the note "Off: VideoEnhancer works at any time. Your hours are kept." and a "Turn on" button.
- Hours that you add or change are visible at once, together with the plan bands (B4).

## 8. Part O: first-run tour

There is no onboarding today.
- Show a short tour on the first start: 4–5 steps, each one sentence, pointing at the real controls. Suggested steps:
  - add videos;
  - Standard or Fast;
  - your hours;
  - History and Compare;
  - Models and Settings.
- "Skip" closes it at any step. "Show the tour again" in Settings opens it again.
- Store the flag like `tray_explained` (`service/settings.py:23`), including its validation and the PUT exclusion.

## 9. Part E: long videos finish later than the first estimate

**Owner report:** short clips are accurate, but jobs of minutes to hours often finish hours later than first estimated.

**Likely contributors** (code review, not yet measured):
- Each segment uses `SimpleDecoder(need_scanned_stream_metadata=True)` (`decode.py:105`), which may scan the whole file. That cost would grow with file length, and a 2 h Standard 1080p job has about 1,000 segments.
- The manifest carries per-frame `cfr_map` and `source_pts`. It is rewritten and fsynced on every save, and reloaded and saved every 10 s during a segment.
- **Finalization:**
  - The model was fitted on outputs up to 28 MB and 900 frames.
  - It does not learn on the built-in profile (`model.py:475`), and is admitted with zero margin (`admission.py:15`).
  - An abort at the window end restarts it in the next window.
- **Not counted in the estimate:**
  - the analysis pass ("preparing");
  - aborted segment time (`timing.wasted_seconds`);
  - the child start-up beyond the 2.0 s constant.
- **Finish times:**
  - The live finish time of the running job is `now + remaining_frames / live_fps + finalization` (`engine.py:796`), which ignores the gaps between operating hours.
  - The correction factor restarts at 1.0 for every job.
- The first overall estimate shown at Add is not stored.

**Do:**
1. **Measure first, then fix what the numbers show.** Use synthetic portrait 720x1280 at 30 fps sources of 5, 30 and 120 minutes. The source files are cheap to generate, and they do not have to be fully processed. Measure, against file length and position (start, middle, end):
   - segment start-up: child, decoder open or scan, and model load;
   - manifest load and save time and size;
   - analysis time;
   - finalization time.
2. **Fix any cost that grows with file length**, for example decoder scans per segment or per-frame arrays in the manifest. Move large per-frame arrays to a separate file written once.
3. **Count the real costs in the estimate:**
   - analysis;
   - measured segment start-up;
   - finalization with a size- and duration-aware model and a safety margin, learned locally even when the built-in profile is used;
   - the time lost when a segment is cut at the end of the operating hours.
4. **Live finish time:** the running job's finish time uses the planner, so it includes operating-hours gaps, and Up next times follow from it.
5. **Correction across jobs:** start a new job's correction from the recent jobs of the same mode on this PC, not from 1.0.
6. **Store the first estimate:** save the estimate and finish time shown at Add (`initial_estimate_seconds`, `initial_finish_at`) in the manifest.
7. **The owner's past jobs.** On 2026-10-12 the owner allowed a read-only analysis of their finished jobs.
   - Copy the `manifest.json` files (and `job.jsonl` if useful) from their real engine home to a folder outside it, and work only on the copy.
   - Do not open, copy or change any video. Do not change any manifest, setting or queue item in the real home.
   - For each job, compare:
     - the first estimate (reconstructed from the stored `machine_profile` and `settings` when it is not stored);
     - per-segment `predicted_seconds` and `timing.observations` against `actual_seconds`;
     - `analysis_seconds`, `timing.wasted_seconds`, the scheduler waits in `timing.events`, and finalization predicted against actual.
   - Report aggregates by source length (<1 min, 1-10 min, 10-60 min, >60 min) and by mode, with anonymised job numbers.
   - No file names, paths or titles go into Git or the report.
   - Use the findings together with step 1 to choose the fixes.
8. **Acceptance on the RTX 4060 Ti:**
   - **Job:** one 10-minute portrait Standard C1 job (about 2 h of GPU), in an isolated home whose test hours make the job span at least one gap (for example 60 min on and 15 min off).
   - **Gate:**
     - the first estimate is within ±10% of the actual processing time;
     - the first finish time is within ±10% of the elapsed time from adding to done, gaps included;
     - the live finish time at 50% progress is within ±5% of the remaining elapsed time.
   - Report the before and after numbers of step 1.

## 10. Part G: acceptance

- **G1:** screenshots of every changed screen at 1280x800 and 1100x700, in dark and light:
  - Home;
  - Add;
  - History (normal, select mode, popup);
  - Models (cards, popup, downloading);
  - Compare (portrait and landscape, 1 and 3 models, full window);
  - Schedule (on and off);
  - Settings (calibration running);
  - the tour.

  Add a side-by-side with the P1d-3 screen for Home, History, Models and Compare. Store everything outside the repository and list the paths.
- **G2:** add CI e2e tests for:
  - B2a (a drop while a modal is open);
  - B3 (pause keeps the order);
  - B4 (hours visible);
  - select mode;
  - clear with Undo;
  - remove with files (fake deletion in CPU tests);
  - Models card popup and the Install/Uninstall switch;
  - Compare pinch, pan and divider via synthetic wheel events with `ctrlKey`;
  - counters with 0 px sibling movement during playback;
  - no estimate request when the delete-original switch changes.
- **G3:** the Part Q1 theme timing, and the P1d-3 renderer budgets again (10 repeats, median and p90).
- **G4: GPU and real PC:**
  - **B1:** on NTFS, finish a synthetic job, then delete its output and original through History. Both go to the Recycle Bin, and restoring both gives identical SHA-256 values. Also test the legacy fallback with a P1d-3-style job.
  - **B2:** the five 4K files.
  - **E:** the step-1 measurements, the step-7 analysis and the step-8 job.
- **G5:** all GPU-marked tests. The default pipeline output must not change; strict equality as before.
- **G6:**
  - `ruff`, `ruff format --check`, `pyright`, CPU tests and D2;
  - GUI lint, typecheck, unit tests, build, e2e and package;
  - Windows and Ubuntu CI green on the final commit.
- **The owner's check:** build the package and give its path. I will write the next owner checklist from your report.

## 11. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs are in English.
- **Never commit:**
  - media, weights, previews or generated videos;
  - `node_modules` or build output;
  - the design export or screenshots;
  - the owner's logs or private sample names.
- **User videos:** never deleted permanently. Only the deletion module may remove a user's video path, and only to the Recycle Bin, behind the guard. Never change the owner's Recycle Bin settings.
- No models that add skin texture, and no GAN real-world video models. No new catalog entries.
- Keep the service security model: localhost, token. No telemetry, no auto-update.
- New dependencies: open-source licences only (MIT, ISC, BSD or Apache-2.0), named in the report.
- Update `docs/GUI.md`, `docs/API.md` and `docs/TROUBLESHOOTING.md` for every change.

## 12. Report (`.ai/LAST_REPORT.md`, English, UTF-8, under 40 KB)

- A table per part (B, Q, V, H, M, C, S, O, E, G): done / partial / NOT RUN / BLOCKED, with evidence (tests, numbers, file:line for key changes).
- **B2:** the result for each of the five 4K files, and the estimate time for the 10-minute 4K file.
- **E:** the measurements before and after, the anonymised analysis of the owner's past jobs, and the three gate numbers.
- The package path for the owner's check.
- "Questions for the designer", each with the default you chose.
- Exact reproduction steps.

Never report a test as passed if it did not run.

## Owner follow-up

Continue P1e. Do not overuse greater-than or chevron icons. Give buttons icons appropriate to their actions. Keep the Settings gear.
The Home Add videos button must show its plus only as an icon; remove the literal plus from the label.
