# CURRENT_TASK: Cycle P1f-3b (make the new calibration GUI test independent of the machine)

- **Task ID:** VE-P1f-3b
- **Date:** 2026-10-22
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- Continue on PR #8's branch `claude/project-thread-1n4s31` from `8302964` (the P1f-3 commit). Do not open another PR.
- Git is handled as AGENTS.md and CLAUDE.md say.
- Replace `.ai/CURRENT_TASK.md` with this file. Write a new `.ai/LAST_REPORT.md` for this cycle. The P1f-3 report stays in Git history at `8302964`.

## 2. Problem

- **Failure:** Windows CI run 39715299978 (job 119615851853) on `8302964` failed two cases of the new test `gui/tests/e2e/p1f3-visual.spec.ts:7`. The other 17 passed, 14 were skipped, and the A7 test passed.
  - **"fresh":** "Using the built-in speed profile." was not visible within 20 s (line 29).
  - **"driver":** "Speed measured with driver synthetic-old-driver" was not visible (line 27).
- **Cause (designer's reading of the code, not yet confirmed by a run):** both cases depend on the real GPU of the machine that runs them.
  - `tests/p1f3_gui_seed.py:132` writes `gpu_name=environment_info().get("gpu")` into the synthetic profile.
  - The "fresh" case expects a built-in profile to match the machine's GPU.
  - Codex's PC has an RTX 4060 Ti, so both cases pass there. GitHub's Windows runners have no NVIDIA GPU, so neither text can appear.

## 3. Required

1. **Confirm the cause.** Run the two cases on a home where `environment_info()` reports no GPU, and show the same failure. Do this without changing the real machine.
2. **Make the test deterministic.** Give the engine a fixed, synthetic GPU name and driver for these test homes. Then all three states show the expected text on any machine, with or without a GPU.
   - Use a test-only override honoured only in e2e or test builds or isolated test homes. It must never affect the delivered package.
   - Do not weaken the assertions. Do not skip the cases or make them conditional on the runner's hardware.
3. **Check the product behaviour without a GPU.** On a machine without a GPU, the calibration area must show something correct and copyable, not an empty or broken card. Add a case for that state if one does not exist.
4. Change nothing else.

## 4. Do not change

Everything listed in P1f-3 section 6, and all P1f-3 behaviour.

## 5. Constraints

Same as P1f-3 section 7:
- separate engine homes;
- no system or registry changes;
- no third-party sites;
- tests clean up their own files;
- never commit media, packages, screenshots or the owner's data.

Also: the owner's sample is not used in this cycle.

## 6. Acceptance

- The two cases fail on `8302964` on a no-GPU home and pass after the fix. Codex's GPU PC still passes all three cases.
- GUI lint, typecheck, unit tests and build pass. The full e2e suite passes.
- CPU Python checks pass if any Python file changed.
- Rebuild the package only if delivered code changed. Report why it was or was not rebuilt.
- Windows and Ubuntu CI are green on the final commit.

## 7. Report (`.ai/LAST_REPORT.md`)

- The confirmed cause, with the before and after output.
- The changed files.
- The CI result.
- Disk: the size of `work\scratch` at the end, and what is left for the owner to delete. The P1f-3 residuals stay listed until the owner removes them.
- "Questions for the designer", each with the default you chose.
