"""Synthetic container boundaries; CPU fixture stages are not GPU model evidence."""

import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
import torch

from videoenhancer.config import executable
from videoenhancer.media.decode import IndexedDecoder
from videoenhancer.media.mux import assemble, audio_sync_delta
from videoenhancer.media.probe import probe
from videoenhancer.pipeline.runner import process_segment

FORMATS = [
    ("libvpx-vp9", "libopus", "webm"),
    ("libaom-av1", "libopus", "webm"),
    ("libaom-av1", "aac", "mp4"),
    ("libvpx-vp9", "libopus", "mkv"),
    ("libx264", "aac", "mp4"),
]


@pytest.mark.gpu
def test_fractional_h264_bframes_keep_presentation_timestamps(
    tmp_path, gpu_available, bounded_cpu, video_factory, ffmpeg_run, build_manifest
):
    seed = video_factory(width=960, height=540, frames=180, rate="30000/1001")
    source = tmp_path / "bframes-2997.mp4"
    ffmpeg_run(
        "-i",
        str(seed),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-bf",
        "2",
        "-g",
        "60",
        "-threads",
        "2",
        str(source),
    )
    job = build_manifest(source, backend="cpu", preset="passthrough", fps="off")
    assert job["media"]["cfr_fps"] == "30000/1001"
    _assert_nvdec_matches_cpu_nv12(source, job)


def test_audio_priming_does_not_hide_a_thirty_millisecond_shift():
    original = dict(codec="aac", sample_rate=48000, start_offset=0, initial_padding=1024)
    shifted = {**original, "start_offset": 0.030}
    assert abs(audio_sync_delta(original, shifted)) > 0.020


