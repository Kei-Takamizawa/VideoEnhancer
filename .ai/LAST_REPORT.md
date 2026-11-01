Task ID: VE-P1e-3d2
Status: PARTIAL
Cycle: 1 - Windows
Execution: FINISHED - partial cycle; remaining product issues deferred to the designer.

## Result and execution

Parts A/B and a provisional median profile were implemented. This candidate is
not ready for merge: H264 decode was not measured, the final CPU suite has one
failure, G-10 finalization misses its gate, and two scheduling readers still
lack cold/warm context. Accuracy PASS labels below describe measured results;
they do not turn the incomplete profile into a fully calibrated profile.

Initial read-only Git checks confirmed a clean claude/project-thread-6lra47 at
69b0450a5b881a18f75a30bc99c7c2276a1dc463 (task base: main 38b41ae). Windows
PowerShell and repo/local-env.ps1 were used. No Git mutation, commit, push, PR or
merge was performed; AGENTS assigns those actions to the operator. CURRENT_TASK
was preserved as the complete instruction. No owner app/home was used. Tests and
measurements used synthetic media and contained work/scratch homes.

Private evidence is in work/evidence/VE-P1e-3d2. Run ledgers record starts, homes
and PIDs before long waits. Their existence alone is not completion evidence.

## Part A - startup model and local learning

Profiles read startup_by_preset[preset] as {cold, warm}; a legacy scalar supplies
both terms. Standalone estimates and GPU model qualification default to cold.
The shared estimate.startup.cold_parts function assigns initial 1-based cold
parts 1, 51, 101, etc. Controller timing.worker_parts records available worker
use; recorded boundaries reset future estimates after waits, pause, shutdown,
failure/retry, dead workers and retry batch changes. Successful part statistics
record startup_kind. The main admission estimate reads the same classification.

Local learning keeps separate last-20 medians by preset and kind; spilled jobs
remain excluded, matching existing policy. Revision p1e3d2-warm1 prevents the new
profile from reading earlier-revision observations. No observation migration or
owner observation-file deletion/rewrite was performed.

Tests cover 1, 2, 50, 51 and 120 parts; resume and failed retry; scalar profiles;
separate local medians and revision mismatch; cold qualification; actual worker
reuse/fault recording. G-10 also observed a real scheduled resume: part 26 was
cold, startup 3.743537 s, total 183.248517 s, in a new worker PID 5748. The first
worker PID was 23476. The 50-part quota is unit-tested, not exercised by G-10's
40-part run.

Boundary: schedule/planner.py and controller.unit_admission still call the
standalone cold default. See Questions for the designer; do not interpret this
cycle as complete integration of every scheduling reader.

## Part B - calibration output and wall time

Calibration retains built-in finalization points and samples unchanged. Existing
measured curves on unknown GPUs are also retained. The tiny measurement is saved
as finalization.tiny_clip_fit and supplies the linear fallback only without a
curve. No disk scaling was applied. Simulated 1/10/30/120-minute predictions and
points/samples equality pass. A no-curve profile uses the tiny fit.

Actual startup calibration uses ProcessExecutor(reuse=True), a 45-frame synthetic
720x1280/30 source split into three 15-frame parts per Standard/Fast preset,
1080x1920/60 HEVC output. Cold is part 1, warm is the median of parts 2/3.
Measured profiles no longer retain fixed segment_overhead_seconds=2.0. The
existing calibration_wall_seconds -> calibration_minutes path remains the only
Settings duration source; the provisional median rounds to about 4 min. No GUI
code or actual GUI interaction was changed/performed.

The timing comparison below has the same missing-H264/P0 diagnostic limitations
in baseline and new runs. It proves the observed startup addition is below 90 s;
it is not a complete-data calibration result. No tiny-clip disk-scaling ratio was
measured or applied.

| Run | Benchmark wall s | Added startup stage s | Delta from baseline s | Root PID |
| --- | --- | --- | --- | --- |
| baseline | 224.64798 | N/A | N/A | 25732 |
| new 1 | 253.03266 | 31.353135 | 28.384675 | 13508 |
| new 2 | 254.8218 | 32.495155 | 30.173818 | 19296 |
| new 3 | 253.46998 | 31.32443 | 28.822001 | 10920 |

## Part C - provisional profile, incomplete data

All four completed benchmark reports (baseline and three new runs) skipped H264
NVDEC: no local 720x1280 H264 sample was supplied through VE_SAMPLES_DIR. The
candidate decode coefficient is null, so prediction falls back to 4e-9
s/(pixel-frame). I should have checked these fields before publishing the
provisional median and freezing the gates. P0 end-to-end also skipped with
"Analysed source timestamps are missing." This also occurred in the baseline.
Other listed component/model timings and reference size points were measured.
The summarizer now refuses null component coefficients; its expected rejection
(exit 1) was verified without changing the frozen profile hash.

