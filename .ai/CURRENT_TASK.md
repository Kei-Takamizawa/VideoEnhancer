# CURRENT_TASK: Cycle P1d (UI v2 from the owner's Claude Design, and the engine work it needs)

- **Task ID:** VE-P1d
- **Date:** 2026-10-11
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** the owner merges PR #4 (`p1c-redesign`, head `fe2b509`) into `main`. Create the branch `p1d-ui-v2` from the latest `main`. If PR #4 is still unmerged when you start, branch from `fe2b509` and say so in the report. Save this file as `.ai/CURRENT_TASK.md`, commit it, open a draft PR to `main`, and write `.ai/LAST_REPORT.md` (English) at the end. Do not push to `main`.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option that keeps existing outputs unchanged (or skip only that item), and continue. Stop early only if every remaining item is blocked.
2. Order: Part D (design package) → Part A (fixes from the P1c-4 review) → Part B (engine and service features for the new UI) → Part U (UI v2) → Part C (Compare) → Part G (acceptance) → Part X (optional). Long GPU measurements run whenever the GPU is free.
3. If time runs out, finish earlier items completely and mark the rest NOT RUN. Never report a test as passed if it did not run.
4. The owner's queue, settings and videos on this PC are not test data. Use synthetic footage and a separate engine home for every test.

## 0. Status after P1c-4 (review of `fe2b509`)

Accepted as done (keep, do not redo):
- **F1 AV1:** the probe uses the production encoder at 1920×1080, `av1_unavailable_reason` is in `health`, Add and Settings share it, no silent codec switch, AV1 timestamps fixed with `setts`.
- **M2:** 9 new entries qualified. C1 and RIFE 4.25 have `reference_speed`.
- **C2 service side:** reuse by cache key, cancellation of the previous compare, `POST compare/range`, three-model GPU compare.
- **E:** trial percent history; no 0% stretch over 60 s.
- **F3:** `summary` exists for every built-in entry, 52 to 69 characters.
- **CI:** 4 of 4 checks green on `fe2b509`.

Designer answers to the three P1c-4 questions:
1. **1xDeH264_realplksr:** stays omitted. The licence string "CC-BY-0.4" is ambiguous, and omission is the safe default.
2. **2xLiveActionV1_SPAN:** follow the publisher's Apache-2.0 licence. Set `commercial_use_allowed` from that licence and show it as such.
3. **Real-ESRGAN blend:** stays omitted for now. One retry with a smaller tile is optional item X1.

## 1. Part D: the design package

The owner made the new UI in Claude Design and exported it as a standalone HTML file.

- **The file:** `VideoEnhancer_Desktop.html`, 7,153,595 bytes, SHA-256 `f19cd6ed307e71e35ef319f4025b70e6e6a72b9d2e6a87cff165cd3e15d7a642`. The owner puts it at `.tmp/design/VideoEnhancer_Desktop.html` in the repository folder; `.tmp/` is already ignored by Git. Check the SHA-256 and do not commit the file.
- **Its format:**
  - The page holds four `<script type="__bundler/...">` blocks: `manifest`, `ext_resources`, `page_order` and `template`.
  - `manifest` is JSON that maps a UUID to `{mime, compressed, data}`. `data` is base64, gzip-compressed when `compressed` is true.
  - The 61 top-level entries are nested HTML bundles, one per artboard, and each has the same four blocks. The `template` of the top level lists the artboards with their titles and sizes.
  - Inside the nested bundles are 7 component sources and the runtime (`dc-runtime.js`, React 18.3.1). The nested template imports a component through `<dc-import>`, with `theme` (dark/light), `size` (1280x800/1100x700) and `variant` (the state) attributes.
