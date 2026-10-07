# VideoEnhancer Cycle P1a-5 Report

- **Task ID / Cycle:** VE-P1a-5
- **Status:** PARTIAL
- **Date:** 2026-10-07
- **Branch:** `p1-restoration-gui`
- **PR:** #2 remains a draft; no merge performed.

## Summary

Task A changes and validation were completed. The direct CUDA-surface NVENC path produced one severe encoded-frame artifact in 1 of 3 earlier repeatability outputs; the internal driver/codec cause is not proven. After switching to synchronized, owned host buffers for NVENC, three Standard outputs had identical decoded frame hashes (1,822 frames each), and no severe encoded-frame artifact was detected. The compute-to-encoder outlier check retries once and falls back to a nearest valid frame, with measured check cost below 2%.

Task B is incomplete. C5, C8, C2, C9, and C11 measurements are available for D2; C10 and `owner-review-3` comparison videos were not completed. No default preset was changed. Benchmark documentation records available values and explicitly marks the incomplete comparison.

## A1 — Repeatability and stress

**PASS for post-fix Standard repeatability.** Three identical runs on clip B used `--preset standard --short-side 1080 --fps 2x --codec hevc --backend cuda --segment-seconds 180 --pipeline-queue-size 2`. Each output decoded to 1,822 frames at 1080x1920. SHA-256 hashes for every decoded frame matched across all three pairwise comparisons: 0 differing frames, maximum decoded-frame MAE 0.

Before the encoder input change, the same original path produced an encoded green/mosaic frame at output frame 895 in run 2 of 3. Across run 1 vs run 2, 621/1,822 decoded frames differed because the outputs were not byte-identical; mean of per-frame MAE was 0.16182, maximum per-frame MAE 65.8279, maximum pixel difference 239. The severe frame was flagged by the full-resolution output scan. This is evidence of an output corruption but does not prove the internal NVENC mechanism.

| Run | Queue size | Segment length | Output frames | Severe encoded corruption | Handoff check overhead |
|---|---:|---:|---:|---|---:|
| Repeat 04 | 2 | 180 s | 1,822 | 0 | 1.63% overall |
| Repeat 05 | 2 | 180 s | 1,822 | 0 | 1.65% overall |
| Repeat 06 | 2 | 180 s | 1,822 | 0 | 1.65% overall |
| Queue stress low | 1 | 180 s | 1,822 | 0 | 1.61–1.63% |
| Queue stress high | 16 | 180 s | 1,822 | 0 | 1.69% |
| Segment stress | 2 | 20 s | 1,822 | 0 | 1.511% overall |

The output scan also flags eight scene-cut boundary signals and one RIFE fallback location per run. Those are known detector signals, not severe encoded-frame corruption. The handoff validator recorded one RIFE nearest-valid fallback in the second segment; no unhandled output artifact remained in the post-fix scans. The 20 s run completed 12 segments without failure or OOM.

The requested forced-FP32 comparison was **NOT RUN**: no force-FP32 CLI/model option exists. The restorer normally uses FP16 on CUDA and falls back to FP32 only after a NaN/Inf failure.

## A2 — Pipeline path inspection

**PARTIAL.** Review found no explicit preallocated frame pool, `out=` writes, or `non_blocking` transfers in the BasicVSR++/RIFE output path. BasicVSR++ returns a newly computed result tensor; RIFE builds output frames via model inference and tensor stacking. The compute stage constructs an owned batch and synchronizes CUDA before placing it on the bounded queue. Queue ownership prevents the producer from mutating that batch after handoff.

The old encoder passed CUDA Array Interface plane views to PyNvVideoCodec. The official API supports GPU input, but its published interface did not give a clear lifetime guarantee for when an input surface may safely be rewritten. An explicit CUDA stream synchronization was added, but it did not prevent the one severe artifact. The encoder now synchronizes the current Torch stream, copies the packed NV12/P010 surface to a contiguous host-owned NumPy buffer, and calls NVENC in CPU-buffer mode. This removes direct GPU-surface lifetime/reuse from the handoff. The matching NVENC benchmark helper was updated to the same host-input mode.

The observed corruption correlated with the old GPU-surface path and was not reproduced in three host-buffer runs plus low/high queue and 20 s segment stress runs. The root cause inside PyNvVideoCodec, the driver, or NVENC is still **unexplained**. No FP32 causal comparison was available. NVIDIA API references: [PyNvVideoCodec Encoder API](https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-reference/encoder.html) and [API programming guide](https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-prog-guide/using_pynvvideocodec_apis.html).

The P1a-1 comparison commit was not verified in this continuation, so a line-by-line historical diff is **NOT RUN**.

## A3 — Handoff outlier guard

**PASS.** The compute-to-encoder handoff computes a downscaled RGB summary, checks NaN/Inf and unexpected range, compares restored/interpolated outputs against neighboring outputs and source summaries, retries a suspicious BasicVSR++ clip or RIFE pair once, then substitutes the nearest valid frame if the anomaly persists. The job report records stage, frame index, retry/fallback count, and check time.

