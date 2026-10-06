# VideoEnhancer Cycle P1a-2 Report

- Task ID / Cycle: VE-P1a-2
- Status: PARTIAL
- Date: 2026-10-07
- Branch: `p1-restoration-gui`

## Summary by requirement

- **R1 — PARTIAL.** Re-ran sample-05 in both presets, then ran the new conservative luma/spatial outlier detector on those outputs and the eight prior-cycle outputs. All 10 outputs had zero flagged frames. The reported flash did not reproduce, including near output frame 1463 (about 24.4 seconds, six seconds before the 30.4-second video ends). Therefore its root cause is unknown. The detector is integrated into segment reports and unit-tested, but a flagged clip is not retried yet. Other eight outputs were from the previous cycle, not re-runs in this cycle.
- **R2 — PARTIAL.** Added `scripts/make_degraded.py`, a unit test, and `docs/BENCHMARK_DEGRADED.md`. Generated all 20 D1–D4 files outside the repository; size and achieved bitrate are recorded in the external manifest and public benchmark document. Candidate restoration runs, C0 quality metrics, C1–C4 comparison, and D2/D3 comparison videos were NOT RUN. No candidate winner or restoration gain is claimed.
- **R3 — FAIL.** Sample-05 Standard exceeded the 5 GB cap in segment 2: Torch reserved 5.34 GiB and process-dedicated memory 5.58 GiB. Only default 21/3 was measured. No clip alternatives or sample-04 retest were run; do not change the default from this evidence.
- **R4 — NOT RUN.** Seam/fidelity/flicker metrics, all-nine seam sweep, `ve trial`, and restore/RIFE calibration are not implemented or verified.
- **R5 — NOT RUN.** Neither two-hour Fast soak nor 60-minute Standard pause/resume/stop/resume run was executed.
- **R6 — PARTIAL.** The degraded generator and detector CPU/GPU tests pass, and privacy hygiene passed in the CPU suite. Smart App Control import mock, P0 job resume, and this-cycle remote CI confirmation were NOT RUN. No private videos, crops, models or weights were committed.

## Environment

