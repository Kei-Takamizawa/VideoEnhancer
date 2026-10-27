# CURRENT_TASK: VE-P1e-3c2-OC (automated owner check of the new player)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3c2-OC
- **Date:** 2026-10-27
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Why

P1e-3c2 is merged (`main` 5d70618). The owner asked for the owner checklist to be run automatically instead of by hand. Codex's Computer Use is rejected inside `codex exec` ("Computer Use was not approved to use <app>", re-tested 2026-10-27 with CLI 0.164), so use the same method as P1e-3c2 runs 2 and 3: drive and capture **only windows of processes you started yourself**.

This is a **check cycle**. Do not change product code. If something fails, record it with evidence and continue with the next item; the designer turns failures into the next task.

## 2. Start

- **Branch:** `claude/project-thread-6lra47`. Its tree equals `main` apart from this file.
- Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.

### Set up by the operator before you start (do not redo or change)

- The owner's normal VideoEnhancer has been quit by the operator. Do not start it, stop it or touch `work\package\VideoEnhancer\`.
- **App under test:** the production candidate `work\package\VideoEnhancer-candidate\VideoEnhancer.exe`. Launch it only with `VE_HOME=D:\my-workspace\VideoEnhancer\work\scratch\owner-check\home`.
- **Clips:** `work\scratch\owner-check\clips\landscape.mp4` (1280x720) and `portrait.mp4` (720x1280), 30 fps, 20 s each, with the frame number and time drawn on every frame and a quiet 440 Hz tone. Copy them; do not modify the originals.
- Never use `D:\my-workspace\VideoEnhancer\VE-check`, `D:\my-workspace\VideoEnhancer\AppData`, or owner media.

## 3. How to drive and observe

- **Input:** synthetic input only to windows that belong to process trees you started: `PostMessage`/`SendMessage` to those HWNDs, or `SendInput` only while one of your windows is the verified foreground window. Never send input when another app is in front. If you cannot make your window the foreground window, record the item as NOT_RUN with the reason.
- **Capture:** Windows.Graphics.Capture of your own windows, as in P1e-3c2 runs 2 and 3. No full-desktop capture.
- **State:** you may read the app's own state through its normal files under `VE_HOME`, process lists and window properties. The production build has no test hooks or CDP; do not add them, and do not use the test-feature build for the items in section 4 (you may use it only to explain a failure afterwards, and must say so).
- To get the clips into History, use the app's own UI (drop or file picker by window messages), or, if the UI cannot be driven, the engine API the app itself uses, started with the same `VE_HOME`. Say which. Use Fast.

## 4. The checklist (the owner checklist, restated here)

Judge each item as **PASS / FAIL / HUMAN / NOT_RUN**. HUMAN means it needs a person's judgment (feel, smoothness) and you could only collect supporting evidence. Every PASS or FAIL needs evidence: capture file names, measured numbers or log lines.

| # | Item | What counts as PASS |
|---|---|---|
| 1 | Hover a landscape History item, then click it | Poster within 200 ms of the click, playback starts (time advances in two captures) |
| 2 | Close, then click without hovering | Poster within 600 ms |
| 3 | Title and round close button | Filename shown at the top, round close button top right |
| 4 | Controller layout | Seek bar on its own row, icon rows below, large round accent play/pause button. Compare against the mockup captures from run 3 (`work\evidence\VE-P1e-3c2\run3\mockup-*.png`) |
| 5 | Same for the portrait clip | Same layout, nothing clipped or overlapping |
| 6 | Transparency and letterbox | Video visible under the controller and title, black bars outside the picture |
| 7 | 10 s back / forward buttons | Moves 10 s (±1 frame), clamps at start and end (read the drawn time in captures) |
| 8 | Frame step while paused | Each step changes the drawn frame number by exactly 1, forward and back, 10 times each |
| 9 | Hover preview at the left edge, middle and right edge | Preview above the bar with the time below, landscape 160x90 / portrait 90x160 CSS px, inside the window |
| 10 | Volume, speed, Details | Each control changes its state (speed visible in time advance; volume in the control state; Details opens) |
| 11 | Autohide | Controls and cursor hide after 2 s still while playing; stay while paused |
| 12 | Shortcuts, fullscreen, Esc | Space toggles play, arrows seek, fullscreen enters and Esc leaves |
| 13 | Before/After on | Original / Enhanced labels on top, original on the left, enhanced on the right |
| 14 | Move the divider while playing | Divider position follows each move in captures; HUMAN for feel. Report the median and worst input-to-capture time as supporting evidence only |
| 15 | 60 s of Before/After playback | Left and right drawn frame numbers differ by at most 2 in at least 20 sampled captures |
| 16 | Zoom then Reset | Zoom percent shown; Reset returns to 100 % |
| 17 | Close the player | History is shown again and accepts input |
| 18 | Open another video, then close | Opens and closes normally |
| 19 | After closing | No `VideoEnhancer-Player.exe` left (a hover prewarm helper may live up to 30 s; check at 35 s) |
| 20 | Settings licences (optional) | Licence and source-offer text for libmpv readable |
| 21 | Fallback without DLLs (optional) | Copy the candidate folder to `work\scratch\owner-check\candidate-nodll\` and delete only the three DLLs in the copy; the History click plays with the HTML5 player without an error |

## 5. Do not change

- Product code, tests, CI, `design/`, the candidate package and the owner's package.
- You may add one script, `gui/scripts/owner-check-auto.py`, for this check. Keep it free of owner paths. It is the only repository file you may add besides `.ai/LAST_REPORT.md`.

## 6. Constraints

- One run of the app at a time. Close everything you started at the end; report the PIDs and that none remain.
- Evidence goes under `work\evidence\VE-P1e-3c2-OC\`, at most 300 MB. Never commit captures.
- Delete `work\scratch\owner-check\home\` contents and the `candidate-nodll` copy at the end, after recording their sizes. Keep the clips.
- Persistent growth ≤ 1 GB. Report free space on C and D.

## 7. Report (`.ai/LAST_REPORT.md`)

- The table from section 4 with the verdict and evidence for each item.
- A short Japanese summary at the end for the owner (3-6 lines): which items passed, which failed, and which need the owner's own eyes (HUMAN).
- How the clips got into History.
- Changed files (only the script and the report).
- COMPLETED when every item in section 4 has a verdict other than NOT_RUN (HUMAN counts as a verdict). Otherwise PARTIAL.
