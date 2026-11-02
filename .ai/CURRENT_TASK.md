# CURRENT_TASK: VE-R1a-2 (fix what the owner's iPad check found: large-video saving, firewall, setup window, TLS accept)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1a-2
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file (on top of f0fded5, VE-R1a). PR #17 continues.
- Write a new `.ai/LAST_REPORT.md` for VE-R1a-2 and keep the VE-R1a report below it under `## Previous: VE-R1a`.
- The VE-R1a task (in Git history at 5650209) still defines the product. Same workspace and isolation rules. The owner's real home now has the remote service installed. **Do not touch it, its Scheduled Task, its library folder or its firewall rules** during development; use scratch homes and fakes. Only the operator's final step in section 6 touches the real installation.

## 1. Owner iPad check results for VE-R1a (2026-11-02 08:18-08:34 UTC, iPadOS 27.2, Home Screen app)

Record these in the new report as the R1a owner results.

- **Network:** at first the iPad could not reach the PC at all. Windows had silently created **Block** inbound rules for the hidden `pythonw.exe` (path `work\cache\py\cpython-3.12.15-windows-x86_64-none\pythonw.exe`), because a windowless program cannot show the firewall prompt. The PC's network profile is **Public**. Later a Windows firewall prompt did appear and the owner allowed it; the rules are now Allow on the Public profile for `python.exe` and `pythonw.exe`.
- **Setup window:** the first 2-minute window closed before the owner had installed the new CA. The setup page (port 8080) is served only while a window is open, so the owner needed three windows. The operator's second `ve remote pair` was once refused by the PC's permission check; the Start-menu shortcut is the reliable path.
- **Pairing:** `POST /api/pair/claim` 200 at 08:22:05; library and storage loaded.
- **Playback:** the H.264 and HEVC samples played (Range 206 requests; no errors).
- **Delete:** deleting the H.264 sample worked; the list and storage bar refreshed.
- **Small video save:** Download, then Save video, then the share sheet, then Save Video to Photos **worked**.
- **1.1 GB video save (FAIL):** the full GET took about 7.4 s at 200 twice, then the Save video tap always showed "This video could not be shared. Try again." The error name and message were not recorded. In R0c the same pattern worked for 500 MB, but the spike built the File from one `response.blob()`, while R1a builds it from thousands of stream chunks.
- Two `GET /static` 404s at 08:21:55 (probably icon probes such as `apple-touch-icon-precomposed.png` or `favicon.ico`).

## 2. Work

### 2.1 Saving large videos

