# CURRENT_TASK: Cycle P1t (replace Electron with Tauri)

- **Task ID:** VE-P1t
- **Date:** 2026-10-16
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:**
- Work in `D:\my-workspace\VideoEnhancer\work\repo` and follow `docs/WORKSPACE.md` (one package, scratch emptied, evidence at most 300 MB, cache cap 40 GB, disk table in the report).
- Create branch `p1t-tauri` from `p1d-ui-v2` at `40755c0`. PR #5 (`p1d-ui-v2`) is still a draft and is not merged: the owner checks P1e-2, this cycle and the next one (P1f, video links) together, and merges afterwards.
- Save this file as `.ai/CURRENT_TASK.md` and commit it. Open a draft PR from `p1t-tauri` to base `p1d-ui-v2`. Do not push to `main` or `p1d-ui-v2`.
- At the end, write `.ai/LAST_REPORT.md` (English, UTF-8 written once, ASCII punctuation, under 40 KB), and update it after the final CI run.
- Do not build any video-link feature in this cycle. That is P1f, which starts from this branch.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option, and continue. Exception: A2 below (a missing system build tool) is a stop.
2. Order: Part A → Part T → Part M → Part D → Part U → Part S → Part X → Part G. Part A's numbers must be measured before Electron is removed.
3. Never report a test as passed if it did not run. Report every run of a gated measurement.
4. **The owner's data is not test data.** Never launch any build against the owner's real app data:
   - the owner's app data is now `D:\my-workspace\VideoEnhancer\AppData` (moved with Settings › Storage › Move in the Electron app); the old copy `%LOCALAPPDATA%\VideoEnhancer` (about 2 GB) still exists;
   - every launch, test and smoke test uses an isolated `VE_HOME` under `work\scratch`, and an isolated `%APPDATA%`/`%LOCALAPPDATA%` override where the test covers start-up location logic (Part U, Part S);
   - read-only checks of the owner's real files are allowed only where this file says so (U1, A3a codec packages), and the report must not contain the owner's file names.
