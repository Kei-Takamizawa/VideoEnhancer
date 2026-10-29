# CURRENT_TASK: VE-P1e-3c2-F3 (remove the false "can't be played" message in the fallback player)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3c2-F3
- **Date:** 2026-10-27
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`, open PR #13. It holds F1 (`1a61dae`, `0da3344`) and F2 (`b3205b5`, in-app licence view).
- **Run this task in the Codex desktop app**, as F2, because item 21 needs Computer Use on the main VideoEnhancer window. The designer approves Computer Use for VideoEnhancer only.
- Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`. Keep F1 and F2 by reference to their commits.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.
- The operator has already quit the owner's normal app and restarts it afterwards. Use the isolated `VE_HOME` `work\scratch\owner-check\home` and the clips in `work\scratch\owner-check\clips\`, queued through the engine API as before. Only windows of processes you started; never send input to a window that is not in front.

## 2. Designer review of F2 (b3205b5)

Accepted: the in-app licence view (`Licences.tsx`, `read_notices` with its limits, focus return, Esc, Show file), its tests, and item 20 PASS. Item 21 playback through the HTML5 player is accepted for H.264. Hosted CI on `0da3344` and `29c64fd` is green.

Items 11 (b, e), 12, 14 and 16 need the native player as a separate Computer Use target, which the tool does not offer. Do not try them again. The owner checks them by hand after this round. Items 11 (a, c, d) stand on F1 run 2 (`0da3344`): hidden after 2.047 s with `GetCursorInfo` flags 0 while the player was in front, visible while paused, controls visible while hovered.

## 3. Fix: no error message while the fallback player plays

The defect: in the copy without the three DLLs, the native player cannot start, so `HistoryDetail.tsx` sets `nativeError` to "This video can't be played here. Open it in your default player instead." and keeps showing it above the HTML5 player, which plays fine.

Designer decision:

- When the native player cannot start and the HTML5 player is used, show no error. Show one short neutral line instead: "Playing with the basic player." Keep the real reason in the log, not on screen.
- Show "This video can't be played here." and the **Open in default player** button only when the HTML5 player also fails (the existing `unsupported` state, a `<video>` error) or HEVC is missing (the existing HEVC notice, unchanged).
- Do not change the native player, the HEVC notice, or anything else in the dialog.
- Test that fails before the fix (Vitest): `openPlayer` rejects and then `onPlayerError` fires. The basic-player line shows, the error text and the default-player button do not, and the `<video>` is shown. Then a `<video>` error shows the error text and the button. Keep the existing fallback tests passing.

## 4. Allowed files

- `gui/src/HistoryDetail.tsx`, `gui/tests/**`, `gui/scripts/owner-check-auto.py`, `.ai/LAST_REPORT.md`.
- Nothing else. If something else seems needed, explain it under "Questions for the designer" and do not change it.

## 5. Rebuild the candidate and re-check

- Rebuild the production candidate in `work\package\VideoEnhancer-candidate\` as before (pinned DLLs and lock check). Report the old and new SHA-256 of `VideoEnhancer.exe` and `VideoEnhancer-Player.exe`. The player exe must not change.
- **21:** copy the candidate without the three DLLs, start it with the isolated home, open the H.264 landscape clip from History through Computer Use, and show in two screenshots at least 2 s apart that the drawn time advances, the basic-player line is shown, and no "can't be played" text or default-player button is shown.
- **20, quick:** open and close the licence view once to confirm it still works.
- Leave the rebuilt candidate in place for the owner's hand check. Delete the no-DLL copy.

## 6. Checks before the report

- Lint, Vitest, the player Playwright e2e, and the main crate's Rust tests and clippy. All must pass. Do not loosen or skip tests.
- Close everything you started and report the PIDs. Empty `work\scratch\owner-check\home`. Evidence goes under `work\evidence\VE-P1e-3c2-F3\`, at most 300 MB. Never commit captures. Persistent growth at most 1 GB.

## 7. Report

- The fix and the test that fails before and passes after.
- Items 20 and 21 with evidence, and the new hashes.
- Changed files.
- A short Japanese summary at the end for the owner (3-6 lines).
- **COMPLETED** if the fix has its test, 20 and 21 are PASS, the player exe is unchanged, and every check in section 6 passed. The owner's hand check is not part of this gate. Otherwise PARTIAL.
