"""Benchmark Practical-RIFE 4.25 from its official MIT source and model release."""

from __future__ import annotations

import hashlib
import importlib.util
import statistics
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from videoenhancer.config import get_home

SOURCE_COMMIT = "bbfd2ea90910789a860ea3e2b32a240cd577b75e"
SOURCE_URL = f"https://codeload.github.com/hzwer/Practical-RIFE/zip/{SOURCE_COMMIT}"
SOURCE_SHA256 = "88a04ad797a8e831110b771fdcd56b6be4ad66a0ad99c8e82be2a92834bdebc2"
WEIGHTS_URL = "https://drive.google.com/uc?id=1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg"
WEIGHTS_ARCHIVE_SHA256 = "e63d481b7ae5d4a4e6ad7ac5b410ff78f3bf7be3b51b2e38ca8152747abde5b4"
WEIGHT_SHA256 = "6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_drive(path: Path) -> None:
    try:
        import gdown  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise RuntimeError(
            "Install the optional gdown package to fetch the official Google Drive model."
        ) from exc
    temporary = path.with_suffix(path.suffix + ".download")
    try:
        downloaded = gdown.download(
            id="1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg", output=str(temporary), quiet=True
        )
        if not downloaded:
            raise RuntimeError("Google Drive did not return the Practical-RIFE 4.25 archive.")
        actual = _sha256(temporary)
        if actual != WEIGHTS_ARCHIVE_SHA256:
            raise RuntimeError(f"Practical-RIFE archive SHA-256 mismatch: {actual}")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _prepare_files() -> tuple[Path, Path]:
    models = get_home() / "models"
    models.mkdir(parents=True, exist_ok=True)
    source_archive = models / "practical-rife-source.zip"
    if not source_archive.is_file() or _sha256(source_archive) != SOURCE_SHA256:
        source_archive.unlink(missing_ok=True)
        temporary = source_archive.with_suffix(".zip.download")
        try:
            with (
                urllib.request.urlopen(SOURCE_URL, timeout=90) as response,
                temporary.open("wb") as sink,
            ):
                while chunk := response.read(1024 * 1024):
                    sink.write(chunk)
            if _sha256(temporary) != SOURCE_SHA256:
                raise RuntimeError("Practical-RIFE source archive SHA-256 mismatch.")
            temporary.replace(source_archive)
        finally:
            temporary.unlink(missing_ok=True)
    source_root = models / f"Practical-RIFE-{SOURCE_COMMIT}"
    marker = source_root / ".videoenhancer-source-sha256"
    if not marker.is_file() or marker.read_text(encoding="ascii") != SOURCE_SHA256:
        source_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source_archive) as archive:
            for member in archive.infolist():
                target = (models / member.filename).resolve()
                if not target.is_relative_to(source_root.resolve()):
                    raise RuntimeError(
                        "Pinned Practical-RIFE source archive contains an unsafe path."
                    )
            archive.extractall(models)
        marker.write_text(SOURCE_SHA256, encoding="ascii")
    weight_archive = models / "RIFEv4.25_0919.zip"
    if not weight_archive.is_file() or _sha256(weight_archive) != WEIGHTS_ARCHIVE_SHA256:
        weight_archive.unlink(missing_ok=True)
        _download_drive(weight_archive)
    checkpoint = models / "rife425_flownet.pkl"
    if not checkpoint.is_file() or _sha256(checkpoint) != WEIGHT_SHA256:
        with zipfile.ZipFile(weight_archive) as archive:
            temporary = checkpoint.with_suffix(".pkl.extracting")
            try:
                with archive.open("train_log/flownet.pkl") as source, temporary.open("wb") as sink:
                    while chunk := source.read(1024 * 1024):
                        sink.write(chunk)
                if _sha256(temporary) != WEIGHT_SHA256:
                    raise RuntimeError("Practical-RIFE checkpoint SHA-256 mismatch.")
                temporary.replace(checkpoint)
            finally:
                temporary.unlink(missing_ok=True)
    architecture = models / "rife425_source" / "train_log" / "IFNet_HDv3.py"
    architecture.parent.mkdir(parents=True, exist_ok=True)
    if not architecture.is_file():
        with zipfile.ZipFile(weight_archive) as archive:
            architecture.write_bytes(archive.read("train_log/IFNet_HDv3.py"))
    return source_root, checkpoint


