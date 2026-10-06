from fractions import Fraction

import pytest
import torch

from videoenhancer.config import samples_dir
from videoenhancer.media.analyze import analyze
from videoenhancer.media.color import nv12_to_rgb, rgb_to_nv12
from videoenhancer.media.decode import IndexedDecoder
from videoenhancer.media.probe import probe, target_rate
from videoenhancer.media.timing import nearest_mapping


@pytest.mark.parametrize("rate", ["30", "30000/1001"])
def test_probe_exact_rationals_counts_and_color(video_factory, rate):
    source = video_factory(rate=rate, frames=12)
    result = probe(source, count_frames=True)
    assert (result.width, result.height) == (96, 64)
    assert Fraction(result.average_fps) == Fraction(rate)
    assert Fraction(result.cfr_fps) == Fraction(rate)
    assert result.frame_count == 12
    assert not result.frame_count_estimated
    assert not result.is_vfr
    assert result.color_matrix == "bt709"
    assert result.color_range == "tv"
    assert abs(result.duration - float(12 / Fraction(rate))) <= float(1 / Fraction(rate))


@pytest.mark.parametrize("transfer", ["smpte2084", "arib-std-b67"])
def test_probe_rejects_hdr_with_clear_message(video_factory, transfer):
    with pytest.raises(ValueError, match="HDR.*unsupported"):
        probe(video_factory(transfer=transfer))


def test_analysis_rejects_unsupported_native_pixel_format_before_decoding(
    video_factory, ffmpeg_run, tmp_path
):
    source = video_factory()
    unsupported = tmp_path / "444.mp4"
    ffmpeg_run("-i", str(source), "-c:v", "libx264", "-pix_fmt", "yuv444p", str(unsupported))
    with pytest.raises(ValueError, match="pixel format yuv444p.*4:2:0 SDR"):
        analyze(unsupported, backend="cpu")


def test_rotation_metadata_changes_display_dimensions(video_factory, ffmpeg_run, tmp_path):
    source = video_factory(width=128, height=72)
    rotated = tmp_path / "rotated.mp4"
    ffmpeg_run("-display_rotation", "90", "-i", str(source), "-c", "copy", str(rotated))
    result = probe(rotated)
    assert result.rotation == 90
    assert (result.width, result.height) == (128, 72)
    assert (result.display_width, result.display_height) == (72, 128)


def test_audio_stream_reports_offset(video_factory):
    result = probe(video_factory(frames=30, audio=True, audio_offset=0.2))
    audio = result.audio_streams[0]
    assert audio["codec"] == "aac"
    assert audio["sample_rate"] == 48000
    # AAC's priming packet shifts the container start by one codec frame.
    assert audio["start_offset"] == pytest.approx(0.2, abs=0.025)


@pytest.mark.parametrize("matrix", ["bt601", "bt709"])
def test_nv12_roundtrip_preserves_out_of_range_color_and_chroma(matrix):
    generator = torch.Generator().manual_seed(7)
    packed = torch.randint(0, 256, (24, 32), dtype=torch.uint8, generator=generator)
    rgb = nv12_to_rgb(packed, 32, 16, matrix)
    assert rgb.min() < 0 and rgb.max() > 1
    restored = rgb_to_nv12(rgb, matrix)
    error = restored.to(torch.int16) - packed.to(torch.int16)
    assert error.abs().max() <= 1
    assert abs(error.float().mean().item()) <= 0.5


def test_p010_roundtrip_preserves_ten_bit_codes():
    values = torch.randint(64, 940, (24, 32), generator=torch.Generator().manual_seed(4))
    packed = (values * 64).to(torch.uint16)
    restored = rgb_to_nv12(nv12_to_rgb(packed, 32, 16, bit_depth=10), bit_depth=10)
    error = restored.to(torch.int32) // 64 - values
    assert error.abs().max() <= 1


def test_full_range_black_and_white_conversion():
    for code, expected in ((0, 0.0), (255, 1.0)):
        packed = torch.full((24, 32), 128, dtype=torch.uint8)
        packed[:16] = code
        rgb = nv12_to_rgb(packed, 32, 16, full_range=True)
        assert torch.all(rgb == expected)


@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_indexed_seek_matches_sequential_decode(video_factory, build_manifest, request, backend):
    if backend == "cuda":
        request.getfixturevalue("gpu_available")
    source = video_factory(frames=16)
    manifest = build_manifest(source, backend=backend)
    decoder = IndexedDecoder(source, manifest["media"], backend, manifest)
    sequential = [frame.cpu() for frame in decoder.frames(list(range(16)), lambda: False)]
    decoder.close()
    # The start is deliberately between keyframes; duplicate indices exercise CFR mapping.
    decoder = IndexedDecoder(source, manifest["media"], backend, manifest)
    try:
        sought = list(decoder.frames([5, 6, 6, 7, 8, 9, 10], lambda: False))
    finally:
        decoder.close()
    for actual, index in zip(sought, [5, 6, 6, 7, 8, 9, 10], strict=True):
        assert torch.equal(actual.cpu(), sequential[index])


