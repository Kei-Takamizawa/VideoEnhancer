# Project handoff for Claude

Updated 2026-11-10. Claude now develops this project directly under
[CLAUDE.md](CLAUDE.md). The former Claude-Codex workflow and its task/report
exchange are retired. Historical instructions must not restart that workflow.

## Project

VideoEnhancer is a Windows 11 app for NVIDIA RTX GPUs. The Python 3.12 engine
uses PyTorch, PyNvVideoCodec and FFmpeg for resumable video processing. The
desktop is Tauri 2 / WebView2 with React and TypeScript. The authenticated remote
web app supports paired iPad and Mac browsers.

- Engine and CLI: `src/videoenhancer/`.
- Desktop UI and shell: `gui/src/` and `gui/src-tauri/`.
- Remote service and web app: `src/videoenhancer/remote/`.
- Fast preset: RIFE interpolation. Standard: C1 BasicVSR++ restoration, resize
  and RIFE. Model licences are separate from the application's MIT licence.
- Setup and commands: [development guide](docs/DEVELOPMENT.md).
- Windows paths, isolation, retention and budgets: [workspace rules](docs/WORKSPACE.md).
- Product references: [architecture](docs/ARCHITECTURE.md), [API](docs/API.md),
  [desktop](docs/GUI.md) and [remote access](docs/REMOTE.md).

## Existing product decisions

Changing the development workflow does not change the product requirements.
Keep these established decisions unless the owner requests a change:

- Restore the pre-compression edited look, including make-up and filters; do not
  invent skin texture. Diffusion models are excluded.
- Inputs are MP4, MOV, MKV or WebM, H.264/HEVC/VP9/AV1, 8/10-bit SDR with short
  side at most 1080. Larger inputs and HDR are refused. Output short side is
  Keep / 1080 / 1440, with no downscaling; frame rate is Keep or 2x, capped at
  60 fps. HEVC Main10 remains the default; H.264 and AV1 are optional. Audio is
  copied, or converted to AAC 256 kbps when MP4 cannot hold it.
- The desktop uses Tauri 2 and the optional embedded libmpv player with an
  IINA-like UI. Electron was removed. The recorded Tauri cold-start targets are
  Home-ready median at most 765 ms and first paint at most 1.0 s; they are targets,
  not fresh measurements.
- Video links use optional checksum-verified tools with no in-app sign-in.
  HTTPS links must not fall back to HTTP media. Keep strict decoder timestamps
  and per-job FFmpeg fallback, without PTS correction.
- Scheduling includes working hours, days off, one-day changes and finalization
  in ETA. Storage defaults to `%LOCALAPPDATA%\VideoEnhancer`, with `VE_HOME`
  override and Settings > Storage relocation. Remote access stays opt-in and
  paired; the older roadmap's ordering has been superseded by the merged R1 work.

## Verified repository state at this handoff

- Baseline `main`: `56e8f6775554a4314e5ecb310011bcac901e675e`,
  [PR #21](https://github.com/Kei-Takamizawa/VideoEnhancer/pull/21), R1e failure
  logging, upload recovery, keep-alive streaming and shorter engine locking.
- The latest retained implementation report is **VE-R1e-2 / CI follow-up**,
  **COMPLETED**. Its reported local results include 932 CPU tests passed,
  25 skipped, 103 deselected, 27 Node tests passed, and successful Ruff and
  Pyright checks. These are historical Windows results, not rerun during this
  documentation cleanup. See [retained reports](docs/archive/claude-codex/REPORTS.md).
- [CPU engine checks on that main commit](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/41984040216)
  completed successfully on GitHub. The workflows contain validation/build jobs;
  no Claude-Codex loop was found in repository automation.
- No pull request was open when this cleanup began. No new product task is
  assigned by this handoff. Do not rerun the archived R1e-2 task or use the old
  October roadmap as the current backlog.

## What needs live confirmation

The owner's Windows checkout, installed package, running remote service, device
pairings and scratch folders were not inspected during this cleanup. Historical
reports list refused cleanup paths and owner/device checks. Check their current
state before acting; do not assume they were completed or are still pending.
The latest report did not perform a remote restart, package replacement or
browser/desktop/GPU checks.

For the next request, inspect the actual branch and working tree, preserve local
work, and choose checks for that request. Claude can implement and test directly;
there is no migration smoke run or Codex setup prerequisite.

## Historical evidence

The [archive index](docs/archive/claude-codex/README.md) maps the former root and
`.ai` files to their retained copies. Their bytes and measurements are preserved.
Older records not present in the retained report bundle remain in Git history.
The 2026-10-21 handoff describes the state then; its branches, CI failures, role
assignments and next-work list are not current instructions.