- **Extract and commit** the 7 components to `design/p1d/components/`. The files must be byte-identical to these:

  | File | Bytes | SHA-256 |
  | --- | --- | --- |
  | `Main.dc.html` (Home) | 75,986 | `5792f656be5f734aa2088a6aa3c40b8fbcbc7b637f4ec0778a59ba56ab25bd8d` |
  | `AddVideos.dc.html` | 27,641 | `a3949a26dabd18fbcb9390b6261003c97c94d5804b33d7ed763b1669e84f3412` |
  | `History.dc.html` | 45,053 | `7a4ea00afa8cd26660e394779e638177993ac78ae6cfa7cc0273db5419c92d43` |
  | `Schedule.dc.html` | 43,378 | `7a4197762622501b7d5216761b5935dbee34794f548c5ebf5d74436d534e411e` |
  | `Models.dc.html` | 37,088 | `82a06dcf542e7ac18005fdfbfe595cf68e09c943e95e58af64a13ee23c00408d` |
  | `Compare.dc.html` | 47,339 | `1acbd48ad2c91cdac5ccb31e57a29044c94614cecde89a3c1754063b565d5e1c` |
  | `Settings.dc.html` | 25,801 | `23cde72b6ed1b9f7bc3cebf808cd24a755bb613f0cb0ccc93dfba5446c586ef1` |

- Add `design/p1d/README.md` (English). It lists the 61 boards (component, variant, theme, size) and says that the components are the visual source of truth for P1d. Do not commit the runtime or the extraction script.
- **How to use the design:**
  - Layout, spacing, tokens, copy, states and keyboard behaviour come from the components. Re-implement them in the existing React + TypeScript renderer. Do not ship the dc runtime.
  - Where the design shows sample data, use real data: file names, times, model names and descriptions, counts, "Driver [version]", "[model publisher's page]".
  - Where the design's copy describes behaviour, the app must really behave that way, or the copy must change to match the engine. For example, "It will try again with smaller parts" must not appear unless the engine retries with smaller parts.

The boards by component:
- **Main (Home), 21 boards and 4 derived states:**
  - working, waiting, finishing, empty, drop, zoom, preview, tray, long, menu
  - confirmCancel, confirmRemove, log, actionError, problem
  - connecting, reconnecting, unreachable, sac
  - derived: paused, preparing, overrun, previewPause
- **AddVideos, 8:** default, options, optionsNoAv1, one, warnings, busy, partial.
- **History, 11:** default, failed, notFound, select, deleteFiles, clear, toast, empty, noMatch.
- **Schedule, 7:** default, addDay, runUntil, override, off.
- **Models, 6:** default, details, licence, remove.
- **Compare, 5:** default, failed, swipe, fast.
- **Settings, 3:** default, advanced.

## 2. Part A: fixes from the P1c-4 review

- **A1. Model-aware estimates.**
  - The estimator ignores the chosen model today. With SCUNet the measured speed is 0.587 fps against C1's 2.473 fps, so the Add dialog would promise a time 4.2× too short. SPAN adds 1.77×.
  - Scale each stage's cost by the ratio of the model's `reference_speed` to the category default's `reference_speed`. Both were measured on the same reference clip. A calibrated profile for that exact model wins when it exists.
  - The Add cards, the Up next times, the Schedule plan and Compare's "About X for this video" all use this one estimator.
  - Evidence on the GPU: one short Standard job with SCUNet and one with SPAN. Estimated and actual processing time must agree within ±15%.
- **A2. Cancel must not destroy reusable previews.**
  - Today a cancelled compare deletes every `*.mp4`, including finished model previews that the reuse cache could serve. This races with `prime_cached`.
  - Delete only incomplete files. Keep finished previews in the cache under its existing limits (5 sessions, 2 GB).
  - Add a test: start a compare, cancel it after one model is ready, start a new compare with the same key, and that model is served from the cache without GPU work.
- **A3. "Busiest part" ignores scene cuts.** Exclude cut frames, and 2 frames on each side, from the motion sum in `compare/range`. Add a test with a hard cut inside a calm clip: the chosen window must not be the cut.
- **A4. AV1 coverage.** Run on the GPU and report `ffprobe` `codec_name`, size, frame count and duration for each case:
  - a Keep-size job with a 720×1280 output;
  - a job with at least 3 segments, to cover concatenation;
  - the smallest output size the production AV1 encoder accepts, found by probing. For outputs below it, the Add dialog shows a blocking warning before queueing ("Output too small for AV1. Choose HEVC or a larger size."), and the service refuses with the same text.
