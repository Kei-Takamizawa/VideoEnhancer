# CURRENT_TASK: Cycle P0 (Engine foundation)

- **Task ID:** VE-P0
- **Date:** 2026-10-05
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

Save this file as `.ai/CURRENT_TASK.md` in the repository and commit it with your work. When you finish, write `.ai/LAST_REPORT.md` using the format in §13. Work on a branch named `p0-engine-foundation` and open a pull request to `main`. Do not push directly to `main`.

---

## 1. Purpose

Build the engine foundation that every later phase depends on:

1. **GPU video I/O pipeline.** NVDEC decode, then processing stages on GPU tensors, then NVENC encode. Include a CPU fallback path for tests.
2. **Segmented, resumable jobs.** A 2-hour video must be processed reliably, even across several days.
3. **Scheduling and time estimates.** An operating-hours scheduler, processing-time estimation, and a day-by-day plan.
4. **Benchmark harness.** It measures I/O throughput, and the speed and VRAM use of candidate AI models, on the target GPU.

This cycle applies no AI enhancement to output videos. Only placeholder stages are used (resize, and frame-rate doubling by blending).

---

## 2. Background (product summary)

VideoEnhancer is a Windows desktop app. It uses an NVIDIA GPU to improve low-quality web videos (social-media and streaming re-encodes) and to raise their frame rate.

### Product principles (they guide later phases; keep the architecture compatible)

- **Target look:** the original video before compression.
  - Remove compression damage: blocking, ringing/mosquito noise, banding, and smeared hair, eyelash and fabric detail.
  - Keep the source look, including beauty filters, makeup and color grading.
  - Never synthesize skin texture (for example pores) that the source does not have.
- **Compute is focused on people.** Faces, hair and skin get careful processing; the background is processed efficiently. This arrives in later phases.
- **Temporal stability first.** No flicker.
- **Long jobs must be reliable**, and the user must always see when processing will finish.

### Decisions already made

- NVIDIA only.
- Offline file conversion only (no real-time playback).
- Non-commercial project. Model licenses may be non-commercial; the code is MIT.
- Inputs are up to about 2 hours long, in portrait and landscape.
- People wearing face masks, and multiple people per frame, are handled in later phases.

### Reference machine

- Windows 11 with an RTX 4060 Ti, 8 GB VRAM (Ada architecture).
- The full pipeline in later phases must peak at 6.5 GB of VRAM or less.
- This cycle's pipeline must peak at **2 GB or less**, so that models fit later.

### Typical inputs (the owner's 5 sample clips)

- Portrait 720×1280, H.264 High, 1.5–2.8 Mbps.
- 30 or 30000/1001 fps, constant frame rate.
- BT.709, limited range, yuv420p.
- HE-AAC audio.
- One clip contains 9 hard scene cuts.
- The samples are third-party clips. **Never commit them.**
  - Read them from the directory in the environment variable `VE_SAMPLES_DIR`, if it is set.
  - ffprobe `nb_frames` values: 532, 326, 375, 561 and 911.

### Expected scale

- A 2-hour video at 30 fps is 216,000 input frames, or 432,000 output frames at 2x.
- The later Standard preset targets about 2.5 input fps on the reference GPU, which means about 24 GPU-hours per 2-hour video.
- Users will restrict processing to operating windows (for example 22:00–08:00), so one job runs across several days.

### Later phases (do NOT implement now)

- P1: whole-frame restoration models, RIFE frame interpolation, and an Electron + React GUI.
- P2: person pipeline (detection, tracking, occlusion-aware face restoration).
- P3: High Quality preset.

---

## 3. Current state

The repository contains only `README.md` and `LICENSE` (MIT). There is no code and there are no `.ai/` files yet.

---

## 4. Problems to solve in this cycle

- No pipeline exists yet.
- Long jobs will run for about a day of GPU time, spread over several days. The engine must make this:
  - **Safe:** resume after a crash, reboot or window end; no memory leaks; no audio/video drift.
  - **Predictable:** accurate time estimates and a day-by-day plan.

---

## 5. Requirements

### R1. Project setup

