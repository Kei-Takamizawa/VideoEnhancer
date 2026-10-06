# Development

Use Python 3.12 and `uv` from the repository root. For the full Windows NVIDIA engine and optional model benchmarks, install both extras:

```powershell
uv sync --extra gpu --extra models
uv run ve --help
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -m "not gpu and not soak"
```

For CPU-only development, use `uv sync --extra models` (or plain `uv sync` when no optional model benchmark dependencies are needed). The `gpu` extra installs PyNvVideoCodec; the `models` extra installs torchvision, Spandrel, ONNX Runtime GPU, and gdown for the optional adapters.

On an NVIDIA Windows machine, run `uv run ve bench --calibrate` to save a local machine profile, then `uv run ve bench --models all` for model availability and timing results. Optional model downloads happen only when the model was requested and its expected SHA-256 is pinned; benchmark reports record every measured or skipped candidate and the reason.

Create short VFR, rotation, HDR-tagged and hard-cut validation clips with `uv run python scripts/generate_synthetic.py --output-dir .tmp/synthetic`. Create the two-hour stream-copy soak file with `uv run python scripts/generate_synthetic.py --output-dir .tmp/synthetic --soak --backend nvenc` (or `--backend cpu` where NVENC is unavailable). Run the long soak separately with `uv run python scripts/soak.py --input .tmp/synthetic/soak_2h.mp4`; it schedules two 15-minute pauses, monitors process-tree RSS and NVML memory, and writes an estimate-versus-actual report. It may take several hours and should only be started on the reference GPU when the machine can remain available.

Never place owner sample videos, generated media, model weights, or job data in Git. Set `VE_SAMPLES_DIR` to the owner's private `Videos` folder when local sample checks are explicitly needed.
