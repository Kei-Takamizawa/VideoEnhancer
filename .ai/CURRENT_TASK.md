# CURRENT_TASK: Cycle P1e-3c2 (the mpv player in the product, Before/After, Compare speed)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3c2
- **Date:** 2026-10-26
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`. `main` (`aad7eed`, the P1e-3c1 squash merge) is merged into it. Apart from this file and `design/player/player_mockup.html`, its tree equals `main`. The operator opens a new draft PR.
- This file is `.ai/CURRENT_TASK.md`. Write a new `.ai/LAST_REPORT.md`. Its first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- **Diff base:** `origin/main`.
- Restore any dependencies the last cleanup removed. The restore does not count toward growth; report its size.
- **Do not stop the cycle for a question.** Write the default you chose under "Questions for the designer" and continue.

### Where this cycle sits

P1e-3c1 (merged: source-built LGPL libmpv, fast B1 spike) → **P1e-3c2 (this cycle: the real player in the product)** → P1e-3d (bit-identical speed-ups, warm worker, recalibration, C17 one-pass).

## 2. What is already decided (read these first)

- `spikes/mpv/README.md`, `spikes/mpv/LICENSES.md`, `spikes/mpv/source-manifest.json`, and the P1e-3c1 report in Git history (`git log -- .ai/LAST_REPORT.md`). The first P1e-3c1 run, commit `0127853`, has the Part C product recommendation.
- **Approach B1:** a WebView2 **composition controller** over a libmpv D3D11 picture in one DirectComposition tree. B2 is dropped.
  - The spike met every target: first frame 25-40 ms, seek median 30-160 ms, CPU 5-11 %, exact frame stepping, hover preview 116 ms for a new position and 9 ms cached.
  - Keep its event-driven design. Never query mpv synchronously from the render path; in P1e-3c1 that starved the flip wait.
- **The DLLs:** CI run `40202006764` on `b65a4cc` built them, and the PC accepted them.
  - The files are `libmpv-2.dll`, `libspirv-cross-c-shared.dll` and `libwinpthread-1.dll`: 36,556,818 bytes in total, SHA-256 in the P1e-3c1 report.
  - A copy is on the PC at `work\cache\mpv-lgpl\ci-build\40202006764\`. Run `40203859946` reproduced them byte for byte.
  - The prebuilt zhongfly DLL is for measurements only. It must never be packaged.
- **The UI design the owner approved** is `design/player/player_mockup.html` (v3). Open it in a browser. Its "Design notes" panel lists the behaviour. Binding points:
  - Clicking a History thumbnail opens the player. The poster shows at once and playback starts on the same click.
  - Controls float on the video with **no dark panel** behind them (thin shadows only). The title, preview box, menus and shortcut sheet are transparent too. The letterbox stays black.
  - Controls, title and cursor hide after 2 s while playing. Any mouse move brings them back. While paused, they stay visible.
  - The seek-bar hover preview sits **above** the bar, never over it, with the time under the picture. A nearest-keyframe preview is fine; the main player stays frame-exact.
  - **Before / After** splits the picture with **nothing drawn on the divider**. The divider moves with the slider or a two-finger horizontal scroll.
  - While paused, the step buttons move one output frame.
  - Ctrl + scroll (pinch) zooms 100-800 % around the cursor. Two-finger scroll pans when zoomed.
  - Other controls: the Details sidebar, the `?` shortcut sheet, double-click for fullscreen, Esc, and the shortcuts listed in the mockup.

## 3. Part A: the player in the product

### A1. Where it lives

- **Default architecture: a separate player helper process.** Build a small Rust binary in the desktop workspace, for example `gui/src-tauri/player/` producing `VideoEnhancer-Player.exe`. Start from the hardened spike host. The main app starts it on demand and talks to it over a private pipe (or stdin/stdout) with versioned JSON messages.
  - **Why:** a libmpv or GPU-driver crash cannot take down the main app (release builds use `panic = "abort"`). Closing the player frees all of its memory and GPU memory. Tauri and wry need no patch.
  - The player window is owned by the main window. It opens centred over it at the same size, or the video's size if smaller, and it can go fullscreen.
  - If you measure that this design cannot reach the targets in A5 and an in-process host can, you may switch. Give the numbers and the reason under "Questions for the designer".
- **Lazy loading:** the DLLs load only when the player opens. Closing the player ends the helper, or leaves it idle for at most 30 s so the next video opens fast. Choose one, measure both, and report.
- **Fallback:** if the helper or the DLLs are missing, fail to load, or fail to create a D3D11 device, the app falls back to today's HTML5 player in `HistoryDetail.tsx`, with its HEVC notice and its "Open in default player" button. The player must never be a dead end. Add a test for each fallback path.
- **Where the player is used this cycle:** History (the detail view and thumbnail click).
  - Compare models (`Trial.tsx`) keeps its HTML5 views this cycle, apart from the speed work in Part C.
  - Do not change the media path the engine writes. Do not change settings. Do not change job behaviour.

### A2. The controls page and IPC

- The controls are a bundled HTML/TS page built with the existing Vite setup, for example a second entry `gui/player.html`. It is loaded only from the app's own embedded assets: a virtual host mapping or `WebResourceRequested` on a private host name.
  - No remote content and no `file://`.
  - A strict Content Security Policy.
  - Navigation and new windows are blocked.
  - DevTools are off in release builds.
