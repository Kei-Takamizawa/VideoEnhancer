# VE-P1a-7 — Inline quality and predicted finalization

Task ID / Cycle: VE-P1a-7 / P1a-7. Date: 2026-10-08.
Status: PARTIAL (CI is pending publication at report-writing time).
Branch: p1-restoration-gui. PR #2 remains draft. Start HEAD: bbfd49c8a080b1510851478ef658fb1126678a5f.

## Summary and acceptance

Default jobs and trials aggregate inline quality instead of running a post-encode
full pass. Fidelity samples every 10th global source-aligned output frame.
Temporal diagnostics reuse every frame's existing 16x16 detector summaries.
The full FFmpeg pass is explicit development-only `ve report --full-quality JOB`.
Finalization is calibrated, included in initial/remaining ETA and the day planner,
corrected from completed observations in the machine profile, and exposes its phase.
Finalization steps and scheduler waits have timed start/end events in job JSONL
and timed intervals retained in the job report.

| Criterion | Result | Evidence |
|---|---|---|
| A1 | PASS | Designer accepted historical aggregate reconciliation and within-PID table below |
| A2 | PASS | Sampled offline replay test; Fast inline mean 0.6162% / maximum 0.6466%; Standard maximum 0.2364%; explicit full-quality CLI test |
| A3 | PASS | Fresh generated-job calibration; profile observation correction; fake-clock admission/planner and progress tests |
| A4 | PASS | Fresh completed Fast run, exact output frames, two verified pauses, estimates and memory below |
| A5 | PASS | Standard overhead below 2%; retain accepted P1a-6 completed 15-minute accuracy result |
| A6 | NOT RUN (CI pending) | Local ruff/format/pyright, CPU and GPU suites and build PASS; Windows/Ubuntu CI checked after push in the final chat |

No thresholds, presets, model weights, encoder behavior, GUI/API or training changed.
No subagents used.

## Task A: accepted historical reconstruction

Individual historical assembly, validation, quality-pass and idle-only durations
are UNAVAILABLE. The designer explicitly accepted the recovered aggregate.

| Component | Seconds |
|---|---:|
| Controller segment actual_seconds | 13943.255627 |
| Combined finalization (last segment event to completed event) | 3416.376805 |
| Controller/supervisor/scheduling residual (idle-only portion unknown) | 299.248568 |
| Total | 17658.881000 |

Engine-only segment time: 13691.167134 s, nested within controller segment time;
controller minus engine is 252.088493 s and must not be added again.
215784 / 13691.167134 = 15.760818 input fps. Versus 17.4 fps this is a 9.4206%
throughput decrease / 10.4004% more time per frame. Isolated host-copy cost and
causality are UNKNOWN. No matched before/after host-copy measurements exist;
no encoder change or unsupported attribution is made (designer addendum: report-only).

| Overlapped counter | Seconds | Source-frame-equivalent fps |
|---|---:|---:|
| Decode worker lifetime, including backpressure | 13371.490594 | 16.137617 |
| Resize calls | 195.518633 | 1103.649287 |
| RIFE calls | 12056.081095 | 17.898353 |
| Encode calls, including finish/copy/conversion | 3192.690188 | 67.586890 |
| Handoff/reference checks | 1775.577565 | 121.528907 |

Encode processed 431568 output frames; its output-frame equivalent rate is
135.173780 fps. These counters overlap and are not additive stage durations
or independent throughput benchmarks.

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


## Task B: implementation and tests

- Inline partial fidelity sums/minima and temporal sums/boundary summaries persist per segment.
- Aggregation includes clip and segment joints, including cross-segment differences and cut exclusions.
- Initial and remaining ETA include finalization; the planner admits it as a whole stage inside a window.
- Machine finalization coefficients and an EMA correction persist; stale calibration observations do not overwrite a newer calibration.
- Packet enumeration validates own MP4 outputs without decoding all frames; short H.264, HEVC and AV1 outputs matched decoded counts exactly (13/13 for each).
- Output validation retains exact counts, duration, audio-presence/timing and container/video contract checks.
- Progress is weighted by predicted time, capped at 99.9% before done (including textual rounding), with phase/step percentages.
- The optional full-quality command ran successfully on a 12-frame CPU file; it does not modify job timing or stored inline quality.

Equality test: independently re-decode source and replay captured pre-encode output
frames on a 24-input-frame / 48-output-frame CPU job, comparing five global
samples. PSNR mean tolerance 1e-5 dB, SSIM mean tolerance 2e-5. Temporal split/full
replay equality is tested at clip/segment joints and cut exclusions, within 1e-7.
These use the defined inline measurements. Numerical equivalence with the legacy
FFmpeg post-encode diagnostic is NOT CLAIMED: that includes codec loss, 8-bit Y
quantization and full-resolution temporal differences. The inline method is
normalized BT.709 Y, area resize to source resolution, 8x8 SSIM windows at stride 4
(smaller windows for inputs below 8 pixels), and 16x16 temporal summaries.

Step percent is reported at start/end boundaries; finalization phase share uses
calibration step durations. This is engine reporting, not a GUI redesign.

