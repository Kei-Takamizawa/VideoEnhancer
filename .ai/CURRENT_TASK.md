# CURRENT_TASK: VE-P1e-3c2-F2 (show the licences inside the app, then finish the re-check)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3c2-F2
- **Date:** 2026-10-27
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`, open PR #13. It holds VE-P1e-3c2-F1: run 1 `1a61dae` (the two player fixes) and run 2 `0da3344` (PARTIAL re-check through Computer Use).
- **Run this task in the Codex desktop app**, as F1 run 2, so that Computer Use can be approved for the VideoEnhancer windows. The designer approves Computer Use for VideoEnhancer and VideoEnhancer-Player only.
- Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`. Keep F1 by reference to `1a61dae` and `0da3344`.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.
- The operator has already quit the owner's normal app and restarts it afterwards. Use the isolated `VE_HOME` `work\scratch\owner-check\home` and the clips in `work\scratch\owner-check\clips\`, queued through the engine API as before. Only windows of processes you started; never send input to a window that is not in front.

## 2. Designer review of F1 run 2 (0da3344)

Accepted as PASS: 10 (1.24996x), 13, 15 (24 pairs, at most 1 frame apart, no banner over 63 s with three Home seeks), 19, and 1 by reference. 14 stays HUMAN. The cursor hide at 2.047 s and the paused visibility are accepted as partial evidence for 11.

Still open:

- **20 is a real product defect.** The Settings button hands `THIRD_PARTY_NOTICES.md` to `ShellExecuteW`. On a PC with no program for `.md`, which includes the owner's PC, Windows shows "Open with" instead of the notices. The LGPL notices and the written source offer must be readable on every PC.
- **21 did not run.** Computer Use refused the click because the Claude window covered the point.
- **11 is incomplete.** The cursor coming back on movement and the cursor outside the player window were not measured.

## 3. Fix: show the licences inside the app

Designer decision: the app shows the notices itself instead of asking Windows to open the file.

- "Open-source licences" in Settings opens a view inside the main window. It shows the full text of `THIRD_PARTY_NOTICES.md` as plain, selectable, scrollable text, with a heading, a **Close** button that returns to Settings, and Esc to close. Plain text is enough; do not add a Markdown library or any other dependency.
- The desktop command reads the file the same way it is found today: next to the exe, then the development fallback `gui/THIRD_PARTY_NOTICES.md`. It returns the text. Refuse a file over 2 MB or one that is not valid UTF-8 with a specific error, and show that error in the view. Do not open any external program for this.
- Add a secondary **Show file** button that uses the existing reveal path (`explorer.exe /select,`), so the owner can still find the file.
- Keep keyboard focus and screen-reader labels as in the rest of Settings.
- Tests that fail before the fix: a Rust unit test of the read (found, missing, too large, invalid UTF-8), and a Vitest test that the button shows the text and that Close and Esc return to Settings. Update the desktop mock and the contract test if the command's return type changes.

## 4. Allowed files

- `gui/src-tauri/src/commands.rs` (and a new small module under `gui/src-tauri/src/` only if the read logic needs one), `gui/src/Pages.tsx`, `gui/src/desktop.ts`, `gui/src/types.ts`, `gui/src/style.css`, a new component under `gui/src/` if needed.
- Their tests: `gui/tests/**` and Rust tests in the main crate.
- `gui/scripts/owner-check-auto.py`.
- Nothing else. The player files from F1 are not to change. If something else seems needed, explain it under "Questions for the designer" and do not change it.

## 5. Rebuild the candidate and re-check

- Rebuild the production candidate in `work\package\VideoEnhancer-candidate\` as in P1e-3c2 run 3 (pinned DLLs and lock check). Report the old and new SHA-256 of `VideoEnhancer.exe` and `VideoEnhancer-Player.exe`. The player exe should not change; say so if it does.
- Re-check on the new candidate and judge each PASS / FAIL / HUMAN / NOT_RUN:
  - **20 licences:** press the Settings button through Computer Use. PASS needs a screenshot of the in-app view showing libmpv, FFmpeg and libplacebo and the written source offer for `sources.tar.zst`, no `OpenWith.exe` or other external process started (check by process start), and Close returning to Settings.
  - **21 the fallback without DLLs:** copy the candidate folder without the three DLLs, start the copy with the isolated home, open the landscape clip from History, and show that it plays through the HTML5 player (drawn time advancing in two screenshots at least 2 s apart). Before every click, maximize the target window and take a fresh screenshot so that nothing covers the point. If a click is still refused, use the keyboard through Computer Use (Tab, Enter, Space) with the target in front. Record each refusal message.
  - **11 autohide and cursor, the missing parts:** while playing, with the player in front, sample `GetCursorInfo` from a script every 100 ms: (a) hidden within 2.5 s of the last movement over the picture; (b) visible again within 300 ms after one Computer Use mouse move over the picture; (c) visible while paused; (d) visible while over the controls; (e) visible after a move outside the player window, for example onto the main VideoEnhancer window. Record the samples.
  - **12 keyboard and Esc**, **16 zoom and Reset**: run them again quickly, because the Esc handling is touched in Settings. Player behaviour must be unchanged.
- Items 1, 10, 13, 15, 19 stand by reference to `0da3344`. 14 stays HUMAN.

## 6. Checks before the report

- Lint, unit tests, the main crate's Rust tests and clippy, the helper's Rust tests and clippy (default and all features), Vitest, and the player Playwright e2e. All must pass, except failures that also happen on `main` and are environmental (no ffmpeg on PATH, LGPL FFmpeg without libx264, no Git): list those with the failing test names and the reason. Do not loosen or skip tests.
- Close everything you started. Report the PIDs and that none remain, including any `OpenWith.exe`. Empty `work\scratch\owner-check\home` and delete the no-DLL copy after recording their sizes. Evidence goes under `work\evidence\VE-P1e-3c2-F2\`, at most 300 MB. Never commit captures. Persistent growth at most 1 GB.

## 7. Report

- The fix for 20 and the tests that fail before and pass after.
- The table of the re-checked items with evidence, and the 11 samples.
- Changed files.
- A short Japanese summary at the end for the owner (3-6 lines).
- **COMPLETED** only if 20, 21, 11 (a-e), 12 and 16 are PASS and every check in section 6 passed or is a listed environmental failure. Otherwise PARTIAL.
