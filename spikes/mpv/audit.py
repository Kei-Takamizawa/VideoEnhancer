"""Inventory a pinned candidate; this is not a licence clearance tool."""

import argparse
import ctypes
import hashlib
import json
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = Path(__file__).resolve().parents[3]
    root = work / "cache/mpv-lgpl"
    dll = root / "libmpv-2.dll"
    expected = "b9f3ddd1ef2d43d6424addb835824ddb4e1e5f72c067e2816f0e09b19a6c4752"
    data = dll.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("DLL checksum mismatch; refusing to load")
    strings = re.findall(rb"[ -~]{16,}", data)
    configuration = next(
        s.decode() for s in strings if s.startswith(b"-Dprefix=") and b"-Dgpl=false" in s
    )
    lib = ctypes.CDLL(str(dll))
    lib.mpv_create.restype = ctypes.c_void_p
    lib.mpv_initialize.argtypes = [ctypes.c_void_p]
    lib.mpv_get_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.mpv_get_property_string.restype = ctypes.c_void_p
    lib.mpv_free.argtypes = [ctypes.c_void_p]
    lib.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]
    handle = lib.mpv_create()
    if not handle:
        raise RuntimeError("mpv_create failed")
    versions = {}
    try:
        result = lib.mpv_initialize(handle)
        if result < 0:
            raise RuntimeError(f"mpv_initialize: {result}")
        for key in ("mpv-version", "ffmpeg-version"):
            pointer = lib.mpv_get_property_string(handle, key.encode())
            if not pointer:
                raise RuntimeError(f"Missing version: {key}")
            try:
                versions[key] = ctypes.string_at(pointer).decode()
            finally:
                lib.mpv_free(pointer)
    finally:
        lib.mpv_terminate_destroy(handle)
    ffmpeg = subprocess.run(
        [str(root / "ffmpeg/ffmpeg.exe"), "-hide_banner", "-buildconf"],
        capture_output=True,
        text=True,
        check=True,
    )
    configuration_ffmpeg = ffmpeg.stdout + ffmpeg.stderr
    if "--enable-gpl" in configuration_ffmpeg or "--enable-nonfree" in configuration_ffmpeg:
        raise RuntimeError("Forbidden FFmpeg configuration")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and "spike-target" not in path.parts:
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    result = {
        "status": "CANDIDATE_NOT_CLEARED_FOR_DISTRIBUTION",
        "versions": versions,
        "mpv_configuration_from_dll": configuration,
        "ffmpeg_companion_configuration": configuration_ffmpeg,
        "ffmpeg_configuration_scope": (
            "Companion EXE from same release, not proof of exact statically linked DLL build"
        ),
        "files": files,
        "bytes_excluding_spike_build": sum(f["bytes"] for f in files),
        "open": [
            "Complete static dependency versions and licence manifest",
            "Exact embedded FFmpeg configure log",
            "Corresponding source archive, patches and reproducible build inputs",
        ],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
