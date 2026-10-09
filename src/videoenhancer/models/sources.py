"""Keep pinned upstream adapter sources outside data-only model folders."""

import shutil
from pathlib import Path

from videoenhancer.config import get_home


def source_path(cache: Path, path: Path) -> Path:
    """Reject redirected cache children before reading or writing adapter code."""
    resolved = path.resolve()
    if not resolved.is_relative_to(cache.resolve()) or resolved.is_relative_to(
        (get_home() / "models").resolve()
    ):
        raise ValueError("Adapter source path must stay outside model data and inside its cache.")
    return path


def source_cache(archives: tuple[str, ...]) -> Path:
    home = get_home()
    cache = home / "adapter-sources"
    if cache.resolve().is_relative_to((home / "models").resolve()):
        raise ValueError("Adapter source cache cannot point into the model data folder.")
    cache.mkdir(parents=True, exist_ok=True)
    for name in archives:
        old, new = home / "models" / name, source_path(cache, cache / name)
        if old.is_file() and not new.exists():
            shutil.copyfile(old, new)
    return cache