- **IPC between the page and the helper:** allowlisted and versioned, with request IDs.
  - Commands: open, close, play/pause, exact seek, step forward/back, speed, volume/mute, fullscreen, zoom/pan, Before/After on/off and divider position, and hover preview with generation numbers. Only the latest hover request counts.
  - Events: loaded, error, EOF, pause, duration, position, seek done, step done, preview ready, and decoder info (`hwdec-current`).
  - Position updates are rate-limited to about 10 Hz.
  - No arbitrary mpv command or property ever crosses from the page.
- **IPC between the main app and the helper:** the main app passes **opaque media handles**, never raw paths from HTML.
  - The Rust media layer (`gui/src-tauri/src/media.rs`) resolves each handle to the job's output or original file. It checks the file exists, then hands the absolute path to the helper.
  - The helper accepts only handles the main app gave it in this session.
- **Errors:** every request completes with a result or an error routed back to the caller. Show plain English messages, for example "This video can't be played here. Open it in your default player instead." The asynchronous mpv log goes to the app log, never to the UI.

### A3. Before / After

- **What it compares:** the enhanced output and its original. The original is scaled to the output size and shown on the same clock, at the output's frame rate.
  - If the original is missing or recycled, Before/After is disabled, with a tooltip saying why, as History already does for "Compare again".
  - Audio comes from the enhanced output.
- **Divider:** it must move **without pausing or rebuilding the decode graph**. P1e-3c1 found that changing a `lavfi-complex` graph pauses playback. Candidate methods:
  1. Render a one-clock `hstack` of [original | enhanced] at the output size into one surface. The host shows two DirectComposition visuals of that surface, each with an offset and a clip rectangle, so moving the divider only changes the clips.
  2. Runtime filter commands, if the pinned FFmpeg and mpv support them on the complex graph.
  3. Your own method.

  Use the first that works. Report the latency of a divider move and any drift between the two sides.
- **If no method moves the divider without a pause,** ship a side-by-side (hstack) mode with the same controls, and report why under "Questions for the designer".
- Frame stepping and seeking act on both sides together.

### A4. Accessibility, input and DPI

- Every control is reachable by keyboard and has an accessible name.
- Shortcuts follow the mockup's sheet.
- Focus returns to History when the player closes.
- Per-monitor DPI and window moves between monitors work.
- Device loss, sleep and resume, and display changes recover, or close the player with a message. They never hang it.

### A5. Targets (GPU PC, measured as in P1e-3c1, capture off)

| Metric | Target |
| --- | --- |
| Click to first frame, player not yet open (cold helper), median of 5 | ≤ 500 ms |
| Click to first frame, player open or helper idle (warm), median of 5 | ≤ 150 ms |
| Seek, median / worst of 20 | ≤ 200 ms / ≤ 400 ms |
| CPU during 60 s playback, one core = 100 % | ≤ 15 % |
| Dropped frames over 60 s | 0 |
| Frame stepping against the burned-in numbers | exact |
| Hover preview, new / cached | ≤ 150 ms / ≤ 30 ms |
| Before/After drift over 60 s | 0 frames |
| Before/After divider move, input to picture | ≤ 50 ms, no pause |
| Main app private bytes and GPU memory 10 s after the player closes | back to within 5 % of before opening |

