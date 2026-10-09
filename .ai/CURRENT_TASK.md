# CURRENT_TASK: Cycle P1b (engine service, local API, complete desktop GUI)

- **Task ID:** VE-P1b
- **Date:** 2026-10-08
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** P1a-6 is finished and PR #2 (`p1-restoration-gui`) has been merged into `main` by the owner. Create a new branch `p1b-gui` from the latest `main` and open a **draft** PR for it. Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Do not push to `main`.

This cycle delivers the whole GUI: engine service + local API + app shell + tray + the **Queue**, **Plan**, **Schedule**, **Models** and **Settings** pages + the **Trial** viewer. Work in the order R1 → R7; if time runs out, finish earlier requirements completely and mark the rest NOT RUN.

## 0. Engine facts from P1a (merged in PR #2)

- Defaults: `standard` = BasicVSR++ NTIRE21 decompression (clip 15 / overlap 2, Torch peak ≈ 4.4 GB) + RIFE 4.25; `fast` = resize + RIFE. Measured on the RTX 4060 Ti: `standard` ≈ 2.35 input fps, `fast` ≈ 15.7 input fps.
- The estimator includes finalization; measured accuracy: `fast` 2 h job −5.2% initial / −2.4% at 10%; `standard` 15 min job −10.9% / −9.3%.
- Jobs report `phase` (`processing` / `finalizing`) and step; quality metrics are computed inline; `ve report --full-quality` is development-only and must not be exposed in the GUI.
- Model registry: `ve models list/add/remove`, JSON manifests with licence and commercial flag, adapters `basicvsrpp`, `rife`, `spandrel`.

## 1. Product context (self-contained)

VideoEnhancer is a Windows 11 desktop app for an owner with an NVIDIA RTX 4060 Ti (8 GB). It converts video files offline: it removes compression damage (BasicVSR++ restoration, `standard` preset) and doubles the frame rate (RIFE), keeping the original look (including beauty filters). Long videos (about 2 hours) take many hours (`standard` ≈ 2.4 input fps, about 25 GPU hours for 2 hours of 30 fps video; `fast` ≈ 17 fps), so the app runs only in **operating hours** the owner sets, shows the **estimated processing time**, and a **day-by-day plan** until the queue is done. The engine (Python, package `videoenhancer`, CLI `ve`) already provides: segmented resumable jobs, the scheduler with weekly windows and date exceptions, the estimator and day planner, calibration, `ve trial`, the model registry (`ve models`), and Smart App Control detection. The GUI must use these, not reimplement them.

## 2. Requirements

### R1. Engine service (`ve serve`)

- A long-running engine process that owns the queue, the schedule and the run controller (reuse the existing controller and job store; the CLI keeps working on the same store; no duplicated state).
- HTTP on `127.0.0.1` only, random free port, plus a Server-Sent Events stream. A random bearer token is created at start and written with port and pid to `%VE_HOME%\serve.json`, readable only by the current user. Requests without the token are rejected. Never listen on another interface. Reject requests whose `Origin`/`Host` is not the local app (protection against DNS rebinding).
- Only one `ve serve` per `VE_HOME` (lock file); a second start exits with a clear message and the existing port.
- Endpoints (names are suggestions; version the API under `/v1`):
  - `health` (version, GPU name, driver, VRAM, Smart App Control status, engine state)
  - `queue`: list, add (file + settings), reorder, pause/resume/cancel a job, remove finished, open-output-folder is done by the GUI, not the engine
  - `estimate`: for a file and settings, the estimate per preset (GPU time with a range, finish date/time under the current schedule and queue), plus warnings (HDR rejected, disk space with numbers, Smart App Control)
  - `plan`: the day-by-day plan for the whole queue (used by the Queue page now, by the Plan page in P1b-2)
  - `schedule`: get/set weekly windows and date exceptions; set/clear a temporary override ("run now until job completes" / "until a time")
  - `events` (SSE): job/segment progress, fps, ETA, state changes, plan changes, errors; a heartbeat every 10 s
  - `trial`: start a trial (file, start, length, settings), progress, cancel, fetch its preview files (uses the existing `ve trial` logic)
  - `models`: list the registry (id, task, architecture, licence, commercial flag, size, weights verified), download a built-in model with the user's consent recorded, add a model folder (same validation as `ve models add`), remove a non-built-in model, verify again
  - `settings`: default output folder, default preset/codec/short side/frame rate, start with Windows, theme, log folder, advanced options (clip length/overlap, interpolation thresholds)
  - `calibrate`: start `ve bench --calibrate`, progress
