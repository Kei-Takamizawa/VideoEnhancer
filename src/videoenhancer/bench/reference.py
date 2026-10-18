"""Whole-pipeline reference deltas for verified installed alternatives."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from videoenhancer import proc
from videoenhancer.config import executable, get_home
from videoenhancer.media.analyze import analyze
from videoenhancer.models.registry import C1, RIFE, ModelRegistry, record_models
from videoenhancer.pipeline.runner import process_segment


def calibrate_references(
    folder: Path,
    gpu: str,
    backend: str,
    progress: Callable[[str, float], None] | None = None,
) -> dict[str, Any]:
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "reference.mp4"
    proc.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=720x1280:rate=30",
            "-frames:v",
            "150",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads",
            "2",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    analysis = analyze(source, backend=backend)
    registry = ModelRegistry()
    results: dict[str, Any] = {}
    installed = registry.list_models()
    total = sum(
        3 if model.get("architecture") == "drunet" else 1
        for model in installed
        if model["weights_verified"] and model["task"] in {"restore", "interpolate", "size"}
    )
    completed = 0
    tasks = [
        (model, strength, size)
        for model in installed
        if model["weights_verified"] and model["task"] in {"restore", "interpolate", "size"}
        for strength in (
            ("light", "medium", "strong") if model.get("architecture") == "drunet" else ("medium",)
        )
        for size in ((1080, 1440) if model["id"] in {C1, RIFE} else (1080,))
    ]
    total = len(tasks)
    for model, strength, size in tasks:
        if progress:
            progress(
                f"Reference pipelines: {model['id']} ({strength}, {size}p)",
                65 + 25 * completed / max(1, total),
            )
        completed += 1
        mode = "fast" if model["task"] == "interpolate" else "standard"
        key = {"restore": "restore_model", "interpolate": "interp_model", "size": "size_model"}[
            model["task"]
        ]
        settings = dict(
            preset=mode,
            backend=backend,
            short_side=size,
            fps="2x",
            codec="hevc",
            restore_strength=strength,
        )
        settings[key] = model["id"]
        output = folder / f"{model['id']}-{strength}-{size}.mp4"
        try:
            identity = registry.snapshot(model["id"], model["task"], download=False)
            job = {
                **analysis,
                "input": {"path": str(source)},
                "settings": settings,
                "models": record_models(settings, get_home(), analysis["media"]),
            }
            started = time.perf_counter()
            stats = process_segment(job, dict(index=0, start=0, end=150), output, lambda: False)
            seconds = time.perf_counter() - started
            results[f"{model['id']}:{strength}" + (f":{size}" if size != 1080 else "")] = dict(
                gpu=gpu,
                input="720x1280 at 30 fps, 150 frames",
                output=f"{size}x{size * 16 // 9} at 60 fps",
                mode=mode,
                fps=150 / seconds,
                seconds=seconds,
                identity=identity,
                output_pixels=size * (size * 16 // 9),
                stats=stats,
            )
        except Exception as error:
            results[f"{model['id']}:{strength}" + (f":{size}" if size != 1080 else "")] = dict(
                status="failed", reason=str(error)
            )
        finally:
            output.unlink(missing_ok=True)
    # Defaults are included even when alternatives use a different category.
    for default in (C1, RIFE):
        if f"{default}:medium" not in results:
            results[f"{default}:medium"] = dict(
                status="failed", reason="Default model is not installed."
            )
    return results


def reference_size_points(profile: dict[str, Any]) -> dict[str, list[dict[str, float]]]:
    """Account for whole-pipeline geometry costs absent from isolated stage timings."""
    from videoenhancer.estimate.model import predict_segment

    points: dict[str, list[dict[str, float]]] = {"standard": [], "fast": []}
    references = profile.get("reference_pipelines", {})
    bare = {**profile, "pipeline_size_points": {}, "startup_by_preset": {"standard": 0, "fast": 0}}
    for preset, model in (("standard", C1), ("fast", RIFE)):
        for size in (1080, 1440):
            reference = references.get(f"{model}:medium" + (f":{size}" if size != 1080 else ""), {})
            if not reference.get("seconds") or not reference.get("stats"):
                continue
            stats = reference["stats"]
            startup = sum(
                float(stats.get(name, 0))
                for name in (
                    "decoder_open_seconds",
                    "model_loading_seconds",
                    "weight_verification_seconds",
                    "cuda_initialization_seconds",
                    "first_memory_sample_seconds",
                )
            )
            media = dict(
                width=720,
                height=1280,
                display_width=720,
                display_height=1280,
                cfr_fps="30",
                frame_count=150,
            )
            settings = dict(
                preset=preset,
                backend=profile.get("backend", "cuda"),
                short_side=size,
                codec="hevc",
                fps="2x",
            )
            predicted = predict_segment(media, settings, 150, bare)
            points[preset].append(
                dict(
                    pixels=float(size * (size * 16 // 9)),
                    factor=max(0.01, (reference["seconds"] - startup) / max(0.001, predicted)),
                )
            )
    return points
