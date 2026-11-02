# CURRENT_TASK: VE-R1b (iPad product, part 2: add jobs by URL or upload, predicted finish, push notifications, cleanup)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1b
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file, on top of `main` b54f2b6 (PR #17, VE-R1a and R1a-2, merged). A new draft PR follows.
- Write a new `.ai/LAST_REPORT.md` for VE-R1b; keep the older reports below it.
- Same workspace and isolation rules as VE-R1a. Do not change the processing pipeline, models or estimator maths.
- **The owner's real remote service is installed and runs from this checkout** (Scheduled Task "VideoEnhancer", library `D:\VideoEnhancer\完成動画`, one paired iPad). Do not touch it, its home, its library, its task or its firewall rules during development. Python files you edit are only loaded by the live service after a restart, which the operator does after review (section 7).

## 0. What R1a built (use it, do not rebuild it)

`src/videoenhancer/remote/`: `gateway.py` (IPv4 HTTPS + HTTP setup port, private-source filter, Host/Origin checks, device cookie `ve_device`, sanitized route-template log, per-connection TLS handshake, one-time `/dl/<token>` downloads, `/api/client-event`), `security.py` (devices, pairing window), `certificates.py`, `library.py` (folder-backed library, Range, delete, storage), `install.py` / `launcher.py` / `firewall.py` (task, shortcut, firewall), `adapter.py` (in-process engine access), `web/` (plain ES modules: `app.mjs`, `logic.mjs`, `style.css`, `sw.js`, black theme, Library and Settings tabs, hidden Add tab). The gateway currently refuses request bodies other than `{}` and the 2 KB client-event; this task must add bounded JSON bodies for the new POST routes and a streamed body path for upload chunks (no whole-file buffering).

## 1. Owner decisions that apply

- Jobs are added from the iPad only: **paste a video URL**, or **upload a video from the iPad** (Photos or Files). iPadOS does not offer the web app in the share sheet, so URL adding is paste only.
- Before adding, the app shows the **predicted finish time**. After adding, the job **starts immediately** (no schedule).
- There is **no live progress**. The iPad gets a **push notification when a job finishes and when it fails**, nothing else.
- The finished video goes into the **library**. The **source and all intermediate files are deleted** when the job ends (done, failed or cancelled). **No job history** is kept; a **one-line log entry without names or URLs** is kept.
- Input is limited to the 1080p class (short side ≤ 1080, owner decision 2026-10-16). A URL picks the best ≤ 1080p SDR format automatically. A larger local upload is refused with the reason.
- Settings come from the saved defaults (preset, codec, size, frame rate) until R2 adds a settings screen.

## 2. Work

### 2.1 Add tab

1. Fill the **Add** tab that R1a reserved. Two cards: **Paste a link** (a text field and a Paste button using `navigator.clipboard.readText()` when allowed) and **Upload a video** (`<input type="file" accept="video/*">`, which offers Photos and Files).
2. **Link:** link downloads go to `VE_HOME/remote/incoming/` (set the existing `video_download_folder` requirement to that folder for gateway jobs only; do not change the desktop's saved preference). Run the existing link check (`links/check` logic in-process). While it runs, show "Checking the link…". Pick the entry and format automatically: the best SDR stream with short side ≤ 1080. For a playlist, show the entries and let the owner tick which to add (all ticked by default). Show title, duration, chosen resolution and the predicted finish time per entry. If the optional link tools are not installed, show one sentence and an **Install link tools** button that runs the existing install flow with explicit consent (show the release plan text it already produces).
3. **Upload:** refuse before starting when the file is larger than the free space on the drive of `VE_HOME/remote/incoming/` minus 10 %, or larger than 20 GB. Resumable upload as proven in the spike (chunked, resumes after a dropped connection or after the app is reopened, SHA-256 verified at the end). Show bytes and speed while uploading; the app must stay open during upload (say so in one line). Uploads land in a temporary folder inside `VE_HOME/remote/incoming/`, never in the library. After the upload completes, probe it; refuse > 1080p class with the reason and delete the file.
4. Before **Add**, show "Ready about <local time> (<duration from now>)" from the existing estimator, including jobs already running. Unknown estimates show "Finish time unknown until the download starts" rather than a guess.
5. **Add** queues the job and returns to the Library tab with a one-line banner "Added. You'll get a notification when it's ready." There is no job list. A small line on the Library tab may show "1 video in progress" with its predicted finish time (no percentage).
6. A job can be cancelled from that line (confirm first). Cancelling deletes its files like any other end.

### 2.2 Running jobs

1. When the gateway runs, the engine ignores the saved schedule (jobs run at any time). Do not delete the saved schedule.
2. Output path: write to a temporary name in the library folder (for example `.<id>.partial.mp4`, hidden and skipped by the library list), then rename to the final name when the job is done. Final name: the source title (URL title or uploaded file name without extension), cleaned for Windows (no reserved names or characters, at most 120 characters), plus ` (enhanced).mp4`; add ` 2`, ` 3`, … on a clash. Never overwrite.
3. When a job ends (done, failed or cancelled): delete the source (downloaded or uploaded file), all segment and working files, previews and the job record; then append one log line to `VE_HOME/remote/activity.log`: UTC time, outcome, preset, input resolution and duration, output bytes, processing seconds, and an error category for failures. **No titles, file names, URLs or paths.** Keep the log under 1 MB by dropping the oldest lines.
4. Keep the PC awake while a job runs or an upload or download is in progress (`SetThreadExecutionState` with `ES_SYSTEM_REQUIRED`, released afterwards). Do not keep the display on.
5. After a restart of the service or PC, unfinished jobs resume as the engine already does; their sources stay until the job ends.

### 2.3 Push notifications

1. After pairing, the Library tab shows a one-line card "Get a notification when a video is ready." with a **Turn on notifications** button. iPadOS requires the permission request to come from that tap. Store the subscription with the device; hide the card once subscribed.
2. VAPID keys are generated once in `VE_HOME/remote/`. Use `sub = https://github.com/Kei-Takamizawa/VideoEnhancer` (proven in R0c). Add `pywebpush` (or an equivalent small implementation) to the dependencies.
3. On **done**: title "Ready", body "<title> is in your library." Tapping opens the app on that library item (`notificationclick` in `sw.js` focuses or opens `/#item=<id>`). On **failure**: title "Couldn't finish", body "<title>: <one plain sentence>". The payload is encrypted end to end by Web Push; do not log it.
4. Record each send's HTTP status and Apple reason in the gateway log (no endpoint, no keys). Drop a subscription after 404 or 410.
5. Settings tab: show whether notifications are on for this iPad, with a **Send a test notification** button.

### 2.4 Service control gaps found in R1a (add to this cycle)

1. `ve remote install` must start the service **through the Scheduled Task** (`Start-ScheduledTask`), not as a child of the install shell, so the task always owns the running service.
2. Add `ve remote restart` and `ve remote stop` (stop the task's service gracefully through the loopback shutdown path, then start the task again). The gateway shutdown refusal (409) applies only to the desktop's request, not to these commands.
3. The Redo-pairing message box must close itself when the pairing window closes, so no helper process remains.

## 3. API additions (device cookie required)

`POST /api/links/check`, `GET /api/links/check/{id}`, `POST /api/uploads` and the chunk, status and finish routes, `POST /api/estimate`, `POST /api/jobs`, `GET /api/jobs/active` (titles, predicted finish, no percentages), `POST /api/jobs/{id}/cancel`, `POST /api/push/subscribe`, `POST /api/push/test`. Document them in `docs/REMOTE.md`.

## 4. Tests

- Python: automatic format choice (≤ 1080, SDR, best), > 1080p upload refused and deleted, upload resume and hash check, finish-time text with known and unknown estimates, schedule ignored while the gateway runs, partial-name and clash naming, Windows name cleaning, cleanup on done, failed and cancelled (source, working files and record gone; library file kept only on done), activity log contents contain no title, URL or path (search the log for the test's title and URL), log size cap, keep-awake set and released (Windows call replaced by a fake on CI), push payloads and dropping a subscription on 410, VAPID JWT fields.
- JavaScript: add-flow state decisions, upload progress and resume text, finish-time text.
- Real GPU run on the PC: one short link (use a public-domain or test video URL that the existing link tests already allow) and one uploaded generated 1080p clip, Standard preset; confirm the library gets both files, the sources and working files are gone, the log has two nameless lines, and the predicted finish time was within the estimator's own reported range. Push to a real device cannot be automated; report it as for the owner.
- `ruff check`, `ruff format --check`, the CI CPU pytest command and the node tests.

## 5. Allowed files

`src/videoenhancer/remote/**`, `src/videoenhancer/cli.py` (restart/stop commands), minimal hooks in `src/videoenhancer/service/engine.py`, `service/server.py` and `service/link_jobs.py` for job-end cleanup, naming, schedule bypass and the stop path, `src/videoenhancer/service/settings.py`, `tests/**`, `docs/REMOTE.md`, `docs/API.md`, `pyproject.toml`, `uv.lock`, `.ai/LAST_REPORT.md`.

## 6. Done when

Sections 2 to 4 pass, the diff contains only allowed files, and the report lists test counts, the GPU run's measurements (predicted vs actual finish time), what was deleted at job end (paths relative to the scratch home), and the exact steps for the owner's iPad check.

## 7. Operator after the commit (exact commands in the report; run only after designer review)

1. `ve remote restart` (new) on the real home, or, if that is refused, stop the service processes and `Start-ScheduledTask -TaskName VideoEnhancer`. Confirm the paired device count is still 1.
2. Report `ve remote status`.
3. The owner then checks from the iPad: turn on notifications and send a test notification; add one short public video by URL; upload one short video from Photos; see the predicted finish time; receive the Ready notifications; play both from the library; confirm with the operator that `VE_HOME/remote/incoming/` is empty afterwards and the activity log has two nameless lines.
