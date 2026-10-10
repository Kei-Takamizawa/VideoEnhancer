"""Sequential model comparisons sharing one source index and range analysis."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from videoenhancer.config import executable, get_home
from videoenhancer.media.decode import IndexedDecoder
from videoenhancer.media.encode import Encoder
from videoenhancer.media.source_index import analyze_range, source_index
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.models.registry import ModelRegistry, record_models
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.pipeline.stages import FrameBatch, ResizeStage
from videoenhancer.proc import run
from videoenhancer.service.settings import write_json


def render_compare(value: dict[str, Any], folder: Path) -> dict[str, Any]:
    source = Path(value["file"]).resolve(strict=True)
    settings = {**value["settings"], "codec": "h264", "lossless": False}
    registry = ModelRegistry()
    index = source_index(source)
    rate = Fraction(index["media"]["cfr_fps"])
    duration = len(index["cfr_map"]) / float(rate)
    seconds = value.get("seconds", 5)
    start = value.get("start")
    if start is None:
        start = max(0, (duration - seconds) / 2)
    first = round(start * float(rate))
    last = min(len(index["cfr_map"]), first + round(seconds * float(rate)))
    if first < 0 or first >= last:
        raise ValueError("Choose a range inside the video.")
    analysis = analyze_range(
        source,
        index,
        first,
        last,
        settings["backend"],
        context_frames=2
        * max(
            [
                int(settings.get("clip_length", 15)),
                *[
                    int(registry.manifest(model_id).get("clip_length", 1))
                    for model_id in value["models"]
                ],
            ]
        ),
    )
    output_fps = output_rate(settings, analysis["media"])
    result: dict[str, Any] = dict(
        start_seconds=first / float(rate),
        seconds=(last - first) / float(rate),
        output_fps=float(output_fps),
        items=[],
    )

    def publish(phase: str, percent: float) -> None:
        write_json(folder / "progress.json", dict(phase=phase, percent=percent, result=result))

    def url(name: str) -> str:
        return f"/v1/operations/{folder.name}/files/{name}"

    width, height = output_size(settings, analysis["media"])
    original = folder / "original-preview.mp4"
    encoder = Encoder(original, width, height, output_fps, "h264", "cpu", analysis["media"], False)
    resize = ResizeStage(width, height)
    decoder = IndexedDecoder(source, analysis["media"], "cpu", analysis)
    try:
        for i, frame in zip(
            range(first, last),
            decoder.frames(analysis["cfr_map"][first:last], lambda: False),
            strict=True,
        ):
            picture = resize.process(
                FrameBatch(torch.stack([frame]), (Fraction(i) / rate,), (i,))
            ).frames[0]
            for _ in range(int(output_fps / rate)):
                encoder.write(picture)
        encoder.finish()
    except BaseException:
        encoder.abort()
        raise
    finally:
        decoder.close()
    result["original"] = url("original")
    publish("Original ready", 0)
    for position, model_id in enumerate(value["models"]):
        model = registry.manifest(model_id)
        key = "restore_model" if model["task"] == "restore" else "interp_model"
        chosen = {**settings, key: model_id}
        job = {
            **analysis,
            "id": "compare",
            "input": {"path": str(source)},
            "settings": chosen,
            "models": record_models(chosen, get_home(), analysis["media"]),
        }
        segment = dict(index=0, start=first, end=last)

        def progress(
            data: dict[str, Any], model: dict[str, Any] = model, position: int = position
        ) -> None:
            fraction = data.get("frames_done", 0) / (last - first)
            publish(
                f"Making {model.get('catalog', {}).get('title', model['display_name'])}",
                100 * (position + fraction) / len(value["models"]),
            )

        raw = folder / f"{model_id}-raw.mp4"
        stats = process_segment(job, segment, raw, lambda: False, progress=progress)
        target = folder / f"{model_id}-preview.mp4"
        run(
            [
                executable("ffmpeg"),
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(raw),
                "-an",
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                "-threads",
                "2",
                str(target),
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
        raw.unlink()
        result["items"].append(
            dict(
                id=model_id,
                name=model.get("catalog", {}).get("title", model["display_name"]),
                preview=url(model_id),
                fps=stats["fps"],
                projected_whole_file_seconds=len(index["cfr_map"]) / stats["fps"],
            )
        )
        publish("Preview ready", 100 * (position + 1) / len(value["models"]))
    return result
