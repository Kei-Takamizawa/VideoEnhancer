from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_degraded.py"
_SPEC = importlib.util.spec_from_file_location("make_degraded", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
make_degraded = _MODULE.make_degraded


def test_make_degraded_writes_four_outside_repo_variants_per_input(video_factory, tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        import pytest

        pytest.skip("FFmpeg and ffprobe are required.")
    input_dir = tmp_path / "private-inputs"
    input_dir.mkdir()
    for index in range(5):
        source = video_factory(width=96, height=64, frames=4)
        source.rename(input_dir / f"private-{index}.mp4")
    output_dir = tmp_path / "generated"

    report = make_degraded(input_dir, output_dir, ffmpeg, ffprobe)

    assert len(report["outputs"]) == 20
    assert {item["sample"] for item in report["outputs"]} == {
        f"sample-{index:02d}" for index in range(1, 6)
    }
    assert {item["degradation"] for item in report["outputs"]} == {
        "D1",
        "D2",
        "D3",
        "D4",
    }
    assert all(
        item["size_bytes"] > 0 and item["video_bitrate_bits_per_second"] > 0
        for item in report["outputs"]
    )
    saved = json.loads((output_dir / "degraded_manifest.json").read_text(encoding="utf-8"))
    assert saved == report
