# CURRENT_TASK: VE-R0b (iPad spike: pairing inside the Home Screen app, request log, lint)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R0b
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file (on top of c4b7529, VE-R0 PARTIAL). PR #16 continues.
- Write a new `.ai/LAST_REPORT.md` for VE-R0b. First lines: Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`. Move the VE-R0 report below it under a heading `## Previous: VE-R0`; do not delete it.
- Same rules as VE-R0 (spike only, `spikes/ipad/` only, no Windows settings, paths under `work\`).

## 2. What the owner's iPad check showed (2026-11-02, iPadOS Safari 27.2)

In a normal **Safari tab** almost everything worked: T1 pass; T4 upload pass with resume (~20 MB/s); T5 H.264, HEVC and AV1 all played (canplay 112-516 ms, seeks under 150 ms); T6 1 GB download 9-19 s (52-114 MB/s) and continued in the background; T7 share sheet loaded 50 MB / 500 MB / 1 GB; T8 manual paste pass, clipboard read `NotAllowedError`, share target not offered by iPadOS; T9 reconnect 3.5 s after 6 min sleep.

But:

- **Opened from the Home Screen ("open as web app"), nothing worked**, and the server has **zero** records from standalone mode.
- **T3 Web Push never ran**: in the Safari tab, subscribe failed with "Web Push unavailable. Open from the Home Screen." Web Push on iPadOS works only in Home Screen web apps, and completion/error notifications are a core product requirement, so the product must run as a Home Screen web app.
- The server has no request log (`access_log=None`), so the standalone failure cannot be diagnosed from the PC.
- Designer's reading (unverified): a Home Screen web app has its own cookie and storage jar, separate from Safari. The pairing cookie set in Safari is not present in the app, so every API call is 401. Also, the claim is a plain-HTTP page on port 8080, which a standalone app opens in Safari (out of scope), so the app can never pair today.
- The 29 PC automated records were written into the same `ipad-results.jsonl` as the owner's, with a fake iPad user agent. That makes the evidence hard to read.
- CI `cpu (ubuntu-latest)` and `cpu (windows-latest)` fail at `uv run ruff check .`: 70 findings in `spikes/ipad/` (E501, E702 and others).

## 3. Work

1. **Pair inside the installed app.**
   - Keep HTTP `:8080` only for the CA download page and the first instructions. The CA is already trusted on the owner's iPad.
   - Add an HTTPS claim on `:8443` (for example `POST /pair/claim`) that works only while the pairing window is open, under the same rules as today: first claimer wins, the window closes at once, the token hash is stored, the cookie is `Secure; HttpOnly; SameSite=Strict`. The HTTP `/pair` claim may stay for Safari but must use the same window.
   - The PWA, when it has no valid session (any 401), shows one screen: "This app is not paired. Ask the operator to open pairing, then tap Pair this app." It calls the HTTPS claim from inside the app, so the cookie lands in the app's own jar.
   - Check the manifest `start_url` and `scope` so every page and API call of the test app stays inside the standalone app, and nothing bounces to Safari.
   - `--redo-pairing` replaces the old device (as today), so re-pairing from the app is possible after the Safari pairing.
2. **Request log for diagnosis.** Log one line per request to `work\evidence\<cycle>\owner-server.log`: time, method, path **without query string**, status, whether the device cookie was present (yes/no), and the `X-Display-Mode` header (step 3). No URLs from the owner, no file names, no tokens.
3. **Mark the mode on every record.** `app.js` sends `X-Display-Mode: standalone|browser` on every request and puts `display_mode` into every result record. T3 also records `Notification.permission`, whether `PushManager` exists, and only the **host** of the push endpoint.
4. **Separate files.** PC automated runs write to `pc-results.jsonl`; only the owner's iPad writes `ipad-results.jsonl`. Results from an owner session go to `work\evidence\VE-R0b\`.
5. **Lint.** Make `uv run ruff check .` pass on the whole repository without adding ignores for `spikes/ipad/` and without changing the ruff configuration. Fix the code.
6. **Owner check addendum.** Add a short section to `spikes/ipad/OWNER_CHECK.md` ("R0b re-check, about 5 minutes"): delete the old Home Screen icon; open the HTTPS address in Safari; Share > Add to Home Screen with "Open as Web App" on; open the app from the Home Screen; ask the operator for `--redo-pairing`; tap **Pair this app**; then run T2, T3 (allow notifications, close the app, wait for both pushes), T6 background 3 min, and T7 with **Save Video** to Photos at 500 MB, confirming in Photos.

## 4. Tests

- Unit tests for the HTTPS claim (window open/closed, first claimer wins, second rejected, redo replaces the device, cookie flags), the request log fields (no query string, no token), and records carrying `display_mode`.
- Rerun the existing spike suites and the PC verifier, writing to `pc-results.jsonl`. The known Windows WebKit codec/download limits from VE-R0 stay as they are; report them, do not try to fix them.
- `uv run ruff check .` and the repository's normal test commands that CI runs must pass.

## 5. Allowed files

`spikes/ipad/**` and `.ai/LAST_REPORT.md`. Nothing else.

## 6. Done when

All of section 3 and 4 hold, CI-equivalent lint and tests pass locally, and the report lists the exact command to start the server in `--redo-pairing` mode for the re-check. Do not leave the server running.