- The engine keeps working when the GUI is closed or crashes.
- `docs/API.md` documents every endpoint with an example. Automated API tests run on the CPU backend without a GPU (add a job, observe SSE progress, reorder, pause/resume, schedule change updates the plan, token required, wrong origin rejected).

### R2. Desktop app shell

- **Stack:** Electron + React + TypeScript + Vite in a top-level `gui/` folder with its own lockfile. Short dependency list; plain CSS or one small well-known library. UI language English. Windows 11 only.
- **Security:** context isolation on, node integration off, sandboxed renderer, strict preload API (only the calls the UI needs: API base URL and token, file-open dialog, open folder, copy to clipboard), no remote content, a strict Content-Security-Policy.
- **Process model:** the main process starts `ve serve` if it is not running, reads `serve.json`, passes the connection to the renderer. Single instance (a second launch focuses the window). Closing the window keeps the app in the **system tray**; tray menu: Open, Pause processing / Resume processing, Quit. **Quit** stops the engine gracefully (the current segment is aborted, state stays consistent, the next start resumes). "Start with Windows" (off by default; toggle on the Settings page) registers with Electron's login-item API so the app starts hidden in the tray at login.
- If the engine is unreachable, show a banner with Retry and keep the last known data visible; never block the UI.
- **Visual style:** calm desktop tool. Dark theme by default, light theme when the system is light. One accent color. Segoe UI Variable. 4 px spacing grid. No gradients, no decorative animation. Time and progress are the most legible elements. Keyboard accessible, visible focus, WCAG AA contrast. Minimum window 1100×700; works at 125% and 150% scaling.
- **Layout:** left navigation rail with **Queue**, **Plan**, **Schedule**, **Models**, **Settings**. A **status strip** at the bottom, always visible: engine state (Running / Finalizing / Waiting for operating hours / Paused / Idle), current job and segment, current fps, and the time of the next change (for example "Pauses at 08:00" or "Starts at 22:00").

### R3. Queue page (home)

```
+--------------------------------------------------------------------------------+
| [+ Add videos]  or drop files here                                              |
+--------------------------------------------------------------------------------+
| 1  clip_a.mp4   720x1280 30fps 1:52:03    Standard  Running  ████████░░ 62%     |
|    Finish: Thu 10/09 02:10   (21 h 40 m GPU, ±25%)  Segment 14/23  [Pause] [⋯]  |
| 2  clip_b.mp4   1280x720 60fps 0:12:40    Fast      Waiting  Starts Thu 10/09   |
|    Finish: Thu 10/09 05:30   (1 h 5 m GPU)                         [Pause] [⋯]  |
+--------------------------------------------------------------------------------+
| All jobs finish Fri 10/10 about 03:40                                           |
+--------------------------------------------------------------------------------+
```

