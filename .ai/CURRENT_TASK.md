# CURRENT_TASK: VE-R1a (iPad product, part 1: headless service, secure gateway, pairing, black web app, library)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1a
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-yyrl3q`, restarted from `main` 4340e22 (PR #16, the R0 spike, is merged). A new draft PR follows.
- Write a new `.ai/LAST_REPORT.md` for VE-R1a. Keep the older reports below it under `## Previous: ...` headings.
- Workspace rules in `docs/WORKSPACE.md` apply. Tests use an isolated `VE_HOME` and an isolated library folder under `work\scratch`. **Never** read or write the owner's real library folder (`D:\VideoEnhancer\完成動画`), `VE-check` or `AppData` during development, and never install the Scheduled Task or Start-menu shortcuts for the owner's real home in this cycle except in the final owner-check step (section 8), which the operator runs.
- Do not change the processing pipeline, models, estimator or scheduler.

## 2. Product direction (owner decisions, 2026-11-02; context for R1a and later parts)

The desktop GUI will be retired. The product becomes:

- a **headless engine service** on the Windows PC that starts by itself at sign-in and shows nothing on the PC;
- an **iPad web app** added to the Home Screen ("Open as Web App" on), used only on the home Wi-Fi. It is the only UI.

Proven in the R0 spike (`spikes/ipad/`, read its README, server and `.ai` reports in Git history): an app-made CA installed once on the iPad gives trusted HTTPS; the Home Screen app has its own cookie jar, so pairing must be claimed **inside the app over HTTPS**; `https://<COMPUTERNAME>.local:<port>` and the PC's IPv4 address work, a fixed `videoenhancer.local` name did not; the server is IPv4-only; H.264, HEVC and AV1 MP4 play with HTTP Range; Web Push works only in the Home Screen app and needs a real VAPID `sub` (R1b); in the Home Screen app a `Content-Disposition: attachment` link traps the app, `target=_blank` delivers nothing, and **fetch into a Blob then `navigator.share({files})`** works (500 MB verified, 1 GB untested).

Parts:

- **R1a (this task):** service, gateway, certificates, pairing, web app shell (black), library (list, stream-play, download, delete), storage bar.
- **R1b (next):** add a job by pasted URL or by uploading a video from the iPad, predicted finish time before adding, jobs start immediately, Web Push on completion and on error, sources and intermediates deleted when a job ends, no job history, a one-line log without names or URLs, keep the PC awake while a job runs.
- **R2:** model download and delete, settings, paired-device list from the iPad.
- **R3:** remove the desktop GUI, the mpv player and the libmpv CI.

Dropped for good: schedule, history, thumbnails and previews, Compare, adding files from PC folders, HDR, streaming processing, a native app.

## 3. Architecture

- New package `src/videoenhancer/remote/`. The gateway runs **inside the existing `ve serve` process** and calls the engine in-process through a small adapter module. It must not go through the loopback token API and must not widen that API's Host, Origin or token rules.
- Use the standard library HTTP server with `ssl` (as `service/server.py` does) and `cryptography` for certificates. Add `cryptography` to `pyproject.toml` and `uv.lock`. Do not add aiohttp, zeroconf or a JavaScript build step.
- The web app is plain HTML, CSS and ES-module JavaScript under `src/videoenhancer/remote/web/`, served by the gateway. No framework, no bundler, no `node_modules`. Logic that can be tested without a browser lives in modules tested with `node --test` (as the spike did).
- Gateway state lives in `VE_HOME/remote/` (CA, server certificate, devices, pairing state). Private keys and device secrets get the same user-only ACL as `serve.json` (mode 0600 on POSIX CI).
- New settings keys in `service/settings.py` defaults: `remote_enabled` (false), `remote_https_port` (8443), `remote_setup_port` (8080), `library_folder` (""). An empty `library_folder` resolves to `D:\VideoEnhancer\完成動画` when drive D exists, otherwise `%USERPROFILE%\Videos\VideoEnhancer`. The folder is created on first use. Changing it from the iPad comes in R2.