The median profile includes size points through 1440x2560, startup cold/warm,
p1e3d2-warm1 and dated commit/method provenance. Original finalization points and
samples are unchanged. analysis_seconds_per_frame was retained from the old
profile, not remeasured. Raw runs are in calibration-fixed-{1,2,3}-bench.json;
profile sample arrays are aggregate/selected diagnostics, not a fourth raw run.

Values below are medians of three runs; spread is (max-min)/median. Unit costs
are s/(pixel-frame), factor is dimensionless, load/startup terms are seconds.

| Term | Old | Run 1 | Run 2 | Run 3 | Median used | Spread % |
| --- | --- | --- | --- | --- | --- | --- |
| components.decode.seconds_per_pixel_frame | 5.7699797e-10 | N/A | N/A | N/A | null / fallback 4e-9 | N/A |
| components.encode.seconds_per_pixel_frame | 2.5921192e-09 | 2.7233732e-09 | 2.7027786e-09 | 2.6558618e-09 | 2.7027786e-09 | 2.4978522 |
| components.encode.size_points[0].seconds_per_pixel_frame | 2.5921192e-09 | 2.7233732e-09 | 2.7027786e-09 | 2.6558618e-09 | 2.7027786e-09 | 2.4978522 |
| components.encode.size_points[1].seconds_per_pixel_frame | NOT_MEASURED | 2.5814562e-09 | 2.5814146e-09 | 2.5813436e-09 | 2.5814146e-09 | 0.0043610207 |
| components.color.seconds_per_pixel_frame | 3.9930556e-10 | 3.9941406e-10 | 4.0022294e-10 | 3.9996646e-10 | 3.9996646e-10 | 0.20223598 |
| components.color.size_points[0].seconds_per_pixel_frame | 3.9930556e-10 | 3.9941406e-10 | 4.0022294e-10 | 3.9996646e-10 | 3.9996646e-10 | 0.20223598 |
| components.color.size_points[1].seconds_per_pixel_frame | NOT_MEASURED | 5.2898944e-10 | 5.2879654e-10 | 5.2873626e-10 | 5.2879654e-10 | 0.047878108 |
| components.resize.seconds_per_pixel_frame | 3.0686969e-10 | 3.0563995e-10 | 3.0577257e-10 | 3.0565202e-10 | 3.0565202e-10 | 0.04338941 |
| components.resize.size_points[0].seconds_per_pixel_frame | 3.0686969e-10 | 3.0563995e-10 | 3.0577257e-10 | 3.0565202e-10 | 3.0565202e-10 | 0.04338941 |
| components.resize.size_points[1].seconds_per_pixel_frame | NOT_MEASURED | 3.0095758e-10 | 3.012424e-10 | 3.0126275e-10 | 3.012424e-10 | 0.10130387 |
| components.blend2x.seconds_per_pixel_frame | 1.765408e-10 | 1.7678192e-10 | 1.7656492e-10 | 1.7684221e-10 | 1.7678192e-10 | 0.15685462 |
| components.blend2x.size_points[0].seconds_per_pixel_frame | 1.765408e-10 | 1.7678192e-10 | 1.7656492e-10 | 1.7684221e-10 | 1.7678192e-10 | 0.15685462 |
| components.blend2x.size_points[1].seconds_per_pixel_frame | NOT_MEASURED | 1.9578044e-10 | 1.9618055e-10 | 1.9584825e-10 | 1.9584825e-10 | 0.20429823 |
| models.basicvsrpp-denoise.load_seconds | NOT_MEASURED | 1.4896891 | 1.5620877 | 1.4889203 | 1.4896891 | 4.9115886 |
| models.basicvsrpp-denoise.seconds_per_pixel_frame | NOT_MEASURED | 9.1357024e-08 | 9.124367e-08 | 9.1263766e-08 | 9.1263766e-08 | 0.12420438 |
| models.basicvsrpp-ntire21-decompress.load_seconds | 1.6541103 | 0.3333497 | 0.337949 | 0.3270741 | 0.3333497 | 3.2623098 |
| models.basicvsrpp-ntire21-decompress.seconds_per_pixel_frame | 2.6231761e-07 | 2.5235883e-07 | 2.5262391e-07 | 2.5258818e-07 | 2.5258818e-07 | 0.1049465 |
| models.rife-4.25.load_seconds | 0.3188243 | 0.1997717 | 0.2057016 | 0.2149761 | 0.2057016 | 7.3914836 |
| models.rife-4.25.seconds_per_pixel_frame | 2.2567775e-08 | 2.2286699e-08 | 2.2307696e-08 | 2.2290901e-08 | 2.2290901e-08 | 0.094191312 |
| models.rife-4.25.size_points[0].seconds_per_pixel_frame | 2.2567775e-08 | 2.2286699e-08 | 2.2307696e-08 | 2.2290901e-08 | 2.2290901e-08 | 0.094191312 |
| models.rife-4.25.size_points[1].seconds_per_pixel_frame | NOT_MEASURED | 2.5435693e-08 | 2.544417e-08 | 2.5441688e-08 | 2.5441688e-08 | 0.033319741 |
| pipeline_size_points.standard[0].factor | 1.0546985 | 0.98728575 | 0.98783325 | 0.98813059 | 0.98783325 | 0.085523966 |
| pipeline_size_points.standard[1].factor | NOT_MEASURED | 0.99040867 | 0.99072568 | 0.99314493 | 0.99072568 | 0.27618779 |
| pipeline_size_points.fast[0].factor | 1.3839229 | 0.94301264 | 0.9437582 | 0.94641104 | 0.9437582 | 0.36009229 |
| pipeline_size_points.fast[1].factor | NOT_MEASURED | 0.9536644 | 0.95712157 | 0.9532657 | 0.9536644 | 0.40432111 |
| startup_by_preset.standard.cold | 4.4917327 | 3.491042 | 3.9171248 | 3.5047662 | 3.5047662 | 12.157239 |
| startup_by_preset.standard.warm | 4.4917327 | 0.0776346 | 0.1907672 | 0.09317025 | 0.09317025 | 121.42567 |
| startup_by_preset.fast.cold | 2.5475333 | 1.7486575 | 1.8914596 | 1.7478829 | 1.7486575 | 8.2106816 |
| startup_by_preset.fast.warm | 2.5475333 | 0.2118056 | 0.18217305 | 0.21614815 | 0.2118056 | 16.0407 |

