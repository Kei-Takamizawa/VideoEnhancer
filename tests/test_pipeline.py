import os
from fractions import Fraction
from io import BytesIO

import numpy as np
import pytest
import torch

from videoenhancer.media import encode as encode_module
from videoenhancer.media.encode import Encoder
from videoenhancer.media.mux import _audio_duration_matches, assemble
from videoenhancer.media.probe import probe
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.pipeline.stages import Blend2xStage, FrameBatch, ResizeStage


def test_gpu_encoder_synchronizes_and_passes_owned_host_input_to_nvenc(monkeypatch):
    class FakeStream:
        def __init__(self):
            self.synchronizations = 0

        def synchronize(self):
            self.synchronizations += 1

    class FakeEncoder:
        def Encode(self, surface):
            assert stream.synchronizations == 1
            assert isinstance(surface, np.ndarray)
            assert np.array_equal(surface, nv12_surface.numpy())
            return b"packet"

    stream = FakeStream()
    nv12_surface = torch.zeros((3, 4, 4), dtype=torch.uint8)
    monkeypatch.setattr(torch.cuda, "current_stream", lambda: stream)
    monkeypatch.setattr(encode_module, "rgb_to_nv12", lambda *_args: nv12_surface)
    encoder = object.__new__(Encoder)
    encoder.backend = "cuda"
    encoder.media = {"color_matrix": "bt709"}
    encoder.bit_depth = 8
    encoder.encoder = FakeEncoder()
    encoder.stream = BytesIO()

    encoder.write(torch.zeros((3, 4, 4)))

    assert stream.synchronizations == 1
    assert encoder.stream.getvalue() == b"packet"