def test_analysis_detects_known_hard_scene_boundary(ffmpeg_run, tmp_path):
    source = tmp_path / "cut.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=black:size=96x64:rate=30:duration=0.2",
        "-f",
        "lavfi",
        "-i",
        "color=white:size=96x64:rate=30:duration=0.2",
        "-filter_complex",
        "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-crf",
        "0",
        "-threads",
        "2",
        str(source),
    )
    result = analyze(source, backend="cpu")
    assert result["scene_cuts"] == [6]
    assert len(result["cfr_map"]) == 12


def test_nearest_pts_mapping_is_frame_exact_and_snaps_standard_rates():
    pts = [Fraction(0), Fraction(1, 30), Fraction(1, 20), Fraction(1, 15)]
    mapped = nearest_mapping(pts, Fraction(1, 10), Fraction(60))
    assert mapped == [0, 0, 1, 2, 3, 3]
    assert target_rate(Fraction("29.97")) == Fraction(30000, 1001)
    assert target_rate(Fraction(37)) == 37


def test_vfr_probe_and_analysis_build_nearest_cfr_mapping(vfr_video):
    info = probe(vfr_video)
    assert info.is_vfr
    analysis = analyze(vfr_video, backend="cpu")
    assert analysis["cfr_map"] != list(range(info.frame_count))
    expected = round(info.duration * float(Fraction(info.cfr_fps)))
    assert len(analysis["cfr_map"]) == expected
    assert abs(analysis["media"]["duration"] - info.duration) <= float(1 / Fraction(info.cfr_fps))


def test_owner_sample_probe_contract():
    directory = samples_dir()
    if directory is None:
        pytest.skip("Set VE_SAMPLES_DIR to validate the five private sample clips.")
    sources = sorted(
        path
        for path in directory.iterdir()
        if path.suffix.lower() == ".mp4" and not path.stem.endswith("_enhanced")
    )
    assert len(sources) == 5
    results = [probe(source, count_frames=True) for source in sources]
    assert sorted(result.frame_count for result in results) == [326, 375, 532, 561, 911]
    for result in results:
        assert (result.width, result.height) == (720, 1280)
        assert Fraction(result.average_fps) in {
            Fraction(30),
            Fraction(30000, 1001),
            Fraction(2997, 100),
        }
        assert Fraction(result.cfr_fps) in {Fraction(30), Fraction(30000, 1001)}
        assert not result.frame_count_estimated
        print(
            f"{result.path}: frames={result.frame_count}, "
            f"avg={result.average_fps}, cfr={result.cfr_fps}"
        )


def test_owner_sample_hard_cut_count():
    directory = samples_dir()
    if directory is None:
        pytest.skip("Set VE_SAMPLES_DIR to validate private sample scene cuts.")
    source = next(
        (path for path in directory.iterdir() if path.stem.lower().startswith("sample-05")), None
    )
    assert source is not None, "The sample-05 clip is required for the hard-cut acceptance check."
    count = len(analyze(source, backend="cpu")["scene_cuts"])
    print(f"sample-05 hard cuts: {count}")
    assert 8 <= count <= 10, f"Detected {count} cuts; expected 9 +/- 1."


@pytest.mark.parametrize("rate", ["30", "30000/1001"])
def test_cpu_seek_uses_absolute_video_pts_and_keeps_fractional_keyframe(
    video_factory, ffmpeg_run, build_manifest, tmp_path, rate
):
    original = video_factory(frames=16, rate=rate)
    delayed = tmp_path / "video_starts_later.mp4"
    ffmpeg_run(
        "-itsoffset",
        "1",
        "-i",
        str(original),
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=1.6",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-copyts",
        str(delayed),
    )
    metadata = probe(delayed)
    assert metadata.start_time == pytest.approx(1.0, abs=0.001)
    assert metadata.audio_streams[0]["start_offset"] < -0.9
    reference = build_manifest(original)
    decoder = IndexedDecoder(original, reference["media"], "cpu", reference)
    try:
        frames = list(decoder.frames(list(range(16)), lambda: False))
    finally:
        decoder.close()
    normalized = build_manifest(delayed)
    decoder = IndexedDecoder(delayed, normalized["media"], "cpu", normalized)
    try:
        selected = list(decoder.frames([5, 6, 7, 8, 9, 10], lambda: False))
    finally:
        decoder.close()
    for actual, index in zip(selected, [5, 6, 7, 8, 9, 10], strict=True):
        assert torch.equal(actual, frames[index])
