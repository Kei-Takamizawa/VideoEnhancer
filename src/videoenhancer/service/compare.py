"""Sequential model comparisons sharing one source index and range analysis."""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from videoenhancer.config import executable, get_home
from videoenhancer.media.decode import IndexedDecoder, choose_backend
from videoenhancer.media.encode import Encoder
from videoenhancer.media.source_index import analyze_range, source_identity, source_index
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.models.registry import ModelRegistry, record_models, selected_models
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.pipeline.stages import FrameBatch, ResizeStage
from videoenhancer.proc import run
from videoenhancer.service.compare_cache import CompareState
from videoenhancer.service.settings import write_json


def compare_manifest(registry: ModelRegistry, model_id: str) -> dict[str, Any]:
    if model_id == "standard-resize":
        return dict(
            id=model_id,
            task="size",
            display_name="Standard resize",
            catalog={"title": "Standard resize"},
            weights={"sha256": "0" * 64},
        )
    return registry.manifest(model_id)


def suggested_range(
    source: Path, analysis: dict[str, Any] | None = None, index: dict[str, Any] | None = None
) -> dict[str, Any]:
    index = index or source_index(source, analysis)
    rate = float(Fraction(index["media"]["cfr_fps"]))
    count = len(index["cfr_map"])
    width = min(count, round(5 * rate))
    scores = (analysis or {}).get("motion_scores", [])
    if (
        analysis
        and analysis.get("input")
        and any(analysis["input"].get(k) != v for k, v in source_identity(source).items())
    ):
        scores = []
    if scores:
        # Score each source frame once, then map it to the existing CFR grid.
        by_source = {s["frame"]: max(0, float(s["delta"])) for s in scores}
        # Scene cuts are CFR frame indices; motion scores refer to source frames.
        excluded = {
            frame
            for cut in (analysis or {}).get("scene_cuts", [])
            for frame in range(max(0, cut - 2), min(count, cut + 3))
        }
        values = [
            0 if i in excluded else by_source.get(frame, 0)
            for i, frame in enumerate(index["cfr_map"])
        ]
        total = sum(values[:width])
        best, start = total, 0
        for first in range(1, count - width + 1):
            total += values[first + width - 1] - values[first - 1]
            if total > best:
                best, start = total, first
        reason = "Most motion in the available analysis, excluding scene cuts."
    else:
        start = max(0, (count - width) // 2)
        reason = "Middle of the video; motion analysis is unavailable."
    return dict(
        start=start / rate,
        seconds=width / rate,
        first_frame=start,
        last_frame=start + width,
        reason=reason,
    )


def cache_key(
    source: Path,
    first: int,
    last: int,
    settings: dict[str, Any],
    model_id: str,
    registry: ModelRegistry,
) -> str:
    selected = selected_models(settings)
    models = {
        task: {key: value for key, value in registry.manifest(name).items() if key != "catalog"}
        for task, name in selected.items()
    }
    identity = dict(
        source=source_identity(source),
        cfr_range=[first, last],
        settings=settings,
        model_id=model_id,
        model_sha256=compare_manifest(registry, model_id)["weights"]["sha256"]
        if model_id != "original"
        else None,
        stage_sha256=models,
    )
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def reuse_preview(folder: Path, key: str, name: str) -> dict[str, Any] | None:
    for metadata in folder.parent.glob("*/cache.json"):
        if metadata.parent == folder:
            continue
        if (
            metadata.is_symlink()
            or metadata.parent.is_symlink()
            or not metadata.parent.resolve().is_relative_to(folder.parent.resolve())
        ):
            continue
        try:
            records = json.loads(metadata.read_text(encoding="utf-8"))
            record = records.get(key)
            if not record:
                continue
            candidate = metadata.parent / record["filename"]
            if (
                candidate.is_symlink()
                or not candidate.resolve().is_relative_to(metadata.parent.resolve())
                or not candidate.is_file()
            ):
                continue
            temporary = folder / f"{name}.copying"
            shutil.copyfile(candidate, temporary)
            temporary.replace(folder / f"{name}-preview.mp4")
            return record
        except (OSError, ValueError, KeyError):
            continue
    return None


def discard_incomplete(folder: Path) -> None:
    """Keep only previews committed to the cache after encoding completed."""
    try:
        records = json.loads((folder / "cache.json").read_text(encoding="utf-8"))
        completed = {record["filename"] for record in records.values()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        completed = set()
    for path in folder.glob("*.mp4"):
        if path.name not in completed:
            path.unlink(missing_ok=True)
    for path in folder.glob("*.copying"):
        path.unlink(missing_ok=True)


def compare_input(value: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any], int, int]:
    from videoenhancer.jobs.store import JobStore

    source = Path(value["file"]).resolve(strict=True)
    settings = {**value["settings"], "codec": "h264", "lossless": False}
    analysis = JobStore().load(value["job_id"]) if value.get("job_id") else None
    if analysis is None:
        identity = source_identity(source)
        analysis = next(
            (
                job
                for job in JobStore().list_jobs()
                if all(job.get("input", {}).get(k) == v for k, v in identity.items())
            ),
            None,
        )
    index = source_index(source, analysis)
    from videoenhancer.jobs.checks import job_support_reason

    unsupported = job_support_reason({"media": index["media"], "settings": settings})
    if unsupported:
        raise ValueError(unsupported)
    rate = float(Fraction(index["media"]["cfr_fps"]))
    seconds = value.get("seconds", 5)
    start = value.get("start")
    if start is None:
        start = (
            suggested_range(source, analysis, index)["start"]
            if seconds == 5
            else max(0, (len(index["cfr_map"]) / rate - seconds) / 2)
        )
    first = round(start * rate)
    last = min(len(index["cfr_map"]), first + round(seconds * rate))
    if first < 0 or first >= last:
        raise ValueError("Choose a range inside the video.")
    return source, settings, index, first, last


def prime_cached(value: dict[str, Any], folder: Path) -> dict[str, Any] | None:
    """Publish cache hits immediately, before acquiring the GPU work lease."""
    if not any(folder.parent.glob("*/cache.json")):
        return None
    source, settings, index, first, last = compare_input(value)
    registry = ModelRegistry()
    rate = float(Fraction(index["media"]["cfr_fps"]))
    result: dict[str, Any] = dict(
        start_seconds=first / rate,
        seconds=(last - first) / rate,
        output_fps=float(output_rate(settings, index["media"])),
        items=[],
    )
    keys = {}
    for name in ["original", *value["models"]]:
        chosen = dict(settings)
        if name != "original":
            model = compare_manifest(registry, name)
            key = {"restore": "restore_model", "interpolate": "interp_model", "size": "size_model"}[
                model["task"]
            ]
            if name == "standard-resize":
                chosen.pop(key, None)
            else:
                chosen[key] = name
        digest = cache_key(source, first, last, chosen, name, registry)
        record = reuse_preview(folder, digest, name)
        if not record:
            continue
        keys[digest] = dict(record, filename=f"{name}-preview.mp4")
        url = f"/v1/operations/{folder.name}/files/{name}"
        if name == "original":
            result.update(original=url, original_reused=True)
        else:
            result["items"].append(
                dict(
                    id=name,
                    name=model.get("catalog", {}).get("title", model["display_name"]),
                    preview=url,
                    fps=record["fps"],
                    projected_whole_file_seconds=whole_file_estimate(index, chosen),
                    reused=True,
                )
            )
    if keys:
        write_json(folder / "cache.json", keys)
        return result
    return None


def whole_file_estimate(index: dict[str, Any], settings: dict[str, Any]) -> float | None:
    from videoenhancer.estimate import estimate_job
    from videoenhancer.jobs.store import load_machine_profile

    registry = ModelRegistry()
    identities = {}
    for task, model_id in selected_models(settings, index["media"]).items():
        try:
            identities[task] = registry.snapshot(model_id, task, download=False)
        except ValueError:
            pass
    estimate = estimate_job(
        {
            "media": index["media"],
            "settings": settings,
            "segments": [{"start": 0, "end": len(index["cfr_map"])}],
            "machine_profile": load_machine_profile(
                get_home(), backend=settings["backend"], models=identities
            ),
        }
    )
    return None if estimate.unknown_models else estimate.seconds


def render_compare(
    value: dict[str, Any], folder: Path, state: CompareState | None = None
) -> dict[str, Any]:
    started = float(
        value.get("_compare_requested_at", value.get("_gpu_admitted_at", time.perf_counter()))
    )
    prepared = time.perf_counter()
    source, settings, index, first, last = compare_input(value)
    input_seconds = time.perf_counter() - prepared
    registry = ModelRegistry()
    rate = Fraction(index["media"]["cfr_fps"])
    analyzed = time.perf_counter()
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
                    int(compare_manifest(registry, model_id).get("clip_length", 1))
                    for model_id in value["models"]
                ],
            ]
        ),
    )
    info = source.stat()
    range_key = (str(source), info.st_size, info.st_mtime_ns, first, last)

    def decoded_range(indices: list[int], abort: Any, backend: str):
        def decode():
            decoder = IndexedDecoder(source, analysis["media"], backend, analysis)
            try:
                yield from decoder.frames(indices, abort)
            finally:
                decoder.close()

        if state is None:
            yield from decode()
        else:
            media = analysis["media"]
            estimated = len(indices) * media["display_width"] * media["display_height"] * 3 * 2
            yield from state.decoded.frames(
                range_key,
                ((backend, analysis.get("decoder", "auto")), tuple(indices)),
                estimated,
                decode,
                backend,
            )

    output_fps = output_rate(settings, analysis["media"])
    result: dict[str, Any] = dict(
        start_seconds=first / float(rate),
        seconds=(last - first) / float(rate),
        output_fps=float(output_fps),
        items=[],
        model_progress={},
        profile=dict(
            gpu_wait_seconds=float(value.get("_gpu_wait_seconds", 0)),
            input_index_seconds=input_seconds,
            range_analysis_seconds=time.perf_counter() - analyzed,
        ),
    )
    cache: dict[str, Any] = {}
    # Match the model pipeline's CPU thread budget before the Original resize.
    torch.set_num_threads(2)

    def remember(key: str, name: str, fps: float | None = None) -> None:
        cache[key] = dict(filename=f"{name}-preview.mp4", fps=fps)
        write_json(folder / "cache.json", cache)

    original_future = None
    original_collected = False

    def collect_original() -> None:
        nonlocal original_collected
        if original_collected or original_future is None or not original_future.done():
            return
        original_profile, original_look = original_future.result()
        result["original"] = url("original")
        result["original_reused"] = reused is not None
        result["profile"]["original_preview_seconds"] = original_profile
        result["first_looks"].insert(0, original_look)
        remember(original_key, "original")
        original_collected = True

    def publish(phase: str, percent: float) -> None:
        collect_original()
        if result["first_looks"] and "time_to_first_tile_seconds" not in result:
            result["time_to_first_tile_seconds"] = time.perf_counter() - started
        write_json(folder / "progress.json", dict(phase=phase, percent=percent, result=result))

    def url(name: str) -> str:
        return f"/v1/operations/{folder.name}/files/{name}"

    width, height = output_size(settings, analysis["media"])
    original = folder / "original-preview.mp4"
    original_key = cache_key(source, first, last, settings, "original", registry)
    reused = reuse_preview(folder, original_key, "original")

    def prepare_original():
        original_started = time.perf_counter()
        if reused is None:
            encoder = Encoder(
                original, width, height, output_fps, "h264", "cpu", analysis["media"], False
            )
            resize = ResizeStage(width, height)
            try:
                for i, frame in zip(
                    range(first, last),
                    decoded_range(analysis["cfr_map"][first:last], lambda: False, "cpu"),
                    strict=True,
                ):
                    picture = resize.process(
                        FrameBatch(torch.stack([frame]), (Fraction(i) / rate,), (i,))
                    ).frames[0]
                    encoder.write_repeated(picture, int(output_fps / rate))
                encoder.finish()
            except BaseException:
                encoder.abort()
                raise
        return time.perf_counter() - original_started, first_look(original, "original")

    look_frame = min(7, last - first - 1) * int(output_fps / rate)

    def first_look(video: Path, name: str) -> dict[str, Any]:
        target = folder / f"{name}-first-look.png"
        run(
            [
                executable("ffmpeg"),
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(video),
                "-vf",
                f"select=eq(n\\,{look_frame})",
                "-frames:v",
                "1",
                str(target),
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
        return {
            "id": name,
            "image": f"/v1/operations/{folder.name}/stills/{name}",
            "seconds": time.perf_counter() - started,
            "frame": first + min(7, last - first - 1),
        }

    result["first_looks"] = []
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ve-original") as original_worker:
        original_future = original_worker.submit(prepare_original)
        for position, model_id in enumerate(value["models"]):
            model = compare_manifest(registry, model_id)
            key = {"restore": "restore_model", "interpolate": "interp_model", "size": "size_model"}[
                model["task"]
            ]
            chosen = {**settings, key: model_id}
            if model_id == "standard-resize":
                chosen.pop("size_model", None)
            model_key = cache_key(source, first, last, chosen, model_id, registry)
            reused_model = reuse_preview(folder, model_key, model_id)
            job = {
                **analysis,
                "id": "compare",
                "input": {"path": str(source)},
                "settings": chosen,
                "models": record_models(chosen, get_home(), analysis["media"]),
            }
            segment = dict(index=0, start=first, end=last)
            from videoenhancer.estimate import predict_segment
            from videoenhancer.jobs.store import load_machine_profile

            expected_seconds = predict_segment(
                analysis["media"], chosen, last - first, load_machine_profile(get_home())
            )

            def progress(
                data: dict[str, Any],
                model: dict[str, Any] = model,
                position: int = position,
                expected_seconds: float = expected_seconds,
            ) -> None:
                fraction = data.get("frames_done", 0) / (last - first)
                elapsed = float(data.get("elapsed_seconds", 0))
                result["model_progress"][model["id"]] = dict(
                    percent=min(100, 100 * fraction),
                    remaining_seconds=max(
                        0,
                        elapsed * (1 - fraction) / fraction
                        if fraction > 0 and elapsed > 0
                        else expected_seconds,
                    ),
                )
                publish(
                    f"Making {model.get('catalog', {}).get('title', model['display_name'])}",
                    100 * (position + fraction) / len(value["models"]),
                )

            if reused_model is not None:
                stats = {"fps": reused_model["fps"]}
                transcode_seconds = 0.0
            else:
                raw = folder / f"{model_id}-raw.mp4"
                published = False

                def observe(
                    frame: torch.Tensor,
                    index: int,
                    model_id: str = model_id,
                    position: int = position,
                ) -> None:
                    nonlocal published
                    if published or index != first * int(output_fps / rate) + look_frame:
                        return
                    target = folder / f"{model_id}-first-look.png"
                    rgb = (
                        frame.detach()
                        .float()
                        .clamp(0, 1)
                        .mul(255)
                        .round()
                        .to(torch.uint8)
                        .permute(1, 2, 0)
                        .contiguous()
                        .cpu()
                        .numpy()
                    )
                    run(
                        [
                            executable("ffmpeg"),
                            "-v",
                            "error",
                            "-nostdin",
                            "-y",
                            "-f",
                            "rawvideo",
                            "-pix_fmt",
                            "rgb24",
                            "-s:v",
                            f"{rgb.shape[1]}x{rgb.shape[0]}",
                            "-i",
                            "pipe:0",
                            "-frames:v",
                            "1",
                            str(target),
                        ],
                        input=rgb.tobytes(),
                        capture_output=True,
                        check=True,
                        timeout=120,
                    )
                    result["first_looks"].append(
                        dict(
                            id=model_id,
                            image=f"/v1/operations/{folder.name}/stills/{model_id}",
                            seconds=time.perf_counter() - started,
                            frame=first + min(7, last - first - 1),
                        )
                    )
                    published = True
                    publish("First look", 100 * position / len(value["models"]))

                extras: dict[str, Any] = {}
                if state is not None:
                    backend = choose_backend(chosen.get("backend", "auto"))
                    extras = dict(
                        session=state.models(job),
                        decoded_frames=lambda indices, abort, backend=backend: decoded_range(
                            indices, abort, backend
                        ),
                    )
                with contextlib.ExitStack() as transcodes:
                    streamed = None
                    if (
                        choose_backend(chosen.get("backend", "auto")) == "cuda"
                        and chosen.get("codec") == "h264"
                    ):
                        from videoenhancer.service.compare_stream import PreviewTranscode

                        streamed = PreviewTranscode(
                            folder / f"{model_id}-preview.mp4", output_fps, analysis["media"]
                        )
                        transcodes.callback(streamed.abort)
                        extras["encoded_packets"] = streamed
                    stats = process_segment(
                        job,
                        segment,
                        raw,
                        lambda: False,
                        progress=progress,
                        frame_observer=observe,
                        **extras,
                    )
                    if state is not None and any(
                        stats.get(k) for k in ("spilled", "oom_retries", "uncapped_re_runs")
                    ):
                        state.close()
                    target = folder / f"{model_id}-preview.mp4"
                    transcode_started = time.perf_counter()
                    if streamed is None:
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
                    else:
                        stats["stream_preview_wall_seconds"] = streamed.finish()
                        stats["stream_preview_packet_write_seconds"] = streamed.packet_write_seconds
                    raw.unlink()
                    transcode_seconds = time.perf_counter() - transcode_started
            result["items"].append(
                dict(
                    id=model_id,
                    name=model.get("catalog", {}).get("title", model["display_name"]),
                    preview=url(model_id),
                    fps=stats["fps"],
                    reused=reused_model is not None,
                    ready_seconds=time.perf_counter() - started,
                    projected_whole_file_seconds=None,
                    profile=dict(
                        model_load_seconds=stats.get("model_loading_seconds"),
                        decode_seconds=stats.get("decode_seconds"),
                        pipeline_timeline=stats.get("pipeline_timeline"),
                        inference_seconds=stats.get("stage_seconds"),
                        encode_seconds=stats.get("encode_seconds"),
                        preview_transcode_seconds=transcode_seconds,
                        preview_stream_wall_seconds=stats.get("stream_preview_wall_seconds"),
                        preview_packet_write_seconds=stats.get(
                            "stream_preview_packet_write_seconds"
                        ),
                        gpu_wait_seconds=result["profile"]["gpu_wait_seconds"],
                    ),
                )
            )
            remember(model_key, model_id, stats["fps"])
            result["model_progress"][model_id] = dict(percent=100, remaining_seconds=0)
            publish("Preview ready", 100 * (position + 1) / len(value["models"]))
            # Publish the playable tile before reading calibration and model files
            # for its optional whole-file estimate. Encoding and its bytes are unchanged.
            result["items"][-1]["projected_whole_file_seconds"] = whole_file_estimate(index, chosen)
            publish("Preview ready", 100 * (position + 1) / len(value["models"]))
        original_future.result()
        collect_original()
        publish("Preview ready", 100)
    result["total_seconds"] = time.perf_counter() - started
    if state is not None:
        result["profile"]["decoded_cache"] = dict(
            hits=state.decoded.hits,
            misses=state.decoded.misses,
            ranges=len(state.decoded.ranges),
            bytes=state.decoded.bytes,
        )
    return result