- **A5. Docs and dead code.**
  - Fix `docs/ADDING_MODELS.md` lines 6 and 7, which contradict its later section.
  - Remove the `realesr-general-x4v3` GUI selectors that have no catalog entry.
  - Make `docs/THIRD_PARTY_MODELS.md` line 58 true: either add a test for the blend path or remove the claim.
  - Add the missing service tests for `restore_strength` and `size_strength` validation and for `percent_history`.

## 3. Part B: engine and service features for the new UI

- **B1. Pause all versus pausing one video.**
  - "Pause all" becomes a global flag and no longer rewrites every job's state.
  - "Resume all" clears the flag. Videos the user paused one by one stay paused ("Waits until you resume it").
  - Pausing the running video lets the next queued video start, within the operating hours. This matches the design's tooltip "Pause this video. The next one starts instead."
  - `health` exposes `paused_all`.
  - Tests: pause one, pause all, resume all, and that video is still paused.
- **B2. Cancel and remove.**
  - A video with no completed segment: the menu's Cancel opens "Remove … from the queue?". Confirming removes the job completely, with no History entry.
  - A started video: Cancel marks it cancelled and deletes its intermediate work files at once, because a cancelled job cannot be resumed. The record stays in History as "Cancelled". The confirm text says the work so far is lost and the original stays as it is (design board `confirmCancel`).
  - The original file is never touched by Cancel or Remove.
- **B3. Delete video files to the Recycle Bin.**
  - Add a service endpoint that takes job ids plus `{output: bool, original: bool}` and moves only those jobs' recorded output and original paths to the Windows Recycle Bin. It accepts no free paths.
  - Use the Windows shell with undo (for example `IFileOperation` with recycle-on-delete). A file that would be deleted permanently must be **kept**. This covers a network drive, the bin turned off, or a file too large for the bin. The result then says, per file, "Kept: <reason>".
  - Verify afterwards that the file left its folder and that no permanent delete happened.
  - The History record stays. It shows "File not found" or "Moved to the Recycle Bin" as appropriate. "Compare again" is disabled with a reason when the original is gone.
  - Tests: mock the shell API for success, refusal and permanent-delete-only. On the real PC, one manual check with a synthetic file that ends up in the Recycle Bin.
- **B4. History removal.**
  - "Remove from history" (one or many) hides the records at once and allows Undo for 10 s, then removes them, together with their work folders, as `remove` does today.
  - "Clear history…" removes every done, failed and cancelled record after its confirm dialog, with no Undo.
  - Neither ever touches video files.
- **B5. Delete the original after a verified output.**
  - Each job has a setting `delete_original_after`. Its default comes from Settings `delete_original_after_processing`, which is false by default. The Add dialog switch sets it per job.
  - After finalization succeeds, check all of these:
    - the output decodes to the end;
    - its frame count equals the expected output frame count;
    - its duration is within one output frame of the expected one;
    - it has an audio stream when the source had one.
  - Only then send the original to the Recycle Bin through B3.
  - If any check fails or the bin cannot take the file, keep the original. History then shows "Original kept: <reason>".
  - If another unfinished job uses the same original, wait until the last of them has finished.
  - Never do this for trials, compares or previews.
  - Tests cover every check, including a forced failure that keeps the original.
- **B6. Schedule and plan performance.** Today one pointer move costs three 120-day plan builds, and the event stream rebuilds a 120-day plan every second for each client.
  - `schedule/preview` builds only the expected plan, unless the caller asks for the best and worst range. The new design does not show that range.
  - The GUI sends at most one preview 400 ms after the last edit and cancels stale requests.
  - The event stream caches the queue snapshot and the plan. It rebuilds them when jobs, schedule or settings change, and at most once every 5 s when only progress changed.
  - Budgets on the RTX 4060 Ti PC, with a Standard job running and 10 queued jobs:
    - no keystroke in a time field is delayed by more than 50 ms;
    - the preview result is shown at most 500 ms after the last keystroke;
    - with one idle client, the service's event-stream work uses at most 5% of one CPU core.
  - Report the measurements and how you took them.
