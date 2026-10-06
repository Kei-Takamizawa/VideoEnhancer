# VideoEnhancer Cycle P1a Report

- Task ID / Cycle: VE-P1a
- Status: PARTIAL
- Date: 2026-10-06
- Branch: `p1-restoration-gui`

## Summary by requirement

- R1: PASS. README is English-only, the language selector and ten translated README files are removed, and no references remain in public docs, tests, CI, project configuration or ignore files. The Windows Smart App Control section remains. The overview now describes command-line compression restoration and smoother motion, with a graphical interface planned.
- R2: PASS for implementation and CPU bound tests. All presets use the bounded decode/compute/encode worker path. Standard restoration uses overlapping, scene-cut-bounded clips. Each overlap frame is owned by the clip where it is farthest from an edge; ties go to the later clip. Segment context and synthetic identity ownership tests pass. Injected CUDA OOM retries once with smaller clips. Long-duration memory and abort-under-10-seconds soak validation remain NOT RUN.
- R3: PARTIAL. The production wrapper uses the P0 BasicVSR++ loader and checkpoint SHA-256 `6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a`. A real CUDA stage test passed. All nine clip-length/overlap combinations were sampled on a 30-frame, 720x1280 excerpt. Seam scores were not implemented, so the default remains the existing provisional 21/3 and is not validated as the final quality trade-off.

  | Clip length | Overlap | Seconds/owned frame* | Torch reserved peak (GB) | Process PDH sample peak (GB) | Seam score |
  |---:|---:|---:|---:|---:|---|
  | 15 | 2 | 0.826 | 2.976 | 2.596 | NOT RUN |
  | 15 | 3 | 0.805 | 3.332 | 2.516 | NOT RUN |
  | 15 | 4 | 1.027 | 3.332 | 2.547 | NOT RUN |
  | 21 | 2 | 0.624 | 3.544 | 2.831 | NOT RUN |
  | 21 | 3 | 0.645 | 3.603 | 2.831 | NOT RUN |
  | 21 | 4 | 0.667 | 3.882 | 3.187 | NOT RUN |
  | 30 | 2 | 0.485 | 5.123 | 3.157 | NOT RUN |
  | 30 | 3 | 0.484 | 5.123 | 3.157 | NOT RUN |
  | 30 | 4 | 0.486 | 5.123 | 3.157 | NOT RUN |

  `*` The sweep sampled PDH synchronously after each restore and RIFE stage. These per-frame times include diagnostic sampling overhead and are not production throughput. Memory figures use decimal GB. PDH samples are point samples after stages, not hardware maxima.
- R4: PARTIAL. GPU RIFE test passed for 1080x1920 stride-32 padding/crop, exactly 2N output frames and bit-exact original-frame pass-through. CPU tests passed for synthetic cuts, extreme-flow fallback and non-finite input. No actual owner-sample hard-cut audit was run. All full outputs had zero reported fallbacks.
- R5: NOT RUN. Seam, downscaled PSNR/SSIM fidelity and flicker metrics are not implemented. No visual-quality claim is made.
- R6: PARTIAL. Windows process-specific `GPU Process Memory` PDH sampling was verified on the reference machine and is recorded every 60 seconds in job telemetry. A 1 GiB CUDA allocation changed PID-scoped PDH from 112,070,656 to 1,204,699,136 bytes while Torch reserved changed from 0 to 1,073,741,824 bytes; after release and `empty_cache`, PDH was 130,953,216 and Torch reserved was 0. The two-hour fast soak and memory-growth criterion are NOT RUN.
- R7: PARTIAL. The estimator has restore and interpolation cost components and `ve add` presents fast/standard estimates. `ve bench --calibrate` was NOT RUN; the current calibration profile generator does not populate measured restore/interpolation coefficients.
- R8: NOT IMPLEMENTED. `ve trial` and the four comparison/report outputs are absent; this remains P1a work despite the separately postponed graphical trial viewer.
- R9: PARTIAL. Full `fast` and `standard` outputs were produced for all five private inputs outside the repository and ffprobe confirmed exactly 2N frames at 1080x1920. Standard exceeded the 5 GB process/Torch reserved target on several samples. The fast two-hour soak and 60-minute standard pause/resume run were NOT RUN.
- R10: PARTIAL. Architecture, development and third-party model docs were updated. The FFmpeg executable's Authenticode status is `NotSigned`; whether it runs with Smart App Control enabled is NOT TESTED because Smart App Control was already off and was not changed. The Smart App Control mock and P0-created job resume acceptance are NOT RUN. `uv sync --locked` could not run locally because `uv` is not installed or available on PATH; GitHub Actions ran it successfully. The first pushed CI run failed because the broad `models/` ignore rule omitted `src/videoenhancer/models/`; after narrowing the ignore rule and tracking the production model package, both Windows and Ubuntu CI passed on commit `d0ecf9e` (runs 37469261585 and 37469270489).

