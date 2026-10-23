"""Spilled calibration measurements must never become timing samples."""

from contextlib import nullcontext
from types import SimpleNamespace


def test_reference_calibration_rejects_spilled_part(tmp_path, monkeypatch):
    from videoenhancer.bench import reference as module

    model = dict(id="synthetic", task="restore", weights_verified=True, architecture="fixture")
    registry = SimpleNamespace(list_models=lambda: [model], snapshot=lambda *a, **k: {})
    monkeypatch.setattr(module, "ModelRegistry", lambda: registry)
    monkeypatch.setattr(module.proc, "run", lambda *a, **k: None)
    monkeypatch.setattr(module, "executable", lambda _: "synthetic")
    monkeypatch.setattr(module, "analyze", lambda *a, **k: {"media": {}})
    monkeypatch.setattr(module, "record_models", lambda *a: {})
    monkeypatch.setattr(module, "get_home", lambda: tmp_path)
    monkeypatch.setattr(module, "process_segment", lambda *a: {"spilled": True})
    result = module.calibrate_references(tmp_path, "synthetic", "cpu")["synthetic:medium"]
    assert result["status"] == "failed"
    assert "spilled into shared GPU memory" in result["reason"]
    assert "seconds" not in result


def test_model_calibration_rejects_spill_and_stops_sampler(monkeypatch):
    from videoenhancer.bench import calibration as module

    stopped = []
    sampler = SimpleNamespace(
        start=lambda: None,
        sample=lambda: None,
        stop=lambda: stopped.append(True),
        spill=SimpleNamespace(spilled=True),
    )
    monkeypatch.setattr("videoenhancer.jobs.gpu_memory.JobMemorySampler", lambda: sampler)
    cuda = SimpleNamespace(
        synchronize=lambda: None,
        reset_peak_memory_stats=lambda: None,
        empty_cache=lambda: None,
        max_memory_reserved=lambda: 0,
        max_memory_allocated=lambda: 0,
    )
    monkeypatch.setattr(
        module,
        "torch",
        SimpleNamespace(
            cuda=cuda,
            float16="fp16",
            float32="fp32",
            Generator=lambda **k: SimpleNamespace(manual_seed=lambda _: None),
            rand=lambda *a, **k: object(),
            inference_mode=nullcontext,
        ),
    )
    stage = SimpleNamespace(
        load=lambda: None, warmup=lambda _: None, process=lambda _: object(), release=lambda: None
    )
    model = dict(
        id="synthetic", task="restore", weights_verified=True, temporal=False, precision="fp16"
    )
    registry = SimpleNamespace(
        list_models=lambda: [model], snapshot=lambda *a: {}, create_stage=lambda *a: stage
    )
    result = module.calibrate_models(registry, backend="cuda", restore_size=(8, 8), repeats=1)[
        "synthetic"
    ]
    assert result["status"] == "failed"
    assert "spilled into shared GPU memory" in result["reason"]
    assert "median_seconds" not in result
    assert stopped == [True]
