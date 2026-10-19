# CURRENT_TASK: Cycle P1f (add videos from a link)

- **Task ID:** VE-P1f, revision 3
- **Date:** 2026-10-12 (revision 2: 2026-10-16; revision 3: 2026-10-18)
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## Revision 3 (2026-10-18): after the P1t review

This revision adds Part P and fixes the start commit. Revision 2 and revision 1 still apply where this section does not override them.

**Start condition:** create branch `p1f-links` from `p1t-tauri` at `cb085bc` (P1t final, reviewed). Draft PR to base `p1t-tauri`.

**Order:** Part P → Part T → Part R → Part L → Part G.

**Designer decisions on P1t (2026-10-18):**
- P1t is accepted as PARTIAL. Its failed gates stay FAIL in the record and are not relabelled: cold start (679.3 ms against 549.3 ms), warm History (134.65 ms against 100 ms), the AV1 memory gates and the repeat-memory gate.
- The media path stays M1 with 1 MiB responses, with the Low memory target while no player is open. M3 stays out.
- The AV1 and repeat-memory results become known issues for the owner check. Reading of the repeat test: the M1 total levels off (cycles 5-10 add 1.4 MB per cycle for AV1 and 0.7 MB for H.264, against 12.0 MB for Electron), so no fix is required in this cycle.
- Electron is removed in this cycle (P4), after the P2 measurements. Git history keeps it.

### Part P: P1t follow-ups

**P1. Storage and shell fixes from the code review** (base `cb085bc`; line numbers are from that commit):
1. **Remove and Move must never overlap.** `remove_old` (`gui/src-tauri/src/storage.rs:255-326`) does not take `storage_busy`, and the Storage card does not disable Move during Remove (`gui/src/Storage.tsx`). Because `remove_old` writes back the pointer it read at the start, a Move started during a slow Remove can be overwritten, and the next launch silently opens the old folder. Hold the same busy lock for the whole removal, disable Move and Remove while either runs, and re-read the pointer just before writing it.
2. **No full verification on every status poll.** `storageStatus` runs `verify` every 500 ms (`Storage.tsx:22`, `storage.rs:197`). That is an engine health call, a full storage scan and a probe write with `sync_all`, each time. Polls must not overlap. Run the full verification only when the Storage card opens, after a Move finishes, and again inside Remove (as now). The progress poll stays cheap.
3. **Remove counts and result.**
   - The confirmation counts only the files that will really be deleted (not `protected_video` entries, and not entries already blocked by a damaged job manifest).
   - If any manifest file in the old folder could not be removed (locked, changed, protected), keep `previous` and the remaining manifest entries in the pointer, so Remove can be offered again later, and say how many were kept and why.
4. **Older pointer without a manifest.** A pointer written by the Electron app has `previous` but no `manifest`; this is the owner's real state. Remove stays disabled, which is correct, but say why: "This folder was moved by an earlier version, so the app can't check it before removing it. Keeping it is safe." Do not offer another way to delete it.
5. **Start with Windows** (`gui/src-tauri/src/window.rs:248-254`, called every 3 s from `main.rs:309`): write the Run value only when it differs from the current one. Skip the Run-key sync in debug builds as well as in `e2e` builds.
6. **Media protocol details** (`media.rs:146`, `169-178`): a HEAD reports the full file size as `Content-Length`. A GET without `Range` keeps the 1 MiB cap. Pick the most standard response that keeps the cap, and test both.
7. **External links** (`commands.rs:129-136`): pass the parsed and normalized URL to the shell, not the raw string, as `on_new_window` already does. Add a test with a quote in the URL.
8. **Release build check in CI:** run the check that `desktop_test` is absent from the release build on the Windows CI job, if the build time allows. If it doesn't, say so in the report.

**P2. Measure before removing Electron** (same CDP harness and fixture as P1t G1, Electron from the P1t baseline package):
1. Warm History on Electron, median of 10.
   - If Electron is also above 100 ms, report both numbers; the designer re-bases the budget.
   - If Electron is at most 100 ms, find the Tauri-specific cause. Fix it if the fix stays in the renderer or the shell and changes no design; otherwise report the cause.
2. Cold start split into phases, median of 5, Tauri and Electron: process start, window created, webview ready, first paint, engine healthy. Remove a wait only when one phase clearly causes it and the fix changes no design. The target stays at most 10% above Electron's median from the same run.