@pytest.mark.parametrize("codec,container", [("aac", "mp4"), ("libopus", "mkv")])
def test_decoded_audio_waveform_stays_within_twenty_milliseconds(
    tmp_path, bounded_cpu, ffmpeg_run, build_manifest, codec, container
):
    import numpy as np

    samples = np.random.default_rng(41).normal(0, 0.1, 5 * 48000).astype("float32")
    audio = tmp_path / "synthetic.f32"
    samples.tofile(audio)
    source = tmp_path / f"synthetic.{container}"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=96x64:rate=30",
        "-f",
        "f32le",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-i",
        str(audio),
        "-t",
        "5",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        codec,
        "-threads",
        "1",
        str(source),
    )
    job = build_manifest(source, backend="cpu", preset="passthrough", short_side="keep", fps="off")
    part = dict(index=0, start=0, end=len(job["cfr_map"]), state="done", file="segment.mp4")
    job.update(output=str(tmp_path / "output.mp4"), segments=[part])
    process_segment(job, part, tmp_path / "segment.mp4", lambda: False)
    output = assemble(job, tmp_path)

    def pcm(path):
        result = subprocess.run(
            [
                executable("ffmpeg"),
                "-v",
                "error",
                "-i",
                str(path),
                "-vn",
                "-f",
                "f32le",
                "-ar",
                "48000",
                "-ac",
                "1",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
            timeout=20,
        )
        return np.frombuffer(result.stdout, dtype="float32")

    original, actual = pcm(source), pcm(output)
    length = 1 << (len(original) + len(actual) - 1).bit_length()
    correlation = np.fft.irfft(
        np.fft.rfft(actual, length) * np.conj(np.fft.rfft(original, length)), length
    )
    lags = np.arange(-4096, 4097)
    offset = int(lags[np.argmax(correlation[lags % length])])
    assert abs(offset) / 48000 <= 0.020


@pytest.fixture
def bounded_cpu(monkeypatch, tmp_path):
    monkeypatch.setenv("VE_HOME", str(tmp_path))
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


@pytest.mark.parametrize("video_codec,audio_codec,container", FORMATS)
@pytest.mark.parametrize(
    "mode",
    [
        "cpu",
        pytest.param("standard", marks=pytest.mark.gpu),
        pytest.param("fast", marks=pytest.mark.gpu),
    ],
)
@pytest.mark.parametrize(
    "variant", ["portrait", "landscape60", "fps25", "offset", "short-audio", "no-audio", "vfr"]
)
def test_container_frames_seek_timestamps_and_audio(
    tmp_path,
    bounded_cpu,
    ffmpeg_run,
    build_manifest,
    video_codec,
    audio_codec,
    container,
    variant,
    mode,
    request,
):
    if mode != "cpu":
        request.getfixturevalue("gpu_available")
        model_home = os.environ.get("VE_GPU_TEST_MODEL_HOME")
        if not model_home:
            pytest.skip("Set VE_GPU_TEST_MODEL_HOME to an isolated qualified model fixture")
        for name in ("models", "adapter-sources"):
            shutil.copytree(Path(model_home) / name, tmp_path / name)
    available = subprocess.run(
        [executable("ffmpeg"), "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if not any(
        len(fields := row.split()) > 1 and fields[1] == video_codec
        for row in available.splitlines()
    ):
        pytest.skip(f"FFmpeg encoder {video_codec} is unavailable")
    width, height = (256, 144) if variant == "landscape60" else (144, 256)
    if mode != "cpu":
        width, height = (1920, 1080) if variant == "landscape60" else (1080, 1920)
    rate = 60 if variant == "landscape60" else 25 if variant == "fps25" else 30
    arguments = ["-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={rate}"]
    if variant != "no-audio":
        arguments += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=10"]
    filters = "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709"
    if variant == "vfr":
        filters += ",settb=1/1000,setpts=if(lt(N\\,150)\\,N/(30*TB)\\,(5+(N-150)/25)/TB)"
    arguments += [
        "-vf",
        filters,
        "-fps_mode",
        "vfr",
        "-t",
        "10",
        "-c:v",
        video_codec,
        "-threads",
        "2",
        "-g",
        "30",
        "-pix_fmt",
        "yuv420p",
    ]
    if video_codec == "libvpx-vp9":
        arguments += ["-deadline", "realtime", "-cpu-used", "8"]
    elif video_codec == "libaom-av1":
        arguments += ["-cpu-used", "8", "-row-mt", "1"]
    else:
        arguments += ["-preset", "ultrafast", "-bf", "0"]
    if variant != "no-audio":
        arguments += ["-c:a", audio_codec]
        if variant == "short-audio":
            arguments += ["-af", "atrim=duration=9.9"]
    if variant == "offset":
        arguments += ["-output_ts_offset", "3"]
    source = tmp_path / f"synthetic.{container}"
    # Full-HD 60 fps software AV1 fixtures can exceed the small-fixture limit.
    ffmpeg_run(*arguments, str(source), timeout=180)
    original = probe(source)
    job = build_manifest(
        source,
        backend="cuda" if mode != "cpu" else "cpu",
        preset=mode if mode != "cpu" else "p0-test",
        short_side="keep",
        fps="2x",
    )
    job.update(
        output=str(tmp_path / "output.mp4"),
        segments=[
            dict(index=0, start=0, end=len(job["cfr_map"]), state="done", file="segment.mp4")
        ],
    )
    if mode == "cpu":
        decoder = IndexedDecoder(source, job["media"], "cpu", job)
        try:
            count = job["media"]["source_frame_count"]
            sequential = [
                (frame * 255).round().clamp(0, 255).to(torch.uint8)
                for frame in decoder.frames(list(range(count)), lambda: False)
            ]
            selected = [count - 1, count // 2, 0]
            for index in selected:
                sought = next(decoder.frames([index], lambda: False))
                assert torch.equal(
                    (sought * 255).round().clamp(0, 255).to(torch.uint8), sequential[index]
                )
        finally:
            decoder.close()
    if mode != "cpu":
        _assert_nvdec_matches_cpu_nv12(source, job)
    process_segment(job, job["segments"][0], tmp_path / "segment.mp4", lambda: False)
    result = probe(assemble(job, tmp_path), count_packets=True)
    factor = 2 if rate < 50 else 1
    assert result.frame_count == len(job["cfr_map"]) * factor
    assert Fraction(result.cfr_fps) == Fraction(job["media"]["cfr_fps"]) * factor
    for first, second in zip(original.audio_streams, result.audio_streams, strict=True):
        assert first["duration_source"] == second["duration_source"] == "packets"
        assert abs(audio_sync_delta(first, second)) <= 0.020
        assert abs(first["duration"] - second["duration"]) <= 0.020 + 1024 / 48000
    if variant == "short-audio":
        assert original.audio_streams[0]["duration"] == pytest.approx(9.9, abs=0.025)


def _assert_nvdec_matches_cpu_nv12(source, job):
    """Compare native 8-bit decoded samples before RGB matrix conversion."""
    from videoenhancer.media.decode import read_exact

    width, height = job["media"]["width"], job["media"]["height"]
    count = job["media"]["source_frame_count"]
    selected = {0, count // 2, count - 1}
    retained = {}
    decoder = IndexedDecoder(source, job["media"], "cuda", {**job, "decoder": "nvdec"})
    decoder._convert = lambda frame: frame.reshape(-1, frame.shape[-1])[
        : height * 3 // 2, :width
    ].clone()
    frames = decoder.frames(list(range(count)), lambda: False)
    cpu = subprocess.Popen(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-threads",
            "2",
            "-i",
            str(source),
            "-an",
            "-fps_mode",
            "passthrough",
            "-pix_fmt",
            "nv12",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert cpu.stdout is not None
    try:
        for index in range(count):
            raw = read_exact(cpu.stdout, width * height * 3 // 2)
            assert len(raw) == width * height * 3 // 2
            expected = torch.frombuffer(bytearray(raw), dtype=torch.uint8).reshape(
                height * 3 // 2, width
            )
            actual = next(frames).cpu()
            assert torch.equal(actual, expected), f"Native decoded samples differ at frame {index}"
            if index in selected:
                retained[index] = expected.clone()
        assert cpu.stdout.read(1) == b""
        assert cpu.wait(timeout=30) == 0
        for index in sorted(selected, reverse=True):
            actual = next(decoder.frames([index], lambda: False)).cpu()
            assert torch.equal(actual, retained[index]), f"Seek differs at frame {index}"
    finally:
        if cpu.poll() is None:
            cpu.kill()
        cpu.communicate(timeout=30)
        frames.close()
        decoder.close()
