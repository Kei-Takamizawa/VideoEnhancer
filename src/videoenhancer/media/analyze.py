"""One bounded analysis pass: presentation mapping and hard scene cuts."""

import importlib
import subprocess
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.media.decode import choose_backend, read_exact, validate_pixel_format
from videoenhancer.media.probe import packet_timeline, probe
from videoenhancer.media.timing import nearest_mapping


def _cut_score(previous: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    delta = float(np.abs(current.astype(np.float32) - previous.astype(np.float32)).mean())
    a = np.histogram(previous, bins=32, range=(0, 256))[0].astype(np.float64)
    b = np.histogram(current, bins=32, range=(0, 256))[0].astype(np.float64)
    distance = float(np.abs(a / a.sum() - b / b.sum()).sum() / 2)
    return delta, distance


def _thumbnails(path: Path, media: dict[str, Any], backend: str):
    if backend == "cuda":
        nvc: Any = importlib.import_module("PyNvVideoCodec")

        decoder = nvc.SimpleDecoder(
            str(path),
            gpu_id=0,
            use_device_memory=True,
            output_color_type=nvc.OutputColorType.NATIVE,
            decoder_cache_size=1,
        )
        remaining = int(media["frame_count"])
        while remaining:
            frames = decoder.get_batch_frames(min(4, remaining))
            if not frames:
                break
            remaining -= len(frames)
            for frame in frames:
                tensor = torch.from_dlpack(frame)[: media["height"], : media["width"]].float()
                if media["bit_depth"] > 8:
                    tensor = tensor / 256
                small = F.interpolate(tensor[None, None], size=(90, 160), mode="area")[0, 0]
                yield small.cpu().numpy().astype(np.uint8)
        return
    command = [
        executable("ffmpeg"),
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "2",
        "-noautorotate",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-vf",
        "scale=160:90",
        "-pix_fmt",
        "gray",
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = proc.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    try:
        while raw := read_exact(process.stdout, 90 * 160):
            if len(raw) != 90 * 160:
                raise RuntimeError("Incomplete frame during scene analysis. Check the input video.")
            yield np.frombuffer(raw, np.uint8).reshape(90, 160)
        _, stderr = process.communicate()
        if process.returncode:
            raise RuntimeError(f"Scene analysis failed: {stderr.decode(errors='replace')}")
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate()


def analyze(path: str | Path, backend: str = "auto") -> dict[str, Any]:
    started = time.perf_counter()
    path = Path(path).resolve()
    selected = choose_backend(backend)
    info = probe(path)
    media = info.to_dict()
    validate_pixel_format(media)
    pts, durations = packet_timeline(path, Fraction(info.time_base))
    if not pts:
        raise ValueError("The input lacks presentation timestamps. Remux it before processing.")
    duration = pts[-1] - pts[0] + (durations[-1] or 1 / Fraction(info.average_fps))
    mapping = nearest_mapping(pts, duration, Fraction(info.cfr_fps))
    cuts = []
    scores = []
    previous: np.ndarray | None = None
    source_count = 0
    for index, thumbnail in enumerate(_thumbnails(path, media, selected)):
        source_count += 1
        if previous is not None:
            delta, distance = _cut_score(previous, thumbnail)
            if delta >= 24 and distance >= 0.18:
                cuts.append(index)
                scores.append(
                    {
                        "frame": index,
                        "delta": round(delta, 3),
                        "histogram_distance": round(distance, 3),
                    }
                )
        previous = thumbnail
    if source_count != len(pts):
        raise ValueError(
            f"Timestamp/frame count mismatch ({len(pts)} packets, {source_count} decoded frames). "
            "Remux the input first."
        )
    normalized_cuts = [
        index
        for index in range(1, len(mapping))
        if any(mapping[index - 1] < cut <= mapping[index] for cut in cuts)
    ]
    command = [
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
    ]
    packets = proc.run(command, capture_output=True, text=True, check=True).stdout.splitlines()
    key_pts = {
        int(row.split(",")[0])
        for row in packets
        if len(row.split(",")) > 1
        and "K" in row.split(",")[1]
        and row.split(",")[0].lstrip("-").isdigit()
    }
    keyframes = [
        {"index": index, "pts": str(timestamp)}
        for index, timestamp in enumerate(pts)
        if int(timestamp / Fraction(info.time_base)) in key_pts
    ]
    media["source_frame_count"] = source_count
    media["frame_count"] = len(mapping)
    media["duration"] = float(Fraction(len(mapping)) / Fraction(info.cfr_fps))
    media["frame_count_estimated"] = False
    return {
        "media": media,
        "cfr_map": mapping,
        "source_pts": [str(p) for p in pts],
        "keyframes": keyframes,
        "scene_cuts": normalized_cuts,
        "scene_scores": scores,
        "analysis_seconds": time.perf_counter() - started,
        "backend": selected,
    }