- Use the P1e-3b fixtures (H.264 1080p30, HEVC Main10 1440p60, AV1 10-bit 1440p60, VP9 1080p60, HEVC rotation).
- Add one Before/After pair: a synthetic original and its synthetic "enhanced" counterpart with burned-in frame numbers, at different resolutions and frame rates.
- If a target is missed, report the best you reached, the profiling evidence of the limit, and continue.

### A6. Packaging and licences

- `gui/scripts/package-tauri.mjs` adds the three DLLs and the helper to the package. It takes the DLLs from a folder given by an environment variable, for example `VE_LIBMPV_DIR`, and checks each file against a pinned lock file in the repo, for example `gui/src-tauri/libmpv.lock.json` with the file names, sizes, SHA-256, CI run ID and artifact digest. On a mismatch it refuses to package.
  - Without the variable, the package builds without the player and the app uses the fallback. CI works this way.
- **Licence materials:**
  - Ship the licence texts from the CI artifact's `LICENSES/` and an app-level third-party notices file.
  - Add an "Open-source licences" entry in Settings (or About) that opens them.
  - Put `sources.tar.zst` **next to** the package as its own file, not inside it, and add a written source offer to the notices.
  - Follow `spikes/mpv/LICENSES.md`, including the user's right to replace the DLLs. The app must keep working with a user-replaced compatible `libmpv-2.dll`; do not pin the DLL hash at run time.
- Report the package size before and after.

## 4. Part B: tests

- **CPU CI (Windows and Ubuntu, no GPU, no DLLs):**
  - Rust unit tests for the IPC schema, the allowlist, handle resolution, request and response routing, latest-only hover, and the lifecycle and lazy-load state machine.
  - Vitest for the controls page: autohide, keyboard shortcuts, the divider, zoom maths, preview placement above the bar, and accessible names.
  - Playwright e2e on Windows for the fallback: no DLL, so History plays through HTML5 as today.
  - Do not loosen or skip any existing test or e2e spec.
- **Optional:** a Windows CI job that downloads the pinned artifact and runs the helper with `hwdec=no` (software decode) for a short open, play and close smoke test. Add it only if it is reliable on `windows-latest`. Never mark it as allowed to fail.
- **GPU PC:**
  - every A5 target on every fixture;
  - Before/After on the pair;
  - every fallback path;
  - a transparency self-check showing the controls over the video with no dark panel, done by self-capture of the player's own window only, as in P1e-3b section 13;
  - a 30-minute open/close soak (open, play 20 s, close, repeat) with private bytes, GPU memory and handle counts.
- **Fix the flaky test `tests/test_link_jobs.py::test_failed_transfer_retries_three_times_then_offers_retry`.** It failed once on Windows CI, at the backoff assertion `b - a >= delay`.
  - Find the root cause.
  - Make it deterministic without weakening what it checks: retries 3 times, with delays of at least 1, 2 and 4 s, then a failed state with a retry offered. For example, inject the clock and sleep.

## 5. Part C: Compare speed

1. Profile a 5 s Compare on the GPU PC with the default model set. Do it in two states: with no job running, and with a Standard job running. Report time to the first tile and, for each model:
   - model load;
   - decode and range analysis;
   - inference;
   - encode;
   - waiting for the GPU lease.
2. Implement only changes that leave every preview **bit-identical** and stay inside the Compare path (`src/videoenhancer/service/compare.py`, the Compare scheduling in `engine.py`, and `Trial.tsx` display). For example:
   - reuse the decoded range and the original preview across models;
   - start the first tile sooner;
   - show each model's tile as soon as it is done.

   Prove bit-identity with hashes of the preview files before and after.
3. Anything bigger, such as a warm worker, model caching across operations or GPU preemption, goes into the report as a proposal for P1e-3d with estimated gains. Do not build it now.

## 6. Do not change

