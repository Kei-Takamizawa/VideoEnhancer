"""Context-aware excerpts and labeled comparisons without a GUI."""

from __future__ import annotations

import json
import math
import tempfile
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from videoenhancer.config import executable, get_home
from videoenhancer.media.analyze import analyze
from videoenhancer.media.decode import IndexedDecoder, choose_backend
from videoenhancer.media.encode import Encoder
from videoenhancer.media.mux import _run
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.models.registry import record_models
from videoenhancer.pipeline.quality import measure_quality
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.pipeline.stages import FrameBatch, ResizeStage


def run_trial(
    source: Path,
    *,
    start: float | None = None,
    seconds: float = 5,
    preset: str = "standard",
    restore_model: str | None = None,
    interp_model: str | None = None,
    out: Path | None = None,
    backend: str = "auto",
    short_side: str | int = 1080,
) -> dict[str, Any]:
    if (
        not math.isfinite(seconds)
        or seconds <= 0
        or (start is not None and (not math.isfinite(start) or start < 0))
    ):
        raise ValueError("Trial seconds must be positive; start must be nonnegative and finite.")
    if preset not in {"fast", "standard"}:
        raise ValueError("Trial preset must be fast or standard.")
    destination = (out or get_home() / "trials" / time.strftime("%Y%m%d-%H%M%S")).resolve()
    repository = Path(__file__).resolve().parents[2]
    if destination.is_relative_to(repository):
        raise ValueError("Trial output must be outside the repository.")
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("original.mp4", "enhanced.mp4", "comparison_split.mp4", "report.json"):
        if (destination / name).exists():
            raise ValueError(f"Trial output already exists: {name}; choose a fresh directory.")
    backend = choose_backend(backend)
    analysis = analyze(source, backend=backend)
    media = analysis["media"]
    rate = Fraction(media["cfr_fps"])
    total_frames = len(analysis["cfr_map"])
    duration = total_frames / float(rate)
    offset = max(0.0, (duration - seconds) / 2) if start is None else start
    first = round(offset * float(rate))
    last = min(total_frames, first + max(1, round(seconds * float(rate))))
    if first >= total_frames:
        raise ValueError("Trial start is beyond the end of the video.")
    settings: dict[str, Any] = dict(
        preset=preset, backend=backend, short_side=short_side, fps="2x", codec="h264", lossless=True
    )
    if restore_model:
        settings["restore_model"] = restore_model
    if interp_model:
        settings["interp_model"] = interp_model
    job = {
        **analysis,
        "id": "trial",
        "input": {"path": str(source.resolve())},
        "settings": settings,
        "models": record_models(settings, get_home(), media),
        "segments": [{"index": 0, "start": first, "end": last}],
    }
    enhanced = destination / "enhanced.mp4"
    stats = process_segment(job, job["segments"][0], enhanced, lambda: False)
    width, height = output_size(settings, media)
    native_width, native_height = int(media["display_width"]), int(media["display_height"])
    original = destination / "original.mp4"
    with tempfile.TemporaryDirectory(prefix="ve-trial-", dir=destination) as temporary:
        native = Path(temporary) / "native.mp4"
        encoder = Encoder(original, width, height, rate, "h264", "cpu", media, True)
        reference_encoder = Encoder(
            native, native_width, native_height, rate, "h264", "cpu", media, True
        )
        resize = ResizeStage(width, height)
        decoder = IndexedDecoder(source, media, "cpu", job)
        try:
            for index, frame in zip(
                range(first, last),
                decoder.frames(job["cfr_map"][first:last], lambda: False),
                strict=True,
            ):
                batch = FrameBatch(torch.stack([frame]), (Fraction(index) / rate,), (index,))
                encoder.write(resize.process(batch).frames[0])
                reference_encoder.write(frame)
            encoder.finish()
            reference_encoder.finish()
        except BaseException:
            encoder.abort()
            reference_encoder.abort()
            raise
        finally:
            decoder.close()
        relative_stats = {**stats, "clip_joints": [frame - first for frame in stats["clip_joints"]]}
        metric_job = {
            **job,
            "input": {"path": str(native)},
            "scene_cuts": [cut - first for cut in job.get("scene_cuts", []) if first <= cut < last],
            "segments": [{"start": 0, "end": last - first, "stats": relative_stats}],
        }
        metrics = measure_quality(metric_job, enhanced)
    midpoint = (width // 2) // 2 * 2
    if midpoint < 2:
        raise ValueError("Trial video is too narrow for a split comparison.")
    output_fps = str(output_rate(settings, media))
    font = ""
    windows_font = Path("C:/Windows/Fonts/arial.ttf")
    if windows_font.exists():
        font = "fontfile='C\\:/Windows/Fonts/arial.ttf':"
    graph = (
        f"[0:v]fps={output_fps},crop={midpoint}:{height}:0:0[l];"
        f"[1:v]crop={width - midpoint}:{height}:{midpoint}:0[r];"
        "[l][r]hstack=inputs=2:shortest=1,"
        f"drawbox=x={midpoint - 1}:y=0:w=2:h=ih:color=white:t=fill,"
        f"drawtext={font}text=Original:x=12:y=12:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6,"
        f"drawtext={font}text=Enhanced:x={midpoint + 12}:y=12:fontsize=24:"
        "fontcolor=white:box=1:boxcolor=black@0.6[v]"
    )
    _run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(original),
            "-i",
            str(enhanced),
            "-filter_complex_threads",
            "2",
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(destination / "comparison_split.mp4"),
        ],
        None,
    )
    report = {
        "preset": preset,
        "backend": backend,
        "start_seconds": first / float(rate),
        "seconds": (last - first) / float(rate),
        "input_frames": last - first,
        "whole_file_frames": total_frames,
        "models": job["models"],
        "pipeline": stats,
        "metrics": metrics,
        "projected_whole_file_seconds": total_frames / stats["fps"],
        "paths": {
            name: str(destination / name)
            for name in ("original.mp4", "enhanced.mp4", "comparison_split.mp4", "report.json")
        },
    }
    (destination / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
