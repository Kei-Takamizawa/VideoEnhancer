# CURRENT_TASK: Cycle P1e-3c1 (LGPL libmpv source build, and a faster B1 host)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-P1e-3c1
- **Date:** 2026-10-23
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- **Branch:** `claude/project-thread-6lra47`. `main` (`ed00b03`, the P1e-3b squash merge) is merged into it, so its tree equals `main` apart from this file. The operator opens a new draft PR.
- This file is `.ai/CURRENT_TASK.md`. Write a new `.ai/LAST_REPORT.md`. The first lines must be the Task ID and `Status: COMPLETED | PARTIAL | BLOCKED`.
- **Diff base:** `origin/main`. `.ai/CURRENT_TASK.md` and `.ai/LAST_REPORT.md` are expected to differ.
- Restore any dependencies the last cleanup removed. The restore does not count toward growth; report its size.
- **Do not stop the cycle for a question.** Write the default you chose under "Questions for the designer" and continue.

### Where this cycle sits

P1e-3b (spike, merged) → **P1e-3c1 (this cycle: clear the licence blocker, make B1 fast)** → P1e-3c2 (the real player in the product, and Compare speed) → P1e-3d (speed-ups, warm worker, recalibration).

This cycle still works **only in `spikes/mpv/`**. The product does not change.

## 2. What P1e-3b established (read `spikes/mpv/README.md` and the P1e-3b report in Git history)

- **B1 is the chosen approach:** WebView2 composition controller over a libmpv D3D11 swap chain in one DirectComposition tree. Its transparency was verified by self-capture. B2 is dropped. Do not spend more time on B2.
- **The B1 prototype is slow:**
  - first frame 430-630 ms (B2: 30-45 ms; HTML5: 23-47 ms);
  - seek median 260-460 ms, worst up to 700 ms;
  - about 63 % of one CPU core during playback (HTML5: about 5 %).

  The step pattern in the first-frame numbers (about 430 or 630 ms) points at the polling/heartbeat loop. Find the cause by profiling; do not guess.
- **Hover preview** through a second paused mpv instance: median 505 ms, too slow.
- **Native frame stepping** was exact (36/36). HTML5 `currentTime` stepping was not (3/18).
- **A/B:** a `lavfi-complex` hstack has one clock and showed no drift. Two instances drifted by up to one frame.
- **Licence (Part A) is OPEN.** The prebuilt zhongfly LGPL DLL is 101.5 MB, has no dependency manifest, and must never ship. The MSVC/meson attempt failed because FFmpeg development files and pkg-config were missing.

## 3. Part A: a minimal LGPL libmpv built from source (the main goal)

