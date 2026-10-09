# CURRENT_TASK: Cycle P1c (redesigned GUI, reliable queue, no console windows, model catalog and compare)

- **Task ID:** VE-P1c
- **Date:** 2026-10-09
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** the owner has merged PR #3 (`p1b-gui`) into `main`. Create a new branch `p1c-redesign` from the latest `main` and open a **draft** PR. Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Do not push to `main`.

**Work order:** Part S (jobs that never start or stay at 0%) → Part W (no console windows) → Part U (redesigned GUI) → Part M (model catalog) → Part C (compare models). If time runs out, finish earlier parts completely and mark the rest NOT RUN. Do not start Part U before S and W pass their tests.

## 0. Facts from P1a and P1b (already in `main`)

- Presets: `standard` = BasicVSR++ NTIRE21 decompression (clip 15 / overlap 2, Torch peak about 4.4 GB) + RIFE 4.25; `fast` = resize + RIFE. On the owner's RTX 4060 Ti 8 GB: `standard` about 2.35 input fps, `fast` about 15.7 input fps.
- Jobs are split into segments of about 3 minutes of predicted work (at most 60 s of source); each segment runs in a new child process (`ProcessExecutor`, multiprocessing spawn). The estimator includes finalization; jobs report `phase` (`processing` / `finalizing`), `step`, and progress capped at 99.9%.
- `ve serve`: stdlib HTTP on 127.0.0.1, random port, bearer token in user-private `serve.json`, Host/Origin checks, SSE `events` with a 10 s heartbeat, one instance per `VE_HOME`. API is documented in `docs/API.md`.
- GUI: Electron + React + TypeScript + Vite in `gui/` (pages Queue, Plan, Schedule, Models, Settings, Trial viewer with a WebCodecs frame clock), tray, detached engine started by `gui/electron/main.cjs`.
- Model registry: JSON manifests in `src/videoenhancer/models/manifests/`, adapters `basicvsrpp`, `rife`, `spandrel`; `ve models list/add/remove`; consent-recorded download of built-ins.

## 1. Why this cycle (owner feedback after the P1b manual check, 2026-10-09)

The P1b checklist passed, but the owner reported:

1. The screens look dated and are hard to read. They want a smart, minimal, modern UI where the main task is immediate, the main things are big, finished work moves to a **History** instead of staying in the queue, and the **Schedule** is modern and easy to read. The owner approved a new design (described completely in Part U).
2. Some videos added to the queue, and some added as Trial, never start. Some finish normally; others show "Running" but stay at 0% forever.
3. More models should be available, installed optionally, each with an easy description of its character, and the owner wants to process a short piece of a video with several models and see the differences side by side.
4. Opening the GUI must not also open a console (command prompt) window.

## 2. Part S: jobs that never start or stay at 0%

### S0. Evidence first (read-only on the owner's PC)

Before changing code, collect evidence from the owner's engine home (`%LOCALAPPDATA%\VideoEnhancer` or `VE_HOME`) for every job or trial that stayed at 0% or never started. Collect: `jobs\<id>\job.jsonl`, `manifest.json`, `control.json`, a folder listing with sizes taken twice 60 s apart (is `seg_NNNNN.tmp.raw.hevc` growing?), `videoenhancer.jsonl`, `service-start.log`, `schedule.json`, `settings.json`, `previews\<op>\request.json`, `operation.log`, `result.json`, and `GET /v1/health` (`engine_state`, `last_error`). Classify each case against H1 to H5 below and report counts and timestamps. Never commit these files; in the report refer to jobs by id, not by file name, and remove private paths. If no stuck case is left on disk, write NOT FOUND and continue: all fixes below are required anyway.

Designer's code review of `936c99b` found these likely causes (line numbers are from that commit):

- **H1, no watchdog.** `ProcessExecutor` waits for the child with no deadline (`schedule/controller.py:288-306`) and keeps waiting for the child to exit after its result already arrived (291-295). A child that hangs (CUDA, NVDEC or NVML teardown, VRAM spill into shared memory, or an ffmpeg stderr pipe that is never read: `media/decode.py:186`, `media/encode.py:188`) leaves the job "Running" forever, and every later job and every trial waits behind it. The trial waiting text is computed once and never updated (`service/engine.py:406-417`).
- **H2, invisible controller errors retried forever.** `_worker` stores every exception in `last_error` (`service/engine.py:100-111`), nothing logs it and the GUI never shows it. Errors outside the executor (for example `PermissionError`/`OSError` from `validate_input`, which only catches `FileNotFoundError` and `ValueError` at `controller.py:643-651`; `os.replace` at 916 while antivirus holds the file; the 5 s manifest lock timeout in `jobs/store.py:29-49`) restart the controller every 0.5 s on the same head job, which resets and re-runs segment 1 forever.
- **H3, frozen view.** The SSE loop catches only `BrokenPipeError`/`ConnectionResetError` (`service/server.py:215-237`); any other exception writes an error response into the open stream and the stream goes silent. The client ignores heartbeats and never reconnects by itself (`gui/src/api.ts:46-60`, `gui/src/App.tsx:121-135`). Every request and every stream tick share `engine.lock`, and adding a video runs a whole-file analysis under it (`jobs/store.py:389`). Operations live only in memory (`service/engine.py:51`), so after a service restart the Trial dialog stays "waiting" forever (`gui/src/Trial.tsx:416, 488`).
- **H4, schedule starvation.** A unit is admitted only when `now + 1.1 × prediction + 30 s` fits before the window ends (`controller.py:801-809`; finalization 667-680). A unit longer than the whole window is never admitted, and only the head job is considered (`controller.py:635`), so every job behind it starves while the status shows "Idle". Each wait also appends an event to the manifest (up to every 2 s).
- **H5, progress only per segment.** Progress counts completed segments only (`estimate/model.py:296-332`) and fps shows "—" until a segment ends, so a correct job shows 0% for about 3 minutes, plus model loading. A trial first analyses the whole file (`trial.py:56`).