- **B7. First look in trials and compares.**
  - After a compare gets the GPU, each model tile first gets a "First look": a still image of one frame near the start of the range, taken from a short run of 15 frames. Original gets the same frame.
  - The full preview continues afterwards. The finished preview keeps the existing frame-identity rules (the D2 suite). The first look is only a preview of it and is labelled "First look".
  - Target: at most 25 s from GPU admission to the C1 first look on the RTX 4060 Ti. Report the time to first look and to the full preview for C1, SCUNet and RIFE 4.25.
- **B8. Data the new screens need.** Expose these in the existing API:
  - the waiting count for the dock badge (queued, paused and preparing videos);
  - per History record: mode, time taken, output size, original size, output folder, failure reason, and the state of the output and original files (present, missing, in Recycle Bin);
  - the driver version for Settings › About;
  - the publisher page URL for each catalog entry, for the licence dialog.

## 4. Part U: UI v2

- **U1. Window shell.**
  - Frameless window with `titleBarStyle: "hidden"` and `titleBarOverlay`. The native Windows caption buttons and Snap Layouts stay.
  - A 32 px title bar with the app icon and name, as in the design. The overlay colours follow the theme.
  - Closing hides the window to the tray, as today. The first time, the tray dialog explains this (board `tray`); that it was shown is remembered.
  - The minimum window stays 1100×700.
- **U2. Dock.**
  - Five items as designed: Home, History, Schedule, Models, a divider, then Settings with a gear.
  - Tooltips appear on hover and on keyboard focus.
  - Badges: Home shows the waiting count; History shows a dot for unseen failures.
  - Ctrl+1 to Ctrl+5 switch screens.
  - Compare is not in the dock. It opens full-window with Back and without the dock.
- **U3. Tokens and type.**
  - Use exactly the CSS custom properties of the design for `dark` and `light`: `--bg`, `--surface`, `--raised`, `--border`, `--text`, `--text2`, `--muted`, `--accent`, `--on-accent`, `--success`, `--warning`, `--danger`, `--on-danger`, the `-soft` variants, `--band`, `--hover`, `--scrim`, `--shadow`.
  - Font "Segoe UI Variable Text", base 13 px. The other sizes, radii and control heights come from the components.
  - Remove the old teal tokens and the undefined `--text-3` and `--surface-2`.
  - No `backdrop-filter`, no blur and no CSS animations. Transitions stay at 120 to 150 ms, as designed.
- **U4. Zoom.**
  - Zoom is 80, 90, 100, 110, 125 or 150%, applied with `webContents.setZoomFactor`.
  - Change it with Ctrl+Plus (also Ctrl+= and the numpad keys), Ctrl+Minus and Ctrl+0, or in Settings.
  - Replace Electron's default menu zoom so a key press never zooms twice.
  - Show the toast "90%" with "Ctrl+0 resets to 100%".
  - The setting is saved and applied before the first paint.
  - At 100%, no screen scrolls at 1100×700. Above 100%, inner areas may scroll (the Settings hint says so).
