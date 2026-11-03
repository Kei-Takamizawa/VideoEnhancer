# CURRENT_TASK: VE-R1b-3 (close VE-R1b-2: classify the local p1f3-visual failure)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1b-3
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #18) at the commit that adds this file, on top of VE-R1b-2 at d22e389.
- Write a new `.ai/LAST_REPORT.md` for VE-R1b-3; keep the older reports below it.
- Same isolation rules as VE-R1b-2. Do not touch the owner's real remote service, its home, library, task or firewall. No dependency changes. No product or test code changes are expected.

## 1. Background

VE-R1b-2 is PARTIAL only because `gui/tests/e2e/p1f3-visual.spec.ts` "fresh calibration" times out locally on `video.readyState > 1` after opening the Japanese-named History video. On GitHub Actions the same suite passed on d22e389 (both `cpu (windows-latest)` runs green, including the desktop E2E step). An older report records the same local symptom. The designer's working assumption is that this is a pre-existing, PC-specific desktop playback issue unrelated to R1b. The desktop GUI is retired in R3.

## 2. Work

1. Create a temporary Git worktree of `main` (b54f2b6, before any R1b change) under `work/scratch/`, with its own isolated test home, and run only `npm run test:e2e -- tests/e2e/p1f3-visual.spec.ts -g "fresh calibration"` there twice (build what that test needs, in scratch). Then run the same command twice on the current branch.
2. Classify the failure:
   - **Pre-existing:** it fails on `main` too. Record the evidence and state that it is a local, pre-existing desktop playback issue outside R1b's scope.
   - **R1b regression:** it passes on `main` and fails on the branch. Stop and report BLOCKED with the evidence (do not change `gui/**`).
3. Remove the worktree and its scratch output afterwards (use `git worktree remove`; no `reset --hard`, no force).
4. Report the disk baseline and growth.

## 3. Done when

The classification is recorded with the command lines, exit codes and timings for all four runs. If it is pre-existing, VE-R1b-2's remaining gate is satisfied: report **COMPLETED** for VE-R1b-3 and state that sections 1 to 6 of VE-R1b-2 pass, with this local test listed as a known pre-existing local failure that CI passes. Allowed files: `.ai/LAST_REPORT.md` only.