- The engine's processing, models, outputs, estimates, calibration and the job pipeline, except the Compare path in Part C.
- The settings format and the media path.
- `spikes/mpv/ci-build/**` and `.github/workflows/libmpv-lgpl.yml`.
- The diff against `origin/main` may contain:
  - `gui/**`, including the new helper crate;
  - `tests/**`;
  - the Compare files named in Part C;
  - `.github/workflows/ci.yml`, only to add the new tests or the optional smoke job;
  - `README.md`, with a short user-facing description of the player;
  - `docs/**`;
  - `spikes/mpv/**`, only if a spike file is moved into the product;
  - `.gitignore`;
  - `.ai/LAST_REPORT.md`;
  - `.ai/CURRENT_TASK.md` and `design/player/**`, which are the designer's.

## 7. Constraints

- Work only inside `work\`. Binaries, DLLs, fixtures, captures and screenshots stay out of Git.
- Downloads only from official sources, verified by checksum, listed in the report. Free software only.
- No system-wide installs beyond what AGENTS.md allows. No driver, registry, PATH, WebView2 Runtime or display-setting changes.
- Self-tests capture and drive only the app's and player's own windows. Never send input to any other window.
- Persistent growth ≤ 1 GB, not counting the restored dependencies. Report the package and evidence sizes. Stop and report if D: would fall below 200 GB free.
- Tests clean up their own files. Do not create scratch folders with mode `0o700`.
- English for all code, comments, UI text and docs.

## 8. Acceptance

- Part A works on the GPU PC, with the A5 table filled for every fixture and the Before/After pair. Every fallback path is shown.
- Part B: new tests pass, the flaky test is fixed, and nothing existing is loosened. Windows and Ubuntu CI are green on the final commit (the operator pushes and checks).
- Part C: the profile tables, the bit-identity hashes, and the proposals for P1e-3d.
- The package builds with and without `VE_LIBMPV_DIR`. The licence notices, the source offer and the replacement right are in place.
- Lint, format and type checks pass for Rust (fmt, clippy `-D warnings`), TypeScript (eslint, tsc) and Python (ruff, pyright).

## 9. Report (`.ai/LAST_REPORT.md`)

- Status line.
- Part A: architecture chosen and why; the IPC schema; the A5 table with every run and raw arrays in an appendix; the Before/After method and its numbers; fallbacks.
- Part B: the tests added, and the flaky test's root cause and fix.
- Part C: the profile tables, the changes made, hashes, and the proposals.
- Package size before and after, and the licence materials added.
- Changed files.
- Disk: dependency restore; package; evidence; other growth; `work\scratch` at the end; free space on C and D; anything left for the owner to delete.
- "Questions for the designer", each with the default you chose.
- A short owner-check list (about 10 steps, plain English) for trying the player by hand. The designer will turn it into the owner check.

## 10. Designer review of the first run (2026-10-26) and what to do now

The first run, 2d996bc, is PARTIAL. **Accepted, do not redo:**
- the helper-process architecture;
- the IPC, the allowlist and the origin rules;
- the fallbacks;
- lazy loading and exit on close;
- the memory return after close;
- seek, reload and preview numbers;
- packaging, the lock file and licences;
- the Compare work in Part C, with its bit-identical hashes and P1e-3d proposals;
- the flaky retry test fix.

Do only the items below. Re-run only the checks they affect, plus the final lint, unit and e2e suites.

### 10.1 Cold start (target missed: 717-813 ms in the harness, 1,366 ms in one History click)

1. **Profile first.** Break one cold open into phases, five runs each:
   - process spawn;
   - window, D3D11 device and DComp creation;
   - WebView2 environment and composition-controller creation;
   - controls-page load;
   - DLL load and `mpv_initialize`;
   - file open to first rendered frame.
2. **Then shorten the critical path.**
   - Start the mpv open at helper start, in parallel with the WebView2 and page setup. The controls can attach when ready.
   - Show the poster in the player window at once, before mpv's first frame.
   - **Pre-warm:** you may start the helper with no file, hidden, when the pointer enters a History thumbnail or the detail view opens. A pre-warmed helper that is not used exits after 30 s.
   - Exit on close stays.
   - Report the idle cost of a pre-warmed helper (private bytes and GPU memory).
3. **Targets, measured from the real History click:**
   - poster visible ≤ 100 ms;
   - first frame, median of 5, ≤ 500 ms cold and ≤ 300 ms pre-warmed.

   Report the phase table before and after.

### 10.2 Before/After CPU (33.5 % at 720p, above 15 %)

The hstack needs copy-back decoding and CPU scaling. At real output sizes it will cost more. **Measure first, at real sizes:**
- an original 1080p30 against an enhanced 1440p60;
- an original 720p30 against an enhanced 1080p60.

Report CPU, GPU memory and dropped frames for 60 s.

If the hstack is above 15 % CPU at 1440p60, **implement the alternative and keep the better one:**
- two mpv instances in the same helper, each with zero-copy d3d11va;
- two composition visuals clipped at the divider, as now;
- the enhanced side is the clock master; the original follows it.
  - While paused or stepping, both sides show the same timestamp exactly, because both do an exact seek.
  - While playing, correct the original with small speed changes or a re-seek when its error passes one frame.

**Targets for the alternative:**
- paused or stepped: identical timestamp, every time;
- playing: drift median ≤ 1 output frame and worst ≤ 2 over 60 s, measured from the burned-in numbers;
- CPU ≤ 15 % at 1440p60;
- no drops.

The owner's design asks only for a split picture, so a drift of up to one frame while playing is acceptable. Report both methods' numbers and say which ships.

### 10.3 Visual and frame proof by self-capture (all NOT_RUN in the first run)

- **Computer Use is not needed and is not the method.** Capture only the player's own window with Windows.Graphics.Capture, as P1e-3b section 13 and P1e-3c1 did. Drive it only through its own IPC. This is the approved method, not a workaround. Never capture or send input to any other window.
- **Prove each of these from the captured pixels:**
  - transparent controls with no dark panel, and a black letterbox;
  - the preview sits above the bar with the time under it;
  - autohide after 2 s while playing, and controls visible while paused;
  - exact frame stepping against the burned-in numbers, 36 steps;
  - Before/After drift over 60 s;
  - divider input-to-picture latency (target ≤ 50 ms).
- **Mockup parity:** compare captures of the player with `design/player/player_mockup.html`. Render the mockup by capturing a Tauri/WebView2 test window that the test itself creates, which also counts as an own window. List the visible differences, and fix any that the mockup's design notes name as binding (section 2).
- Captures stay in `work\evidence`, never in Git.

### 10.4 The HTTP 400 in `test_cpu_queue_sse_controls_and_completed_output`

- Run that test 20 times on this branch, capturing the response body on failure.
- If it fails again, find the cause. If this cycle's changes caused it, fix them. If the test or the engine has an older race, report it with evidence; do not loosen the test.

### 10.5 Supervisor note (operator side, not yours)

The operator records that `work\ops\codex-supervisor.ps1` missed this cycle's usage limit, because the session's `rate_limits` record was null. Do not change the supervisor.

### 10.6 Report

- Rewrite `.ai/LAST_REPORT.md` for this run, with the 10.1-10.4 tables.
- Keep the first run's accepted results by reference to commit 2d996bc instead of repeating them.
- Update the Changed files list and the owner-check list.

### 10.7 CI: GitHub API rate limit in the link-tools setup step (added 2026-10-26 18:5x, after round 2 started)

On a04bcf0, Windows CI failed in "Prepare verified optional tools for local media tests". `scripts/prepare_link_test_tools.py` calls `https://api.github.com/repos/.../releases/latest` with no token. The hosted runner's shared IP hit the anonymous limit: `HTTP Error 403: rate limit exceeded`. The same commit's first attempt failed earlier, in `packaged.spec.ts` ("Tauri CDP attachment failed"). That spec passed on 2d996bc.