## 4. Work

### 4.1 Service and start-up

1. `ve serve --remote` (or `remote_enabled` true) starts the gateway together with the engine. Without it, `ve serve` behaves exactly as today.
2. `ve remote install`: creates the CA and server certificate if missing, sets `remote_enabled`, registers a **per-user Scheduled Task** "VideoEnhancer" that runs at sign-in with no console window (`pythonw.exe` from this checkout's `.venv`, working folder = the engine location), restarts on failure (3 tries, 1 minute apart) and needs no administrator rights; creates a Start-menu shortcut **"VideoEnhancer - Redo pairing"**; starts the service; opens a 2-minute pairing window; prints the setup address. It must be idempotent.
3. `ve remote uninstall` removes the task and shortcut and stops the service. It keeps the CA, devices and the library unless `--forget-devices` is given. It never deletes the library.
4. `ve remote pair` reopens the pairing window for 2 minutes on the running service (new token-authenticated loopback route `POST remote/pairing`). The Start-menu shortcut runs it and shows one small Windows message box with the address and the closing time. This is the only thing the product shows on the PC.
5. `ve remote status` prints whether the service and gateway run, the addresses, the certificate expiry, the number of paired devices and whether a pairing window is open.
6. Coexistence until R3: the desktop app may still be started. If a headless service already runs, the desktop connects to it as it does today through `serve.json`. Quitting the desktop must **not** stop a service that was started with `--remote`: `POST shutdown` from the desktop returns 409 with a clear message, and the desktop treats that as "closed the window, service keeps running". Change the Tauri shell only as much as needed for this; add a test.

### 4.2 Certificates

1. CA: "VideoEnhancer Local CA (<COMPUTERNAME>)", 10 years, name-constrained to the PC's names and private IPv4 ranges if iPadOS accepts that (verify with the spike's knowledge; if unverifiable, do not constrain and say so).
2. Server certificate: SANs `<COMPUTERNAME>.local`, `<COMPUTERNAME>`, and every current private IPv4 address of the PC. Validity 397 days. At every start, reissue it when it expires within 30 days or when the PC's private IPv4 addresses changed. Reissuing never changes the CA, so the iPad needs no new profile.
3. The setup page offers the CA as a `.mobileconfig` profile (and the plain `.cer`), as in the spike.

### 4.3 Network rules