## Verification, warnings and resolved failure

| Check | Result |
|---|---|
| ruff check . | PASS |
| ruff format --check . | PASS (77 files) |
| pyright | PASS (0 errors / warnings) |
| CPU suite, not gpu and not soak | PASS: 182 passed, 3 skipped, 18 deselected |
| GPU suite, gpu and not soak | PASS: 18 passed, 185 deselected |
| 100000-byte subprocess result regression | PASS |
| Real GPU subprocess smoke, 60 Fast input frames | PASS: 7.976780 s, inline 0.071169 s (0.8922%) |
| Hatchling wheel and sdist build | PASS; wheel 54 entries, includes both new modules, no weights/media |
| Final tracked-text privacy check | PASS: 1 test after staging the 22 cycle files |
| Windows / Ubuntu Actions CI | NOT RUN at writing time; requires publication; result reported in final chat |
| GUI / Computer Use | NOT RUN; explicitly out of scope |

The first fresh Fast attempt (job acd75e10cbe34908823d2af290bae0e6) exposed an
existing IPC deadlock: a measured 11329-byte result exceeded the 8192-byte Windows
pipe buffer, but the parent joined the child before receiving. It was cancelled
through the CLI, with zero completed segments, at 351.439389 active seconds.
Its report says incomplete / soak FAIL / estimate FAIL and remains external.
The parent now drains results while the child is alive. A 100000-byte regression
and a real 60-frame GPU subprocess verified the fix before the fresh acceptance
run in `fast-soak-fixed`; no resumption was presented as a fresh run.

Early test failures were fixed without changing acceptance thresholds: missing
finalization fields in old test expectations; mock callback/metadata signatures;
a test timezone/import; fidelity collection initially bypassed by the no-repair
return; SSIM cancellation for flat areas (bounded covariance); and IPC backpressure.
Initial sandbox attempts could not execute FFmpeg/build dependencies. The listed
successful checks ran with the required execution access. `uv` was not on PATH;
builds used the existing local Hatchling 1.32.4 tools. No dangerous authentication
or permission workaround was used.

## Fresh Fast estimates and finalization

Job: 59bedc111e08460fa68b0e0f117fa3b3. Same P1a-6 synthetic input, 215784 source
frames. State: done. Expected / actual output frames:
431568 / 431568.
Detector raw/final flags: 0 / 0.
Scheduled pauses verified: [True, True].
Engine input rate: 15.703019 fps.
Inline fidelity samples: 43,157 (stride 10 across 431,568 output frames).

| Estimate/reference | Seconds | Relative error |
|---|---:|---:|
| Initial | 13699.916142 | -5.1597% (target +/-30%) |
| At first completed progress >=10% | 14092.287628 | -2.4435% (target +/-15%) |
| Actual active wall time | 14445.254722 | Reference unchanged |
| Finalization predicted at admission | 50.783482 | Actual/predicted - 1: 141.6290% |
| Finalization observed | 122.707609 | Includes timing persistence overhead |

Calibration: a=0.152323518157 s,
b=2.452197337e-09 s/byte, c=1.00108037086e-05 s/frame;
8 generated three-segment assembly/validation samples; residual RMS
0.006645845 s. Profile correction and observation are retained
under the fresh home/profiles folder.
The saved next-job finalization correction is 1.424886937 (one observation,
EMA 0.7 previous + 0.3 observed/baseline). It was verified in the profile file;
the first full-job finalization prediction remains an underprediction.

| Recoverable new timing | Seconds |
|---|---:|
| Controller segment time | 14006.569638 |
| Combined observed finalization | 122.707609 |
| Active controller/supervisor/scheduling residual | 315.977475 |
| Active total | 14445.254722 |
| Timed assembling step | 110.737223 |
| Timed validating step | 9.621585 |
| Timed aggregating step | 0.868308 |
| All timed scheduler waits (includes excluded scheduled pauses) | 2007.882211 |

The first three rows reconcile exactly. Timed step intervals are nested within
combined finalization. Scheduler waits include off-hours and must not be added
to active time. Engine time 13741.561034 s and inline metric time
84.673717 s are nested inside controller segment time.

## Fresh Fast memory

These are the unchanged P1a-6 acceptance comparisons: peak in the first and last
five-minute windows after minute 10. Engine processes change per segment;
these resource comparisons are not proof of persistent-process leakage.

| Resource | Growth MB | Limit MB | Result |
|---|---:|---:|---|
| process_dedicated_gpu_bytes | 12.582912 | 150 | PASS |
| torch_reserved_bytes | 12.582912 | 100 | PASS |
| tree_rss_bytes | 145.6128 | 200 | PASS |

## Standard overhead and retained accuracy run

Each sample used 90 input frames, two enabled and two disabled fresh processes.

| Sample | Disabled mean s | Enabled mean s | A/B delta | Measured inline fraction range |
|---|---:|---:|---:|---:|
| sample-04 | 40.388017 | 40.447805 | 0.1480% | 0.1817%–0.2364% |
| sample-05 | 39.110651 | 39.207238 | 0.2470% | 0.1886%–0.1890% |

