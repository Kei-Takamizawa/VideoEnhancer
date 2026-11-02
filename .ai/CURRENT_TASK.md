# CURRENT_TASK: VE-R0c (iPad spike: make Web Push send succeed, download without trapping the app)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R0c
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file (on top of ab45b12, VE-R0b). PR #16 continues.
- New `.ai/LAST_REPORT.md` for VE-R0c; move the VE-R0b report below it under `## Previous: VE-R0b` (keep the older sections too).
- Same rules as VE-R0b. Spike only; `spikes/ipad/**` and `.ai/LAST_REPORT.md` only.
- Do not re-run the legacy desktop E2E suite in this cycle (the desktop GUI is being retired; its two local failures are known and unrelated). Run the spike suites, `uv run ruff check .`, `uv run ruff format --check .`, and the CPU pytest command CI uses.

## 2. Owner re-check results (2026-11-02 05:09-05:17 UTC, Home Screen app, iPadOS 27.2)

- In-app pairing worked: `POST /pair/claim` 200 in standalone mode; no 401 after pairing. T1, T2 pass.
- **T3:** permission `granted`, `PushManager` present, subscription stored (endpoint host `web.push.apple.com`). Both sends (+10 s, +60 s) raised `pywebpush.WebPushException`; the server logged only the class name, so the HTTP status and reason are unknown. The PC reaches `web.push.apple.com:443`. Designer's reading (unverified): the VAPID claim uses `sub: mailto:spike@example.invalid` (server.py around line 570), and Apple's push service rejects a JWT whose subject is not a real `mailto:` or `https:` contact (403 `BadJwtToken`).
- **T6 in the Home Screen app:** tapping the 1 GB download link opened a full-screen download view with **no back or close control**; only relaunching the app returned to it. No background observation was recorded.
- **T7:** 500 MB loaded in 3.7 s, share sheet returned, **Save Video to Photos passed**.

## 3. Work

1. **Push diagnostics.** On every send failure record `exc.response.status_code` and Apple's `reason` from the JSON body (for example `BadJwtToken`), plus the `apns-id` response header if present. Never record the endpoint path, keys or tokens.
2. **Push fix.** Make the VAPID `sub` a real contact. Use `https://github.com/Kei-Takamizawa/VideoEnhancer` by default, overridable with a `--vapid-subject` flag. Do not put any personal e-mail address into the repository. Keep `exp` within 24 hours and check the JWT `aud` equals the push endpoint's origin. Add a unit test that decodes the generated VAPID JWT and asserts `sub`, `aud` and `exp`.
3. **Prove the send path from the PC.** Add a `--push-selftest` option that, given a stored subscription in the spike home, sends one push and records the status and reason. The operator will run it after the owner subscribes; it must not require a code change.
4. **Download inside the Home Screen app.** Offer three variants on the T6 screen and record which one the owner picks as usable:
   - **A:** link with `target="_blank"` (expect it to open an in-app browser sheet with a Done button);
   - **B:** fetch the file into a Blob in the page, then `navigator.share({files:[...]})` so the owner can choose "Save to Files" or "Save Video" (like T7);
   - **C:** the current `Content-Disposition: attachment` link, kept only for comparison, with a visible warning that it may trap the app.
   For each variant record: started, finished (if observable), whether the app returned without relaunch (owner taps), and the time. Variant B must handle 500 MB and 1 GB and record a memory failure if the page is killed (as T7 does).
5. **Owner check addendum.** Add "R0c re-check, about 3 minutes" to `spikes/ipad/OWNER_CHECK.md`: the app is already installed and paired, so no new pairing unless the server home was cleaned (then use `--redo-pairing` and **Pair this app**). Steps: T3 again (allow, close the app, wait 75 s); then T6 variants A and B with 500 MB, tapping whether the app returned normally.

## 4. Tests

Spike unit tests (VAPID JWT fields, failure record contains status/reason and no secrets, `--push-selftest` parsing), the spike JS tests, `ruff check`, `ruff format --check`, and the CI CPU pytest command. Do not leave the server running.

## 5. Done when

Section 3 is implemented, section 4 passes, and the report gives the exact commands to start the server (keeping the existing paired device and subscription if the spike home still exists) and to run `--push-selftest`.
