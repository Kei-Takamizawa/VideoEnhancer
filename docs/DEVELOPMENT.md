# Development

## Playback measurements

Historical comparative measurements and their exact recipes are retained in the
external cycle evidence and Git history. New measurements use the Tauri shell,
isolated synthetic media and process-role samples. Never use owner media or the
owner app-data folders. A generated playback fixture is not an enhancement input.
The bounded media protocol uses 1 MiB responses; no unauthenticated media URLs are
exposed by the production engine. Known acceptance failures remain in the report.

## Tauri desktop

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
Owner packages must omit both `e2e` and `cdp`; their test-command denial is verified separately.
Debug, `e2e` and `cdp` builds never write the Windows Run key. Startup-write
failure tests use a fake writer; `e2e` can inject `VE_TEST_STARTUP_ERROR`.
The Windows CI job checks for the WebView2 Runtime and installs Microsoft's
Evergreen Runtime on the hosted runner when missing. It passes the resolved
runtime folder explicitly so isolated local app-data paths do not hide a
per-user runtime. This does not install software on the developer's PC.
Elevated hosted runners can ignore environment-only WebView2 debugging flags.
The `cdp` feature (also enabled by `e2e`) forwards only the validated CDP port through Tauri's browser
arguments API; feature-free owner builds do not include this test configuration.

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