- **Package:** a Python 3.12 package `videoenhancer` with a CLI entry point `ve`.
  - Use `pyproject.toml`. Prefer uv for dependency management; pin versions in a lock file.
- **Platforms:** Windows 11 x64 is the primary platform. CPU-path tests must also pass on Linux, for CI.
- **Dependencies:**
  - PyTorch with CUDA: a current stable wheel that supports Ada. Record the versions in the report.
  - PyNvVideoCodec (PyPI `pynvvideocodec`, by NVIDIA, MIT license, supports Windows). Decoded frames convert to torch tensors without copying through DLPack.
  - FFmpeg and ffprobe: located through the `VE_FFMPEG_DIR` environment variable, or on PATH. Do not bundle them in this cycle.
- **Tooling:**
  - ruff for lint and format.
  - pytest.
  - Type hints, checked with pyright (basic) or mypy.
  - GitHub Actions CI that runs the CPU tests and lint on `windows-latest` and `ubuntu-latest`.
- **`.gitignore`:** cover media files (`*.mp4`, `*.mkv`, `*.mov`, `*.webm`, …), model weights, job folders and caches.
- **Language:** English for all code, comments and docs.

### R2. Probe and input normalization

**Probe.** `probe(path) -> MediaInfo` returns:
- Container and duration.
- Video codec, profile and bit depth.
- Coded width/height, display width/height after rotation, rotation (from side data or tags), and SAR.
- fps as exact rationals (average and `r_frame_rate`), and whether the stream is CFR or VFR.
- Frame count. Use the exact count when it is cheap; otherwise estimate it and flag it as estimated.
- Color matrix, range, primaries and transfer.
- Audio streams: codec, sample rate, channels, duration and start offset.

**HDR.** Reject HDR inputs (PQ or HLG transfer) with a clear message. HDR is out of scope for v1.

**Rotation.** Physically rotate output pixels to the display orientation. The output file must have no rotation flag.

**VFR to CFR.**
- Target rate: take the average rate. If it is within 0.5% of a standard rate, snap to that rate. Standard rates are 24000/1001, 24, 25, 30000/1001, 30, 50, 60000/1001 and 60. Otherwise, use the exact average rational.
- Map frames by presentation timestamp, choosing the nearest frame and duplicating or dropping frames as needed.
- Audio/video drift over the whole file must be at most 1 output frame duration.

**Color.**
- Convert decoded NV12/P010 to RGB float16 on the GPU, nominally in [0,1].
  - Use the correct matrix: BT.709, or BT.601 for untagged SD content of 576 lines or fewer.
  - Use the correct range.
- Convert back for encoding with the same matrix, limited range, and the same tags.
- Do not clamp out-of-range RGB values in intermediate stages unless a stage requires it, so that a passthrough round-trip is near-lossless.

### R3. Pipeline

**Data.** Stages operate on batches of RGB float16 CUDA tensors shaped (N,3,H,W). Each frame carries a timestamp as an exact rational. The CPU path uses torch CPU tensors.

**Stage interface** (suggested; adapt as needed):
- `name`.
- `context_before` and `context_after`: how many frames of temporal context the stage needs.
- The output size and frame-rate transform.
- `process(batch)`, plus setup and teardown.
- An `estimate_cost(input_size)` hook for the estimator.

Later stages will need per-face costs. Keep the cost model extensible.

**Placeholder stages for this cycle:**
- `resize`: GPU resize to the target short side.
  - Use bicubic with antialias, or Lanczos.
  - Preserve the aspect ratio and round dimensions to even numbers.
- `blend2x`: doubles the frame rate by inserting the average of neighboring frames. It stands in for RIFE.
  - Needs `context_after = 1`.
  - Must not blend across a scene cut; duplicate the frame instead.

**Presets for this cycle:**
- `passthrough`.
- `resize`.
- `p0-test`, which is resize plus blend2x.

The real presets (Fast, Standard, High Quality) come later. Design the preset registry so they can be added.

**Output size rule.**
- Target short side: `keep`, `1080` (default), `1440` or `2160`.
- Never downscale. If the source short side is at least the target, keep the source size.