- **U5. Theme.** "System" follows `nativeTheme` live, including the title bar overlay. Light and Dark force the theme.
- **U6. Screens.** Implement every board and state listed in Part D with real data. The following are the points the design leaves open, and the defects my review found. The review measured the export in headless Chromium with Arial-metric fonts; Segoe UI widths were not measurable there.
  - **Home:**
    - All states. The "Your hours this week" card shows 5 days starting today.
    - The menu closes on an outside click and on Escape.
    - The log dialog shows the job log and the log file's real path.
    - Preview result is side by side or result only, as designed.
    - The problem banner time is formatted ("Problem · Sun 10/11, 23:02"), not a raw ISO string.
    - Singular and plural are correct ("Drop to add 1 video").
  - **Add videos:**
    - The Standard and Fast estimates cover all files together.
    - The fix buttons in `warnings` work: "Choose a folder…" opens the folder picker; "Remove it" removes that file; "Use Keep" sets Size to Keep; "Read instructions" opens `docs/TROUBLESHOOTING.md`.
    - "Bigger picture" is enabled when a verified size model is installed (SPAN). Otherwise it is disabled with the note "More choices come later."
    - Closed selects must not clip their text. Today "BasicVSR++ decompression (de…" is clipped.
  - **History:**
    - The grid is virtualized and stays smooth with 1,000 records. Counts and groups are real (Today, Yesterday, Last 7 days, Earlier in <Month>).
    - Portrait and landscape thumbnails are centre-cropped into the designed tile.
    - "Show in folder" selects the file.
    - **Defect:** the detail panel's action row "Play | Show in folder | Compare again" overflows by 38 to 75 px, and "Compare again" is cut off. No action label may be clipped at 1100×700 or 1280×800, at zoom 100% or 110%.
  - **Schedule:**
    - Numeric rows, quick fills that also turn the switch on, and "All day", which is stored as 00:00–00:00.
    - "next day", the overlap note, and Up and Down by 15 minutes.
    - Special days with several time ranges.
    - "Run now until a time…" shows the new finish before it starts. The override state has Stop.
    - The timeline is read-only and shows "was …" after a change. Autosave with "Saved · Undo".
    - Remove the "Custom…" dialog and all drag code.
    - **Defect:** the bar tooltips (about 365 px wide) run up to 62 px past the window edge. Tooltips must stay inside the window: flip or clamp them.
  - **Models:**
    - Only real catalog entries. The design's examples ("Strong Restore", "Detail Restore", "Low-light Cleanup" and the rest) are not products, and models that add texture stay excluded.
    - Card title = the catalog `title` in plain words (for example "Gentle cleanup"). `display_name` (for example "BasicVSR++ NTIRE21 Track 3") goes under it in the details. The card shows `summary`.
    - The DRUNet strength selector, and per-card download progress with Cancel. Remove the duplicate operation list.
    - Details: licence and `licence_plain`, source host, short SHA-256 with copy, speed on this PC, peak memory "of N GB" from the detected VRAM, invents detail, flicker.
    - The licence dialog's checkbox gates Download, and it links to the real publisher page.
    - The remove-blocked dialog gives the real reasons.
  - **Compare:** Part C.
  - **Settings:**
    - Autosave with "Saved". Zoom and System theme really work.
    - "Start with Windows" keeps its current default, off. The design shows it on only as an example.
    - About shows the real driver version.
  - **Global states:** connecting, reconnecting (buttons disabled, "Last update HH:MM"), unreachable (Retry, Copy details), the Smart App Control panel, the action error, and the toasts.
- **U7. Accessibility.**
  - Everything works by keyboard, with a visible focus ring.
  - Dialogs trap focus and close on Escape. The safe button is focused first.
  - Status is never shown by colour alone.
  - Every control has a hit area of at least 24×24 px, even where the visual is smaller (checkboxes 13 to 18 px, seek bars 6 px, the small links in the design).
- **U8. Renderer performance budgets.** Measure with Performance marks in the packaged app on the RTX 4060 Ti PC while a Standard job runs:
  - switching screens takes at most 100 ms, from click to the next painted frame;
  - input latency is at most 50 ms;
  - with the window visible, idle, and progress updating, the renderer uses at most 2% of one CPU core;
  - opening History with 1,000 records takes at most 300 ms.
  - Progress text updates at most once per second.
- **U9. Clean-up.** Remove the dead `QueuePage` and `PlanPage` and the unused CSS. Update the tests.

## 5. Part C: Compare (the GUI parts deferred from P1c-4)

- **Range box.** Click places the 5 s box. Left and Right move it 1 s, Shift 5 s. The position slider moves through the whole video. It starts on the busiest part (A3). Length is 3, 5 or 10 s.
- **Choosing models.**
  - Pick a category, then up to 3 models. Original is always shown.
  - Models that are not installed appear as "+ Name". Installing one selects it after verification. If 3 are already picked, it replaces the last one.