**P3. GPU memory left by the player** (measurement only, no fix):
- On the 1440p synthetic H.264 and AV1 fixtures (recreate them with the P1t recipe), record the dedicated GPU memory per app process, and the total from `nvidia-smi`:
  - before playback;
  - during 2 minutes of playback;
  - 30 s and 5 minutes after the player closes.
- Then start one allowed GPU job (source at most 1080, output at most 1440) with the player closed. Report the free GPU memory before it starts, and its speed against the same job with the app freshly started.
- Never use a source above 1080 or an output above 1440.

**P4. Remove Electron** after P2:
- Remove `gui/electron`, the Electron and `@electron/packager` dependencies, and the Electron-only scripts, tests and CI steps.
- Update the docs so they describe only Tauri.
- Keep the U1 and U2 reading of the old Electron pointer locations; that is migration, not Electron.
- The package rule still holds: one package, `work\package\VideoEnhancer\`.

**P5. Default output codec:** HEVC stays the default (owner decision 2026-10-18). Do not change it. The M4 guidance stays.

**Cleanup:** the owner will have emptied `work\scratch` by hand before this cycle. Keep the old Electron package `work\package\VideoEnhancer-win32-x64` until P2 is done. Then add it to "For the owner to delete" if your own delete is refused.

## Revision 2 (2026-10-16): after the move to Tauri

This revision overrides the parts it names. Everything else in this file still applies.

**What changed since revision 1:**
- Cycle P1t replaced Electron with Tauri 2 (`.ai/CURRENT_TASK.md` of P1t, branch `p1t-tauri`). The desktop shell is now Rust (`gui/src-tauri`), and the renderer reaches it only through `window.desktop`.
- All cycle work now lives in `D:\my-workspace\VideoEnhancer\work` under `docs/WORKSPACE.md`.
- The owner checks P1e-2, P1t and P1f together after this cycle, and merges afterwards.

**Decisions (2026-10-16):**
1. **Video links only.** Part M (models from a link) and everything that belongs only to it are deferred to a later cycle. Do not build them. This covers M1 to M6, G2, the model items of G3 and G4, and `docs/ADDING_MODELS.md`.
2. **Sign-in is still not supported** (owner decision 2026-10-16). Links that need sign-in are refused with the L2 message. Instagram links may often fail this way (a yt-dlp report from March 2026, cause not confirmed); report what the local tests can show, and nothing about real Instagram.
3. **Sources up to 1080p only** (owner decision 2026-10-16). This replaces "4K sources are Fast-only". See Part R.
4. **Output sizes: Keep, 1080 (default) and 1440.** 2160 is removed (owner decision 2026-10-16). See Part R.

**Start condition (overrides the one below):**
- Create branch `p1f-links` from `p1t-tauri` at the commit the owner names when handing this file over (the designer will have reviewed it). Open a draft PR to base `p1t-tauri`. Do not push to `main`, `p1d-ui-v2` or `p1t-tauri`.
- Save this file as `.ai/CURRENT_TASK.md` and commit it. At the end, write `.ai/LAST_REPORT.md` (English, UTF-8 written once, ASCII punctuation, under 40 KB), and update it after the final CI run.
- **Deleting your own files:** first try the delete inside `work\` without asking for approval. If the auto-approval still refuses, list at most 3 folders with sizes under "For the owner to delete".
- The owner's app data is `D:\my-workspace\VideoEnhancer\AppData`. `VE-check\` and `AppData\` are the owner's: never write, move, clean or open them. Every test uses an isolated `VE_HOME` under `work\scratch`.

**New Part R: size limits** (do it before Part L, because L3 depends on it)

*Why:* 4K sources ran out of GPU memory in Standard (P1e-2), and take about 9x as long as 720p. A 2160 output reserved 14.5 GB on the owner's 8 GB GPU and always spilled into shared memory. The owner's main material is 720p social video.

- **R1. Which sources are supported:** a source is supported only if its short side is at most 1080 px.
  - Examples: 1920x1080, 1080x1920 and 720x1280 are supported; 2560x1440 and 3840x2160 are not.
  - Use the same displayed dimensions that the output-size and estimate code already use (after rotation).
- **R2. Where the limit is enforced:**
  - The engine's admission check refuses an unsupported source with a 400 response. The UI check is not the only guard.
  - **Add:** an unsupported file is refused with "This video is larger than 1080p (short side N px). VideoEnhancer processes videos up to 1080p." Use the existing per-file blocking-warning layout; the other files in the same batch still add.
  - **Compare on my video:** the same refusal.
  - **Unfinished jobs already in a queue** with an unsupported source or a 2160 output never start. Each shows "No longer supported: <reason>" with Remove. Finished History items stay as they are, including their playback.
- **R3. Output sizes:**
  - The choices become Keep, 1080 (default) and 1440. Keep now means the source's own size, which is at most 1080.
  - A saved default of 2160 in settings becomes 1440, and the change is logged.
- **R4. Clean-up:**
  - Remove the code paths that became unreachable: the 4K Fast-only guidance, and the 2160 estimate and calibration entries.
  - Replace their tests with refusal tests. Do not leave dead branches.
  - Keep the engine able to read and play existing larger outputs in History.
- **R5. Tests:**
  - sources of 1080x1920, 1920x1080, 1081x1920 and 1440x2560, plus a rotated 1920x1080 (rotation metadata);
  - the API refusal;
  - a mixed batch in Add;
  - a queued job with a 4K source and one with a 2160 output;
  - the settings migration from 2160.

**Changes to the parts below:**
- **Order:** Part T → Part R → Part L → Part G.
- **L1, entry points:**
  - Keep the "Paste a video link" field in Add.
  - Keep Ctrl+V on Home: when focus is not in a text field, a pasted `http`/`https` link opens Add with that link. Use the paste event, not a clipboard read permission.
  - **Remove the drop of a link dragged from a browser.** In Tauri on Windows, the page cannot receive it while native file drops are on (P1t decision 5).
- **L2, the link card thumbnail:** the engine fetches the thumbnail and serves it through its API. The renderer's Content Security Policy stays as strict as in P1t (no remote images).
- **L3, quality (replaces the 4K rules below):**
  - The picker lists only streams whose short side is at most 1080 (Part R).
  - The default is the highest-quality SDR stream whose short side is at most the chosen output's short side, and never above 1080.
  - "Best available" means the best stream up to 1080, so a 4K YouTube video can still be added at 1080p.
  - If a link has no stream of 1080 or less, refuse it with the R2 message.
  - The rest of L3 (fps, bitrate, HDR disabled, audio, MKV remux) stays.
- **L4, the download folder:** the first link download asks for a download folder with the folder picker, and remembers it in Settings › Video links. Do not default silently to `%USERPROFILE%\Videos`, because the owner's drive C was full.
- **L4, History "Source link":** add a shell command that opens a job's stored `source.url` in the default browser. It reads the URL from the engine by job id, allows only `http` and `https`, and never accepts a URL from the renderer. The P1t external-link allowlist stays unchanged for everything else.
- **T1, tool versions:** on 2026-10-16 the latest stable yt-dlp was still 2026.08.19, and the latest nightly was 2026.09.27. yt-dlp deprecated Bun in May 2026 and recommends Deno. At implementation time, check yt-dlp's documented minimum Deno version and use that instead of the 2.3.0 written below.
- **G4, screenshots:** all on the Tauri app, video-link screens only.
- **G6:** add the P1t Rust checks and the CDP end-to-end tests.
- **The package** for the owner's check is `work\package\VideoEnhancer\` (one-package rule).

---

*Revision 1 follows. Where it conflicts with revision 2, revision 2 wins.*

**Start condition (revision 1, replaced above):**
- Start from the latest `main` after PR #5 (P1d and P1e) is merged, on a new branch `p1f-links`.
- If PR #5 is not merged yet, branch `p1f-links` from the head of `p1d-ui-v2` instead, and say so in the report.
- Save this file as `.ai/CURRENT_TASK.md` and commit it. At the end, write `.ai/LAST_REPORT.md` (English, UTF-8 written once, ASCII punctuation, under 40 KB), and update it after the final CI run.
- Open a draft PR to `main`. Do not push to `main`.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option, and continue.
2. Order: Part T (tools) → Part L (video links) → Part M (model links) → Part G (acceptance).
3. Never report a test as passed if it did not run. Report every run of a gated measurement.
4. The owner's queue, settings, videos, models and Recycle Bin are not test data. Use a separate engine home for every test.
5. **Network rules for tests:**
   - **CI:** no third-party sites at all. Use a local HTTP test server with synthetic media.
   - **Local real-network tests:** only sources that allow downloading, for example Wikimedia Commons and the Internet Archive.
   - **Never download from YouTube, TikTok, Instagram or X in tests.** The owner tests those sites in their own check.

## 0. Goal and owner decisions (2026-10-12)

The owner wants to paste a link to an internet video and have it processed at the best quality available, and to add restoration models from a link such as GitHub or Hugging Face. The owner chose this cycle before P2 (faces, skin and hair). Control from another device comes after P2, on the same Wi-Fi only.

**"Uncompressed" is not the goal.** The owner asked for videos "uncompressed, at the best quality". Every site delivers video that is already compressed (VP9, AV1 or H.264), and converting it to an uncompressed or lossless file adds no quality (raw 1080p30 is about 5.6 GB per minute). So:
- download the best available video and audio streams;
- merge them without re-encoding (remux only);
- hand that file to the normal pipeline, which encodes once at the end.

The owner was told that some sites' terms (for example YouTube's Terms of Service, 15 Dec 2023) do not allow downloading without permission, and still wants the feature for personal use. Show that note once, in plain words, when the link tools are installed.

## 1. Part T: link tools (optional install, manual update)

1. **What gets installed:**
   - **yt-dlp:** use the official Windows executable `yt-dlp.exe`. The research found the latest stable release is 2026.08.19. Licence: Unlicense; the PyInstaller executable is a GPLv3+ combined work.
   - **Deno:** a JavaScript runtime, which yt-dlp needs for YouTube. It must be version 2.3.0 or later. Licence: MIT.
   - Do not add yt-dlp to the Python lock file. Run both as separate processes. This keeps the engine's dependencies fixed, and lets the update button use the executable's own updater (`-U`, `--update-to`), which does not work for pip installs.
2. **Where:** `<engine home>/tools/yt-dlp/` and `<engine home>/tools/deno/`. FFmpeg is the existing one.
3. **Install:** Settings › Video links › "Install link tools".
   - The dialog shows the two tools, their sizes and their licences, and the plain note: "Only download videos you have the right to use. Some sites' terms do not allow downloading."
   - Download from the official GitHub releases. Verify against the published SHA-256 checksums (yt-dlp publishes `SHA2-256SUMS`; check what Deno publishes).
   - If no checksum is published, refuse and say why. Never run an unverified binary.
   - Show determinate progress with time left (as in P1e Part Q).
4. **Update:**
   - Settings shows each tool's version and release date.
   - "Check for updates" contacts GitHub only when pressed. "Update" installs the newer release with the same verification.
   - Channel: Stable (default) or Nightly. YouTube fixes often reach Nightly first.
   - There is no automatic check and no telemetry.
   - When a link fails with a site or extractor error and yt-dlp is older than 60 days, the error suggests "Update link tools".
5. **Uninstall** removes both folders. Jobs already downloaded are not affected.
6. **Process rules:**
   - Run the tools with an argument list, never through a shell.
   - Use `--ignore-config`, so that no user or system config can add options. Never use `--exec`.
   - Allow only `http` and `https` links.
   - Redirects must stay on `https`, or on `http` only if the original link was `http`.
   - Kill the whole process tree on cancel, as P1d-3 does for compare children.

## 2. Part L: add videos from a link

### L1. Entry points
- The Add dialog gets a "Paste a video link" field at the top, with a "Check" button.
- Paste a link with Ctrl+V on Home, or drop a link dragged from a browser (`text/uri-list` or `text/plain`). Either one opens Add with that link.
- If the link tools are not installed, the field offers "Install link tools" and nothing else.

### L2. Checking a link
- Run yt-dlp in metadata mode (`-J`, without downloading). While it runs, show "Checking link…" with Cancel.
- Show a link card with:
  - the thumbnail, title, site, uploader and duration;
  - a quality picker;
  - the download size and the processing estimate for the chosen quality and mode.
- **Playlists and channels:** list up to 200 entries with selection marks, all selected by default. Each selected entry becomes its own job.
- **Refuse, with a plain reason:**
  - live streams and upcoming premieres;
  - content that needs sign-in: "This video needs you to sign in to the site. Sign-in is not supported yet.";
  - DRM-protected formats;
  - links that fail for other reasons, with yt-dlp's short reason and, if old, the update hint.
- **Already downloaded:** if the same video (same extractor and video id) was downloaded before and the file still exists with its recorded identity, offer "Use the file downloaded on <date>" instead of downloading again.

### L3. Choosing the quality

Restoration runs at the source resolution. A 4K source in Standard is about 9x slower than 720p (from the built-in profile, the review expects 4K Standard segments of only about 2 s; this is inferred, not measured), so the default must not silently pick the biggest stream.
- **The quality picker** lists every video format with: resolution, fps, codec, dynamic range (SDR or HDR), size, and the processing estimate for the current mode.
- **The default** is the highest-quality SDR stream whose short side is at most the chosen output short side.
  - If none exists, use the smallest SDR stream above it.
  - Among equal resolutions, prefer higher fps, then higher bitrate.
  - The rule must match yt-dlp's notion of resolution (`res` is the smallest dimension). Verify this against the installed version.
- **"Best available"** (the largest stream) is one choice in the picker, shown with its longer estimate.
- **HDR** formats are shown but disabled, with "HDR is not supported yet", because the pipeline does not support HDR.
- **Audio:** the best audio stream. Keep it without re-encoding unless the output container cannot hold it.
  - Report which audio codecs reach the final output untouched for each output container.
  - If a re-encode would be needed, ask under "Questions for the designer" before adding one.
- **Merge:** remux video and audio into MKV (`--merge-output-format mkv`), with no re-encode. Confirm the pipeline reads MKV with VP9, AV1 and H.264 video and Opus or AAC audio, and fix it if not.

### L4. Downloading as part of the job
- **The job starts in a new state "downloading"**, ahead of analysis. Its card shows percent, speed, time left and Cancel.
  - Downloads do not use the GPU. They run at any time, even outside the operating hours.
  - A setting caps simultaneous downloads (1–3, default 2).
- **The GPU queue skips a job that is still downloading.** The planner treats a download as "ready at <estimated time>", using the size and the measured download speed. Until the first speed sample, treat it as ready when the download finishes.
- **Files:**
  - Download into a folder set in Settings › Video links. The default is `%USERPROFILE%\Videos\VideoEnhancer Downloads`.
  - Use safe Windows file names: the title, trimmed to 120 characters, plus the video id.
  - Write to a temporary name and rename only when the download is complete.
  - The free-space check (P1e B2) includes the download size.
- **After the download:**
  - Probe the file normally. If it turns out to be HDR or otherwise unsupported, the job fails with the reason, and the downloaded file is kept.
  - Record its identity like any original (P1d-3 S-M1), so History deletion and "Delete the original when it is done" work for it. Both go to the Recycle Bin behind the guard, as for local files.
- **Interruptions:**
  - Pause all and Quit stop downloads too. Resume continues partial downloads where yt-dlp supports it, and restarts them otherwise.
  - A failed download retries up to 3 times with back-off, then fails with the reason and a "Retry" action.
- **History:** the detail popup shows "Source link" (opens in the default browser) and the downloaded file's location. Store the link in the manifest (`source.url`, `source.extractor`, `source.id`, `source.format`). Never send it anywhere.

### L5. Estimates
- Before the download, the estimate uses the format's width, height, fps and duration from the metadata, through the same estimate function as files.
- After the download, the normal probe replaces it.
- The Add card says "Download about X MB" and "Processing about H:MM:SS". The finish time includes the download once a speed sample exists.

## 3. Part M: add models from a link

### M1. Entry point
Models › "Add a model from a link…", next to the existing "Add my own model…".

### M2. Accepted links
- **GitHub:**
  - a release asset (`/releases/download/<tag>/<file>`);
  - a raw file (`raw.githubusercontent.com`);
  - a `blob` page, which is converted to the raw link and shown to the owner.
- **Hugging Face:** `/resolve/<rev>/<file>`. A `/blob/` page is converted to `/resolve/`.
- **Any other `https` link** to a single file.
- **Repository or model pages** are refused with "Paste the link to the model file itself (.safetensors or .pth)."
- **File types:**
  - `.safetensors` (preferred);
  - `.pth`, `.pt` and `.ckpt`, loaded with `torch.load(weights_only=True)`. The research notes that `weights_only` is not a sandbox (CVE-2025-32434 affected 2.5.1 and earlier), so show "A .safetensors file is safer than .pth" when the link is not safetensors;
  - archives are refused in this cycle.
- **Size:** files over 500 MB need a confirmation, and files over 2 GB are refused.

### M3. Download and identify
- Download with progress and time left. Compute SHA-256 and show it. When Hugging Face publishes a hash for the file, the two must match.
- **Identify the architecture**, only with code already in the repository:
  - **Spandrel models** (main `spandrel` package):
    - scale 1 becomes a "cleanup" model;
    - scale 2 or 4 becomes a "size" model;
    - other scales are refused.
  - **BasicVSR++ state dicts** that match C1's architecture are accepted as cleanup video models, for example the owner's future fine-tunes.
  - **Face restoration architectures** (for example GFPGAN, CodeFormer, RestoreFormer) are refused with "Face models come in a later version."
  - **Anything else** is refused with the reason.
- Never import or run code from the link's repository.

### M4. Manifest and licence
- Generate the manifest automatically:
  - the id from the file name plus a short hash;
  - category, architecture, scale and temporal flag;
  - weights file name, SHA-256 and bytes;
  - `source.url`.

  The title is editable and starts from the file name.
- **Licence:**
  - The owner must pick one before the model can be used: MIT, Apache-2.0, BSD, CC-BY, CC-BY-NC, Other (free text), or "Unknown".
  - They must also tick "I may use this model".
  - Record the licence and `commercial_use_allowed` from it. Unknown means not allowed.
- The card summary says "A model you added from <host>".

### M5. Qualification before use
Use the same checks as catalog models:
- load on the GPU;
- run synthetic frames at the 1080 output size;
- choose the largest tile among 512, 256 and 128 whose sampled process peak is at most 5.0 GB;
- check the output shape and that there is no NaN or Inf;
- measure the reference speed on the 5 s reference clip (P1d-3), so estimates are known.

If any check fails, the model stays listed as "Not usable: <reason>", with Remove. It is never offered in Add or Compare. Show the qualification as a determinate bar with time left.

### M6. After qualification
- The model appears in Models, Add and Compare like any custom model.
- Uninstall works as in P1e Part M. The default model rules still apply.

## 4. Part G: acceptance

- **G1. Local server, in CI:**
  - a direct MP4 link (generic extractor);
  - an HLS stream;
  - a DASH stream with separate video and audio;
  - a playlist page of 3 entries;
  - a link that needs sign-in (HTTP 403 with a login page);
  - a live-stream marker;
  - an HDR-tagged format;
  - a server that stops halfway, so retry and resume are tested.

  Check:
  - the default quality rule for portrait and landscape at outputs 1080 and Keep;
  - that HDR is disabled;
  - the remux keeps stream bytes (compare packet hashes of video and audio with the served streams);
  - cancel kills the process tree;
  - pause and resume;
  - the free-space check;
  - "Use the file downloaded on <date>".
- **G2. Model links, local server, in CI:**
  - a safetensors cleanup model;
  - a `.pth` size model;
  - a GitHub `blob`-style URL rewrite;
  - a Hugging Face `/blob/` rewrite;
  - a repository page refusal;
  - a face model refusal (a synthetic state dict with the right key names is enough);
  - a non-model file refusal;
  - a file over 2 GB refused from its headers, without downloading it.
- **G3. Real network on the owner's PC** (allowed sources only):
  - one Wikimedia Commons video and one Internet Archive video, downloaded, processed in Fast and checked;
  - one permissively licensed real model from GitHub releases (for example a SwinIR classical super-resolution `.pth`, Apache-2.0) and one `.safetensors` model from Hugging Face with an MIT or Apache-2.0 licence, imported and qualified. Name the files, licences and SHA-256 values in the report.
  - Install, check for updates, update and uninstall the link tools, with verified checksums.
- **G4: screenshots** at 1280x800 and 1100x700, in dark and light:
  - Add with a link card and the quality picker;
  - a playlist;
  - a downloading job on Home;
  - Settings › Video links;
  - the model link dialog with the licence step;
  - qualification;
  - a "Not usable" card.

  Store them outside the repository and list their paths.
- **G5:** all GPU-marked tests. The default pipeline output must not change; strict equality as before.
- **G6:**
  - `ruff`, `ruff format --check`, `pyright`, CPU tests and D2;
  - GUI lint, typecheck, unit tests, build, e2e and package;
  - Windows and Ubuntu CI green on the final commit.
- **The owner's check:** build the package and give its path. I will write the checklist; it will include real sites the owner chooses.

## 5. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs are in English.
- **Never commit:**
  - media, weights, downloaded tools, previews or generated videos;
  - `node_modules` or build output;
  - screenshots;
  - the owner's logs, links or private sample names.
- **User videos**, including downloaded ones, are never deleted permanently. Only the deletion module may remove them, and only to the Recycle Bin, behind the guard.
- No telemetry and no automatic update checks. Every network access starts from an owner action, except a download the owner queued.
- Keep the service security model: localhost, token. The link and model endpoints require the token like every other endpoint.
- No new catalog entries. Imported models are custom models.
- New dependencies: open-source licences only, named in the report.
- Update `docs/GUI.md`, `docs/API.md`, `docs/TROUBLESHOOTING.md` and `docs/ADDING_MODELS.md`.

## 6. Report (`.ai/LAST_REPORT.md`)

- A table per part (T, L, M, G): done / partial / NOT RUN / BLOCKED, with evidence.
- The tool versions and checksums installed.
- The audio-codec table from L3.
- The package path for the owner's check.
- "Questions for the designer", each with the default you chose.
- Exact reproduction steps.

Never report a test as passed if it did not run.

## Designer decision on P1f T6 (2026-10-18)

The T6 process rules in .ai/CURRENT_TASK.md are updated the same way.
The rule "Redirects must stay on https, or on http only if the original link was http" is withdrawn. Your probe shows yt-dlp 2026.08.19 follows an HTTPS-to-HTTP redirect, and it has no option to refuse one. Do not add a proxy or a yt-dlp plugin.
Instead:
1. After the metadata check (-J), if the link is https and the chosen format's url, manifest_url or fragment_base_url in the metadata is http, refuse the download with: "This site would send the video without encryption, so VideoEnhancer won't download it."
2. Redirects during the transfer follow yt-dlp's default. Record this accepted limit in one sentence in the docs: a site can still redirect a download from an https link to plain http.
3. Tests: a local https link whose chosen format URL is http is refused. Keep t-redirect-probe.json as evidence of the documented limit.
The other T6 process rules stay: an argument list with no shell, --ignore-config, no --exec, http/https links only, verified binaries, and killing the whole process tree on cancel.
Resume the link work that you put on hold, in the existing order.

## L2b. Designer decision on direct video links without size metadata (2026-10-18)

yt-dlp's generic extractor gives no width, height, fps or duration for a direct file. Keep not guessing them. Add a header probe and a fallback.
1. Header probe
- For each format the user may pick whose width, height or duration is missing, run the app's existing ffprobe on that format's url from -J, before any download.
- Argument list, no shell. Pass the format's http_headers.
- -protocol_whitelist https,tls,tcp for an https link; add http only when the link itself is http.
- Read timeout 10 s; kill the process tree after 20 s in total. Keep the probe and analyse limits small, and write nothing to disk.
- Read width, height, rotation, frame rate, duration, codec and the colour transfer (to mark HDR).
- Use the result for R1, the L3 default and the L5 estimate, exactly like yt-dlp metadata.
2. HTTP refusal
 When the probe fails because http is not on the whitelist for an https link, refuse with the T6 message.
3. Any other probe failure or a timeout
- Allow the link, and show on the card: "VideoEnhancer can't read this video's size before downloading. It is checked after the download. If it is larger than 1080p or HDR, the job stops and the downloaded file is kept."
- The estimate reads "after download".
- After the download, the normal probe applies R2 and the HDR rule, as L4 already says.
4. G1 tests
- a direct MP4 with its header at the start and Range support: size known before download;
- a direct 1440p MP4: refused before download;
- a rotated portrait MP4: R1 checked after rotation;
- a direct MP4 on a server without Range and with its header at the end: the fallback path, then the check after download;
- an https link whose file redirects to http: refused.
Continue in the existing order.

## Designer decision on P1f L3 audio (2026-10-18)

The L3 audio rule in .ai/CURRENT_TASK.md is updated the same way.
Keep the existing mux rule for every job, local and link alike:
- codecs in MP4_AUDIO_CODECS are copied;
- anything else, including Opus, becomes AAC 256 kbps in the MP4 output.
Reason: the output is always MP4, and Opus inside MP4 often plays with no sound on iPhone and Safari (Apple supports Opus only in CAF, by a developer forum report). One rule for every job also keeps G5's default output unchanged.
So:
- do not add Opus to MP4_AUDIO_CODECS;
- do not add a link-only audio rule;
- keep the yt-dlp best-audio choice;
- in the report, list which audio codecs reach the MP4 output untouched and which become AAC 256 kbps;
- keep l-audio-container-probe.json (Opus and AAC copy into MP4 with matching packet hashes) as evidence for a possible later "keep original audio" option.
Continue in the existing order.

## Designer decisions received 2026-10-18 (supersede earlier rows)

### P1f L2 Already downloaded
1. Keep your current rule: for the generic extractor, the normalized link must equal the stored source.url. Normalize only the case of the scheme and host and drop the fragment. Keep the path and query exactly. Signed links that change on every visit are then never reused, which is accepted.
2. Add two checks for the generic extractor only:
- When yt-dlp reports timestamp (the server's Last-Modified) now and one was stored at download, they must be equal. Store it as source.timestamp when the download finishes.
- The width, height and duration known before the download (metadata or the L2b probe) must equal the stored file's probe, with the duration within 0.5 s. If any of them is unknown (the L2b fallback), do not offer the earlier file.
- Otherwise download as usual, with no extra message.
3. Site extractors keep extractor_key plus id only, the same key as yt-dlp's download archive. Do not add a link match there.
4. For all links, the offer reads "Use the file downloaded on <date> (<width>x<height>, <fps> fps)", and "Download again" stays available.
5. Write the known limit in the report: a file replaced at the same link with the same resolution and duration and an unchanged Last-Modified is still offered.
6. Tests (G1): two different video.mp4 files on two local hosts give no offer; the same link with the file replaced by one of a different duration gives no offer; the same unchanged link gives the offer; the same link in the L2b fallback gives no offer.

### P1f L3 Commons VP9 finding
Designer decision: fix it in this cycle. Do not correct or guess timestamps.
Why now: VP9 is common for link sources, and L3 already asks for it. Also, decode.py _cuda_frames skips a decoded stamp smaller than the expected one. So a repeated label is skipped silently, and a segment that does not reach the last frame can finish with frames shifted by one, without an error. This is inferred from the code; confirm it with a test.
1. Make the check strict. After a seek, the first decoded stamp must be one of the analysed source_pts, and every following stamp must equal the next analysed entry. A repeated, missing or unknown stamp is an error at that frame.
2. Choose the decoder per job, in analysis. Compare the NVDEC stamps of the whole file with the packet timeline, using the same NVDEC calls the segments use.
- All stamps match: NVDEC as now.
- Any stamp differs: the job uses the existing FFmpeg decode path. The models stay on CUDA, and decoded frames go to the GPU before the same nv12_to_rgb conversion.
- Record the decoder and the reason in the manifest and in Copy details. Add no new UI.
3. At run time, if check 1 fails in a segment on NVDEC, switch that job to FFmpeg decoding, retry the segment once, and record it.
4. Call Flush() only if the binding has it. Otherwise rely on the demuxer's empty packet at the end of the file. Confirm that the last frame is decoded for H.264 and VP9.
5. Tests:
- The Commons VP9 file finishes in Fast with 131 output frames.
- Archive H.264 keeps NVDEC.
- A fake decoder returning [0, 0, 33, ...] fails at frame 1.
- The same H.264 file decoded both ways gives identical converted frames (maximum difference 0). If not, report the maximum difference and the PSNR, and leave rule 3 out until I answer.
- Make local VP9 (alt-ref) and AV1 files, at most 1080p, and report the NVDEC stamp result and the decoder chosen for each.
- G5 strict equality still holds.
6. Report:
- For the Commons file, compare NVDEC and FFmpeg pictures by hash, frame by frame: are only the labels shifted, or is a picture repeated or missing?
- Give the Fast 1080p speed ratio of FFmpeg decoding against NVDEC on the same H.264 file. If FFmpeg decoding is more than 10% slower, ask under "Questions for the designer".

### P1f L1 browser link drop
The browser link drop is out of this cycle. Revision 2 already removed it ("Changes to the parts below", L1: "Remove the drop of a link dragged from a browser", P1t decision 5). The original L1 line was not updated at the time, which was my mistake. It is now struck through in the task doc.
- Keep dragDropEnabled = true and the native file drop unchanged.
- Paste in Add and Ctrl+V on Home are the link entry points.
- In the report, list the link drop as "removed by the designer (revision 2)", not as a failure.
- Add no native URL drop handling and no WebView2 COM code in this cycle. A later cycle may try the HTML5 drop for both links and files, with file paths from WebView2's postMessageWithAdditionalObjects (CoreWebView2File), after a spike.

### Approved oversized refusal fixtures: P1f L2b and G1
The 1080p source limit is about processing, not about refusal tests. The task doc now says so under Constraints ("Test files above 1080p"). The P3 line now reads "The GPU job never uses a source above 1080 or an output above 1440."
Approved run:
- Make a 2-frame 2560x1440 H.264 MP4 with FFmpeg on the CPU, with -movflags +faststart.
- Serve it from the local test server as a direct link.
- Check:
  - it is refused before download with the R2 message;
  - only the header probe reads it;
  - nothing is written to the downloads folder;
  - no job is created.
- Never pass it to a job, restoration, interpolation, output encoding or any GPU processing.
- The test deletes the file afterwards (P6).
The same rule covers the other small synthetic files above 1080p that R5, P3 and P5 already ask for.


## Owner cleanup update after GPU acceptance

Retry deletion of the previously rejected old Electron package as well.
Finish the work with disk usage reduced as much as possible.
