# Development with Claude

Claude handles design, product and test code, builds, verification, review and Git
operations directly. The owner ended the Claude-Codex loop on 2026-11-10. Do not
start Codex or require a separate designer, operator or implementer handoff.

Read [the project handoff](MIGRATION_HANDOFF.md), [development setup](docs/DEVELOPMENT.md)
and [workspace rules](docs/WORKSPACE.md) before working. The records under
`docs/archive/claude-codex/` are historical evidence, not active instructions or a
queue of work. New work comes from the owner's current request; no
`CURRENT_TASK.md` / `LAST_REPORT.md` exchange is required.

## Workflow

1. Inspect the current branch, working tree and relevant code. Preserve existing
   changes and avoid simultaneous sessions changing the same checkout. A cloud
   Claude session may plan or review, and Claude Code may work on Windows through
   Remote Control; both follow these rules and may implement directly.
2. Agree on the requested scope from the owner's instructions, implement it and
   add meaningful regression coverage where needed. Do not skip, disable or
   weaken tests to make a change pass.
3. Run the checks appropriate to the change, using the commands in
   `docs/DEVELOPMENT.md` and `.github/workflows/ci.yml`. Windows desktop, GPU and
   physical-device checks require their actual environments. Distinguish passed,
   failed and not-run checks; a CPU or browser result does not prove a hardware or
   owner check passed. Report every run of a gated measurement, including failures.
4. Review the diff, stage only intended source and documentation, commit and push
   the task branch, and inspect CI on the latest commit. Report the change,
   verification results, remaining limitations and any owner actions. Keep
   durable task notes when useful; do not overwrite historical reports.
5. Preserve the owner's existing merge conditions: squash a pull request only
   when implementation is complete, review accepts the change, every CI check on
   the latest commit passed, and the diff stays within the agreed scope.
   Otherwise report the missing conditions. A seemingly flaky CI failure may be
   rerun once; it must not be skipped. Other merges need the owner's authorization.

No force push, `reset --hard` or history rewrite. Do not commit media, weights,
downloaded tools, packages, `node_modules`, build output, screenshots,
`local-env.ps1`, or private logs, links, paths or names.

## Workspace and verification

- On the owner's Windows PC, work under
  `D:\my-workspace\VideoEnhancer\work`, with the checkout in `work\repo`.
  Dot-source the Git-ignored `repo/local-env.ps1` in each shell before installing,
  building or testing. Use session-only environment variables.
- Never read, write, clean or move the owner's `VE-check`, `AppData`, the Recycle
  Bin, or anything else in `D:\my-workspace` outside `work`.
- Isolate `VE_HOME`, `TEMP`, `TMP`, pytest's `--basetemp`, GUI app-data roots and
  the WebView2 profile under task-owned scratch. Do not touch another session's
  scratch or the owner's running app, queue or service.
- Keep one current package, at most 300 MB of evidence per task and the last
  three tasks' evidence, a complete cache below 40 GB, and persistent growth at
  most 1 GB per task unless an explicit task exception applies. Record the disk
  table, growth, cleanup paths and measured removed bytes as described in
  `docs/WORKSPACE.md`. Do not invent Windows drive measurements from another host.
- Inventory exact paths and sizes before deleting confirmed development
  artifacts. Clean only this task's scratch after saving required evidence.
  If deletion is refused, record the remaining path and size for the owner;
  never bypass the refusal or assume old cleanup succeeded.

## Boundaries

- Do not change system or user environment variables, drivers, Windows settings
  or assistant-wide configuration. Do not bypass permission controls.
- Tests must not download from YouTube, TikTok, Instagram or X. CI uses local
  servers and synthetic media. Use owner media only when explicitly requested.
- If a usage limit, sign-in error, permission error or environment failure blocks
  work, record what is done, what remains, the branch/commit and working-tree
  state. Stop the blocked operation; do not retry in a loop or buy extra usage.
- Report only what actually ran and was observed. Code, comments, UI text and
  repository documentation are in English.
