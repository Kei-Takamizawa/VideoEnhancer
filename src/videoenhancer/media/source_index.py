"""Whole-source timestamp indexes and bounded, unchanged scene detection."""

import hashlib
import json
import logging
import os
import subprocess
import time
import uuid
from bisect import bisect_left, bisect_right
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from videoenhancer import proc
from videoenhancer.config import executable, get_home
from videoenhancer.media.analyze import _cut_score, analyze
from videoenhancer.media.decode import _load_pynvcodec, read_exact, validate_pixel_format
from videoenhancer.media.probe import packet_timeline, probe
from videoenhancer.media.timing import nearest_mapping

CACHE_LIMIT = 1_000_000_000


def source_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return dict(path=str(path.resolve()), size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def build_source_index(
    path: Path, progress: Callable[[str, float], None] | None = None
) -> dict[str, Any]:
    """Keep the existing packet passes until combined-pass equivalence is proven."""
    message = "Reading the video (first time only)…"
    if progress:
        progress(message, 0)
    info = probe(path)
    if progress:
        progress(message, 100 / 3)
    media = info.to_dict()
    validate_pixel_format(media)
    pts, durations = packet_timeline(path, Fraction(info.time_base))
    if not pts:
        raise ValueError("The input lacks presentation timestamps. Remux it before processing.")
    duration = pts[-1] - pts[0] + (durations[-1] or 1 / Fraction(info.average_fps))
    mapping = nearest_mapping(pts, duration, Fraction(info.cfr_fps))
    if progress:
        progress(message, 200 / 3)
    packets = proc.run(
        [
            executable("ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_packets",
            "-show_entries",
            "packet=pts,flags",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    key_pts = {
        int(row.split(",")[0])
        for row in packets
        if len(row.split(",")) > 1
        and "K" in row.split(",")[1]
        and row.split(",")[0].lstrip("-").isdigit()
    }
    media.update(
        source_frame_count=len(pts),
        frame_count=len(mapping),
        duration=float(Fraction(len(mapping)) / Fraction(info.cfr_fps)),
        frame_count_estimated=False,
    )
    if progress:
        progress(message, 100)
    return dict(
        media=media,
        source_pts=[str(p) for p in pts],
        packet_durations=[str(d) for d in durations],
        cfr_map=mapping,
        keyframes=[
            dict(index=i, pts=str(p))
            for i, p in enumerate(pts)
            if int(p / Fraction(info.time_base)) in key_pts
        ],
    )


def source_index(
    path: Path,
    manifest: dict[str, Any] | None = None,
    progress: Callable[[str, float], None] | None = None,
) -> dict[str, Any]:
    identity = source_identity(path)
    if manifest and all(manifest.get("input", {}).get(k) == v for k, v in identity.items()):
        if all(k in manifest for k in ("media", "source_pts", "cfr_map", "keyframes")):
            return {k: manifest[k] for k in ("media", "source_pts", "cfr_map", "keyframes")}
    cache = get_home() / "cache" / "source-index"
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    target = cache / f"{key}.json"
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if value["identity"] == identity and value.get("version") == 1:
            return value["index"]
    except (OSError, ValueError, KeyError):
        pass
    value = build_source_index(path, progress)
    if source_identity(path) != identity:
        raise ValueError("The input changed while reading its timestamps. Retry the video.")
    temporary = cache / f"{key}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(
            json.dumps(dict(version=1, identity=identity, index=value)), encoding="utf-8"
        )
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    entries = sorted(cache.glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
    total = sum(p.stat().st_size for p in entries)
    for entry in entries:
        if total <= CACHE_LIMIT:
            break
        total -= entry.stat().st_size
        entry.unlink(missing_ok=True)
    return value


def _range_thumbnails(path: Path, index: dict[str, Any], backend: str, first: int, last: int):
    media = index["media"]
    if backend == "cuda":
        nvc = _load_pynvcodec()
        decoder = nvc.SimpleDecoder(
            str(path),
            gpu_id=0,
            use_device_memory=True,
            output_color_type=nvc.OutputColorType.NATIVE,
            decoder_cache_size=1,
            need_scanned_stream_metadata=True,
        )
        for position in range(first, last):
            tensor = torch.from_dlpack(decoder[position])[
                : media["height"], : media["width"]
            ].float()
            if media["bit_depth"] > 8:
                tensor = tensor / 256
            yield (
                F.interpolate(tensor[None, None], size=(90, 160), mode="area")[0, 0]
                .cpu()
                .numpy()
                .astype(np.uint8)
            )
        return
    previous = max((k["index"] for k in index["keyframes"] if k["index"] <= first), default=0)
    seek = Fraction(index["source_pts"][previous]) * 1_000_000
    microseconds = seek.numerator // seek.denominator
    command = [
        executable("ffmpeg"),
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "2",
        "-noautorotate",
        "-seek_timestamp",
        "1",
        "-ss",
        f"{microseconds / 1_000_000:.6f}",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-vf",
        f"select=between(n\\,{first - previous}\\,{last - previous - 1}),scale=160:90",
        "-pix_fmt",
        "gray",
        "-fps_mode",
        "passthrough",
        "-frames:v",
        str(last - first),
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = proc.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    try:
        while raw := read_exact(process.stdout, 90 * 160):
            if len(raw) != 90 * 160:
                raise ValueError("Incomplete frame during range scene analysis.")
            yield np.frombuffer(raw, np.uint8).reshape(90, 160)
        _, stderr = process.communicate()
        if process.returncode:
            raise RuntimeError(f"Range scene analysis failed: {stderr.decode(errors='replace')}")
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate()


def analyze_range(
    path: Path, index: dict[str, Any], first: int, last: int, backend: str, context_frames: int = 30
) -> dict[str, Any]:
    started = time.perf_counter()
    mapping = index["cfr_map"]
    if not 0 <= first < last <= len(mapping):
        raise ValueError("Trial range is outside the video.")
    pts = [Fraction(p) for p in index["source_pts"]]
    margin = max(Fraction(2), Fraction(context_frames) / Fraction(index["media"]["cfr_fps"]))
    lower = bisect_left(pts, pts[mapping[first]] - margin)
    upper = bisect_right(pts, pts[mapping[last - 1]] + margin)
    cuts, scores = [], []
    previous = None
    count = 0
    try:
        for position, thumbnail in enumerate(
            _range_thumbnails(path, index, backend, lower, upper), lower
        ):
            count += 1
            if previous is not None:
                delta, distance = _cut_score(previous, thumbnail)
                if delta >= 24 and distance >= 0.18:
                    cuts.append(position)
                    scores.append(
                        dict(
                            frame=position,
                            delta=round(delta, 3),
                            histogram_distance=round(distance, 3),
                        )
                    )
            previous = thumbnail
        if count != upper - lower:
            raise ValueError(
                f"Range timestamp/frame mismatch ({upper - lower} packets, {count} frames)."
            )
    except (ValueError, RuntimeError) as error:
        logging.getLogger(__name__).warning("Range analysis fallback: %s", error)
        full = analyze(path, backend=backend)
        full["range_fallback"] = str(error)
        return full
    return {
        **index,
        "scene_cuts": [
            i
            for i in range(1, len(mapping))
            if any(mapping[i - 1] < cut <= mapping[i] for cut in cuts)
        ],
        "scene_scores": scores,
        "analysis_seconds": time.perf_counter() - started,
        "backend": backend,
        "analysis_span": [lower, upper],
        "range_fallback": None,
    }
