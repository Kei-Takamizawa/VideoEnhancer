# VE-P1a-6 — Engine hardening report

Task ID: VE-P1a-6. Status: BLOCKED.
Branch: `p1-restoration-gui`. PR #2 remains a draft. No main push or merge.
Windows and Ubuntu CI passed for controller commit `1c00c8783ad4c4a1ba38228d555f397d4310af81` (run 37738629274).

## Implementation and acceptance

| Criterion | Result | Evidence |
|---|---|---|
| A1 | PASS | JSON model registry; BasicVSR++, RIFE and Spandrel adapters; CLI selection and model management; unchanged built-in short-clip output |
| A2 | PASS | Re-registered C1 is bit-identical; schema/hash/adapter/task rejection; model snapshots and changed-model resume refusal |
| A3 | PASS | `docs/ADDING_MODELS.md`: fine-tuning checkpoints, Spandrel, adapters, licences and C1 comparison |
| A4 | PASS | All five samples × both presets: zero final and independently scanned encoded flags across 10,820 output frames; detector regressions pass |
| A5 | PASS | Default 15/2: Torch/PDH <5 decimal GB on sample-04/05; speed improves 2.6%/0.05% against 21/3 |
| A6 | PASS | Five Standard seams 1.003–1.038; nine-case sweep below; CPU/GPU trial produces all four artifacts |
| A7 | FAIL | Real completed accuracy runs, stability, scheduled pauses, P0 resume and SAC mock; detailed results below |
| A8 | PASS | Ruff, format, Pyright, CPU/GPU suites, wheel and Windows/Ubuntu CI pass; private source-name/media/weight diff scan passes |

### Task A

Manifests describe identity, version, architecture parameters, task, licence,
commercial permission, precision, temporal preferences, scale and verified weights.
Built-ins download and verify SHA-256. Model folders contain data, never executable
adapter code. Architecture code is registered in the repository and cached in a
separate verified adapter-source directory. Restricted weight loaders are used.
Presets and overrides use model IDs. Jobs record model versions, weight hashes and
manifest hashes and refuse changed models on resume or between segments.

C1 SHA-256: `6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a`.
RIFE SHA-256: `6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2`.

### Task B

Scene-cut comparisons use the same source side, including inserted frames.
Repairs follow the owner decision: inserted frames use the 50/50 adjacent-output
blend; restored frames use the corresponding source through the preset resize path.
Repaired frames are checked again. Overlap context is repaired before interpolation;
raw unique flags and final owned-frame flags are recorded separately.

Sample-05 raw/final counts: Fast 1/0, Standard 2/0; all other sample runs 0/0.
Unrepaired PNGs at 26.276 seconds and neighbours were inspected outside Git.
No white/mosaic corruption or implementation padding/crop error was established.
Replicate-32, constant-32 and upstream constant-128 padding produced bottom-band
luma deviations 0.10091, 0.09998 and 0.10032 versus a blend. Padding was unchanged.
The discrepancy also extends beyond the bottom band; unknown true intermediate
content prevents claiming the blend is ground truth.
Tensor-lifetime regression verifies bounded clip ownership and release.
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
## Task C: trial and quality

Job reports include Y PSNR/SSIM, flicker, clip/segment seams, cut exclusions and
output/source relative ratios at every joint. Source cuts within ±1 frame are
excluded from pass/fail; jobs without eligible joints report N/A.
Separate sample-05 segment boundaries at 300/600 frames gave segment seam 1.066986.
Real CLI trials on CPU and GPU produced 3 original, 6 enhanced and 6 comparison
frames plus report.json. CPU/GPU speeds including initialization were 0.165/0.655
input fps on the small test. Labels and the thin divider were inspected.

## Task D: calibration and long runs

| Model | Calibration work | Median seconds | Throughput | Seconds/pixel/work item |
|---|---|---:|---:|---:|
| basicvsrpp-ntire21-decompress | 15 frames, 720×1280 | 3.718132 | 4.034 frames/s | 2.689621e-7 |
| rife-4.25 | 8 pairs, 1080×1920 | 0.385726 | 20.740 pairs/s | 2.325217e-8 |

Warm-up, inference mode and synchronization precede three measured samples.
Profiles bind model/version/hash/parameters/backend/device; the estimator rejects
stale profiles and accounts for geometry, overlap and actual interpolation pairs.

| Completed case | Initial estimate s | Estimate at 10% s | Actual active wall s | Initial error | 10% error | Accuracy |
|---|---:|---:|---:|---:|---:|---|
| standard-accuracy-final | 11367.293 | 11572.704 | 12755.272 | -10.88% | -9.27% | PASS |
| fast-soak-fixed | 13600.021 | 13964.986 | 17658.881 | -22.98% | -20.92% | FAIL |

Actual values are completed wall time excluding observed pauses, including final assembly and validation; no projection substitutes for an actual total.

