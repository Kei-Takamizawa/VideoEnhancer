"""Context-aware excerpts and labeled comparisons without a GUI."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from videoenhancer.config import executable, get_home
from videoenhancer.media.decode import IndexedDecoder, choose_backend
from videoenhancer.media.encode import Encoder
from videoenhancer.media.mux import _run
from videoenhancer.media.source_index import analyze_range, source_index
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.models.registry import record_models
from videoenhancer.pipeline.inline_quality import aggregate_quality
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
    settings_patch: dict[str, Any] | None = None,
    source_manifest: dict[str, Any] | None = None,
    progress: Callable[[str, float], None] | None = None,
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
    index_started = time.perf_counter()
    analysis = source_index(source.resolve(), source_manifest, progress)
    index_seconds = time.perf_counter() - index_started
    media = analysis["media"]
    rate = Fraction(media["cfr_fps"])
    total_frames = len(analysis["cfr_map"])
    duration = total_frames / float(rate)
    offset = max(0.0, (duration - seconds) / 2) if start is None else start
    first = round(offset * float(rate))
    last = min(total_frames, first + max(1, round(seconds * float(rate))))
    if first >= total_frames:
        raise ValueError("Trial start is beyond the end of the video.")
    if progress:
        progress("Checking the preview range…", 0)
    analysis = analyze_range(
        source,
        analysis,
        first,
        last,
        backend,
        context_frames=2 * int((settings_patch or {}).get("clip_length", 15)),
    )
    settings: dict[str, Any] = dict(
        preset=preset, backend=backend, short_side=short_side, fps="2x", codec="h264", lossless=True
    )
    if settings_patch:
        settings.update(settings_patch)
        settings.update(preset=preset, backend=backend)
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
    if progress:
        progress("Processing", 0)

    def render_progress(value: dict[str, Any]) -> None:
        if progress and "frames_done" in value:
            progress(value["step"], min(100.0, 100 * value["frames_done"] / (last - first)))

    stats = process_segment(
        job,
        job["segments"][0],
        enhanced,
        lambda: False,
        progress=render_progress if progress else None,
    )
    width, height = output_size(settings, media)
    original = destination / "original.mp4"
    encoder = Encoder(original, width, height, rate, "h264", "cpu", media, True)
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
        encoder.finish()
    except BaseException:
        encoder.abort()
        raise
    finally:
        decoder.close()
    job["segments"][0]["stats"] = stats
    metrics = aggregate_quality(job)
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
        "output_fps": float(output_rate(settings, media)),
        "start_seconds": first / float(rate),
        "seconds": (last - first) / float(rate),
        "input_frames": last - first,
        "whole_file_frames": total_frames,
        "index_seconds": index_seconds,
        "range_analysis_seconds": analysis["analysis_seconds"],
        "analysis_span": analysis.get("analysis_span"),
        "range_fallback": analysis.get("range_fallback"),
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
