# CURRENT_TASK: VE-R1d-3 (CI pyright fix for the optional onnxruntime import)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1d-3
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #20), on top of VE-R1d-2 at d751d9e.
- Write a new `.ai/LAST_REPORT.md` for VE-R1d-3; keep the older reports below it. Same isolation rules as VE-R1d-2. Record disk baseline and growth. The known local `p1f3-visual` failure does not make the cycle PARTIAL.

## 1. Problem

CI `cpu (ubuntu-latest)` on d751d9e fails in `uv run pyright`:

```
src/videoenhancer/remote/faces.py:120:16 - error: Import "onnxruntime" could not be resolved (reportMissingImports)
src/videoenhancer/remote/faces.py:194:12 - error: Import "onnxruntime" could not be resolved (reportMissingImports)
```

CI installs no `models` extra, so `onnxruntime` is absent there. Your local pyright passed because the live `.venv` has `onnxruntime-gpu`.

## 2. Work

1. Mark both optional imports the same way the repository already does in `src/videoenhancer/bench/scrfd.py:132` (`# pyright: ignore[reportMissingImports]`). Do not change behaviour.
2. Prove it: run pyright in an environment **without** `onnxruntime` (for example a scratch venv synced with the CI command, or `uv run --no-extra models pyright` if that reproduces CI), show the two errors before the fix and 0 errors after. Report the exact command.
3. Run `ruff check`, `ruff format --check`, the CI CPU pytest command and the node tests. The desktop E2E suite is not needed for this one-line change.

## 3. Allowed files

`src/videoenhancer/remote/faces.py`, `.ai/LAST_REPORT.md`.

## 4. Done when

Pyright reports 0 errors without `onnxruntime`, the other checks pass, and the diff has only the allowed files.