### S1. Live progress and a segment watchdog

- The segment child reports progress to the controller at least every 2 s: frames done, current step (`Loading model`, `Processing`, `Encoding`), and memory. `GET queue` and SSE show percent, fps and ETA moving inside a segment (percent = processed frames of the whole job, still capped at 99.9%). The first visible change must appear within 30 s of the segment start, including model load. Write the manifest at most every 10 s for this.
- Watchdog per segment:
  - no new frame for `max(180 s, 20 × predicted seconds per frame)` after the first frame, or no first frame within 300 s of start → stalled;
  - wall time over `3 × predicted + 300 s` → stalled;
  - a stalled child's process tree is killed, the event is logged, and the segment is retried once in a fresh child. A second stall marks the job failed with: "Processing stopped responding at segment k of N. Retry, or use Copy details to report it."
  - after the child's result has arrived, it gets 15 s to exit; then its tree is killed and the result is kept (not a failure).
- Log memory samples (dedicated and shared GPU memory where Windows reports it, process RSS) every 30 s during a segment, not only at its end, so a stuck segment leaves evidence.
- Save each segment child's stdout and stderr to `jobs\<id>\logs\seg_NNNNN.log` (keep the last 1 MB). Copy details includes its last 40 lines.
- The heartbeat must not change any output: the CPU fixture output must be byte-identical before and after this change.

### S2. One bad job never blocks the others

- Every exception in the controller loop is logged with its traceback to the service log and, when it belongs to a job, to that job's log. `last_error` becomes `{time, job_id, message}` and is shown in the GUI (Part U).
- A job that raises a controller-level error twice in a row is marked failed with a plain-English message; the controller backs off (5 s, then 30 s) between attempts and moves on to the next job.
- `validate_input` maps `PermissionError`/`OSError` to a failed job with: "The file could not be opened. It may be in use, or in a cloud folder that is not downloaded to this PC."
- `os.replace` and the other finishing file operations retry on `PermissionError` (0.2, 0.5, 1, 2, 4 s) before failing.
- At service start, every job left in `running` is reset to `queued` (unfinished segment discarded as today), not only when it reaches the head.

### S3. The schedule never starves the queue

- If the head job's next unit cannot be admitted in the current window but another job's unit can, run the other job; otherwise keep the owner's order.
- A unit (segment or finalization) whose prediction is longer than the whole current window is admitted at the start of that window and may run past its end; the GUI says "Finishing one step after your hours, about N min".
- While waiting for allowed hours, `engine_state` is "Waiting for your hours" with the next start time, never "Idle".
- Write a waiting event when the waiting reason changes, and at most once every 10 minutes while it stays the same.

### S4. Trials and compare renders start when the owner asks

- **Designer decision:** a trial or compare render is started by the owner at the PC, so it runs immediately even outside operating hours. It never runs at the same time as a segment: if a segment is running, the trial starts right after that segment ends (the queue pauses between segments for the trial and resumes after it). The waiting text is live: "Starts after the current step, about 1 min 20 s". Remove the "operating-window deadline" abort for trials.
- A trial analyses only its own time range (plus the margin scene detection needs), never the whole file: a 5 s trial on a 2 h file starts rendering within 30 s.
- Hard timeout: `max(10 min, 4 × predicted)`; then it is cancelled with a plain message.
- Operations are persisted (`previews\<op>\state.json`). After a service restart the GUI shows a lost operation as "Interrupted. Try again." and re-enables its start button.
- While a trial runs, the job that waits shows "Paused for a preview".

### S5. Live updates never freeze

- Snapshots are built without holding the mutation lock during slow work. Adding a video (analysis), estimates and thumbnails become background work: adding returns at once with the job in a `preparing` state, and the GUI shows "Preparing…". The lock is held only for short in-memory changes (target under 50 ms; log any hold over 500 ms).
- The SSE loop catches every exception, logs it, sends `event: error` with a short text, and keeps the stream open. It never writes an HTTP error response into an open stream.
- The client reconnects automatically when no event and no heartbeat arrived for 30 s (backoff 1, 2, 5, 10 s), shows a small "Reconnecting…" state, keeps the last snapshot, and also reconnects when the window is restored from the tray.

### S6. Pipes cannot deadlock

Every engine subprocess with a piped stderr drains it continuously in a thread into a bounded buffer (last 64 KB), used in error messages and the segment log.

### S7. Tests (CPU, no GPU, fake children and fake clock)

