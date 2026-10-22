"""Probe stream metadata and exact packet presentation times."""

import json
import subprocess
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from videoenhancer import proc
from videoenhancer.config import executable

STANDARD_RATES = tuple(
    Fraction(s) for s in ("24000/1001", "24", "25", "30000/1001", "30", "50", "60000/1001", "60")
)


def rational(value: Any, default: Fraction = Fraction(0)) -> Fraction:
    try:
        return Fraction(str(value).replace(":", "/"))
    except (ValueError, ZeroDivisionError):
        return default


def target_rate(rate: Fraction) -> Fraction:
    if rate <= 0:
        raise ValueError("The input has no usable average frame rate.")
    closest = min(STANDARD_RATES, key=lambda v: abs(v / rate - 1))
    return closest if abs(closest / rate - 1) <= Fraction(5, 1000) else rate


@dataclass
class MediaInfo:
    path: str
    container: str
    duration: float
    codec: str
    profile: str
    bit_depth: int
    width: int
    height: int
    display_width: int
    display_height: int
    rotation: int
    sar: str
    average_fps: str
    r_frame_rate: str
    cfr_fps: str
    is_vfr: bool
    frame_count: int
    frame_count_estimated: bool
    color_matrix: str
    color_range: str
    color_primaries: str
    color_transfer: str
    pixel_format: str
    time_base: str
    start_time: float
    audio_streams: list[dict[str, Any]] = field(default_factory=list)
    has_subtitles: bool = False
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def packet_timeline(path: str | Path, time_base: Fraction) -> tuple[list[Fraction], list[Fraction]]:
    command = [
        executable("ffprobe"),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_packets",
        "-show_entries",
        "packet=pts,duration",
        "-of",
        "csv=p=0",
        str(path),
    ]
    result = proc.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
    )
    records: list[tuple[int, int]] = []
    for line in result.stdout.splitlines():
        fields = line.split(",")
        if len(fields) >= 2 and fields[0].lstrip("-").isdigit():
            records.append((int(fields[0]), int(fields[1]) if fields[1].isdigit() else 0))
    records.sort()
    return (
        [Fraction(pts) * time_base for pts, _ in records],
        [Fraction(d) * time_base for _, d in records],
    )