- Windows 11 build 26300; NVIDIA GeForce RTX 4060 Ti 8 GB; driver 617.14.
- Python 3.12.14; PyTorch 2.14.1+cu130; CUDA runtime 13.0; PyNvVideoCodec 2.2.3; FFmpeg 9.0.2.
- Input videos and all derived media were kept under `Videos/` (ignored) or `C:\Users\pro\Documents\VideoEnhancer-P1a-2\` (outside the repository).

## A1–A9 acceptance status

| Criterion | Status | Evidence / limitation |
|---|---|---|
| A1 White frame | PARTIAL | 10/10 current/prior outputs tested; zero outliers. Root cause not reproduced; retry-once behavior remains absent. |
| A2 Degraded benchmark | PARTIAL | Generator and 20 files exist; degradation size/bitrate measured. C0–C4 image metrics and candidate comparison NOT RUN. |
| A3 Comparison videos | NOT RUN | D2/D3 side-by-side owner review videos not generated. |
| A4 Standard memory | FAIL | Sample-05 segment 2 measured 5.34 GiB Torch reserved and 5.58 GiB process dedicated. No sample-04 or alternatives. |
| A5 Seam and sweep | NOT RUN | No seam metric or nine-combination full-sample sweep. |
| A6 `ve trial` | NOT RUN | Command and four artifacts not implemented. |
| A7 Calibration | NOT RUN | Restore/RIFE calibration coefficients and 10%/initial estimate error not tested. |
| A8 Soaks | NOT RUN | Two-hour Fast and 60-minute Standard runs not executed. |
| A9 Housekeeping | PARTIAL | CPU/GPU suites pass; degraded generator test and privacy test pass. SAC mock, P0 resume and CI confirmation NOT RUN. |

## R1 white-frame investigation

Commands used for the two fresh sample-05 runs (the input is resolved privately; aliases are used in all outputs):

```powershell
$env:VE_FFMPEG_DIR = "<installed FFmpeg bin directory>"
$env:PYTHONPATH = "src"
$env:VE_HOME = "C:\Users\pro\Documents\VideoEnhancer-P1a-2\home"
python -m videoenhancer.cli enhance <private sample-05 input> --preset fast --short-side 1080 --fps 2x --codec hevc --backend cuda --segment-seconds 180 --output "C:\Users\pro\Documents\VideoEnhancer-P1a-2\quality\sample-05_fast.mp4"
python -m videoenhancer.cli enhance <private sample-05 input> --preset standard --short-side 1080 --fps 2x --codec hevc --backend cuda --segment-seconds 180 --output "C:\Users\pro\Documents\VideoEnhancer-P1a-2\quality\sample-05_standard.mp4"
```

Both produced 1,822 output frames from 911 inputs. The average output luma jump detector found no anomalous isolated frame in the reported region, and the integrated 16×16 RGB summary detector found zero outliers for both fresh outputs. The same detector found zero outliers in the eight previous-cycle full outputs. There is no frame index for an observed white frame because none was present in these encodes. The cause cannot be attributed to cuts, RIFE, BasicVSR++, encoding, or decoder ordering without reproducing it. A1 is therefore not a complete fix. Regression tests inject an absent-from-source white frame, retain a real cut, and reject a white frame also present in the source.

## R2 degradation measurements

All rates below are measured average file bitrates in kbit/s; sizes are decimal MB. Restoration metrics (PSNR-Y, SSIM, LPIPS, flicker), candidate speeds, and C0–C4 gain comparisons are NOT RUN.

| Sample | D1 MB / kbit/s | D2 MB / kbit/s | D3 MB / kbit/s | D4 MB / kbit/s |
|---|---:|---:|---:|---:|
| sample-01 | 1.43 / 676 | 0.63 / 298 | 1.60 / 756 | 0.74 / 351 |
| sample-02 | 1.06 / 815 | 0.56 / 434 | 1.27 / 980 | 0.48 / 369 |
| sample-03 | 1.23 / 827 | 0.65 / 436 | 1.44 / 969 | 0.59 / 399 |
| sample-04 | 2.89 / 1296 | 1.40 / 626 | 3.12 / 1397 | 0.90 / 403 |
| sample-05 | 3.16 / 872 | 1.56 / 431 | 3.75 / 1036 | 1.29 / 356 |

No claim can be made about which restoration candidate wins or whether BasicVSR++ gains over degraded input. D2/D3 comparison video paths: NOT CREATED.

## R3 memory and speed

Fresh Standard run: `C:\Users\pro\Documents\VideoEnhancer-P1a-2\quality\sample-05_standard.mp4`; input length 911 frames. Values are binary GiB from Torch/PDH telemetry. PDH is sampled every 60 seconds and can miss a higher transient.

| Segment | Input frames | Seconds | Input fps | Torch reserved peak (GiB) | Process dedicated sampled peak (GiB) |
|---:|---:|---:|---:|---:|---:|
| 0 | 394 | 160.1 | 2.46 | 4.91 | 4.76 |
| 1 | 388 | 164.5 | 2.36 | 5.34 | 5.58 |
| 2 | 129 | 57.8 | 2.23 | 4.24 | no sample above worker baseline |
| **Overall peak** | **911** | **382.4** | **2.38** | **5.34** | **5.58** |

The third segment's short duration did not yield a non-baseline 60-second PDH observation. Relative to the prior 2.483 input fps on this same sample, the aggregate is about 4.2% slower, but this was not a controlled A/B and the memory requirement fails regardless. The process-dedicated peak is a sampled peak, not an asserted hardware maximum. Potential allocation contributors include BasicVSR++ clip activations, RIFE full-resolution tensors and retained allocator blocks; this cycle did not isolate their individual contributions. No alternatives were measured and the default remains unvalidated against seam quality.

## R4 metrics and trial

| Metric or artifact | Result |
|---|---|
| Seam ratio at clip and segment joints | NOT RUN |
| Downscaled PSNR/SSIM and flicker, both presets | NOT RUN |
| Nine clip/overlap combinations on full sample-05 | NOT RUN |
| `ve trial` CPU/GPU and four output files | NOT RUN |
| Restore/RIFE calibration and estimate error | NOT RUN |

## R5 long runs

| Run | Result |
|---|---|
| Fast, 2-hour synthetic 720×1280 at 30000/1001 with audio and two pauses | NOT RUN |
| Standard, ≥60-minute real-content run with pause/resume and clean-stop resume | NOT RUN |
| Whole-run luma-outlier count and memory-growth bounds | NOT RUN |
| P0-created job resumes | NOT RUN |

## R6 verification

- `ruff check .`: PASS.
- `ruff format --check .`: PASS, 64 files.
- `pyright src`: PASS, 0 errors, 0 warnings, 0 informations.
- `pytest -m "not gpu and not soak" -q --basetemp .tmp\pytest-p1a2-final`: PASS, 110 passed, 3 skipped, 15 deselected, 38.33 s.
- `pytest -m gpu -q --basetemp .tmp\pytest-p1a2-gpu`: PASS, 15 passed, 113 deselected, 36.51 s.
- `pytest tests\test_degraded.py -q --basetemp .tmp\pytest-p1a2-degraded`: PASS, 1 passed, 1.81 s.
- Targeted detector/streaming regression tests: PASS, 4 passed, 10 deselected, 5.77 s.
- `ve probe` / `ve enhance` Smart App Control blocked-import mock: NOT RUN.
- `ve bench --calibrate`: NOT RUN.
- `ve trial`: NOT RUN.
- Degraded restoration benchmark and seam sweep: NOT RUN.
- Fast and Standard long soaks: NOT RUN.
- Initial CI run 37538292947: FAIL on both Windows and Ubuntu during test collection because `scripts` was not an importable package under CI. The test now loads the committed script by file path. Corrected CI run 37538587044: PASS on Windows (2m07s) and Ubuntu (56s); Ruff, format, Pyright and CPU tests passed on both.
- `git diff --check`: PASS before the final report was written.

## Files and external outputs

Changed repository files: `.ai/CURRENT_TASK.md`, `.ai/LAST_REPORT.md`, `docs/BENCHMARK_DEGRADED.md`, `scripts/make_degraded.py`, `src/videoenhancer/pipeline/outliers.py`, `src/videoenhancer/pipeline/runner.py`, `tests/test_degraded.py`, and `tests/test_p1a_pipeline.py`.

- Fresh sample-05 output: `C:\Users\pro\Documents\VideoEnhancer-P1a-2\quality\sample-05_fast.mp4`
- Fresh sample-05 output: `C:\Users\pro\Documents\VideoEnhancer-P1a-2\quality\sample-05_standard.mp4`
- Degraded inputs and manifest: `C:\Users\pro\Documents\VideoEnhancer-P1a-2\degraded\`
- D2/D3 side-by-side videos: NOT CREATED.
- GUI test: NOT RUN; GUI is explicitly out of scope for this cycle.

## Known issues and exact remaining work

The white frame was not reproduced; its cause is unresolved and flagged clips are not retried. The detector thresholds (0.20 mean-luma jump, 0.12 mean RGB difference on 16×16 summaries) are conservative engineering thresholds covered by synthetic tests, not calibrated against a representative dataset. Candidate restoration metrics, all-sample reruns through the integrated report path, quality comparisons, trial, seam measurements, memory tuning, long-duration pause/resume, SAC mock, P0 resume, and this-cycle CI remain outstanding.

Reproduce the private outputs with the commands above; generate degradations with:

```powershell
python scripts/make_degraded.py --input-dir "<private Videos directory>" --output-dir "C:\Users\pro\Documents\VideoEnhancer-P1a-2\degraded" --ffmpeg "<FFmpeg bin>\ffmpeg.exe" --ffprobe "<FFmpeg bin>\ffprobe.exe"
```

Designer/owner review is required for the unresolved root cause and for any decision to prioritize a follow-up cycle that completes the NOT RUN requirements. This report does not claim P1a completion; PR #2 should remain draft.
