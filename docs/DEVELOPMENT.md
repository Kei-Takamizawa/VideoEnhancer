# Development

## P1t media memory qualification

Run `node scripts/media-matrix.mjs` from `gui` only on the isolated Windows test
machine. Set `VE_M2_SCRATCH`, `VE_M2_EVIDENCE`, `VE_M2_MEDIA`,
`VE_M2_TAURI_EXE`, `VE_M2_ELECTRON_EXE`, `VE_M2_TEMPLATE`, and `VE_PYTHON`. The media directory must
contain the FFmpeg-only 1440p H.264 and AV1 fixtures of at least 2 GB, plus the
1080p source fixtures. Never use owner media or the owner app-data folders.
Use an isolated copy of the old Electron executable so its startup-registration
check cannot match the owner's installed executable path.
`VE_M2_TEMPLATE` points to a genuinely finished synthetic job manifest. Each run
starts the production Python engine and uses its unchanged authenticated Range
handler. The comparison service alone can opt into a process-local legacy Origin
override for the old Electron package; the production server policy is unchanged.
The 1440p fixture is never sent through the enhancement pipeline. A small synthetic
thumbnail is seeded so the thumbnail generator does not decode it as a new source.
For a long matrix, `VE_M2_ENGINE_SNAPSHOT` can point to a frozen scratch copy
containing `src/` and `gui/scripts/{media-service.py,private-bytes.py}`. Save its
source hashes with the evidence before starting, and keep the measurement binary
unchanged throughout the matrix.

Build the Tauri measurement executable with release optimization and the `e2e`
feature. Only that feature accepts `VE_TEST_MEDIA_CHUNK_MIB` (8, 2 or 1) and
exposes diagnostic counters. The owner package has neither test capability.
The driver alternates Electron and Tauri, records timing medians of ten, runs
three P/R repetitions with fixed-seed seeks, records thirty-second residuals,
and samples each process's Windows Private Bytes every second. Raw per-process
samples, recipe, progress, and completed-run checkpoints go to external evidence.
An interrupted matrix resumes completed runs; do not replace failed evidence.
This long measurement is opt-in and does not run in CPU CI.

The old absolute 100 MB memory-growth gate was withdrawn by the designer.
Compare P/R growth against Electron plus 100 MB, check the specified residual
limit, and check the ten-minute stability gate before selecting a response size.
No unauthenticated M3 media URL is exposed by the production engine.

## Tauri desktop candidate

On Windows 11, install MSVC C++ Build Tools, a Windows SDK and the WebView2 Runtime.
Use Rust 1.99.1 with rustfmt and Clippy. Keep `RUSTUP_HOME`, `CARGO_HOME` and
`CARGO_TARGET_DIR` under the workspace cache, using session-only environment values.
See [workspace rules](WORKSPACE.md) before installing or launching anything.

From `gui`, `npm run dev` starts Tauri and the existing Vite renderer.
`npm run build:desktop` builds the unsigned portable executable without an installer.
For local tests, build the renderer, then run
`cargo build --manifest-path src-tauri/Cargo.toml --features e2e` once before Playwright.
Every desktop test uses an isolated home under scratch, isolated roaming/local
app-data roots and a separate WebView2 data directory, and attaches over CDP.
Owner packages must omit `e2e`; their test-command denial is verified separately.

The owner package is an executable and `engine-location.json` in one folder.
The engine checkout and Python environment remain external. No updater is included.

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

On an NVIDIA Windows machine, run `uv run ve bench --calibrate` to save a local machine profile. Calibration measures installed restoration and interpolation adapters in inference mode and records their model IDs, versions, weight and manifest hashes, geometry, clip preferences, loading time, and per-pixel coefficients. The estimator selects coefficients for the job's verified model identities and includes overlap work. Changed model identities invalidate their old coefficients. C1 is the first-release restoration model; candidate benchmarking is closed. Use `uv run ve enhance INPUT --preset fast` for smoother motion or `--preset standard` for compression restoration and smoother motion.

Use `uv run ve trial INPUT --seconds 5 --preset standard --out C:\Evaluation\trial`
for a labeled original-left/enhanced-right comparison. The default excerpt is
five seconds centered in the input. `--start`, `--backend cpu`, `--short-side keep`,
`--restore-model ID` and `--interp-model ID` are supported. Trial retains source
context outside the excerpt, writes four files outside the repository, and refuses
existing result filenames. Original uses the same resize stage as Enhanced;
the comparison duplicates original frames to the enhanced rate. Reports include
speed, metrics and projected whole-file processing time.

`uv run ve models list`, `uv run ve models add C:\MyModels\finetune`, and
`uv run ve models remove my-model` manage installed models. Built-ins cannot be
removed. See [ADDING_MODELS.md](ADDING_MODELS.md) for manifests and adapters.

Create short VFR, rotation, HDR-tagged and hard-cut validation clips with `uv run python scripts/generate_synthetic.py --output-dir .tmp/synthetic`. Create the two-hour stream-copy soak file with `uv run python scripts/generate_synthetic.py --output-dir .tmp/synthetic --soak --backend nvenc` (or `--backend cpu` where NVENC is unavailable).

Run each long experiment in a fresh external `VE_HOME` with verified models, adapter sources and a matching calibration profile. For example, `uv run python scripts/soak.py --input C:\Evaluation\synthetic-2h.mp4 --output C:\Evaluation\fast.mp4 --preset fast --scheduled-pauses 2` completes the input with two 15-minute scheduled pauses. `--preset standard --scheduled-pauses 0` completes a separate 15-minute input for estimate accuracy. `--preset standard --mode stability --scheduled-pauses 1` runs at least 60 active minutes, pauses on schedule, abruptly stops and resumes its own controller, then leaves the job paused. It does not finish the two-hour input.

Reports compare calibrated initial and first-at-or-after-10% predictions with completed wall time excluding observed pauses. Partial stability runs have no estimate-accuracy result. Epoch timestamps are used consistently for memory growth; report the maximum in the first and last five-minute sample windows after minute 10. Engine-PID Windows dedicated GPU memory, Torch reserved memory, engine RSS and controller-tree RSS are recorded separately. These jobs take several hours.

Never place owner sample videos, generated media, model weights, or job data in Git. Set `VE_SAMPLES_DIR` to the owner's private `Videos` folder when local sample checks are explicitly needed.
