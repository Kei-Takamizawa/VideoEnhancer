"""The GUI-only startup hook cannot alter ordinary engine homes."""

import runpy
from pathlib import Path

import pytest

import videoenhancer.logging as diagnostics


@pytest.mark.parametrize(
    ("mode", "isolated", "expected_gpu"),
    [
        ("gpu", True, "NVIDIA GeForce RTX 4060 Ti"),
        ("no-gpu", True, None),
        ("gpu", False, "real GPU"),
        ("no-gpu", False, "real GPU"),
        ("", True, "real GPU"),
    ],
)
def test_gui_environment_hook(monkeypatch, tmp_path, mode, isolated, expected_gpu):
    monkeypatch.setenv("VE_P1F3_TEST_ENVIRONMENT", mode)
    # These paths are only inspected; no non-isolated home is created or read.
    home = tmp_path / "scratch" / "home" if isolated else Path(tmp_path.anchor) / "ordinary-home"
    monkeypatch.setenv("VE_HOME", str(home))
    monkeypatch.setattr(
        diagnostics,
        "environment_info",
        lambda: {"gpu": "real GPU", "driver": "real driver", "os": "test OS"},
    )
    runpy.run_path(str(Path(__file__).parent / "p1f3_environment" / "sitecustomize.py"))
    info = diagnostics.environment_info()
    assert info.get("gpu") == expected_gpu
    assert info["os"] == "test OS"
    if isolated and mode == "gpu":
        assert info["driver"] == "synthetic-current-driver"
    elif isolated and mode == "no-gpu":
        assert "driver" not in info
    else:
        assert info["driver"] == "real driver"
