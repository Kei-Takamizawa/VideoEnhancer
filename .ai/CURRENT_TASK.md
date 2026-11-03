# CURRENT_TASK: VE-R1d-4 (remove face posters, manual "set as thumbnail", seek thumb stays on playback position)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1d-4
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #20), on top of VE-R1d-3 at a8ebb1d.
- Write a new `.ai/LAST_REPORT.md` for VE-R1d-4; keep the older reports below it. Same isolation rules as before (do not touch the real service, home or library). Record disk baseline and growth.
- **Budget:** the owner's Codex weekly limit is nearly used up (4 % left). Keep this cycle small: read only the files you need, no screenshots, no browser suite, no desktop E2E suite. Run only the checks listed in section 3. If you hit the usage limit, stop and report the state; do not retry.

## 1. Owner requests (2026-11-03 14:06Z)

1. Drop face-based thumbnail selection.
2. On the video page, let the owner set any frame as that video's thumbnail.
3. While hovering over the seek bar, the round thumb follows the cursor. It must stay at the playback position; only the preview follows the cursor.

## 2. Work

1. **Remove face selection:** delete `src/videoenhancer/remote/faces.py` and `tests/test_remote_faces.py`; posters go back to the R1c rule (10 %, skip dark frames). Remove the face section and model licence text from `docs/REMOTE.md`. Bump the sidecar version so v2 face posters are regenerated once with the R1c rule (manual posters from item 2 are kept). At service start, delete `VE_HOME/models/face/` if it exists (only that folder; log one line).
2. **Set as thumbnail:**
   - API: `POST /api/library/{id}/poster` with JSON `{"time": <seconds>}` (device cookie, same Host/Origin/private-source checks as other POSTs; 0 ≤ time ≤ duration; 400 otherwise). It writes the poster at that exact time (same size and format as now) and records `{"source": "manual", "time": ...}` in `poster.json`. A manual poster is never replaced by background regeneration or version bumps. The new ETag changes so clients reload it.
   - UI: on the video page, a small low-key **Set as thumbnail** button with the page actions under the video (next to Download and Delete), using the current playback time; on a Mac also the key `T`. Show "Thumbnail updated." briefly. The Library shows the new poster on return (update that card's image only).
3. **Seek thumb:** hovering (mouse, no button pressed) only moves the preview; the range value and thumb stay at the playback position. Only a press/drag on the bar changes the value and seeks.

## 3. Checks (minimal)

- Python: one test file for the poster API (cookie required, bad time 400, manual poster written and kept across a version bump) and the face-folder cleanup at start.
- Node: one test that hover does not change the seek value and drag does.
- `ruff check`, `ruff format --check`, `uv run pyright` (as in CI, also without onnxruntime), the CI CPU pytest command, and the node tests. Nothing else.

## 4. Allowed files

`src/videoenhancer/remote/**`, `tests/**`, `docs/REMOTE.md`, `docs/API.md`, `.ai/LAST_REPORT.md`.

## 5. Done when

Sections 2 and 3 pass and the diff has only allowed files.

## 6. Operator after the commit (after designer review)

`ve remote restart`, `ve remote status`. Then stop: the owner asked to pause all work after this cycle.
