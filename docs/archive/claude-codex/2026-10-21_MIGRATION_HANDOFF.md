# Migration handoff: Claude + Codex on Windows

- **Prepared:** 2026-10-21 by Claude (designer and reviewer), from a read-only investigation.
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer (public, MIT)
- **Marks used below:** **[verified]** = checked directly (Git, GitHub, CI logs, files). **[reported]** = taken from Codex's report (`.ai/LAST_REPORT.md`) and not re-run by Claude. **[unverified]** = not checked yet; must be confirmed on the Windows machine before relying on it.

## 1. Project overview

VideoEnhancer is a Windows 11 desktop app for NVIDIA RTX GPUs. It restores streaming-compression damage and doubles the frame rate of already-edited Beauty, MV, idol and streaming videos, without redrawing faces. The edited look (make-up, filters, skin smoothing) is treated as correct. A "restore only" path (no upscaling) is part of the product goal.

- **Engine:** Python 3.12 + PyTorch (CUDA), PyNvVideoCodec (NVDEC/NVENC), FFmpeg. Resumable segments, scheduler (working hours), estimator, local authenticated loopback API, CLI `ve`. Source: `src/videoenhancer/`.
- **Desktop shell:** Tauri 2 (Rust, WebView2) in `gui/src-tauri/`, React + TypeScript UI in `gui/src/`. Electron was removed in P1f.
- **Presets:** Fast = Practical-RIFE interpolation. Standard = BasicVSR++ restoration (model C1, `basicvsrpp-ntire21-decompress`) → resize → RIFE (`rife-4.25`).
- **CI:** `.github/workflows/ci.yml`, Windows + Ubuntu, CPU-only. GPU tests run only on the Windows development machine.

## 2. Roles and working model

| Role | Who | Responsibility |
| --- | --- | --- |
| Owner | The project owner | Approves specs, runs owner checks, deletes files Codex cannot delete |
| Designer / reviewer | Claude (cloud project) | Specs, Codex task documents, reviews of diffs, reports and CI. Does not write product or test code |
| Operator | Claude Code on the Windows machine, started from the cloud project through Remote Control | Starts Codex with `codex exec`, runs all Git commands (fetch, branch, commit, push), reports back. Does not write product or test code |
| Implementer / tester | Codex on the Windows machine | Implements, builds, tests, writes `.ai/LAST_REPORT.md`. Runs no Git commands that change anything (since 2026-10-21) |

- Every cycle has a Task ID (for example `VE-P1f-2`). Codex copies the task into `.ai/CURRENT_TASK.md` and writes `.ai/LAST_REPORT.md`. **[verified]**
- Claude's task documents are kept in the cloud project's shared files (`design/codex/<ID>_CURRENT_TASK.md`), not in Git. Owner checklists and review memos are there too (in Japanese). **[verified]**
- **Until 2026-10-21** the owner handed each task document to the Codex desktop app by hand.
- **From now on (owner decisions, 2026-10-21):** the cloud project starts a Remote Control session on the Windows machine. The operator checks out the cycle branch, starts Codex with `codex exec` in the same approval mode as the Codex desktop app (on request, reviewed automatically), then commits and pushes Codex's work. The official plugin's `/codex:rescue` is not used for implementation, because it runs Codex without approvals (section 12). Rules: `AGENTS.md` (Codex) and `CLAUDE.md` (Claude).

## 3. Current specification (summary)

The full spec is `design/02_spec_v1.md` in the cloud project (Japanese). Decisions made later override it where they differ.

- **Input:** MP4, MOV, MKV, WebM. H.264, HEVC, VP9, AV1; 8/10-bit SDR. Short side ≤ 1080 only (1080x1920 vertical allowed). Larger files and HDR are refused with a reason. **[verified in spec]**
- **Output:** short side Keep / 1080 (default) / 1440; never downscales. Frame rate Keep or 2x (max 60 fps). MP4, HEVC Main10 by default, H.264 and AV1 optional. Audio copied, or AAC 256 kbps when MP4 cannot hold it. Rotation applied to pixels.
- **Video links (P1f):** optional yt-dlp tools installed on request with checksums; best SDR stream ≤ 1080p; no in-app sign-in; reuse of an earlier download; `https` links never fall back to `http` media.
- **Scheduling:** working hours, days off, one-day changes, per-day plan, ETA including finalization.
- **Storage:** app data defaults to `%LOCALAPPDATA%\VideoEnhancer` (`VE_HOME` overrides); Settings > Storage can move it.
- **Language:** all code, comments, UI text and repository docs in English.