- **Automatic re-render.**
  - Changing the moment or the models starts a render 800 ms after the last change. It cancels the running one (keeping finished previews, A2) and serves cached models at once.
  - "Try again" stays for failures.
- **Tile states:** Waiting ("Starts after the current step, about N min"), First look (B7), Making preview N%, Ready, and Problem with Try again.
- **Viewer:** side by side, or swipe with Left and Right pickers; zoom 100 to 400% with shared pan; play and pause with Space, frame step with Left and Right, seek, Loop, "Frame n/N". Keep the four-stream sync test passing.
- **Per model:** "About X for this video" (A1), Use this / Chosen, Make it my default.
- **Fast videos:** the "Fast does not clean up." panel, with "Switch to Standard" (enabled before the video starts) and "Compare smoother motion instead".
- **At 1100×700:** no button wraps. Long model titles may end in an ellipsis, with the full name in a tooltip.

## 6. Part G: acceptance

- **G1. Screens:**
  - Build the packaged app with synthetic data that reproduces each board in Part D.
  - Take screenshots at 1280×800 and 1100×700: dark and light for the 7 main screens, dark for the other states. For the 7 main screens at 1280×800 dark, put the design board and the app side by side in one image.
  - Store the screenshots outside the repository and list their paths in the report.
- **G2. No clipping and no page scroll.** An Electron e2e test opens each main screen at 1100×700 and 1280×800 at zoom 100%. It asserts:
  - the page does not scroll;
  - no button or label is clipped (`scrollWidth > clientWidth` without an ellipsis style);
  - nothing is hidden behind the dock;
  - no tooltip runs outside the window.
  The test runs in CI.
- **G3. Performance:** the B6 and U8 budgets, each with measured numbers.
- **G4. GPU evidence:**
  - A1 estimate accuracy (2 jobs);
  - A4 AV1 cases;
  - B7 first-look times;
  - B5 with a real synthetic file: one success, where the original lands in the Recycle Bin, and one forced failure, where the original is kept;
  - B3 on the real PC.
- **G5. Unchanged default output:** the strict C1/RIFE tensor-equality tests and the D2 suite pass. The default pipeline output does not change.
- **G6. Checks:**
  - `ruff`, `ruff format --check`, `pyright`, CPU tests and the D2 suite;
  - GUI lint, typecheck, unit tests, build and e2e;
  - Windows and Ubuntu CI green on the final commit.
- **The owner's visual check:** not your job. I will write `P1d_owner_check.md` after your report.

## 7. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs are in English.
- **Never commit:**
  - media, weights, previews or generated videos;
  - `node_modules` or build output;
  - the 7 MB design export or the screenshots;
  - the owner's logs or private sample names.
  The 7 component files in `design/p1d/components/` are allowed.
- **User files:** never delete a user's video permanently. Videos may only go to the Recycle Bin, through B3, with verification.
- No models that add skin texture, and no GAN real-world video models. Do not add catalog entries beyond the P1c-4 M2 table.
- Keep the service security model. No telemetry, no auto-update.
- Update `docs/GUI.md`, `docs/API.md` and `docs/TROUBLESHOOTING.md`, and fix the stale "P1c partial reliability update" section in `docs/GUI.md`.

## 8. Part X: optional, only after everything above

- **X1.** Re-qualify the Real-ESRGAN blend ("Sharper detail") with tile 128 and halo 16. If the sampled process peak is at most 5.0 GB, finish steps 5 and 6. Otherwise it stays omitted, with the numbers.
- **X2.** Keep the last compare model loaded for 120 s while the queue is idle, so re-renders start faster. Report the gain. Turn it off if it ever delays a queued job.

## 9. Report (`.ai/LAST_REPORT.md`, English)

- A table per part (D, A, B, U, C, G, X): done / partial / NOT RUN, with evidence (tests, numbers, file:line for key changes).
- The design-versus-app screenshot list (G1), the clipping-test result (G2) and every performance number (G3).
- The GPU evidence (G4), with exact commands and `ffprobe` output for AV1.
- "Questions for the designer", each with the default you chose.
- Exact reproduction steps.

Never report a test as passed if it did not run.
