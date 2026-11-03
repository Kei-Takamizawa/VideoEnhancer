# CURRENT_TASK: VE-R1d-2 (face-aware library posters)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1d-2
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` (draft PR #20), on top of VE-R1d at cdf799c.
- Write a new `.ai/LAST_REPORT.md` for VE-R1d-2; keep the older reports below it. Record a disk baseline and growth. The known local `p1f3-visual` "fresh calibration" failure does not make the cycle PARTIAL. If a scratch delete is refused, list paths and sizes for the operator.
- **Date:** 2026-11-03
- Same isolation rules as VE-R1d. Do not start, stop or restart the real service.
- **Dependencies:** first check whether the live `.venv` already has a usable ONNX runtime (`onnxruntime` or `onnxruntime-gpu`) or OpenCV with `FaceDetectorYN`. If a new or changed Python dependency is needed, stop **before** changing `pyproject.toml`/`uv.lock` or running `uv sync`, and report BLOCKED with the exact package and version; the operator stops the service first and resumes you.

## 1. Owner request (2026-11-03 12:24Z)

"Use face detection so the library thumbnail is a place where faces are clearly visible. A person wearing a mask: a place where the masked face is clearly visible. A person who takes the mask off partway: a place where the unmasked face is clearly visible. Several people: a place where all their faces are clearly visible."

## 2. Work

1. **Detector:** a small CPU face detector with landmarks under a permissive licence (MIT/Apache/BSD), e.g. YuNet from OpenCV Zoo. Do not use models with non-commercial licences (for example InsightFace/SCRFD weights). Do not commit weights: download once at first use from a pinned URL into `VE_HOME/models/face/`, verify a pinned SHA-256, and record the licence in `docs/REMOTE.md`. If the download fails, fall back to the R1c poster rule and retry later.
2. **Mask signal:** decide per detected face whether the lower face is covered (masked) or visible. Prefer a permissively licensed classifier if a small one exists; otherwise a documented heuristic (for example colour/texture difference between the cheek/forehead region and the mouth/nose region using the landmarks). Report its accuracy on the test set below.
3. **Candidate frames:** decode about 1 frame per second (at most 300, evenly spread, skip the first and last 3 %), downscaled to about 640 px wide, CPU only, low priority, never while a GPU segment runs (same gate as R1c thumbnails).
4. **People count:** estimate N = the 90th percentile of per-frame face counts (faces above a minimum size, about 3 % of the frame height).
5. **Unmasked preference:** if any frame has at least as many unmasked faces as faces in other frames, prefer unmasked faces (this covers a person who takes the mask off). A person who never removes the mask is scored on their masked face.
6. **Score per frame:** first maximise the number of good faces up to N (all people visible); then the number of unmasked faces; then the sum of face quality = size × frontalness (landmark symmetry) × sharpness (Laplacian variance of the face box) × detector confidence; penalise faces cut by the frame edge and motion blur. Ties: prefer frames nearer 10–50 % of the duration.
7. **No faces:** fall back to the R1c poster rule (10 %, skip dark frames).
8. **Output:** poster as in R1c (short side 270 px), plus `poster.json` with the chosen time, N, face count, unmasked count and algorithm version. Bump the sidecar version so existing posters are regenerated in the background once. Keep the 8 MB storyboard cap; the face pass must finish within about 60 s CPU for a 10-minute 1080p video (report the real time).
9. **Privacy:** nothing leaves the PC; store no face crops, embeddings or identities; log only counts and timing.

## 3. Tests

- Unit tests with a fake detector: scoring rules (all-visible beats bigger single face; unmasked preferred when present; masked accepted when never removed; edge-cut penalty; no-face fallback), people-count estimate, version bump triggers regeneration, GPU gate.
- Integration on generated or licence-clear sample clips (no private videos in Git): one person, two people, one masked person, one person who removes the mask. If a real model is needed, skip the test cleanly when the model file is absent so CI passes offline.
- Do **not** read the owner's real home or library (AGENTS.md). Use only generated or licence-clear clips in an isolated home. After the designer's review the operator restarts the real service, which regenerates the posters itself, and reports the chosen times from each `poster.json`.
- `ruff check`, `ruff format --check`, `uv run pyright`, CI CPU pytest, node tests, desktop E2E.

## 4. Allowed files

`src/videoenhancer/remote/**`, `tests/**`, `docs/REMOTE.md`, `.ai/LAST_REPORT.md` (and `pyproject.toml`/`uv.lock` only after the operator has stopped the service and resumed you).

## 5. Done when

Sections 2 and 3 pass, the diff contains only allowed files, and the report lists test counts, timing for a 10-minute 1080p video, the mask-signal accuracy, disk baseline and growth, and owner re-check steps.

## 6. Operator after the commit (after designer review)

`ve remote restart`, then `ve remote status`, and report how many posters were regenerated after 10 minutes and the chosen time, N, face count and unmasked count from each real `poster.json` (read-only).
