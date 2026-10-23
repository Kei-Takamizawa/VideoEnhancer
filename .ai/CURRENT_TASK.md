# CURRENT_TASK: Cycle P1e-3b (spike: embedded mpv player in the Tauri window)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3b
- **Date:** 2026-10-23
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`. `main` (`aa107af`, the P1e-3a squash merge) is merged into it at `a2879e8`, so its tree equals `main`. The operator opens a new draft PR.
- This file is `.ai/CURRENT_TASK.md`. Write a new `.ai/LAST_REPORT.md`.
- Restore any dependencies the last cleanup removed. The restore does not count toward growth; report its size.

### Where this cycle sits

P1e-3a (done, merged) → **P1e-3b (this spike)** → P1e-3c (the real player with an IINA-like UI, and Compare speed) → P1e-3d (speed-ups, warm worker, recalibration).

This cycle is a **spike**: it answers whether and how an embedded mpv player works in this app, with measurements, and it leaves a small prototype. **It does not replace the current player.** The delivered app must behave exactly as on `main`.

## 2. Background and fixed decisions

- **Owner decision (2026-10-18):** the player is embedded mpv (libmpv) with an IINA-like UI.
- **Licence:** the app is MIT. libmpv must be an **LGPL build** (`-Dgpl=false`), loaded dynamically (`libmpv-2.dll`), and every bundled library must be LGPL-compatible or more permissive. No GPL component may be linked or shipped.
- **Approved design (owner, 2026-10-14, mockup in the cloud project `design/claude_design/player_mockup_v1.html`, summary here):**
  - controls: play/pause, back/forward 10 s, previous/next frame, seek bar, volume and mute, playback speed, fullscreen, video details, keyboard shortcuts sheet, close;
  - the seek-bar hover preview sits **above** the bar, YouTube style, with the time under the thumbnail;
  - **no dark panels over the video**: the controller, title, preview box, menus and the shortcut sheet are transparent, with thin shadows to keep text and icons readable. The letterbox stays black.
- **Consequence for the architecture:** HTML controls must be drawn **with real transparency over the native video picture**. A layout that puts the controls beside the video, or over an opaque panel, does not meet the approved design. It may be reported only as a fallback.
- **Today's player (`main`):** an HTML5 `<video>` in `gui/src/HistoryDetail.tsx`, fed through the app's media path (`gui/src-tauri/src/media.rs`, 1 MiB responses, at most 2 fetches at once).
- **Inputs it must play:** results and sources up to 1440 output (short side), H.264, HEVC Main10 (default output), AV1, VP9; 8-bit and 10-bit SDR; MP4, MKV, WebM, MOV; up to 60 fps; with rotation metadata.

## 3. Part A: an LGPL libmpv build

1. Find or build a Windows x64 `libmpv-2.dll` configured with `-Dgpl=false`.
   - Prefer building from official mpv sources with a documented, reproducible recipe (for example MSYS2/meson or the mpv-winbuild-cmake project with GPL options off). A prebuilt binary is acceptable only if its build configuration proves `gpl=false` and lists every dependency and its licence.
   - FFmpeg inside it must be an LGPL configuration (no `--enable-gpl`, no `--enable-nonfree`).
   - Keep D3D11 output and hardware decoding (`d3d11va`) for H.264, HEVC Main10, AV1 and VP9.
2. Record: mpv version, FFmpeg version, the full configure options, every bundled DLL with its licence, SHA-256 of each file, and total size.
3. Store the binaries under `work\cache\mpv-lgpl\` (outside the repository). **Never commit binaries.** Commit only the recipe or a download-and-verify script with pinned versions and checksums, under `spikes/mpv/`.
4. Write `spikes/mpv/LICENSES.md`: what must ship with the app (licence texts, source offer or source link) for LGPL compliance. Mark anything you are not sure about as open.

## 4. Part B: embedding approaches

Build a minimal prototype for each approach below in `spikes/mpv/` (a separate small Tauri 2 app or a Rust example, **not** the product's `gui/` crate). Each prototype plays one file in a window with a transparent HTML control bar (play/pause, seek bar with the hover preview position, time) drawn over the picture.

- **B1. Composition hosting.** WebView2 with the composition controller (`ICoreWebView2CompositionController`) and a transparent background, in a DirectComposition tree. mpv draws through the libmpv render API (D3D11) into a swap chain for composition placed below the WebView2 visual.
- **B2. Transparent overlay window.** mpv draws into a child or owned native window (`wid`). A transparent Tauri/WebView2 window owned by it sits on top and follows its position, size, minimise, maximise, fullscreen, DPI change and multi-monitor moves.
- **B3. Fallback only.** mpv in a child window, with the controls outside the picture. Implement it only if B1 and B2 both fail, and say why.

For each approach, report:
- whether HTML is truly transparent over the moving picture (screenshots outside Git; describe any halo, flicker, tearing or z-order fault);
- input: pointer, wheel, keyboard and focus reach the HTML controls; the video area passes clicks for play/pause and double-click for fullscreen;
- resize, maximise, fullscreen, DPI 100/125/150 %, a move between monitors if available, minimise and restore;
- how much Tauri, wry or WebView2 internals it needs (for example, does B1 need a Tauri fork or a custom wry setup?), and how it would fit the product's current window code (`gui/src-tauri/src/window.rs`, `main.rs`);
- the risk of breaking with a WebView2 Runtime or Tauri update.

## 5. Part C: measurements (on the development PC, RTX 4060 Ti, nothing else on the GPU)

For the best working approach (and for B2 too if both work), with synthetic fixtures made locally:

| Clip | Codec |
| --- | --- |
| 1080p30 | H.264 8-bit |
| 1440p60 | HEVC Main10 |
| 1440p60 | AV1 10-bit |
| 1080p60 | VP9 |
| 1080x1920 vertical | HEVC, with rotation metadata |

Measure and compare with today's HTML5 `<video>` player on `main` for the same files:
- time to the first frame (5 runs, median);
- seek latency to a random point (20 seeks, median and worst);
- frame step forward and back: exact frame accuracy against known frame numbers burned into the fixture;
- dropped frames over 60 s at normal speed (mpv `frame-drop-count`, and the HTML5 equivalent);
- GPU dedicated memory and CPU use during playback, and memory left after closing the player (the known HTML5 leftover is about 80-90 MB GPU memory);
- hardware decoding actually used (mpv `hwdec-current`) per codec.

Also test, without UI polish:
- **seek-bar hover preview:** a second, paused, small mpv instance (or `mpv` screenshot-to-memory) that shows a frame at the hovered time; report latency per hover move;
- **before/after for P1e-3c:** two synchronised mpv instances side by side, or one mpv with a `lavfi-complex` split/stack. Report sync drift over 60 s and the cost of each.

## 6. Part D: recommendation

In the report, recommend one approach for P1e-3c with:
- what P1e-3c must build;
- the risks, and how to test them in CI (CI runners have no GPU; say what can and cannot run there);
- the package size added, and the start-up cost (the P2 cold-start gate is Home-ready median ≤ 765 ms; mpv must load lazily, only when the player opens);
- any point that needs the owner's decision (for example, the approved transparent design is impossible, or the licence needs something the owner must accept). Put each one under "Questions for the designer" with the option you recommend. Do not stop the cycle for them.

## 7. Do not change

- The product: `gui/`, `src/`, `tests/`, the package, the current HTML5 player, the media path, settings and the engine. The delivered app must be byte-for-byte what `main` builds, apart from nothing. If you believe a product change is necessary, describe it in the report instead.
- CI must stay green. Do not add the spike to the product build, lint or test jobs unless it is fully isolated and cannot fail them; prefer leaving it out of CI.

## 8. Constraints

- Work only inside `work\`. Binaries, builds, fixtures and screenshots stay out of Git (`work\cache`, `work\scratch`, `work\evidence`).
- Downloads only from official sources (mpv, FFmpeg, MSYS2, GitHub releases of the projects themselves), verified by checksum, noted in the report. Free software only; no paid tools.
- No system-wide installs beyond what AGENTS.md allows; no driver, registry or WebView2 Runtime changes.
- Persistent growth ≤ 1 GB, except the mpv build cache under `work\cache\mpv-lgpl\` (report its size on its own line; keep it, P1e-3c uses it). Build toolchains you install for the build (for example MSYS2 under `work\cache`) also go on their own line.
- Tests and prototypes must clean up their own files. Create scratch folders so the owner's account can delete them (no mode `0o700`).
- English for all code, comments and docs.

## 9. Acceptance

- Part A: an LGPL libmpv with recorded configuration, licences and checksums, or a clear report of why none could be produced.
- Part B: B1 and B2 each built and tried, with the results above.
- Part C: the measurement table for every clip and both players, every run reported.
- Part D: a recommendation.
- `git diff main` contains only `spikes/mpv/**` and `.ai/LAST_REPORT.md` (plus `.gitignore` lines for spike build output, if needed).
- Product checks unchanged: CPU suite, ruff, pyright, GUI lint/typecheck/unit/build are **not** required to re-run if no product file changed; say so. Windows and Ubuntu CI green on the final commit.

## 10. Report (`.ai/LAST_REPORT.md`)

- Status line: COMPLETED, PARTIAL or BLOCKED. A spike is COMPLETED when every part has an answer backed by evidence, even if the answer is "this approach does not work".
- Part A details; B1/B2/B3 results; the Part C tables; the recommendation.
- Changed files.
- Disk: dependency restore; mpv build cache; toolchains; other growth; `work\scratch` at the end; free space on C and D; anything left for the owner to delete.
- "Questions for the designer", each with the default you chose.