| Other term | Old | New |
| --- | --- | --- |
| max_measured_output_pixels | 2073600 | 3686400 |
| estimate_revision | p1e2-stage-sizes2 | p1e3d2-warm1 |
| analysis_seconds_per_frame | 0.0010458961222223782 | 0.0010458961222223782 |
| finalization points/samples | measured curve | unchanged |

Spread exceeds 10% only for Standard cold (12.157%), Standard warm (121.426%)
and Fast warm (16.041%). Run 2 has the highest Standard cold/warm and lowest
Fast warm. The absolute Standard warm range is 0.113133 s. The exact cause is not
established: per-startup-term traces were not retained by this calibrator, so
child import/model I/O versus parent IPC cannot be separated from these medians.
No coefficient was adjusted on a gate result.

| Tiny-fit diagnostic | Run 1 | Run 2 | Run 3 | Median | Spread % |
| --- | --- | --- | --- | --- | --- |
| a | 0.2482473 | 0.27377764 | 0.25549298 | 0.25549298 | 9.992581 |
| b | 8.7660151e-09 | 6.5875353e-09 | 6.7722179e-09 | 6.7722179e-09 | 32.167892 |
| c | 1.3387125e-06 | 1.2628149e-05 | 2.606281e-05 | 1.2628149e-05 | 195.7856 |

## Part D - estimate gates

Every valid processing gate began in a new home with the frozen provisional
built-in profile and no timing observations. Source/profiles were hashed before
the gates. No prediction field changed during or after the gates. After they
finished, only provenance was annotated INCOMPLETE; the exact original profile
and hash are preserved in profile-used-for-gates.json and
profile-metadata-correction.json. No completed gate was repeated or tuned.

Actual processing is analysis_seconds + sum(part.actual_seconds) + actual
finalization. Elapsed to done uses the persisted terminal timestamp minus adding
time; observer polling elapsed is also retained. First-finish errors use total
elapsed. Live errors use actual remaining time at capture, a stricter denominator
than total elapsed. The 15-minute configured gap was 14:15-14:30 UTC, in the
second half. Admission waiting began at 14:12:34 UTC after 25/40 parts (62.36%).
The gate worker was closed; CPU and GUI/static final checks finished during this
pause, before GPU processing resumed. GPU tests started only after G-Cal ended.

| Job | Measurement | Predicted s | Actual s | Error % | Gate | Result |
| --- | --- | --- | --- | --- | --- | --- |
| G-1440-attempt2 | initial processing | 419.62105 | 431.46941 | -2.746047 | +/-15% | PASS |
| G-Fast | initial processing | 241.56369 | 221.46733 | 9.074185 | +/-10% | PASS |
| G-10 | initial processing | 7031.1753 | 7231.9998 | -2.776888 | +/-10% | PASS |
| G-10 | first finish elapsed | 8135.5604 | 8324.3949 | -2.268448 | +/-10% | PASS |
| G-10 | 50% remaining finish | 4695.2746 | 4687.4967 | 0.165929 | +/-5% | PASS |
| G-10 | finalization | 12.071394 | 19.322049 | -37.525288 | +/-25% | FAIL |
| G-Cal | normal loaded profile | 19.322049 | 19.322049 | 0.000000 | +/-25% | PASS |
| G-Cal diagnostic | raw curve, no local learning | 12.071394 | 19.322049 | -37.525288 | +/-25% | FAIL |

