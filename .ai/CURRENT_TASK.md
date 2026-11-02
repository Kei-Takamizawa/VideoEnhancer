# CURRENT_TASK: VE-R0 (iPad web app spike: HTTPS, pairing, push, upload, playback)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R0
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 0. Why this cycle exists

The owner changed the product direction on 2026-11-02:

- The desktop window (Tauri GUI, mpv player, Compare, History, Schedule, previews) will be retired. The PC side becomes a headless engine service that starts at Windows sign-in and shows nothing on the PC.
- The only user interface becomes a **web app on the owner's iPad** (Safari, added to the Home Screen), used **only on the home Wi-Fi**.
- The iPad adds jobs by **pasting a URL**, by the **share sheet**, or by **uploading a video from the iPad** (Photos or Files). Before adding, it shows a **predicted finish time**. There is no live progress; the iPad gets a **push notification** when a job completes or stops with an error.
- Finished videos stay on the PC in a **library folder** on drive D. The web app can **stream-play**, **download** and **delete** them. Sources and intermediate files are deleted when processing ends. No job history is kept. A one-line log without names or URLs (time, result, duration) is kept.
- HTTPS uses a **certificate authority that the app creates**, installed on the iPad once by the owner.
- **Pairing:** the **first iPad that opens the pairing page** within **2 minutes** after install becomes the trusted device; the window closes the moment it is claimed. A Start-menu shortcut "Redo pairing" reopens the window for 2 minutes. No QR code, nothing shown on the PC.
- HDR support (old P1g) is dropped. Streaming processing (process while downloading) is not wanted.

R0 is a **spike only**: it proves or disproves, on the real iPad, the browser features that the product plan depends on. It changes **no product code**. Everything goes under `spikes/ipad/`.

## 1. Start

- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file (based on `main` 05852c8).
- Write a new `.ai/LAST_REPORT.md` for VE-R0. First lines: the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- Usual rules: every written path under `D:\my-workspace\VideoEnhancer\work\`; isolated homes and generated media under `work\scratch\`; never touch `VE-check`, `AppData` or the owner's normal app.
- Spike-only Python dependencies (for example `cryptography`, `zeroconf`, `pywebpush`) may be installed with `uv` into a spike-only environment under `work\cache\` or declared as inline script metadata. Do **not** add them to the product `pyproject.toml` or `uv.lock`.
- Do not change Windows settings (firewall, network profile, certificates in the Windows store). If Windows asks to allow the spike through the firewall, that is an owner step (section 5).

## 2. What to build (`spikes/ipad/`)

One small Python spike server plus a static test web app. Keep it self-contained and readable; it is a measuring tool, not product code.

### 2.1 Server

1. **Certificates.** On first run, create a local root CA (name it "VideoEnhancer Local CA (spike)") and a server certificate signed by it. SANs: the fixed name `videoenhancer.local`, the PC's own `<PCNAME>.local`, and the PC's current private LAN IPv4 addresses. Keys and certificates live in the spike home under `work\scratch\`. Validity of the server certificate must satisfy Apple's rules for TLS server certificates (at most 398 days; SHA-256; key usage and extended key usage set; SAN present). Explain in the report which rules you checked.
2. **Two listeners on the LAN** (bind to the private LAN address(es), not `0.0.0.0` if avoidable):
   - plain HTTP on port 8080: only the pairing claim (2.2) and the CA download (`/ca.mobileconfig` with the CA as a configuration profile, plus `/ca.crt`). Nothing else.
   - HTTPS on port 8443: everything else.
3. **Name.** Advertise `videoenhancer.local` on mDNS (for example with `zeroconf`). Report whether Windows' own mDNS responder conflicts, and whether `<PCNAME>.local` works as a fallback.
4. **Auth.** Every HTTPS request except the PWA's static files needs the device token from pairing (cookie set with `Secure; HttpOnly; SameSite=Strict`, or a bearer header, your choice; report it). Unpaired requests get 401. Check `Host` and `Origin` against the allowed names.

### 2.2 Pairing (trust the first iPad)

- The window opens when the server starts in "fresh install" mode and lasts **120 seconds** (configurable for tests).
- The **first** `GET http://<name>:8080/pair` inside the window claims it: the server creates a device record and a one-time claim secret, closes the window at once, and answers with a page that (a) links to the CA profile and the install steps, and (b) links to `https://<name>:8443/pair/finish#<claim secret>`. The finish page exchanges the secret for the long-lived device token over HTTPS. The claim secret expires after 30 minutes or first use.
- Every later `/pair` request, and every request after the window, gets a fixed "pairing is closed" page.
- A CLI flag `--redo-pairing` reopens the window for 120 seconds (stands in for the Start-menu shortcut).
- Store only a hash of the device token on the PC.

