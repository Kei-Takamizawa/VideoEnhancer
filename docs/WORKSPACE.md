# Workspace and disk budget

All local cycle work belongs under `D:\my-workspace\VideoEnhancer\work`:

| Folder | Purpose |
| --- | --- |
| `repo` | Git checkout and its `.venv`; run Git here |
| `package` | The single current `VideoEnhancer-win32-x64` package |
| `evidence/<cycle>` | Reports, JSON measurements, logs and essential screenshots |
| `scratch` | Isolated test homes, generated media and temporary outputs |
| `cache` | Recipe-keyed reusable fixtures, GPU test model home and tool caches |

`D:\my-workspace\VideoEnhancer\VE-check` and `D:\my-workspace\VideoEnhancer\AppData` belong to the owner. Never clean, prune, move or write them during development. Exclude them from every growth gate; measure their sizes only when asked. Do not touch anything else in `D:\my-workspace` outside `work`.

## Session environment

Use a Git-ignored `repo/local-env.ps1` and dot-source it before installing, building or testing. Set `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `npm_config_cache`, `PLAYWRIGHT_BROWSERS_PATH`, `ELECTRON_CACHE`, `HF_HOME`, `TORCH_HOME`, `TEMP` and `TMP` to subfolders of `work/cache` or `work/scratch`. Use an isolated `VE_HOME` under scratch and `VE_GPU_TEST_MODEL_HOME` under cache. These variables apply only to the current shell or command. Never change system or user environment variables, long-path policy, drivers or Recycle Bin settings.

Windows-managed event logs, crash reporting and application compatibility data can still be written to the system drive. The Codex host's own installation, sessions and runtime are outside this project's control. Do not clean these as project cache. Electron's owner-facing folder-location preference lives in Electron userData, outside the movable app data. Development GUI launches must use a user-data directory under scratch. Installed system FFmpeg and Git remain where the owner installed them; development does not modify them.

## Retention

1. Keep one package. Build a candidate within `package`, smoke-test it, then replace the old current package. Keep the old package until the candidate passes; delete the replaced one immediately afterward. Its `resources/engine-location.json` must reference this checkout on D.
2. Empty scratch at the end of each cycle, after saving the report's numbers as JSON in `evidence/<cycle>`. Never retain a synthetic file larger than 100 MB. Preserve no owner queue or media as a fixture.
3. Keep at most 300 MB of evidence per cycle and only the last three cycles. Delete older cycle evidence after retaining the required report in Git. P1e-2 evidence predates this rule and may exceed 300 MB; disclose its measured size instead of discarding it.
4. Cache reusable fixtures once, keyed by the exact recipe (including tools, dimensions, codec and duration). Keep the GPU test model home here. Cap the complete cache at 40 GB; prune the oldest entries first. Never regenerate a large fixture simply to leave another copy behind.
5. Before permanent cleanup, list every candidate path and its measured size in the cycle report. Delete only confirmed development artifacts. An automatic approval rejection is final: list the path under "For the owner to delete" and do not bypass it. Never inspect or clean the Recycle Bin.

## Report and growth gate

Every cycle report must show decimal GB:

- C and D free space at the start and end;
- current package, this cycle's evidence, scratch and cache sizes;
- bytes removed per cleanup item, measured independently from drive-wide free-space changes;
- persistent growth, which must be at most 1 GB unless the report explains the exception (for example, bootstrapping a new environment or downloading required models).

Do not sum overlapping inventory rows or equate logical file lengths with allocated disk space. Record access errors and incomplete attribution. Keep media, weights, packages, screenshots, caches, `node_modules`, build output and `local-env.ps1` out of Git. Keep private evidence and summaries outside the checkout. Do not rewrite historical measurements when files have been lost; disclose the loss and reference the original report's Git revision.
