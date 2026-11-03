# CURRENT_TASK: VE-R1d (minimal transparent player, thumbnail-only library, no header, seamless return)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1d
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file, on top of `main` ca6e0f6 (PR #19 merged). A new draft PR follows.
- Write a new `.ai/LAST_REPORT.md` for VE-R1d; keep the older reports below it.
- Same workspace and isolation rules as VE-R1c-3. The owner's real remote service runs from this checkout. Do not start, stop, install or restart it. No dependency changes.
- Record a disk baseline at the start and report growth at the end. If a scratch delete is refused, list paths and sizes for the operator (that alone does not make the cycle PARTIAL). The known local `p1f3-visual` "fresh calibration" failure (pre-existing, VE-R1b-3) does not make the cycle PARTIAL if everything else passes.
- Face-based poster selection is a separate later cycle (VE-R1d-2). Do not start it here.

## 1. Owner requests (2026-11-03 12:24Z, after trying the R1c-3 player)

"Good, but make the UI transparent and less visible. Show only the time, the seek bar and the preview. Make the seek bar white. Keep the other controls available from the keyboard. No frame around the preview. The Library disappears for a moment every time I go back to it; make it seamless. The Library shows only thumbnails, no file name, duration or other text. Remove 'VideoEnhancer DESKTOP-2H8794C' at the top and do not waste the space."

## 2. Work

### 2.1 Minimal player overlay

1. Over the video, show **only**: the current time (left), the seek bar, the remaining time `-m:ss` (right), and the seek preview while hovering or dragging. Remove the floating bar background, the blur, the top title bar, and the on-screen play/pause, skip, volume and full-screen buttons.
2. **Transparent:** no panel background. The seek bar track is semi-transparent white (about 35 % opacity), the played part and the thumb are solid white; the time text is white. Use a soft dark text/box shadow or a very light bottom gradient (at most about 25 % black, only behind the bar) so white stays readable on bright video. Keep the bar thin (about 4 px, 6 px while hovered or dragged) and the touch target at least 32 px high.
3. **Preview:** the storyboard tile with no border, no frame and no background box; the time text under it in white with a shadow. Keep it inside the player edges.
4. **Auto-hide:** as in R1c-3 (2.5 s idle while playing, cursor hidden too; shown on pointer move, key press, pause, or while dragging).
5. **Kept behaviour:** single click on the video plays or pauses; double click toggles full screen; the centre play/pause feedback icon stays but small and translucent. Every keyboard shortcut from R1c-3 stays (Space/K, Left/Right 5 s, Shift+Left/Right 30 s, Up/Down volume on Mac, M, F, Esc).
6. **iPad (touch):** tap on the video shows or hides the time and seek bar. Double tap toggles full screen (`webkitEnterFullscreen`). Play/pause on the iPad: a tap while the overlay is already visible plays or pauses; a tap while hidden only reveals it. Say in the report how a touch user plays, pauses and goes full screen.
7. **Page actions outside the video** (Back to the Library, Download, Delete) stay as they are now, outside the video area, in the existing low-key style. On a Mac, also allow Esc (when not full screen) and Backspace to go back to the Library. If any of these actions currently sit inside the video overlay, move them out under the video.

### 2.2 Library: thumbnails only

1. The grid shows only the posters. No title, duration, size or other text on or under the cards. Keep an accessible name on each card (`aria-label` with the title and duration) and a tooltip (`title`) with the title on Mac.
2. Tighten the grid: small gaps (about 4 px), posters fill the width, 16:9 boxes, black letterbox as now.
3. Move the storage bar to the top of the Settings tab. Keep the "N videos in progress" line above the grid only while a job is running, as one small line.

### 2.3 Remove the header

Remove the top header (`VideoEnhancer` and the PC name) from every screen and give the space to the content. The PC name stays visible in Settings. Respect the iPad safe-area insets (`env(safe-area-inset-*)`) so nothing sits under the status bar.

### 2.4 Seamless return to the Library

1. Going back from the player to the Library must not blank the screen. Keep the last Library view (the DOM, or at least the rendered list and the loaded poster images) in memory and show it at once; refresh in the background and update only the changed cards (keyed by item id), without re-creating unchanged `<img>` elements.
2. Restore the scroll position of the Library on return.
3. The first load may show the existing placeholder; later returns must not show an empty frame. Posters use the existing `Cache-Control`/ETag; do not add cache-busting query strings.
4. Apply the same no-blank rule when switching tabs (Library, Add, Settings) where it is cheap to do so.

## 3. Tests

- JavaScript: overlay contains only time, seek bar and preview (no buttons in the overlay); remaining-time text; touch tap logic (reveal vs play/pause) and double tap; keyboard shortcuts unchanged including Esc/Backspace back; Library diff update keeps existing `<img>` nodes for unchanged items; scroll restore.
- Browser (WebKit and Chromium; Mac-like 1440x900 mouse; iPad-like 1180x820 touch): no header; library cards have no visible text; open a video and go back: sample the Library DOM every animation frame during the return and assert the grid is never empty and no poster `<img>` is re-created; the overlay hides after idle; hover shows a frameless preview. Save screenshots (player with overlay, Library) at both viewports in `work\evidence\VE-R1d\` (not committed) and describe them.
- `ruff check`, `ruff format --check`, `uv run pyright`, the CI CPU pytest command, the node tests and the desktop E2E suite.

## 4. Allowed files

`src/videoenhancer/remote/**`, `tests/**`, `docs/REMOTE.md`, `.ai/LAST_REPORT.md`.

## 5. Done when

Sections 2 and 3 pass, the diff contains only allowed files, and the report lists test counts, disk baseline and growth, and short owner re-check steps (Mac and iPad).

## 6. Operator after the commit (after designer review)

`ve remote restart` (owner standing OK; allow rule added 2026-11-03), then `ve remote status`.