G-10 was added at 2026-10-30T12:57:05.537045+00:00; persisted done is 2026-10-30T15:15:49.931974+00:00.
First finish prediction: 2026-10-30T15:12:41.097397+00:00. Observed polling elapsed
was 8325.686472 s versus 8324.394929 s to state done.

| Capture % | Actual % | Capture UTC | Predicted finish UTC | Error s | Remaining error % |
| --- | --- | --- | --- | --- | --- |
| 25 | 25.005556 | 2026-10-30T13:27:40.190947+00:00 | 2026-10-30T15:15:55.162328+00:00 | 5.230354 | 0.080594 |
| 50 | 50.011111 | 2026-10-30T13:57:42.435289+00:00 | 2026-10-30T15:15:57.709900+00:00 | 7.777926 | 0.165929 |
| 75 | 75.016667 | 2026-10-30T14:45:25.167674+00:00 | 2026-10-30T15:16:31.599869+00:00 | 41.667895 | 2.283467 |

G-Cal keeps points AND samples unchanged. Its actual profile loader applies the
existing G-10 local finalization factor 1.600647632, so before/after calibration
predictions with local learning are both 19.322049 s. The uncorrected curve stays
12.071394 s and still fails. Thus G-Cal PASS is not independent evidence that the
raw built-in curve is accurate; both contexts are intentionally exposed.
No curve or correction was manually fitted to G-10 or used for a rerun.

### Per-part predictions and actuals

Initial/actual kind shows the initial plan and observed worker. Admitted
prediction includes the existing live correction and current worker boundary.
All times are seconds; errors are (prediction/actual-1)*100.