1. **Diagnostics first.** Add `POST /api/client-event` (device cookie and Origin required, body ≤ 2 KB JSON) that records `{kind, error_name, error_message (≤ 200 characters, no file names), size_bytes, can_share, phase}` to the gateway log. Do not log the video name. Send it on every share failure and every load failure. Show the error name in small grey text under the user message (for example "NotAllowedError"), so the owner can read it out.
2. **Build the File from one Blob:** `await response.blob()` then `new File([blob], name, {type})`, as the R0c spike did. Keep a byte progress line: read `Content-Length`, and if you need progress, use a cloned response or a separate lightweight counter, but the final File must come from a single Blob. Before calling `navigator.share`, check `navigator.canShare({files:[file]})` and record its result.
3. **Fallback for videos the share sheet refuses, or above a threshold:** **Save to Files with Safari.**
   - `POST /api/library/{id}/download-link` returns a **one-time URL** with a random 256-bit token that is valid for 10 minutes and for one complete download. That URL is `https://<same host>/dl/<token>`, served with `Content-Disposition: attachment; filename*=UTF-8''<name>`, Range support and no cookie requirement (the token is the authorization). Store only a hash of the token. The token is not logged; the route template is logged as `/dl/{token}`.
   - The app opens it **in Safari, not inside the Home Screen app** (a download inside the app traps it; R0b). Try `x-safari-https://<host>/dl/<token>` first. If iPadOS does not support that, show the link with a **Copy link** button and the sentence "Paste this link into Safari to save the video to Files." Report which one works only from the owner's check; do not claim it.
   - The UI: on a share failure, show "This video is too large to share directly." with a **Save to Files with Safari** button. Also show that button directly, without trying to share, when the video is larger than a threshold `share_limit_bytes` (setting, default 900,000,000 until the owner's check gives a measured limit).
4. Keep the existing Save video path for small videos unchanged in behaviour.

### 2.2 Firewall

1. `ve remote install` adds **one inbound allow rule per protocol (TCP)** for the exact `pythonw.exe` the task runs, limited to the **Private** profile and to the gateway ports, named "VideoEnhancer (iPad)". It does this through one elevated PowerShell call (one UAC prompt). If the owner declines UAC, install still succeeds and status says what is missing.
2. It also removes **Block** rules that Windows created for that exact program path (named "Python" or "pythonw.exe", Program equal to that path), and only those. List what it removed.
3. `ve remote status` adds `firewall` with: the network profile of each connected interface, whether the VideoEnhancer allow rule exists, and any Block rule for that program. If the active profile is Public, print one line: "Your network is set to Public. Set it to Private in Settings > Network & internet, or the iPad may not connect."
4. Do not change the network profile and do not touch other programs' rules. `ve remote uninstall` removes only the "VideoEnhancer (iPad)" rule.
5. Do not run these against the real PC in this cycle; fake the PowerShell calls in tests.

### 2.3 Setup page and pairing window

1. The plain HTTP port now serves the setup page and the CA profile **at all times** (the CA certificate is public). The 2-minute window gates **only** `POST /api/pair/claim`.
2. The setup page shows whether pairing is open right now and, if not, says "When you are ready to pair, click 'VideoEnhancer - Redo pairing' on the PC, then tap Pair this iPad within 2 minutes."
3. The app's unpaired screen says the same and has a **Try again** button that re-checks `/api/session`.

### 2.4 TLS accept

Move the TLS handshake out of `get_request` (the accept thread) into the per-connection worker (`do_handshake_on_connect=False`, then handshake with the 15-second timeout in the worker), so one slow or stalled client cannot delay others. Add a test: a client that connects and sends nothing must not delay a second client's request by more than 1 second.

### 2.5 Small things

- Serve `apple-touch-icon-precomposed.png` (same icon) and `favicon.ico`, or return 204, so icon probes no longer show as 404.

## 3. Tests

- Python: client-event endpoint (auth, Origin, size limit, no name in log); download-link token: one-time use, expiry, hash only stored, Range on `/dl/`, `Content-Disposition` with a non-ASCII name, no cookie needed, token absent from logs, 404 after use or expiry; setup page always served; claim still requires the window; firewall install, status and uninstall command construction with fakes, including declined UAC; TLS stall test.
- JavaScript: single-Blob construction path, threshold decision, share failure leading to the Safari option, x-safari URL construction, copy-link text.
- Browser smoke as before, plus: a video above a test threshold shows Save to Files with Safari, and the `/dl/` link downloads in a fresh context without cookies.
- `ruff check`, `ruff format --check`, pyright, the CI CPU pytest command, node tests.

## 4. Allowed files

The VE-R1a allowed list, unchanged: `src/videoenhancer/remote/**`, `src/videoenhancer/cli.py`, `src/videoenhancer/service/server.py`, `src/videoenhancer/service/settings.py`, `tests/**`, `docs/REMOTE.md`, `docs/API.md`, `.ai/LAST_REPORT.md`.

## 5. Report status rule

The VE-R1a Windows-WebKit playback gate is replaced by the owner's iPad result (playback passed on iPad). Mark it as "replaced by owner iPad check" with the date, not as a pass. VE-R1a-2 may be COMPLETED when sections 2 and 3 pass. Items that only the owner can check are listed under "For the owner", not counted as failures.

## 6. Operator after the commit (in the report, exact commands)

1. Restart the remote service on the real home so it runs the new code: stop and start the Scheduled Task "VideoEnhancer". Do not reinstall unless needed. If a reinstall is needed for the firewall rule, run `ve remote install` and let the owner answer the UAC prompt.
2. Report `ve remote status`, including the new firewall section.
3. Keep the two remaining R1a samples (HEVC and 1 GB) for the owner's re-check.