## 4. Important design decisions (settled; do not reopen without the owner)

| Date | Decision |
| --- | --- |
| 2026-10-05 | Quality principle: the pre-compression edited video is the target; no added skin texture; diffusion models excluded |
| 2026-10-16 | Inputs limited to ≤ 1080p (short side); 2160 output removed; outputs Keep/1080/1440 |
| 2026-10-16 | Electron → Tauri 2 (done in P1t; Electron removed in P1f) |
| 2026-10-16 | All development work on drive D under `D:\my-workspace\VideoEnhancer\work` (see `docs/WORKSPACE.md`) |
| 2026-10-18 | HEVC stays the default output. Owner installed HEVC Video Extensions |
| 2026-10-18 | P1e-3 player = embedded mpv (libmpv) with an IINA-like UI |
| 2026-10-18 | Links: no sign-in; model links deferred; browser link drag deferred; strict decoder timestamp check with per-job FFmpeg fallback, no PTS correction |
| 2026-10-19 | Cold-start gate re-based to Tauri: Home-ready median ≤ 765 ms, first paint ≤ 1.0 s |
| 2026-10-12 | Later order: video links (done) → P2 face/skin/hair → LAN remote control last (same Wi-Fi only, off by default, QR pairing) |

## 5. Completed work

All seven PRs are merged into `main`. **[verified]**

| PR | Cycle(s) | Content | Merged (UTC) |
| --- | --- | --- | --- |
| #1 | P0 | Engine foundation: GPU I/O, segments and resume, schedule, estimates, benchmark | 2026-10-06 |
| #2 | P1a | Real enhancement pipeline (C1 + RIFE) | 2026-10-09 |
| #3 | P1b | Local engine service and Windows desktop GUI | 2026-10-09 |
| #4 | P1c | Desktop redesign, qualified model catalog, previews | 2026-10-11 |
| #5 | P1d, P1e, P1e-2, P1e-2b | UI v2, guarded deletion, estimates, hardening, drive-D workspace and Storage move | 2026-10-21 |
| #6 | P1t | Tauri desktop shell and safe storage migration | 2026-10-21 |
| #7 | P1f, P1f-2 | Video links and review fixes (A1-A3, B1-B14) | 2026-10-21 |

P1f-2 results **[reported]**: CPU 582 pass, GPU 101 pass, GUI e2e 16 pass, real-tool link bundle 99 pass; Home-ready median 718 ms. PR #7's head `2f12d43` passed Windows and Ubuntu CI **[verified]**.

## 6. Incomplete work

- **Next fix cycle (not handed to Codex yet):** the owner's P1f check results arrived on 2026-10-21. Claude is analysing them in the cloud project and will write the next task document. Its Task ID is not assigned yet. Do not start it until the migration route is decided.
- **P1e-3:** mpv player; VRAM cap with shared-memory spill detection; recalibration and gate rerun; finalization calibration fix; Compare speed; engine start must survive a damaged JSON file; 19 minor findings from the P1f review (`P1f2_CURRENT_TASK.md` section 6) plus 4 from the P1f-2 review.
- **P1g:** HDR input.
- **P2:** face/skin/hair processing (detection, tracking, occlusion, faithful face restoration).
- **Later:** P3 High Quality preset, P4 TensorRT/FP8, LAN remote control, model import from links, browser link drag.

## 7. Current Task ID

- **Last completed:** `VE-P1f-2` (COMPLETED, merged). `.ai/CURRENT_TASK.md` and `.ai/LAST_REPORT.md` on `main` describe this cycle. **[verified]**
- **Next:** not assigned (see section 6).

## 8. Latest branch and commit

