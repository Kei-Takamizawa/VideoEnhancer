# CURRENT_TASK: Cycle P1e-2b (move the work to drive D and stop disk growth)

- **Task ID:** VE-P1e-2b
- **Date:** 2026-10-16
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Why:**
- The owner's drive C is full.
- Every cycle has left several GB behind: packages, synthetic media, finalization fixtures (up to 29 GB for a 120-minute output) and isolated homes.
- The owner wants all work on drive D from now on, with no unbounded growth.

**Start condition:**
- Branch `p1d-ui-v2` at `7347029` (draft PR #5).
- Save this file as `.ai/CURRENT_TASK.md` in the new checkout on D (Part B) and commit it there.
- **This cycle runs in a new Codex project** whose folder is `D:\my-workspace\VideoEnhancer\work`. The owner creates that folder and the project. The old checkout on C belonged to the previous Codex project. Because it is no longer your working folder, step B5 can delete it. Find it: it is a folder on C whose `origin` is this repository. If you are unsure which folder it is, ask the owner.
- At the end, write `.ai/LAST_REPORT.md` (English, UTF-8, ASCII punctuation, under 40 KB).
- Do not push to `main`.

## Working rules

1. **Never delete, move or open** any of the following:
   - the owner's videos and finished outputs;
   - anything in the Recycle Bin;
   - the owner's app data (`%LOCALAPPDATA%\VideoEnhancer`: queue, History, settings, models, logs), except by reading sizes in Part A;
   - the owner's folders next to your project folder: `D:\my-workspace\VideoEnhancer\VE-check\` (the owner's test copies) and `D:\my-workspace\VideoEnhancer\AppData\` (where the owner will move the app data). Either may already exist when you start.
     - Do not write to them or use them as scratch or test homes.
     - Do not include them in any cleanup.
     - They are outside your project folder on purpose, so the sandbox asks before any write there. Never request that approval;
   - anything in `D:\my-workspace` outside `D:\my-workspace\VideoEnhancer\work`, except the two owner folders' sizes if a report needs them.

   The owner moves their app data with the Part S feature.
2. **You may delete only what you created** for VideoEnhancer cycles: packages, synthetic media, isolated test homes, fixtures, caches and old checkouts.
   - List every path with its size in the report before deleting it.
   - Delete it permanently, not to the Recycle Bin, because the Recycle Bin on C would keep the space in use.
   - If the auto-approval refuses a deletion, do not work around it. Put the path and size under "For the owner to delete" in the report.
3. **Do not change system-wide settings:** no system or user environment variables, no driver settings, no Recycle Bin settings. Environment variables for one command or one session are fine.

## Part A: inventory (before changing anything)

Report a size table (decimal GB) for each of these:
- every `C:\Users\pro\Documents\VideoEnhancer-*` folder, and `C:\Users\pro\Documents\jobs`;
- the previous checkout on C (give its path), its `.venv`, `gui\node_modules` and build outputs;
- `D:\VideoEnhancer-P1e-2`, broken down by top-level subfolder;
- `D:\VideoEnhancer`, if it exists, broken down by top-level subfolder, saying which parts you created;
- the caches you used:
  - uv, pip and npm;
  - Electron's download cache and the Playwright browsers;
  - Hugging Face and torch hub;
  - the GPU test model home;
  - test leftovers in `%TEMP%`;
- the owner's app data, `%LOCALAPPDATA%\VideoEnhancer`, **sizes only**:
  - per top-level subfolder (jobs, models, logs, others);
  - the total size of part files (`seg_*.mp4`, joined files) left in failed and cancelled job folders.

  This is read-only: open no videos and change nothing.
- the free space on C and on D.

## Part B: one fixed workspace on D

The owner chose `D:\my-workspace\VideoEnhancer` for everything. Your Codex project folder is `work\` inside it. The owner's two folders sit beside it, outside the project folder.

```
D:\my-workspace\VideoEnhancer\
  work\                Codex project folder (yours)
    repo\              git checkout and its .venv
    package\           the current package only (VideoEnhancer-win32-x64\VideoEnhancer.exe)
    evidence\<cycle>\  reports, JSON, logs, screenshots
    scratch\           isolated test homes, synthetic media, temporary outputs
    cache\             reusable fixtures, GPU test model home, uv/npm/Playwright/Electron caches
  VE-check\            the owner's test copies (owner's: never touch)
  AppData\             the owner's app data after they press Move... (owner's: never touch)