## Environment and verification

- OS: Windows 11 build 26300
- GPU: NVIDIA GeForce RTX 4060 Ti, 8 GB; driver 617.14
- Python 3.12.14; PyTorch 2.14.1+cu130; CUDA runtime 13.0; PyNvVideoCodec 2.2.3
- FFmpeg 9.0.2 (Gyan shared build)
- FFmpeg executable signature: `NotSigned` (`Get-AuthenticodeSignature`)
- `ruff check .`: PASS
- `ruff format --check .`: PASS (56 files)
- `pyright src`: PASS (0 errors, 0 warnings)
- CPU suite: PASS, 107 passed, 3 skipped, command `python -m pytest -m "not gpu and not soak" --basetemp <fresh local temp directory>`; FFmpeg was supplied through `VE_FFMPEG_DIR`.
- GPU suite: PASS, 15 passed, command `python -m pytest -m gpu --basetemp <fresh local temp directory>`; included real BasicVSR++ and RIFE stages on CUDA.
- The first CPU test invocation used pytest's protected default temp root and produced 46 setup errors (`PermissionError: C:\Users\pro\AppData\Local\Temp\pytest-of-pro`). Re-running with a new dedicated `--basetemp` passed; these were test-environment setup errors, not test assertion failures.
- `git diff --check`: PASS.
- `uv sync --locked`: NOT RUN locally; PowerShell could not resolve `uv` (`The term 'uv' is not recognized`).
- An initial sweep instrumentation attempt failed with a `NameError` in the temporary observer; the observer was corrected and all nine sweep rows completed. No application code change was needed for that harness error.

## Full-sample GPU runs

Inputs are listed privately under `Videos/`. To avoid writing their names into committed files, output IDs `sample-01` through `sample-05` follow the input filenames in lexicographic order. All files are outside the repository:

- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-01_fast.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-01_standard.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-02_fast.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-02_standard.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-03_fast.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-03_standard.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-04_fast.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-04_standard.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_fast.mp4`
- `C:\Users\pro\Documents\VideoEnhancer-P1a\quality\sample-05_standard.mp4`

Frame verification: the five inputs had 532, 326, 375, 561 and 911 frames (2,705 total). Each fast and standard output had exactly twice its corresponding input count, was 1080x1920, and retained the 60 or 60000/1001 CFR rate. Audio was preserved by the full `ve enhance` job assembly.

| Sample ID | Preset | Input frames | Pipeline seconds | Input fps | Decode s | Restore s | Resize s | RIFE s | Encode s | Other s | Peak Torch reserved GB | Peak process PDH sampled GB | Peak RSS GB | Fallback / NaN / OOM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 01 | fast | 532 | 30.634 | 17.366 | 28.11 | 0 | 0.05 | 27.94 | 14.41 | 2.52 | 1.428 | Peak not sampled (<60s) | 1.228 | 0 / 0 / 0 |
| 01 | standard | 532 | 230.278 | 2.310 | 205.55 | 185.32 | 0.03 | 34.69 | 41.80 | 10.24 | 5.014 | 4.290 | 1.889 | 0 / 0 / 0 |
| 02 | fast | 326 | 19.679 | 16.566 | 17.21 | 0 | 0.03 | 17.16 | 8.74 | 2.47 | 1.432 | Peak not sampled (<60s) | 1.226 | 0 / 0 / 0 |
| 02 | standard | 326 | 137.815 | 2.365 | 130.64 | 111.79 | 0.01 | 20.93 | 25.20 | 5.09 | 5.031 | 5.186 | 1.906 | 0 / 0 / 0 |
| 03 | fast | 375 | 22.238 | 16.863 | 19.86 | 0 | 0.04 | 19.73 | 10.16 | 2.38 | 1.533 | Peak not sampled (<60s) | 1.226 | 0 / 0 / 0 |
| 03 | standard | 375 | 157.602 | 2.379 | 149.22 | 128.30 | 0.02 | 24.06 | 29.38 | 5.22 | 5.214 | 4.391 | 1.890 | 0 / 0 / 0 |
| 04 | fast | 561 | 32.268 | 17.385 | 29.74 | 0 | 0.05 | 29.48 | 15.28 | 2.53 | 1.428 | Peak not sampled (<60s) | 1.227 | 0 / 0 / 0 |
| 04 | standard | 561 | 240.658 | 2.331 | 217.69 | 193.73 | 0.01 | 36.27 | 44.94 | 10.64 | 5.641 | 5.186 | 1.890 | 0 / 0 / 0 |
| 05 | fast | 911 | 50.425 | 18.066 | 47.88 | 0 | 0.08 | 47.39 | 24.72 | 2.54 | 1.567 | Peak not sampled (<60s) | 1.227 | 0 / 0 / 0 |
| 05 | standard | 911 | 366.853 | 2.483 | 352.82 | 299.77 | 0.03 | 55.99 | 73.09 | 11.06 | 4.989 | 4.779 | 1.943 | 0 / 0 / 0 |

Per-stage clocks overlap because decode, compute and encode are concurrent worker threads, so their times are not additive. The Standard end-to-end aggregate was 2,705 / 1,133.206 = 2.388 input fps; Fast was 2,705 / 155.244 = 17.426 input fps. Standard met the 2.0 fps target in this run, but failed the ≤5 GB memory target: Torch reserved peaked at 5.641 GB and process-specific PDH samples peaked at 5.186 GB. The largest sampled RSS was 1.943 GB. The PDH series is sampled every 60 seconds and may miss a higher transient; Torch's peak reserved statistic is the per-segment high-water mark.

Fallbacks, NaN retries and OOM retries were all zero in these full-sample runs. Seam, fidelity and flicker scores are NOT RUN, so the files are for the owner's visual inspection and are not a claim of perceptual quality.

## Acceptance criteria

| Criterion | Status | Evidence / limitation |
|---|---|---|
| A1 | PASS | README translation cleanup and search. |
| A2 | FAIL | Streaming/live-frame-bound unit test passes; Standard peak 5.641 GB Torch reserved and 5.186 GB process PDH sampled. |
| A3 | PARTIAL | CPU ownership, identity, cut-bounded clips, segment context tests pass; exhaustive GPU seam equivalence was not run. |
| A4 | PARTIAL | Nine memory/timing rows collected; seam metric absent and final 21/3 default not justified by visual/seam results. |
| A5 | PARTIAL | GPU padding/crop, bit-exact originals and 2N test pass; CPU synthetic cut/fallback test passes; real sample cut audit not run. |
| A6 | PASS | Injected NaN retry/failure and OOM retry tests pass. |
| A7 | NOT RUN | Seam, PSNR/SSIM and flicker metrics absent. |
| A8 | PARTIAL | PID-specific PDH and 1 GiB allocate/free test pass; 2-hour fast soak not run. |
| A9 | PASS | Standard aggregate 2.388 fps across all five; Fast 17.426 fps. |
| A10 | NOT RUN | 60-minute standard pause/resume/clean-stop soak not run. |
| A11 | PARTIAL | Ten full outputs exist and frame counts pass; `ve trial` and its four files are not implemented. |
| A12 | PARTIAL | FFmpeg is unsigned; Smart App Control mock and enabled-state behavior not tested. |
| A13 | PARTIAL | Local CPU/GPU suites pass; GitHub Actions passed on Windows and Ubuntu (runs 37469261585 and 37469270489). The P0-created job resume acceptance remains unrun. No media or weights were added to Git. |

## Deviations, unresolved work and reproduction

- Standard peak GPU memory exceeds its stated cap; use the table and the `clip_sweep/` measurements to guide the next authorized tuning cycle. The 30-frame sweep did not establish long-run peaks or seams.
- Seam/fidelity/flicker computation, `ve trial`, calibrated restore/interpolation coefficients, Smart App Control mock, real cut audits, fast soak, 60-minute standard soak, and remote CI confirmation remain unresolved.
- Reproduce the passing CPU suite with `VE_FFMPEG_DIR` set to the installed FFmpeg `bin` directory and a new writable pytest `--basetemp`; run `pytest -m "not gpu and not soak"` and `pytest -m gpu` separately.
- Reproduce each full output with `ve enhance <input> --preset fast|standard --short-side 1080 --fps 2x --codec hevc --backend cuda --output <path outside repository>`.
- No GUI was built or tested, as required for this cycle. Visual judgments of faces, seams and temporal texture remain the owner's review step.
