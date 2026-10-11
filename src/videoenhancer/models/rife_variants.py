"""Hash-pinned publisher IFNet variants; never execute code from model folders."""

import importlib
import zipfile
from pathlib import Path

from videoenhancer.models.registry import sha256
from videoenhancer.models.sources import source_cache, source_path

VARIANTS = {
    "4.26": (
        "1gViYvvQrtETBgU1w8axZSsr7YUuw31uy",
        "c2452dd2b244947d4be580156bbead60d6b72af5736860f7d6b3f99648c9c4cc",
    ),
    "4.25-lite": (
        "1zlKblGuKNatulJNFf5jdB-emp9AqGK05",
        "e84366c23e0eb1a637a55aad2e4f3442ec2bf4c388043b4aabbf590be289e6e8",
    ),
}


def prepare_variant(version: str) -> tuple[Path, Path]:
    file_id, expected = VARIANTS[version]
    cache = source_cache(())
    archive = source_path(cache, cache / f"rife-{version}.zip")
    if not archive.exists():
        gdown = importlib.import_module("gdown")
        temporary = archive.with_suffix(".download")
        try:
            if not gdown.download(id=file_id, output=str(temporary), quiet=True):
                raise RuntimeError("The publisher did not return the RIFE archive.")
            if sha256(temporary) != expected:
                raise ValueError("RIFE publisher archive SHA-256 mismatch.")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    if sha256(archive) != expected:
        raise ValueError("Pinned RIFE variant archive changed; refusing to execute it.")
    root = source_path(cache, cache / f"rife-{version}-source")
    with zipfile.ZipFile(archive) as bundle:
        for name in ("train_log/IFNet_HDv3.py", "train_log/flownet.pkl"):
            target = source_path(cache, root / name)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = bundle.read(name)
            if target.exists() and target.read_bytes() != content:
                raise ValueError("Pinned RIFE variant source changed; refusing to load it.")
            if not target.exists():
                target.write_bytes(content)
    return root, root / "train_log/flownet.pkl"
