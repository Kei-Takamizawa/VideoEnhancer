"""Verified benchmark-only assets. Processing never calls these download helpers."""

import hashlib
import importlib.util
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

from videoenhancer.config import get_home


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verified_asset(url: str, expected_sha256: str, filename: str) -> Path:
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("A pinned SHA-256 is required before downloading benchmark assets.")
    directory = get_home() / "models"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    if path.exists() and file_sha256(path) == expected_sha256:
        return path
    temporary = path.with_suffix(path.suffix + ".download")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = file_sha256(temporary)
        if actual != expected_sha256:
            raise RuntimeError(
                f"Checksum mismatch for {filename}: expected {expected_sha256}, got {actual}."
            )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def verified_source(url: str, expected_sha256: str, archive_name: str, root_name: str) -> Path:
    archive = verified_asset(url, expected_sha256, archive_name)
    directory = archive.parent
    root = directory / root_name
    marker = root / ".videoenhancer-source-sha256"
    if marker.exists() and marker.read_text() == expected_sha256:
        return root
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = (directory / member.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError("The source archive contains an unexpected path.")
        source.extractall(directory)
    marker.write_text(expected_sha256, encoding="ascii")
    return root


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load external benchmark module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def module_stub(name: str, **members: Any) -> ModuleType:
    result = ModuleType(name)
    result.__path__ = []
    result.__dict__.update(members)
    sys.modules[name] = result
    return result


@contextmanager
def isolated_modules(*prefixes: str) -> Iterator[None]:
    def selected(name: str) -> bool:
        return any(name == p or name.startswith(p + ".") for p in prefixes)

    original = {name: module for name, module in sys.modules.copy().items() if selected(name)}
    try:
        yield
    finally:
        for name in list(sys.modules):
            if selected(name):
                sys.modules.pop(name, None)
        sys.modules.update(original)


class Registry:
    def register(self, **_kwargs: Any):
        return lambda cls: cls

    register_module = register