- **`main` = `bc7e10e`** (merge of PR #5, 2026-10-21 03:20 UTC). Its file tree is identical to `p1f-links` at `2f12d43`. **[verified]**
- Remote branches `p0-engine-foundation`, `p1-restoration-gui`, `p1b-gui`, `p1c-redesign`, `p1d-ui-v2`, `p1t-tauri`, `p1f-links` still exist; all are merged. **[verified]**
- No open PRs and no open issues. **[verified]**
- The cloud clone has no uncommitted or unpushed changes. **[verified]**
- The Windows checkout `D:\my-workspace\VideoEnhancer\work\repo` (checked 2026-10-21) **[verified]**:
  - on `p1f-links` at `2f12d43`, working tree clean, no stash, nothing unpushed;
  - the clone's fetch refspec covers only `p1d-ui-v2`, so `origin/main` does not exist locally. Start the next cycle by fetching `main` explicitly. Local `p1t-tauri` and `p1d-ui-v2` are behind the remote and have no unpushed commits.

## 9. Unresolved issues

1. **`main` CI is red on Windows.** **[verified]** Run 39538012425: `tests/test_p1f2_review.py::test_a1_unreadable_history_folder_undo_and_cleanup[{torn record-expire]` failed. The staged folder under `jobs/.removing/` still existed after the 13-second wait. The same tree passed twice at `2f12d43`, so the test is flaky on hosted Windows runners. Cause **[unverified]**. Fix it in the next cycle; never skip or disable it.
2. **Owner check of P1e-2 + P1t + P1f (2026-10-21):** item 8 failed (`Timestamp/frame count mismatch (5421 packets, 0 decoded frames)` on the earlier failing file); item 32 failed (the app does not appear in Windows startup apps); item 6 passed but showed the error text "`charmap` codec can't decode byte 0*90 in position 2200: character maps to <undefined>" (as transcribed by the owner); items 22-27 and 33-34 unanswered; item 29 unclear. New owner requests: copyable error messages, error toasts that fade out, a "Copied" confirmation, a calibration error shown in Settings since start-up, and wider link-site coverage. Analysis is in progress in the cloud project.
3. **Known regression from P1f-2 B6:** a link with unknown dimensions and output 1080/1440 can be refused for "not enough space" (unknown size treated as 1x1). Workaround: output Keep.
4. **Codex cannot permanently delete** on this machine: the Codex automatic approval review refuses deletes ("blocked by policy"). Leftovers are listed for the owner. Never bypass a refused delete.
5. **Accepted known issues:** cold start slower than Electron (718 ms vs 421 ms); about 250 MB more memory after AV1 playback; about 80-90 MB GPU memory left after closing the player.

## 10. Next work for Codex

1. **Migration check run (no commit):** through the new route, Codex restores dependencies (uv, npm, Cargo), runs lint, the CPU suite, a GPU smoke test and the Tauri build, empties `work\scratch` from inside the sandbox, and reports. This proves the route before real work.
2. **Next fix cycle:** the task document Claude is preparing (section 6), which must also fix the flaky Windows CI test (section 9.1) and the B6 regression (section 9.3).
3. **Then P1e-3, P1g, P2** in that order.

Each cycle starts with dependency restore: P1f-2 removed `node_modules`, the Cargo registry, the uv and npm caches and the Tauri target to save space (about 4.3 GB to restore) **[reported]**. `.venv`, toolchains, verified link tools and the GPU test model cache were kept **[reported]**.

## 11. Required environments

### Windows (the only implementation and test machine)

- Windows 11, NVIDIA RTX GPU with driver, drive D on NTFS (exFAT breaks the deletion guard).
- Python 3.12 via `uv` (CI uses uv 0.12.23); `uv sync --locked --all-extras`.
- Node.js 24 + npm for `gui`.
- Rust 1.99.1 with rustfmt and clippy (`gui/src-tauri/rust-toolchain.toml`); MSVC C++ Build Tools, Windows SDK, WebView2 Runtime.
- FFmpeg and ffprobe (system install), Git for Windows, HEVC Video Extensions.
- Git-ignored `work\repo\local-env.ps1` that sets session-only cache paths (`docs/WORKSPACE.md`).
- **Checked 2026-10-21 [verified]:** Claude Code 2.1.289 and Git 2.56.0 are installed. Node.js is **not** on PATH. The Codex desktop app bundles its own Codex CLI (signed in with ChatGPT) and Node runtime, but neither is on PATH and their folders change on app updates.
- **Installed 2026-10-21 [verified]:** Node.js LTS 24.20.0 (`C:\Program Files\nodejs`), Codex CLI 0.163.0 (`npm install -g`; inside the Claude desktop app it lands in the app's private package folder, so a plain terminal needs its own install), plugin `codex@openai-codex` 1.0.6 (user scope), `/codex:setup` ready with the review gate off.
- **First smoke test 2026-10-21 [verified]:** with Codex started in `work\` and writes allowed, Codex read `.ai/CURRENT_TASK.md` and created, read and deleted a file in `work\scratch`. `git` failed inside the sandbox ("Access is denied"; Git is installed per-user under AppData). The plugin runs Codex without approval prompts, so a refused action fails instead of escalating. **Owner decision (2026-10-21):** Claude on the Windows machine runs all Git operations (fetch, branch, commit, push) outside the sandbox; Codex only edits files and runs tests and builds. No machine-wide Git and no Codex config change.
- **Originally planned:** Node.js ≥ 18.18 on PATH (LTS via winget), Codex CLI (`npm install -g @openai/codex`) signed in, the official Codex plugin for Claude Code (`openai/codex-plugin-cc`), and Remote Control enabled for the work folder.

### Mac

- Claude Code with the Codex plugin, for general use.
- **Not an implementation or test machine for this project:** the app and GPU tests need Windows and an NVIDIA GPU. Do not run cycles for this repository on the Mac.

## 12. Migration cautions

- **One route per cycle.** Never run the same task in the Codex desktop app and through the plugin at the same time. Check `/codex:status` and `.ai/CURRENT_TASK.md` before starting.
- **Keep the workspace rules** in `docs/WORKSPACE.md`: work only in `work\`; never touch `VE-check\`, `AppData\`, the Recycle Bin or anything else in `D:\my-workspace`; ≤ 1 GB growth per cycle; evidence ≤ 300 MB per cycle, last 3 cycles; empty scratch; one package.
- **Codex working folder [verified]:** start Codex in `work\`, not `work\repo`. Started in `work\repo`, Codex can write only inside the repository, so writes to `work\scratch`, `work\evidence`, `work\cache` and `work\package` are blocked.
- **Codex settings are shared:** `codex exec`, the plugin and the desktop app use the same sign-in, usage limits and `~/.codex/config.toml`, so the delete refusals may continue.
- **Do not implement through `/codex:rescue` [verified]:** plugin 1.0.6 starts `codex app-server` with approval policy `never`, fixed. Inside that sandbox Codex cannot run Git, FFmpeg (installed per-user) or anything that needs the network. `codex exec -s workspace-write -c approval_policy="on-request" -c approvals_reviewer="guardian_subagent"` from `work\` ran FFmpeg, a network request and `git status` after automatic review (2 of 2 approved); uv, pytest, PyTorch with CUDA, Node and Cargo ran inside the sandbox. Approved commands run outside the sandbox with the owner's rights; the automatic reviewer is the only check, as in the desktop app. Its reasons are not logged.
- **Sandbox-owned folders [verified]:** folders Python creates inside the sandbox with mode 0o700 (pytest temp folders, `mkdtemp`) can be opened only by the sandbox account. The owner's account cannot delete them. Keep `TEMP`, `TMP` and `--basetemp` under `work\scratch`, and clean them from inside the sandbox.
- **Usage limits:** stop and record the state when a limit is reached; no retries in a loop; no extra billing. Do not enable the plugin's review gate (it can loop and drain limits).
- **Long runs:** the GPU suite took about 4 h 16 min in P1f-2 **[reported]**. The machine must not sleep, and the Remote Control session must stay open.
- **Git safety:** no force push, no reset, no history rewrite. The designer merges only under the conditions in `CLAUDE.md` (owner decision, 2026-10-21).
- **Public repository:** never commit media, weights, packages, screenshots, caches, `local-env.ps1`, device names, account names or private logs.