| Run | State / mode | Input frames completed | Output frames verified | Active seconds | Input fps | Raw/final flags | Pause / stop-resume |
|---|---|---:|---:|---:|---:|---:|---|
| standard-accuracy-final | done / complete | 26980/26980 | 53960 | 12755.272 | 2.352 | 10/0 | [] / False |
| standard-stability-retry | paused / stability | 7202/215837 | N/A | 3607.268 | 2.334 | 2/0 | [True] / True |
| fast-soak-fixed | done / complete | 215784/215784 | 431568 | 17658.881 | 15.761 | 0/0 | [True, True] / False |

| Run | Dedicated growth MB | Reserved growth MB | Engine RSS growth MB | Tree RSS growth MB |
|---|---:|---:|---:|---:|
| standard-accuracy-final | -222.298 | -1010.827 | 3.801 | -45.961 |
| standard-stability-retry | 255.857 | -413.139 | -39.035 | -20.554 |
| fast-soak-fixed | 50.332 | 50.332 | 1.569 | 29.196 |

Growth compares first/last five-minute windows after minute 10. Fast limits are
150 MB dedicated, 100 MB reserved, 200 MB RSS. Standard records trends; these Fast
growth limits are not applied to Standard. Dedicated memory is sampled (1 second
for sample memory trials, approximately 60 seconds for long runs); Torch peaks
are allocator max-reserved measurements. Output audio and exact frame counts are
validated by the controller. The Standard two-hour stability job intentionally
remains paused after more than 60 active minutes, including one scheduled pause
and an actual stop/restart; completion is not required by its specification.

SAC simulated blocked PyNvVideoCodec import reports the specific message in probe
and enhance: PASS. An isolated copy of the original P0 schema-1 job with no model
snapshot resumed and regenerated 1,139 source / 2,278 output frames: PASS. The
original P0 job was preserved.

### Corrected failures and retained evidence

- The first Standard fixture had a 21.333 ms video/audio origin discrepancy from
  concat without `-copyts`; final mux validation failed. Rebuilt zero-origin inputs
  with `-copyts`, preserved AAC priming and verified a real assembly smoke test.
  The fresh completed Standard accuracy result above replaces that failed fixture.
- Initial calibration lacked inference mode; corrected and recalibrated. Old
  invalid calibration is retained externally and was not used for acceptance.
- The first Fast render finished, but quality control read a 7.4 MB job manifest
  on every FFmpeg metadata line. This was an implementation accessor error:
  40.797 ms/read versus 0.129 ms for existing lightweight control-state access.
  Replaced the accessor and added a regression covering pause detection without
  full manifest reload. Its output was resumed and validated separately; the fresh
  Fast run above is the acceptance timing, not a mixed interrupted-run total.
- A temporary controller-test fixture modified control generation and requeued
  itself; fixed the fixture and reran the controller and full suites.

## Validation, expected and actual

Expected: registry safety/reproducibility, zero final flags, bounded memory,
seams ≤1.3, completed-run estimate errors within ±30% initial / ±15% at 10%,
pause/restart stability, clean local checks and Windows/Ubuntu CI.

Actual local final checks after the control accessor correction:

| Check | Result |
|---|---|
| Ruff | PASS |
| Ruff format --check | PASS, 74 files |
| Pyright | PASS, zero errors/warnings/information |
| CPU suite | PASS, 170 passed / 3 skipped / 18 GPU deselected, 75.52 seconds |
| GPU suite | PASS, 18 passed / 173 deselected, 45.06 seconds |
| Controller focused suite | PASS, 14 passed / 1 skipped |
| Wheel build | PASS, 52 entries; built-in manifests included; no weights/media |
| Final Windows/Ubuntu CI | PASS, both jobs in https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/37738629274 |

## New CLI commands and reproduction

```powershell
ve models list
ve models add C:\MyModels\finetune
ve models remove my-basicvsr-finetune
ve enhance input.mp4 -o enhanced.mp4 --restore-model basicvsrpp-ntire21-decompress --interp-model rife-4.25
ve trial input.mp4 --seconds 5 --preset standard --restore-model basicvsrpp-ntire21-decompress --out C:\Evaluation\trial
ve trial trial-input.mp4 --start 0 --seconds 0.1 --preset standard --backend cpu --short-side keep --out C:\Evaluation\cpu-trial
ve bench --calibrate --output-dir C:\Evaluation\calibration
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\pyright.exe
.venv\Scripts\python.exe -m pytest -m "not gpu"
.venv\Scripts\python.exe -m pytest -m gpu
```

Use a fresh VE_HOME for each soak, installing models, adapter sources and the
verified calibration profile; do not reuse existing completed-job directories:

```powershell
python scripts/soak.py --input standard-15min-zero-origin.mp4 --output standard.mp4 --preset standard --mode complete --scheduled-pauses 0
python scripts/soak.py --input standard-2h-zero-origin.mp4 --output stability.mp4 --preset standard --mode stability --scheduled-pauses 1
python scripts/soak.py --input fast-synthetic-2h.mp4 --output fast.mp4 --preset fast --mode complete --scheduled-pauses 2
```

