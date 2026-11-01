# CURRENT_TASK: VE-P1e-3d2c (Windows CI: a finished job's warm worker still holds its part log)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3d2c
- **Date:** 2026-11-01
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47` at 654bd35 (VE-P1e-3d2b, COMPLETED) plus this task commit. The operator pushes to the same branch; PR #15 continues.
- Write a new `.ai/LAST_REPORT.md` for VE-P1e-3d2c. First lines: the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`. Keep the P1e-3d2b report content below it (or move it to the bottom under a heading); do not delete the gate results.
- Same rules as before: do not stop for a question, isolated homes under `work\scratch\`, every written path under `D:\my-workspace\VideoEnhancer\work\`, never touch the owner's normal app.
- This is a small cycle. No calibration or gate jobs.

## 2. The failure

GitHub Actions `cpu (windows-latest)` failed twice on 654bd35 (runs 41316632739 and 41316637780) with the same error; Linux passed:

```
FAILED tests/test_service.py::test_cpu_queue_sse_controls_and_completed_output - HTTPError 400
HTTP failure: DELETE queue/<id>: 400: {"error": "[WinError 32] The process cannot access the file because it is being used by another process: '...\\home\\jobs\\<id>\\logs\\seg_00000.log'"}
```

The test waits until both jobs are `done`, then deletes the first job. The delete fails because a process still has that job's `seg_00000.log` open.

Designer's reading (unverified): since P1e-3d1 the part worker is reused (`ProcessExecutor(reuse=True)`). The child redirects its output to the part log. When a job's last part finishes, the worker stays alive until the next scheduler loop closes it (`controller.py` around the "A cancelled/paused/finished job must release its idle GPU worker" block), so the job can be `done` while its worker still holds the log. Deleting a just-finished job from History on Windows can then fail for the owner too. The same race may also delay freeing GPU memory after a job.

## 3. Work

1. Reproduce it on Windows: run the test in a loop (at least 20 times) on the current branch and report how often it fails. If it never fails locally, add a deterministic test that holds the worker open past `done` with a fake, and show it fails before the fix.
2. Fix the cause, not the test:
   - Close the job's warm worker when the job has no more parts to run, before finalization starts and before the job is marked `done`. A worker must never outlive its job's last part.
   - Make sure the worker's log handle for a part is closed when that part ends, even if the worker is reused for the next part (each part has its own log file).
   - Do not change the worker-reuse rules from P1e-3d1 otherwise, and keep output bytes identical.
3. Optional and only if cheap: a short bounded retry in the History delete path for `WinError 32` is **not** a substitute for item 2. Do not add it unless item 2 alone is not enough, and then explain why.
4. Run the test 20 times in a row on Windows after the fix: 0 failures.

## 4. Allowed files

- `src/videoenhancer/schedule/controller.py` and `src/videoenhancer/service/engine.py`, for the worker life cycle and log handles only.
- `tests/**`.
- `docs/part-worker-lifecycle.md` (one or two lines).
- Nothing else.

## 5. Checks

- Full CPU suite, ruff, ruff format, pyright. The GPU suite `-m "gpu and not soak"` only for the worker tests it contains (`tests/test_warm_worker.py` and any GPU test touching the controller), not the full suite.
- A quick G5 check: one 30 s 1080p Standard H.264 fixture from P1e-3d1 section 7, output SHA-256 identical to the P1e-3d1 hash.
- Close everything you started; evidence under `work\evidence\VE-P1e-3d2c\`; report free space.

## 6. Report

- The reproduction rate before, the cause found, the fix, the 20-run result after, the G5 hash, changed files, and a 2-4 line Japanese summary.
- **COMPLETED** only if the test passes 20/20 on Windows, the hash matches, and every check passed.
