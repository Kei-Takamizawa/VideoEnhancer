# CURRENT_TASK: VE-P1e-3c2-F1 (fix the two player defects found by the automated owner check, then re-check)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3c2-F1
- **Date:** 2026-10-27
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`, open PR #13. It holds your check run `7288e34` (VE-P1e-3c2-OC, PARTIAL: 14 PASS, 1 FAIL, 1 HUMAN, 5 NOT_RUN) on top of `main` 5d70618.
- Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`. Keep the OC run by reference to `7288e34`; do not repeat its passing items unless section 4 asks.
- **Do not stop for a question.** Write the default you chose under "Questions for the designer" and continue.
- The operator again quits the owner's normal app before you start and restarts it afterwards. Use the same isolated `VE_HOME` (`work\scratch\owner-check\home`) and the same clips. The same input and capture rules as VE-P1e-3c2-OC section 3 apply: only windows of processes you started, foreground verified before `SendInput`, WGC of your own HWNDs only.

## 2. Designer review of the OC run

Accepted: items 2-9, 12, 13, 15-18 as PASS, and the method: own-process tracking, guarded input, HWND capture, the engine API for queueing. Item 14 stays HUMAN; its 54.5 ms median capture latency is supporting evidence only, and the capture-free gate (26.7 / 32.6 ms) was accepted in P1e-3c2 run 3.

Two defects are real and must be fixed in the product:

### 2.1 "The player did not respond." during Before/After playback

The banner appeared during the 63 s Before/After run while the video kept advancing (`sync-00..20.png`). The likely path is the host's 10 s request timeout in `gui/src-tauri/player/src/host.rs` (`timed_out` → `reply(..., "The player did not respond.")`). For a frame request in Before/After, the host waits until the follower (original) is aligned *and* playback restarted. The OC run pressed Home every 17 s while playing, so a seek during Before/After playback may never meet that condition. This is a designer hypothesis; verify it.

- Reproduce it with the production candidate and the OC sequence (Before/After on, playing, Home every 17 s for 60 s or more). Record which command timed out and why.
- Fix the root cause so that seeks, steps and other commands during Before/After playback complete, or fail with a specific error when they really fail. Do not just raise the timeout, and do not hide the banner.
- Add a test that fails before the fix: a Rust unit test of the completion logic, or the helper's test-feature e2e.

### 2.2 The cursor stays visible after the controls auto-hide

`autohide-retest-hidden.png`: the controls hide while playing, but the cursor stays. The page sets `cursor:none` (`.hidden-controls` in `gui/src/player/player.css`), and the host applies cursors only through WebView2's `CursorChanged` → `SetCursor` (`composition.rs`). A likely cause is that the composition controller does not raise `CursorChanged` until the next mouse input, so a still mouse never gets the hidden cursor, or the window's own `WM_SETCURSOR` handling resets it. This is a hypothesis; verify it.

- Fix it so the cursor hides within 2.5 s of the last mouse movement while playing over the picture, and comes back on the next movement. It must never hide while paused, over the controls, or outside the window.
- Prove it with a production-candidate capture that has cursor capture on, and also with `GetCursorInfo` (`CURSOR_SHOWING` / `hCursor`) read while your window is in front.

## 3. Allowed files

- `gui/src-tauri/player/src/**`, `gui/src/player/**`, their tests (`gui/tests/player-*`, Rust tests in the helper crate), and `gui/scripts/owner-check-auto.py`.
- Nothing else. If a fix seems to need another file, explain why under "Questions for the designer" and do not change it.

## 4. After the fixes: rebuild the candidate and re-check

- Rebuild the production candidate in `work\package\VideoEnhancer-candidate\` the same way as P1e-3c2 run 3 (pinned DLLs and lock check). Report the old and new helper and exe SHA-256 values.
- Re-run these items on the new candidate and judge each PASS / FAIL / HUMAN / NOT_RUN as in the OC task:
  - **11 autohide and cursor**, per 2.2.
  - **15 the 60 s Before/After run with Home every 17 s**: no error banner, and left/right within 2 frames in at least 20 samples.
  - **10 speed**: with focus on the blank surface, 1.25x advances 1.25 ± 0.05 s of media per wall second, measured over 8 s or more from the drawn time.
  - **19 no player process at 35 s**: check executable names and creation times, not windows.
  - **21 the fallback without DLLs**: the copy without the three DLLs plays through the HTML5 player. If foreground activation fails again, use `AllowSetForegroundWindow` from your own process, or start the copy with a `STARTUPINFO` that shows the window. Never send input to a window that is not in front.
  - **20 licences**: confirm that the Settings button starts the viewer, and that `THIRD_PARTY_NOTICES.md` in the candidate names libmpv, FFmpeg and libplacebo and contains the written source offer for `sources.tar.zst`. Check the viewer process by its process start only; read the file contents directly. Do not drive or capture the external viewer. A PASS here means the file is correct and the viewer starts.
  - **1 the 200 ms warm poster:** do not re-measure by capture. The capture-free measurement from run 2 (prewarmed 190 ms) stands. Mark it "PASS by reference to 0fd7293".
- Also re-run 13 and 14, to make sure the fixes did not break Before/After. 14 stays HUMAN.

## 5. Checks before the report

- Lint, unit tests, the helper's Rust tests and clippy (default and all features), Vitest, and the player Playwright e2e. All must pass. Do not loosen or skip tests.
- Close everything you started. Report the PIDs and that none remain. Empty `work\scratch\owner-check\home` at the end and delete the no-DLL copy after recording their sizes. Evidence goes under `work\evidence\VE-P1e-3c2-F1\`, at most 300 MB. Never commit captures. Persistent growth ≤ 1 GB.

## 6. Report

- The root cause and fix for 2.1 and 2.2, with the test that fails before and passes after.
- The table of the re-checked items, with evidence.
- Changed files.
- A short Japanese summary at the end for the owner (3-6 lines).
- **COMPLETED** only if both defects are fixed with tests, items 10, 11, 15, 19, 20 and 21 are PASS, 13 is PASS, and every check in section 5 passed. Otherwise PARTIAL.
