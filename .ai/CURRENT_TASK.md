# CURRENT_TASK: VE-R1c-3 (owner-check fixes: player keyboard focus, IINA-like player, Brave push hint)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1c-3
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #19), on top of VE-R1c-2 at a6e178b.
- Write a new `.ai/LAST_REPORT.md` for VE-R1c-3; keep the older reports below it.
- Same workspace and isolation rules as VE-R1c-2. The owner's real remote service runs from this checkout. Do not start, stop, install or restart it, and do not touch its home, library, task or firewall rules. No dependency changes.
- Record a disk baseline at the start and report growth at the end. Delete the scratch folders this cycle creates; if a delete is refused, list the paths and sizes for the operator (the operator deletes them; that alone does not make the cycle PARTIAL).
- The known local failure `gui/tests/e2e/p1f3-visual.spec.ts` "fresh calibration" (pre-existing on `main`, see VE-R1b-3) does not make the cycle PARTIAL if everything else passes.

## 1. Owner check results of R1c and R1c-2 (record in the report)

The owner checked on 2026-11-03 (iPad, and a Mac on **macOS 27.2**). Everything passed except:

- **Step 8 (Mac keyboard):** right after opening a video from the Library, Space and the arrow keys do nothing. They start working only after the owner clicks some button (a blue focus ring appears on it).
- **Step 11 (Mac notifications):** in **Brave Nightly**, Turn on notifications fails with "Registration failed - push service error". Brave turns off Google's push service by default (setting "Use Google services for push messaging" in `brave://settings/privacy`). This is a browser setting, not a server bug.
- The operator deleted the two R1c-2 scratch caches (`work\scratch\r1c2-pytest-cache-elevated`, 83,034 bytes; `work\scratch\r1c2-pytest-cache-final`, 83,367 bytes). Record this as resolved closeout for VE-R1c-2.

## 2. Work

### 2.1 Keyboard works as soon as the player opens (step 8)

1. When the player page opens (from the Library, from a notification link, or by Back/Forward), keyboard shortcuts work at once, with no click.
2. Listen for keys at the document level while the player is shown (remove the listener when the player closes), not only on the focused container. Ignore keys when focus is in a text field, a textarea, a select or a contenteditable element, and when a modifier (Cmd, Ctrl, Alt) is held, so browser shortcuts still work.
3. Do not show a focus ring because of a programmatic focus or a mouse click. Keep a visible ring for keyboard focus (`:focus-visible`), for accessibility.
4. Shortcuts (Mac and any device with a keyboard): Space and K play or pause; Left and Right seek 5 s; Shift+Left and Shift+Right seek 30 s; Up and Down change the volume by 10 % (where the page controls volume); M mutes; F toggles full screen; Esc leaves full screen. Call `preventDefault` for handled keys, so Space does not scroll the page.

### 2.2 IINA-like player (owner request)

The owner wants the player to look and behave as close as practical to IINA on the Mac. Build an original implementation in that style. Do not copy IINA's code, icons or other assets (IINA is GPL); use simple inline SVG icons of your own.

1. **Layout:** the video fills the player area on a black background. A floating, rounded control bar sits centred near the bottom, over the video, on a dark translucent background with a blur (`backdrop-filter`, with a solid fallback). In the bar: skip back 10 s, play/pause, skip forward 10 s; the current time to the left of the seek bar and the remaining time (`-m:ss`) to the right; volume (Mac only) and full screen to the right. The video title appears in a translucent bar at the top. Keep the seek preview from R1c, now placed above the floating bar.
2. **Auto-hide:** the top bar and the control bar fade out after 2.5 s without pointer movement while playing, and the mouse cursor hides with them. Moving the pointer, a key press, or a pause shows them again. They never hide while paused, while the pointer is over a bar, or while dragging the seek bar.
3. **Click on the video (mouse):** a single click anywhere on the video plays or pauses. A double click toggles full screen; the double click must not leave the play state changed (delay the single-click action by the double-click interval, about 250 ms, or undo it). Show a short play/pause icon in the centre (fade out in about 0.5 s) as feedback. Clicks on the bars do not reach the video.
4. **Touch (iPad):** a tap on the video shows or hides the bars (play/pause stays on the play button), because a tap must also reveal the controls on a touch screen. Use pointer events (`pointerType`) to tell mouse from touch. Full screen on the iPad stays `webkitEnterFullscreen` as in R1c.
5. **Mac full screen:** Fullscreen API on the player container (as in R1c), so the IINA-like bars stay in full screen.
6. Keep: Range streaming, Download, Delete, the Back button to the Library, and the R1c storyboard preview.

### 2.3 Brave push hint (step 11)

1. When push subscription fails, show the browser's error text plus a hint. If the browser is Brave (`navigator.brave?.isBrave()`), say: "In Brave, open brave://settings/privacy, turn on Use Google services for push messaging, restart Brave, and try again." Otherwise keep a short generic message.
2. Confirm in a test that a Brave subscription endpoint on `fcm.googleapis.com` is accepted by the server (it is the same endpoint host as Chrome).

## 3. Tests

- JavaScript: the key handler (each shortcut; ignored in text fields and with Cmd/Ctrl/Alt; `preventDefault` called), the single-click versus double-click logic with a fake clock, the auto-hide timer rules, mouse versus touch tap behaviour, the remaining-time text, and the Brave hint selection.
- Browser (WebKit and Chromium, Mac-like 1440x900 with mouse; iPad-like 1180x820 with touch): open a video from the Library and press Space and Right **without any click first** (the regression for step 8); click on the video toggles play state; double click enters full screen without changing the play state; bars and cursor hide after idle and come back on mouse move; touch tap shows/hides bars. On Windows WebKit, video playback is a known platform limit (VE-R1a), so check play state with a stubbed or paused video where needed. Save screenshots of the player (bars shown) at both viewports in `work\evidence\VE-R1c-3\` (not committed) and describe them in the report.
- `ruff check`, `ruff format --check`, `uv run pyright`, the CI CPU pytest command, the node tests and the desktop E2E suite.

## 4. Allowed files

`src/videoenhancer/remote/**`, `tests/**`, `docs/REMOTE.md`, `.ai/LAST_REPORT.md`.

## 5. Done when

Sections 1 to 3 pass, the diff contains only allowed files, and the report lists test counts, the disk baseline and growth, the owner-check results from section 1, and exact re-check steps for the owner (Mac: keyboard right after opening, click/double-click, auto-hide; Brave: setting and retry; iPad: tap shows bars).

## 6. Operator after the commit (only after designer review)

`ve remote restart` on the real home. The owner said 「再起動して」 for the R1c-2 restart on 2026-11-03; for this cycle the designer will relay the owner's go-ahead. Report `ve remote status`.
