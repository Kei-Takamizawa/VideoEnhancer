"""Long-run memory comparisons use one epoch clock and separated windows."""

import importlib.util
from pathlib import Path


def test_memory_growth_ignores_startup_and_compares_window_peaks():
    source = Path(__file__).parents[1] / "scripts" / "soak.py"
    spec = importlib.util.spec_from_file_location("soak_helper", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    epoch = 1_790_000_000.0
    records = [
        {"timestamp": epoch + t, "memory": value}
        for t, value in ((0, 999), (601, 100), (900, 120), (1200, 110), (1800, 135))
    ]
    assert module._memory_growth(records, "memory", epoch) == 15
    assert module._memory_growth(records[:3], "memory", epoch) is None


def test_process_exit_during_sample_does_not_abort_supervisor(monkeypatch):
    source = Path(__file__).parents[1] / "scripts" / "soak.py"
    spec = importlib.util.spec_from_file_location("soak_helper", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def exited(pid):
        raise module.psutil.NoSuchProcess(pid)

    monkeypatch.setattr(module.psutil, "Process", exited)
    assert module._tree_rss(1234) == 0
