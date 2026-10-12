# CURRENT_TASK: Cycle P1d-3 (close out P1d: estimates without calibration, live progress, a cheaper event stream)

- **Task ID:** VE-P1d-3
- **Date:** 2026-10-11
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** continue on branch `p1d-ui-v2` (draft PR #5, head `fbaf4d3`). If `origin/main` has moved, merge it into `p1d-ui-v2` with a merge commit first (no rebase, no force-push). Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Update the report again after the final CI run, so it never says "pending CI". Do not push to `main`.

This is meant to be the last P1d cycle. After it, the owner runs the visual check and then merges PR #5.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option that keeps existing outputs unchanged (or skip only that item), and continue. Stop early only if every remaining item is blocked.
2. An open question is not a blocker when this task already gives a fail-closed rule for it. Implement the safe parts and the guard, then ask.
3. Order: Part S (deletion fixes) → Part E (estimates) → Part L (live progress and event stream) → Part A (Add checks) → Part P (harness and budgets) → Part G (acceptance) → Part X (optional). Long GPU measurements run whenever the GPU is free.
4. If time runs out, finish earlier items completely and mark the rest NOT RUN. Never report a test as passed if it did not run.
5. The owner's queue, settings and videos on this PC are not test data. Use synthetic footage and a separate engine home for every test.
6. No result is selected because it is favourable. Report every run of a gated measurement.

## 0. Status after P1d-2 (review of `fbaf4d3`)

Accepted as done (keep, do not redo):
- **E:** the per-model delta rule. With a calibrated profile, all four 30 s jobs were within −3.4% to −6.2%.
- **S:** guarded recycling, journal, crash recovery, History deletion and the automatic original deletion. All four real-PC checks passed, with matching SHA-256 values. Part S below lists the review findings to fix.
- **F:** the first look comes from the real render (C1 22.9 s from GPU admission).
- **U:** every row of the P1d-2 gap table.
- **P:** the harness, the manifest cache and the AV1 minimum-size cache.
- **R:** all three robustness items.
- **G:** 30 GPU tests and 61 packaged boards. CI is 4 of 4 green on `fbaf4d3`, and PR #5 is mergeable.

Designer answers to your seven questions:
1. **Estimates without calibration.** You were right not to fit coefficients to the acceptance clips. The cause is in the defaults, and Part E fixes it:
   - `DEFAULT_COMPONENTS` (`estimate/model.py:17-36`) are provisional numbers.
   - The default interpolate term alone is 95.4 ms per source frame. The whole real Fast pipeline is 66.9 ms (60.23 s / 900 frames).
   - Calibration never runs by itself.
   - A profile matches only the exact GPU name and driver string (`jobs/store.py:172-206`). So a driver update silently falls back to these defaults: C1 +37%, Fast +147%.
2. **RIFE full preview 65.16 s > 63.5 s.** My gate was wrong.
   - The P1d numbers were timed from `render_compare` entry, with shared resources already warm. P1d-2 timed from cold GPU admission, as I asked. The two are not comparable.
   - With the stricter boundary, C1 still improved by 12.9% (75.1 → 65.4 s) and SCUNet by 6.4% (196.7 → 184.1 s).
   - Accepted. The new baselines, all from cold GPU admission, are C1 65.4 s, SCUNet 184.1 s and RIFE 4.25 65.2 s. A later change may not exceed them by more than 5%.
3. **Service CPU 10.03%.** This is a real cost that grows with History. Part L fixes it.
4. **Hard-link guard.** Agreed. Fail closed and keep the bytes.
5. **Standalone Trial.** No GUI code calls `POST trial`. In UI v2, Compare is the only trial surface, and it already shows the first look. No change. Keep the trial API for the CLI and tests.
6. **Progress spacing 999.5 ms.** My wording was too literal; 0.5 ms is timer jitter. The review also found that the 1 Hz rate exists only in the perf fixture. In the product, progress reaches the GUI only with the 5 s structural refresh (`live_progress` is not in the snapshot key, `engine.py:493`). Part L and Part P give the new rule.
7. **Input delay and interaction duration.** Gate both. Event Timing input delay must be ≤50 ms. Interaction duration must be ≤200 ms, the web.dev "good" threshold for Interaction to Next Paint. Details are in Part P.

The downscale note (1440p or 4K source with output 1080) stays non-blocking, with "Use Keep", as you built it.

## 1. Part S: deletion review findings

The P1d-2 scheme stays: preflight, journal, hard-link guard, shell recycle, confirm or restore, crash recovery. The review of `service/deletion.py` at `fbaf4d3` found two narrow races that can lose a user's video, and several smaller faults. These come first in this cycle.

**Critical (bytes can be lost):**

- **S-C1. The guard is removed without proving that the bin item is our file.**
  - `_finish` (`deletion.py:229-233`) removes the guard when the path is gone and the shell reported `recycled`. Nothing holds the file between the `samefile` check (`:315`) and the shell call.
  - If another program replaces the path with a different file B in that window, the shell recycles B. Removing the guard then deletes the last link to the original A.
  - Recovery (`:229-233`) has the same gap.
  - **Fix:**
    - Repeat the `samefile(path, guard)` check immediately before the shell call.
    - Take the bin item's file-system path from `psiNewlyCreated` and store it in the journal at the shell phase.
    - Remove the guard only if `samefile(bin item, guard)` holds, in `_finish` and in recovery.
    - Otherwise keep the bytes: move the guard back to the original path when it is free, without replacing anything; when it is not free, keep the guard and report its full path.
- **S-C2. Recovery does not coordinate with a deletion running in another process.**
  - `recover()` runs at every service start (`engine.py:98-104`), and `VideoDeletion.lock` belongs to one instance (`:205`).
  - The CLI `run` path runs auto-delete under `worker.lock`, not `serve.lock` (`controller.py:976-978`, `cli.py:497-502`).
  - A recovery can therefore remove the guard of a deletion that is still in progress in another process.
  - **Fix:**
    - Use one cross-process deletion lock: an OS file lock in the engine home. Hold it for the whole `delete()` and for `recover()`.
    - Record the owning process id and its start time in each journal entry.
    - Recovery never touches an entry whose owner is alive. When it cannot take the lock, it retries later: on the next deletion, or at least every 60 s.

**Major (wrong behaviour, no byte loss traced):**

- **S-M1. Identity is never checked.**
  - The recorded size, `mtime_ns` and edge hash of the original (`store.py:83-96`) are not compared before deletion. Outputs have no recorded identity.
  - So History can recycle a different file that now sits at the recorded path, for example a newer output with the same default name, or a new download with the same name.
  - **Fix:**
    - Before deleting an original, require a match with its recorded identity.
    - Record the same identity for the output when it is published, and require it before deleting the output.
    - For older jobs without an output identity, require `output_bytes` to match and the modification time to be no later than `finished_at` plus 60 s.
    - On any mismatch, return "Kept: the file changed after this job used it".
- **S-M2. Read-only videos.**
  - READONLY is copied back onto the guard before `guard.unlink()` (`:231-232`, `:244-245`), so the unlink fails after a real recycle. The guard is left for good, and recovery fails at every start.
  - **Fix:** remove the guard link without changing the attributes the bin item keeps, for example with `FileDispositionInfoEx` and `FILE_DISPOSITION_FLAG_IGNORE_READONLY_ATTRIBUTE`.
  - Also stop setting HIDDEN on the guard. Attributes belong to the file, not the name, so hiding the guard also hides the user's original during the operation.
- **S-M3. Concurrency.**
  - Auto-delete creates its own `VideoDeletion` (`:415`) and runs on the worker thread without `engine.lock`. History deletion uses `Engine.deletion` under `engine.lock`.
  - Auto-delete also saves a job snapshot taken before a decode that can take minutes (`:394-423`). That overwrites newer `video_deletions` and history changes, and recreates a removed job folder (`store.py:304`).
  - **Fix:**
    - Use one shared deletion object per process, plus the S-C2 lock.
    - After the decode, re-read the job and write only its own fields.
    - Skip the save if the job was removed in the meantime.
- **S-M4. No Windows dialogs, and no stalled queue.**
  - A "too big for the Recycle Bin" or similar shell prompt from the windowless service can block the queue worker overnight, or block every mutating API call while `engine.lock` is held.
  - **Change from P1d-2:** now that the guard keeps the bytes whatever the shell does (proven on the real NTFS volume in P1d-2), pass `FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI` together with `FOFX_RECYCLEONDELETE`. If the shell deletes the name instead of recycling it, the existing restore path brings the file back.
  - This is allowed only behind the guard and only after S-C1 is fixed.
  - **Before calling the shell**, read the volume's Recycle Bin settings when they are readable: per-volume `MaxCapacity` and `NukeOnDelete` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume\{GUID}`, plus any policy override. Verify these names on the PC; if they cannot be read, call the shell as described. If recycling is off for that drive, or the file is larger than the bin's maximum size, keep the file without calling the shell. Results:
    - "Kept: the file is too big for the Recycle Bin";
    - "Kept: the Recycle Bin is turned off for this drive".
  - Run the shell step outside `engine.lock` and off the queue worker, so a deletion never delays the next job.
  - Replace raw HRESULT text (`:171-172`) with plain reasons.
- **S-M5. Retained guards are invisible.**
  - Recovery results are thrown away (`engine.py:104`), and the "guard retained" messages do not say where the bytes are.
  - **Fix:**
    - Show every non-resolved result in History, or as a Home notice when no job matches. Include the full guard path and a "Show in folder" action.
    - A guard is never deleted while its entry is unresolved.

**Minor:**
- After the guard exists, every exception, not only `OSError`, goes through `_finish` (`:324`).
- **The "unfinished job uses it" checks** (`:296-301`, `:402-407`): compare file identity (`samefile` or file ID), not path strings.
- **`verify_output`:**
  - Add CPU tests with real small files: pass, short frame count, wrong duration, missing audio when the source has audio, and no video stream.
  - Every failure gives a non-empty reason.
  - Apply the same audio checks the mux applies at assembly (`mux.py:180-193`).

**Tests:**
- **Fake-shell unit tests** for each finding above:
  - the path replaced between the guard and the shell (the original's bytes survive);
  - a second process recovering while a deletion is held open (nothing is touched);
  - a read-only file;
  - an identity mismatch;
  - a stale auto-delete save;
  - bin "too big" and "turned off" (kept, no shell call);
  - a non-OSError after the guard.
- **On the real PC**, synthetic files on NTFS only:
  - the three P1d-2 checks again;
  - a read-only file recycled and restored from the bin with its attributes;
  - the path-replacement race through a test hook, where the original's SHA-256 is unchanged.
- **Never change the owner's Recycle Bin settings.** Test the size and off cases with fakes.

## 2. Part E: estimates before calibration

**Facts from the review:**
- Default Fast estimate: 162.9 ms per source frame. The actual was 66.9 ms.
- Default Standard estimate: about 591 ms per source frame. The actual was about 435 ms.
- Calibration runs only from Settings or `ve bench --calibrate`, has no timeout, and its wall time is unknown.
- `calibrated` is a single boolean. "No machine profile" and "no reference for the chosen model" show the same badge.
- In the no-reference case the model delta is skipped silently (`model.py:171-179`). A model 4× slower than C1 is then estimated as C1.

**Rules:**
1. **Built-in profile for the RTX 4060 Ti 8 GB.**
   - Commit a machine profile (numbers only) produced by `bench --calibrate` on this PC from the 5 s **reference** clip, never from an acceptance clip. State in the report which run it came from.
   - Use it when no measured profile exists for this GPU. Match it by GPU name, not by driver.
2. **Driver change.**
   - When a measured profile exists for the same GPU name with another driver, use the newest one.
   - This does not make the estimate "uncalibrated". Settings shows "Speed measured with driver X. This PC now has driver Y." next to "Run speed calibration".
3. **Labels.** Keep three cases apart:
   - **Measured or built-in profile:** a normal estimate. Settings says which profile is used.
   - **No profile for this GPU:** "uncalibrated" badge and a ±25% range, as now.
   - **A chosen model has no reference for this GPU** (for example a model added later with `ve models add`): the Add card says "Speed unknown for <model>. Run speed calibration." It must never quietly reuse the default model's cost. Adding stays allowed.
4. **Calibration.**
   - It stays manual; the app never uses the GPU without the owner's action.
   - Make it cancellable.
   - Record its wall time. Show "about N min" on the button from the last run, or from the installed models when there is no run yet.
   - Report the wall time with only the default models installed, and with every installed model.
5. The Add cards, Up next, admission, the planner and Compare's "About X for this video" keep using the one estimate function.

**Acceptance on the RTX 4060 Ti:**
- **Setup:** a fresh engine home with no measured profile, so the built-in profile is used. No per-job correction.
- **Jobs:**
  - the four 30 s portrait jobs from P1d-2: C1, SCUNet, C1 + SPAN and Fast;
  - a 30 s landscape job: 1280×720 at 30 fps, Standard with C1, output 1920×1080 at 60 fps.
- **Gate:** the first estimate of each job is within ±15% of the actual time.
- **Tests:**
  - A changed driver string gives the same estimate (within 0.1%) and the Settings note.
  - A fixture model without `reference_speed` shows "Speed unknown".
  - Unit tests cover the profile selection order: measured exact → measured same GPU (newest driver) → built-in → defaults.

## 3. Part L: live progress and a cheaper event stream

**Facts from the review:**
- **Every second, per client:**
  - `os.stat` runs on all ~1,010 manifests under the store lock (`store.py:393-408`);
  - operations are deep-copied through JSON, and a sorted-key dump is made (`engine.py:470-487`);
  - `health()` re-reads `schedule.json` and queries the registry (`engine.py:219-300`).
- **Every 5 s:**
  - `list_jobs` deep-copies every manifest (`store.py:428-431`);
  - `queue()` stats the original and output of every job and deep-copies the rows again;
  - the result is keyed on `id(queue)`, so it is serialised again even when nothing changed; `server.py:252` then drops the duplicate.
- **Progress:**
  - `live_progress` is not in the key, so progress reaches the GUI only about every 5 s;
  - the GUI applies every message without a throttle (`App.tsx:211-225`);
  - the child reports about 7 times per second in Fast and once per C1 clip (about every 4.8 s) in Standard.
- **History sorting:** sort and grouping run over all 1,000 records on every render (`Home.tsx:586-625`).

**Rules:**
1. **Two kinds of events.**
   - **Progress event:** only for running jobs, and small: id, percent, work left, finish time, fps, phase and step.
     - Send it when a value changes, at most once per second per client.
     - While a job runs, send one at least every 2 s. Recompute "work left" from the measured rate, so it counts down smoothly between child reports.
   - **Structural snapshot:** only when something structural changed, for example a job added, removed or changing state, a manifest revision, an operation, health or the schedule.
     - Unchanged data is not rebuilt or serialised on a timer.
     - If you keep a safety refresh, make it at least 60 s apart, and make an unchanged check cost no more than comparing keys.
2. **Terminal records** (done, failed, cancelled):
   - Build each row once per manifest revision and cache its serialised form. Never deep-copy whole manifests to build the list.
   - The list carries only what the History list, the detail panel and their actions need (review list: `Home.tsx:690-735`, `HistoryDetail.tsx:31-33`, `App.tsx:435-440`).
   - Anything heavier, for example the full media probe for "Compare again" or "Retry", comes from a structured per-job JSON endpoint when the action needs it.
3. **File states** (`output_state`, `original_state`) of terminal records are refreshed:
   - by a background pass at most every 60 s;
   - when History opens;
   - right after the app's own deletions and restores.

   They are not refreshed every 5 s for every job.
4. **`health()`:** cache `schedule.json` by modification time. Query the registry at most every 60 s.
5. **GUI:**
   - Progress text repaints at most once per second, as a guard even when the service already limits it.
   - Memoise History sort and grouping on the record set, so a progress event does not re-sort 1,000 records.

**Acceptance:** see Part P (service CPU and real-engine progress).

## 4. Part A: Add checks

1. **HDR source.**
   - A PQ or HLG file makes `probe()` raise before the HDR warning is built (`probe.py:120-121` versus `engine.py:663-664`). One HDR file then fails the whole multi-file estimate with HTTP 400.
   - Evaluate each file on its own. The HDR file gets its "HDR" warning with "Remove it", and the other files get normal estimates.
   - Test it through the real API with a synthetic PQ-tagged clip in a mixed multi-file request, not a fabricated warning.
2. **Service enforcement.**
   - At add time the service applies the same blocking rules as the dialog: HDR, free space, Smart App Control, cleanup below 256 px and the AV1 minimum size. `ve add` and the API cannot bypass them.
   - The error names the rule.
   - Downscale stays a non-blocking note.

## 5. Part P: harness and budgets (revised)

1. **Repeats.**
   - Run every renderer measurement 10 times. Report all samples, the median and p90. The gate uses the median.
   - Run the service CPU measurement 3 times and gate on the median.
2. **Screens.**
   - **Warm switch** (second and later visit) between Home, History, Schedule, Models and Settings, with the 1,000-record fixture: median ≤100 ms.
   - **Cold first open of History** with 1,000 records: median ≤300 ms.
   - Measure the two separately. Remove `history_open_ms = screens.History`.
3. **Input.**
   - Event Timing input delay (`processingStart − startTime`): max ≤50 ms.
   - Interaction duration: p98 ≤200 ms over all recorded interactions. Also report the max and which interaction it was.
4. **Progress.**
   - The average progress-text change rate is ≤1.0 Hz over 30 s, and no two paints are less than 900 ms apart.
   - Measure it with the fake engine, and with the real engine on the GPU during one Fast and one Standard job.
   - With the real engine, at least 95% of the gaps between progress events are between 0.9 s and 2.1 s.
5. **Service CPU.**
   - **Fixture:**
     - 1,000 terminal records with realistic diagnostics (timing, quality and detector fields of a real finished job);
     - 10 queued jobs and one running Standard job;
     - one idle client.

     Commit the synthetic fixture generator under `gui/tests/perf/`.
   - **Gate:** ≤5% of one core.
   - **Scaling:** also report 5,000 records without a gate, to show that the cost no longer grows with History.
6. **Unchanged budgets:**
   - keystroke ≤50 ms;
   - preview ≤500 ms after the last keystroke;
   - idle renderer ≤2% of one core.
7. **Part F totals:** after Part L, measure the full preview from cold GPU admission again for C1, SCUNet and RIFE 4.25. Each must be within 5% of the new baselines.

## 6. Part G: acceptance

- **G1:** screenshots, at 1280×800 and 1100×700, of only the screens this cycle changes, for example Settings with the calibration note and the Add dialog with an HDR file. Store them outside the repository and list their paths.
- **G2:** the CI clipping tests stay green.
- **G3:** every Part P number.
- **G4:** the GPU evidence:
  - Part E: 5 jobs;
  - Part L: real-engine progress;
  - Part P7: the 3 totals;
  - Part S: run the real-PC deletion checks again if the deletion code changed.
- **G5:** all GPU-marked tests. The default pipeline output must not change; strict equality as before.
- **G6:**
  - `ruff`, `ruff format --check`, `pyright`, CPU tests and the D2 suite;
  - GUI lint, typecheck, unit tests, build, e2e and package;
  - Windows and Ubuntu CI green on the final commit, recorded in the report.
- **The owner's visual check** is not your job. After this cycle, build the package and give its path in the report. The owner will run `P1d_owner_check.md`.

## 7. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs are in English.
- **Never commit:**
  - media, weights, previews or generated videos;
  - `node_modules` or build output;
  - the design export or screenshots;
  - the owner's logs or private sample names.
- **User videos:** never deleted permanently. Only the deletion module may remove a user's video path, and only to the Recycle Bin, behind the guard.
- No models that add skin texture, and no GAN real-world video models. No new catalog entries.
- Keep the service security model. No telemetry, no auto-update.
- Update `docs/GUI.md`, `docs/API.md` and `docs/TROUBLESHOOTING.md` for every change.

## 8. Part X: optional, only after everything above passes

- **X1.** Re-qualify the Real-ESRGAN blend with tile 128 and halo 16. It qualifies if the sampled process peak is at most 5.0 GB.
- **X2.** Keep the last compare model loaded for 120 s while the queue is idle. Report the gain, and turn it off if it ever delays a queued job.

## 9. Report (`.ai/LAST_REPORT.md`, English)

- A table per part (S, E, L, A, P, G, X): done / partial / NOT RUN / BLOCKED, with evidence (tests, numbers, file:line for key changes).
- **Part E:** for each of the 5 jobs, the estimate, the actual time and the error. Also the calibration wall times, and which run produced the built-in profile.
- **Part P:** every sample, the median and p90.
- **Part S:** each finding, fixed or not, with its test.
- The path of the packaged app for the owner's check.
- "Questions for the designer", each with the default you chose.
- Exact reproduction steps.

Never report a test as passed if it did not run.

## Owner follow-up (2026-10-12, Japan time)

Continue the work. Do not forget to change the Settings icon to a gear.
