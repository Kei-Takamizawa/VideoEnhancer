# CURRENT_TASK: Cycle P1e-3a (GPU memory cap with spill detection, start-up robustness, deferred minor findings)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3a
- **Date:** 2026-10-22
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`, created from `main` at `c84ce1a` (PR #8 merge). The operator opens a draft PR for it.
- This file is `.ai/CURRENT_TASK.md` on the branch; do not replace it. Write a new `.ai/LAST_REPORT.md` for this cycle.
- Restore the dependencies the last cleanup removed (`gui\node_modules` and anything else missing). The restore does not count toward the 1 GB growth limit; report its size on its own line.

### Where this cycle sits

P1e-3 is split into four cycles, in this order. Do only P1e-3a now.

| Cycle | Content |
| --- | --- |
| **P1e-3a (this one)** | GPU memory cap with spill detection; engine start survives a damaged JSON file; deferred minor findings; the flaky e2e test |
| P1e-3b | mpv (libmpv, LGPL build) embedding spike in Tauri |
| P1e-3c | Embedded mpv player with an IINA-like UI; Compare speed |
| P1e-3d | Bit-identical speed-ups and a warm worker; recalibration that keeps the long finalization curve; gate rerun |

## 2. Background

- **Spill (confirmed 2026-10-22, P1f-3 A2 run):** Standard, AV1 output, 1440, on the RTX 4060 Ti 8 GB. Dedicated GPU memory peaked at 7.91 GB of 8 GB and shared GPU memory at 2.01 GB. 7 of 29 parts took 1.1x to 2.4x their predicted time.
- **Why it spills:** the Windows NVIDIA driver (536.40 and later, default "CUDA Sysmem Fallback Policy") moves allocations to shared system memory instead of raising out-of-memory. The job keeps running, 3-10x slower, and can trip the segment watchdog (`schedule/controller.py` `SegmentWatchdog`: wall time > 3x predicted + 300 s), which retries the part in a fresh child that spills again.
- **Facts from the code (c84ce1a):**
  - No `torch.cuda.set_per_process_memory_fraction` or other cap anywhere.
  - Pipeline order is restore (BasicVSR++, `clip_length` 15, overlap 2) → resize → RIFE, so RIFE runs at output size.
  - BasicVSR++ moves its model to the GPU per clip and back to the CPU afterwards, with `empty_cache()` around it (`models/basicvsr.py`).
  - On CUDA OOM, `pipeline/runner.py` `restore_with_retry` retries once with half-length clips. That changes the output of that clip.
  - `jobs/gpu_memory.py` samples dedicated and shared usage through PowerShell `Get-Counter`, about 3 s per sample, every 60 s.
  - NVDEC, NVENC and the display use GPU memory outside PyTorch's allocator.
- **Earlier measurements (P1e-2):** 1440 Standard reached 7.2 GB device memory in isolation. 2160 RIFE alone reserved 7.0 GB (2160 output is no longer offered).

## 3. Part A: GPU memory cap with spill detection

### A1. Measure first

Before changing behaviour, on the development PC, measure per stage (decode, BasicVSR++, resize, RIFE, encode) for Standard 1080 and Standard 1440, each with frame rate Keep and 2x, and Fast 1440 2x:
- PyTorch allocated peak and reserved peak;
- process dedicated and shared GPU memory (1 s samples);
- non-PyTorch GPU memory (process dedicated minus PyTorch reserved).

Use a synthetic or allowed (Wikimedia Commons / Internet Archive) 1080p source of at least 2 minutes. Report the table. The owner's sample is not used in this cycle.

### A2. Cut the peak without changing the output

Try the bit-identical options and keep only those that lower the peak and pass G5 strict equality:
- PyTorch allocator settings that reduce fragmentation (for example `expandable_segments:True`), set only for the engine's processing children;
- releasing cached blocks or tensors between stages that are not needed by the next stage;
- anything else that does not change a single output byte.

Report the peak before and after for each option, and which ones you kept.

### A3. A budget that turns spill into a handled error

- **Budget:** at the start of each part, in the processing child, compute a PyTorch budget from the free dedicated memory at that moment, minus a reserve for NVDEC, NVENC and the display. Measure the reserve from A1 instead of guessing, and report the value and how you chose it.
- **Cap:** apply the budget with `torch.cuda.set_per_process_memory_fraction` (or an equivalent cap that makes PyTorch raise OOM instead of letting the driver spill).
- **On OOM under the cap**, in this order:
  1. the existing BasicVSR++ half-clip retry, unchanged (record it as now);
  2. if that is exhausted, or the OOM is in RIFE or another stage: run that part once more **without the cap**. That keeps the output identical to today's and lets the job finish. Mark the part "ran over GPU memory".
  3. A part must never fail only because of the cap.
- **Never** lower quality settings, tile RIFE, or change any other output-affecting parameter to fit the budget.
- When the whole part fits under the cap, the output must be byte-identical to the uncapped output (G5).

### A4. Spill detection

- **Sampler:** replace the PowerShell `Get-Counter` path with a direct PDH (or D3DKMT) query through `ctypes`, so one sample costs ≤ 50 ms. Keep the PowerShell path only as a fallback when the direct query fails, and report which one ran. Sample every 1 s during processing.
- **Detection:** a part has "spilled" when the processing child's shared GPU usage rises more than 256 MB above its value at part start. Record per part: peak dedicated, peak shared, spilled yes/no, and whether the cap was on.
- **Effects of a spill:**
  - the segment watchdog does not count spill time as a hang: when spill is detected, scale that part's wall-time limit so a slow but progressing part is not killed and retried (the "no new frame" rule still applies);
  - spilled parts are excluded from estimate learning and calibration samples;
  - the job log gets one line per spilled part. The job's details show "Some parts ran slower because GPU memory was full." once, with Copy (P1f-3 B1 style). This is a condition notice: it does not fade.
- On machines without the counters (non-Windows, no NVIDIA GPU), spill detection reports "unavailable" and the cap still works.

### A5. Tests

- **CPU (CI):** budget arithmetic; the OOM order in A3 with a fake stage that raises OOM under the cap and passes without it; spill detection from a fake counter stream; watchdog scaling; spilled parts excluded from learning; the details notice.
- **GPU (development PC):**
  - Standard 1440 2x and Standard 1080 on the A1 source with the cap on: report peak dedicated, peak shared, spilled parts, and wall time per part against the prediction. Target: no spill and no part slower than 1.3x its prediction when nothing else uses the GPU.
  - **With a competing load:** a test-only helper process that holds 2 GB of GPU memory during the run. The cap must adapt at the next part start; report what happened (OOM retries, uncapped re-runs, spills).
  - **G5:** capped and uncapped outputs byte-identical for at least one Standard 1080 and one Standard 1440 part that fit.
  - Report every run, including failures.

## 4. Part B: engine start survives one damaged JSON file

- **Problem:** start-up reads these without a guard, so one damaged file stops the engine:
  - `service/engine.py:~247` previews `state.json` and `:~255` previews `request.json` in `_recover`;
  - `service/settings.py:~42` `settings.json`;
  - job manifests and `analysis.json` loaded at start (`jobs/store.py` `_load_unlocked`, `~374-383`) outside the P1f-2 A1 broken-record path;
  - any other JSON read on the start path that you find (list them).
- **Required:**
  - Skip the damaged file, log it once with path and parse error, and show one condition notice with Copy. Settings fall back to defaults for the session.
  - **Never repair, rewrite, rename or delete** the damaged file. Saving settings later must not overwrite a damaged `settings.json` silently: refuse the save with a copyable reason until the owner fixes or removes the file. Report how you did it.
  - The P1f-2 A1 broken-record handling for History stays as it is.
- **Test:** for each file type, a home with that one file damaged (truncated, not JSON, wrong type at top level): the engine starts, the rest of the data loads, the file is byte-identical afterwards.

## 5. Part C: deferred minor findings

Each item below was found in the P1f and P1f-2 reviews and deferred here. The descriptions are short; find the code, confirm the problem, then fix it with a test. If an item does not reproduce or cannot be identified, report the evidence and leave the code.

### C1. Decoder
1. **OOM after the decoder retry:** when a part has already used its one decoder retry (NVDEC → FFmpeg) and then hits CUDA OOM, the OOM must go through the A3 order, not be reported as a decoder failure.
2. **Re-analysis keeps a runtime FFmpeg choice:** a job that switched to FFmpeg at run time (P1f L3 / P1f-3 A2) must keep that choice and its reason after re-analysis, instead of returning to NVDEC.
3. **12-bit sources:** use `p016le` where 12-bit input is converted, instead of a format that drops bits. 12-bit input stays refused if the spec refuses it today; then only make the refusal reason exact.

### C2. Storage
4. Remove is offered when nothing can be deleted: hide or disable it, with the reason.
5. The "earlier version" message must not appear on a pointer this app itself recovered.
6. Raw JSON appears in a result text: show a sentence instead (keep the detail in Copy details).
7. A disconnected drive must not clear the storage pointer: show the drive as unavailable and keep the pointer.
8. The status line during Remove: show what is being removed and progress, not a stale or empty line.
9. A second Move overwrites `previous`: keep the earlier `previous` record (or refuse the second Move until the first is cleaned up). Report which you chose and why.
10. Remove hashes files twice: hash once and reuse the result.

### C3. Links
11. The downloaded tool's bytes are read again before install: verify and install from the same read, so the checked bytes are the installed bytes.
12. Install and uninstall of link tools must be refused while a link check or download runs, with a reason.
13. One audio-only choice disables every video format: fix the format filter so audio choices do not affect video eligibility.
14. Retry after a crash between the rename and the record: recover the finished download instead of downloading again. Also handle names that differ only in letter case (Windows is case-insensitive).
15. Quit is refused while a downloaded video is being analysed: allow Quit, stop the analysis cleanly, and resume it at the next start.
16. Reuse mismatches for odd widths: compare the same rounded width the reuse record stores.

### C4. From the P1f-2 review
17. **Second decode in analysis:** the thumbnail pass decodes the file a second time (17.4 s of 40.7 s for a 10-minute 1080p file). Make thumbnails from the first decode when the result is the same. The strict count check stays.
18. **Unreadable record title:** the details dialog of an unreadable record shows the 32-character ID as its title. Show "Unreadable record" plus the folder date instead. Keep the ID in Copy details.
19. **Link estimates:** new finished jobs do not update link-job time estimates until the app restarts. Refresh them when a job finishes.

(The B6 false space refusal was fixed in P1f-3 A3; do not change it.)

## 6. Part D: flaky e2e test `gui/tests/e2e/p1f2-review.spec.ts:68`

- **Failure:** `expect.poll(() => app.clipboardText()).toContain("Parse error:")` after Copy details on the unreadable record, with "page closed". It recurred on hosted Windows CI: run 39737098567, attempt 1 (head `68bef06`); attempt 2 passed. P1f-3 A7 ran it 50 times on the development PC without a failure.
- **Required:**
  - Read the failing attempt's log and artifacts (the operator can fetch them; ask under "Questions for the designer" if you need them and cannot reach them) and state what closed the page.
  - Remove the dependency on the shared system clipboard in e2e builds: read the copied text through the app's own copy path (an e2e-only hook), covering the P1f-3 "Copied" flow. The real-clipboard path keeps one unit or integration test.
  - Never skip, quarantine or retry-wrap the test. Do not only lengthen timeouts.
  - Run the spec 50 times locally after the fix and report the count.

## 7. Do not change

- G5 strict equality of the default pipeline output.
- The P1f decoder decisions: strict timestamp check, per-job decoder choice, one retry.
- HEVC as the default output; the M1 media path with 1 MiB responses; the MP4 audio rule.
- Input ≤ 1080 (short side); outputs Keep, 1080 and 1440.
- The T6 rules, the L2 reuse rule, the P1f-2 A1 broken-record handling, all P1f-3 and P1f-3b behaviour.
- The player and Compare (P1e-3b/c), calibration and estimates beyond A4's exclusion of spilled parts (P1e-3d).

## 8. Constraints

- A separate engine home for every test; TEMP, TMP and `--basetemp` under `work\scratch`.
- No system, driver, registry or NVIDIA Control Panel changes. Do not change the "CUDA Sysmem Fallback Policy".
- CI uses only local servers with synthetic media. Local real-network tests may use only Wikimedia Commons and Internet Archive. Never YouTube, TikTok, Instagram or X.
- The GPU load helper in A5 is test-only and must exit at the end of the test, even on failure.
- Never commit media, weights, packages, `node_modules`, build output, screenshots, `local-env.ps1`, or the owner's data.
- English for all code, comments, UI text and docs. Update `docs/API.md`, `docs/GUI.md` and `docs/TROUBLESHOOTING.md` where behaviour changes (the spill notice, the damaged-file notice).

## 9. Acceptance

- Every A, B, C and D item has a test that failed on `c84ce1a` (or evidence that it does not reproduce) and passes now.
- **Python:** `ruff`, `ruff format --check`, `pyright`, the CPU suite.
- **GPU:** the suite `-m "gpu and not soak"`, plus the A5 GPU runs.
- **GUI:** lint, typecheck, unit tests, build, full e2e.
- **Rust:** fmt, clippy (default and e2e), unit tests (only if Rust changed; say so either way).
- **P2 cold start:** 5 launches with nothing else running. Home-ready median ≤ 765 ms, first paint median ≤ 1.0 s.
- **Package:** rebuilt at `work\package\VideoEnhancer` if delivered code changed, with an isolated start-up smoke and its SHA-256.
- **CI:** Windows and Ubuntu green on the final commit (the operator pushes; final CI may be reported as pending).

## 10. Report (`.ai/LAST_REPORT.md`)

- Status line: COMPLETED, PARTIAL or BLOCKED.
- A table of every item (A1-A5, B, C1-C19, D, P2): done / partial / not reproduced / NOT RUN, with tests and evidence files.
- The failing output on `c84ce1a` and the passing output after, per item.
- **A:** the A1 memory table; A2 options with before/after peaks; the reserve value and reasoning; the A5 runs (per part: peak dedicated, peak shared, spilled, cap on/off, wall vs predicted); the sampler cost per sample.
- **D:** what closed the page, and the 50-run count.
- Changed files.
- **Disk:** the dependency restore size; growth for the rest of the cycle; `work\scratch` at the end; free space on C and D; anything left for the owner to delete.
- "Questions for the designer", each with the default you chose.

## 11. Designer answers and resume (2026-10-22, after the first run stopped at `216043d`)

Continue this same cycle on the same branch, from the partial work in `216043d`. Keep that work; do not start over. Everything in sections 1-10 still applies, and every item still marked partial or NOT RUN in your report is still required.

### 11.1 Do not stop the whole cycle for one question

When one item needs a designer decision, choose the safer default that keeps the settled spec, record it under "Questions for the designer", and **continue with every other item**. Stop early only for the reasons in `AGENTS.md` (a conflict between `AGENTS.md` and this task, a usage limit, or an environment failure). BLOCKED is for a cycle that cannot continue at all.

### 11.2 C3 answer: follow the spec and refuse inputs above 10 bits

- The spec allows 8-bit and 10-bit SDR input only (`MIGRATION_HANDOFF.md` section 3). The current acceptance of `yuv420p12le` and other formats above 10 bits is a gap, not a product decision.
- **Required:**
  - Refuse local files above 10 bits at admission (the Add dialog and the API), with this reason: "This video uses <N>-bit color. VideoEnhancer accepts 8-bit and 10-bit videos only." Make it copyable (P1f-3 B1).
  - For links, never choose a format above 10 bits. If only formats above 10 bits exist, refuse the link with the same reason.
  - A job already in the queue or History from an earlier build with such a source: it is not deleted or changed. If it has not finished, it fails at its next start with the same reason.
  - Do not add `p016le` conversion. Remove or narrow the code path that accepts 12-bit input, so the refusal cannot be bypassed.
- **Test:** the synthetic 12-bit HEVC fixture you made is refused, with the exact reason, on `c84ce1a` behaviour (accepted) versus now (refused). An 8-bit and a 10-bit fixture are still accepted.
- Update `docs/GUI.md` or `docs/TROUBLESHOOTING.md` with the refusal.

### 11.3 D answer: the cause stays unknown; make the next failure leave evidence

- The designer accepts "what closed the page is unknown" for the failure in run 39737098567 attempt 1. No other trace exists: the run kept no artifacts.
- Keep your e2e-only copy capture. Finish the 50-run local repetition of the whole spec file and report the count.
- **Add evidence for the future (allowed file: `.github/workflows/ci.yml`):** on an e2e failure, CI uploads the Playwright trace, the app log and the engine log of the failing test as an artifact (kept 7 days, at most 100 MB, no owner data; e2e homes are synthetic). The upload runs only on failure. It must not change pass/fail and must not retry.
- Also log, in e2e builds only, why a window or webview closes (the Tauri close or destroy event, the reason if known, and the time), so a future "page closed" can be explained.

### 11.4 Measurements in A

- Run A1 again **with nothing else using the GPU** (no GUI e2e or other GPU tests at the same time). The earlier runs that overlapped e2e do not count for choosing the reserve.
- If exact per-stage attribution is not possible because stages overlap, measure each stage alone in a test harness on the same frames (decode only, BasicVSR++ only, resize, RIFE only, encode only), and report both: the per-stage table from the harness, and the whole-part peaks from real runs.

### 11.5 Cleanup

- The operator deleted most of `work\scratch` after your first run. 17 empty folders that only the sandbox account can open are still there (`minor-*`, `startup-*`, `tmp\ve-av1-probe-*`). Delete them from inside the sandbox at the end of this run if you can. List any that remain.
- Create test folders so the owner's account can delete them (see `docs/WORKSPACE.md`), for example by avoiding mode `0o700`, where the test code is yours to change.
