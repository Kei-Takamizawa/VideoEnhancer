# CURRENT_TASK: VE-R1e (reliability: failure logging, one upload at a time, faster streaming, shorter engine lock)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1e
- **Date:** 2026-11-05
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file, on top of `main` a67c62c (PR #20 merged). A new draft PR follows.
- Write a new `.ai/LAST_REPORT.md` for VE-R1e; keep the older reports below it. Same isolation rules as before: do not touch the real service, home or library; no dependency changes. Record disk baseline and growth.
- **Budget:** the Codex weekly limit is low. Read only the files you need; no screenshots; run only the checks in section 3. If you hit the usage limit, stop and report the state.
- **Cleanup:** delete every scratch folder this cycle creates. If a delete is refused, list the paths and sizes; the operator deletes them, and that alone does **not** make the cycle PARTIAL. The known local `p1f3-visual` failure does not make it PARTIAL either.

## 1. Owner report and log findings (2026-11-05, read-only analysis of the real logs; no video content was opened)

The owner says URL jobs and uploads are unstable, and asks for faster streaming without lower quality. From `videoenhancer.jsonl` (2026-11-03 14:00Z to 11-05 05:08Z):

1. **URL jobs:** 3 of 9 failed (11-05 01:52, 01:56, 02:05) with 0 s processing time after probing succeeded (816p/767 s; 1080p/1,484 s twice). The cause cannot be found: `activity.log` writes only "processing" for every failure (`remote/jobs.py` ~57), remote job folders are deleted at the end, the link-job error (`service/link_jobs.py` ~313) is never logged, the service runs under `pythonw` so stderr is lost, and gateway exceptions log only the status code. Dropped connections are not logged at all (`gateway.py` ~269).
2. **Engine lock:** 402 warnings "engine lock held over 5 s" on 11-04 while processing (365 from `_progress`, `service/engine.py` ~353; 37 from the notification status collection, ~1113). During those windows job status took up to 9.4 s, job add 7–12.8 s, an upload chunk 7.4 s.
3. **Uploads (client):** in `remote/web/add-ui.mjs` (~155) the busy flag is cleared before the upload starts, so a second upload can start while the first runs; the resume record has a single slot, so the second upload overwrites it, and **Add** on the first (~133–134) deletes the second's record. On 11-05 a second upload (908 MB) started during the first and stopped at 77 %, and could not be resumed.
4. **Streaming:** 2,259 range responses (median 16 ms, p95 265 ms). Every video response sends `Connection: close` (`gateway.py` ~772), so Safari opens a new TLS connection for every range request (about 6 per second while scrubbing). Library files are AV1 10-bit MP4 with `moov` first and keyframes about every 2 s.
5. **Manual thumbnail on a long video:** one POST to the library took 600 s and failed (500) right after a 12.5 GB video; three library POSTs returned 503 on 11-04.

## 2. Work

1. **Failure logging (no names, no URLs, no file paths):**
   - Log every job failure with its stage (download, probe, enhance, encode, publish, cleanup), the exception type and a short message with library or home paths and URLs replaced by placeholders. Write the stage and a short reason to `activity.log` instead of only "processing".
   - Log the link-job error from `link_jobs.py`.
   - For unhandled gateway exceptions, log the route class, exception type and a sanitised traceback (file and line numbers only, no locals).
   - Log dropped client connections (route class, bytes sent so far, elapsed time) at info level.
   - Log bytes sent for video range responses.
   - Since the service runs under `pythonw`, also write Python warnings and uncaught thread exceptions to the log (for example `logging.captureWarnings` and `threading.excepthook`).
2. **One upload at a time (client):** keep the busy state from the moment an upload is chosen until it finishes, fails or is cancelled; while busy, the Upload control shows "Uploading… (one at a time)" and cannot start another. Store resume records per upload id (a small map, not one slot); **Add** removes only its own record; on open, offer **Resume upload** for each unfinished upload the server still has. The server refuses a second concurrent upload *start* from the same device with a clear 409 message.
3. **Faster streaming, same bytes:** for video range responses use HTTP/1.1 keep-alive (no `Connection: close`) with a sensible idle timeout (about 30 s, and close after about 100 requests per connection); keep `Content-Length` exact so the connection stays usable; raise the read and write block to 1 MiB; make sure an aborted range (client stops reading) frees the thread quickly and logs it. Do not transcode or change the files. **Device caching (owner OK 2026-11-05, "do not keep it forever"):** for library video range responses send `Cache-Control: private, max-age=86400` plus a strong `ETag` and `Last-Modified` derived from file size and mtime, and answer `If-Range` correctly (full 200 when it does not match). Never add `immutable`; never cache API JSON, pairing, setup or download-link responses (those stay `no-store`). When a library video is deleted, the delete response sends `Clear-Site-Data: "cache"` (cache only, never cookies or storage) so cached bytes of the deleted video do not stay on the device. Document in docs/REMOTE.md that the browser keeps cached parts for at most one day and drops them earlier on its own. Add a test for the headers, the ETag/If-Range behaviour and the delete header.
4. **Shorter engine lock:** in `_progress` and the notification status collection, copy the needed state under the lock and do slow work (file I/O, JSON writes, estimates) outside it. Target: no lock hold over 1 s during a CPU test job; keep the existing warning.
5. **Manual thumbnail on long videos:** seek with input-side `-ss` (before `-i`) so the frame is found in seconds; give up after 30 s with a clear message instead of 600 s.

## 3. Checks (minimal)

- Python: tests for the sanitised failure log (no path or URL in the output), link-job error logging, keep-alive on two consecutive range requests over one connection, aborted range logging, second upload start 409, lock hold under 1 s with a fake slow writer, and the manual poster seek time on a generated long clip (CPU, small).
- Node: busy state across the whole upload; per-id resume records; Add removes only its own record.
- `ruff check`, `ruff format --check`, `uv run pyright` (also without onnxruntime as in CI), the CI CPU pytest command and the node tests. No browser suite, no desktop E2E.

## 4. Allowed files

`src/videoenhancer/remote/**`, minimal changes in `src/videoenhancer/service/engine.py`, `service/link_jobs.py` and the service logging setup, `tests/**`, `docs/REMOTE.md`, `.ai/LAST_REPORT.md`.

## 5. Done when

Sections 2 and 3 pass, the diff has only allowed files, and the report lists the checks and short owner re-check steps (one URL job, one upload while trying to start a second, scrubbing a long video).

## 6. Operator after the commit (after designer review)

`ve remote restart`, `ve remote status`.