- Add by button or drag and drop, several files at once. Adding opens one short dialog (not a wizard): preset (Standard default, Fast), output short side (Keep / 1080 default / 1440 / 2160), frame rate (Keep / 2× default), codec (HEVC default / H.264 / AV1 if supported), output folder (default from settings, else the source folder's `enhanced` subfolder). An **Advanced** disclosure holds the restoration model choice (from the model registry; default the preset's model). The dialog shows **live, for each preset, the GPU time and the finish date/time** under the current schedule and queue, and warnings with exact numbers. Adding a video and seeing when it will finish takes at most three clicks.
- Rows: reorder by drag (and by keyboard), row menu: Move to top, Pause, Resume, Cancel, Remove, Open output folder, Show log, Copy details. Progress shows percent, segment count and finish time. Use the engine's `phase` and step fields: during finalization the row shows "Finalizing: assembling / validating" with its own step progress, and the job is never shown as 100% before the engine reports it done (the engine already caps progress at 99.9%). Times are always concrete ("Finish: Thu 10/09 02:10", "21 h 40 m"), never only a percent. Uncalibrated estimates show an "uncalibrated" badge.
- Error rows: plain-English message saying what failed, which job and segment, what to do next, and "Copy details" (a block the owner can paste to the designer).
- Cancel and Remove ask for confirmation; Pause and Resume do not.
- Empty state: one friendly sentence and the Add button.
- Summary line at the bottom: when all jobs finish.

### R4. Schedule page

- A **weekly grid** (7 columns, 24 hours, 15-minute resolution) that the owner paints or drags to select allowed hours, and the same data as an editable list ("Mon–Fri 22:00 → 08:00"). Windows may cross midnight.
- **Exceptions:** a month calendar; click a date to mark it Off or set custom hours for that date; list of upcoming exceptions with delete.
- A toggle "Only run during these hours" (off = always allowed) and a "Run now, ignore schedule" button with two options: until the current job completes, or until a chosen time.
- A live preview line: "Next window: Tue 22:00 – Wed 08:00 (10 h)", and the effect on the queue: "All jobs finish Fri 10/10 about 03:40 (was Sat 10/11 01:20)".
- Plain-English validation (minimum 15 minutes; overlapping windows are merged). Changes apply on Save; unsaved changes are indicated.

### R5b. Plan page

- The day-by-day plan as a table and a timeline: one row per day with date and weekday, the operating windows, planned run hours, and per job the progress range (for example `A 8% → 50%`) and a "done ~02:00" marker. Next to it a horizontal 00:00–24:00 bar per day: windows as light blocks, planned running time as filled blocks colored per job.
- Summary line on top ("All jobs finish Fri 10/10, about 03:40"), live updates over SSE when jobs, order, schedule, preset or measured speed change, and a best / expected / worst toggle.
- Uncalibrated estimates show a badge and a "Calibrate" button (progress indicator; at most about 5 minutes).

### R5c. Models page

- Table of the registry: name, task (Restore / Interpolate), licence, "Non-commercial" label where it applies, size, built-in or user-added, weights verified. Download of a built-in model requires a confirmation dialog showing the licence name and source URL; record the consent. Download progress and SHA-256 result, "Verify again".
- "Add model…" picks a folder that contains a manifest and weights; show the validation result in plain English (for example "The weights do not match the SHA-256 in model.toml"). "Remove" for user-added models only, with confirmation. A link to `docs/ADDING_MODELS.md` on GitHub.

### R5d. Settings page

- Default output folder, default preset, codec, short side, frame rate, "Start with Windows", theme (System / Dark / Light), log folder with Open, "Run speed calibration", "Copy diagnostics" (GPU, driver, versions, last errors), the advanced options behind an "Advanced" disclosure, and an About box with the version and licence notes (including that some models are non-commercial).

### R6b. Trial viewer

- "Trial" in the add dialog and the row menu. The owner picks the start (a slider over the timeline with a thumbnail strip; default the middle) and the length (3, 5 or 10 s; default 5).
- The engine renders the trial through the real pipeline with the job's settings, reports the measured speed, and this updates the job's estimate.
- Preview files for the GUI only: the trial result and the matching source excerpt resized to the same output size with the same resize filter, both **H.264 8-bit** high quality (Chromium may not decode HEVC Main10). Delete them when the job is removed.
- Viewer: before/after with a draggable split slider, synchronized play/pause/seek/loop, frame stepping with the arrow keys, zoom with pan up to 400% (nearest-neighbour when zoomed), side-by-side toggle, labels "Original" / "Enhanced", and "Processed at 2.4 fps". The two videos stay in sync within one frame; if two `<video>` elements cannot guarantee it, use WebCodecs to canvas and say why in the report.
- A trial is cancelable and never disturbs a running job: if the worker is busy it runs between segments and the UI says how long it will wait; a trial may exceed the operating window by at most its own length, and the UI says so.

