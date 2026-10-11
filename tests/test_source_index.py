"""P1c-2 indexes, bounded cuts, cache invalidation and rendered equivalence."""

import json
import tempfile
from pathlib import Path

import pytest

from videoenhancer.media.analyze import analyze
from videoenhancer.media.source_index import analyze_range, build_source_index, source_index
from videoenhancer.trial import run_trial


@pytest.fixture(params=["cfr", "vfr", "bframes", "short-tail"])
def indexed_video(request, tmp_path, ffmpeg_run):
    target = tmp_path / f"{request.param}.mp4"
    size = "256x256" if request.node.callspec.params.get("backend") == "cuda" else "96x64"
    expression = {
        "cfr": "PTS",
        "bframes": "PTS",
        "vfr": "if(lt(N\\,60)\\,N/(20*TB)\\,(3+(N-60)/30)/TB)",
        "short-tail": "if(eq(N\\,159)\\,(N-0.75)/(20*TB)\\,N/(20*TB))",
    }[request.param]
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate=20",
        "-vf",
        f"drawbox=color=white:t=fill:enable='between(n,60,99)',setpts={expression}",
        "-frames:v",
        "160",
        "-fps_mode",
        "vfr",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-g",
        "20",
        "-bf",
        "3" if request.param == "bframes" else "0",
        "-threads",
        "2",
        "-video_track_timescale",
        "60000",
        str(target),
    )
    return target


@pytest.mark.parametrize("position", ["start", "middle", "end"])
@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_range_matches_full_index_cuts_and_trial_bytes(
    indexed_video, position, monkeypatch, tmp_path, backend
):
    from videoenhancer.pipeline.presets import PRESETS, _placeholder

    monkeypatch.setenv("VE_HOME", str(tmp_path / "home"))
    monkeypatch.setitem(PRESETS, "fast", _placeholder)
    monkeypatch.setattr("videoenhancer.trial.record_models", lambda *_: {})
    full = analyze(indexed_video, backend)
    index = build_source_index(indexed_video)
    for field in ("media", "source_pts", "cfr_map", "keyframes"):
        assert index[field] == full[field]
    count = len(index["cfr_map"])
    first = {"start": 0, "middle": count // 2, "end": count - 10}[position]
    last = first + 10
    ranged = analyze_range(indexed_video, index, first, last, backend)
    assert ranged["range_fallback"] is None
    lower, upper = ranged["analysis_span"]
    expected = [s for s in full["scene_scores"] if lower < s["frame"] < upper]
    assert ranged["scene_scores"] == expected
    cuts = {s["frame"] for s in expected}
    assert ranged["scene_cuts"] == [
        i
        for i in range(1, count)
        if any(index["cfr_map"][i - 1] < cut <= index["cfr_map"][i] for cut in cuts)
    ]
    rate = float(__import__("fractions").Fraction(index["media"]["cfr_fps"]))
    with tempfile.TemporaryDirectory(prefix="ve-d2-") as folder:
        base = Path(folder)
        options = dict(
            start=first / rate, seconds=10 / rate, preset="fast", backend=backend, short_side="keep"
        )
        if backend == "cuda":
            options["settings_patch"] = {"lossless": False}
        run_trial(indexed_video, out=base / "range", **options)
        monkeypatch.setattr("videoenhancer.trial.source_index", lambda *_: full)
        monkeypatch.setattr("videoenhancer.trial.analyze_range", lambda *_args, **_kwargs: full)
        run_trial(indexed_video, out=base / "whole", **options)
        for name in ("original.mp4", "enhanced.mp4"):
            assert (base / "range" / name).read_bytes() == (base / "whole" / name).read_bytes()


def test_range_count_failure_falls_back(video_factory, monkeypatch):
    source = video_factory(frames=24)
    index = build_source_index(source)
    monkeypatch.setattr("videoenhancer.media.source_index._range_thumbnails", lambda *_: iter([]))
    value = analyze_range(source, index, 0, 10, "cpu")
    assert "mismatch" in value["range_fallback"]
    assert value["scene_cuts"] == analyze(source, "cpu")["scene_cuts"]


def test_cache_manifest_precedence_invalidation_and_limit(video_factory, tmp_path, monkeypatch):
    import videoenhancer.media.source_index as module

    monkeypatch.setenv("VE_HOME", str(tmp_path / "home"))
    source = video_factory()
    value = source_index(source)
    original = module.build_source_index
    monkeypatch.setattr(
        module, "build_source_index", lambda *_: pytest.fail("Must reuse the index")
    )
    assert source_index(source) == value
    manifest = {**value, "input": module.source_identity(source)}
    cache = tmp_path / "home" / "cache" / "source-index"
    for entry in cache.glob("*.json"):
        entry.unlink()
    assert source_index(source, manifest) == {
        k: value[k] for k in ("media", "source_pts", "cfr_map", "keyframes")
    }
    monkeypatch.setattr(module, "build_source_index", original)
    source.touch()
    source_index(source, manifest)
    assert len(list(cache.glob("*.json"))) == 1
    entry = next(cache.glob("*.json"))
    assert json.loads(entry.read_text(encoding="utf-8"))["identity"] == module.source_identity(
        source
    )
    monkeypatch.setattr(module, "CACHE_LIMIT", 1)
    source.touch()
    source_index(source)
    assert not list(cache.glob("*.json"))