### 2.3 Test web app (served over HTTPS)

A single-page PWA (manifest, service worker, iPad-friendly layout) with one button per test. Each test records its result by POSTing JSON to the server, which appends it to `work\evidence\VE-R0\ipad-results.jsonl` with a timestamp and the user agent. The owner should only need to tap; every result is recorded automatically. Tests:

| ID | Test | Recorded result |
| --- | --- | --- |
| T1 | Page loaded over HTTPS with the private CA, no warning | pass/fail (owner taps "I saw no warning" or "I saw a warning") |
| T2 | Home Screen install detected (`display-mode: standalone`) | pass/fail |
| T3 | Web Push: ask permission, subscribe (VAPID), server sends a test push 10 s later and again 60 s later while the app is closed | subscription ok; service worker posts back on receipt; owner taps "I saw it" when reopening |
| T4 | Upload: pick a video from Photos and from Files, upload in chunks with resume after a forced disconnect | MB/s, chunk size, resume ok, file hash matches on the PC |
| T5 | Playback: stream-play generated 1080p60 samples in H.264, HEVC and AV1 (MP4, faststart) with HTTP Range | `canplay` time, first frame time, seek time to 50 % and 90 %, errors per codec |
| T6 | Download: download a ~1 GB sample to Files with `Content-Disposition: attachment` | time, MB/s, whether it continued when the app went to the background for 30 s and for 3 min |
| T7 | Save to Photos: offer the sample through the share sheet (`navigator.share` with a file) and report size limits or failures | pass/fail per size (50 MB, 500 MB, 1 GB) |
| T8 | Paste a URL from the clipboard into a field; receive a URL from the share sheet (Web Share Target, if iPadOS supports it for Home Screen web apps; report if not) | pass/fail |
| T9 | Live status after sleep: keep an SSE connection, lock the iPad for 1 minute, unlock, check that the page recovers | pass/fail, reconnect time |

Generate the T5 to T7 samples locally with FFmpeg from synthetic sources (no downloads from video sites). Keep every generated media file under `work\scratch\` and delete it at the end of the cycle; samples are never committed.

## 3. Automated checks on the PC (before the owner check)

Run these yourself, record them in the report, and fix the spike until they pass:

1. Unit tests for certificate fields, pairing window (open, claim, close, expiry, redo, second claimer rejected), token hashing, Host/Origin checks, 401 for unpaired requests, chunked upload with resume and hash check, HTTP Range responses (`206`, correct `Content-Range`, open-ended and suffix ranges).
2. A Playwright run with **WebKit** and the `iPad Pro 11` device profile against the LAN address over HTTPS (trust the spike CA in the test browser context only), covering the pairing flow, T4, T5 (H.264 at least) and T6. Report what WebKit on Windows can and cannot show compared with real iPadOS Safari.
3. Measure LAN-free numbers on the PC (loopback) for upload and download MB/s as a baseline.

## 4. Owner check sheet

Write `spikes/ipad/OWNER_CHECK.md` in English: numbered, plain steps for the iPad, about 15 minutes, written for a non-engineer. It covers: open `http://videoenhancer.local:8080/pair` within the window, install the CA profile, turn on full trust in Settings > General > About > Certificate Trust Settings, open the finish link, add to Home Screen, then run T1 to T9 by tapping. It must say how to restart the window (`--redo-pairing`) if two minutes pass, and how to remove the CA profile afterwards. The designer will translate it for the owner.

The operator starts the spike server and leaves it running for the owner check; the owner check itself happens after this Codex run.

## 5. Owner steps that Codex must not do

- Allowing the spike server through Windows Defender Firewall (Private networks only) when Windows asks.
- Everything on the iPad.

List these in the report under "For the owner".

## 6. Report (`.ai/LAST_REPORT.md`)

- Status line; what was built; how to start the server (exact command).
- Section 3 results with numbers.
- A table T1 to T9 with "PC automated result" filled in and "iPad result" left as `pending owner check`.
- Known limits and risks you found (for example Web Push with a private CA, mDNS name conflicts, AV1 decode on older iPads, background download behavior).
- Changed files; disk table from `docs/WORKSPACE.md`; "For the owner".

## 7. Allowed files

- `spikes/ipad/**` (code, static web app, tests, `README.md`, `OWNER_CHECK.md`)
- `.ai/LAST_REPORT.md`

Nothing else. No product code, no `pyproject.toml`, no `uv.lock`, no `gui/`, no CI workflow changes. No media, certificates, keys or tokens in the repository.

## 8. Done when

- Section 3 passes and is reported with numbers.
- The spike server runs on the PC and serves the pairing page and test app on the LAN.
- `OWNER_CHECK.md` exists.
- Status is COMPLETED when all of the above hold; the iPad results are filled in by the designer after the owner check.