| Job | Part | Initial/actual kind | Initial s | Admitted s | Actual s | Initial error % | Admitted error % | Actual startup s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G-1440-attempt2 | 1 | cold/cold | 179.0329 | 179.0329 | 183.0726 | -2.207 | -2.207 | 3.495577 |
| G-1440-attempt2 | 2 | warm/warm | 175.6213 | 176.8101 | 179.8229 | -2.337 | -1.675 | 0.040602 |
| G-1440-attempt2 | 3 | warm/warm | 63.6703 | 64.4290 | 65.0372 | -2.102 | -0.935 | 0.225119 |
| G-Fast | 1 | cold/cold | 119.3530 | 119.3530 | 106.6670 | 11.893 | 11.893 | 1.762926 |
| G-Fast | 2 | warm/warm | 117.8161 | 114.0593 | 104.7182 | 12.508 | 8.920 | 0.212480 |
| G-10 | 1 | cold/cold | 178.1783 | 178.1783 | 182.4934 | -2.364 | -2.364 | 3.559252 |
| G-10 | 2 | warm/warm | 174.7667 | 176.0365 | 179.2611 | -2.507 | -1.799 | 0.117733 |
| G-10 | 3 | warm/warm | 174.7667 | 177.0038 | 179.1327 | -2.437 | -1.188 | 0.108931 |
| G-10 | 4 | warm/warm | 174.7667 | 177.6425 | 179.0069 | -2.369 | -0.762 | 0.160281 |
| G-10 | 5 | warm/warm | 174.7667 | 178.0518 | 179.1134 | -2.427 | -0.593 | 0.242112 |
| G-10 | 6 | warm/warm | 174.7667 | 178.3703 | 179.0325 | -2.383 | -0.370 | 0.043607 |
| G-10 | 7 | warm/warm | 174.7667 | 178.5690 | 178.9608 | -2.344 | -0.219 | 0.093783 |
| G-10 | 8 | warm/warm | 174.7667 | 178.6865 | 179.0173 | -2.374 | -0.185 | 0.122865 |
| G-10 | 9 | warm/warm | 174.7667 | 178.7858 | 178.9832 | -2.356 | -0.110 | 0.162312 |
| G-10 | 10 | warm/warm | 174.7667 | 178.8450 | 179.1463 | -2.445 | -0.168 | 0.252680 |
| G-10 | 11 | warm/warm | 174.7667 | 178.9354 | 178.9045 | -2.313 | 0.017 | 0.063062 |
| G-10 | 12 | warm/warm | 174.7667 | 178.9261 | 179.0808 | -2.409 | -0.086 | 0.090058 |
| G-10 | 13 | warm/warm | 174.7667 | 178.9725 | 179.0217 | -2.377 | -0.027 | 0.129062 |
| G-10 | 14 | warm/warm | 174.7667 | 178.9873 | 178.9751 | -2.351 | 0.007 | 0.067254 |
| G-10 | 15 | warm/warm | 174.7667 | 178.9836 | 178.9394 | -2.332 | 0.025 | 0.116316 |
| G-10 | 16 | warm/warm | 174.7667 | 178.9704 | 179.2990 | -2.528 | -0.183 | 0.204090 |
| G-10 | 17 | warm/warm | 174.7667 | 179.0689 | 178.9410 | -2.333 | 0.071 | 0.124529 |
| G-10 | 18 | warm/warm | 174.7667 | 179.0306 | 179.1677 | -2.456 | -0.077 | 0.109883 |
| G-10 | 19 | warm/warm | 174.7667 | 179.0717 | 179.0305 | -2.382 | 0.023 | 0.065120 |
| G-10 | 20 | warm/warm | 174.7667 | 179.0593 | 179.1983 | -2.473 | -0.078 | 0.160637 |
| G-10 | 21 | warm/warm | 174.7667 | 179.1010 | 179.0612 | -2.398 | 0.022 | 0.145891 |
| G-10 | 22 | warm/warm | 174.7667 | 179.0891 | 179.1286 | -2.435 | -0.022 | 0.043063 |
| G-10 | 23 | warm/warm | 174.7667 | 179.1009 | 179.0502 | -2.392 | 0.028 | 0.221485 |
| G-10 | 24 | warm/warm | 174.7667 | 179.0857 | 179.3114 | -2.535 | -0.126 | 0.380092 |
| G-10 | 25 | warm/warm | 174.7667 | 179.1534 | 179.2734 | -2.514 | -0.067 | 0.128047 |
| G-10 | 26 | warm/cold | 174.7667 | 182.6874 | 183.2485 | -4.629 | -0.306 | 3.743537 |
| G-10 | 27 | warm/warm | 174.7667 | 179.3546 | 179.1795 | -2.463 | 0.098 | 0.140664 |
| G-10 | 28 | warm/warm | 174.7667 | 179.3020 | 179.3157 | -2.537 | -0.008 | 0.339795 |
| G-10 | 29 | warm/warm | 174.7667 | 179.3061 | 178.9136 | -2.318 | 0.219 | 0.167578 |
| G-10 | 30 | warm/warm | 174.7667 | 179.1884 | 179.0450 | -2.389 | 0.080 | 0.245032 |
| G-10 | 31 | warm/warm | 174.7667 | 179.1453 | 179.3279 | -2.543 | -0.102 | 0.294956 |
| G-10 | 32 | warm/warm | 174.7667 | 179.2001 | 178.9798 | -2.354 | 0.123 | 0.209794 |
| G-10 | 33 | warm/warm | 174.7667 | 179.1340 | 179.0345 | -2.384 | 0.056 | 0.238784 |
| G-10 | 34 | warm/warm | 174.7667 | 179.1042 | 178.7919 | -2.251 | 0.175 | 0.059743 |
| G-10 | 35 | warm/warm | 174.7667 | 179.0105 | 178.9709 | -2.349 | 0.022 | 0.241746 |
| G-10 | 36 | warm/warm | 174.7667 | 178.9986 | 178.8966 | -2.309 | 0.057 | 0.079053 |
| G-10 | 37 | warm/warm | 174.7667 | 178.9680 | 179.2492 | -2.501 | -0.157 | 0.210628 |
| G-10 | 38 | warm/warm | 174.7667 | 179.0523 | 179.2048 | -2.477 | -0.085 | 0.192147 |
| G-10 | 39 | warm/warm | 174.7667 | 179.0981 | 178.9468 | -2.336 | 0.085 | 0.121331 |
| G-10 | 40 | warm/warm | 190.3279 | 194.9954 | 194.6066 | -2.199 | 0.200 | 0.213842 |

### Finalization failure evidence

The retained curve's nominal components below sum to 10.496865 s. The existing
15% margin yields 12.071394 s versus 19.322049 s actual. Assembly, validation and
aggregation event elapsed times were 14.918976, 2.224512 and 1.020755 s. The
low-level I/O components are slower than the retained curve, and aggregation /
orchestration overhead is also underrepresented. Exact environmental cause is
not established; no disk/driver/Windows setting was changed.

| Component | Curve nominal before margin s | Observed s |
| --- | --- | --- |
| concat_seconds | 3.2898894 | 4.8334747 |
| mux_seconds | 2.6390936 | 4.821738 |
| faststart_seconds | 3.1853392 | 4.6085526 |
| checkpoint_validation_seconds | 0.075500369 | 0.3266885 |
| validation_seconds | 1.2268621 | 1.7345707 |
| aggregation_seconds | 0.080180153 | 1.020755 |

Aggregation above uses the full event, not just 0.350034 s core quality work.
The nominal byte and part ratios were 0.956393 and 0.946939, respectively.
A future fix needs independent calibration of current I/O plus aggregation /
orchestration costs (or updated long-output points). Updating/scaling these
points was explicitly prohibited this cycle. Do not multiply the built-in curve
by G-10's acceptance result and rerun the same gate.