### R5. Smart App Control

If the engine reports the problem, show a blocking, plain-English message at start and on the Queue page: what is happening, a link to `docs/TROUBLESHOOTING.md` on GitHub, and a Retry button. Do not change Windows settings from the app.

### R6. Packaging for the owner (development build)

- `gui/` npm scripts: `dev`, `build`, `test`, `lint`, `typecheck`, and `package` that produces an unsigned Windows folder or installer the owner can run. Document in `docs/GUI.md` how to run it (prerequisites, commands, how it finds the engine and Python environment). No auto-update, no telemetry.

## 3. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs in English. No media, weights, generated videos, `node_modules` or build output committed; no private sample names anywhere.
- Do not change the engine's processing behaviour or presets. API additions to the engine are fine; CLI behaviour stays the same.
- The README stays for non-engineers; add one short paragraph "Using the app" (English, no technical terms beyond "NVIDIA RTX graphics card"). No screenshots showing real people; use synthetic test footage for any screenshot.

## 4. Acceptance criteria

- **A1** `ve serve` with token, localhost-only, origin check, single instance; API tests pass on CPU; `docs/API.md` complete.
- **A2** The app starts the engine, survives window close (tray), Quit stops the engine cleanly and the job resumes on next start; single instance works.
- **A3** Queue page: add (button and drop) with live per-preset estimate and finish time, reorder, pause/resume/cancel/remove with confirmations, error rows with Copy details, live progress over SSE, summary line.
- **A4** Schedule page: weekly grid and list stay in sync, crossing midnight works, exceptions, override, live preview and queue effect, validation; saved schedule is respected by the engine (verified by an automated test with a fake clock).
- **A5** Engine-unreachable banner and Smart App Control message work (tested with a mocked engine).
- **A6** GUI tests: component tests for the Queue and Schedule pages, and one end-to-end test (Playwright for Electron) that adds a short synthetic file on the CPU backend and sees it finish.
- **A7** Engine checks (`ruff`, `ruff format --check`, `pyright`, CPU tests) and GUI checks (lint, typecheck, tests) pass; CI green on Windows and Ubuntu (GUI e2e on Windows only is fine).
- **A8a** Plan page: table and timeline match the engine plan, live updates, best/expected/worst, calibrate button works.
- **A8b** Models page: list, consent-recorded download, add a user model folder (valid and invalid cases), remove, verify again.
- **A8c** Settings page: all settings persist and are used by new jobs; Start with Windows registers and unregisters; Copy diagnostics works.
- **A8d** Trial viewer: trial on GPU with speed shown and estimate updated, sync within one frame, zoom/pan, frame stepping, cancel, waits correctly while a job runs.
- **A8** Manual check on the RTX 4060 Ti: one real sample through the GUI with `standard`, close the window during processing, reopen from the tray, Quit, restart, resume to completion.

## 5. Checks for the owner after the PR

1. Add a video by drag and drop and read the finish time for Standard and Fast in the dialog.
2. Paint operating hours on the Schedule page and watch the finish time change.
3. Close the window while it runs, reopen it from the tray, then Quit and start again: the job continues.
4. Run a 5-second Trial and compare Original and Enhanced with the slider and zoom.
5. Open the Plan page and check the day-by-day schedule.

## 6. Report (`.ai/LAST_REPORT.md`, English)

Summary per requirement; A1–A8 with PASS / FAIL / NOT RUN and evidence; screenshots of every page and the trial viewer with synthetic footage (outside the repository, paths listed); how to start the app; known issues and questions for the designer; exact reproduction steps. Never report a test as passed if it did not run.
