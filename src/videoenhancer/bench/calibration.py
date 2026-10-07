"""Measure installed adapters with their verified model identities."""

from __future__ import annotations

import statistics
import time
from fractions import Fraction
from typing import Any

import torch

from videoenhancer.models.registry import ModelRegistry
from videoenhancer.pipeline.stages import FrameBatch


def calibrate_models(
    registry: ModelRegistry | None = None,
    *,
    backend: str = "cuda",
    restore_size: tuple[int, int] = (720, 1280),
    interpolate_size: tuple[int, int] = (1080, 1920),
    repeats: int = 3,
) -> dict[str, Any]:
    """Time complete stage calls, including their parameter transfers, after warmup."""
    if repeats < 1:
        raise ValueError("Calibration repeats must be positive.")
    registry = registry or ModelRegistry()
    results: dict[str, Any] = {}
    for installed in registry.list_models():
        model_id, task = installed["id"], installed["task"]
        entry: dict[str, Any] = {"task": task, "backend": backend, "status": "failed"}
        results[model_id] = entry
        stage = batch = frames = None
        try:
            entry["identity"] = registry.snapshot(model_id, task)
            stage = registry.create_stage(model_id, task, {"backend": backend}, Fraction(30), set())
            width, height = restore_size if task == "restore" else interpolate_size
            if width <= 0 or height <= 0:
                raise ValueError("Calibration geometry must be positive.")
            length = int(getattr(stage, "clip_length", installed.get("clip_length", 1)))
            overlap = int(getattr(stage, "clip_overlap", installed.get("clip_overlap", 0)))
            count = (length if installed["temporal"] else 2) if task == "restore" else 9
            dtype = torch.float16 if backend == "cuda" else torch.float32
            generator = torch.Generator(device=backend).manual_seed(1234)
            frames = torch.rand(
                (count, 3, height, width), device=backend, dtype=dtype, generator=generator
            )
            batch = FrameBatch(
                frames, tuple(Fraction(i, 30) for i in range(count)), tuple(range(count))
            )
            started = time.perf_counter()
            stage.load()
            entry["load_seconds"] = time.perf_counter() - started
            with torch.inference_mode():
                stage.warmup(batch)
            if backend == "cuda":
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
            timings = []
            for _ in range(repeats):
                if backend == "cuda":
                    torch.cuda.synchronize()
                started = time.perf_counter()
                with torch.inference_mode():
                    result = stage.process(batch)
                if backend == "cuda":
                    torch.cuda.synchronize()
                timings.append(time.perf_counter() - started)
                del result
            # The terminal duplicated source frame does not run RIFE inference.
            processed = count if task == "restore" else count - 1
            median = statistics.median(timings)
            entry.update(
                status="measured",
                width=width,
                height=height,
                batch_frames=count,
                processed_frames_or_pairs=processed,
                clip_length=length,
                clip_overlap=overlap,
                single_frame=bool(getattr(stage, "single_frame", False)),
                precision=installed["precision"],
                effective_precision=installed["precision"] if backend == "cuda" else "fp32",
                seconds_samples=timings,
                median_seconds=median,
                processed_frames_or_pairs_per_second=processed / median,
                seconds_per_pixel_frame=median / (width * height * processed),
                torch_reserved_peak_bytes=torch.cuda.max_memory_reserved()
                if backend == "cuda"
                else 0,
            )
        except Exception as exc:
            entry["reason"] = str(exc)
        finally:
            batch = frames = None
            if stage is not None:
                stage.release()
            if backend == "cuda":
                torch.cuda.empty_cache()
    return results