## Checks and output contracts

| Check | Result | Evidence |
| --- | --- | --- |
| Full CPU: pytest -m "not gpu" | FAIL: 1 failed, 717 passed, 24 skipped, 101 deselected; 415.32 s | check-cpu-final.log |
| GPU: pytest -m "gpu and not soak" | PASS coverage: 101 unique cases (37 + 5 retained PASS, 59 resumed PASS); no full uninterrupted invocation | check-gpu-final.log; check-gpu-resume-1.log; check-gpu-resume-2.log; gpu-final-coverage.json |
| Ruff src/tests/gui/scripts | PASS | check-ruff-final.log |
| Ruff format --check | PASS, 165 files | check-format-final.log |
| Pyright | PASS, 0 errors/warnings | check-pyright-final.log |
| GUI lint | PASS | check-gui-lint-final.log |
| Vitest | PASS, 86 tests / 18 files | check-vitest-final.log |
| Incomplete-profile guard | PASS: expected exit 1, actual 1, profile hash unchanged | summary-guard-result.json |
| Actual GUI / Computer Use | NOT_RUN, task explicitly says none needed | No GUI claim |

CPU failure: tests/test_p1d3.py::test_driver_change_preserves_first_estimate,
line 60, expects changed.calibrated; actual is False because decode is null.
The assertion was NOT loosened. Existing skips are not counted as PASS.

The first sandbox CPU attempt was interrupted after FFmpeg was not visible.
An approved elevated intermediate run completed 716 passed / 24 skipped / 101
deselected in 430.27 s, but source changed afterward, so it is not final proof.
The 16 new estimator tests pass and are included in the final CPU suite. Initial
GUI checks also passed; final checks above include owned process ledgers.

| Output | Actual size | Actual fps | Actual frames | Actual codec | Duration s | Result |
| --- | --- | --- | --- | --- | --- | --- |
| G-1440-attempt2 | 1440x2560 | 60 | 1800 | hevc | 30.0 | PASS |
| G-Fast | 1920x1080 | 60 | 7200 | h264 | 120.0 | PASS |
| G-10 | 1080x1920 | 60 | 36000 | hevc | 600.0 | PASS |

## Errors and interrupted attempts

- Git/FFmpeg were unavailable in the sandbox; approved read-only Git and isolated
  test/measurement escalation worked. No automatic approval review was rejected.
- calibration-1 failed at a standalone executor's nonexistent queue-ID lookup.
  Removed the artificial ID, added a regression test, and real startup smoke
  completed in 33.037791 s. The failed run is excluded from the three medians.
- Initial G-1440 preparation was interrupted by the harness starting Engine after
  adding a preparing job. Startup order was fixed, only that job reran in a fresh
  attempt2 home. No partial result was used. Four transient child PIDs in its
  return ledger were all verified gone after parent exit.
- A closure type-inference error was fixed; final pyright passes.
- Output audit initially combined count_packets with read_timeline=False, which
  yields an empty packet list in that API. Correct timeline reads verified all
  actual counts; no processing job was rerun. A Windows path-key mismatch in the
  metadata audit was corrected. Prediction fields were verified unchanged.
- H264 decode and P0 benchmark diagnostics are NOT_MEASURED/SKIPPED, not PASS.

## Questions for the designer and deliberate deferrals

Default chosen: keep the frozen numeric candidate, report PARTIAL, and do not
repeat completed gates after discovering missing calibration data. The candidate
provenance explicitly says INCOMPLETE / not ready for merge.

1. Supply a generated H264 720x1280 sample through a contained VE_SAMPLES_DIR for
   complete calibration, or make the calibration backend generate it itself.
   The harness omission should have been caught before freezing the gates.
2. bench/runner.py's P0 helper copies media/cfr_map/scene_cuts but omits
   source_pts; media/decode.py requires it. A new cycle should fix and verify this
   simple benchmark metadata issue before collecting three complete runs.
3. schedule/planner.py is outside the allowed files and lacks per-part context.
   controller.unit_admission also still uses the cold default. The main loop's
   estimate uses recorded context. Authorize complete scheduling-reader
   integration in the next cycle; no scheduling policy was independently changed.
4. Decide how to remeasure or revise finalization I/O/orchestration prediction
   using independent data. This cycle kept points/samples exactly as instructed.

No completed gate was tuned/repeated. No GUI, models/manifests, presets/defaults,
GPU cap/admission policy, player, Compare implementation, packaging/CI/LGPL build
or C17 was changed. Packaging/build/GUI acceptance not requested here was NOT_RUN.
All Git mutations and draft-PR publication remain the operator's responsibility.

## Changed files

