"""Whole-pipeline reference deltas for verified installed alternatives."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from videoenhancer import proc
from videoenhancer.config import executable, get_home
from videoenhancer.media.analyze import analyze
from videoenhancer.models.registry import C1, RIFE, ModelRegistry, record_models
from videoenhancer.pipeline.runner import process_segment


def calibrate_references(folder: Path, gpu: str, backend: str) -> dict[str, Any]:
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
    for model in registry.list_models():
        if not model["weights_verified"] or model["task"] not in {"restore", "interpolate", "size"}:
            continue
        for strength in (
            ("light", "medium", "strong") if model.get("architecture") == "drunet" else ("medium",)
        ):
            mode = "fast" if model["task"] == "interpolate" else "standard"
            key = {"restore": "restore_model", "interpolate": "interp_model", "size": "size_model"}[
                model["task"]
            ]
            settings = dict(
                preset=mode,
                backend=backend,
                short_side=1080,
                fps="2x",
                codec="hevc",
                restore_strength=strength,
            )
            settings[key] = model["id"]
            output = folder / f"{model['id']}-{strength}.mp4"
            try:
                identity = registry.snapshot(model["id"], model["task"], download=False)
                job = {
                    **analysis,
                    "input": {"path": str(source)},
                    "settings": settings,
                    "models": record_models(settings, get_home(), analysis["media"]),
                }
                started = time.perf_counter()
                process_segment(job, dict(index=0, start=0, end=150), output, lambda: False)
                seconds = time.perf_counter() - started
                results[f"{model['id']}:{strength}"] = dict(
                    gpu=gpu,
                    input="720x1280 at 30 fps, 150 frames",
                    output="1080x1920 at 60 fps",
                    mode=mode,
                    fps=150 / seconds,
                    seconds=seconds,
                    identity=identity,
                )
            except Exception as error:
                results[f"{model['id']}:{strength}"] = dict(status="failed", reason=str(error))
            finally:
                output.unlink(missing_ok=True)
    # Defaults are included even when alternatives use a different category.
    for default in (C1, RIFE):
        if f"{default}:medium" not in results:
            results[f"{default}:medium"] = dict(
                status="failed", reason="Default model is not installed."
            )
    return results
