# CURRENT_TASK: VE-R1c-2 (add a device from a paired device, CI type error, R1c fixes)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1c-2
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #19) at the commit that adds this file, on top of VE-R1c at 532c573.
- Write a new `.ai/LAST_REPORT.md` for VE-R1c-2; keep the older reports below it.
- Same isolation rules as VE-R1c. Do not start, stop, install or restart the owner's real remote service; do not touch its home, library, task or firewall. No dependency changes.
- Record a disk baseline at the start and report growth at the end.

## 1. Owner request (2026-11-03, urgent): add a new device from an already paired device

Today a new device can only be paired after "VideoEnhancer - Redo pairing" is run on the PC. The owner wants to start pairing from the app on a device that is already paired, without touching the PC.

1. Add `POST /api/pair/open` (device cookie required, same Host, Origin and private-source checks as other writes, body `{}`). It opens the existing 2-minute pairing window (the same `Devices.open_pairing`) and returns `closes_at`. Rate-limit it to 5 calls per device per 10 minutes. Log the route and the opening device's id only.
2. **Settings** tab: an **Add a new device** button. After it is pressed, show "Pairing is open for 2:00. On the new device, open <setup address> and follow the steps, then select Pair this device." with a live countdown, the setup address (the HTTP setup page, which serves the CA and the steps for iPad and Mac), and a **Copy address** button. When the window closes or a device claims it, the panel says so ("Pairing closed." or "New device added: <label>.") and the device list refreshes.
3. `GET /api/session` reports `pairing_open` and `closes_at` so the Settings panel can show the state after a reload.
4. The new device still has to install and trust the CA first (unchanged; the setup page explains it). Pairing itself still claims inside the window exactly as now; the first claim closes the window.
5. Keep the PC path ("Redo pairing" and `ve remote pair`) working unchanged.
6. Update docs/REMOTE.md and docs/API.md.

## 2. CI fix (must fix)

PR #19 CI fails at `pyright`: `src/videoenhancer/remote/gateway.py:123` assigns `self.jobs.thumbnails` but `RemoteJobs` does not declare `thumbnails`. Declare it in `RemoteJobs.__init__` (optional, `None` by default). Run `uv run pyright` locally and report it passing; add `pyright` to the checks you always run.

## 3. Small fixes from review

1. `POST /api/pair/claim` with a body that is not a JSON object (or invalid JSON) must return 400 with a clear message, not a server error. Add a test.
2. Report whether any other new R1c route can raise an unhandled exception from client input, and fix what you find.

## 4. Known local failure

`gui/tests/e2e/p1f3-visual.spec.ts` "fresh calibration" fails on this PC on `main` too (classified as pre-existing in VE-R1b-3; CI passes it). Run the desktop E2E suite as usual and list results, but this one known local failure does not by itself make this cycle PARTIAL when every CI check passes. Any other E2E failure does.

## 5. Tests

- Python: `pair/open` needs the cookie, checks Origin, rate-limits, opens the window, is logged without secrets; `session` reports the window; a claim after `pair/open` succeeds and closes the window; bad claim bodies get 400.
- JavaScript: countdown text, closed and added states.
- Browser smoke: the Settings button, countdown and copy on an iPad and a Mac viewport.
- `ruff check`, `ruff format --check`, `pyright`, the CI CPU pytest command, the node tests and the desktop E2E suite.

## 6. Allowed files

`src/videoenhancer/remote/**`, `tests/**`, `docs/REMOTE.md`, `docs/API.md`, `.ai/LAST_REPORT.md`.

## 7. Done when

Sections 1 to 5 pass, the diff contains only allowed files, and the report lists test counts, the disk baseline and growth, and the owner steps to add a Mac from the iPad. The operator restarts the real service after the designer's review.