1. Child hangs before its result: killed by the watchdog, retried once, then the job fails; the next job still finishes.
2. Child hangs after sending its result: result kept, child killed after the grace period.
3. Progress percent moves during a segment while frames advance.
4. Controller-level `PermissionError` on job A (input and `os.replace`): A fails with the message after retries; job B finishes.
5. Finalization predicted longer than the whole window: admitted at the window start and finishes.
6. Head job not admissible, second job admissible: the second job runs.
7. Trial requested outside operating hours while idle: starts within 5 s. Trial requested while a fake segment runs: starts right after that segment.
8. Exception while building an SSE snapshot: the stream continues. Client reconnects after 30 s of silence (fake timers).
9. Service restart with a job in `running`: reset to `queued` at start.
10. Fake process writing more than 1 MB to stderr: no deadlock.

## 3. Part W: no console windows

- **W1 (Electron).** Start the service with `pythonw.exe` (the sibling of the configured `python.exe`; use `VE_PYTHON` as is when it already points to `pythonw.exe`; fall back to `python.exe` with `windowsHide: true` only if `pythonw.exe` is missing, and log that). Node's documentation states that a `detached` child on Windows gets its own console window, and the engine's own children then open new consoles; `pythonw.exe` has no console at all.
- **W2 (engine).** One small module (for example `videoenhancer/proc.py`) wraps `subprocess.run` and `subprocess.Popen` and adds `creationflags=subprocess.CREATE_NO_WINDOW` on Windows. Every engine subprocess (ffmpeg, ffprobe, nvidia-smi, PowerShell, icacls and others) goes through it. A test (or ruff banned-api) fails when `subprocess.run/Popen/call/check_output` is used anywhere else under `src/`.
- **W3 (segment children).** On Windows, when the parent is `pythonw.exe`, the multiprocessing spawn context uses `pythonw.exe` (`context.set_executable`). Child stdout and stderr go to the segment log (S1). `sys.stdout`/`sys.stderr` can be `None` under `pythonw.exe`; logging and any prints must handle that.
- **W4.** `ve` used from a terminal keeps its console output unchanged.

## 4. Part U: redesigned GUI

The owner approved the design canvas "VideoEnhancer UI Redesign" (screens Home, Add videos, History, Schedule, Models, Compare). You cannot open it, so this part is the complete specification. Replace the P1b look and layout; keep every P1b capability unless this part removes it. The wireframes below show structure; follow the tokens and the rules in the text for the exact look.

### U0. Design tokens

| Token | Dark (default) | Use |
| --- | --- | --- |
| ground | `#0E1014` | window background |
| surface-1 | `#161920` | cards |
| surface-2 | `#1D212A` | buttons, selected nav item, inputs |
| placeholder | `#232833` | thumbnails while loading |
| border | `#22262F` | card borders |
| border-strong | `#2A2F3A` | button and input borders |
| text | `#ECEEF2` | main text |
| text-2 | `#C9CED8` | descriptions |
| text-3 | `#A0A8B6` | meta and captions |
| accent | `#5EEAD4` | primary buttons, progress, focus ring; text on accent is `#0E1014` |
| success | `#7EE2B8` | "Finished" |
| warning | `#F5B84B` | "Needs attention" |
| danger | `#F28B82` | destructive confirmations only |

- Light theme (System/Dark/Light setting stays): same structure with ground `#F6F7F9`, surface-1 `#FFFFFF`, surface-2 `#EEF0F4`, borders `#DDE1E8`/`#CDD2DB`, text `#14171C`/`#3A414D`/`#5A6372`, accent `#0F766E` with white text. All text at WCAG AA (4.5:1; 3:1 at 24 px and larger).
- Font: `Segoe UI Variable Text`, `Segoe UI`, system-ui. Page title 28 px / 650. The current job's percent 64 px / 650 with tabular numbers; finish time 20 px / 650; card titles 17 px / 650; body 14 px; meta 12 to 13 px.
- Radius: cards 18 px (the Now processing card 24 px), buttons 10 px, chips and filter pills fully round. Spacing on a 4 px grid; page padding 28 px top, 36 px sides; gaps 16 to 22 px.
- No gradients, no shadows beyond a subtle one on dialogs, no decorative animation. Icons are simple 1.8 px stroke icons (one icon set, for example Lucide). No emoji.
- Focus: 2 px accent ring with 2 px offset on every interactive element. Touch targets at least 36 px high (44 px for the main buttons).

### U1. Shell

```
+------+------------------------------------------------------------------+
| [VE] |  page                                                            |
|      |                                                                  |
| Home |                                                                  |
| Hist.|                                                                  |
| Sched|                                                                  |
| Model|                                                                  |
|      |                                                                  |
|  ⚙   |                                                                  |
+------+------------------------------------------------------------------+
```