- Make the CI setup authenticated:
  - in `ci.yml`, pass `GITHUB_TOKEN: ${{ github.token }}` to that step only;
  - in `scripts/prepare_link_test_tools.py`, send `Authorization: Bearer <token>` to `api.github.com` only, and only when the variable is set.
- **Do not** change the product's own update check in `link_tools.py`. The app must never read `GITHUB_TOKEN`. If the request needs a seam to add a header, add a narrow one and test that the product path sends no `Authorization` header.
- `packaged.spec.ts` CDP attach: if you can reproduce a failure locally, find the cause. If you cannot, add the startup-diagnostics output the spec already collects to the CI failure artifact, so the next failure can be diagnosed. Do not add retries that hide it.

## 11. Designer review of run 2 (2026-10-26) and the last round

Run 2, 0fd7293, is PARTIAL. **Accepted, do not redo:**
- startup: cold 463 ms and pre-warmed 190 ms, from real History clicks;
- the two-decoder Before/After;
  - its drift: median 0, worst 2;
  - its 36/36 steps;
  - no pause on divider moves;
- the own-window visual proofs;
- 10.4;
- 10.7.

### 11.1 Target decisions (designer)

- **Before/After CPU:** the target is now **≤ 25 %** of one core at 1440p60. Two hardware decoders plus the follower measured 20.7 % of one core, which passes. Report the PC's logical core count once, so the share of the whole CPU is known. No more work.
- **Cold poster:** the target is now a **median of 5 ≤ 100 ms**. The run measured 70.1 ms, which passes. The first-ever open (165.8 ms, which includes a cold thumbnail fetch) is reported and accepted.
- **Divider latency:** the WGC readback stalls the render thread, so it cannot measure this. **Measure it instead without capture:** use QPC timestamps from the input event in the page, through the IPC receipt in the helper, to the DComp `Commit` that carries the new clip, plus the next `GetFrameStatistics` present time.
  - **Target:** median ≤ 34 ms (two 60 Hz frames) and worst ≤ 50 ms, over 20 moves while playing.
  - Keep the WGC numbers as an upper bound in the report.
  - If the target is missed, find which hop is slow and fix it. A likely cause is position messages queued behind 10 Hz position updates, or the WebView2 message pump.

