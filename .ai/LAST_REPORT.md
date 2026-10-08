# VE-P1a-7 — Existing-evidence audit

Task ID: VE-P1a-7. Status: BLOCKED. Date: 2026-10-08.
Branch: p1-restoration-gui. PR #2 remains a draft.

## Blocking question

Task A requires separate historical assembly, validation, full-quality and idle
measurements from existing P1a-6 logs, with no rerun. Those stages were not timed
or logged separately. Only their combined interval is recoverable. No invented
stage durations or relabelled residuals are reported.

Claude decision requested: accept the exact aggregate reconciliation below,
mark individual historical stages unavailable, and authorize continuing B/C with
separate timing in new runs; or specify an additional measurement that is clearly
a new experiment, not a reconstruction of the historical run. The owner requires
stopping on a material missing requirement rather than changing the specification.
No implementation decisions, encoder changes, or acceptance thresholds were changed.

## Acceptance

| Criterion | Result | Evidence |
|---|---|---|
| A1 | FAIL / incomplete evidence | Aggregate total and within-PID memory reported; individual historical stage durations unavailable |
| A2 | NOT RUN | No inline implementation, equality or overhead measurement |
| A3 | NOT RUN | No finalization calibration/planner/progress implementation |
| A4 | NOT RUN | No fresh P1a-7 Fast soak |
| A5 | NOT RUN | No Standard overhead experiment or repeat accuracy run |
| A6 | NOT RUN | No build/lint/type/CPU/GPU/CI suite for this evidence-only change |

P1a-6 results are preserved in Git at 4f02cbf and externally; they are not claimed
as validation of unimplemented P1a-7 changes.

## Task A: exact recoverable timing

Sources: fast-soak-fixed/home/reports/soak_report.json, job manifest and job.jsonl.
The supervisor active clock excludes scheduled pauses. Seconds:

| Component | Seconds | Meaning |
|---|---:|---|
| Controller segment actual_seconds sum | 13943.255627 | Includes subprocess startup/teardown |
| Last segment-complete event to job-complete event | 3416.376805 | Combined finalization, with no individual stage boundaries |
| Remaining active-clock residual | 299.248568 | Controller/supervisor/control/scheduling overhead; exact idle portion unknown |
| Total | 17658.881000 | Equals reported 17658.9 seconds after rounding |

Engine-only segment time sums to 13691.167134 s. Controller minus engine equals
252.088493 s; these are nested measurements and must not be added to the table.
Assembly, validation, full-quality and idle-only individual durations: NOT AVAILABLE.
The controller logs no events between last segment completion and job completion.
Assembly validates internally without timing. Quality uses several FFmpeg passes
without timing; temporary metric logs were removed by its temporary-directory context.

215784 source frames / engine time = 15.760818 input fps. The 17.4 fps reference
in the instruction implies a 9.4206% throughput decrease (10.4004% more time/frame).
This does not prove causality. Encoder.write synchronizes, copies surfaces to
owned host memory, then submits to NVENC. The recorded encode counter includes
color conversion/copy/submission/finish, with no isolated host-copy timing or
matched before/after comparison. The cost attributable to the copy is UNKNOWN;
there is no evidence that its isolated cost exceeds 10%. No encoder change made.

| Overlapped counter | Seconds |
|---|---:|
| Decode worker lifetime (includes queue backpressure) | 13371.490594 |
| Resize calls | 195.518633 |
| RIFE calls | 12056.081095 |
| Encode calls including finish | 3192.690188 |
| Handoff and reference checks | 1775.577565 |

Workers overlap; these counters are not an additive stage breakdown or standalone
throughput benchmark. Divide 215784 by each duration for source-frame-equivalent
fps; encode covers 431568 output frames. No unsupported causal claim is made.

## Dedicated memory within each engine process

ProcessExecutor.run spawns a new engine process for each segment. The earlier
+255.856640 MB is a comparison across processes and time windows, not growth of
one persistent GPU engine. Grouping actual samples by PID gives the table below.
MB is decimal. Samples are approximately 60 seconds apart (only 3–4 per engine).
First-loaded means first recorded dedicated sample >100 MB; the initial 24576-byte
pre-load sample is excluded. Deltas include normal clip/allocation variations;
they are not measured leaks or minute-10-to-end steady-state trends.

