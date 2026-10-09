"""Contract checks for benchmark report shape and safe model selection."""

import sys
from types import SimpleNamespace

import numpy as np
import torch

from videoenhancer.bench.runner import MODEL_CATALOG, _bench_models, _bench_nvenc


def test_nvenc_benchmark_input_mode_matches_owned_host_buffers(monkeypatch):
    encoders = []

    class FakeEncoder:
        def __init__(self, width, height, color_format, host_input, **settings):
            assert host_input is True
            assert "cudastream" not in settings
            self.calls = 0
            encoders.append(self)

        def Encode(self, surface):
            assert isinstance(surface, np.ndarray)
            assert surface.flags.c_contiguous
            assert surface.dtype == np.uint8
            self.calls += 1
            return b"encoded"

        def EndEncode(self):
            return b"tail"

    fake_cuda = SimpleNamespace(
        current_stream=lambda: SimpleNamespace(synchronize=lambda: None, cuda_stream=123),
        synchronize=lambda: None,
        max_memory_allocated=lambda: 0,
    )
    fake_torch = SimpleNamespace(
        rand=lambda *args, **kwargs: torch.zeros((3, 8, 8), dtype=torch.float16),
        float16=torch.float16,
        uint16=torch.uint16,
        uint8=torch.uint8,
        cuda=fake_cuda,
        inference_mode=torch.inference_mode,
    )
    monkeypatch.setitem(sys.modules, "PyNvVideoCodec", SimpleNamespace(CreateEncoder=FakeEncoder))

    result = _bench_nvenc(fake_torch)

    assert set(result) == {"hevc_main10", "h264", "av1"}
    assert all(item["status"] == "measured" for item in result.values()), result
    assert len(encoders) == 3
    assert all(encoder.calls == 68 for encoder in encoders)


def test_model_candidates_have_sources_and_explicit_hash_state() -> None:
    results = _bench_models("all", gpu_available=True)
    assert set(results) == set(MODEL_CATALOG)
    for key, result in results.items():
        assert result["status"] == "skipped"
        assert result["source_url"].startswith("https://")
        assert result["weights_url"].startswith("https://")
        assert result["sha256"] == MODEL_CATALOG[key].get("sha256")
        if result["status"] == "skipped":
            assert result["reason"].strip()


def test_model_candidates_explain_missing_cuda() -> None:
    result = _bench_models("rife", gpu_available=False)["rife"]
    assert result["status"] == "skipped"
    assert "CUDA" in result["reason"]
