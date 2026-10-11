"""Data-only model manifests and repository-owned architecture adapters."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from videoenhancer.config import get_home
from videoenhancer.pipeline.stages import Stage

C1 = "basicvsrpp-ntire21-decompress"
RIFE = "rife-4.25"
BUILTINS = {path.stem for path in (Path(__file__).parent / "manifests").glob("*.json")}
AdapterFactory = Callable[[dict[str, Any], Path, dict[str, Any], Fraction, set[int]], Stage]
ADAPTERS: dict[str, tuple[str, AdapterFactory]] = {}


def register_adapter(name: str, task: str, factory: AdapterFactory) -> None:
    """Register trusted repository code, never a path from a manifest."""
    if name in ADAPTERS:
        raise ValueError(f"Adapter already registered: {name}")
    if task not in {"restore", "interpolate", "size"}:
        raise ValueError(f"Unsupported adapter task: {task}")
    ADAPTERS[name] = (task, factory)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", value):
        raise ValueError("Model id must contain lowercase letters, digits, '.', '_' or '-'.")
    if value.split(".")[0] in {
        "con",
        "prn",
        "aux",
        "nul",
        *[f"com{i}" for i in range(1, 10)],
        *[f"lpt{i}" for i in range(1, 10)],
    } or value.endswith("."):
        raise ValueError("Model id is a reserved Windows filename.")
    return value


def validate_manifest(value: Any, task: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Model manifest must be a JSON object.")
    required = {
        "id",
        "display_name",
        "version",
        "description",
        "task",
        "architecture",
        "architecture_params",
        "weights",
        "licence",
        "commercial_use_allowed",
        "scale",
        "temporal",
        "precision",
    }
    missing = required - value.keys()
    if missing:
        raise ValueError(f"Model manifest missing fields: {', '.join(sorted(missing))}")
    _id(value["id"])
    for field in ("display_name", "version", "description", "licence", "architecture"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"Model manifest {field} must be nonempty text.")
    if value["task"] not in {"restore", "interpolate", "size"}:
        raise ValueError("Model task must be restore, interpolate or size.")
    if task is not None and value["task"] != task:
        raise ValueError(f"Model {value['id']} has task {value['task']}; expected {task}.")
    adapter = ADAPTERS.get(value["architecture"])
    if adapter is None:
        raise ValueError(f"Unknown model adapter: {value['architecture']}")
    if adapter[0] != value["task"]:
        raise ValueError(f"Adapter {value['architecture']} requires task {adapter[0]}.")
    for field in ("commercial_use_allowed", "temporal"):
        if type(value[field]) is not bool:
            raise ValueError(f"Model manifest {field} must be a boolean.")
    if type(value["scale"]) is not int or value["scale"] not in (
        {2, 4} if value["task"] == "size" else {1}
    ):
        raise ValueError(
            "Restoration and interpolation require scale=1; size requires scale=2 or 4."
        )
    if value["precision"] not in {"fp16", "fp32"}:
        raise ValueError("Model precision must be fp16 or fp32.")
    params = value["architecture_params"]
    if not isinstance(params, dict):
        raise ValueError("architecture_params must be an object.")
    if value["architecture"] == "basicvsrpp":
        if set(params) - {"mid_channels", "num_blocks"}:
            raise ValueError("BasicVSR++ accepts only mid_channels and num_blocks.")
        if any(type(number) is not int or number < 1 for number in params.values()):
            raise ValueError("BasicVSR++ architecture parameters must be positive integers.")
    elif value["architecture"] in {"spandrel", "drunet", "spandrel-size"}:
        allowed = {"tile_size", "tile_overlap"}
        if value["architecture"] == "drunet":
            allowed.add("quality_factor")
            if params.get("quality_factor") not in {50, 30, 10}:
                raise ValueError("DRUNet quality factor must be 50, 30 or 10.")
        if set(params) - allowed or any(type(n) is not int or n < 0 for n in params.values()):
            raise ValueError("Invalid single-frame architecture parameters.")
        if params.get("tile_size", 256) < 64 or params.get("tile_overlap", 32) >= params.get(
            "tile_size", 256
        ):
            raise ValueError("Tile size must be at least 64 and larger than overlap.")
    elif value["architecture"] == "rife" and params:
        if set(params) != {"variant"} or params["variant"] not in {"4.26", "4.25-lite"}:
            raise ValueError("Unknown pinned RIFE variant.")
    if value["architecture"] in {"spandrel", "drunet", "spandrel-size"} and value["temporal"]:
        raise ValueError("Spandrel restoration is single-frame; temporal must be false.")
    if value["architecture"] in {"basicvsrpp", "rife"} and not value["temporal"]:
        raise ValueError("BasicVSR++ and RIFE require temporal=true.")
    if value["temporal"]:
        length, overlap = value.get("clip_length"), value.get("clip_overlap")
        if (
            type(length) is not int
            or type(overlap) is not int
            or length < 1
            or overlap < 0
            or 2 * overlap >= length
        ):
            raise ValueError("Temporal models require clip_length > 2 * clip_overlap >= 0.")
    weights = value["weights"]
    if not isinstance(weights, dict) or not {"filename", "sha256"} <= weights.keys():
        raise ValueError("weights requires filename and sha256.")
    filename = weights["filename"]
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or any(char in filename for char in "/\\:")
        or filename.endswith((".", " "))
    ):
        raise ValueError("weights.filename must be a plain filename, without a path.")
    if not isinstance(weights["sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", weights["sha256"]
    ):
        raise ValueError("weights.sha256 must contain 64 lowercase hexadecimal digits.")
    if "url" in weights:
        url = weights["url"]
        if not isinstance(url, str) or urlparse(url).scheme != "https" or not urlparse(url).netloc:
            raise ValueError("weights.url must be an HTTPS URL.")
    archive = weights.get("archive")
    if archive:
        if not isinstance(archive, dict) or not re.fullmatch(
            r"[0-9a-f]{64}", archive.get("sha256", "")
        ):
            raise ValueError("Publisher archive requires its pinned SHA-256.")
        member = archive.get("member", "")
        if (
            not isinstance(member, str)
            or not member
            or Path(member).is_absolute()
            or ".." in Path(member).parts
        ):
            raise ValueError("Publisher archive member must be a safe relative path.")
    blend = weights.get("blend")
    if blend:
        if value["architecture"] != "spandrel-size" or not isinstance(blend, dict):
            raise ValueError("Only the size adapter supports a blend checkpoint.")
        filename = blend.get("filename", "")
        if (
            not filename
            or filename in {".", ".."}
            or any(char in filename for char in "/\\:")
            or filename.endswith((".", " "))
        ):
            raise ValueError("Blend weights filename must be a plain filename.")
        if (
            not re.fullmatch(r"[0-9a-f]{64}", blend.get("sha256", ""))
            or urlparse(blend.get("url", "")).scheme != "https"
        ):
            raise ValueError("Blend weights require SHA-256 and an HTTPS publisher URL.")
    estimates = value.get("vram_estimate_mb", {})
    if not isinstance(estimates, dict) or any(
        not isinstance(key, str)
        or type(number) not in {float, int}
        or not math.isfinite(number)
        or number < 0
        for key, number in estimates.items()
    ):
        raise ValueError("vram_estimate_mb must map size classes to nonnegative numbers.")
    catalog = value.get("catalog")
    if catalog is not None:
        if not isinstance(catalog, dict):
            raise ValueError("catalog must be an object.")
        category = {"restore": "cleanup", "interpolate": "motion", "size": "size"}[value["task"]]
        if catalog.get("category") != category:
            raise ValueError(f"This adapter requires catalog category {category}.")
        for field in ("title", "description", "licence_plain"):
            if not isinstance(catalog.get(field), str) or not catalog[field].strip():
                raise ValueError(f"catalog.{field} must be nonempty text.")
        if "summary" in catalog and (
            not isinstance(catalog["summary"], str) or not 1 <= len(catalog["summary"]) <= 90
        ):
            raise ValueError("catalog.summary must contain 1-90 characters.")
        for field, choices in {
            "look_change": {"very_little", "little", "noticeable"},
            "invents_detail": {"low", "medium", "high"},
            "flicker": {"none", "possible"},
        }.items():
            if catalog.get(field) not in choices:
                raise ValueError(f"Invalid catalog.{field}.")
        if "reference_speed" in catalog:
            speed = catalog["reference_speed"]
            if not isinstance(speed, dict) or any(
                type(speed.get(key)) not in {int, float}
                or not math.isfinite(speed[key])
                or speed[key] <= 0
                for key in ("fps", "peak_memory_gb")
            ):
                raise ValueError("Catalog speed and memory require positive measured numbers.")
    return value


class ModelRegistry:
    def __init__(self, home: Path | None = None) -> None:
        self.home = Path(home) if home is not None else get_home()
        self.root = self.home / "models"
        self.root.mkdir(parents=True, exist_ok=True)
        for model_id in sorted(BUILTINS):
            folder = self.folder(model_id)
            folder.mkdir(exist_ok=True)
            path = folder / "model.json"
            if not path.exists():
                # Exclusive creation leaves a concurrently installed manifest untouched.
                try:
                    with path.open("x", encoding="utf-8") as sink:
                        sink.write(
                            (Path(__file__).parent / "manifests" / f"{model_id}.json").read_text(
                                encoding="utf-8"
                            )
                        )
                except FileExistsError:
                    pass

    def folder(self, model_id: str) -> Path:
        folder = self.root / _id(model_id)
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Model folder must stay inside VE_HOME/models.")
        return folder

    def manifest(self, model_id: str, task: str | None = None) -> dict[str, Any]:
        path = self.folder(model_id) / "model.json"
        if not path.is_file():
            raise ValueError(f"Model is not installed: {model_id}")
        if path.is_symlink():
            raise ValueError("Model manifest cannot be a symbolic link.")
        value = validate_manifest(json.loads(path.read_text(encoding="utf-8")), task)
        if value["id"] != model_id:
            raise ValueError("Model manifest id does not match its folder.")
        if model_id in BUILTINS:
            shipped = json.loads(
                (Path(__file__).parent / "manifests" / f"{model_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            if "catalog" in shipped:
                value["catalog"] = shipped["catalog"]
        return value

    def weights(self, model: dict[str, Any], *, download: bool = False) -> Path:
        path = self.folder(model["id"]) / model["weights"]["filename"]
        if path.is_symlink():
            raise ValueError("Model weights cannot be a symbolic link.")
        expected = model["weights"]["sha256"]
        if not path.exists() and download:
            legacy = self.root / (
                {C1: "basicvsrpp-ntire-track3.pth", RIFE: "rife425_flownet.pkl"}.get(
                    model["id"], ""
                )
            )
            if model["id"] in BUILTINS and legacy.is_file() and sha256(legacy) == expected:
                shutil.copyfile(legacy, path)
            elif model["id"] == RIFE:
                from videoenhancer.bench.rife import _prepare_files

                # The built-in archive has its own pinned hash and Drive downloader.
                if self.home.resolve() != get_home().resolve():
                    raise ValueError(
                        "Set VE_HOME to this registry before downloading built-in RIFE."
                    )
                _, legacy = _prepare_files()
                shutil.copyfile(legacy, path)
            elif model["architecture"] == "rife" and model["architecture_params"].get("variant"):
                from videoenhancer.models.rife_variants import prepare_variant

                if self.home.resolve() != get_home().resolve():
                    raise ValueError("Set VE_HOME to this registry before downloading RIFE.")
                _, checkpoint = prepare_variant(model["architecture_params"]["variant"])
                shutil.copyfile(checkpoint, path)
            elif "url" in model["weights"] and model["weights"].get("archive"):
                from videoenhancer.bench.basicvsr import _verified_download

                bundle = path.with_suffix(".publisher.zip")
                archive = model["weights"]["archive"]
                try:
                    _verified_download(bundle, model["weights"]["url"], archive["sha256"])
                    with (
                        zipfile.ZipFile(bundle) as zipped,
                        zipped.open(archive["member"]) as source,
                        path.open("wb") as target,
                    ):
                        shutil.copyfileobj(source, target)
                finally:
                    bundle.unlink(missing_ok=True)
            elif "url" in model["weights"]:
                from videoenhancer.bench.basicvsr import _verified_download

                _verified_download(path, model["weights"]["url"], expected)
        if not path.is_file():
            raise ValueError(f"Model {model['id']} weights missing: {path.name}")
        if sha256(path) != expected:
            raise ValueError(f"Model {model['id']} weights SHA-256 mismatch; refusing to load.")
        blend = model["weights"].get("blend")
        if blend:
            secondary = self.folder(model["id"]) / blend["filename"]
            if secondary.is_symlink():
                raise ValueError("Blend weights cannot be a symbolic link.")
            if not secondary.exists() and download:
                from videoenhancer.bench.basicvsr import _verified_download

                _verified_download(secondary, blend["url"], blend["sha256"])
            if not secondary.is_file() or sha256(secondary) != blend["sha256"]:
                raise ValueError("Blend weights missing or SHA-256 mismatch.")
        return path

    def list_models(self) -> list[dict[str, Any]]:
        result = []
        for path in sorted(self.root.glob("*/model.json")):
            model = self.public_manifest(path.parent.name)
            try:
                self.weights(model)
                verified = True
            except ValueError:
                verified = False
            result.append(
                {**model, "builtin": model["id"] in BUILTINS, "weights_verified": verified}
            )
        return result

    def public_manifest(self, model_id: str) -> dict[str, Any]:
        """Current licence presentation without changing frozen resume identities."""
        model = self.manifest(model_id)
        if model_id in BUILTINS:
            shipped = json.loads(
                (Path(__file__).parent / "manifests" / f"{model_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            model = {
                **model,
                "licence": shipped["licence"],
                "commercial_use_allowed": shipped["commercial_use_allowed"],
                "weights": {
                    **model["weights"],
                    "bytes": shipped["weights"].get("bytes", model["weights"].get("bytes", 0)),
                },
            }
        return model

    def add(self, folder: Path) -> dict[str, Any]:
        model = validate_manifest(json.loads((folder / "model.json").read_text(encoding="utf-8")))
        target = self.folder(model["id"])
        if model["id"] in BUILTINS or target.exists():
            raise ValueError(f"Model already installed or built-in: {model['id']}")
        weights = folder / model["weights"]["filename"]
        if weights.is_symlink() or not weights.is_file():
            raise ValueError("Model weights missing or symbolic link.")
        if sha256(weights) != model["weights"]["sha256"]:
            raise ValueError("Model weights SHA-256 mismatch.")
        # Copy only data: unrelated Python files are never installed or imported.
        with tempfile.TemporaryDirectory(prefix=".install-", dir=self.root) as temporary:
            staged = Path(temporary)
            shutil.copyfile(weights, staged / weights.name)
            blend = model["weights"].get("blend")
            if blend:
                secondary = folder / blend["filename"]
                if (
                    secondary.is_symlink()
                    or not secondary.is_file()
                    or sha256(secondary) != blend["sha256"]
                ):
                    raise ValueError("Blend weights missing or SHA-256 mismatch.")
                shutil.copyfile(secondary, staged / secondary.name)
            if sha256(staged / weights.name) != model["weights"]["sha256"]:
                raise ValueError("Model weights changed while installing.")
            (staged / "model.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
            target.mkdir()
            try:
                for source in staged.iterdir():
                    source.replace(target / source.name)
            except BaseException:
                shutil.rmtree(target)
                raise
        return model

    def remove(self, model_id: str) -> None:
        from videoenhancer.jobs.store import JobStore

        used = sum(
            model_id in selected_models(job["settings"]).values()
            for job in JobStore(self.home).list_jobs()
            if job["state"] not in {"done", "failed", "cancelled"}
        )
        if used:
            raise ValueError(f"Used by {used} videos in the queue")
        model = self.manifest(model_id)
        if model_id in BUILTINS:
            (self.folder(model_id) / model["weights"]["filename"]).unlink(missing_ok=True)
            if model["weights"].get("blend"):
                (self.folder(model_id) / model["weights"]["blend"]["filename"]).unlink(
                    missing_ok=True
                )
        else:
            shutil.rmtree(self.folder(model_id))

    def snapshot(self, model_id: str, task: str, *, download: bool = True) -> dict[str, Any]:
        model = self.manifest(model_id, task)
        self.weights(model, download=download)
        # Presentation metadata cannot invalidate an existing resumable job.
        identity = {key: value for key, value in model.items() if key != "catalog"}
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "id": model_id,
            "version": model["version"],
            "sha256": model["weights"]["sha256"],
            "manifest_sha256": digest,
        }

    def create_stage(
        self, model_id: str, task: str, settings: dict[str, Any], rate: Fraction, cuts: set[int]
    ) -> Stage:
        model = self.manifest(model_id, task)
        weights = self.weights(model, download=True)
        return ADAPTERS[model["architecture"]][1](model, weights, settings, rate, cuts)


def selected_models(
    settings: dict[str, Any], media: dict[str, Any] | None = None
) -> dict[str, str]:
    selected: dict[str, str] = {}
    preset = settings.get("preset")
    if preset == "standard" or settings.get("restore_model"):
        selected["restore"] = settings.get("restore_model") or C1
    eligible = settings.get("fps", "2x") == "2x" and preset in {"standard", "fast"}
    if media is not None:
        from videoenhancer.media.timing import output_rate

        eligible &= output_rate(settings, media) == Fraction(media["cfr_fps"]) * 2
    if eligible:
        selected["interpolate"] = settings.get("interp_model") or RIFE
    elif settings.get("interp_model"):
        raise ValueError(
            "--interp-model requires active 2x interpolation for this preset and input rate."
        )
    if settings.get("size_model"):
        selected["size"] = settings["size_model"]
    return selected


def record_models(
    settings: dict[str, Any], home: Path, media: dict[str, Any] | None = None
) -> dict[str, Any]:
    selected = selected_models(settings, media)
    if not selected:
        return {}
    registry = ModelRegistry(home)
    return {task: registry.snapshot(model_id, task) for task, model_id in selected.items()}


def validate_job_models(job: dict[str, Any], home: Path | None = None) -> None:
    recorded = job.get("models", {})
    if not recorded:
        return  # P0 manifests contain no model stages.
    registry = ModelRegistry(home)
    if {task: model["id"] for task, model in recorded.items()} != selected_models(
        job["settings"], job.get("media")
    ):
        raise ValueError("Job model selection changed; create a new job instead of resuming.")
    for task, expected in recorded.items():
        actual = registry.snapshot(expected["id"], task, download=False)
        if actual != expected:
            raise ValueError(f"Model {expected['id']} changed since job creation; resume refused.")


def _basicvsr(
    model: dict[str, Any], weights: Path, settings: dict[str, Any], _rate: Fraction, _cuts: set[int]
) -> Stage:
    from videoenhancer.models.basicvsr import BasicVSRRestoreStage

    return BasicVSRRestoreStage(settings, manifest=model, weights=weights)


def _rife(
    model: dict[str, Any], weights: Path, settings: dict[str, Any], rate: Fraction, cuts: set[int]
) -> Stage:
    from videoenhancer.models.rife import RifeInterpolateStage

    return RifeInterpolateStage(rate, cuts, settings, manifest=model, weights=weights)


def _spandrel(
    model: dict[str, Any], weights: Path, settings: dict[str, Any], _rate: Fraction, _cuts: set[int]
) -> Stage:
    from videoenhancer.models.spandrel import SpandrelRestoreStage

    return SpandrelRestoreStage(model, weights, settings)


register_adapter("basicvsrpp", "restore", _basicvsr)
register_adapter("rife", "interpolate", _rife)
register_adapter("spandrel", "restore", _spandrel)
register_adapter("drunet", "restore", _spandrel)


def _spandrel_size(
    model: dict[str, Any], weights: Path, settings: dict[str, Any], _rate: Fraction, _cuts: set[int]
) -> Stage:
    from videoenhancer.models.spandrel import SpandrelSizeStage

    return SpandrelSizeStage(model, weights, settings)


register_adapter("spandrel-size", "size", _spandrel_size)