A/B differences contain normal run variance; directly timed inline work was
0.073189–0.096000 s per segment, at most 0.2364%. The >2% condition was not met,
so the Standard 15-minute run was intentionally not repeated. Retained accepted
P1a-6 result: initial 11367.293360 s
(-10.8816%), at 10%
11572.703614 s
(-9.2712%), actual
12755.272370 s;
26980 source / 53960 output
frames, detector 10/0 raw/final.
This is historical evidence, not a new P1a-7 Standard accuracy measurement.

## Changed files

- .ai/CURRENT_TASK.md
- .ai/LAST_REPORT.md
- docs/ARCHITECTURE.md
- scripts/soak.py
- src/videoenhancer/bench/finalization.py
- src/videoenhancer/bench/runner.py
- src/videoenhancer/cli.py
- src/videoenhancer/estimate/model.py
- src/videoenhancer/jobs/store.py
- src/videoenhancer/media/mux.py
- src/videoenhancer/media/probe.py
- src/videoenhancer/pipeline/inline_quality.py
- src/videoenhancer/pipeline/runner.py
- src/videoenhancer/schedule/controller.py
- src/videoenhancer/schedule/planner.py
- src/videoenhancer/trial.py
- tests/test_controller.py
- tests/test_estimate.py
- tests/test_finalization.py
- tests/test_jobs.py
- tests/test_planner.py
- tests/test_quality_trial.py

## External outputs, logs and reproduction

All videos, model weights, calibration data and measurement JSON stay outside
Git at C:\Users\pro\Documents\VideoEnhancer-P1a-7.

- calibration/bench_report.json and calibrate.log
- overhead-00 through overhead-07/report.json and overhead.json
- ipc-smoke.mp4 and ipc-smoke.json
- fast-soak/home/reports/soak_report.json (cancelled IPC failure, preserved)
- fast-soak-fixed/home/reports/soak_report.json (fresh completed acceptance run)
- fast-soak-fixed/home/jobs/59bedc111e08460fa68b0e0f117fa3b3/manifest.json and job.jsonl
- fast-soak-fixed/enhanced.mp4 and fast-soak-fixed-supervisor.log

Historical Standard evidence is in VideoEnhancer-P1a-6/standard-accuracy-final/
home/reports/soak_report.json. Historical Task A evidence is in fast-soak-fixed and
standard-stability-retry beneath that P1a-6 folder.
Local verification logs are ignored .tmp/p1a7-cpu5.log and .tmp/p1a7-gpu2.log.

Reproduce with installed verified C1/RIFE models and FFmpeg, using a fresh external
VE_HOME with models and adapter-sources copied from the existing development home:

```powershell
$env:VE_HOME = 'C:\Users\pro\Documents\VideoEnhancer-P1a-7-reproduction\home'
$env:VE_FFMPEG_DIR = '<installed FFmpeg bin directory>'
.venv/Scripts/python.exe -m videoenhancer.cli bench --calibrate --output-dir '<external calibration directory>'
.venv/Scripts/python.exe -u scripts/soak.py --input 'C:\Users\pro\Documents\VideoEnhancer-P1a-6\long-inputs\fast-synthetic-2h.mp4' --output '<fresh external output.mp4>' --preset fast --mode complete --scheduled-pauses 2
.venv/Scripts/python.exe -m videoenhancer.cli --json report <job-id>
# Development-only, outside acceptance timing:
.venv/Scripts/python.exe -m videoenhancer.cli --json report --full-quality <job-id>
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/pyright.exe
.venv/Scripts/python.exe -m pytest -m 'not gpu and not soak' --basetemp .tmp/p1a7-cpu-reproduction -p no:cacheprovider
.venv/Scripts/python.exe -m pytest -m 'gpu and not soak' --basetemp .tmp/p1a7-gpu-reproduction -p no:cacheprovider
$env:PYTHONPATH = (Resolve-Path .tmp/build-tools).Path
.venv/Scripts/python.exe -m hatchling build
```

Expected: exact frames, zero final detector flags, estimates within +/-30% / +/-15%,
inline overhead <=2%, finalization inside operating hours, recoverable stage/wait
intervals, local suites and both CI platforms green. Actual: numbers above;
CI remains unexecuted at the instant this report is committed and is checked after push.

Unresolved / Claude decisions: no new architecture or product-policy decision
was made. The designer reviews diagnostic definitions and measured limitations
above and decides when to merge draft PR #2. No claim of legacy post-encode numeric
equivalence or perceptual restoration quality is made. Finalization extrapolates
short calibration through bytes/frames; the completed observation corrects the
next job, and the measured prediction error is reported without changing limits.

Intentionally not run: GUI/API; training/new models; encoder changes; a second
full quality pass on the 2-hour acceptance output; another Standard 15-minute
run (the conditional overhead threshold was not exceeded).

Git: the 22 listed cycle files are the intended stage/commit scope, including full
CURRENT_TASK and this report. Private media/cache/weights are excluded. The final
chat records the actual branch commit/push and post-publication CI result. No main push, force push, history rewrite or merge.