def audio_packet_spans(path: Path, streams: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Measure audible packet spans, including codec skip/discard samples."""
    rates = {
        int(s["index"]): int(s.get("sample_rate", 0))
        for s in streams
        if s.get("codec_type") == "audio"
    }
    starts = {
        int(s["index"]): float(s.get("start_time", 0))
        for s in streams
        if s.get("codec_type") == "audio"
    }
    if not rates:
        return {}
    command = [
        executable("ffprobe"),
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_packets",
        "-show_entries",
        "packet=stream_index,pts_time,duration_time:packet_side_data=skip_samples,discard_padding",
        "-of",
        "compact=p=0:nk=0",
        str(path),
    ]
    spans: dict[int, dict[str, Any]] = {}
    with proc.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            fields = dict(field.split("=", 1) for field in line.strip().split("|") if "=" in field)
            if not fields.get("stream_index") or fields.get("pts_time", "N/A") == "N/A":
                continue
            index = int(fields["stream_index"])
            rate = rates[index]
            start = float(fields["pts_time"])
            duration = float(fields.get("duration_time", "0").replace("N/A", "0"))
            skip = int(fields.get("skip_samples", "0"))
            discard = int(fields.get("discard_padding", "0"))
            end = start + duration - (discard / rate if rate else 0)
            start += skip / rate if rate else 0
            span = spans.setdefault(index, dict(start=start, end=end, initial_padding=skip))
            span.update(
                start=min(span["start"], start),
                end=max(span["end"], end),
                initial_padding=max(span["initial_padding"], skip),
            )
        process.communicate()
        if process.returncode:
            raise RuntimeError("Could not measure audio packets: " + proc.stderr_text(process))
    for index, span in spans.items():
        # MP4 edit lists can trim a copied AAC priming packet without repeating
        # its skip-samples side data. Respect the audio stream's presentation start.
        if starts[index] > span["start"]:
            span["initial_padding"] += round((starts[index] - span["start"]) * rates[index])
            span["start"] = starts[index]
    return spans


def probe(
    path: str | Path,
    count_frames: bool = False,
    *,
    count_packets: bool = False,
    read_timeline: bool = True,
    allow_hdr: bool = False,
) -> MediaInfo:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input video does not exist: {source}")
    command = [executable("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json"]
    if count_frames:
        command += ["-count_frames"]
    result = proc.run(
        [*command, str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    raw = json.loads(result.stdout)
    streams = raw.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    if video is None:
        raise ValueError("The file has no video stream. Choose a video file.")
    transfer = video.get("color_transfer", "unknown")
    if not allow_hdr and transfer in {"smpte2084", "arib-std-b67"}:
        raise ValueError("HDR (PQ/HLG) input is unsupported in v1. Convert the input to SDR first.")
    width, height = int(video["width"]), int(video["height"])
    tags = video.get("tags", {})
    rotation = round(float(tags.get("rotate", 0))) % 360
    for side in video.get("side_data_list", []):
        if "rotation" in side:
            rotation = round(float(side["rotation"])) % 360
    if rotation not in {0, 90, 180, 270}:
        raise ValueError(f"Unsupported rotation {rotation} degrees. Use a multiple of 90 degrees.")
    rate = rational(video.get("avg_frame_rate")) or rational(video.get("r_frame_rate"))
    cfr_rate = target_rate(rate)
    tb = rational(video.get("time_base"), Fraction(1, 90000))
    duration = float(video.get("duration", raw.get("format", {}).get("duration", 0)))
    count_text = video.get("nb_read_frames") if count_frames else video.get("nb_frames")
    count = int(count_text) if str(count_text).isdigit() else round(duration * float(rate))
    pts, durations = packet_timeline(source, tb) if read_timeline else ([], [])
    is_vfr = any(abs((b - a) - 1 / rate) > tb for a, b in zip(pts, pts[1:], strict=False))
    if count_packets:
        count = len(pts)
    if pts:
        # Packet count is exact for ordinary one-access-unit-per-packet video. A decode
        # count, when requested, takes precedence for unusual containers/codecs.
        if not count_text:
            count = len(pts)
        duration = float(pts[-1] - pts[0] + (durations[-1] or 1 / rate))
    pixel_format = video.get("pix_fmt", "unknown")
    bit_depth = int(video.get("bits_per_raw_sample", "0") or "0")
    if not bit_depth:
        bit_depth = (
            10
            if any(s in pixel_format for s in ("10", "p010"))
            else (12 if "12" in pixel_format else 8)
        )
    matrix = video.get("color_space", "unknown")
    if matrix in {"unknown", "unspecified"}:
        matrix = "bt601" if height <= 576 else "bt709"
    if matrix in {"smpte170m", "bt470bg"}:
        matrix = "bt601"
    if matrix not in {"bt601", "bt709"} and not (
        matrix == "bt2020nc"
        and (
            transfer in {"bt709", "bt2020-10", "bt2020-12"}
            or (allow_hdr and transfer in {"smpte2084", "arib-std-b67"})
        )
    ):
        raise ValueError(f"Unsupported SDR color matrix {matrix}. Convert to BT.709 first.")
    sar = rational(video.get("sample_aspect_ratio", "1:1"), Fraction(1)) or Fraction(1)
    if sar <= 0:
        raise ValueError(
            "The input has an invalid sample aspect ratio. Remux it before processing."
        )
    square_width = max(2, 2 * round(Fraction(width) * sar / 2))
    display_w, display_h = (
        (height, square_width) if rotation in {90, 270} else (square_width, height)
    )
    spans = (
        audio_packet_spans(source, streams)
        if read_timeline or count_packets or count_frames
        else {}
    )
    audio = [
        {
            "index": int(s["index"]),
            "codec": s.get("codec_name", "unknown"),
            "sample_rate": int(s.get("sample_rate", 0)),
            "channels": int(s.get("channels", 0)),
            "initial_padding": spans.get(int(s["index"]), {}).get(
                "initial_padding", int(s.get("initial_padding", 0))
            ),
            "duration": (
                spans[int(s["index"])]["end"] - spans[int(s["index"])]["start"]
                if int(s["index"]) in spans
                else float(s.get("duration", 0))
            ),
            "duration_source": "packets" if int(s["index"]) in spans else "stream metadata",
            "start_offset": spans.get(int(s["index"]), {}).get(
                "start", float(s.get("start_time", 0))
            )
            - float(video.get("start_time", 0)),
            "start_time": spans.get(int(s["index"]), {}).get(
                "start", float(s.get("start_time", 0))
            ),
        }
        for s in streams
        if s.get("codec_type") == "audio"
    ]
    return MediaInfo(
        str(source),
        raw.get("format", {}).get("format_name", "unknown"),
        duration,
        video.get("codec_name", "unknown"),
        video.get("profile", "unknown"),
        bit_depth,
        width,
        height,
        display_w,
        display_h,
        rotation,
        str(sar),
        str(rate),
        str(rational(video.get("r_frame_rate"))),
        str(cfr_rate),
        is_vfr,
        count,
        not bool(count_text or pts),
        matrix,
        video.get("color_range", "tv"),
        video.get("color_primaries", "bt709"),
        transfer,
        pixel_format,
        str(tb),
        float(video.get("start_time", 0)),
        audio,
        any(s.get("codec_type") == "subtitle" for s in streams),
        raw.get("format", {}).get("tags", {}),
    )
