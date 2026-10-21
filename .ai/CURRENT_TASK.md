# CURRENT_TASK: Cycle P1f-2 (fixes from the P1f review)

- **Task ID:** VE-P1f-2
- **Date:** 2026-10-19
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- Continue on branch `p1f-links` from `05dbf72` (the P1f final commit). Keep draft PR #7 (base `p1t-tauri`). Do not open a new PR.
- Replace `.ai/CURRENT_TASK.md` with this file. Write a new `.ai/LAST_REPORT.md` for this cycle. The P1f report stays in Git history at `05dbf72`.
- **Restore the dependencies removed at the end of P1f** (Python environment and uv cache as needed, `npm ci` in `gui`, the Cargo registry, and the Rust target through a normal build).
  - This restore does not count toward the 1 GB per-cycle growth limit in `docs/WORKSPACE.md`. Report its size on its own line.
  - Every other workspace rule still applies.

## 2. Background

- P1f finished as PARTIAL at `05dbf72`. P2 cold start failed; everything else passed. Windows and Ubuntu CI passed.
- The designer reviewed the P1f code by reading it, without running it. The review found the defects in Parts A and B below. Each one names its file and line at `05dbf72`.
- For each item:
  - first write a test that fails on `05dbf72` and record that failure;
  - then fix it and show the same test passing.
  - If a test shows that an item does not reproduce, report that with the evidence and do not change the code for it.
- After this cycle, the owner checks P1e-2, P1t, P1f and P1f-2 together, then merges.

## 3. Designer decision on P2 (2026-10-19)

- **The P2 cold-start failure is accepted as a known issue.** P1f measured a G1 Home-ready median of 694.6 ms for Tauri, against 420.9 ms for Electron. Most of the gap is WebView2 start-up: the median window-to-navigation interval is 297.6 ms for Tauri and 16.8 ms for Electron.
- Electron is removed, so the gate relative to Electron is retired. The P1f FAIL stays in the record.
- **New gate, from this cycle on:** measure on the same G1 fixture (5 launches). The G1 Home-ready median must be at most 765 ms (694.6 ms + 10%), and the first-paint median at most 1.0 s.
- In this cycle, run that measurement once at the end.

## 4. Part A: must fix

### A1. A link job without known size or frame rate breaks Home and History

- **Where:**
  - `service/link_jobs.py:78-87` stores `width`, `display_width`, `height` and `display_height` as `0`, and `cfr_fps` as `"0"`, when the metadata has no size or no frame rate. Internet Archive formats from yt-dlp have no frame rate. Many HLS formats have none either.
  - After the download, the job enters `preparing` with these values (`link_jobs.py:241-254`). `add_job` replaces the media only later.
  - The queue snapshot calls `estimate_job` (`service/engine.py:720-724`) and `job_progress` (`engine.py:758`). Both reach `estimate/model.py` `_geometry`, which raises "Media dimensions must be positive." or "Media frame rate must be positive."
  - The snapshot has no per-row guard, so `GET /queue` fails and Home and History stop updating.
  - If the job then fails, the failed row breaks every later snapshot until someone removes the manifest by hand. Ways the job can fail here:
    - the download fails after its retries;
    - R2 or HDR refuses it after the download;
    - its preparation is interrupted.
- **Required:**
  1. Never store `0` or `"0"` for an unknown size, frame rate, duration or frame count. Store `null`.
  2. Show a link job that has no analysed media with the link-style row, like the downloading row at `engine.py:~625-655`. Do not call `estimate_job` or `job_progress` for it. This covers the downloading, preparing, failed and cancelled states before analysis.
     - Its estimate comes from `link_estimate`, or reads "after download".
  3. **One bad record must never break the whole snapshot.** If building one row fails:
     - log it once;
     - show that job with "This job's record can't be shown: <reason>" and a Remove action;
     - keep all the other rows.
  4. Read the placeholders written by P1f builds (`0` and `"0"`) as unknown, so existing manifests load safely.
