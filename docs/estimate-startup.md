# Worker startup estimates

Profiles may provide `startup_by_preset` with `cold` and `warm` seconds for each
preset. A legacy scalar remains valid and supplies both terms. Standalone
predictions, including model qualification, default to a fresh worker.

`estimate.startup.cold_parts` assigns the initial cold parts at zero-based
positions 0, 50, 100, and so on. The controller records the actual startup kind
in each successful part's statistics and the available worker's successful-part
count in `timing.worker_parts`. Replacements, waits and shutdown reset that count;
remaining estimates start a new 50-part lifetime from that boundary. This records
the existing worker policy without changing processing or scheduling policy.

Local learning uses separate last-20 medians by preset and startup kind. Spilled
jobs remain excluded. Revision `p1e3d2-warm1` separates the new engine's timing
observations from earlier revisions; no migration of existing observations runs.

Calibration measures startup through a real reusable ProcessExecutor with three
15-frame parts per preset at 720x1280 input and 1080x1920 output, 30 to 60 fps.
Part one supplies cold startup; the remaining two supply the warm median.

Measured long-output finalization curves remain unchanged during calibration.
The small-clip measurement is retained as `finalization.tiny_clip_fit`, and its
linear coefficients are used only when there is no measured curve. No disk-speed
scaling is applied.

The planner and next-unit admission reader use the same `cold_parts` assignment
as `estimate_job`; neither adds a cold startup to every remaining part.

Decode calibration accepts `VE_SAMPLES_DIR` as an optional NVDEC sample override.
For either missing codec/size, it generates a temporary synthetic portrait clip:
H.264 at 720x1280 or HEVC at 1080x1920. These clips are decoded and removed within
the calibration's temporary-directory lifetime. The FFmpeg fallback also uses
portrait dimensions. The P0 diagnostic carries analyzed source timestamps and
keyframes to the real segment worker.

`gui/scripts/estimate-complete-cycle.py` records isolated runs for P1e-3d2b.
Before a gate or independent finalization replay it reads all three calibration
reports and the built-in profile, rejecting skipped sections and null stage
coefficients. Gates also require the independent four-point finalization curve.
The replay renders genuine Standard C1 parts for every distinct planned length,
then tiles their encoded bytes and shifted inline-quality partials into distinct
files using the production planner's boundaries. Each repetition starts with new
part files and no assembly checkpoint. It measures real assembly, exact packet
validation, quality aggregation, and the timer's durable manifest operations.
An actual part worker is primed and remains resident during every measurement,
matching the model residency and memory pressure at the end of a real job.
The measurement records and verifies that worker's PID, creation time and RSS.
It records available memory and machine-wide disk counters rather than assuming
that repeated files reproduce the cache state of a job that ran for hours.

The P1e-3d2b curve uses three repetitions at each of 1, 10, 30 and 120 minutes.
It keeps the existing prediction shape: interpolate step times by frame count,
scale concat/mux/faststart by output bytes, and checkpoint/aggregation by part
count. The existing 15% margin is unchanged. Aggregation points contain the
complete timed event, including durable manifest operations; the core
`aggregate_quality` function is recorded separately for diagnosis. Gate jobs and
their files never supply fit points or scaling factors.
