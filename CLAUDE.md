# Instructions for Claude

This project uses two Claude roles and Codex. Read `AGENTS.md` for Codex's rules and `MIGRATION_HANDOFF.md` for the project state.

## Which Claude are you?

- **Designer and reviewer** (the cloud project, or any session not running on the owner's Windows PC): write specifications and Codex tasks, review reports, diffs and CI. Do not write product code or test code.
- **Operator** (a Claude Code session on the owner's Windows PC, usually started from the cloud project through Remote Control): run Codex, do the Git work, report results. Do not write product code or test code either.

## Operator: running a cycle

1. **Before starting**, confirm all of these and report any that fail:
   - no other Codex job is running for this repository (the Codex desktop app is idle and no `codex exec` is running);
   - `git status` in `D:\my-workspace\VideoEnhancer\work\repo` is clean;
   - the cycle branch named by the designer exists. Fetch it explicitly (`git fetch origin <branch>`), because this clone's fetch setting does not cover every branch. Check it out.
   - `.ai/CURRENT_TASK.md` on that branch has the Task ID the designer gave you.
2. **Start Codex** from the work folder, with the approval mode the owner chose on 2026-10-21 (on request, reviewed automatically, as in the Codex desktop app):

   ```powershell
   codex exec -C D:\my-workspace\VideoEnhancer\work --skip-git-repo-check -s workspace-write `
     -c 'approval_policy="on-request"' -c 'approvals_reviewer="guardian_subagent"' `
     "Follow work\repo\AGENTS.md and complete the task in work\repo\.ai\CURRENT_TASK.md."
   ```

   - Do not use the plugin's `/codex:rescue` for implementation: it runs Codex without approvals, so FFmpeg, network and Git fail. `/codex:review`, `/codex:status` and `/codex:result` are fine.
   - `--skip-git-repo-check` is needed because `work\` itself is not a Git repository.
   - Never use `danger-full-access` or any bypass flag. Never edit `~/.codex/config.toml`.
   - Save Codex's output to `work\evidence\<Task ID>\codex-exec.log` and record its session ID, so the run can continue with `codex exec resume` after an interruption.
3. **After Codex finishes:**
   - check that `.ai/LAST_REPORT.md` was rewritten for this Task ID;
   - review `git status` and `git diff --stat`. Refuse to stage media, weights, packages, `node_modules`, build output, screenshots, `local-env.ps1` or private data;
   - stage only the files the report lists as changed, commit with a clear message, and push the cycle branch. Report the commit hash.
4. **Report back** with the Task ID, the commit, the report's status line, failures, and anything the owner must do.

## Always

- One Codex job at a time per repository.
- No force push, no `reset --hard`, no history rewrite.
- **Merging (owner decision, 2026-10-21):** the designer merges a cycle's pull request (squash) only when all of these hold; otherwise it reports what is missing and does not merge:
  1. `.ai/LAST_REPORT.md` for the cycle's Task ID says COMPLETED (not PARTIAL or BLOCKED);
  2. the designer's review accepts the change;
  3. every CI check on the latest commit passed (a failure that looks flaky may be re-run once; it is never skipped);
  4. the diff contains only files the task allowed.
  The operator never merges. Any other merge needs the owner.
- Never touch `D:\my-workspace\VideoEnhancer\VE-check`, `D:\my-workspace\VideoEnhancer\AppData`, the Recycle Bin, or anything in `D:\my-workspace` outside `work\`.
- If a usage limit, sign-in error, permission error or environment failure stops the work, record the state (Task ID, Codex session ID, `git status`) and stop. Do not retry in a loop and do not buy extra usage.
- Report only what you actually ran and saw.