### 11.2 Match the approved mockup's layout (the main item)

The owner approved the mockup's look, not only its behaviour. Run 2 lists differences that this round must remove:
- **two control rows with icons,** as in the mockup:
  - the seek bar on its own row;
  - a row of icon buttons below it, using the mockup's SVG icons, not text buttons;
- the **large play/pause button** in the mockup's accent style;
- the separate **10-second back/forward buttons**;
- the mockup's **slider spacing and preview size**;
- the Before/After row (`xrow`): the split slider, its labels and the zoom chip, laid out as in the mockup;
- the title row with the round close button.

**How to work:**
- Use `design/player/player_mockup.html` as the source of CSS values, icons and structure. Copy what fits, rather than re-drawing it.
- Its demo toolbar (theme, sample shape, status chip) is not product UI; leave it out.
- Keep every behaviour and every accessible name already built.
- The native window frame may stay. Report it if the mockup's frameless title row would need more work.

**Prove it** with own-window captures of the product next to the mockup:
- 16:9 and 9:16;
- playing, paused and hover states;
- Before/After on.

List any difference that remains, and why.

### 11.3 Report and status

- Rewrite `.ai/LAST_REPORT.md` for run 3. Keep the accepted results by reference to 2d996bc and 0fd7293.
- Set **COMPLETED** only if all of these pass: the 11.1 divider measurement, 11.2 with its captures, the final lint/unit/e2e suites, and the package build.
- Update the owner-check list.

### 11.4 CI: `test_cancelled_transfer_resumes_partial_file[cancel]` fails on Windows (added after round 3 started)

On 0fd7293, and on c3e712c (same code), Windows CI fails in the "Local synthetic link media acceptance" step:

```text
tests/test_link_download.py:365: assert partials and partials[0].stat().st_size > 0
AssertionError: ... .ve-<id>.mp4.part ... st_size=0
```

It failed twice in a row on the same code. That is a real failure, not a flake. On 2d996bc this step passed. On a04bcf0 the step never ran, because the 403 stopped the setup step before it. A possible cause, **unverified**: the setup now downloads whatever yt-dlp/deno release is `latest` at run time, and a newer release may handle cancellation or the `.part` file differently. Also check whether this PR's own changes touch the download path.

- Reproduce it on the PC. Record the yt-dlp and deno versions CI installed (the setup step prints `status()`) and the ones the PC uses.
- Find the root cause and fix it in the code at fault. If the product's resume of a partial file really broke with a new tool release, fix the product, because users get the same release. **Do not** loosen or skip the assertion.
- If the cause is in the test's assumption (for example, the size is checked before the tool flushes), make the test deterministic without weakening what it proves: a cancelled transfer keeps a non-empty partial file, and the next attempt resumes it.
