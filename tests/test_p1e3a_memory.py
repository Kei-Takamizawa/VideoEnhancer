"""Memory caps preserve fallback order and exclude spilled samples."""

from types import SimpleNamespace

import pytest
import torch

from videoenhancer.jobs.gpu_budget import budget_fraction, run_with_budget
from videoenhancer.jobs.gpu_memory import SpillTracker
from videoenhancer.schedule.controller import SegmentWatchdog


@pytest.mark.parametrize(
    "free,total,reserve,expected", [(80, 100, 10, 0.7), (5, 100, 10, 0), (200, 100, 0, 1)]
)
def test_budget_uses_free_memory_less_measured_reserve(free, total, reserve, expected):
    assert budget_fraction(free, total, reserve) == expected


@pytest.mark.parametrize("stage", ["restore", "rife", "decoder-retried"])
def test_oom_order_preserves_half_retry_then_runs_once_without_cap(stage):
    events = []
    cuda = SimpleNamespace(
        fraction=1.0,
        mem_get_info=lambda: (800, 1000),
        empty_cache=lambda: None,
        get_per_process_memory_fraction=lambda: cuda.fraction,
    )
    cuda.set_per_process_memory_fraction = lambda value: setattr(cuda, "fraction", value)

    def run(progress):
        events.append((stage, cuda.fraction))
        if cuda.fraction < 1:
            if stage == "restore":
                events.append(("half-clip", cuda.fraction))
                progress({"oom_retries": 1})
            raise torch.cuda.OutOfMemoryError("synthetic CUDA OOM")
        return {"output": b"unchanged"}

    result = run_with_budget(run, enabled=True, cuda=cuda)
    assert result["output"] == b"unchanged"
    assert result["uncapped_re_runs"] == 1
    assert result["ran_over_gpu_memory"]
    assert events[-1] == (stage, 1.0)
    assert result["capped_oom_retries"] == int(stage == "restore")
    assert cuda.fraction == 1.0


def test_non_oom_is_not_hidden_by_cap():
    with pytest.raises(ValueError, match="bad input"):
        run_with_budget(lambda _: (_ for _ in ()).throw(ValueError("bad input")), enabled=False)


def test_fake_counter_stream_and_unavailable_detection():
    tracker = SpillTracker()
    tracker.observe(None, None)
    assert tracker.spilled is None
    tracker.observe(100, 50)
    tracker.observe(200, 50 + 256_000_000)
    assert tracker.spilled is False
    tracker.observe(300, 51 + 256_000_000)
    tracker.observe(150, 50)
    assert tracker.spilled is True
    assert tracker.peak_dedicated == 300


def test_spill_scales_wall_time_but_keeps_no_new_frame_rule():
    watchdog = SegmentWatchdog(10, 100, 0)
    watchdog.progress(1, 340)
    assert watchdog.reason(340) == "wall time"
    watchdog.spilled = True
    assert watchdog.reason(340) is None
    assert watchdog.reason(521) == "no new frame"


def test_spilled_completion_is_not_learned(tmp_path):
    from videoenhancer.estimate.local import record_completed

    path = tmp_path / "timing-observations.json"
    path.write_text('{"original":true}', encoding="utf-8")
    record_completed({"segments": [{"stats": {"spilled": True}}]}, tmp_path)
    assert path.read_text() == '{"original":true}'


def test_direct_counter_failure_uses_fallback_and_labels_source(monkeypatch):
    from videoenhancer.jobs.gpu_memory import JobMemorySampler

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    sampler = JobMemorySampler.__new__(JobMemorySampler)
    sampler._pdh = SimpleNamespace(
        read=lambda _: (_ for _ in ()).throw(OSError("counter failed")), close=lambda: None
    )
    sampler.counter_source = "PDH ctypes"
    sampler.spill = SpillTracker()
    sampler._nvml = None
    sampler.samples = []
    sampler.on_sample = None
    monkeypatch.setattr(sampler, "_dedicated_bytes", lambda _: 100)
    monkeypatch.setattr(sampler, "_windows_bytes", lambda *args: 50)
    assert sampler.sample()["counter_source"] == "PowerShell fallback"


def test_unsupported_cap_does_not_fail_a_runnable_part():
    def unavailable(_):
        raise RuntimeError("Allocator cap unavailable")

    cuda = SimpleNamespace(
        mem_get_info=lambda: (800, 1000),
        get_per_process_memory_fraction=lambda: 1.0,
        set_per_process_memory_fraction=unavailable,
    )
    result = run_with_budget(lambda _: {"output": b"unchanged"}, enabled=True, cuda=cuda)
    assert result["output"] == b"unchanged"
    assert result["gpu_cap_on"] is False
    assert result["gpu_budget"]["unavailable_reason"] == "Allocator cap unavailable"