def load_rife_model(torch: Any | None = None) -> Any:
    """Load Practical-RIFE 4.25 from its pinned external source and weights."""
    if torch is None:
        import torch as torch_module

        torch = torch_module
    source_root, checkpoint = _prepare_files()
    code_root = checkpoint.parent / "rife425_source"
    external_root = source_root / f"Practical-RIFE-{SOURCE_COMMIT}"
    if not external_root.is_dir():
        external_root = source_root
    sys.path.insert(0, str(external_root))
    sys.path.insert(0, str(code_root))
    module_path = code_root / "train_log" / "IFNet_HDv3.py"
    spec = importlib.util.spec_from_file_location("ve_external_rife425_ifnet", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load the official RIFE 4.25 IFNet module.")
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import torch.nn.functional as functional

    warplayer: Any = importlib.import_module("model.warplayer")

    def half_warp(image: Any, flow: Any) -> Any:
        height, width = flow.shape[-2:]
        horizontal = torch.linspace(-1.0, 1.0, width, device=flow.device, dtype=image.dtype)
        horizontal = horizontal.view(1, 1, 1, width).expand(flow.shape[0], -1, height, -1)
        vertical = torch.linspace(-1.0, 1.0, height, device=flow.device, dtype=image.dtype)
        vertical = vertical.view(1, 1, height, 1).expand(flow.shape[0], -1, -1, width)
        grid = torch.cat((horizontal, vertical), 1)
        normalized = torch.cat(
            (
                flow[:, 0:1] / ((image.shape[3] - 1.0) / 2.0),
                flow[:, 1:2] / ((image.shape[2] - 1.0) / 2.0),
            ),
            1,
        )
        return functional.grid_sample(
            image,
            (grid + normalized).permute(0, 2, 3, 1),
            mode="bilinear",
            padding_mode="border",
            align_corners=True,
        )

    warplayer.warp = half_warp
    module.warp = half_warp
    network = module.IFNet().eval()
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = {
        key.removeprefix("module."): value
        for key, value in state.items()
        if not key.startswith(("module.teacher.", "module.caltime."))
    }
    loaded = network.load_state_dict(state, strict=False)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError("The official checkpoint did not match the Practical-RIFE architecture.")
    return network


def bench_rife(torch: Any) -> dict[str, Any]:
    common: dict[str, Any] = {
        "name": "Practical-RIFE 4.25",
        "license": "MIT",
        "source_url": "https://github.com/hzwer/Practical-RIFE",
        "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCE_SHA256,
        "weights_url": "https://drive.google.com/file/d/1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg/view",
        "expected_sha256": WEIGHT_SHA256,
        "weights_archive_sha256": WEIGHTS_ARCHIVE_SHA256,
        "checksum_provenance": (
            "Pinned after first acquisition from the official source and release links over HTTPS."
        ),
        "source_resolution": "1080x1920",
        "input_shape": [1, 6, 1920, 1088],
        "horizontal_padding_pixels": 8,
        "batch_size": 1,
        "precision": "float16",
        "torch_inference_mode": True,
    }
    try:
        source_root, checkpoint = _prepare_files()
        external_root = source_root / f"Practical-RIFE-{SOURCE_COMMIT}"
        if not external_root.is_dir():
            external_root = source_root
        code_root = checkpoint.parent / "rife425_source"
        sys.path.insert(0, str(external_root))
        sys.path.insert(0, str(code_root))
        module_path = code_root / "train_log" / "IFNet_HDv3.py"
        spec = importlib.util.spec_from_file_location("ve_external_rife425_ifnet", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("Could not load the official RIFE 4.25 IFNet module.")
        module: Any = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Upstream warplayer caches FP32 coordinate grids. Its addition with the
        # FP16 flow promotes `grid`, which grid_sample rejects against FP16 input.
        import torch.nn.functional as functional

        warplayer: Any = importlib.import_module("model.warplayer")

        def half_warp(image: Any, flow: Any) -> Any:
            height, width = flow.shape[-2:]
            horizontal = (
                torch.linspace(-1.0, 1.0, width, device=flow.device, dtype=image.dtype)
                .view(1, 1, 1, width)
                .expand(flow.shape[0], -1, height, -1)
            )
            vertical = (
                torch.linspace(-1.0, 1.0, height, device=flow.device, dtype=image.dtype)
                .view(1, 1, height, 1)
                .expand(flow.shape[0], -1, -1, width)
            )
            grid = torch.cat((horizontal, vertical), 1)
            normalized = torch.cat(
                (
                    flow[:, 0:1] / ((image.shape[3] - 1.0) / 2.0),
                    flow[:, 1:2] / ((image.shape[2] - 1.0) / 2.0),
                ),
                1,
            )
            return functional.grid_sample(
                image,
                (grid + normalized).permute(0, 2, 3, 1),
                mode="bilinear",
                padding_mode="border",
                align_corners=True,
            )

        warplayer.warp = half_warp
        module.warp = half_warp
        network = module.IFNet().eval().cuda().half()
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        state = {
            key.removeprefix("module."): value
            for key, value in state.items()
            if not key.startswith(("module.teacher.", "module.caltime."))
        }
        loaded = network.load_state_dict(state, strict=False)
        if loaded.missing_keys or loaded.unexpected_keys:
            raise RuntimeError(
                "The official checkpoint did not match the Practical-RIFE IFNet architecture."
            )
        # RIFE's encoder downsamples three times. Pad to a multiple of 32 so
        # transposed convolutions and pyramid warps return matching geometry.
        sample = torch.rand((1, 6, 1920, 1088), device="cuda", dtype=torch.float16)
        with torch.inference_mode():
            for _ in range(10):
                network(sample, scale_list=[8, 4, 2, 1, 1], fastmode=True)
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            timings: list[float] = []
            for _ in range(50):
                start = time.perf_counter()
                network(sample, scale_list=[8, 4, 2, 1, 1], fastmode=True)
                torch.cuda.synchronize()
                timings.append((time.perf_counter() - start) * 1000)
        ordered = sorted(timings)
        return {
            **common,
            "status": "measured",
            "backend": "Practical-RIFE IFNet; external original source",
            "sha256": _sha256(checkpoint),
            "median_ms": statistics.median(timings),
            "p90_ms": ordered[int(0.9 * (len(ordered) - 1))],
            "iterations": len(timings),
            "warmup_iterations": 10,
            "peak_vram_bytes": int(torch.cuda.max_memory_reserved()),
            "tile": "whole frame",
        }
    except Exception as exc:
        return {
            **common,
            "status": "skipped",
            "reason": f"RIFE benchmark unavailable or failed: {type(exc).__name__}: {exc}",
        }
