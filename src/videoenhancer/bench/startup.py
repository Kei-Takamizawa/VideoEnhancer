"""Measure actual cold and reused ProcessExecutor startup at reference geometry."""

import statistics
from pathlib import Path
from typing import Any

from videoenhancer import proc
from videoenhancer.config import executable, get_home
from videoenhancer.media.analyze import analyze
from videoenhancer.models.registry import record_models
from videoenhancer.schedule.controller import ProcessExecutor, SystemClock


def calibrate_startup(folder: Path, backend: str) -> dict[str, Any]:
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "startup.mp4"
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
            "45",
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
    terms = {}
    for preset in ("standard", "fast"):
        settings = dict(preset=preset, backend=backend, short_side=1080, fps="2x", codec="hevc")
        job = {
            **analysis,
            "input": {"path": str(source)},
            "settings": settings,
            "models": record_models(settings, get_home(), analysis["media"]),
        }
        samples = []
        executor = ProcessExecutor(SystemClock(), reuse=True)
        try:
            for index in range(3):
                output = folder / f"{preset}-{index}.mp4"
                result = executor.run(
                    job,
                    dict(index=index, start=index * 15, end=(index + 1) * 15),
                    output,
                    lambda: False,
                    batch_size=2,
                )
                if result.status != "done" or not result.stats or result.stats.get("spilled"):
                    raise ValueError(f"Startup calibration failed: {preset} part {index}: {result}")
                expected = "cold" if index == 0 else "warm"
                if result.stats.get("startup_kind") != expected:
                    raise ValueError("Startup calibration did not reuse its worker.")
                samples.append(float(result.stats["per_part_startup_seconds"]))
                output.unlink(missing_ok=True)
        finally:
            executor.close()
        terms[preset] = {"cold": samples[0], "warm": statistics.median(samples[1:])}
    return terms
