# CURRENT_TASK: VE-R1b-2 (R1b fixes: CI regressions, abandoned uploads, notification lifetime, owner-check findings)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1b-2
- **Date:** 2026-11-02
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #18), on top of VE-R1b at 4da42f4.
- Write a new `.ai/LAST_REPORT.md` for VE-R1b-2; keep the older reports below it.
- Same workspace and isolation rules as VE-R1b. The owner's real remote service runs from this checkout. Do not start, stop, install or restart it; do not touch its home, library, task or firewall rules. No dependency changes in this cycle (do not run `uv sync` with a changed lock).
- Record a disk baseline at the start and report growth at the end, so this cycle can be COMPLETED.

## 1. CI regression: records whose `source` is `null` (must fix)

CI `cpu (windows-latest)` on 4da42f4 fails twice in a row in the desktop E2E tests `gui/tests/e2e/p1f2-review.spec.ts` and `p1f3-copy.spec.ts` (`damaged-record.mkv` never shows in History). `tests/p1f2_gui_seed.py` writes a job with `source=None`. R1b added `job.get("source", {}).get("remote")` in many places (about 17 in `src/`), which raises `AttributeError` when `source` is present but `null`, e.g. in the engine's start-up recovery loop, `_clean_cancelled`, `RemoteJobs.sweep`, `_watch` and `active`.

1. Add one small helper (for example `remote_info(job)` that returns the `remote` dict or `None` and tolerates a missing, `null` or non-dict `source`) and use it everywhere R1b reads `source.remote`.
2. Add a Python test that runs start-up recovery, sweep, active and cancel over a store that includes a `source: null` record and a non-dict `source`, and asserts no exception and that non-remote records are untouched.
3. Run the two failing E2E specs locally and report them passing.

## 2. CI flake: unauthenticated POST closes before reading the body

`tests/test_service.py::test_remote_shutdown_refusal_and_authenticated_pairing` failed once on Windows with `ConnectionAbortedError [WinError 10053]` on `POST remote/pairing` without a token (it passed on re-run). The loopback server likely answers 401 without reading the request body, then closes, and Windows resets the connection before the client reads the status line. In the loopback server (`service/server.py`) and the LAN gateway, read and discard a request body up to a small bound (for example 64 KiB) before sending an early error, or send `Connection: close` after draining; refuse larger bodies with 413 as now. Add a test that sends an unauthenticated POST with a body 50 times in a row and gets the error status every time.

## 3. Abandoned uploads (owner rule: the PC keeps nothing)

An upload that is never finished, or finished but never added as a job, currently stays in `VE_HOME/remote/incoming/` forever and counts toward reserved space.

1. Delete an unfinished upload with no chunk for 24 hours, and a finished upload not added to a job within 24 hours. Check at service start and then hourly. Never delete an upload that belongs to a job.
2. When the iPad resumes an upload that was deleted this way, show "This upload expired. Choose the video again." (the existing "no longer available" path is fine if the text matches).
3. Tests with a fake clock.

## 4. Notification lifetime

`push.py` sends with `ttl=3600`, so a Ready notification is lost if the iPad is off or out of the house for more than an hour. Use `ttl=86400` for Ready and Couldn't-finish, keep 3600 or less for the test notification. Update the test.

## 5. Upload lock scope

`Uploads.chunk` holds the global lock while reading up to 4 MiB from the network, and `finish` hashes the whole file (up to 20 GB) inside the lock, so a slow client or a large finish blocks every status call. Use a per-upload lock (or mark the upload busy under the global lock and do the network read and hashing outside it). Refuse a second concurrent chunk or finish for the same upload with a clear message. Test: a status call returns while another upload's finish is hashing.

## 6. Owner iPad check findings

None. The owner's iPad check of R1b passed on 2026-11-03 (notifications, URL job, upload, predicted finish roughly right, playback). Record this in the report.

## 7. Allowed files

`src/videoenhancer/remote/**`, minimal changes in `src/videoenhancer/service/engine.py`, `service/server.py` and `service/link_jobs.py`, `tests/**`, `docs/REMOTE.md`, `.ai/LAST_REPORT.md`. Do not change `gui/**` (the failing E2E tests must pass unchanged).

## 8. Done when

Sections 1 to 6 pass; `ruff check`, `ruff format --check`, the CI CPU pytest command, the node tests and the desktop E2E suite pass on Windows; the report lists test counts, the disk baseline and growth, and confirms the real service was not touched. The operator restarts the real service after the designer's review.