- Left rail 88 px wide with a right border: a 40 px "VE" tile in accent, then Home, History, Schedule, Models (22 px icon above a 12 px label; item 72 px wide, 12 px radius; current page = surface-2 background and text color, others text-3). Settings is a gear button at the bottom of the rail. Home shows a small warning dot when something needs attention.
- Removed: the Plan page (its content moves to Schedule and to Home's "This week") and the bottom status strip (its content moves to the Home header chip).
- Dropping files anywhere in the window shows an overlay "Drop to add N videos" and opens the Add dialog.
- Minimum window 1100×700. Under 1280 px wide, the right column of Home and Schedule moves below the main column. Works at 125% and 150% scaling.
- Tray, single instance, Quit and Start with Windows behave as in P1b.

### U2. Home (replaces Queue)

```
| Home  (● Working · 15.7 fps · pauses at 08:00)            [Pause all] [+ Add videos] |
| +--------------------------------------------------+  +------------------------------+ |
| | +------+  Now processing                         |  | This week          Edit hours | |
| | |      |  evening_talk.mp4                       |  | Thu ██████████░░░░░   10 h    | |
| | | 9:16 |  720 × 1280 · 30 fps · 1:52:03 ·        |  | Fri ████░░░░░░░░░░░   3.7 h   | |
| | | thumb|  Standard → 1080p · 60 fps              |  | Sat                   off     | |
| | |      |  62%                 Segment 14 of 23   |  | Sun                   free    | |
| | |      |  ██████████████████░░░░░░░░░░░          |  | Everything finishes Fri 10/10| |
| | |      |  Finishes Thu 10/09 · 02:10   Work left |  | · 03:40                      | |
| | +------+                              8 h 15 m   |  +------------------------------+ |
| |           [Pause] [Preview result] [⋯]           |  | Recently finished All history| |
| +--------------------------------------------------+  | [t] cafe_vlog.mp4       Open | |
| Up next          2 videos · all done Fri 10/10 · 03:40 | [t] dance_clip.mp4      Open | |
| ⋮⋮ [t] beach_walk.mp4      0:12:40 · Fast      Starts Thu 22:00  Done Thu 23:10  [⋯] | |
| ⋮⋮ [t] live_stream_p2.mp4  0:45:10 · Standard  Starts Thu 23:10  Done Fri 03:40  [⋯] | |
| [ +  Drop videos anywhere in this window, or click to add ]   (dashed border)          |
```

- **Header chip** (round, surface-1, colored dot): "Working · 15.7 fps · pauses at 08:00", "Waiting for your hours · starts Thu 22:00", "Paused", "Finishing evening_talk.mp4", "Paused for a preview", "Idle · nothing to do", "Reconnecting…", or "Problem · details" (warning color; opens the engine error with Copy details). **Pause all** toggles to **Resume all**. **Add videos** is the primary button.
- **Now processing card** (the running job, or the next job when waiting): thumbnail in the video's own orientation (150×266 portrait, 266×150 landscape) from a new endpoint that returns a cached JPEG of the source at 10% of its duration; file name; one meta line; the percent (64 px) and "Segment k of N"; a 10 px progress bar; "Finishes" with a concrete date and time and "Work left" with the remaining work time. During finalization: "Finishing: assembling / checking" with its own step progress. When waiting for hours: "Starts Thu 22:00" in place of the finish time. Buttons: Pause/Resume; **Preview result** (enabled after the first finished segment: opens the Compare viewer with Original and the result for 5 s that are already processed; it must not use the GPU or disturb the job; CPU transcode to H.264 previews is fine); ⋯ menu: Cancel (confirm), Show log, Copy details, Open output folder.
- **Up next**: compact rows (min height 56 px): drag handle and keyboard reorder (Alt+Up/Down and a menu item), small thumbnail, name, duration · mode, "Starts …", "Done …". Row ⋯ menu: Move to top, Pause/Resume, Try models on this video (Compare), Change mode (only before the job starts), Remove (confirm), Show log, Copy details. A paused row says "Paused". A preparing row says "Preparing…".
- **Finished, failed and cancelled jobs leave Home at once** and appear in History. When there are failures the owner has not seen, Home shows a warning banner: "1 video needs attention · Open History". When the engine reports an error (`last_error`), Home shows a banner in plain English with Copy details.
- **Right column:** "This week": one row per day for the next 5 days, a bar of planned working hours (from the engine plan) and the hours text ("10 h", "off", "free"), a summary line, and "Edit hours" (to Schedule). "Recently finished": the last 3 History items with Open (plays the file in the default player) and "All history".
- Empty state: "Nothing in the queue. Add a video to see when it will be ready." with the Add button.

### U3. Add videos dialog

```
| Add 2 videos                                                              [x] |
| (beach_walk.mp4 · 0:12:40)  (live_stream_part2.mp4 · 0:45:10)                 |
| Choose a mode                                                                 |
| +----------------------------------+  +----------------------------------+   |
| | Standard                         |  | Fast                             |   |
| | Cleans up blockiness and noise,  |  | Only makes motion smoother and   |   |
| | then makes motion smoother.      |  | resizes. No cleanup.             |   |
| | Keeps the original look.         |  |                                  |   |
| | About 7 h of work                |  | About 1 h of work                |   |
| | Done Fri 10/10 · 03:40           |  | Done Thu 10/09 · 23:10           |   |
| +----------------------------------+  +----------------------------------+   |
| Output: 1080p · 60 fps · HEVC · Saved next to the original, in "enhanced"  More options |
| [Try models first]                                              [Add to queue] |
```

- Opens on Add, drop, or a click on the drop area; one dialog for several files. The two mode cards are large buttons (selected = 2 px accent border, `aria-pressed`); the default comes from Settings. The done time is 20 px / 650.
- Estimates fill in as each file finishes preparing ("Preparing…" until then); the dialog never blocks. Warnings (HDR, disk space with exact numbers, Smart App Control) appear as one line each above the buttons.
- **More options** reveals: Size (1080 recommended / Keep original / 1440 / 2160), Frame rate (Double recommended / Keep original), Cleanup model (installed restoration models; default the preset's model), File format (HEVC / H.264 / AV1 when supported), Output folder.
- **Try models first** opens Compare for the first file with the dialog's settings; returning keeps the dialog state; "Use this" in Compare sets the dialog's Cleanup model.
- Enter = Add to queue. From a drop to a queued job is one click.

### U4. History

- Header "History" and a search field ("Search by file name"). Filter pills with counts: All, Standard, Fast, Needs attention.
- Card grid (cards at least 240 px wide): thumbnail of the output (72×128 portrait or 128×72 landscape), name, when it ended ("Today 06:42", "Yesterday 23:18", "Mon 10/06 04:55"), "Standard · took 3 h 05 m · 412 MB", and a status line: Finished (success color), "Needs attention: the file could not be read" (warning color, one line), Cancelled (text-3).
- Actions: Finished → Play, Show in folder. Needs attention → Retry (re-queues from the last valid segment), Copy details. ⋯ menu → Compare again, Show log, Remove from history (confirm; never deletes the output).
- Footnote: "Finished and failed jobs move here automatically. Removing an item from History never deletes the video file."
- Engine additions: `finished_at`, `took_seconds` (wall time), output size and the thumbnail for done/failed/cancelled jobs, and a Retry endpoint (failed → queued, keeping valid segments).

### U5. Schedule (replaces Schedule and Plan)

```
| Schedule   Everything finishes Fri 10/10 · 03:40   (could be Thu 23:10 – Fri 06:00)  [● Only work during my hours] |
| (Weeknights 22:00–08:00 + weekends) (Every night 22:00–08:00) (While I'm at work 09:00–18:00) (Custom…)          |
| +-------------------------------------------------------------------+  +---------------------------+ |
| |               00      06      12      18      24                   |  | Exceptions                | |
| | Thu 10/09 today [▓▓▓▓▓▓░░░            |now          ░░▓▓]   10 h   |  | Sat 10/11   Off all day   | |
| | Fri 10/10       [▓▓▓░░░░                            ░░░░]   3.7 h  |  | Wed 10/15   13:00–18:00   | |
| | Sat 10/11       [                                       ]   off    |  | [Add a day]               | |
| | Sun 10/12       [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   free   |  +---------------------------+ |
| | Mon 10/13       [░░░░░░░                            ░░░░]   free   |  | Need it sooner?           | |
| | Tue 10/14       [░░░░░░░                            ░░░░]   free   |  | Ignore your hours and keep| |
| | Wed 10/15       [                  ░░░░░░░░             ]   free   |  | working. Everything would | |
| | ░ Allowed hours (drag the edges to change)   ▓ Planned work   | Now |  | finish Thu 10/09 · 23:10. | |
| +-------------------------------------------------------------------+  | [Run now until the queue  | |
|                                                                        |  is done]                 | |
|                                                                        | [Run now until a time…]   | |
```

- Seven rows, starting today. Each row is a 24 h track (rounded, surface-2): allowed hours as translucent accent blocks (about 22% opacity), planned work as solid accent bars from the engine plan (hover or focus shows "evening_talk.mp4 62% → 100%, done 02:10"), and a vertical "now" line on today. The note on the right: planned hours, "free" (allowed, nothing planned) or "off".
- Editing: drag a block's edges in 15-minute steps with a live time label, drag its middle to move it, click an empty part of a track to add a 2 h block there, and remove a block with its × or the Delete key. Editing a weekday row changes that weekday's weekly rule (the row label shows "Every Thu" while editing); a block's menu offers "Only on Thu 10/09" to make it a date exception instead. Keyboard: arrow keys move a focused edge by 15 minutes.
- Quick choices replace the weekly rule (with Undo). **Custom…** opens the exact-time list editor from P1b.
- Changes save automatically 600 ms after the last edit, with a toast "Saved · Undo" for 8 s. Validation messages appear in plain English next to the block. The header finish time updates live while dragging (schedule preview, throttled).
- Switch off = always allowed; the tracks show full-day allowed blocks and the note "Working any time".
- Exceptions card: upcoming dates with "Off all day" or hours, edit and delete; **Add a day** opens a date picker with Off or hours.
- Need it sooner card: shows the finish time the override would give. Buttons: "Run now until the queue is done" (add an override value for the whole queue, for example `until='queue-complete'`) and "Run now until a time…" (time picker). With an active override the card shows "Working now until 18:00 · Stop".
- The header range "could be … – …" comes from the plan's best and worst scenarios.

### U6. Models and U7. Compare

See Part M and Part C. Both use the shell, tokens and card style above.

### U8. Settings (gear at the bottom of the rail)

Same content as the P1b Settings page in the new style, grouped as: Defaults (mode, size, frame rate, file format, output folder), App (Start with Windows, theme), Advanced (behind a disclosure), Diagnostics (Copy diagnostics, log folder with Open, Run speed calibration), About (version, licence notes including non-commercial models).

### U9. Words

English, short, no jargon on the main screens. Times are always concrete ("Done Thu 23:10", "8 h 15 m"), never only a percent. Use "mode" (Standard / Fast), "cleanup", "smoother motion", "your hours".

## 5. Part M: optional model catalog

### M1. What the catalog is

Built-in manifests gain a `catalog` block so the Models screen can describe each model in plain words. Every catalog model is optional: nothing downloads without the owner's consent, and the current defaults (BasicVSR++ NTIRE21 Track 3 for cleanup, RIFE 4.25 for motion, the non-learned resize for size) keep producing exactly what they produce today.

Suggested manifest additions (names are suggestions):

```json
"catalog": {
  "category": "cleanup",
  "title": "Gentle cleanup",
  "description": "Removes blockiness and smeared detail using neighbouring frames. Keeps faces and the filtered look as they are.",
  "look_change": "very_little",
  "invents_detail": "low",
  "flicker": "none",
  "default": true,
  "licence_plain": "Code free for any use; the weights' terms are not stated",
  "reference_speed": {"gpu": "RTX 4060 Ti 8GB", "input": "720x1280", "output": "1080x1920", "fps": 2.38, "peak_memory_gb": 4.7}
},
"weights": {"url": "...", "mirrors": ["..."], "sha256": "...", "bytes": 0}
```

- `category`: `cleanup` (1x restoration), `motion` (frame interpolation), `size` (learned enlarging before the final resize). `faces` is reserved for P2 and shown as a disabled tab "Faces · coming later".
- `look_change`: very_little / little / noticeable. `invents_detail`: low / medium / high (from the training type: fidelity-trained = low, perceptual or unknown losses = medium, GAN = high). `flicker`: none (video models) / possible (single-frame models).
- `reference_speed` and memory are **measured by you** on the owner's RTX 4060 Ti (720×1280 input, 1080×1920 output, the model in its real pipeline position). Never copy speeds from papers. After a compare on the owner's PC, the GUI shows the speed measured there.
- SHA-256 and size are computed by you from the downloaded file. Prefer the original publisher's URL; a mirror is allowed only if it serves a byte-identical file (same SHA-256).
- `licence` keeps the exact licence string; `licence_plain` is the short text for the card ("Free for any use", "Free with credit (CC BY 4.0)", "Personal use only (non-commercial)").

### M2. Catalog for this cycle

Only models that run on the existing adapters (`basicvsrpp`, `rife`, `spandrel`), plus one small wrapper for DRUNet. Models that need a new adapter (FTVSR, EDVR, FastDVDnet, IFRNet, EMA-VFI) are out of scope for P1c.

| Category | Card title | Model and weights (verify) | Licence | Character for the card | Look / invents detail / flicker |
| --- | --- | --- | --- | --- | --- |
| cleanup | **Gentle cleanup** (default, already installed) | BasicVSR++ NTIRE21 decompression Track 3 (`basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth`) | Apache-2.0 code; weights' terms not stated | Removes blockiness and smeared detail using neighbouring frames. Keeps faces and the filtered look as they are. | very little / low / none |
| cleanup | **Cleanup, other training** | BasicVSR++ NTIRE21 Track 1 (fixed-quality x265 training), existing adapter | Same | Same idea, trained on a different kind of compression. Usually looks almost the same; sometimes calmer. | very little / low / none |
| cleanup | **Crisper cleanup** | BasicVSR++ NTIRE21 Track 2 (`..._ntire_decompress_track2_20210314-eeae05e6.pth`), existing adapter | Same | Trained to look sharper rather than to match the original exactly. Can add a little artificial sharpness. | little / medium / none |
| cleanup | **Grain and noise calmer** | BasicVSR++ denoise (`basicvsr_plusplus_denoise-28f6920c.pth`, mid 64, 15 blocks), existing adapter | Same | Calms grain and noise across frames. Not made for blockiness; may soften very fine edges slightly. Faster than Gentle cleanup. | little / low / none |
| cleanup | **Adjustable deblock** (Light / Medium / Strong) | DRUNet deblocking (`github.com/cszn/KAIR/releases/download/v1.0/drunet_deblocking_color.pth`) through spandrel with your own wrapper that passes the strength map (spandrel's default call fixes it); three catalog choices share one weights file | MIT | Smooths blocks and ringing on each picture without adding detail. Strong can look waxy. | little / low / possible |
| cleanup | **All-round cleaner** | SCUNet real PSNR (`github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_psnr.pth`) | Apache-2.0 | Cleans mixed noise and compression on each picture. Calm, slightly smoothing. | little / low / possible |
| cleanup | **Picture deblock** | FBCNN (already used as a benchmark candidate) | Apache-2.0 | Cleans each picture on its own. Good for calm clips; can flicker a little on moving ones. | little / low / possible |
| cleanup | **H.264 remover (community)** | 1xDeH264_realplksr (`github.com/Phhofm/models/releases/download/1xDeH264_realplksr/1xDeH264_realplksr.safetensors`) | CC BY 4.0 | Made by the community for H.264 blockiness. Crisper, slower, and less predictable. | noticeable / medium / possible |
| motion | **Smooth motion** (default, already installed) | RIFE 4.25 | MIT | Makes new in-between frames. Recommended by its author for most scenes. | very little / low / none |
| motion | **Smooth motion, newest** | RIFE 4.26 (from the Practical-RIFE release; verify the source) | MIT | The newest version. Sometimes better on fast motion, sometimes not. | very little / low / none |
| motion | **Smooth motion, faster** | RIFE 4.25 lite | MIT | Faster, slightly less accurate on fast motion. | very little / low / none |
| size | **Standard resize** (default, no download) | the existing non-learned resize | none | Makes the picture bigger without AI. Never changes the look. | very little / low / none |
| size | **Faithful 2× enlarger** | 2xLiveActionV1_SPAN (from `github.com/jcj83429/upscaling`) | CC BY-NC-SA 4.0 (personal use only) | Enlarges real-life video and tidies compression edges and halos. Keeps grain and colours. Can over-sharpen a little. | little / medium / possible |
| size | **Sharper detail** | Real-ESRGAN realesr-general-x4v3 (and the `wdn` version for a blend) | BSD-3-Clause | Makes edges crisper. Can invent texture that was not there, so it may change skin and hair. | noticeable / medium / possible |

Rules:

- Do not add models that add skin texture or are GAN real-world video models (for example h264Texturize, SkinDiffDetail, RealBasicVSR). The product keeps the beauty-filter look and never redraws faces.
- Every model must stay within the memory budget from P1a-6 (process total under 5 GB at 720×1280 → 1080×1920); single-frame models may use tiling with overlap. A model that cannot meet it, cannot be downloaded, or whose licence cannot be confirmed is left out, with the reason in the report.
- The `size` stage runs after cleanup and before the final resize to the chosen size and before RIFE. With "Standard resize" the pipeline is exactly today's.

### M3. Models screen (U6)

```
| Models                                       [Add my own model…] [Compare on my video] |
| (Cleanup · 8) (Smoother motion · 3) (Bigger picture · 3) (Faces · coming later)        |
| +--------------------------------+ +--------------------------------+ +-------------+ |
| | Gentle cleanup        [Default]| | Crisper cleanup                | | Adjustable  | |
| | BasicVSR++ · compressed video  | | BasicVSR++ · perceptual        | | deblock     | |
| | Removes blockiness and smeared | | Trained to look sharper rather | | ...         | |
| | detail using neighbouring ...  | | than to match the original...  | |             | |
| | Speed      Changes the look  Licence                             | |             | |
| | Slow       Very little       Free   | ...                        | |             | |
| | 176 MB                [Installed]| | 176 MB              [Install] | |             | |
| +--------------------------------+ +--------------------------------+ +-------------+ |
```

- Tabs per category with counts; Faces is disabled. Card grid (cards at least 320 px wide): title (17 px / 650), technical name (12 px, text-3), Default badge, description (14 px, text-2), three small facts (Speed: Fast / Medium / Slow / Very slow from the measured fps, with "about N h per hour of video" in the tooltip; Changes the look; Licence plain text), size, and one button: Install (accent) or Installed. The ⋯ menu has Make it my default, Verify again, Details (exact licence, source URL, SHA-256, measured speed and memory), Remove (refused for a model used by queued jobs: "Used by 2 videos in the queue").
- Install opens the licence dialog from P1b (licence name and source URL, explicit agreement, consent recorded), then shows download progress and the SHA-256 result on the card.
- "Make it my default" sets the default model of that category in Settings; Standard uses the cleanup default, both modes use the motion and size defaults. New jobs pick up defaults; queued jobs keep their settings.
- The Add dialog's More options lists installed models per category (Cleanup model, Smoother motion, Bigger picture).
- "Add my own model…" keeps the P1b validation; user models choose their category in their manifest (`docs/ADDING_MODELS.md` explains the new fields).

## 6. Part C: compare models on the owner's video

### C1. Engine

- `POST compare` with `{file, start, seconds (3/5/10, default 5), models: [up to 3 model ids of the same category], settings}` returns one operation. It renders the source excerpt once ("Original", resized with the pipeline's own resize to the output size) and then each model through the real pipeline with that model in place of the stage it belongs to (other stages as in the settings). Previews are H.264 8-bit, as the Trial previews are.
- Per model: progress, measured speed, and "about X h Y m for this video" from the measured speed and the estimator. Each model's preview is available as soon as it is done.
- Scheduling as in S4. A model that is not installed is installed first, only after its licence dialog.
- Keep previews of the last 5 compare sessions (at most 2 GB, oldest removed first); previews tied to a job are removed with the job. Outside Git, under the engine home.
- The P1b Trial (`POST trial`) stays for the API, and the GUI's Trial becomes Compare with one model (classic Original vs result).

### C2. Compare screen

```
| [<]  Compare models                                                     [Change video…] |
|      beach_walk.mp4 · 5 seconds from 0:42                                              |
| 0:42 – 0:47   Picked a part with lots of motion. Drag the box to choose other seconds.   |
| [▒▒▒▒[■]▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒]   (thumbnail strip)   |
| Compare (Original) (✓ Gentle cleanup) (✓ Cleanup, alternative) (✓ Picture deblock)       |
|         (+ Sharper detail · installs 5 MB)        [All side by side|Swipe two] [Fit|2×|4×] |
| +----------+  +----------+  +----------+  +----------+                                  |
| | Original |  | Gentle   |  | Cleanup, |  | Picture  |                                  |
| |          |  | cleanup  |  | altern.  |  | deblock  |                                  |
| |   9:16   |  |          |  |          |  |  Making  |                                  |
| |          |  |          |  |          |  |  preview |                                  |
| |          |  |          |  |          |  |  · 64%   |                                  |
| +----------+  +----------+  +----------+  +----------+                                  |
| Your file     Default       Calmer, a     Each frame                                   |
| as it is      About 2 h 40m bit softer    on its own                                    |
|               [Chosen]      [Use this]    Measuring speed…                              |
| [|<] [▶] [>|]  ───────●───────────────  0:44.2 / 0:47.0  [Loop]  All pictures stay in step, frame by frame. |
```

- Top: a thumbnail strip of the whole source with a draggable box for the chosen seconds. The default range is the busiest part (most motion from the analysis data), else the middle. Changing the range renders again.
- A small "Comparing: Cleanup ▾" selector before the chips picks the category (Cleanup, Smoother motion, Bigger picture); the other stages stay as in the job's settings.
- Chips: Original is always shown; up to 3 installed models of one category can be selected (selected = filled chip with a check). Models not installed appear as dashed chips "+ Name · installs N MB" (opens the licence dialog, then installs and adds it). Changing the selection renders only what is missing.
- Layouts: **All side by side** (portrait sources: up to 4 in one row, about 240 px wide each at 1280×800; landscape sources: a 2×2 grid) and **Swipe two** (one large picture with a draggable divider and a "Left"/"Right" picker for any two of the shown items; zoom 2× by default).
- Zoom Fit / 2× / 4×, nearest neighbour when zoomed, with synchronized panning (drag any picture to move all of them). Frame step with buttons and the arrow keys, Play/Pause with Space, Loop, a position slider and "0:44.2 / 0:47.0".
- Synchronization: extend the P1b WebCodecs frame clock to up to 4 streams; draw only when every visible stream has the same frame index.
- Each tile: name label on the picture; two caption lines (character, "About 2 h 40 m for this video" or "Measuring speed…"); "Use this" sets the model for the job (only before it starts) or for the open Add dialog. For a job that already started the button is disabled with "Already started. Remove it and add it again to use another model." The chosen tile has an accent border and the button reads "Chosen". The tile's ⋯ menu has "Make it my default".
- Opened from: Models "Compare on my video" (pick a file), Add dialog "Try models first", Home and Up next row menus, History "Compare again". The back button returns to where it was opened.

## 7. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs in English.
- Never commit media, weights, previews, generated videos, `node_modules`, build output, the owner's logs, or private sample names. Screenshots use synthetic footage only and stay outside the repository.
- Do not change what the existing presets produce: the CPU fixture outputs stay byte-identical, and a Standard trial on the GPU gives the same frames as before for the same settings.
- Keep the service security model (localhost only, token, Host/Origin checks). No telemetry, no auto-update.
- The CLI keeps working on the same store; CLI behaviour stays the same apart from the bug fixes above.
- README (for non-engineers): fix the duplicated "developer guide" link and update "Using the app" for Home, History, Schedule and comparing models. No technical terms beyond "NVIDIA RTX graphics card".
- Update `docs/API.md`, `docs/GUI.md`, `docs/ADDING_MODELS.md` and `docs/TROUBLESHOOTING.md` for everything that changed.

## 8. Acceptance criteria

- **A1** S0 evidence report: each stuck case classified against H1 to H5 (or NOT FOUND).
- **A2** S7 tests pass. On the RTX 4060 Ti, a Standard job shows a changing percent within 30 s of its first segment start (log timestamps).
- **A3** Owner-PC queue run: three jobs in a row (Standard 30 s, Fast 30 s, Standard 2 min synthetic or authorized clips), a trial while a job runs, and a trial outside operating hours. All finish; no job or trial stays at 0% for more than 60 s; report the timings.
- **A4** No console window or flash appears at any point: cold start of the packaged app (engine not running), adding Standard and Fast jobs, a trial, a compare, a model install, Quit. Plus the W2 static test, and a log line showing that the service and segment children run as `pythonw.exe`.
- **A5** Part U implemented: component tests for Home (now processing, up next, banners, finished jobs leaving), History (filters, search, retry, remove keeps the file), Schedule editing (drag edges, add, delete, keyboard, autosave and Undo, exceptions, override), and the Add dialog; one Electron e2e test adds a synthetic file, sees it in Now processing, sees it finish and appear in History.
- **A6** Part M: every catalog entry has a verified URL and SHA-256 and its exact licence, loads through its adapter, runs a 5 s compare on the RTX 4060 Ti within the memory budget, and has its measured fps and peak memory in its manifest and the report (or is left out with the reason). Install, Verify again, Make it my default and Remove work from the GUI. The default pipeline output is unchanged.
- **A7** Part C: compare with 3 models on the GPU; automated sync test with synthetic clips that have the frame number drawn in: for 100 random seeks and 300 played frames, all visible streams show the same frame index.
- **A8** Checks green: `ruff`, `ruff format --check`, `pyright`, CPU tests, GUI lint, typecheck, unit tests, build, e2e; CI green on Windows and Ubuntu.
- **A9** Screenshots (synthetic footage) of every screen at 1280×800 and 1100×700, dark and light, plus one at 150% scaling.

## 9. Checks to run

- Engine: `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest` (CPU).
- GUI: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`, `npm run package`.
- Owner hardware: A2, A3, A4, A6 and A7 on the RTX 4060 Ti.

## 10. GUI checks for the owner after the PR

1. Open the app: no black console window appears, now or while it works.
2. Drop a video on the window: the dialog shows Standard and Fast with their done times; Add to queue.
3. Home shows the video large with a percent that starts moving within about half a minute.
4. When a video finishes, it leaves Home and appears in History; Play opens it.
5. On Schedule, drag the edge of an hours block: the finish time at the top changes, and "Saved · Undo" appears.
6. Start a trial outside your hours: it starts at once.
7. On Models, install one optional model, then "Compare on my video" with three models and switch between All side by side and Swipe two.

## 11. Report (`.ai/LAST_REPORT.md`, English)

Summary per part; A1 to A9 with PASS / FAIL / NOT RUN and evidence; the S0 classification; measured speed and memory per catalog model; screenshot paths (outside the repository); known issues and questions for the designer; exact reproduction steps. Never report a test as passed if it did not run.
