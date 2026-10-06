"""Pinned BasicVSR++ benchmark using external Apache-licensed source and weights.

The official MMagic source is loaded from VE_HOME/models at benchmark time. Its
MMCV deformable convolution is connected to the prebuilt torchvision operator;
no original source or compiled extension is added to this repository.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import statistics
import sys
import time
import types
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from videoenhancer.config import get_home

COMMIT = "0a560bba9b79ebe78574e1d4cbbdd0e798e63568"
CODE_URL = f"https://codeload.github.com/open-mmlab/mmagic/zip/{COMMIT}"
CODE_SHA256 = "faf15899d1a558a80a2b835e9efc1dff517d27070b06b3f265258ae0adceb9b1"
WEIGHTS_URL = (
    "https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/"
    "basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth"
)
WEIGHTS_SHA256 = "6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a"
SOURCE_NAME = f"mmagic-{COMMIT}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_download(path: Path, url: str, expected: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and _sha256(path) == expected:
        return path
    path.unlink(missing_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as sink:
            while chunk := response.read(1024 * 1024):
                sink.write(chunk)
        observed = _sha256(temporary)
        if observed != expected:
            raise ValueError(f"SHA-256 mismatch for {path.name}: {observed}")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _source_files(models: Path) -> tuple[Path, Path]:
    archive = _verified_download(models / "mmagic-code.zip", CODE_URL, CODE_SHA256)
    root = models / SOURCE_NAME
    basic = root / "mmagic/models/editors/basicvsr/basicvsr_net.py"
    plus = root / "mmagic/models/editors/basicvsr_plusplus_net/basicvsr_plusplus_net.py"
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.namelist()
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in members):
            raise ValueError("Pinned MMagic archive contains an unsafe path")
        if not basic.is_file() or not plus.is_file():
            bundle.extractall(models)
        for path in (basic, plus):
            archive_name = f"{SOURCE_NAME}/{path.relative_to(root).as_posix()}"
            if path.read_bytes() != bundle.read(archive_name):
                raise ValueError(f"External MMagic source differs from pinned archive: {path}")
    return basic, plus


def _helpers(torch: Any) -> dict[str, Any]:
    nn, functional = torch.nn, torch.nn.functional
    deform_conv2d = importlib.import_module("torchvision.ops").__dict__["deform_conv2d"]

    class ConvModule(nn.Module):
        def __init__(
            self,
            in_channels: int,
            out_channels: int,
            kernel_size: int,
            stride: int,
            padding: int,
            norm_cfg: Any = None,
            act_cfg: dict[str, Any] | None = None,
        ) -> None:
            super().__init__()
            if norm_cfg is not None:
                raise ValueError(
                    "BasicVSR++ adapter only supports unnormalized SPyNet convolutions"
                )
            self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding)
            self.activate = nn.ReLU(inplace=True) if act_cfg else nn.Identity()

        def forward(self, x: Any) -> Any:
            return self.activate(self.conv(x))

    class ResidualBlockNoBN(nn.Module):
        def __init__(self, mid_channels: int = 64, res_scale: float = 1.0) -> None:
            super().__init__()
            self.res_scale = res_scale
            self.conv1 = nn.Conv2d(mid_channels, mid_channels, 3, padding=1)
            self.conv2 = nn.Conv2d(mid_channels, mid_channels, 3, padding=1)
            self.relu = nn.ReLU(inplace=True)

        def forward(self, x: Any) -> Any:
            return x + self.conv2(self.relu(self.conv1(x))) * self.res_scale

    class PixelShufflePack(nn.Module):
        def __init__(
            self, in_channels: int, out_channels: int, scale_factor: int, upsample_kernel: int
        ) -> None:
            super().__init__()
            self.scale_factor = scale_factor
            self.upsample_conv = nn.Conv2d(
                in_channels,
                out_channels * scale_factor * scale_factor,
                upsample_kernel,
                padding=(upsample_kernel - 1) // 2,
            )

        def forward(self, x: Any) -> Any:
            return functional.pixel_shuffle(self.upsample_conv(x), self.scale_factor)

    class ModulatedDeformConv2d(nn.Module):
        def __init__(
            self,
            in_channels: int,
            out_channels: int,
            kernel_size: int,
            stride: int = 1,
            padding: int = 0,
            dilation: int = 1,
            groups: int = 1,
            deform_groups: int = 1,
            bias: bool = True,
        ) -> None:
            super().__init__()
            self.out_channels = out_channels
            self.deform_groups = deform_groups
            self.stride = stride
            self.padding = padding
            self.dilation = dilation
            self.groups = groups
            self.weight = nn.Parameter(
                torch.empty(out_channels, in_channels // groups, kernel_size, kernel_size)
            )
            self.bias = nn.Parameter(torch.zeros(out_channels)) if bias else None

    def modulated_deform_conv2d(
        x: Any,
        offset: Any,
        mask: Any,
        weight: Any,
        bias: Any,
        stride: Any,
        padding: Any,
        dilation: Any,
        _groups: Any,
        _deform_groups: Any,
    ) -> Any:
        return deform_conv2d(x, offset, weight, bias, stride, padding, dilation, mask=mask)

    def flow_warp(
        x: Any,
        flow: Any,
        interpolation: str = "bilinear",
        padding_mode: str = "zeros",
        align_corners: bool = True,
    ) -> Any:
        height, width = x.shape[-2:]
        if tuple(flow.shape[1:3]) != (height, width):
            raise ValueError("Optical flow and feature geometry differ")
        y, xcoord = torch.meshgrid(
            torch.arange(height, device=x.device, dtype=x.dtype),
            torch.arange(width, device=x.device, dtype=x.dtype),
            indexing="ij",
        )
        grid = torch.stack((xcoord, y), dim=-1) + flow
        grid_x = 2 * grid[..., 0] / max(width - 1, 1) - 1
        grid_y = 2 * grid[..., 1] / max(height - 1, 1) - 1
        normalized = torch.stack((grid_x, grid_y), dim=-1)
        return functional.grid_sample(
            x,
            normalized,
            mode=interpolation,
            padding_mode=padding_mode,
            align_corners=align_corners,
        )

    def constant_init(module: Any, val: float = 0, bias: float = 0) -> None:
        nn.init.constant_(module.weight, val)
        if module.bias is not None:
            nn.init.constant_(module.bias, bias)

    return {
        "ConvModule": ConvModule,
        "ResidualBlockNoBN": ResidualBlockNoBN,
        "PixelShufflePack": PixelShufflePack,
        "ModulatedDeformConv2d": ModulatedDeformConv2d,
        "modulated_deform_conv2d": modulated_deform_conv2d,
        "flow_warp": flow_warp,
        "constant_init": constant_init,
        "make_layer": lambda block, count, **kwargs: nn.Sequential(
            *(block(**kwargs) for _ in range(count))
        ),
    }


@contextmanager
def _temporary_modules(helpers: dict[str, Any], torch: Any) -> Iterator[None]:
    names = (
        "mmcv",
        "mmcv.cnn",
        "mmcv.ops",
        "mmengine",
        "mmengine.model",
        "mmengine.model.weight_init",
        "mmengine.runner",
        "mmagic",
        "mmagic.models",
        "mmagic.models.archs",
        "mmagic.models.utils",
        "mmagic.models.editors",
        "mmagic.models.editors.basicvsr",
        "mmagic.models.editors.basicvsr.basicvsr_net",
        "mmagic.models.editors.basicvsr_plusplus_net",
        "mmagic.models.editors.basicvsr_plusplus_net.basicvsr_plusplus_net",
        "mmagic.registry",
    )
    previous = {name: sys.modules.get(name) for name in names}
    try:
        for name in names:
            module = types.ModuleType(name)
            if name in {
                "mmcv",
                "mmengine",
                "mmengine.model",
                "mmagic",
                "mmagic.models",
                "mmagic.models.editors",
                "mmagic.models.editors.basicvsr",
                "mmagic.models.editors.basicvsr_plusplus_net",
            }:
                module.__path__ = []
            sys.modules[name] = module

        sys.modules["mmcv.cnn"].__dict__.update(ConvModule=helpers["ConvModule"])
        sys.modules["mmcv.ops"].__dict__.update(
            ModulatedDeformConv2d=helpers["ModulatedDeformConv2d"],
            modulated_deform_conv2d=helpers["modulated_deform_conv2d"],
        )
        sys.modules["mmengine"].__dict__.update(
            MMLogger=type("MMLogger", (), {"get_current_instance": staticmethod(lambda: None)}),
            print_log=lambda *_args, **_kwargs: None,
        )
        sys.modules["mmengine.model"].__dict__.update(BaseModule=torch.nn.Module)
        sys.modules["mmengine.model.weight_init"].__dict__.update(
            constant_init=helpers["constant_init"]
        )
        sys.modules["mmengine.runner"].__dict__.update(
            load_checkpoint=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("External SPyNet checkpoint loading is disabled")
            )
        )
        sys.modules["mmagic.models.archs"].__dict__.update(
            PixelShufflePack=helpers["PixelShufflePack"],
            ResidualBlockNoBN=helpers["ResidualBlockNoBN"],
        )
        sys.modules["mmagic.models.utils"].__dict__.update(
            flow_warp=helpers["flow_warp"], make_layer=helpers["make_layer"]
        )

        class Registry:
            def register_module(self, module: Any = None, **_kwargs: Any) -> Any:
                if module is None:
                    return lambda item: item
                return module

        sys.modules["mmagic.registry"].__dict__.update(MODELS=Registry())
        yield
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _load_source(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load pinned external source: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _model_from_checkpoint(torch: Any, basic_path: Path, plus_path: Path, weights: Path) -> Any:
    helpers = _helpers(torch)
    with _temporary_modules(helpers, torch):
        _load_source("mmagic.models.editors.basicvsr.basicvsr_net", basic_path)
        module = _load_source(
            "mmagic.models.editors.basicvsr_plusplus_net.basicvsr_plusplus_net", plus_path
        )
        model = module.BasicVSRPlusPlusNet(
            mid_channels=128,
            num_blocks=25,
            is_low_res_input=False,
            cpu_cache_length=0,
        )
    checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    state = checkpoint["state_dict"]
    if not isinstance(state, dict) or not all(
        key.startswith("generator.") for key in state if key != "step_counter"
    ):
        raise ValueError("Checkpoint does not contain the expected BasicVSR++ generator weights")
    generator = {
        key.removeprefix("generator."): value
        for key, value in state.items()
        if key.startswith("generator.")
    }
    model.load_state_dict(generator, strict=True)
    return model


def bench_basicvsr(torch: Any) -> dict[str, Any]:
    """Time 50 FP16 15-frame clips at the largest tile that fits the GPU."""
    result: dict[str, Any] = {
        "name": "BasicVSR++ NTIRE 2021 compressed-video enhancement",
        "license": "Apache-2.0",
        "source_url": CODE_URL,
        "source_sha256": CODE_SHA256,
        "weights_url": WEIGHTS_URL,
        "sha256": WEIGHTS_SHA256,
        "precision": "float16",
        "source_resolution": "720x1280 (width x height)",
        "input_shape": [1, 15, 3, 1280, 720],
        "adapter": "torchvision.ops.deform_conv2d; pinned external MMagic source",
    }
    if torch is None or not torch.cuda.is_available():
        return {**result, "status": "skipped", "reason": "CUDA is unavailable"}
    models = get_home() / "models"
    try:
        basic_path, plus_path = _source_files(models)
        weights = _verified_download(
            models / "basicvsrpp-ntire-track3.pth", WEIGHTS_URL, WEIGHTS_SHA256
        )
        model = _model_from_checkpoint(torch, basic_path, plus_path, weights).eval().cuda().half()
    except Exception as error:
        return {
            **result,
            "status": "skipped",
            "reason": f"Pinned model load failed: {type(error).__name__}: {error}",
        }

    failures: list[dict[str, Any]] = []
    chosen: tuple[int, int, int] | None = None
    sample = None
    try:
        for frames, height, width in (
            (15, 1280, 720),
            (15, 1024, 576),
            (15, 768, 432),
            (15, 512, 288),
            (15, 384, 216),
            (15, 256, 144),
            (7, 256, 144),
        ):
            try:
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                sample = torch.rand(
                    (1, frames, 3, height, width), device="cuda", dtype=torch.float16
                )
                with torch.inference_mode():
                    output = model(sample)
                torch.cuda.synchronize()
                del output
                chosen = (frames, height, width)
                break
            except torch.cuda.OutOfMemoryError as error:
                failures.append(
                    {"frames": frames, "tile": [height, width], "reason": str(error)[:200]}
                )
                sample = None
                torch.cuda.empty_cache()
        if chosen is None or sample is None:
            return {
                **result,
                "status": "skipped",
                "reason": "No tile or clip fit GPU memory",
                "attempts": failures,
            }
        with torch.inference_mode():
            for _ in range(5):
                model(sample)
            torch.cuda.synchronize()
            times = []
            torch.cuda.reset_peak_memory_stats()
            for _ in range(50):
                started = time.perf_counter()
                model(sample)
                torch.cuda.synchronize()
                times.append((time.perf_counter() - started) * 1000)
        ordered = sorted(times)
        return {
            **result,
            "status": "measured",
            "input_shape": [1, chosen[0], 3, chosen[1], chosen[2]],
            "inference_resolution": f"{chosen[2]}x{chosen[1]} (width x height)",
            "tile": [chosen[1], chosen[2]],
            "clip_frames": chosen[0],
            "batch_size": 1,
            "iterations": len(times),
            "warmup_iterations": 5,
            "median_ms": statistics.median(times),
            "p90_ms": ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))],
            "peak_vram_bytes": int(torch.cuda.max_memory_reserved()),
            "cpu_feature_cache": True,
            "attempts": failures,
        }
    except Exception as error:
        return {
            **result,
            "status": "skipped",
            "reason": f"Inference failed: {type(error).__name__}: {error}",
            "attempts": failures,
        }
    finally:
        del model
        del sample
        torch.cuda.empty_cache()