- .ai/LAST_REPORT.md
- docs/estimate-startup.md
- gui/scripts/estimate-check.py
- gui/scripts/estimate-cycle.py
- src/videoenhancer/bench/finalization.py
- src/videoenhancer/bench/runner.py
- src/videoenhancer/bench/startup.py
- src/videoenhancer/estimate/live.py
- src/videoenhancer/estimate/local.py
- src/videoenhancer/estimate/model.py
- src/videoenhancer/estimate/startup.py
- src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json
- src/videoenhancer/schedule/controller.py
- src/videoenhancer/service/downloads.py
- tests/test_p1e2.py
- tests/test_warm_estimate.py
- tests/test_warm_worker.py

## Usage-limit resumption

The initial GPU invocation was interrupted by the usage limit after 37 PASS
cases. Its root/recorded process instances are gone. The remaining fixture is
AV1 with a 3-second offset, matching case 38 rather than case 37's VP9; this
confirms execution had advanced beyond the retained cases' teardown. Current
collection contains 101 unique GPU/non-soak node IDs; source/profile hashes and
test files are unchanged, with no reorder/randomizer configured (only anyio).
The completed 37 were mapped to that deterministic prefix. The remaining 64
explicit node IDs were selected in gpu-resume-1 with verbose per-case logging
and JUnit XML. Driver remains 621.01. See gpu-interruption-audit.json.

The second usage-limit interruption stopped gpu-resume-1 after five explicit
PASSED results. Its recorded PID/creation instances were all gone. Those five
match the next deterministic collection prefix. The remaining 59 explicit IDs
ran in fresh gpu-resume-2 and completed: 59 passed, 0 failed/skipped, exit 0.
The ordered union 37 + 5 + 59 equals all 101 unique selected GPU/non-soak IDs,
with no duplicate or missing case. Source, profile and test hashes were unchanged.
See gpu-resume-1-interruption.json and gpu-final-coverage.json.

The interrupted invocations are NOT reported as completed suites. PASS describes
complete case coverage across those invocations; there was no uninterrupted
101-case invocation. No completed calibration, media gate, CPU, GUI or static
check was repeated.
## Processes

Measurement roots and sampled descendants are listed below. Check ledgers also
retain PID creation times, including 2181 sampled CPU process instances. PID
numbers may be reused; do not treat an old number as a currently owned process.
Full private process ledgers, not just this report's existence, are the evidence.

| Run | Root PID | Run state | Sampled child PIDs | Remaining |
| --- | --- | --- | --- | --- |
| baseline | 25732 | done | 25540, 29072 | [] |
| calibration-1 | 30064 | failed | 4912, 21456 | [] |
| startup-smoke | 17404 | done | 10736, 16920 | [] |
| calibration-fixed-1 | 13508 | done | 10528, 24240, 25124, 25900 | [] |
| calibration-fixed-2 | 19296 | done | 7860, 16400, 23024, 28540 | [] |
| calibration-fixed-3 | 10920 | done | 6628, 16272, 27528, 29140 | [] |
| G-1440 | 25964 | failed | none sampled | 4 transient; post-exit 0 |
| G-1440-attempt2 | 8088 | done | 7592 | [] |
| G-Fast | 15096 | done | 5896, 7324, 8348, 11996, 18364 | [] |
| G-10 | 17744 | done | 4640, 4784, 5748, 6596, 7276, 7812, 11988, 17304, 17612, 18872, 20652, 22680, 22832, 23396, 23476, 25332 | [] |

Final check root PIDs: CPU 6712, Ruff 18824, format 24496, Pyright 17028,
GUI lint 17304, Vitest 7100, rejection guard 26352. Their ledgers report no
remaining process. GPU/process closure: original root 18308 and resume-1 root 3816 were interrupted; no matching recorded PID/creation instances remained before resuming. Final resume-2 root 4292 completed with exit 0 in 5523.319047 s (pytest: 5521.76 s), 1108 sampled process instances and no remaining process.
The interrupted sandbox CPU root was 3148; its recorded children were terminated
and none remained. Initial unwrapped checks have tool exit evidence, not a full
sampled PID ledger. No owner process was terminated.

## Disk, cleanup and retention

Decimal GB are logical file lengths / drive free bytes, not allocated-space
claims. Hardlinked model bytes remain in cache when a home link is removed.
Do not sum overlapping directory rows. Start inventory was recorded before the
long calibration/gate runs; repository/runtime caches were not fully inventoried
at task start, so total project attribution has that limitation.

| Item | Start GB | End GB | Delta GB |
| --- | ---: | ---: | ---: |
| package | 0.125288579 | 0.125288579 | +0.000000000 |
| evidence/VE-P1e-3d2 | 0.000208419 | 0.028666080 | +0.028457661 |
| scratch | 0.042238391 | 0.048139467 | +0.005901076 |
| cache | 11.385460991 | 11.320157539 | -0.065303452 |
| C: free | 329.987174400 | 348.585488384 | +18.598313984 |
| D: free | 876.266160128 | 876.235108352 | -0.031051776 |

