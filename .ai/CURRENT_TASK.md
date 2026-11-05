# Task ID: VE-R1e-2 (finish VE-R1e on the same branch)

Read AGENTS.md first. Continue from commit 072f377 on branch `claude/project-thread-yyrl3q`. Keep everything VE-R1e built; this cycle answers the three blockers in the VE-R1e report, then runs the full checks.

## 1. Designer decisions

### 1.1 Upload recovery (blocker 1)
- When a start is refused because the same device has an unfinished upload, the 409 response body includes that upload's public fields: `id`, `name`, `size`, `offset` (never `device` or paths).
- Add `DELETE /api/uploads/{id}`: only the device that owns the upload may cancel it; it removes the partial folder and returns 204. Unknown id or another device: 404. Cancelling a finished (`ready`) upload that is already queued as a job is refused (409).
- Client, on a 409 start:
  - If the chosen file has the same `name` and `size` as the returned upload, resume it from the server's `offset` (the server offset is the truth) and store a resume record for that id.
  - Otherwise show one plain message, "Another upload from this device is unfinished.", with two buttons: **Resume it** (asks the owner to pick that file again; matching name and size resumes) and **Cancel it** (calls DELETE, then starts the new upload once).
- No idle lease. The 24-hour sweep stays as is.
- Tests: lost-start-response path (start, drop the id, start again with the same file resumes; with another file, cancel then start works), DELETE ownership and ready refusal, client busy state through the recovery path.

### 1.2 Private failure logs (blocker 2)
- You may now edit `src/videoenhancer/schedule/controller.py`, but only the error logging at the segment-failure branch (manifest/result error, around line 1433), the latest-error log (around line 1500) and the controller exception branch (`job_logger.exception("Controller error", ...)`, around line 1747), plus any other `job_logger` call in that file that writes raw error text or tracebacks.
- Route them through `remote/diagnostics.py` (or a small shared helper it uses): log the stage, the classified reason, the exception type and the sanitised traceback locations (file name and line, no arguments, no messages, no paths, no names, no URLs).
- Do not change the controller's behaviour, return values, manifest content or retry logic. Only what is written to the log changes.
- Test: drive a segment failure and a controller exception with a fake error message containing a fake file name, path and URL, and prove none of them reach any log record, while stage and type do.

### 1.3 Preparation failure detail (blocker 3)
- In `service/engine.py`, the preparation exception handler must not overwrite the failure detail that `_error` wrote: reload or merge before saving. Add a test with a real preparation failure that checks the stored stage and reason survive.

## 2. Checks (all must be run on the final code)
- ruff check, ruff format --check, pyright (also the no-onnxruntime variant used in CI).
- The VE-R1e Python and Node tests, plus the new ones.
- The full CPU pytest suite to completion. Report pass/fail counts.
- No browser suite, desktop E2E or GPU suite.

## 3. Allowed files
VE-R1e's allowed files, plus `src/videoenhancer/schedule/controller.py` (logging lines only, as above) and `.ai/LAST_REPORT.md`.

## 4. Done when
All three decisions are implemented and tested, every check in section 2 passes, and LAST_REPORT.md for **VE-R1e-2** says COMPLETED with the counts. Scratch cleanup as usual; a refused scratch delete alone does not make the cycle PARTIAL (list it for the operator).

## 5. Operator after the commit
Wait for designer review. Then the designer will ask for `ve.exe remote restart` and `ve.exe remote status`.
