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