Managed-folder net growth: -0.030944715 GB. A conservative positive-only
change bound, including full current lengths of all 17 changed source/report
files rather than just their deltas, is 0.034651546 GB (<1 GB).
Evidence is 28.666 MB (<300 MB); cache is
11.320157539 GB (<40 GB). No installation or model download was performed.
These are managed-folder measurements, not a complete allocation audit of repo
runtime caches or Windows-managed files. Cache shrink and drive free-space
changes are observations, not bytes claimed as removed by this cleanup.
The evidence inventory precedes the final small JSON/report writes by seconds.


### Measured cleanup candidates (before deletion)

| Work-relative path | Logical bytes | Hardlinked bytes | Files |
| --- | ---: | ---: | ---: |
| scratch/home | 0 | 0 | 0 |
| scratch/p1e3d2 | 6844834257 | 3082373090 | 1777 |
| scratch/p1e3d2-cpu | 181 | 0 | 2 |
| scratch/p1e3d2-cpu-elevated | 0 | 0 | 0 |
| scratch/p1e3d2-curve-final | 0 | 0 | 0 |
| scratch/p1e3d2-focused-final | 0 | 0 | 0 |
| scratch/p1e3d2-focused2 | 0 | 0 | 0 |
| scratch/p1e3d2-focused3 | 0 | 0 | 0 |
| scratch/p1e3d2-profile-tests | 0 | 0 | 0 |
| scratch/p1e3d2-ready-tests | 0 | 0 | 0 |
| scratch/p1e3d2-startup-fix | 0 | 0 | 0 |
| scratch/p1e3d2-warm-tests | 0 | 0 | 0 |
| scratch/p1e3d2-worker-tests | 0 | 0 | 0 |
| evidence/VE-P1e-3c2-F2 | 6095246 | 0 | 121 |

| Work-relative path | Removed logical bytes | Residual bytes | Result |
| --- | ---: | ---: | --- |
| scratch/home | 0 | 0 | REMOVED |
| scratch/p1e3d2 | 6844834257 | 0 | REMOVED |
| scratch/p1e3d2-cpu | 181 | 0 | REMOVED |
| scratch/p1e3d2-cpu-elevated | 0 | 0 | REMOVED |
| scratch/p1e3d2-curve-final | 0 | 0 | REMOVED |
| scratch/p1e3d2-focused-final | 0 | 0 | REMOVED |
| scratch/p1e3d2-focused2 | 0 | 0 | REMOVED |
| scratch/p1e3d2-focused3 | 0 | 0 | REMOVED |
| scratch/p1e3d2-profile-tests | 0 | 0 | REMOVED |
| scratch/p1e3d2-ready-tests | 0 | 0 | REMOVED |
| scratch/p1e3d2-startup-fix | 0 | 0 | REMOVED |
| scratch/p1e3d2-warm-tests | 0 | 0 | REMOVED |
| scratch/p1e3d2-worker-tests | 0 | 0 | REMOVED |
| evidence/VE-P1e-3c2-F2 | 6095246 | 0 | REMOVED |

Cleanup ran once per path inside the default sandbox after containment checks.
No deletion was refused; no elevation, ACL change or retry workaround was used.
For the owner to delete: none from this cycle. Model hardlinks were unlinked;
the shared cache was preserved. Older F2 development evidence was removed;
F3, d1 and d2 are the three retained development cycles. Owner-check evidence
was preserved.

Scratch is not globally empty: pre-existing/shared owner-check (42,232,471
bytes), p1e3c2-native (0), tmp (5,895,136) and videoenhancer.jsonl (11,860)
remain. The shared tmp contains node-compile-cache and torchinductor_pro; its
starting entries were not inventoried, so ownership of every byte is unknown.
Focused tests appended to the shared development log. These paths were not
purged to avoid deleting pre-existing work; all named cycle-owned scratch
paths above are gone. Remaining shared scratch is disclosed rather than claimed
as cleaned. No owner app/data path or Recycle Bin was accessed.

Final read-only Git verification: same branch and HEAD as start, 17 allowed
source/report files changed, git diff --check exit 0, no media/cache artifacts
in the change list. No Git mutation was performed. Source hashes still match
the gate freeze; only profile provenance differs as documented.


## Owner summary

cold/warm推定とfinalization曲線の保持を実装しました。
GPU対象101件は中断前の完了分と再開分を合わせてPASS、lint・型検査・VitestもPASSです。
decode未測定、CPUテスト1件FAIL、G-10 finalization誤差-37.53%のため、判定はPARTIALです。
今回のscratchは削除済みです。既存の共有scratchは保持し、残量を記録しました。
候補はmerge不可です。次の修正方針はClaudeの判断が必要です。commit・pushは行っていません。