All videos, weights, raw-frame PNGs and detailed JSON/logs are outside the repository:
`C:\Users\pro\Documents\VideoEnhancer-P1a-6`.
Key folders: checked-samples, segment-joints, trial-cpu-real, trial-gpu-real,
calibration-inference, p0-resume, standard-accuracy-final, standard-stability-retry,
fast-soak-fixed. Each long-run home/reports holds soak_report.json and soak.log.
Exact fixture recipe is preserved in prepare_D_retry.py; long-run orchestration
in run_D_final.py / finish_fast_fixed.py; sample validation in final_B.py and
continue_C.py. Original failed/interrupted reports remain in separate folders.

## Limitations and intentionally unrun scope

PSNR/SSIM against compressed input measure fidelity, not restoration gain against
unavailable pre-compression ground truth. Exact VFR quality-reference alignment
has not been validated. No proof of a padding implementation defect was found.
30-frame seam measurements were intentionally NOT RUN after the memory cap,
as explicitly required. GUI/API, training, face processing and new benchmark
candidates were NOT RUN (out of scope). No subagents were used.

## Blocking decision for Claude

Fast completed in 17,658.881 active seconds (4 h 54 min 19 s). Initial prediction
13,600.021 seconds is -22.985% (PASS at ±30%); the 10% prediction 13,964.986
seconds is -20.918% (FAIL at ±15%). Standard completed accuracy passes both targets.
Fast memory growth is 50.332 MB dedicated, 50.332 MB reserved, 1.569 MB engine RSS
and 29.196 MB controller-tree RSS; all Fast growth limits pass. The two scheduled
pauses were observed, exact 431,568 output frames were decoded, audio retained,
and raw/final detector counts are 0/0.

| Long run | Torch reserved peak GB | Sampled PDH peak GB |
|---|---:|---:|
| Standard completed accuracy | 4.718592 | 4.531409 |
| Standard stability | 4.395631 | 4.353151 |
| Fast fresh completed soak | 1.589641 | 1.823961 |

Cause: `src/videoenhancer/estimate/model.py:212` sums pending segment predictions;
it does not predict final assembly/validation/quality work. That work runs after
all segments in `src/videoenhancer/schedule/controller.py:548` and includes full
PSNR/SSIM and difference passes in `src/videoenhancer/pipeline/quality.py`.
The full-manifest polling bug was corrected and regression-tested; the fresh run
still misses the acceptance target. Do not alter the actual-total reference or
the ±15% threshold to make this pass.

Decision requested: specify how to calibrate and incorporate finalization into
initial and remaining-time estimates (including geometry/backend dependence and
progress reporting). A separate measured finalization coefficient/stage would
address the missing work, but has not been implemented without design approval.
Reproduce with the fresh-home Fast soak command above and compare the report's
prediction_at_ten_percent with actual_wall_excluding_pauses_seconds. Exact report:
`C:\Users\pro\Documents\VideoEnhancer-P1a-6\fast-soak-fixed\home\reports\soak_report.json`.
No more product changes or acceptance reruns were made after this design blocker.

## Changed files

- `.ai/CURRENT_TASK.md`
- `.ai/LAST_REPORT.md`
- `README.md`
- `docs/ADDING_MODELS.md`
- `docs/ARCHITECTURE.md`
- `docs/BENCHMARK_DEGRADED.md`
- `docs/DEVELOPMENT.md`
- `scripts/soak.py`
- `src/videoenhancer/bench/basicvsr.py`
- `src/videoenhancer/bench/calibration.py`
- `src/videoenhancer/bench/rife.py`
- `src/videoenhancer/bench/runner.py`
- `src/videoenhancer/cli.py`
- `src/videoenhancer/estimate/model.py`
- `src/videoenhancer/jobs/store.py`
- `src/videoenhancer/media/mux.py`
- `src/videoenhancer/models/basicvsr.py`
- `src/videoenhancer/models/manifests/basicvsrpp-ntire21-decompress.json`
- `src/videoenhancer/models/manifests/rife-4.25.json`
- `src/videoenhancer/models/registry.py`
- `src/videoenhancer/models/rife.py`
- `src/videoenhancer/models/sources.py`
- `src/videoenhancer/models/spandrel.py`
- `src/videoenhancer/pipeline/clips.py`
- `src/videoenhancer/pipeline/outliers.py`
- `src/videoenhancer/pipeline/presets.py`
- `src/videoenhancer/pipeline/quality.py`
- `src/videoenhancer/pipeline/runner.py`
- `src/videoenhancer/pipeline/stages.py`
- `src/videoenhancer/schedule/controller.py`
- `src/videoenhancer/trial.py`
- `tests/test_cli.py`
- `tests/test_controller.py`
- `tests/test_estimate.py`
- `tests/test_jobs.py`
- `tests/test_model_registry.py`
- `tests/test_p1a_pipeline.py`
- `tests/test_quality_trial.py`
- `tests/test_soak.py`

## Git record

Checkpoint commit: 7be0cc372bbf3015020c90e7054bad341e16e452.
Controller correction and completed evidence: 1c00c8783ad4c4a1ba38228d555f397d4310af81.
Both were pushed to origin/p1-restoration-gui and remote SHA verified.
PR #2 remains OPEN and draft. No main push, merge or history rewrite.
The final report-only commit records the CI outcome; its identifier is available in Git history.

