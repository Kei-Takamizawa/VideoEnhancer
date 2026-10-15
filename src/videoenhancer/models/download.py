"""Byte reporting for publisher Drive archives, including older gdown versions."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO, cast


def drive_archive(
    path: Path,
    file_id: str,
    expected: str,
    size: int,
    progress: Callable[[str, float], None] | None = None,
) -> None:
    import gdown

    from videoenhancer.models.registry import remember_verified_hash, sha256

    temporary = path.with_suffix(path.suffix + ".download")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("wb") as stream:

            class Sink:
                received = 0

                def write(self, data: bytes) -> int:
                    written = stream.write(data)
                    self.received += written
                    if progress:
                        progress(f"Downloading {path.name}: {self.received} / {size} bytes", 0)
                    return written

                def __getattr__(self, name: str) -> Any:
                    return getattr(stream, name)

            downloaded = gdown.download(
                id=file_id, output=cast(BinaryIO, Sink()), quiet=True, use_cookies=False
            )
            if not downloaded:
                raise RuntimeError("The publisher did not return the RIFE archive.")
        observed = sha256(temporary, progress)
        if observed != expected:
            raise ValueError("RIFE publisher archive SHA-256 mismatch.")
        info = temporary.stat()
        temporary.replace(path)
        remember_verified_hash(path, observed, (info.st_size, info.st_mtime_ns))
    finally:
        temporary.unlink(missing_ok=True)