| PID | Controller restart side | Samples | First-loaded MB | Last MB | Delta MB | Peak MB |
|---|---|---:|---:|---:|---:|---:|
| 23884 | Before | 4 | 4353.151 | 3489.120 | -864.031 | 4353.151 |
| 23972 | Before | 3 | 3226.968 | 2327.290 | -899.678 | 3226.968 |
| 17792 | Before | 3 | 4246.196 | 2205.651 | -2040.545 | 4246.196 |
| 14652 | Before | 4 | 3401.036 | 3596.071 | 195.035 | 3596.071 |
| 12480 | Before | 3 | 2314.703 | 3373.777 | 1059.074 | 3373.777 |
| 8164 | Before | 4 | 3384.263 | 3356.996 | -27.267 | 3384.263 |
| 20160 | Before | 4 | 3533.156 | 3470.242 | -62.915 | 3866.608 |
| 10740 | Before | 3 | 3516.379 | 2499.256 | -1017.123 | 3516.379 |
| 10648 | Before | 3 | 3533.160 | 2337.780 | -1195.381 | 3533.160 |
| 10500 | Before | 4 | 3556.229 | 3474.440 | -81.789 | 3556.229 |
| 19840 | Before | 3 | 2348.261 | 3289.883 | 941.621 | 3289.883 |
| 22432 | Before | 4 | 3222.778 | 3868.701 | 645.923 | 3868.701 |
| 16532 | After | 4 | 3537.355 | 4101.497 | 564.142 | 4101.497 |
| 24832 | After | 3 | 4114.076 | 2352.460 | -1761.616 | 4114.076 |
| 17156 | After | 3 | 3545.743 | 2444.730 | -1101.013 | 3545.743 |
| 9556 | After | 4 | 3331.830 | 3851.928 | 520.098 | 3851.928 |

Controller stop epoch 1791397015.7821596; restart epoch 1791397022.9582138.
There is no engine PID spanning the restart. Missing samples are not treated as zero.

## Expected, actual, files and reproduction

Expected: recover separate stage times from existing logs. Actual: only segment
intervals and the combined post-segment interval exist. Warning: exact idle and
individual finalization stage durations cannot be reconstructed from this evidence.

Changed tracked files: .ai/CURRENT_TASK.md (full pasted instruction), .ai/LAST_REPORT.md.
No product code changed. Build/tests/GUI: NOT RUN. No subagents used. B/C intentionally
NOT RUN until Claude resolves the historical-evidence requirement. No rerun was
substituted for historical data.

Existing evidence outside repository:
C:\Users\pro\Documents\VideoEnhancer-P1a-6\fast-soak-fixed\home\reports\soak_report.json
C:\Users\pro\Documents\VideoEnhancer-P1a-6\fast-soak-fixed\home\jobs\9b23f111416745c090461abb2ec7deb8\manifest.json
C:\Users\pro\Documents\VideoEnhancer-P1a-6\fast-soak-fixed\home\jobs\9b23f111416745c090461abb2ec7deb8\job.jsonl
C:\Users\pro\Documents\VideoEnhancer-P1a-6\standard-stability-retry\home\reports\soak_report.json

Reproduce: sum segments[].actual_seconds and segments[].stats.seconds; subtract
last segment-complete log timestamp from job-complete timestamp; subtract both
intervals from actual_wall_excluding_pauses_seconds for the residual. Group stability
job_memory_samples by PID; compare first sample above 100 MB with last dedicated
sample; classify each group against stop_event.timestamp. The ignored helper
.tmp/p1a7_existing_evidence.py reproduces the primary timing audit and raw PID groups.

Git start: clean p1-restoration-gui at 4f02cbf2b17208f282f9fd43c45ca09a9c65e5d7.
Remote fetched and matched HEAD (0 ahead / 0 behind). Only this cycle's two .ai
files are committed/pushed; the final response identifies the resulting commit.
PR #2 remains draft. No main push, merge, media or private source names committed.
