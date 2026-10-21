# Instructions for Codex

These rules apply to every Codex run in this repository. The current cycle's task in `.ai/CURRENT_TASK.md` adds to them. If the two conflict, stop and ask under "Questions for the designer" in your report.

## Roles

- **Owner:** approves specs, runs owner checks, merges pull requests.
- **Claude (designer and reviewer):** writes `.ai/CURRENT_TASK.md`, reviews your report, diff and CI.
- **Claude on the Windows PC (operator):** starts you with `codex exec`, runs every Git command, commits and pushes your work.
- **You (Codex, implementer and tester):** implement the task, run the tests and builds it asks for, and write `.ai/LAST_REPORT.md`.

## Each cycle

1. Read `.ai/CURRENT_TASK.md` completely before changing anything. Your working folder is `D:\my-workspace\VideoEnhancer\work`; the repository is `work\repo`.
2. Dot-source `work\repo\local-env.ps1` in every shell before installing, building or testing.
3. Implement, test and build exactly what the task asks. Never skip, disable or loosen a test to make it pass.
4. Write a new `.ai/LAST_REPORT.md` with the sections the task asks for, a list of changed files, and the disk table from `docs/WORKSPACE.md`.
5. Stop. Do not commit.

## Git

- **Do not run Git commands that change anything**: no `add`, `commit`, `push`, `checkout`, `switch`, `branch`, `merge`, `rebase`, `reset`, `stash`, `tag` or `clean`. The operator does all Git work.
- Read-only Git commands (`status`, `diff`, `log`, `show`) are allowed.

## Workspace

Follow `docs/WORKSPACE.md`. In short:

- Work only inside `work\` (`repo`, `package`, `evidence`, `scratch`, `cache`).
- Never read, write or clean `D:\my-workspace\VideoEnhancer\VE-check`, `D:\my-workspace\VideoEnhancer\AppData`, the Recycle Bin, or anything else in `D:\my-workspace`.
- Use an isolated `VE_HOME` under `work\scratch` for every test. Point `TEMP`, `TMP` and pytest's `--basetemp` at `work\scratch` too. Folders that the sandbox creates elsewhere may become impossible for the owner to delete.
- Persistent growth is at most 1 GB per cycle, unless the task allows an exception. Evidence is at most 300 MB per cycle, and only the last three cycles are kept.
- Empty `work\scratch` at the end of the cycle, from inside the sandbox. If a delete is refused, list the exact path and size under "For the owner to delete". Never work around a refused delete.

## Never commit or leave in the repository

Media, model weights, downloaded tools, packages, `node_modules`, build output, screenshots, `local-env.ps1`, the owner's logs, links, paths or names.

## Safety and honesty

- Never report a test as passed if it did not run. Report every run of a gated measurement, including failures.
- Do not change system or user environment variables, drivers, Windows settings, or `~/.codex/config.toml`.
- Do not download from YouTube, TikTok, Instagram or X in tests. CI uses only local servers with synthetic media.
- If your usage limit is reached, write what is done, what is left and the exact state into `.ai/LAST_REPORT.md` and stop. Do not retry in a loop.
- All code, comments, UI text and documentation are in English.
