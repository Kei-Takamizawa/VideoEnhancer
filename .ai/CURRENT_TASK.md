# CURRENT_TASK: Migration check run

- **Task ID:** VE-MIG-1
- **Date:** 2026-10-21
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex, started by the operator (Claude on the Windows PC) with `codex exec`
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Purpose

Prove the new route end to end before real work goes through it: the cloud designer writes this task, the operator checks out the branch and starts you, you restore dependencies and run the checks, the operator commits your report.

**Change no product code, test code, configuration or documentation.** The only file you write in the repository is `.ai/LAST_REPORT.md`.

## 2. Start

- Read `AGENTS.md` first. It replaces the per-task working rules of earlier cycles.
- The operator has checked out the branch that contains this file. Do not run Git commands that change anything.
- Your working folder is `D:\my-workspace\VideoEnhancer\work`. Dot-source `work\repo\local-env.ps1` in every shell.
- Use `work\scratch\VE-MIG-1` for every temporary file: `VE_HOME`, `TEMP`, `TMP` and pytest `--basetemp`. Keep evidence in `work\evidence\VE-MIG-1`.

## 3. Steps

1. **Disk at start:** C and D free space, and the sizes of `work\cache`, `work\package`, `work\scratch` and `work\repo`, as in `docs/WORKSPACE.md`.
2. **Restore dependencies** (P1f-2 removed them to save space):
   - `uv sync --locked --all-extras` in `work\repo`;
   - `npm ci` in `work\repo\gui`;
   - the Cargo registry and Rust target through a normal `cargo build --manifest-path gui/src-tauri/Cargo.toml`.
   - Report the restored size on its own line. It does not count toward the 1 GB growth limit.
3. **Python checks:** `ruff check .`, `ruff format --check .`, `pyright`, and `pytest -m "not gpu and not soak"`.
4. **Flaky test (diagnostic only, no fix):** run `tests/test_p1f2_review.py::test_a1_unreadable_history_folder_undo_and_cleanup` five times. Report the pass and fail count for each parameter and the failure text. It failed once on `main` CI (run 39538012425) and passed twice on the same code.
5. **GPU smoke:** `pytest tests/test_media.py tests/test_pipeline.py -m "gpu and not soak"` with `VE_GPU_TEST_MODEL_HOME` under `work\cache`. Report the duration.
6. **GUI and Rust:** in `gui`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`; then `cargo fmt --check`, `cargo clippy -- -D warnings` and `cargo test` for `gui/src-tauri`. Do not rebuild or replace the owner's package.
7. **Cleanup:**
   - Delete the dependency folders you restored in step 2 (uv and npm caches, Cargo registry, Tauri target, `gui\node_modules`, `gui\dist`) after listing each path and size, as P1f-2 did. Keep `.venv`, the toolchains and the GPU test model cache.
   - Empty `work\scratch` from inside the sandbox.
   - If any delete is refused, list the exact path and size under "For the owner to delete" and do not work around it.
8. **Disk at end**, in the same form as step 1, plus the persistent growth.

## 4. Report (`.ai/LAST_REPORT.md`)

- Status line: COMPLETED, PARTIAL or BLOCKED, with Task ID VE-MIG-1.
- A table of steps 1-8 with PASS / FAIL / NOT RUN, duration, and evidence file names.
- **Escalations:** every command that left the sandbox, and whether the automatic reviewer approved or refused it. Quote any refusal text.
- Anything that failed only because of the sandbox (for example "Access is denied" or a missing program) on its own list, with the exact command and text.
- The disk table and "For the owner to delete".
- "Questions for the designer", each with the default you chose.

## 5. Do not

- Change any file in the repository other than `.ai/LAST_REPORT.md`.
- Touch the owner's folders, queue, settings, videos, models or Recycle Bin.
- Download anything except the project's locked dependencies.
- Run Git commands that change anything.
