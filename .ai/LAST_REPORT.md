# VideoEnhancer Cycle P1a-6 Report

- **Task ID / Cycle:** VE-P1a-6
- **Status:** PARTIAL (paused at the owner's request; long-run acceptance remains incomplete)
- **Branch:** `p1-restoration-gui`; PR #2 remains a draft.
- **Validation date:** 2026-10-07 UTC.

## Implementation so far

Task A implements JSON manifests, verified model installation, built-in C1/RIFE,
repository adapters for BasicVSR++, RIFE and Spandrel, preset/CLI selection,
and model identity checks at job creation, resume and every segment.
Architecture sources are pinned and verified separately from model data folders;
model folders never supply executable code. Restricted Torch deserialization is
used by all adapters. Fine-tuned BasicVSR++ wrapped and bare state dictionaries
are accepted with strict parameter matching. `docs/ADDING_MODELS.md` documents
installation, licensing, new adapters and the existing degraded comparison tools.

Task B adds same-scene detector neighbors and fixes retained prior-clip tensor
references. The owner's revised repair policy replaces persistent restored
frames with the same decoded source through the preset resize stage and persistent
inserted frames with an exact 50/50 blend of source-aligned output endpoints.
Repairs are checked again; raw and final flags are recorded separately. Raw counts
include unique flagged compute-context indices inside the segment; final counts
include only owned output frames. Compute-context defects are repaired before
those frames can contaminate owned interpolation. A regression failed before
this fix and passes afterwards.
The flagged sample-05 source pair at 26.276 s was saved unrepaired before these
repairs, and padding/crop conditions were tested on the same pair. No padding/crop
implementation bug was demonstrated. Actual padding is bottom 0/right 8 px.
The bottom-band luma deviation from the endpoint blend remains 0.1009 with current
padding, 0.1000 with zero padding to 32, and 0.1003 with upstream helper padding to
128. Difference is concentrated around fast-moving hands but not strictly confined
to the bottom band. Intermediate ground-truth exposure is unavailable.
Private PNG evidence remains external and is not committed.

Task C implementation supplies per-job encoded Y fidelity, flicker, clip/segment
seams, source-cut exclusions, excluded counts and every joint's relative diagnostic.
No eligible joint yields N/A. `ve trial` supplies the required four output files,
source context, selected model identities and projected whole-file time.
Task B full sample measurements and the encoded scan are complete: all ten
runs have zero final flags and exact 2x counts (10,820 total encoded frames).
All five Standard seam values lie between 1.003 and 1.038. C1 default is now
15/2 after the memory/speed and all-five guards passed. Task C
segment-joint and nine-combination validation are complete. Task D is paused at the owner's request.
The latest Task D instruction adds a separate completed 15-minute Standard
accuracy job; its two-hour Standard input is a >=60-minute stability test.
Estimate accuracy must use actual completed wall time excluding pauses.

## Checks completed so far

- Ruff / format / Pyright: PASS on the current files (0 type errors/warnings).
- CPU suite before the compute-context repair regression fix: 156 PASS, 3 SKIP,
  18 GPU deselected. Current focused context/detector tests: 52 PASS, 4 GPU
  deselected; redirected adapter source path test: 1 PASS. Full suites must be
  re-run after final implementation.
- GPU suite before the compute-context repair regression fix: 18 PASS,
  159 CPU deselected; final-version full GPU suite is pending.
- GPU C1: exact tensor equality between legacy loader, built-in registry ID,
  re-registered checkpoint copy and bare state-dictionary checkpoint.
- GPU RIFE: exact tensor equality between legacy and registry loader.
- Repair tests: exact endpoint blend and exact same-source resize pixels; raw
  and final counts; scene-cut, synthetic flash, edge flash, chroma and endpoints.
- Real C1/RIFE CPU trial: PASS, 3 original / 6 enhanced / 6 comparison frames,
  256x256, labeled split inspected; 0.165 input fps, zero detector flags.
- Real GPU C1/RIFE CLI trial: PASS, 3 original / 6 enhanced / 6 split frames,
  selected restoration override used, 0.655 input fps including initialization.
  All four required files were written; trial seam is N/A (no non-cut joint).
- Wheel build: PASS before the latest repair/report changes; 51 entries, both
  built-in manifests included, no weights or videos.
- CI at the final commit: NOT RUN yet.

## Evidence and reproduction

External evidence root: `%USERPROFILE%/Documents/VideoEnhancer-P1a-6`.
Unrepaired PNGs: `unrepaired-c15-o2-window-785-800/frame-1574.png`,
`frame-1575.png`, `frame-1576.png`; padding alternatives and numeric JSONs are
in the same external root. No private video names or frames are in tracked files.

Commands added:

```powershell
ve models list
ve models add C:\MyModels\finetune
ve models remove my-basicvsr-finetune
ve enhance input.mp4 -o enhanced.mp4 --restore-model basicvsrpp-ntire21-decompress --interp-model rife-4.25
ve trial input.mp4 --seconds 5 --preset standard --out C:\Evaluation\trial
```

Full measurement tables, A1-A8 results, calibration, soak, unresolved issues,
exact reproduction and final Git/CI results will replace this interim section.
GUI, local API, training, face processing and additional benchmark candidates are
intentionally out of scope. No subagents were used.

## Current-version memory results (fresh process per full sample)

GB means decimal 1,000,000,000 bytes; PDH is sampled process-dedicated peak.
All six cases ran after the compute-context regression fix.

| Sample | Clip/overlap | Input fps | Torch reserved GB | PDH GB | Raw/final flags | Seam |
|---|---:|---:|---:|---:|---:|---:|
| sample-04 | 15/2 | 2.375 | 4.419 | 4.678 | 0/0 | 1.032 |
| sample-04 | 15/3 | 1.961 | 4.352 | 4.611 | 0/0 | 1.040 |
| sample-04 | 21/3 | 2.314 | 5.727 | 5.987 | 0/0 | 1.039 |
| sample-05 | 15/2 | 2.395 | 4.435 | 4.695 | 2/0 | 1.003 |
| sample-05 | 15/3 | 2.040 | 4.631 | 4.884 | 2/0 | 1.004 |
| sample-05 | 21/3 | 2.394 | 5.492 | 5.752 | 2/0 | 0.966 |

15/2 passes the 5 GB cap and speed criteria on both clips, and all-five
Standard seams and all-ten encoded detector scans pass. The built-in manifest
and the local development installation now use 15/2.

## Subsequent regression checks

Current-version CPU full suite with 15/2 and the source-path safety check:
158 PASS, 3 SKIP, 18 GPU deselected. A later expanded model-override check
found 3 failures: resize, p0-test and passthrough recorded but did not invoke
an explicitly selected restore adapter. The preset dispatch was corrected;
final full-suite checks are still pending after Task D.

The model-override regression re-check passes on all 5 presets. The separate
three-segment sample-05 run (non-cut joints at source frames 300 and 600) gives
segment seam 1.066986, clip seam 1.000968 and combined seam 1.002706;
9 source-cut joints are excluded and all 85 joint diagnostics are retained.

## Task D interim checkpoint

- Corrected model calibration: PASS. C1 15/2, 720x1280, 15 computed frames:
  median 3.718132 s (4.034 frames/s), coefficient 2.689621e-7 s/pixel/frame.
  RIFE, 1080x1920, eight computed pairs: median 0.385726 s
  (20.740 pairs/s), coefficient 2.325217e-8 s/pixel/pair.
- Calibration initially omitted inference mode for RIFE. This implementation
  error inflated its memory and timing; corrected results use inference mode,
  matching the pipeline. A regression asserts inference mode is active.
  Initial invalid calibration is retained externally and not used.
- SAC blocked-import mocks: PASS in probe and enhance in the final CPU suite.
- Actual historical P0 job compatibility: PASS on an isolated copy of the
  2026-10-06 job without model fields; first resumed segment 1,139 source / 2,278
  encoded output frames, 24.124 s. Original job and source unchanged.
- Final local checks: Ruff PASS; format PASS (74 files); Pyright PASS (0 errors,
  warnings or information); CPU suite 168 PASS, 3 SKIP, 18 GPU deselected;
  GPU suite 18 PASS, 171 deselected. Wheel PASS, 52 entries, both manifests and
  calibration present, C1 defaults 15/2, no media or weights.
- A first GPU suite invocation encountered inaccessible pre-existing Windows
  pytest temporary directories (15 fixture errors, 3 PASS). A fresh workspace
  basetemp resolved the environment issue; the complete rerun passed.
- Long experiments: RUNNING, not PASS. Standard accuracy job uses the completed
  total as its reference. Its 15-minute input has 26,973 decoded input frames,
  CFR-normalized to 26,980 frames because of concatenated timestamps. Initial
  calibrated prediction: 11,367.293 s. Standard stability and Fast completion
  are queued sequentially by the validation supervisor, on one GPU.
- External inputs and per-job homes: C:/Users/pro/Documents/VideoEnhancer-P1a-6/.
  Long-run progress and reports are under each home/reports directory.
- Memory comparison helper fixed epoch/performance-clock mixing and compares
  separated five-minute window peaks after minute 10. Targeted regression PASS.
- CI, final commit and push: NOT RUN until the required long experiments finish.

## Completed nine-combination sweep

All six 15/21-frame rows processed the full 911-source-frame sample-05.
30-frame rows are initial 30-owned-frame memory probes only; their timings
are not full-run throughput. Their seams were NOT RUN as instructed after
the 5 GB cap was exceeded. PDH is sampled; Torch is max reserved.

| Clip/overlap | Seconds/owned frame | Torch GB | PDH GB | Seam |
|---|---:|---:|---:|---:|
| 15/2 | 0.417493 | 4.435476 | 4.694991 | 1.003345 |
| 15/3 | 0.490150 | 4.630512 | 4.883735 | 1.003634 |
| 15/4 | 0.618154 | 4.808770 | 5.068284 | 0.990968 |
| 21/2 | 0.386566 | 5.467275 | 5.726798 | 0.929599 |
| 21/3 | 0.417720 | 5.492441 | 5.751964 | 0.966403 |
| 21/4 | 0.481434 | 5.305795 | 5.565317 | 0.952541 |
| 30/2 | 0.445880 | 5.096079 | 5.309133 | NOT RUN (memory cap) |
| 30/3 | 0.444829 | 5.096079 | 5.309137 | NOT RUN (memory cap) |
| 30/4 | 0.444654 | 5.096079 | 5.309137 | NOT RUN (memory cap) |

## Five-sample Standard metrics at final 15/2 defaults

Encoded Y fidelity is against the compressed source, not pre-compression
ground truth or an objective restoration-gain measurement. Flicker includes
inserted output frames. Every joint diagnostic remains in external JSON.

| Sample | PSNR Y dB | SSIM Y | Flicker | Seam | Excluded / all joints |
|---|---:|---:|---:|---:|---:|
| sample-01 | 40.865733 | 0.98175774 | 0.544791 | 1.009609 | 0 / 47 |
| sample-02 | 43.642853 | 0.98523623 | 0.525946 | 1.037914 | 0 / 29 |
| sample-03 | 44.836293 | 0.98827716 | 0.550161 | 1.012716 | 0 / 33 |
| sample-04 | 38.764278 | 0.98230918 | 0.539597 | 1.032429 | 0 / 50 |
| sample-05 | 42.144874 | 0.98287651 | 0.550588 | 1.003345 | 9 / 85 |

Fast single-segment samples have no eligible joints; their seam is N/A,
not PASS. Separate Standard non-cut segment-joint validation at 300 and
600 source frames passed, segment ratio 1.066986.

## Failed first Standard accuracy attempt and fixture correction

The first attempt processed all 26,980 CFR frames (20 raw / 0 final flags),
2.350415 engine input fps, but final assembly FAILED at 11,636.343 s because
source audio offset was -0.021333 s while the muxed offset was 0. It is not a
completed accuracy run and neither estimate accuracy nor completion is PASS.
The validation concat command omitted `-copyts`: FFmpeg normalized AAC's first
priming packet and shifted video presentation to +0.021333 s. The source
parts themselves have zero video/audio presentation origin. `-copyts`, without
`-start_at_zero`, preserves that zero origin and 1,024-sample AAC priming.
No product audio tolerance or mux policy was changed. The failed input, job,
all rendered segments and logs remain external for inspection.

Separate corrected 15-minute and two-hour inputs retain exact decoded counts
26,973 and 215,784. Their video origin and relative audio offset are both zero.
A corrected 60-frame input completed the actual CPU p0-test CLI pipeline and
final assembly successfully before restarting the long experiments.
The original Standard stability preparation was interrupted before creating
its job; Fast had not started. New Standard homes are named
standard-accuracy-retry and standard-stability-retry. The Fast home is unchanged.

A supervisor sampling race was corrected: process construction now occurs
inside the NoSuchProcess guard. Both soak helper regression tests PASS.
Core GPU implementation is unchanged; final CPU checks will include this test.


## Owner-requested pause checkpoint (2026-10-07)

The owner requested: stop now and continue tomorrow. No additional validation
or improvement is being started. The long-run driver and its supervisors were
stopped; the actual queue received the official `pause` command first. Its
running second segment was aborted and returned to pending, while the verified
first segment remains done. No model, input or completed segment was deleted.

- Retry job: `fec4d764981b4df9ab0491303cf373ed`, state **paused**.
- Completed: **1 / 60 segments, 531 / 26,980 CFR source frames (1.97%)**.
- Standard 15-minute completion/estimate accuracy: **NOT RUN to completion**.
- Standard two-hour stability retry: **NOT RUN**.
- Fast two-hour soak: **NOT RUN**.
- Local full checks last run: Ruff PASS, format PASS (74 files), Pyright PASS
  (0 errors/warnings); CPU 168 PASS / 3 SKIP / 18 GPU deselected;
  GPU 18 PASS / 171 deselected. The subsequent supervisor race regression
  passed its two focused tests; the full CPU suite after that change is NOT RUN.
- Wheel build: PASS, 52 entries; final CI for this checkpoint: NOT RUN.
- GUI: NOT RUN, outside this cycle's scope.

External checkpoint:
`C:/Users/pro/Documents/VideoEnhancer-P1a-6/user-pause-checkpoint.json`.
Logs, inputs, models and previous measurements remain under that external root.
Corrected fixture and retry driver reproduction scripts were saved under its
`reproduction` folder. This pause is intentional, not a completed acceptance
run or a new design blocker.

### Continuation instructions

1. Verify Git state and this report before starting; preserve all external
   evidence. Do not rerun the already-completed Task A-C GPU measurements.
2. For processing-only continuation, set `VE_HOME` to the external
   `standard-accuracy-retry/home`, run `ve resume` with the job ID above, then
   `ve run --ignore-schedule`. Completed segments are reusable.
3. For acceptance accuracy, use a fresh isolated home and a fresh supervised
   Standard 15-minute experiment using `standard-15min-zero-origin.mp4` and
   the saved calibrated model coefficients. The interrupted supervisor's
   wall-clock measurement cannot be used as a completed total. Do not simply
   rerun `scripts/soak.py` against the existing home: it requires a fresh home.
4. Complete Standard stability and Fast soak sequentially, including prescribed
   pauses and stop/resume. Compare estimates against real completed totals;
   record memory, detector counts and exact frame/audio validation.
5. Run final checks, replace this interim report with final acceptance results,
   commit and push on `p1-restoration-gui`; keep PR #2 draft and never merge.

Git checkpoint commit/push result is supplied in the chat; if either operation
fails, record the exact failure here and stop. No final acceptance or CI success
is claimed by this checkpoint.