- **Tests:**
  - a format without a frame rate whose download fails after all retries: `GET /queue` and History still work, and the row shows the failure and Retry;
  - the same with no size (the L2b fallback);
  - the same with a 1440p file refused by R2 after the download;
  - a snapshot taken during the preparing window;
  - a manifest from a P1f build with `0`/`"0"` placeholders.

### A2. A download with missing fragments counts as finished

- **Where:** `service/video_links.py:632-657` passes `--fragment-retries 0` without `--abort-on-unavailable-fragments`.
  - yt-dlp's default skips fragments it cannot fetch and still exits with 0.
  - So an HLS or DASH download with one failed middle segment is renamed and processed with a gap.
- **Required:**
  - Add `--abort-on-unavailable-fragments`, so the app's own retry (the first attempt plus 3 retries) handles the failure. Keep resume working.
  - **Check the duration after the download.** When the metadata duration is known and the file is shorter by more than max(1 s, 1%), fail with "The download is incomplete (N s of M s). Retry the download." Keep the file.
- **Tests:** the local HLS server returns HTTP 500 for one middle segment:
  - once: the retry succeeds and the file is complete;
  - always: the job fails with the reason, after its retries.

### A3. A partial remux can be accepted when a download resumes

- **Where:** `service/video_links.py:639-671`.
  - For a single stream that is not MKV (for example a direct MP4), yt-dlp's remuxer writes straight into `.ve-<id>.mkv`. In yt-dlp 2026.08.19, `FFmpegVideoConvertorPP.run` uses no temporary file, while the merger does.
  - Pause all, Quit or a crash during that remux leaves a partial `.mkv`.
  - On the next attempt, `--no-overwrites` can treat that partial file as already downloaded. It is then renamed and processed.
- **Required:** before each attempt, remove a leftover `.ve-<job id>.mkv` unless the job has recorded a completed download for it. Alternatively, remux to a temporary name yourself and rename it.
  - These are the app's own temporary files in the download folder, so removing them is allowed. Match the exact name pattern with the job id, and never touch any other file.