**Frame-rate rule.**
- `off`, or `2x` (default).
- Skip 2x if the source is 50 fps or more. Cap the result at 60 fps.
- Use exact rationals, for example 30000/1001 becomes 60000/1001.
- With 2x, N input frames produce exactly 2·N output frames; the last frame is duplicated. Output duration therefore equals input duration.

**Encoder.** NVENC through PyNvVideoCodec.
- Default: HEVC Main10 (P010 input), with quality-oriented settings.
  - Choose the preset and tuning yourself, aiming for visually transparent quality.
  - Record the chosen settings and the resulting bitrate on the samples.
- Options: H.264 High 8-bit, and AV1 10-bit (supported on Ada).
- A test-only lossless mode, used by the color round-trip test.
- CPU path: libx265 or libx264 through FFmpeg.

**Concurrency.**
- Put bounded queues between decode, stages and encode, with a fixed maximum number of frames in flight.
- Overlap decode, compute and encode where practical, using CUDA streams or threads.

**Audio.**
- Do not process audio per segment.
- At final assembly, copy all original audio streams with the correct start offset.
- If a codec is not allowed in MP4, transcode it to AAC 256 kbps.
- Copy chapters and metadata if that is simple. Subtitles may be dropped in this cycle; log when they are.

### R4. Jobs, segments and resume