1. **Toolchain.** Use a **portable MSYS2** from the official `repo.msys2.org` base archive (`msys2-base-x86_64-<date>.tar.xz`, checksum verified). Unpack it under `work\cache\msys2\`.
   - This is not a system install. Do not run its installer, do not add it to the system PATH, and do not touch the registry.
   - Use the `UCRT64` or `CLANG64` environment, and install packages only with `pacman` from the official MSYS2 mirrors.
   - Use MSYS2 packages for build tools only: gcc/clang, meson, ninja, pkgconf, nasm, cmake, python. Build the **libraries** that end up inside the DLL from pinned upstream source yourself, so that their versions, flags and licences are known.
   - Alternative: `mpv-winbuild-cmake` (the project the prebuilt came from) inside the same MSYS2 or the existing WSL, with every GPL and non-free option off. Choose whichever you can make work; say which you used and why.
2. **What goes in** (each from a pinned release or commit, checksum recorded):
   - **FFmpeg, LGPL.** No `--enable-gpl`, no `--enable-nonfree`; `--enable-version3` is allowed only if a dependency needs it (then the result is LGPL-3.0, say so).
     - Enable only file playback: demuxers mov/mp4, matroska/webm, and the parsers and decoders for h264, hevc, av1 (through libdav1d and/or the native av1 decoder with hwaccel), vp9, aac, opus, vorbis, mp3, flac, pcm.
     - Enable the d3d11va hwaccels for h264, hevc, vp9 and av1, plus swscale, swresample, and the avfilter pieces mpv needs (including the `hstack` and `split` filters for A/B).
     - Disable: programs, doc, network, devices, encoders, muxers, and every external library not listed here.
   - **dav1d** (BSD-2-Clause).
   - **libplacebo** (LGPL-2.1+), with its d3d11 support. If it needs glslang or shaderc, check their licences: glslang mixes BSD-3-Clause, MIT and Apache-2.0, and no GPL part may be linked.
   - **libass** (ISC) and what it needs: FreeType (choose the FTL licence option), FriBidi (LGPL-2.1+), HarfBuzz (MIT).
   - **zlib** (Zlib).
   - **mpv** at the pinned commit with `-Dgpl=false -Dlibmpv=true -Dcplayer=false`, d3d11 and d3d-hwaccel on, everything optional off. That includes lua, javascript, vapoursynth, libbluray, libarchive, libcurl, sdl2, vulkan, spirv-cross unless libplacebo's d3d11 path needs it, sixel, egl-angle, openal, cuda, uchardet, lcms2, and rubberband.
3. **Output:** `libmpv-2.dll` plus any DLLs it needs. Prefer static linking into one DLL, but LGPL libraries may stay separate DLLs if that makes replacement simpler; say which.
   - Store the result under `work\cache\mpv-lgpl\source-build\out\`. **Never commit binaries.**
   - Report the size. Expect much less than 101.5 MB; there is no hard limit, but explain anything above 40 MB.
4. **Proof:**
   - `spikes/mpv/source-manifest.json`: every component's version, source URL, checksum, licence (SPDX), configure flags and patches. Mark nothing as OPEN unless you explain exactly what is missing.
   - `spikes/mpv/source-build.ps1` (or `.sh`), which rebuilds the DLL from nothing. Run it once more from a clean build folder to show it reproduces. Byte-identical output is not required; report the SHA-256 of both runs.
   - Check the built DLL itself: it must report the mpv version and `gpl=false`. The FFmpeg it contains must report its configuration with no `--enable-gpl` or `--enable-nonfree`; check this through libmpv's `ffmpeg-version` and the static library's configuration string, not through a separate ffmpeg.exe.
   - Confirm that each required codec (h264, hevc main10, av1 10-bit, vp9) plays with `hwdec-current=d3d11va` through the B1 prototype, using the P1e-3b fixtures.
5. **`spikes/mpv/LICENSES.md`:** rewrite it for the built DLL. List the licence texts that must ship, the source offer (an archive of the exact sources and build script, attached to each release), and the user's right to replace the DLL. Close each OPEN item or say exactly why it stays open.
6. **If the source build fails** after real attempts with both routes, record each exact failure, keep the measurements below on the prebuilt candidate, and set Part A to OPEN. That gives a PARTIAL status for this cycle, because Part A is its main goal.

## 4. Part B: make B1 fast (in the spike)

Using the source-built DLL (or the prebuilt candidate if Part A failed):

1. **Profile first.** Find what causes B1's slow first frame and seek and its high CPU. Look at the render loop, the polling and heartbeat, `mpv_render_context_update` and `MPV_RENDER_UPDATE_FRAME` handling, the swap-chain present mode, the capture instrumentation, and the WebView2 message loop. Report the evidence.
2. **Fix it** with an event-driven design:
   - render only when mpv's update callback says a new frame is due;
   - wake the UI thread from mpv's wakeup callback instead of polling;
   - turn capture and self-test instrumentation off for timing runs;
   - use a flip-model swap chain with a frame-latency waitable object, if it helps.
3. **Targets**, measured on the same five clips with the same methods as P1e-3b, with the self-test capture off:

   | Metric | Target |
   | --- | --- |
   | First frame, median of 5 | ≤ 150 ms |
   | Seek, median of 20 | ≤ 200 ms |
   | Seek, worst of 20 | ≤ 400 ms |
   | CPU during 60 s playback (one core = 100 %) | ≤ 15 % |
   | Dropped frames over 60 s | 0 |
   | Frame stepping against the burned-in numbers | exact |

   - If a target cannot be met, report the best you reached, the profiling evidence of what limits it, and continue.
   - Re-run the B1 transparency self-check once after the changes, to show the picture and controls still look the same.
4. **Hover preview:** make it fast enough for a seek bar.
   - Coalesce hover moves: only the latest request counts, and older ones are cancelled.
   - Use keyframe-only or fast seeks for the preview (`hr-seek=no`), a small decode size, and a cache of recent thumbnails.
   - Optionally pre-generate a low-resolution strip on open, if it does not slow down the first frame of the main player.
   - **Targets:** median ≤ 150 ms for a new position; ≤ 30 ms for a cached one. Report what the preview shows (nearest keyframe vs exact frame). The preview may show the nearest keyframe; the main player must stay exact.
5. **A/B (for P1e-3c2):** measure the `lavfi-complex` hstack again with the source-built DLL and the event-driven host: CPU, GPU memory and drift.
   - Also try a vstack, and a split view with a movable divider (crop and overlay, or two instances under one clock master), and report whether each is feasible.
   - Recommend one method for the product's before/after compare.
6. **Lazy load:** show that the host loads `libmpv-2.dll` only when the player opens (`LoadLibrary` at open, `FreeLibrary` or process exit at close).
   - Measure DLL load plus init time.
   - Measure the memory and GPU memory left after closing, inside a host that stays open (the product case).

## 5. Part C: recommendation for P1e-3c2

In the report:
- how the B1 host should enter the product, given today's `gui/src-tauri/src/window.rs` and `main.rs`:
  - a custom WebView2 composition host for the player window only, or a wry/Tauri extension point;
  - what in Tauri 2 / wry must be patched or wrapped, and the update risk;
- the IPC between the HTML controls and the native player (commands, events, time updates);
- what can be tested on the CPU-only CI and what needs the GPU PC;
- package size added (DLLs plus licence and source materials);
- anything that needs the owner's decision, with the option you recommend.

## 6. Do not change

- The product: `gui/`, `src/`, `tests/`, the package, the current HTML5 player, the media path, settings, the engine, CI. The delivered app must be exactly what `main` builds. If you believe a product change is necessary, describe it in the report.
- The diff against `origin/main` may contain only `spikes/mpv/**`, `.ai/LAST_REPORT.md`, `.ai/CURRENT_TASK.md` (designer's) and, if needed, `.gitignore` lines for spike build output.

## 7. Constraints

- Work only inside `work\`. Binaries, builds, toolchains, fixtures and screenshots stay out of Git (`work\cache`, `work\scratch`, `work\evidence`).
- Downloads only from official sources (msys2.org and its mirrors, the upstream projects' own release pages or Git hosts), verified by checksum, listed in the report. Free software only; no paid tools.
- No system-wide installs beyond what AGENTS.md allows. No driver, registry, PATH, WebView2 Runtime or display-setting changes.
- Self-tests capture and drive only the spike's own windows, exactly as P1e-3b section 13 allowed. Never send input to any other window.
- **Disk:** report each of these on its own line, each with its size:
  - the MSYS2 toolchain;
  - the source and build trees;
  - the built output.

  Keep the toolchain and the built output, because P1e-3c2 uses them. Delete intermediate build trees once the reproduction run succeeds, if they are over 5 GB. Other persistent growth ≤ 1 GB. Stop and report if the D: drive would fall below 200 GB free.
- Tests and prototypes clean up their own files. Do not create scratch folders with mode `0o700`.
- English for all code, comments and docs.

## 8. Acceptance

- Part A: a source-built LGPL libmpv with a complete manifest, a reproducible script that was run twice, a licence list, and codec/hwdec proof; or evidenced failures of both routes (PARTIAL).
- Part B: profiling evidence, the B1 measurement table for all five clips against the targets, hover preview numbers, A/B numbers, lazy-load numbers, and the transparency re-check.
- Part C: the recommendation.
- Lint and format checks for the spike's Rust (fmt, clippy `-D warnings`) and Python (ruff) pass. Product checks are not required to re-run if no product file changed; say so. Windows and Ubuntu CI must be green on the final commit (the operator pushes and checks).

## 9. Report (`.ai/LAST_REPORT.md`)

- Status line. Part A details; Part B tables with every run, as in P1e-3b, and raw arrays in an appendix; Part C.
- Changed files.
- Disk: dependency restore; toolchain; source/build trees; built output; other growth; `work\scratch` at the end; free space on C and D; anything left for the owner to delete.
- "Questions for the designer", each with the default you chose.

## 10. Designer review of the first run (2026-10-23) and what to finish now

The first run is PARTIAL. Part B is accepted: every B1 target is met, the hover and lazy-load results pass, and the A/B recommendation (a one-clock hstack first, with the divider kept experimental) is accepted. Part C is accepted as input for P1e-3c2. **Do not redo Part B or Part C.** Finish **Part A only**.

### 10.1 The keyring blocker and what the operator does first

- **Cause.** The MSYS2 first-start step (`pacman-key --init`, then gpg's migration) hangs inside the Codex sandbox. Most likely gpg-agent cannot start or reach its socket under the sandbox account; the stray gpg-agent and dirmngr processes the operator found support this.
- **Fix, done by the operator before Codex resumes.** The operator, running as the owner's normal account, initialises the portable MSYS2 under `work\cache\msys2\` with official keys and normal signature checks:
  - `pacman-key --init`
  - `pacman-key --populate msys2`
  - `pacman -Syuu --noconfirm`, once or twice until it reports nothing to do
  - installation of the build-tool packages listed in your native UCRT64 command, plus `git`, `patch`, `make` and `autotools` if available.

  The operator stops every gpg-agent or dirmngr it started and reports the result in `work\evidence\VE-P1e-3c1\operator-msys2-init.log`.
- **What Codex does.** Use that initialised MSYS2. Do not run `pacman-key --init` again and do not change `SigLevel`.
  - If you must install another package and pacman hangs in the sandbox, stop that step, record the package name under "Questions for the designer", and continue with what you have.
  - If any step leaves a gpg-agent or dirmngr process running, stop it before you finish.

### 10.2 Then do Part A exactly as section 3 says

- Build FFmpeg (LGPL), dav1d, libplacebo, libass with FreeType, FriBidi and HarfBuzz, zlib, and mpv from pinned sources.
- Write a complete `source-manifest.json`, and a `source-build` script that rebuilds everything.
- Do two clean runs and record the SHA-256 of each.
- Prove from the DLL itself that it reports `gpl=false` and that its embedded FFmpeg configuration has no `--enable-gpl` and no `--enable-nonfree`.
- Prove that all five fixtures play with `hwdec-current=d3d11va` through the B1 host (`smoke.py` is enough here; do not rerun the full matrix).
- Re-run only the B1 H.264 first-frame and seek measurement once with the new DLL, to confirm it is not slower.
- Rewrite `LICENSES.md`.
- Choose UCRT64 native meson or mpv-winbuild-cmake, whichever gets there first.

### 10.3 Cleanup

The operator deletes the paths listed in `evidence\VE-P1e-3c1\cleanup-candidates.json`, after it re-checks each path and size:
- the duplicate `p1e3c1-*` files under `evidence\VE-P1e-3b\section13\`;
- `evidence\VE-P1f-3b`, under the keep-the-last-3-cycles rule.

Do not try these deletions yourself. Scratch is already empty. Clean only what this continuation creates.

### 10.4 Status rule

- **COMPLETED** when Part A is done as above.
- **PARTIAL** if the source build still fails at a real compile or link step. Then record the exact failing component, its command and the error, and say what would fix it.

## 11. Owner decision (2026-10-23): build libmpv on GitHub Actions instead of the PC

The MSYS2 keyring initialisation hung three times on the development PC: in the Codex sandbox, and twice for the operator outside it, including in a fresh tree. **The owner chose to build on GitHub Actions.** This replaces section 10.1 and the build route in section 3.1. Everything else in section 3 (contents, proof, licences) and section 10.2 still applies. **Do not use the PC's MSYS2 trees** (`work\cache\msys2\*`); leave them as they are.

The repository is public, so GitHub-hosted Linux runners are free. Paid runners, larger runners and any billing are not allowed.

### 11.1 The workflow

Add **`.github/workflows/libmpv-lgpl.yml`**. This is an exception to section 6, which allows this one new workflow file only. Do not change `ci.yml`.

- **Triggers:** `workflow_dispatch`, plus `push` and `pull_request` limited by `paths:` to `spikes/mpv/ci-build/**` and the workflow file itself. Product changes must not trigger it.
- **Security:**
  - `permissions: contents: read`;
  - no secrets;
  - every third-party action pinned by full commit SHA, with the version in a comment;
  - a job `timeout-minutes` of at most 330.
- **Runner:** `ubuntu-24.04`, cross-compiling for `x86_64-w64-mingw32`. Choose one approach and say why:
  - **(a)** mpv-winbuild-cmake at a pinned commit, with every GPL, non-free and unneeded option off. It builds its own toolchain, which is slower but closest to how upstream Windows builds are made.
  - **(b)** Ubuntu's `mingw-w64` packages plus meson cross files, building each library listed in section 3.2 yourself.

  Either way, every library source is fetched at a pinned version and verified by SHA-256 inside the scripts. Use `actions/cache` for the source downloads and the toolchain, keyed on the pinned versions.
- **Scripts** live in `spikes/mpv/ci-build/` (shell plus cross files or CMake options). The workflow only calls them, so the same scripts can be run by hand on any Linux machine.
- **Outputs:**
  - Upload one artifact, `libmpv-lgpl-<mpv commit short>`, with retention 30 days, containing:
    - the DLL(s);
    - `SHA256SUMS`;
    - `source-manifest.json`, generated by the build from what it actually fetched and configured;
    - the licence texts of every component;
    - `sources.tar.zst` with the exact sources, patches and build scripts. This is the LGPL source offer.
  - Print the SHA-256 of every DLL in the job log.
- **Checks on the runner before upload:**
  - `x86_64-w64-mingw32-objdump -p` shows only allowed DLL imports (Windows system DLLs, plus the LGPL DLLs you chose to keep separate);
  - the FFmpeg `configure` line recorded by the build has no `--enable-gpl` and no `--enable-nonfree`;
  - mpv was configured with `-Dgpl=false`.

  Fail the job if any check fails.

### 11.2 Iteration loop (Codex cannot run the Linux build locally)

1. **Round start.** Write or fix the scripts and the workflow. Check what you can on Windows: YAML parses, shell scripts pass `bash -n` if a bash is available, `actionlint` if you can get it from its official release. Then finish the round with `Status: PARTIAL` and the line `Awaiting CI build`. List the changed files as usual.
2. **The operator** commits and pushes. The workflow runs on the PR.
3. **The designer** reads the result.
   - On failure, the designer appends the failing step and the relevant log lines under a new subsection of section 11. The operator then resumes you.
   - On success, the operator downloads the artifact with `gh run download` into `work\cache\mpv-lgpl\ci-build\<run id>\` and checks `SHA256SUMS`. Then the operator resumes you.
4. **When the artifact exists**, do section 10.2's proof on the PC:
   - the DLL reports `gpl=false`, and its embedded FFmpeg configuration is clean (read through libmpv properties);
   - the five fixtures play with `hwdec-current=d3d11va` through B1 (`smoke.py`);
   - one B1 H.264 first-frame and seek run, compared with the prebuilt;
   - the size;
   - rewrite `LICENSES.md` for this build.
5. **Reproducibility.** The designer re-runs the workflow once with `workflow_dispatch`, and you compare the two runs' `SHA256SUMS`. Byte-identical output is not required; report the result and explain any difference you can.

At most 6 CI rounds in total. If the build still fails after 6, report PARTIAL with the exact failing component and stop.

### 11.3 Status rule for this route

- **COMPLETED** when an artifact from a green workflow run passes every check in 11.2 step 4, and `LICENSES.md` and the manifest are complete.
- **PARTIAL** for "Awaiting CI build" rounds and for the 6-round stop.

### 11.4 CI round 1 result (designer, 2026-10-25): FAIL in the toolchain step, 1 of 6 rounds used

Run 40167238004, job `build`, failed about 1 minute after start in `driver.py toolchain`. The PR-triggered run 40167239065 has the same commit:

```text
File "spikes/mpv/ci-build/driver.py", line 170, in toolchain
    checksums = ubuntu_source_metadata(package, version)
File "spikes/mpv/ci-build/driver.py", line 138, in ubuntu_source_metadata
    raise ValueError(f"No authenticated source metadata for {package}={version}")
ValueError: No authenticated source metadata for binutils=2.41.90.20240122-1ubuntu1
```

The installed package was `binutils-mingw-w64-x86-64 2.41.90.20240122-1ubuntu1+11.4`. Its `Built-Using` field names `binutils (= 2.41.90.20240122-1ubuntu1)`, and the runner's `deb-src` index does not offer that exact source version.

**What to change:**
- **Toolchain sources are not part of the LGPL source offer.** The compiler and binutils are not shipped. Do not fail the build because a toolchain package's source, or a source named in its `Built-Using` field, is not in the `deb-src` index. Record each such package with its name, version and `unavailable in deb-src` in the manifest's toolchain section, and continue. Archive the sources that are available, as now.
- **Pieces of the toolchain that end up inside the shipped DLLs are a different matter.** These are the mingw-w64 CRT and headers, winpthreads, and libgcc / libstdc++ if they are linked statically.
  - Record each one's exact package version and licence: ZPL/public domain, MIT, and GPL-3.0 with the GCC Runtime Library Exception. The exception allows shipping without source.
  - Keep fetching their sources when the index has them. When it does not, record the package's `Vcs`/Launchpad URL instead of failing.
- **Check this path before the next push.** Add a unit test in `test_driver.py` for the missing-source path.
- **Find further toolchain-step problems before the next round:** run as much of `driver.py plan` / `toolchain` locally as you can with mocked apt output.

Then end the round with `Awaiting CI build` again, as in 11.2.