- **Test:** stop the process during the remux, resume, and confirm the final file is complete (its frame count equals the source's).

## 5. Part B: should fix

### B1. Every playlist entry reads the whole playlist again

- **Where:** `video_links.py:507-513` re-checks `source["request_url"]`, which `link_jobs.py:91` sets to the playlist link. So every entry's download, and every retry, runs `-J` on the whole playlist, with up to 200 entries and their header probes. That can exceed the timeout and can trigger a site's rate limit.
- **Required:** re-check with the entry's own link (`source.url`, from `webpage_url`) and `--no-playlist`, still matching `extractor_key` and `id`. If an entry has no link of its own, keep today's behaviour for it.
- **Test:** a local 3-entry playlist. Each entry's download runs exactly one single-video check. Count the yt-dlp runs.

### B2. A list of lists makes the check fail

- **Where:** a channel's home page and its "Playlists" tab return entries with `_type: playlist`, which have no `formats` and no `url`.
  - `video_links.py:213` reads `item["url"]` outside the `try` that starts at line 214.
  - `check()` catches only `ValueError` (line 752).
  - So the operation fails with the bare text `'url'`.
- **Required:**
  - Refuse such a link with: "This link is a list of lists. Paste the link of one list, for example a channel's Videos tab."
  - Any entry without a usable URL gets a plain reason on its own card. It must not fail the whole check.
- **Test:** a local fixture with nested playlists.

### B3. The header probe gives the wrong "not encrypted" refusal

- **Where:** `video_links.py:255-260` tests `"http" in str(error)`. This is always true for a whitelist error, because FFmpeg's message includes the whitelist `'https,tls,tcp'`. So these are refused with the T6 message instead of falling back as L2b says:
  - an AES-128 HLS link ("Protocol 'crypto' not on whitelist");
  - a link opened through a proxy.
- **Required:**
  - Give the T6 refusal only when the error matches `Protocol 'http' not on whitelist` (case-insensitive). Every other probe failure uses the L2b fallback.
  - You may add `crypto` to the whitelist for `https` links. It does not allow plain transport. Never add `http` for an `https` link.
- **Tests:**
  - AES-128 HLS over local TLS: the probe succeeds or falls back, and never shows the T6 message;
  - an `https` link that redirects to `http`: still refused.

### B4. DASH fragments over http are not checked

- **Where:** `check()` (around line 745) never checks `fragments`. `download()` (lines 564-567) only checks that each fragment's scheme is `http` or `https`.
- **Required:** for an `https` link, refuse a format when any fragment URL is `http`, with the T6 message. Resolve each fragment as `urljoin(fragment_base_url or url, fragment path)`. Apply the same check in `check()`, in `links/queue` and again in `download()`.
- **Test:** a local MPD with absolute `http://` `SegmentURL` values.

### B5. The storage lock blocks the whole app

- **Where:**
  - `gui/src-tauri/src/storage.rs:204` (`refresh`, which runs when the Storage card opens) and `storage.rs:298` (`remove_old`, including its confirmation dialog) hold `storage_busy`.
  - `State::connected` (`main.rs:53-58`) refuses every command while that flag is set. The media protocol returns 502 (`media.rs:137`), and tray Quit fails (`window.rs:274`). Pause, zoom, hide and `sourceLink` fail too.
- **Required:**
  - Use a separate lock to keep Move, Remove and refresh from overlapping.
  - `connected()` refuses only during the Move phase that stops the engine.
- **Test:** run Remove on a large synthetic old folder, and open the Storage card. While each runs, a video plays and tray Quit works.

### B6. The free-space check before a download

- **Where:** `link_jobs.py:73-76` checks only the download folder. L4 says the free-space check (P1e B2) includes the download size. Today the output and working-space check runs first in `add_job`, after the download.
- **Required:**
  - At queue time, run the same working and output space check that `add_job` runs. Add the download size when the download folder is on the same drive.
  - Apply one margin once. Today the margins multiply: 2.2 × 2 copies × 1.1, about 4.84× (`link_jobs.py:76`, `video_links.py:531` and `617`).
- **Test:** a drive with room for the download but not for the output is refused at queue time, with the existing message.

### B7. External programs started on every refresh

- **Where:**
  - `engine.py:315-331` calls `load_machine_profile` for each downloading job in every forecast. With the `cuda` backend, that calls `environment_info` (`logging.py:75`), which starts external programs each time.
  - The same happens per format in `check()` (`video_links.py:318`) and in `links/estimate` with `all_formats`.
  - `gui/src/LinkPanel.tsx:70-80` asks again for every entry's estimates whenever any quality changes.
- **Required:**
  - Load the machine profile once per engine start, and again only when the GPU, driver or installed models change. Pass it in.
  - The GUI asks only for the entry whose quality changed.
- **Report:** external process starts per minute with 20 queued downloads, before and after.

### B8. The yt-dlp cache is written to drive C

- **Where:** `video_links.py:341-350` runs yt-dlp without `--cache-dir`. yt-dlp therefore writes to `%USERPROFILE%\.cache\yt-dlp` on drive C, and Uninstall leaves it there. The owner moved all app data off drive C because it is full.
- **Required:**
  - Pass `--cache-dir <engine home>/tools/yt-dlp/cache` on every yt-dlp run.
  - Uninstall removes that folder.
- **Test:** no file appears under the user profile's `.cache\yt-dlp` during the real-tool bundle.

### B9. Reuse is off by default

- **Where:** `LinkPanel.tsx:39` and `104`. The reuse checkbox starts unchecked, so the default is to download again. L2 says to offer the earlier file instead of downloading again.
- **Required:**
  - When an offer exists, select it by default. "Download again" switches to downloading.
  - Keep the label "Use the file downloaded on <date> (<width>x<height>, <fps> fps)".
- **Test:** a GUI unit test.

### B10. YouTube chunk size is dropped

- **Where:** `video_links.py:532-553`. `safe_keys` drops `downloader_options`, so yt-dlp's `http_chunk_size` is lost. yt-dlp sets it because YouTube slows down large chunks.
- **Required:** keep `downloader_options.http_chunk_size` in the info file, and accept only a positive integer.
- **Test:** a unit test on the info file. Do not test against YouTube.

### B11. Analysis decodes every NVDEC video twice

- **Where:** in `media/analyze.py`, `verify_timestamps` (lines 112-122) decodes the whole file with NVDEC. Then `_thumbnails` (lines 130-132) decodes it again with `SimpleDecoder`.
- **Required:**
  - If the change stays inside `analyze.py`, make the thumbnails from the frames `verify_timestamps` already decodes.
  - Otherwise, measure the extra time on a 10-minute 1080p30 synthetic file and report it.
  - Scene cuts, analysis output and the pipeline output must not change (G5 strict equality).

### B12. HEVC playback with the owner's extension (missed in P1f)

- The task copy Codex received for P1f did not include this check.
- The owner installed HEVC Video Extensions on 2026-10-18. Run the A3a HEVC check once in the packaged app:
  - synthetic 1080 and 1440 files;
  - the exact codec strings and `canPlayType`;
  - real playback and seeking.
- Change no code unless playback fails. If it fails, report it under "Questions for the designer".

### B13. Link thumbnails can be fetched from the local network

- **Where:** `video_links.py:455-472` and `service/server.py:240-249`. The engine fetches any thumbnail URL from the metadata, including loopback, private and link-local addresses.
- **Required:**
  - Fetch only `https`, or `http` when the link itself is `http`.
  - Resolve the host and refuse loopback, private, link-local, multicast and unspecified addresses.
  - Follow no redirect to such an address.
  - A refused thumbnail just shows no image.
- **Tests:** a loopback thumbnail URL, a private-address thumbnail URL, and a redirect to loopback.

### B14. Cancelling a download leaves large partial files

- **Where:** `engine.py:1447-1448`. Cancel, and Remove of a failed download, delete only the job folder. The `.ve-<job id>.*` and `.part` files stay in the user's download folder, possibly several GB.
- **Required:**
  - On Cancel, and on Remove of a job that never finished downloading, delete that job's own temporary files in the download folder.
  - Match the exact name pattern with the job id. Never touch any other file, and never touch a finished, renamed download.
- **Test:** cancel during a download. The temporary files are gone, and an unrelated file in the same folder is untouched.

## 6. Not in this cycle

The designer keeps these for P1e-3. Do not change them now:
- **Decoder:**
  - the out-of-memory fallback after the decoder retry;
  - re-analysis keeping a runtime FFmpeg choice;
  - `p016le` for 12-bit sources.
- **Storage:**
  - Remove offered when nothing can be deleted;
  - the "earlier version" message on a pointer this app recovered;
  - the raw JSON in the result text;
  - a disconnected drive clearing the pointer;
  - the status line during Remove;
  - a second Move overwriting `previous`;
  - hashing twice in Remove.
- **Links:**
  - the downloaded tool's bytes being read again before install;
  - the install/uninstall guard while checks or downloads run;
  - one audio choice disabling every video format;
  - Retry after a crash between the rename and the record, and collisions that differ only in letter case;
  - Quit refused while a downloaded video is being analysed;
  - odd-width reuse mismatches.

## 7. Do not change

- The default pipeline output: G5 strict equality.
- The P1f decoder decisions: the strict timestamp check, the per-job decoder choice and the single retry.
- HEVC as the default output.
- The M1 media path with 1 MiB responses.
- The MP4 audio rule.
- The Part R limits.
- The T6 rules, except the tightening in B3 and B4.
- The generic reuse rule from L2.

## 8. Working rules and constraints (unchanged from P1f)

- Never report a test as passed if it did not run. Report every run of a gated measurement.
- **Not test data:** the owner's queue, settings, videos, models, Recycle Bin, `D:\my-workspace\VideoEnhancer\AppData` and `D:\my-workspace\VideoEnhancer\VE-check`. Use a separate engine home for every test.
- **Network:**
  - CI uses no third-party site at all, only local servers with synthetic media.
  - Local real-network tests may use only sources that allow downloading (Wikimedia Commons, Internet Archive).
  - Never download from YouTube, TikTok, Instagram or X in tests.
- **Size limits:**
  - No source above 1080 and no output above 1440 is processed.
  - Small CPU-made fixtures above 1080p are allowed only for refusal, probe and playback tests, as P1f section 5 says.
- **Cleanup:**
  - Tests remove their own files under `work\scratch`. Report the size of `work\scratch` at the end.
  - Do not use a separate delete command to get around a refused delete. List what is left under "For the owner to delete".
- **Never commit:**
  - media, weights, downloaded tools or packages;
  - `node_modules` or build output;
  - screenshots;
  - `local-env.ps1`;
  - the owner's logs, links, paths or names.
- No telemetry and no automatic update checks.
- All code, comments, UI text and docs are in English. Update `docs/GUI.md`, `docs/API.md` and `docs/TROUBLESHOOTING.md` where behaviour changes.

## 9. Acceptance

- Every A and B item has a test that failed on `05dbf72` (or evidence that it does not reproduce) and passes now.
- **Python:** `ruff`, `ruff format --check`, `pyright`, the CPU suite, and the local real-tool link bundle.
- **GUI:** lint, typecheck, unit tests, build and e2e.
- **Rust:** fmt, clippy (default and e2e) and unit tests.
- **GPU:** the suite `-m "gpu and not soak"`.
- **P2 cold start:** 5 launches against the new gate in section 3.
- **Package:** rebuilt at `work\package\VideoEnhancer`, with an isolated startup smoke and its SHA-256.
- **CI:** Windows and Ubuntu green on the final commit.

## 10. GUI checks (screenshots outside the repository, 1280x800, dark and light)

- Home and History keep updating with a failed link job that had no frame rate.
- The record-error row from A1 (use a synthetic damaged manifest).
- The reuse offer, selected by default.
- The list-of-lists refusal.
- A video playing while the Storage card is open.

## 11. Report (`.ai/LAST_REPORT.md`)

- A table with every item (P2 gate, A1-A3, B1-B14): done / partial / not reproduced / NOT RUN, with test names and evidence files.
- The failing output on `05dbf72` and the passing output after, for each item.
- **Numbers:** B7 process starts, B11 analysis time, the B12 HEVC result, and the P2 cold-start medians.
- **Disk:**
  - the dependency restore size;
  - growth for the rest of the cycle;
  - the size of `work\scratch` at the end;
  - free space on C and D.
- "Questions for the designer", each with the default you chose.
- The package path and its SHA-256.
- Exact reproduction steps.


Designer decision (2026-10-19), P1f-2 A1. Added to the task doc as A1 item 5.
Keep the same Remove with the 10-second Undo for every broken record, including one whose JSON does not parse.
- Valid JSON with bad values: use the existing History removal and Undo.
- JSON that does not parse:
  - Remove moves the whole job folder aside, inside the engine home (for example jobs/.removing/<id>). Undo moves it back unchanged.
  - After the Undo window, delete the moved folder. At engine start, delete any folder left in that place.
- Never repair, rewrite or partly read the broken file.
- Do not offer the video options (moving the finished video or the original to the Recycle Bin) for a record that can't be read, because the app can't tell which files belong to it. Show instead: "This record can't be read, so its videos stay where they are."
- Copy details shows the parse error and the record's path.
- Tests:
  - Remove, then Undo, restores the folder byte for byte;
  - Remove without Undo removes only that job folder;
  - no file outside the job folder is touched.