Injected one-time and persistent corrupted-tensor tests cover retry and fallback. Measured Standard handoff-check overhead across the three repeat runs was 1.63–1.65%, below the 2% target. This is a guard for detected outliers, not proof that all possible corruption patterns will be detected.

## A4 — Regression evidence

**PARTIAL.** The current detector found one severe encoded artifact in one pre-fix output, so the “none in N frames” alternative does not apply. Unit tests inject corruption at the compute/handoff stage and verify retry/fallback. A regression test that reproduces the specific old NVENC encoded mosaic before the host-buffer change was not created; the low-level cause is not deterministic on demand.

## A5 — D2 candidate results (partial)

**PARTIAL: C10 is missing.** The 150-frame measurements and deltas versus C0/C1 are recorded in [BENCHMARK_DEGRADED.md](../docs/BENCHMARK_DEGRADED.md). Available candidates are C5, C8, C2, C9 and C11. C9 used BasicVSR++ NTIRE compressed-video Track 1 weights, SHA-256 `7b0e2ba02a24989bfb8f2ed4a06c8e6fd5dbeb193b1178ef7171cd1c455ddb0f`; the pinned external MMagic source is Apache-2.0. Peak Torch reserved VRAM was 5.599 GB (A) and 5.629 GB (B). The track-1 checkpoint is a different compression challenge track in the same BasicVSR++ family; no claim is made that it is a larger model.

C9 and 50/50 C1 blends were rendered in both clips. The blend candidate metrics are in the benchmark table. Blend speed was not measured; its reported VRAM is N/A because blending ran through CPU FFmpeg. C2 peak Torch memory was not recorded in its earlier job manifest. C11 has lower SSIM-Y than C1 on both clips and is therefore ineligible for recommendation under the task rule.

C10 was not run. FBCNN was staged externally, but it is a JPEG artifact-removal model and the benchmark was not completed; no claim of suitability for HEVC degradation or 5 GB runtime is made.

## A6 — Review videos

**NOT RUN.** No `owner-review-3` videos were produced. External candidate videos are in `C:\Users\pro\Documents\VideoEnhancer-P1a-5\bench\A` and `...\bench\B`; they are individual candidate files, not the requested labeled five-panel review composition.

## A7 — Validation and privacy

- `ruff check src tests`: PASS.
- `pyright src`: PASS (0 errors, 0 warnings).
- Full CPU/GPU pytest suite with an external temp directory: PASS, 132 passed, 3 skipped, 80.38 s. The skips are existing optional/platform conditions; no test was reported as run without execution.
- `git diff --check`: PASS.
- CI status: PASS for the four checks returned by `gh pr checks 2` (two Ubuntu CPU and two Windows CPU checks). No GPU-specific CI job was listed in that response.
- No source videos, names, or generated comparison videos were added to the repository.

## Changed files

- `.ai/CURRENT_TASK.md`
- `.ai/LAST_REPORT.md`
- `docs/BENCHMARK_DEGRADED.md`
- `src/videoenhancer/bench/runner.py`
- `src/videoenhancer/cli.py`
- `src/videoenhancer/media/encode.py`
- `src/videoenhancer/pipeline/outliers.py`
- `src/videoenhancer/pipeline/runner.py`
- `tests/test_cli.py`
- `tests/test_p1a_pipeline.py`
- `tests/test_pipeline.py`

## External artifacts and reproduction

External root: `C:\Users\pro\Documents\VideoEnhancer-P1a-5`.

- Standard repeatability outputs and decoded frame hashes: `repeatability\run-04-host.mp4`, `run-05-host.mp4`, `run-06-host.mp4` and the corresponding `run-04/05/06-hashes.jsonl`.
- Stress outputs: `stress\queue-01.mp4`, `stress\queue-16.mp4`, `stress\segment-20s.mp4`.
- D2 candidates: `bench\A\D2_C*.mp4` and `bench\B\D2_C*.mp4`.
- C9 runner: `run_c9.py`; Track 1 weights and FBCNN sources/checkpoints are under `models\`.
- Detector and metric tools: `scan_encoded.py`, `hash_frames.py`, `compare_frames.py`; base metric tool is `C:\Users\pro\Documents\VideoEnhancer-P1a-3\measure_metrics.py`.

To repeat C5 B quality measurement, run the existing `measure_metrics.py` with the original 150-frame reference, C5 output, `--first 0 --last 149`, and the installed FFmpeg/ffprobe paths. C9 inference uses `run_c9.py`; C9 blend uses FFmpeg `blend=all_expr=(A+B)/2` over equal-length, same-size C1 and C9 videos. The full Standard command settings are listed under A1.

## Errors, warnings, unresolved decisions, and intentionally omitted work

- Exact internal cause of the pre-fix NVENC artifact remains unknown.
- C10 and `owner-review-3` are unfinished; therefore the cycle is PARTIAL and no candidate ranking/recommendation is made.
- P1a-1 historical code comparison, forced-FP32 run, and CI status were not verified here.
- Candidate videos, model weights, temporary files, source footage, and metric intermediates remain outside the repository.
- No default-preset change, merge, or main-branch push was made.
