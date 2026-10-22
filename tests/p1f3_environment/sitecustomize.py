"""Explicit Python startup hook for isolated calibration GUI tests only.

Loaded solely by the test's PYTHONPATH, never by application code or packaging.
"""

import os
from pathlib import Path


def install() -> None:
    mode = os.environ.get("VE_P1F3_TEST_ENVIRONMENT")
    home = Path(os.environ.get("VE_HOME", "")).resolve()
    if mode not in {"gpu", "no-gpu"} or "scratch" not in home.parts:
        return

    import videoenhancer.logging as diagnostics

    original = diagnostics.environment_info

    def environment_info() -> dict[str, str]:
        info = original()
        info.pop("gpu", None)
        info.pop("driver", None)
        if mode == "gpu":
            # Match the shipped built-in fixture; the driver is deliberately synthetic.
            info.update(gpu="NVIDIA GeForce RTX 4060 Ti", driver="synthetic-current-driver")
        return info

    diagnostics.environment_info = environment_info


install()