**Job store.**
- Default location: `%LOCALAPPDATA%\VideoEnhancer\jobs\<job_id>\`. Make it configurable through `VE_HOME`.
- Each job has a schema-versioned `manifest.json` containing:
  - The input path, size, mtime, and a hash of the first and last MB.
  - Settings, MediaInfo and scene cuts.
  - The segment list, with a state per segment: `pending`, `running`, `done` or `failed`.
  - Timing statistics, and created/updated timestamps.

**Atomic writes.**
- Write the manifest to a temp file, then replace the original with `os.replace`.
- Write segment outputs as `seg_XXXXX.tmp.<ext>` and rename them only on success.

**Analysis pass.**
- On job creation: probe, CFR mapping and scene-cut detection.
- Target: 10 minutes or less for a 2-hour 720p video on the reference GPU. Report the measured time.

**Segment planning.**
- Detect hard scene cuts first. The method is your choice, but it must be robust. On the sample `noachan1`, expect 9 ± 1 cuts.
- Prefer scene cuts as segment boundaries.
- Each segment must be 2–60 s of video.
- Target about 180 s of predicted processing time per segment, using the estimator. Make the target configurable.
- Segments are frame-exact, by frame index after CFR normalization, and do not depend on keyframe positions.
  - The decoder seeks to the previous keyframe and discards frames before the segment start.
  - PyNvVideoCodec's `SimpleDecoder` offers indexed random access. Verify frame-exactness with tests.

**Temporal context.**
- When processing segment k, feed `context_before` frames before its start and `context_after` frames after its end into the stages.
- Output only segment k's own frames.
- Frames interpolated between the last frame of segment k and the first frame of segment k+1 belong to segment k.

**Resume.**
- On start, validate the segments marked `done`: the file exists, and its ffprobe frame count and duration match expectations.
- Re-queue invalid segments and delete stale `.tmp` files.

**Final assembly.**
- Concatenate the segments without re-encoding (FFmpeg concat demuxer with stream copy), then mux the audio.
- By default, write `<name>_enhanced.mp4` next to the input. Make the location configurable.
- Check that the output frame count and duration match the plan.
- Then delete the segments, unless `--keep-segments` is given.

**Disk check.**
- Before start and before assembly, require free space of about 2.2 × the estimated output size, because segments and the final file coexist for a while.
- Fail early with a clear message.

**Out-of-memory handling.**
- On CUDA OOM, retry the segment once with a smaller batch or tile.
- If it fails again, mark the segment failed and log it.
- A failed segment must never corrupt other segments.

**Sleep prevention (Windows).**
- While a segment runs, call `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`.
- Release it when idle or waiting. The display may still sleep.

### R5. Operating-hours scheduler

**Settings file.** A schema-versioned `schedule.json` in `VE_HOME`:
- `enabled`: default false, which means processing is always allowed.
- `weekly`: a list of windows `{days: [mon..sun], start: "HH:MM", end: "HH:MM"}`.
  - Times use 15-minute granularity.
  - A window with `end <= start` ends on the next day.
  - Minimum window length is 15 minutes.
- `exceptions`: entries `{date: "YYYY-MM-DD", windows: [{start, end}] | "off"}`.
  - Availability between that date's 00:00 and 24:00 is replaced by the exception's windows.
  - An exception window may cross midnight explicitly.
- `override_until`: optional. An ISO datetime, or `"job-complete"`, meaning "ignore the schedule until then".

**Semantics.**
- Availability is the union of intervals on the local-time timeline.
- Use `zoneinfo` and keep the logic DST-safe: compute in local wall-clock time, and resolve nonexistent or ambiguous times to the earliest valid instant.

**Run controller** (the `ve run` worker):
- Processes the queue in order while processing is available.
- Before starting a segment, predicts its duration d̂. It starts the segment only if `now + 1.1·d̂ + 30 s ≤` the end of the current availability interval. Otherwise it waits for the next interval.
- At the end of an interval, if a segment is still running, it must:
  - abort the segment within 10 s;
  - discard its temp output and mark it `pending`;
  - record the wasted time.
- Outside availability, it sleeps with negligible CPU and GPU use and wakes at the next interval start. It re-reads the settings file at least every 60 s, so edits take effect.
- On Ctrl+C it stops gracefully: no new work starts, the current segment is aborted cleanly, and state stays consistent.

**Job control while a worker runs.**
- Pause, resume and cancel a job, either through job state in the store (the worker polls at least every 2 s) or through a local IPC. Your choice.
- Design it so that a GUI process can control the worker later (P1).

### R6. Estimation and day-by-day plan

**Machine profile.**
- `ve bench --calibrate` takes 5 minutes or less. It measures the throughput of decode, color conversion, each placeholder stage, and encode, at 720×1280 and 1080×1920.
- Store the result as JSON, keyed by GPU name and driver version.
- Without a profile, the estimator uses conservative defaults and marks estimates as "uncalibrated".

**Job estimate.**
- The sum, over pending segments, of the predicted time. Predictions come from per-stage cost models: cost per input frame as a function of pixel count, plus a per-segment overhead.
- Return `{seconds, low, high, calibrated: bool}`.
- The range is ±25% before the job has any data, then narrows using the observed variance.

**Live correction.**
- After each finished segment, update a per-job correction factor: an EMA (α = 0.3) of actual over predicted time.
- Apply the factor to the remaining segments.

**Planner.**
- Inputs: the queue, each job's remaining estimate, the schedule, and the current time.
- Outputs:
  - A timeline of run intervals per job, and each job's predicted completion datetime.
  - A per-day summary with:
    - the date;
    - the availability windows on that date;
    - planned run hours;
    - each job's progress range (start % → end %);
    - the completion time, if it falls on that date.
- Days split at local midnight.

**Accuracy targets** (on the 2-hour soak run in §10.I):
- After 10% progress, the predicted total must be within ±15% of the actual total.
- The initial calibrated estimate must be within ±30%.

### R7. Benchmark harness (`ve bench`)

**Part A: I/O and placeholder stages.** Measure:
- NVDEC decode fps for 720×1280 H.264 and for 1080×1920 HEVC.
- Color conversion, resize and blend2x.
- NVENC encode fps at 1080×1920 for HEVC Main10 (with the chosen settings), H.264 and AV1.
- End-to-end `p0-test` fps.
- Peak VRAM (from NVML and from torch) and peak RSS.

**Part B: candidate models.** This part is best effort.
- Each item is independent. If an item is skipped, report the reason.
- Run PyTorch FP16 on CUDA under `torch.inference_mode()`. Warm up, then time at least 50 iterations.
- Report the median ms, p90 ms, peak VRAM, and the largest batch or tile that works on this GPU.
- TensorRT is optional in this cycle.

Items:
1. RIFE 4.25 (Practical-RIFE, MIT): 2x interpolation on 1080×1920 frame pairs.
2. Real-ESRGAN compact `realesr-general-x4v3` (SRVGGNetCompact, BSD-3-Clause): 720×1280 input.
3. BasicVSR++ (Apache-2.0): 720×1280 input, in clips of 15 frames.
   - Use its compressed-video-enhancement weights (NTIRE 2021 decompression) if obtainable; otherwise use its VSR weights.
   - Find a tile and clip size that fits in 8 GB.
4. CodeFormer (S-Lab License 1.0, non-commercial): 512×512 aligned faces, batch 1, 4 and 8, fidelity weight 0.7.
5. KEEP (ECCV 2024, S-Lab License 1.0, non-commercial; video face super-resolution): 512×512 face clips.
6. Face detection on a full 720×1280 frame: SCRFD (InsightFace model zoo; the weights are for non-commercial research only), or RetinaFace.
7. Face parsing: BiSeNet trained on CelebAMask-HQ, or an equivalent model, at 512×512.

**Output.**
- Write `bench_report.md` and `bench_report.json`.
- Include the GPU name, driver, VRAM, OS, and the torch, CUDA and TensorRT versions.
- For each item, include its license, the weights' source URL and sha256.
- Download model weights on demand to `VE_HOME/models/`, verify them with sha256, and never commit them.

### R8. CLI

- All output is in English.
- Output is human-readable by default; `--json` gives machine-readable output.

Commands:
- `ve probe <input>`
- `ve add <input> [-o OUTPUT] [--preset passthrough|resize|p0-test] [--short-side keep|1080|1440|2160] [--fps off|2x] [--codec hevc|h264|av1] [--keep-segments]`
  - Analyzes the video, plans segments, and prints the estimate and the day-by-day plan.
- Queue management:
  - `ve queue`: lists jobs with state, progress % and ETA.
  - `ve move <job> <position>`
  - `ve pause|resume|cancel <job>`
- `ve plan [--days N]`: prints the day-by-day plan for the whole queue, as in the example below.
- `ve schedule show | set-weekly ... | add-exception ... | remove-exception ... | enable | disable | override --until <ISO>|job-complete`
- `ve run [--ignore-schedule]`: runs the worker in the foreground until the queue is empty.
- `ve enhance <input> [same options as add]`: adds the job and runs it immediately, ignoring the schedule. A convenience for testing.
- `ve bench [--calibrate] [--models all|<list>]`

Example `ve plan` output (illustrative numbers):

```
Date        Windows                     Run    Job progress
Mon 10/06   22:00–24:00                 2.0h   A: 0% → 8%
Tue 10/07   00:00–08:00, 22:00–24:00    10.0h  A: 8% → 50%
Wed 10/08   00:00–08:00, 22:00–24:00    10.0h  A: 50% → 92%
Thu 10/09   00:00–08:00                 2.0h   A: 92% → 100% (done ~02:00)
```

### R9. Logging and diagnostics

- A per-job rotating log file, plus a global log. Write structured logs (JSON lines) and human-readable console output.
- Every error message states what failed, which segment, and what to do next.
- Write the GPU name, driver and software versions at the top of each job log.
- Stay local: no network access except model downloads requested by the user or by `ve bench`.

---

## 6. UI/UX requirements (this cycle)

**No GUI in this cycle.** The CLI is the UI:
- Concise English text.
- Consistent units: h/m/s, %, fps, GB.
- Local times shown with the weekday.
- Clear progress lines during `ve run`: the job, segment k/n, fps, ETA, and the next pause time if a window will end.

**Prepare for the P1 GUI.** Keep the engine API stable enough that an Electron GUI can later call it through a local API. Do not build that API server yet, unless it falls out naturally.

---

## 7. Technical constraints

- **Windows-first.** Do not require WSL.
- **No custom CUDA extensions.** Do not compile them (for example mmcv/mmagic or DCN builds); they break on Windows.
  - Use pure PyTorch or torchvision ops. For example, `torchvision.ops.deform_conv2d` supports modulated deformable convolution.
  - Prebuilt wheels are fine.
- **No non-commercially licensed source code in this MIT repository.** Do not copy code from CodeFormer, KEEP, InsightFace models and similar projects.
  - Use them as external dependencies instead: pip packages, git dependencies, or code fetched at runtime into `VE_HOME`.
  - Document their licenses in `docs/THIRD_PARTY_MODELS.md`.
  - Apache, MIT and BSD code may be vendored only together with its license notice.
  - Hint: `spandrel` and `spandrel_extra_arches` can load several image-restoration architectures without their original repositories. Verify which architectures they cover.
- **VRAM:** this cycle's pipeline must peak at 2 GB or less for 720×1280 → 1080×1920 with 2x.
- **Determinism:** the CPU path must be deterministic, so that exact resume tests are possible.
- **Network:** none at processing time, except explicit model downloads.

---

## 8. Change targets (what to create)

- `pyproject.toml` and a lock file.
- `src/videoenhancer/...`. Suggested modules:
  - `media/`: probe, decode, encode, color, mux.
  - `pipeline/`: stages, presets, runner.
  - `jobs/`: store, manifest, segments.
  - `schedule/`: windows, planner, controller.
  - `estimate/`, `bench/`, `cli.py`, `config.py`, `logging.py`.
- `tests/`: unit, integration, `gpu` and `soak` markers.
- `scripts/`: synthetic test-video generation and the soak test.
- `docs/ARCHITECTURE.md` (short) and `docs/THIRD_PARTY_MODELS.md`.
- `.github/workflows/ci.yml` and `.gitignore`.
- `README.md`: keep it short, in English, written for non-engineers.
  - Say what VideoEnhancer will do, and that it is under development.
  - Give no technical detail beyond "requires an NVIDIA RTX GPU".

---

## 9. Do not change / out of scope

- Do not add AI enhancement to the output pipeline; use placeholders only. Models appear only in `ve bench`.
- No GUI, installer, auto-start or wake-from-sleep.
- Do not commit media samples, model weights or generated videos.
- Do not change `LICENSE`.

---

## 10. Acceptance criteria

**A. Setup**
- `uv sync` (or a documented equivalent) works on Windows 11.
- `ve --help` lists all commands.
- ruff and the type check pass.
- CI is green on `windows-latest` and `ubuntu-latest` (CPU tests).

**B. Probe**, on synthetic tests and, if `VE_SAMPLES_DIR` is set, on the 5 samples:
- Reports 720×1280.
- Reports exact fps rationals (30/1 and 30000/1001).
- Reports correct frame counts: 532, 326, 375, 561 and 911.
- Rotation handling and HDR rejection behave as specified.

**C. Output geometry and timing.** Run `ve enhance` with `p0-test`, on both the CPU and GPU paths.
- Geometry:
  - Portrait 720×1280 → 1080×1920.
  - Landscape 1280×720 → 1920×1080.
  - A 1280×720 file with rotation=90 metadata → 1080×1920 portrait output pixels, with no rotation flag.
- Timing:
  - The fps is exactly doubled (30000/1001 → 60000/1001), and the output has 2·N frames.
  - Output duration equals input duration ± 1 output frame.
  - Audio duration and start offset match the source within ± 20 ms.
  - A synthetic VFR input (mixed 30 and 60 fps timestamps) gives CFR output with total audio/video drift of at most 1 frame.

**D. Color round-trip.** GPU path, lossless test mode, passthrough preset. Compare decoded output with decoded input, as 8-bit planes:
- Y PSNR ≥ 48 dB.
- U and V PSNR ≥ 40 dB.
- The mean signed error per plane is at most 0.5 code values, to catch matrix or range bugs.

**E. Resume.**
- Use a 3-minute synthetic video. During processing, hard-kill the worker process (`taskkill /F` or SIGKILL) at 3 random points, resuming after each kill.
- The final output has exactly the expected frame count.
- CPU path: per-frame hashes equal those of an uninterrupted run.
- GPU path: per-frame PSNR ≥ 50 dB against an uninterrupted run.
- No temp files are left over.

**F. Scheduler.** Unit tests with an injectable clock cover:
- Windows crossing midnight, and multiple windows per day.
- Exceptions (`off` and custom windows), and the override.
- DST transitions, tested with `America/New_York`.
- 15-minute validation.

The run controller must also, in tests:
- Not start a segment that is predicted to overrun the window.
- Abort and re-queue a running segment within 10 s of the window end.
- Resume at the next window.

**G. Planner.**
- Deterministic tests for multi-day, multi-job plans.
- `ve plan` prints the table format shown in R8.
- The plan updates after `ve move`, a schedule edit, or a preset change.

**H. Estimation.** On the GPU soak run (criterion I):
- After 10% progress, the predicted total is within ±15% of the actual total.
- The initial calibrated estimate is within ±30%.
- Report the numbers.

**I. Soak test** (GPU, reference machine).
- Input: a synthetic 2-hour portrait 720×1280 video at 30000/1001 fps with audio.
  - Generate it with FFmpeg: a moving test pattern, plus noise and a tone, with a few hard cuts.
- Process it with `p0-test`, using a schedule (exception windows are fine) that forces at least 2 pauses.
- Pass conditions:
  - The job completes, and the output is valid according to ffprobe.
  - The frame count is 2·N.
  - Between minute 10 and the end, RSS grows by 200 MB or less, and VRAM by 100 MB or less.
  - There are zero crashes.
- Record the total wall time, GPU time and fps, and the analysis-pass time.

**J. Benchmark.**
- `ve bench` produces both report files.
- Part A is complete.
- Part B has measurements for at least items 1, 2, 3, 4 and 6, and reasons for any skipped items.

**K. Disk check.** With a fake small free-space value (injectable), `ve add` fails early with a clear message.

**L. Hygiene.**
- No media or model files are in git.
- `docs/THIRD_PARTY_MODELS.md` lists every model that `ve bench` touches, with its license and source.

---

## 11. Builds and tests to run

1. `uv sync` (or equivalent), `ruff check`, `ruff format --check`, and the type check.
2. `pytest -m "not gpu and not soak"` (CPU tests; run everywhere).
3. `pytest -m gpu` on the RTX machine.
4. The soak test script (criterion I) on the RTX machine. It takes hours and may run unattended overnight.
5. `ve bench --calibrate` and `ve bench --models all` on the RTX machine.

If your environment has no NVIDIA GPU:
- Implement everything and run the CPU tests.
- List the exact GPU, soak and bench commands the owner must run, and mark them "NOT RUN" in the report.
- Never report a test as passed if it did not run.

---

## 12. GUI checks

There is no GUI in this cycle. Instead, the owner will check on the RTX 4060 Ti machine:

1. `ve enhance` on each sample in `VE_SAMPLES_DIR`. The output must:
   - play in a standard player (VLC or Windows Media Player);
   - have the correct orientation;
   - play smoothly at 60 fps;
   - keep audio in sync.
2. Set a schedule window that ends about 5 minutes from now, then start `ve run`.
   - The worker must pause at the window end and resume at the next window.
   - `ve plan` must match what actually happened.

---

## 13. Report to write in `.ai/LAST_REPORT.md`

- **Summary:** what was implemented, by requirement ID (R1–R9), with any deviations and the reasons for them.
- **Environment:** OS, GPU, driver, and the Python, torch, CUDA, PyNvVideoCodec and FFmpeg versions. State whether you had access to a GPU.
- **Test results by acceptance criterion (A–L):**
  - PASS, FAIL or NOT RUN for each.
  - The commands used.
  - Key numbers: fps, VRAM and RSS peaks, PSNR values, estimate errors, soak duration, analysis-pass time.
- **Benchmark tables:** a copy of `bench_report.md`.
- **Encoder:** the chosen NVENC settings and the resulting bitrate on the samples, if available.
- **Known issues and risks**, and open questions for the designer. For example: segment overhead %, seek-accuracy problems, encoder limits.
- **Reproduction steps:** the exact steps for the owner to reproduce the GPU, soak and bench runs.