1. Listen on IPv4 only, port `remote_https_port` (HTTPS) and `remote_setup_port` (plain HTTP).
2. Accept connections only from private or link-local IPv4 source addresses (10/8, 172.16/12, 192.168/16, 169.254/16) and loopback. Close all others without a response.
3. The Host header must be one of the certificate names with the right port; otherwise 421.
4. The plain HTTP port serves **only** the setup page and the CA profile, and only while a pairing window is open; otherwise a one-line page that says "Run 'VideoEnhancer - Redo pairing' on the PC". No API, no library, no cookies on HTTP.
5. Every state-changing request requires a same-origin `Origin` header. Responses carry a strict Content-Security-Policy (no inline script), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store` for API responses.
6. The gateway log records method, route template, status and duration only: never query strings, file names, URLs, cookies or device secrets.

### 4.4 Pairing and devices

1. Flow for a new iPad: Safari opens `http://<COMPUTERNAME>.local:8080/` while the window is open → installs and trusts the CA profile (the page shows the exact Settings steps, in English) → opens `https://<COMPUTERNAME>.local:8443/` → Share → Add to Home Screen with "Open as Web App" on → opens the Home Screen app → taps **Pair this iPad**. The claim is `POST /api/pair/claim` over HTTPS from inside the app.
2. The first valid claim inside an open window creates a device and **closes the window at once**. Later claims fail with a message that says to run Redo pairing. Claims are rate-limited (5 per minute per address).
3. A device gets a random 256-bit secret in a cookie `ve_device`: `HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=34560000`. Store only its SHA-256 hash with the device id, a label derived from the User-Agent (for example "iPad, Safari 27"), created and last-seen times.
4. Every page except the pairing screen and static assets, and every API route except the claim, requires a valid device cookie. An unpaired app shows the pairing screen with the steps above.
5. Redo pairing keeps existing devices. Removing devices comes in R2 (`--forget-devices` in 4.1 is the only way in R1a).
6. Record in the report whether a paired Home Screen app keeps its cookie after the iPad restarts and after 24 hours (the owner's check, section 8). If iPadOS drops it, say so; do not work around it in this cycle.

### 4.5 Web app shell (black)

1. Home Screen web app: `manifest.webmanifest` (`display: standalone`, `background_color` and `theme_color` `#000000`), `apple-touch-icon` (a simple original icon), `apple-mobile-web-app-capable`, status bar `black-translucent`, `viewport-fit=cover` with safe-area insets, and a service worker that caches only the shell files (never API responses or videos).
2. **Black-based design (owner, 2026-11-02):** page background pure black `#000000`; raised surfaces dark grey (about `#111` to `#1c1c1e`); primary text near white (about `#f5f5f7`), secondary text grey with at least 4.5:1 contrast on its background; one accent colour used sparingly for primary actions and the library segment of the storage bar; destructive actions in red. `color-scheme: dark`. No light theme. System font stack. Touch targets at least 44 by 44 points. Works in portrait and landscape on iPad sizes; no horizontal scrolling.
3. English UI text. Two tabs in R1a: **Library** (default) and **Settings**. Leave a hidden, unreachable place for **Add**, which R1b fills.
4. Settings in R1a shows only: the PC name and address, the certificate expiry date, "This iPad is paired since <date>", and the app version. No controls yet.
5. Errors are shown as one plain sentence near what failed. When the PC cannot be reached, show "Can't reach the PC. Check that it is on and on the same Wi-Fi." with a Retry button.

### 4.6 Library

1. The library is the set of `.mp4`, `.m4v` and `.mov` files directly inside the library folder (no subfolders, no database). Skip files still being written (R1b writes to a temporary name and renames when finished) and anything that is not a regular file inside the folder (reject symbolic links and junctions that point outside it).
2. `GET /api/library` returns the items, newest first: an opaque stable id (not the path), the display name (file name without extension), size in bytes, modified time, and duration, width, height and codec from ffprobe. Cache probe results by (name, size, mtime) in `VE_HOME/remote/`; never let one bad file break the list (show it with "Can't read this video" and still allow delete).
3. Item view: a `<video controls playsinline preload="metadata">` that streams `GET /api/library/<id>/video` with correct `Range`, `206`, `Accept-Ranges`, `Content-Length` and MIME type. No thumbnails and no posters (owner dropped previews).
4. **Download (variant B from R0c):** fetch the file into a Blob with a progress line ("Loading 312 of 1,024 MB"), then `navigator.share({files: [new File([blob], name, {type})]})` so the owner can pick "Save Video" or "Save to Files". Release the Blob afterwards. A cancelled share is not an error. If the page runs out of memory or `navigator.share` is missing, show one sentence that says so. Never use a `Content-Disposition: attachment` link or `target="_blank"` in the app.
5. **Delete:** a red button, then a confirmation sheet that names the video and its size. Deletion is permanent (not the Recycle Bin), refused with a clear message while that file is being streamed or downloaded by the gateway, and the list and storage bar refresh afterwards.
6. **Storage bar** at the top of the Library tab, one horizontal bar for the drive that holds the library folder: segment 1 = space the library files use (accent colour), segment 2 = other used space on that drive (grey), segment 3 = free space (dark). Under it one line, decimal GB with one decimal: "Library 12.3 GB · Free 456.7 GB of 1,000.2 GB (D:)". `GET /api/storage` provides the numbers.

## 5. API summary (gateway, HTTPS, device cookie required unless noted)

| Method and route | Purpose |
| --- | --- |
| GET / and static assets | Web app shell (assets need no cookie; the app decides what to show) |
| GET /api/session | `{paired, device_label, paired_at, pc_name, addresses, cert_expires}`; no cookie gives `{paired:false, pairing_open}` |
| POST /api/pair/claim | Claim during an open window (no cookie needed) |
| GET /api/library | Library items |
| GET /api/library/{id}/video | Range streaming |
| DELETE /api/library/{id} | Permanent delete |
| GET /api/storage | Drive total, free, library bytes, drive label |

Document it in a new `docs/REMOTE.md` (also the install, pairing, addresses and security rules). Add one line to `docs/API.md` pointing there, and document the loopback `POST remote/pairing`.

## 6. Tests

- Python: certificate SANs, validity and reissue on IP change or near expiry (CA unchanged); private-address filter; Host check (421); HTTP port serves only setup and only while the window is open; claim opens, closes and rate-limits correctly and stores only the hash; cookie attributes; every protected route rejects a missing or wrong cookie; Origin check on DELETE and POST; log lines contain no query, file name or secret; library listing skips temporary, hidden, non-video and outside-folder entries and survives an unreadable file; Range responses (first byte, middle, suffix, invalid range 416); delete refuses traversal ids and files in use; storage numbers on a temporary folder; `serve --remote` shutdown refusal (409) while plain `serve` keeps today's behaviour; `ve remote install` and `uninstall` with the Windows task and shortcut calls replaced by a fake on CI.
- JavaScript (`node --test`): storage bar segment widths and text, size and time formatting, download progress text, share-cancel handling, pairing-state rendering decisions.
- Browser smoke on Windows with Playwright WebKit against a scratch home and a scratch library with two generated short videos: pairing screen → pair → library shows both with the bar → open one, play starts → delete one after confirming → the list and bar update. Save two screenshots (library, item view) to `work\evidence\VE-R1a\` (not Git) and check by measuring pixels that the page background is `#000000`.
- Run `uv run ruff check .`, `uv run ruff format --check .`, the CI CPU pytest command and the new node tests. The legacy desktop E2E suite is not required this cycle (known unrelated failures); say so in the report.

## 7. Allowed files

`src/videoenhancer/remote/**`, `src/videoenhancer/cli.py`, `src/videoenhancer/service/server.py`, `src/videoenhancer/service/engine.py` (only the shutdown refusal and the `remote/pairing` route), `src/videoenhancer/service/settings.py`, `tests/**` (new remote tests and the minimal changes needed for the shutdown behaviour), `docs/REMOTE.md`, `docs/API.md`, `pyproject.toml`, `uv.lock`, `gui/src-tauri/**` and `gui/src/**` only for 4.1 item 6, `.github/workflows/**` only to run the new node tests, `.ai/LAST_REPORT.md`. Do not change `spikes/ipad/**` (R3 removes it).

## 8. Owner check preparation (operator runs this after the commit)

At the end, the report must give the exact commands for the operator to:

1. stop the owner's everyday desktop app (standing permission) and any spike server;
2. run `ve remote install` for the owner's real home (`D:\my-workspace\VideoEnhancer\AppData` as the engine home if that is the active storage location; read the storage pointer, do not guess) with the default library folder;
3. put two short generated sample videos (H.264 and HEVC, under 50 MB each) and one 1 GB sample into the library folder for the check, named `R1a sample ...`;
4. afterwards, remove the samples (only those three files) and leave the service installed.

The designer then gives the owner a short Japanese check sheet: remove the spike's CA profile and "VE spike" icon, install the new profile, add the app, pair, check the library, play, download 1 GB with Save Video, delete a sample, check the bar, restart the PC and confirm the app still works without pairing again, and later report whether the app is still paired the next day.

## 9. Done when

Sections 4 to 6 are implemented and pass, the diff contains only allowed files, and the report lists: test counts, the screenshots' measured background colour, whether the CA name constraint was used, the commands in section 8, the workspace growth numbers, and anything not verified.