def test_gpu_encoder_configures_nvenc_for_host_input(monkeypatch, tmp_path):
    captured = {}

    class FakeNvCodec:
        @staticmethod
        def CreateEncoder(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return object()

    monkeypatch.setattr(encode_module.importlib, "import_module", lambda *_args: FakeNvCodec)
    encoder = Encoder(
        tmp_path / "output.mp4",
        4,
        4,
        Fraction(30),
        "hevc",
        "cuda",
        {"color_matrix": "bt709"},
    )
    assert captured["args"][:4] == (4, 4, "P010", True)
    assert "cudastream" not in captured["kwargs"]
    encoder.abort()


@pytest.mark.parametrize("arrival", ["before", "during"])
def test_assembly_never_overwrites_another_file(
    video_factory, build_manifest, tmp_path, monkeypatch, arrival
):
    source = video_factory(frames=6)
    manifest = build_manifest(source)
    segment = {"index": 0, "start": 0, "end": 6, "file": "seg_00000.mp4"}
    process_segment(manifest, segment, tmp_path / segment["file"], lambda: False)
    output = tmp_path / "protected.mp4"
    manifest.update(segments=[segment], output=str(output))
    payload = b"Another program owns this file."
    if arrival == "before":
        output.write_bytes(payload)
    else:
        operation = "rename" if os.name == "nt" else "link"
        publish = getattr(os, operation)

        def conflicting_publish(temporary, destination):
            output.write_bytes(payload)
            return publish(temporary, destination)

        monkeypatch.setattr(os, operation, conflicting_publish)
    with pytest.raises(FileExistsError):
        assemble(manifest, tmp_path)
    assert output.read_bytes() == payload
    assert not list(tmp_path.glob("*.tmp.mp4"))


def test_blend_exact_timestamps_last_duplicate_and_cut_protection():
    frames = torch.tensor([0, 1, 0.25], dtype=torch.float16)[:, None, None, None].expand(3, 3, 4, 4)
    rate = Fraction(30000, 1001)
    batch = FrameBatch(frames, tuple(Fraction(i) / rate for i in range(3)), (0, 1, 2))
    result = Blend2xStage(rate, {1}).process(batch)
    assert result.frames.shape == (6, 3, 4, 4)
    assert result.indices == tuple(range(6))
    assert result.timestamps == tuple(Fraction(i) / (rate * 2) for i in range(6))
    assert torch.equal(result.frames[1], frames[0])
    assert torch.equal(result.frames[3], (frames[1] + frames[2]) * 0.5)
    assert torch.equal(result.frames[5], frames[2])


def test_resize_preserves_timestamp_and_float16_data():
    frame = torch.rand((2, 3, 8, 12)).half()
    batch = FrameBatch(frame, (Fraction(0), Fraction(1, 30)), (0, 1))
    result = ResizeStage(24, 16).process(batch)
    assert result.frames.shape == (2, 3, 16, 24)
    assert result.frames.dtype == torch.float16
    assert result.timestamps == batch.timestamps


def test_output_rules_keep_size_no_downscale_and_rate_limits():
    settings = {"preset": "p0-test", "short_side": 1080, "fps": "2x"}
    media = {"display_width": 720, "display_height": 1280, "cfr_fps": "30000/1001"}
    assert output_size(settings, media) == (1080, 1920)
    assert output_size(settings, {**media, "display_width": 1280, "display_height": 720}) == (
        1920,
        1080,
    )
    assert output_size(settings, {**media, "display_width": 2160, "display_height": 3840}) == (
        2160,
        3840,
    )
    assert output_size({**settings, "short_side": "keep"}, media) == (720, 1280)
    assert output_rate(settings, media) == Fraction(60000, 1001)
    assert output_rate(settings, {**media, "cfr_fps": "50"}) == 50
    assert output_rate(settings, {**media, "cfr_fps": "40"}) == 40
    assert output_rate({**settings, "fps": "off"}, media) == Fraction(30000, 1001)


@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
@pytest.mark.parametrize("width,height", [(720, 1280), (1280, 720)])
def test_p0_geometry_exact_frame_count_and_rate(
    video_factory, build_manifest, request, tmp_path, backend, width, height
):
    if backend == "cuda":
        request.getfixturevalue("gpu_available")
    source = video_factory(width=width, height=height, frames=6, rate="30000/1001")
    manifest = build_manifest(source, backend=backend, short_side=1080, lossless=False)
    output = tmp_path / "enhanced.mp4"
    statistics = process_segment(
        manifest, {"index": 0, "start": 0, "end": 6}, output, lambda: False
    )
    result = probe(output, count_frames=True)
    expected_size = (1080, 1920) if width < height else (1920, 1080)
    assert (result.width, result.height) == expected_size
    assert result.frame_count == 12
    assert Fraction(result.average_fps) == Fraction(60000, 1001)
    assert result.duration == pytest.approx(
        manifest["media"]["duration"], abs=float(Fraction(1001, 60000))
    )
    assert statistics["output_frames"] == 12
    if backend == "cuda":
        assert statistics["peak_torch_vram_bytes"] <= 2 * 1024**3
        print(f"GPU {width}x{height}: {statistics}")


@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_rotation_becomes_portrait_pixels_without_flag(
    video_factory, build_manifest, ffmpeg_run, tmp_path, request, backend
):
    if backend == "cuda":
        request.getfixturevalue("gpu_available")
    original = video_factory(width=1280, height=720, frames=6)
    source = tmp_path / "rotated.mp4"
    ffmpeg_run("-display_rotation", "90", "-i", str(original), "-c", "copy", str(source))
    manifest = build_manifest(source, backend=backend, short_side=1080, lossless=False)
    output = tmp_path / "rotated_enhanced.mp4"
    process_segment(manifest, {"index": 0, "start": 0, "end": 6}, output, lambda: False)
    result = probe(output)
    assert (result.width, result.height) == (1080, 1920)
    assert result.rotation == 0
    manifest["segments"] = [{"index": 0, "start": 0, "end": 6, "file": str(output)}]
    manifest["output"] = str(tmp_path / "rotated_final.mp4")
    assembled = probe(assemble(manifest, tmp_path))
    assert (assembled.width, assembled.height) == (1080, 1920)
    assert assembled.rotation == 0


@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_segment_temporal_context_matches_whole_reference(
    video_factory, build_manifest, ffmpeg_run, request, tmp_path, backend
):
    if backend == "cuda":
        request.getfixturevalue("gpu_available")
    source = video_factory(width=256, height=144, frames=16)
    manifest = build_manifest(source, backend=backend)
    whole = tmp_path / "whole.mp4"
    segment = tmp_path / "part.mp4"
    process_segment(manifest, {"index": 0, "start": 0, "end": 16}, whole, lambda: False)
    process_segment(manifest, {"index": 1, "start": 5, "end": 11}, segment, lambda: False)

    def raw(path):
        data = ffmpeg_run(
            "-i", str(path), "-an", "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1"
        ).stdout
        return np.frombuffer(data, np.uint8).reshape(-1, 256 * 144 * 3 // 2)

    reference = raw(whole)[10:22]
    actual = raw(segment)
    # Compare decoded frames rather than differently located keyframe bitstreams.
    assert actual.shape == reference.shape
    assert np.array_equal(actual, reference)


def test_final_mux_preserves_audio_offset_and_duration(
    video_factory, build_manifest, ffmpeg_run, tmp_path
):
    source = video_factory(frames=30, audio=True, audio_extra=0.15)
    manifest = build_manifest(source)
    segment = {"index": 0, "start": 0, "end": 30, "file": "seg_00000.mp4"}
    process_segment(manifest, segment, tmp_path / segment["file"], lambda: False)
    manifest["segments"] = [segment]
    manifest["output"] = str(tmp_path / "final.mp4")
    output = assemble(manifest, tmp_path)
    info = probe(output, count_frames=True)
    assert info.frame_count == 60
    original = probe(source).audio_streams[0]
    actual = info.audio_streams[0]
    assert _audio_duration_matches(original, actual)
    assert info.audio_streams[0]["start_offset"] == pytest.approx(
        original["start_offset"], abs=0.020
    )
    source_pcm = ffmpeg_run(
        "-i", str(source), "-map", "0:a:0", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"
    ).stdout
    output_pcm = ffmpeg_run(
        "-i", str(output), "-map", "0:a:0", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"
    ).stdout
    assert output_pcm == source_pcm
    assert not list(tmp_path.glob("*.tmp.mp4"))


def test_audio_duration_comparison_accounts_for_aac_priming():
    source = {
        "duration": 17.854708,
        "sample_rate": 48000,
        "initial_padding": 5058,
    }
    stream_copied = {"duration": 17.749333}
    assert _audio_duration_matches(source, stream_copied)
    assert not _audio_duration_matches(source, {"duration": 17.70})


@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_vfr_normalization_preserves_total_duration_and_audio(
    vfr_video, build_manifest, tmp_path, request, backend
):
    if backend == "cuda":
        request.getfixturevalue("gpu_available")
    manifest = build_manifest(vfr_video, backend=backend, preset="passthrough", fps="off")
    segment = {"index": 0, "start": 0, "end": len(manifest["cfr_map"]), "file": "seg_00000.mp4"}
    process_segment(manifest, segment, tmp_path / segment["file"], lambda: False)
    manifest["segments"] = [segment]
    manifest["output"] = str(tmp_path / "vfr_normalized.mp4")
    result = probe(assemble(manifest, tmp_path), count_frames=True)
    original = probe(vfr_video)
    assert not result.is_vfr
    assert result.frame_count == len(manifest["cfr_map"])
    tolerance = float(1 / Fraction(result.cfr_fps))
    assert abs(result.duration - original.duration) <= tolerance
    assert result.audio_streams[0]["duration"] == pytest.approx(
        original.audio_streams[0]["duration"], abs=0.020
    )


@pytest.mark.gpu
@pytest.mark.parametrize("codec", ["h264", "hevc"])
def test_gpu_lossless_color_roundtrip_acceptance(
    video_factory, build_manifest, ffmpeg_run, gpu_available, tmp_path, codec
):
    source = video_factory(width=256, height=144, frames=12)
    manifest = build_manifest(source, backend="cuda", preset="passthrough", fps="off", codec=codec)
    output = tmp_path / "color.mp4"
    process_segment(manifest, {"index": 0, "start": 0, "end": 12}, output, lambda: False)

    def planes(path):
        data = ffmpeg_run(
            "-i", str(path), "-an", "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1"
        ).stdout
        pixels = 256 * 144
        values = np.frombuffer(data, np.uint8).reshape(12, pixels * 3 // 2)
        return values[:, :pixels], values[:, pixels : pixels * 5 // 4], values[:, pixels * 5 // 4 :]

    for plane, original, actual, minimum_psnr in zip(
        ("Y", "U", "V"), planes(source), planes(output), (48, 40, 40), strict=True
    ):
        difference = actual.astype(np.float64) - original.astype(np.float64)
        mse = np.mean(difference**2)
        psnr = float("inf") if mse == 0 else 10 * np.log10(255**2 / mse)
        print(
            f"GPU lossless {codec} {plane}: PSNR={psnr:.6f} dB, "
            f"signed_error={difference.mean():.6f}"
        )
        assert psnr >= minimum_psnr, f"PSNR {psnr:.3f} dB < {minimum_psnr} dB"
        assert abs(difference.mean()) <= 0.5


@pytest.mark.gpu
@pytest.mark.parametrize("codec", ["hevc", "h264", "av1"])
def test_gpu_encoder_codec_options(video_factory, build_manifest, gpu_available, tmp_path, codec):
    source = video_factory(width=256, height=144, frames=6)
    manifest = build_manifest(
        source, backend="cuda", preset="passthrough", fps="off", codec=codec, lossless=False
    )
    output = tmp_path / f"{codec}.mp4"
    process_segment(manifest, {"index": 0, "start": 0, "end": 6}, output, lambda: False)
    result = probe(output, count_frames=True)
    assert result.frame_count == 6
    assert result.bit_depth == (8 if codec == "h264" else 10)
    assert result.color_matrix == "bt709"
    assert result.color_range == "tv"
    assert result.color_transfer == "bt709"


@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_passthrough_normalizes_sar_before_display_rotation(
    video_factory, build_manifest, ffmpeg_run, tmp_path, request, rotation, backend
):
    if backend == "cuda":
        request.getfixturevalue("gpu_available")
    original = video_factory(width=256, height=144, frames=6)
    anamorphic = tmp_path / "anamorphic.mp4"
    ffmpeg_run(
        "-i",
        str(original),
        "-vf",
        "setsar=2/1",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-threads",
        "2",
        str(anamorphic),
    )
    if rotation:
        rotated = tmp_path / "anamorphic_rotated.mp4"
        ffmpeg_run(
            "-display_rotation", str(rotation), "-i", str(anamorphic), "-c", "copy", str(rotated)
        )
        anamorphic = rotated
    source = probe(anamorphic)
    expected = (144, 512) if rotation else (512, 144)
    assert source.sar == "2"
    assert (source.display_width, source.display_height) == expected
    manifest = build_manifest(
        anamorphic,
        backend=backend,
        preset="passthrough",
        fps="off",
        codec="hevc" if backend == "cuda" else "h264",
    )
    output = tmp_path / "square_pixels.mp4"
    process_segment(manifest, {"index": 0, "start": 0, "end": 6}, output, lambda: False)
    actual = probe(output, count_frames=True)
    assert (actual.width, actual.height) == expected
    assert Fraction(actual.sar) == 1
    assert actual.rotation == 0
    assert actual.frame_count == 6