5. `VE-check\` and `AppData\` beside `work\` belong to the owner. Never write, move, clean or open them.
6. **Deleting your own files:** first try the delete inside `work\` without asking for approval. If the auto-approval still refuses, do not work around it: list at most 3 folders with sizes under "For the owner to delete".
7. Do not change system or user settings: no system or user environment variables, no registry changes outside an isolated test value, no driver or Recycle Bin settings. Environment variables for one session or one command are fine.

## 0. Goal and decisions

**Owner decision (2026-10-16):** replace Electron with Tauri 2 now, before the owner's check.

**What should get better:** the size of the desktop app. The Electron package is about 0.43 GB per copy (`P1e-2b` report: `package` was 0.86 GB with two copies). A Tauri shell is expected to be tens of MB (inferred, not measured).

**What is not expected to change:** processing speed (the GPU engine is untouched) and, roughly, memory (WebView2 is also Chromium). Measure both in Part A and Part G. Do not claim gains that were not measured.

**Designer decisions:**
1. **Tauri 2, latest stable at the start of the cycle.** It was 2.12.3 on 2026-10-10. Pin exact versions of every crate and npm package. Use Rust stable at or above Tauri's minimum (1.90 for 2.12).
2. **The renderer stays.** React, Vite and TypeScript, every screen and every UI string stay as they are, except the title bar (decision 4).
   - The only seam is the `window.desktop` interface (`gui/src/types.ts`, today implemented by `gui/electron/preload.cjs`). Keep its shape and implement it with `@tauri-apps/api` in one module.
   - Screen components must not import `@tauri-apps/*` directly.
3. **The Python engine and its HTTP API stay.** The only engine change is the allowed `Origin` (T18), plus the Part S fixes in `storage.py`. Keep the localhost, token and Host checks.
4. **Title bar:** use the native Windows title bar (window decorations on), coloured to the app theme with DWM (`DWMWA_CAPTION_COLOR` and `DWMWA_TEXT_COLOR`; this needs Windows 11, which the app already requires).
   - Colours as today: dark `#1C1814` with text `#DCCFBD`, light `#F5EFE6` with text `#574A3F`. They follow the theme setting live.
   - Remove the HTML `.title-bar` strip and its 138 px reserve. The app content starts at the top of the client area.
   - Snap Layouts (hover on maximize) must work.
   - Only if DWM colouring fails, use a frameless window instead, and report why.
5. **Drag and drop:** native Tauri file drops (they give absolute paths). On Windows, native file drops disable HTML5 drag and drop inside the page, so queue reordering moves to pointer events (D2). Dropping links from a browser is not needed (P1f uses paste and a link field).
6. **Video playback** goes through a custom protocol in the shell that forwards Range requests to the engine (Part M).
7. **Storage findings 1 to 9** from the P1e-2b review are fixed here (Part S), because the Electron code they live in is being rewritten.
8. **Package:** an unsigned, portable folder as today, with no installer and no updater. Build with `tauri build --no-bundle` or equivalent.
9. **Remove Electron completely** at the end: dependencies, `gui/electron`, scripts, Playwright `_electron` use, CI steps, `ELECTRON_CACHE` in the workspace rules, and the Electron caches you created in `work\cache`. Do this only after Part G passes on Tauri.

## Part A: baseline and feasibility (do first)

### A1. Electron baseline

Measure with the current package (`work\package\VideoEnhancer-win32-x64`) on an isolated home that holds the existing 1,000-item History fixture. Save JSON in `evidence\P1t\`.
- Package size on disk: bytes and file count.
- Cold start: from process start to the first paint of Home with data, median of 5 launches (each after all app processes have exited).
- Idle memory after 5 minutes on Home: private working set summed over the app's own processes (all `VideoEnhancer.exe` processes). Report the Python engine separately; it is the same in both shells.
- The existing perf suites (`gui/tests/perf/renderer.spec.ts`, `real-progress.spec.ts`) with their current budgets.

### A2. Toolchain (stop if a system tool is missing)

- Check for the MSVC build tools and a Windows SDK (`vswhere`), and the WebView2 Runtime version.
- Install Rust with `rustup` into `work\cache` (`RUSTUP_HOME`, `CARGO_HOME` set for the session only). Put `CARGO_TARGET_DIR` under `work\cache` too.
- **If the MSVC build tools are missing, stop the cycle here** and report the exact steps for the owner (which installer, which workload, roughly how much space on which drive). Installing system software is the owner's job.

### A3. Feasibility spike

A throwaway, minimal Tauri 2 window in `work\scratch` (not committed). Report each result before porting.
- **a. Playback codecs.** Encode short clips with the engine's own encoder: HEVC Main10 (the default output), H.264 and AV1, at 1080 and 2160.
  - In the WebView2 page, report `MediaSource.isTypeSupported` and `canPlayType` with the exact codec strings of those files, and whether each file plays and seeks.
  - Read-only, report which Microsoft Store codec packages are installed (`Get-AppxPackage *HEVC*`, `*AV1*`, `*VP9*`).
  - Expect a risk here: Microsoft documents that Edge (and so WebView2, inferred) needs the HEVC Video Extensions for HEVC, while Electron decodes HEVC itself. If HEVC does not play, continue and build M4.
  - Also report the codec of the engine's Compare previews (`previews/<op>/<name>-preview.mp4`).
- **b. Range proxy:** play and seek a file of at least 2 GB through a custom protocol, as in Part M. Report play start, seek time and the shell's memory.
- **c. Test harness:** Playwright `chromium.connectOverCDP` attaches to the Tauri window (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<port>`, with a separate `WEBVIEW2_USER_DATA_FOLDER` per test).
- **d. File drops** give absolute paths for 1 file and 50 files, including non-ASCII names and paths longer than 200 characters.
- **e. Title bar:** DWM caption colours apply, and the Snap Layouts flyout appears on the maximize button.

## Part T: the Tauri shell, with feature parity

Layout: `gui/src-tauri/` (standard Tauri layout). Keep the Rust code split by concern (engine process, storage, media protocol, tray and window, commands).

Every row below must behave as the Electron app does today (`gui/electron/main.cjs`, `preload.cjs`, `storage.cjs`, `python.cjs`, `permissions.cjs`). The report lists every row with its evidence: a test name, or a screenshot for visual rows.

| # | Feature | Required behaviour |
|---|---|---|
| T1 | Single instance | A second launch focuses the existing window and exits. |
| T2 | Window | 1280x800 client area at first launch, minimum 1100x700 client area. Start hidden and show after the first paint, with the theme background colour, so there is no white flash. `--hidden` starts in the tray. |
| T3 | Close to tray | Closing hides the window. The first time, the renderer shows the existing tray explanation (`onTrayExplanation`), and its button calls `hide`, which saves `tray_explained`. |
| T4 | Tray | Icon with tooltip "VideoEnhancer". Menu: Open VideoEnhancer, Pause processing / Resume processing (from `health.paused_all`, refreshed every 3 s as today), separator, Quit. Double-click opens. |
| T5 | Quit | Graceful: call `shutdown`, wait up to 20 s for the engine's PID to exit, then quit. On failure, show the window and "The engine could not stop cleanly. Retry Quit." as today. |
| T6 | Engine start | Same logic as `startService`: reuse a healthy `serve.json`; otherwise start `pythonw.exe` (fall back to `python.exe`) with `-m videoenhancer.cli serve`, hidden and detached, with `VE_HOME`; append to `service-start.log`; wait up to 30 s for `health`. `VE_PYTHON` and `VE_ENGINE_ROOT` overrides; `engine-location.json` beside the packaged exe. |
| T7 | Start with Windows | Synced from the `start_with_windows` setting, starting with `--hidden`. See U4 for the old Electron entry. |
| T8 | Zoom | Levels 80, 90, 100, 110, 125, 150. Ctrl + / - / 0 and the numpad keys step through them, save `zoom` to settings, and emit `zoom-changed`. WebView2's own zoom (Ctrl+wheel on the page, browser shortcuts, pinch on the page) must never change the page scale. |
| T9 | Theme | system / dark / light, applied to the window background and the title bar colours (decision 4), live. |
| T10 | Dialogs | Open videos (multiple, filter mp4 mkv mov avi webm m4v), open folder, error boxes, and the start-up "The app data folder was not found" dialog with Choose…, Use the previous folder and Quit. |
| T11 | Files | `openFolder`, `reveal`, `play` (default app), with today's validation: absolute path, exists, no NUL. |
| T12 | Clipboard | `copy`, at most 100,000 characters. |
| T13 | External links | Only today's allowlist opens in the default browser: `https://github.com/Kei-Takamizawa/VideoEnhancer/blob/main/docs/...`, `.../pull/...`, and the built-in models' `publisher_url`s. Everything else is denied. The page can never navigate away from the app or open a new window. |
| T14 | Renderer errors | `logRendererError` appends to `renderer-errors.log` in the home, at most 64,000 characters per entry. |
| T15 | Reload, restart engine | As today. |
| T16 | Player fullscreen | The fullscreen button and the video's own fullscreen fill the whole monitor (the window goes fullscreen), Esc and the button leave, and the window returns to its previous size and position (P1e-2 fixed this in Electron). |
| T17 | Content Security Policy | As strict as today: no remote scripts, styles only from the app, `connect-src` only to the engine on `127.0.0.1` plus what Tauri's IPC needs, media only from the media protocol and `blob:`, no frames, no objects. Dev mode may add the Vite server. DevTools are off in release builds. |
| T18 | Engine origin | The engine's `APP_ORIGIN` (`server.py`) becomes the exact origin the Tauri webview sends (expected `http://tauri.localhost`; verify it). Keep the dev origin, the token, the Host check and the `Sec-Fetch-Site` rule. Remove `app://videoenhancer` once nothing uses it. |
| T19 | IPC security | Tauri capabilities grant commands only to the main window and only for the app's own origin. Grant no file system, shell or HTTP plugin scope to the renderer. Validate every command's arguments as `main.cjs` does today. |
| T20 | Non-Windows | The shell shows "The desktop app requires Windows 11." and quits, as today. |
| T21 | Storage commands | `storageStatus`, `moveStorage`, `removeOldStorage` with the same flow as today, plus the Part S fixes. |
| T22 | Browser behaviour | No browser context menu anywhere (no Back, Reload, Print, Save as, Inspect). Text fields keep Cut, Copy, Paste and Select all. Browser accelerator keys are off (reload, find, print, DevTools, back and forward). |

## Part M: video playback

**M1. Media protocol.**
- A custom scheme handled in Rust replaces `app://videoenhancer/media/<job id>`. Update `HistoryDetail.tsx` and any other user of that URL.
- GET and HEAD only. Validate the job id. Forward the `Range` header to `GET /v1/queue/<id>/video` with the token, and return 200 or 206 with correct `Content-Range`, `Content-Length`, `Content-Type` and `Accept-Ranges`.
- **Never buffer a whole file.** Answer an open or large range with at most 8 MiB per response and a matching `Content-Range`; the media stack asks for the rest. Abort the engine request when the webview cancels.

**M2. Gates** on a 2160p output of at least 2 GB, in a codec that plays (A3a), median of 10:
- play start at most 0.5 s;
- seek at most 0.3 s;
- the shell's private memory grows by at most 100 MB during 2 minutes of playback with 20 seeks.

For reference, the Electron app measured 0.32 s and 0.12 s in P1e-2.

**M3. Only if M1 cannot meet M2:** try a short-lived, read-only, per-job URL issued by the engine and loaded straight from `127.0.0.1`.
- Use a random 128-bit value that expires after 10 minutes and serves only that one job's video.
- Report both designs' numbers and the security trade-off under "Questions for the designer". Do not ship M3 if M1 passes.

**M4. When HEVC does not play** (from A3a, checked again at start-up with the exact codec string of the app's HEVC output):
- The player says: "This PC can't play HEVC videos inside the app. Install HEVC Video Extensions from the Microsoft Store, or open the video in your default player." It offers "Open Microsoft Store" (the HEVC Video Extensions page, through the opener with an allowlisted `ms-windows-store:` link) and "Open in default player".
- In Add, the HEVC codec choice shows "Needs HEVC Video Extensions to play inside the app".
- **Do not change the default output codec.** That is an owner decision; ask under "Questions for the designer", with the A3a facts.

## Part D: input

- **D1. File drops.** Use native drag-and-drop events.
  - The existing overlay "Drop to add N videos" takes N from the entering paths.
  - A drop adds exactly as today: same filters, messages and Add flow.
  - Remove the HTML5 file-drop code and `filePath` (`webUtils`).
- **D2. Queue reordering** keeps today's look and behaviour, rebuilt with pointer events, because HTML5 drag and drop does not work on Windows while native drops are on.
  - Keep keyboard reordering (Arrow keys, `Home.tsx`).
  - Add a test that reorders by pointer and by keyboard.
- **D3. Touchpad pinch and Ctrl+wheel in Compare** zoom the video exactly as the P1e-2 build does (P1e-2 O5), never the page.

## Part U: moving the owner's PC from Electron to Tauri

**Background:**
- The owner moved the app data with the Electron app's Storage › Move to `D:\my-workspace\VideoEnhancer\AppData`.
- The engine reads the pointer from `%APPDATA%\VideoEnhancer\storage-location.json` (`config.py`).
- The Electron shell wrote it to its `userData` folder. That may be the same folder or `%APPDATA%\videoenhancer-desktop` (P1e-2b review finding 4, inferred).
- **The danger:** if the new shell misses the pointer, it silently starts on the old `%LOCALAPPDATA%\VideoEnhancer`, shows old History and settings, and splits new jobs from the real data.

**Do:**
- **U1. Find the pointer** on the owner's PC, read-only: check both folders above for `storage-location.json`, and report which exist and whether `active` points to a folder that exists. Do not report other contents.
- **U2. One pointer file:** `%APPDATA%\VideoEnhancer\storage-location.json`, shared by the shell and the engine (this fixes finding 4, so CLI runs follow a move too).
  - At start-up, if it is missing but the Electron pointer exists in the other folder, copy it with an atomic write and log that.
  - If any pointer exists but its `active` folder is missing, show the "not found" dialog (T10). Never fall back to the default folder silently.
- **U3. Test U2** with isolated `%APPDATA%` and `%LOCALAPPDATA%`:
  - the Electron pointer in each possible folder;
  - a stale default folder holding different History.

  Assert that the app opens the pointer's folder with the expected History count. The owner checks the real PC.
- **U4. Start with Windows.** If the setting is on, register the Tauri app (`--hidden`) and remove the old Electron entry, but only an entry whose command points to the old Electron package's `VideoEnhancer.exe`.
  - Unit-test this with a fake registry or an isolated test value.
  - Do not change the owner's real `Run` key during development.
- **U5. Leftovers.** Read-only, list Electron's own leftover profile folders on the owner's PC (cache and similar) with sizes, as at most 3 items under "For the owner to delete later".
  - Never list or touch the pointer file, the app data, or `%LOCALAPPDATA%\VideoEnhancer`.
  - The old Electron package is replaced under the one-package rule once the Tauri package passes its smoke test.

## Part S: Storage fixes (P1e-2b review, 2026-10-16)

| # | Finding | Fix |
|---|---|---|
| S1 | "Remove the old folder" does not check that the new folder exists and works, and has no confirmation (finding 1). | Enable it only when: the running engine reports the same home as the pointer's `active`; that folder exists and is writable; and every file in the move manifest exists there with the recorded size. Then show a confirmation dialog: "Remove the old app data folder? `<path>` · `<N>` files · `<size>`. This permanently deletes the app's old copy. Your videos are not in this folder." with Remove and Cancel (Cancel is the default). |
| S2 | It deletes the whole folder recursively (finding 2). | Keep a manifest of the move: relative path, size, and SHA-256 where hashed. Delete only the old files that are in it and still match its size (and hash where recorded). Then remove the folders that became empty. Never follow links. Refuse a drive root, the active folder, or any folder that contains it. Result: "Removed X files (Y GB). Kept Z files that were not part of the move." with the folder. |
| S3 | Move works while `VE_HOME` is set, and the next start then ignores the move (finding 3). | When `VE_HOME` is set, disable Move and Remove with "App data is set by VE_HOME. Unset it to use Move." |
| S4 | The shell's and the engine's pointer locations may differ (finding 4). | U2. |
| S5 | One torn or invalid JSON or JSONL line stops the whole move (finding 5). | Copy every file's bytes first. Rebase paths only in lines and files that parse; keep the rest byte-for-byte. The move succeeds, and its result lists how many damaged records were copied unchanged and in which files. Never drop a record. |
| S6 | A failure during `storage/prepare` leaves "App data is moving" until a restart (finding 6). | Any failure before the copy starts resets the moving state and resumes normal operation without a restart. Add a test. |
| S7 | Opening Storage during processing can fail when temporary files vanish (finding 7). | The status scan skips files that vanish or are locked during the scan. Add a test with concurrent file churn. |
| S8 | The Clean up list shows internal job ids (finding 8). | Show the video's file name, the state, the date and the size. Show the id only in details or a tooltip. |
| S9 | No end-to-end test of the real restart path (finding 9). | Without `VE_HOME`, in isolated `%APPDATA%` and `%LOCALAPPDATA%`: Move → Quit → relaunch uses the new folder with History intact → Remove the old folder through the dialog → relaunch is still fine. Also cover the missing-folder dialog at start-up. |

## Part X: tests and CI

- **X1. New end-to-end harness.** Build the app once per run, launch it per test with an isolated home and WebView2 data folder, and connect Playwright over CDP.
  - Replace every `app.evaluate` (Electron main process) with renderer-level checks or test-only commands.
  - Test-only commands are compiled only with a cargo feature (for example `e2e`) for dialog stubs and window queries. The owner's package is built without it, and a test proves those commands are absent from the release build.
- **X2. Port every existing end-to-end spec** (12 files in `gui/tests/e2e`, including the GPU-marked ones) and both perf suites. The report maps each old test to its new test. None is dropped silently.
- **X3. Rust:** `cargo fmt --check`, `cargo clippy -- -D warnings`, and `cargo test`. Cover at least: pointer migration, storage manifest deletion rules, the engine start and `serve.json` parsing, the Range math, the link allowlist, and argument validation.
- **X4. Frontend unit tests** keep running under Vitest, with `window.desktop` mocked as today or with `@tauri-apps/api/mocks`.
- **X5. CI:**
  - The Windows job adds the Rust toolchain (cached), the Rust checks, a Tauri build and the CDP end-to-end tests.
  - The Ubuntu job keeps the Python checks and the frontend lint, typecheck, unit tests and build. It does not need to build the Windows-only shell.
  - Both must be green on the final commit.

## Part G: acceptance

- **G1. Before and after**, Electron (A1) against Tauri, on the same PC and fixture:

  | Measure | Gate |
  |---|---|
  | Package size | Tauri shell at most 50 MB, without the engine checkout. Report both numbers. |
  | Cold start, median of 5 | Not more than 10% slower than Electron |
  | Idle memory after 5 min | Report only. Sum the app's own processes, including the `msedgewebview2.exe` processes that belong to it, and say how you attributed them. |
  | Perf suites | All existing budgets pass |
  | Media | M2 |

- **G2.** Every row of the Part T table with evidence.
- **G3.** The codec table from A3a, and M4 if HEVC does not play.
- **G4.** Part S: tests S1 to S9.
- **G5.** Part U: the U1 finding and tests U2 to U4.
- **G6. Screenshots** at 1280x800 and 1100x700, in dark and light:
  - Home with a queue;
  - Add;
  - History and the player, including fullscreen;
  - Compare;
  - Models;
  - Schedule;
  - Settings with the Storage card and the remove confirmation.

  Compare them with the last Electron screenshots (`work\evidence\P1e-2`) and list every visible difference other than the title bar. Store them outside the repository.
- **G7.** All GPU-marked tests. The default pipeline output must not change: strict equality, as before.
- **G8.** `ruff`, `ruff format --check`, `pyright`, CPU tests, the Rust checks, and GUI lint, typecheck, unit tests, build, end-to-end and package. Windows and Ubuntu CI green on the final commit.
- **G9. Package for the owner's check:**
  - `work\package\VideoEnhancer\` with `VideoEnhancer.exe` and `engine-location.json` (give the exact path);
  - smoke-tested with an isolated home;
  - then the old Electron package removed under the one-package rule.
- **G10. The disk table.** The Rust toolchain and build cache are a one-time bootstrap exception to the 1 GB gate: report their sizes. Keep `CARGO_TARGET_DIR` within the 40 GB cache cap, and say how you limit it.

## Constraints

- Windows 11, no WSL. All code, comments, UI text and docs are in English.
- **Never commit:**
  - media, weights, packages, screenshots or previews;
  - `node_modules`, `target` or other build output;
  - `local-env.ps1`;
  - the owner's logs, paths or private names.
- **New dependencies:** open-source licences only. Name every crate, Tauri plugin and npm package added, with its licence, in the report.
- No telemetry, no auto-update, no update checks. The shell makes no network access except to the local engine.
- **User videos are never deleted permanently.** Only the deletion module may remove them, and only to the Recycle Bin, behind the guard. Part S deletes only the app's own old data, as specified.
- The default pipeline output must not change.
- **Update the docs:** `docs/ARCHITECTURE.md`, `docs/GUI.md`, `docs/DEVELOPMENT.md`, `docs/API.md` (origin), `docs/TROUBLESHOOTING.md` (WebView2 missing, HEVC playback) and `docs/WORKSPACE.md` (Rust paths and package layout). `README.md` does not mention Electron; change it only if something it says becomes untrue.

## Report (`.ai/LAST_REPORT.md`)

- A table per part (A, T, M, D, U, S, X, G): done / partial / NOT RUN / BLOCKED, with evidence.
- The A1 and G1 numbers side by side.
- The A3 feasibility results, including the codec table.
- The Part T parity table with evidence per row.
- The old-to-new test map (X2).
- Dependencies with licences.
- The disk table, and "For the owner to delete" if anything was refused.
- The package path for the owner's check.
- "Questions for the designer", each with the default you chose.
- Exact reproduction steps.

Never report a test as passed if it did not run.
