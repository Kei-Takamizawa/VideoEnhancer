"""Runtime paths; processing never downloads dependencies."""

import os
import shutil
from pathlib import Path


def get_home() -> Path:
    explicit = os.environ.get("VE_HOME")
    if explicit:
        result = Path(explicit).expanduser().resolve()
    elif os.name == "nt":
        result = (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "VideoEnhancer"
        )
    else:
        result = (
            Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "VideoEnhancer"
        )
    result.mkdir(parents=True, exist_ok=True)
    return result


def executable(name: str) -> str:
    directory = os.environ.get("VE_FFMPEG_DIR")
    if directory:
        candidate = Path(directory) / (name + (".exe" if os.name == "nt" else ""))
        if candidate.is_file():
            return str(candidate)
        raise FileNotFoundError(f"{name} was not found in VE_FFMPEG_DIR: {directory}.")
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"Install FFmpeg and ffprobe, then set VE_FFMPEG_DIR or add them to PATH ({name} missing)."
    )


def samples_dir() -> Path | None:
    value = os.environ.get("VE_SAMPLES_DIR")
    return Path(value).expanduser().resolve() if value else None