```

**Git in the project.** The project folder `work\` is not a git repository, so the Codex app's own Git and pull-request actions will not find one. Run git inside `work\repo` as before.

**Path length.** The checkout path `D:\my-workspace\VideoEnhancer\work\repo` is 39 characters.
- If any tool (npm, the Electron packager, pip, git) fails on the 260-character path limit, report the path and the tool.
- Do not enable long paths system-wide (working rule 3). Shorten folder names inside `package\` or `cache\` instead, and say so in the report.

1. **New checkout.**
   - Clone `origin` into `D:\my-workspace\VideoEnhancer\work\repo` and check out `p1d-ui-v2` at `7347029`.
   - Create the `.venv` there from the lock file.
   - Run `ruff`, `ruff format --check`, `pyright`, the CPU tests, and the GUI lint, typecheck, unit tests and build, to prove the new checkout works.
2. **Caches on D for your own work only.** Set `UV_CACHE_DIR`, `npm_config_cache`, `PLAYWRIGHT_BROWSERS_PATH`, Electron's cache, `HF_HOME`, `TORCH_HOME` and `TMP`/`TEMP` for test runs, per session.
   - Use, for example, a git-ignored `local-env.ps1` that you dot-source.
   - Do not set them system-wide.
3. **Package.** Rebuild it into `D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-win32-x64\`.
   - Its `engine-location.json` must point at `D:\my-workspace\VideoEnhancer\work\repo`.
   - Repeat the P1e-2 smoke test.
   - The package must find the engine on D and never fall back to an old checkout.
4. **Evidence.** Move the P1e-2 evidence that the P1e-2 report refers to into `D:\my-workspace\VideoEnhancer\work\evidence\P1e-2`: reports, JSON, logs, the 92 screenshots, and the Japanese summaries.
   - Do not move synthetic media. It is regenerated when needed.
   - Update the paths in `.ai/LAST_REPORT.md` only in this cycle's report; do not rewrite the P1e-2 report.
5. **Clean up the old locations, only after steps 1 to 4 pass:**
   - the old checkout on C, only if `git status` is clean and every commit is on `origin`;
   - old package folders;
   - the `C:\Users\pro\Documents\VideoEnhancer-*` folders;
   - `C:\Users\pro\Documents\jobs`, only if it holds only test files;
   - `D:\VideoEnhancer-P1e-2`, after step 4;
   - `D:\VideoEnhancer`, if it exists and holds only what you created;
   - the caches on C that step 2 replaced.

   Report the space freed by each item.

## Part C: disk rules for every future cycle

Write these rules in `docs/WORKSPACE.md` (English). Future instructions refer to that file.
1. **Location.** All cycle work goes under `D:\my-workspace\VideoEnhancer\work`, which is the Codex project folder. List anything that Windows or a tool still puts on C and that cannot be moved.
   - `D:\my-workspace\VideoEnhancer\VE-check\` and `D:\my-workspace\VideoEnhancer\AppData\` belong to the owner and stay outside the project folder. No rule below applies to them.
     - Never clean, prune, move or write them.
     - Leave them out of the growth gate.
     - Report their sizes only if asked.
   - Nothing else in `D:\my-workspace` is touched.
2. **One package.** Build the new package into `package\`. Replace the old one only after the new one passes its smoke test.
3. **Scratch.** Empty `scratch\` at the end of every cycle, after the report's numbers are saved as JSON in `evidence\<cycle>\`. Never keep a synthetic file larger than 100 MB.
4. **Evidence.** At most 300 MB per cycle. Keep the last 3 cycles and delete older ones.
5. **Cache.** Generate reusable fixtures once, keyed by their recipe, and keep the GPU test model home here. Cap: 40 GB, pruning the oldest first.
6. **Disk table in every report.** Show:
   - free space on C and D, at the start and at the end;
   - the size of `package\`, `evidence\<cycle>\`, `scratch\` and `cache\`.

   **Gate:** persistent growth is at most 1 GB per cycle, unless the report says why.

## Part S: the owner's app data (Settings → Storage)

**Today:**
- App data lives in `%LOCALAPPDATA%\VideoEnhancer`. The location is chosen in `config.py` `get_home` and `gui/electron/main.cjs:38-40`, and `VE_HOME` overrides it.
- It holds the History, settings, installed models and logs.
- It also holds the working files of jobs, which are parts and the joined video. When app data and the output folder are on the same drive, admission reserves three copies of the estimated output there (`store.py` `working_space_locations`). For a 2-hour job whose output is about 29 GB, that is about 87 GB of free space.
- Parts are deleted only after a job finishes successfully (`controller.py:1087-1089`). Failed and cancelled jobs keep theirs.

**Do:**
1. **A Storage card in Settings.**
   - It shows the app data folder and its size, split into:
     - Models;
     - Working files of unfinished jobs;
     - History and logs.
   - It also shows the free space on that drive.
2. **Move…** lets the owner choose a folder. The owner plans to choose `D:\my-workspace\VideoEnhancer\AppData`.
   - It works only while nothing is processing. Otherwise it says "Pause processing first."
   - The target must be a new or empty folder. Refuse a non-empty folder with a message, so a wrong pick cannot mix the data with other files.
   - **Steps:**
     - Copy the data.
     - Verify it: every file's size, plus hashes for manifests, settings, journals and model weights.
     - Switch to the new folder.
     - Restart the service on the new folder.
     - Show the result.
   - **The old folder:** it is removed only after the switch works and the owner presses **Remove the old folder**. That is a permanent delete, because it holds only the app's own data.
   - **Where the location is stored:** outside the app data folder (for example in Electron's userData), so the app finds the folder at start-up. `VE_HOME` still overrides it.
   - **Records that keep working:** every record type must work after a move:
     - the History and Undo;
     - the deletion journal and its guards;
     - the model registry;
     - the schedule and logs;
     - resuming a paused job.

     Test each one.
   - **An interrupted copy** (app killed midway) leaves the old folder in use and unchanged.
   - **A missing new folder at start-up** shows "The app data folder was not found" with **Choose…** and **Use the previous folder**.
3. **Clean up working files.**
   - It lists failed and cancelled jobs that still have working files, with their sizes.
   - **Clean up** removes only the engine's own part and joined files. The job stays in History, and Retry starts from the beginning.
   - A setting, on by default, cleans these up automatically 7 days after the job failed or was cancelled.
4. **The Add dialog.** If the app data drive lacks the space a job needs, the message names the drive and the free space, and offers **Open Storage settings**.
5. **Do not move the owner's real app data yourself.** The owner does it with **Move…** after this cycle.

## Part G: acceptance

- **G1:** screenshots of the Storage card (both sizes and both themes, including a move in progress and the result), stored in `evidence\P1e-2b\`.
- **G2:** CI tests:
  - a move with a fake home that contains every record kind;
  - the interrupted copy;
  - the missing folder at start-up;
  - **Clean up** removes only part and joined files;
  - the space message names the drive.
- **G3:** the package smoke test from `D:\my-workspace\VideoEnhancer\work\package`, plus a real move of an isolated test home on the PC (from a test folder on C to one under `scratch\` on D, and back) with a finished job, a paused job and an installed model. Never use `AppData\` or `VE-check\` for this.
- **G4:** `ruff`, format, `pyright`, CPU tests, GUI lint, typecheck, unit tests, build and e2e. Windows and Ubuntu CI green on the final commit.
- **Report:**
  - the Part A table;
  - the space freed per item;
  - the Part C disk table;
  - "For the owner to delete", if anything was refused;
  - the new package path;
  - anything the owner must change on their side, for example removing the old Codex project once its folder is gone.

## Constraints

- English for code, comments, UI text and docs. Update `docs/GUI.md`, `docs/TROUBLESHOOTING.md` and the new `docs/WORKSPACE.md`.
- **Never commit:**
  - media, weights, packages or screenshots;
  - `node_modules` or build output;
  - `local-env.ps1`;
  - the owner's logs or private names.
- No new dependencies unless open source (name them in the report). No telemetry, no auto-update.
- The default pipeline output must not change.

Never report a test as passed if it did not run.
