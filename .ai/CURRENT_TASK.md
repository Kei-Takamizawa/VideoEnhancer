# CURRENT_TASK: Cycle P1f-3 (fixes from the owner check)

> **Ready (2026-10-21).** Follow AGENTS.md and CLAUDE.md from PR #8 for the workflow; this file defines only the work.
> **Base branch: PR #8's branch (owner decision 2026-10-21).** See section 1.

- **Task ID:** VE-P1f-3
- **Date:** 2026-10-21
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

## 1. Start

- PRs #5, #6 and #7 were merged into `main` on 2026-10-20. `main` is at `bc7e10e`, with the same tree as `2f12d43`.
- **Branch (owner decision 2026-10-21):** work on PR #8's branch `claude/project-thread-1n4s31`, starting from its current head. Call that head "the start commit" and record its hash in the report.
  - Do not open another PR.
  - PR #8 carries the Windows Codex rules and handoff. It cannot merge into protected `main` while the A7 test is flaky, so PR #8 and this cycle merge together. The owner merges.
  - Git is handled as AGENTS.md and CLAUDE.md on that branch say.
- Replace `.ai/CURRENT_TASK.md` with this file. Write a new `.ai/LAST_REPORT.md` for this cycle.
- Restore the dependencies removed at the end of P1f-2. This restore does not count toward the 1 GB per-cycle growth limit. Report its size on its own line.
- Workspace paths are as in PR #8's handoff (`D:\my-workspace\VideoEnhancer\work`).

## 2. Background: owner check results (2026-10-21)

The owner ran the combined check (P1e-2, P1t, P1f, P1f-2) on the package from `2f12d43`.

- **Passed:** 23 of 34 items, including:
  - start-up under 1 second;
  - the title-bar theme;
  - processing and the queue;
  - History, playback, HEVC playback and seek;
  - Compare and pinch;
  - Remove and Undo;
  - Models and Schedule;
  - link tools install;
  - the Storage legacy message;
  - display scale;
  - quality.
- **Failed:**
  - **Item 6:** a 4K file showed `'charmap' codec can't decode byte 0x90 in position 2200: character maps to <undefined>` instead of the 1080p refusal text. See A1.
  - **Item 8:** the owner's earlier failing file stopped in analysis with `Timestamp/frame count mismatch (5421 packets, 0 decoded frames). Remux the input first.` See A2.
- **Additional report:** the calibration area in Settings shows an error from app start. See A4.
- **Not tested:** items 22-27 (links). The owner says the cause was how the link was passed, not the app. No change for them.
- **Also fixed here:** the designer's review of P1f-2 found one regression in B6. See A3.

For each item:
- first write a test that fails on the start commit and record that failure;
- then fix it and show the same test passing.
- If an item does not reproduce, report the evidence and do not change the code for it.

## 3. Part A: must fix

### A1. Tool output is decoded with the Windows ANSI code page (item 6)

- **Where:** these calls use `text=True` without `encoding`:
  - `media/probe.py:81`, `:122` and `:168`;
  - `media/analyze.py:170`;
  - `media/decode.py:89`;
  - `media/source_index.py:69`;
  - `media/encode.py:324`;
  - `jobs/gpu_memory.py:70`;
  - `logging.py:90` and `:104`;
  - `service/server.py:74`;
  - `bench/runner.py:198`.
  - Python then decodes with the ANSI code page: 1252 on the owner's PC and on GitHub's Windows runners.
- **Why it fails:** ffprobe, FFmpeg and nvidia-smi write UTF-8. Non-ASCII text in a path, file name or metadata tag makes decoding fail or garble. Japanese text often contains the bytes 0x81, 0x8D, 0x8F, 0x90 and 0x9D, which code page 1252 does not define. `service/video_links.py` already decodes yt-dlp output as UTF-8; follow that.
- **Required:**
  1. **Tool output:** decode all external-tool output as UTF-8.
     - Use `errors="replace"` for diagnostics and stderr.
     - Also use it for ffprobe JSON. Never take a file path from tool output.
  2. **File I/O:** audit text reads and writes that use no explicit encoding. This covers `open(`, `read_text` and `write_text`, and logging `FileHandler`s.
     - Make the app's own files UTF-8.
     - Logs must keep non-ASCII paths. Today a `FileHandler` with the ANSI code page cannot encode Japanese text.
     - Report each file type where earlier builds may have written non-ANSI-safe bytes, and how existing files are read safely.
     - Do not switch the whole engine to Python UTF-8 mode in this cycle.
  3. **Guard:** add a lint rule or a test that fails on a new text-mode subprocess call or `open` without an explicit encoding.
- **Tests (Windows CI, code page 1252):**
  - **Fixture:** a synthetic 1080p (or smaller) video at `日本語フォルダ/サンプル「夏」の動画.mp4`, with Japanese `title` and `comment` tags.
  - **Steps:** add, probe, analysis, a short processing run, History row, details, playback URL, Copy details, Remove and Undo.
  - **Refusal:** a tiny CPU-made fixture above 1080p with a Japanese name shows the 1080p refusal text.

### A2. "0 decoded frames" in analysis (item 8)

- **Facts from the code:**
  - `analyze()` counts the frames yielded by `_thumbnails`.
  - With NVDEC chosen, `_thumbnails` uses `SimpleDecoder.get_batch_frames`. If that returns an empty list at once, the result is 0 frames with no exception. Then the generic mismatch error says "Remux the input first", which does not describe a decoder failure.
  - If NVDEC verification had failed, the FFmpeg path would have been used instead.
- **The owner's record** (from Copy details, 2026-10-21):
  - **File:** the name ends in `.f399.mp4`. yt-dlp gives this kind of name to one downloaded format before it merges the formats.
    - On YouTube, format 399 is AV1 video at 1080p, without audio. This is inferred from the name only, so confirm it with ffprobe.
    - The owner confirms it has no audio. It is a different file from the one that failed in P1e-2. Report the actual codec, size and container layout (for example, a fragmented MP4).
  - **Settings:** Standard, AV1 output, output 1440, frame rate 2x.
  - **Error:** "Preparation failed: …".
  - **Placeholders:** during preparation the manifest stored `0` for `display_width`, `display_height`, `frame_count` and `duration`. This is the same placeholder problem P1f-2 A1 fixed for link jobs, here for a local file.
- **Hypothesis (not established):** `SimpleDecoder` with `need_scanned_stream_metadata=True` may not handle this container, while the streaming demuxer that `verify_timestamps` uses does.
- **Required:**
  1. **Reproduce** with the owner's sample (section 8). Find and report the root cause.
  2. **Decoder failure:** when the NVDEC thumbnail pass yields fewer frames than the packet timeline, treat it as an NVDEC failure for this job.
     - Switch the job to FFmpeg decoding, as in P1f L3, and record the reason.
     - Run the thumbnail pass again on the FFmpeg path.
     - The strict count check stays.
     - Say "Remux the input first" only when the FFmpeg path also fails the count.
  3. **Full run:** after the fix, process the owner's sample to the end with the owner's settings: Standard, AV1, 1440, 2x. The output goes under `work\scratch`.
     - Report the dedicated and shared GPU memory peaks: PDH or Task Manager GPU counters, sampled at 1 s.
     - Report the per-part speed against the prediction.
     - This feeds the P1e-3 VRAM cap.
  4. **Placeholders:** store `null`, not `0`, for unknown media values of a local file during preparation, as for link jobs.

### A3. Queue-time space check for links with unknown dimensions (P1f-2 regression)

- **Where:** `service/link_jobs.py` (P1f-2, "space_media").
  - It turns unknown `width` and `height` into `1`.
  - `estimated_output_size` then scales by `target / 1`. That is 1080x or 1440x per side, about 1.17 million x or 2.07 million x in area.
  - So a 50 MB download with output 1080 asks for more than 41 TB, and the job is refused with "not enough space".
- **Required:** when the source width or height is unknown, the queue-time check reserves only the download (twice, as now) plus one margin. The output and working-space check stays in `add_job` after the download, as before P1f-2.
- **Test:** a format with a file size but no width or height, with output 1080 and 1440, on a drive with room for the download: it is accepted at queue time. The post-download check still refuses when the real output does not fit.

### A4. Calibration area shows an error from start-up

- **Owner report:** Settings → Diagnostics (calibration) shows an error from app start.
- **Status:** the exact text is not available. The owner prefers to copy it after B1 makes errors copyable, so the owner will copy it in the next check.
- **What the code can show there:**
  - the last `calibrate` operation, which is persisted and may be a failure from an earlier build;
  - the `driver_note`;
  - the "No speed profile for this GPU" text.
- **Required:**
  - Reproduce with an isolated home in each of these states:
    - fresh;
    - with a failed calibrate operation saved by an earlier build;
    - with a measured profile from another driver.
  - Show only something the user can act on, with Copy.
  - A failed operation from an earlier session must not look like a current error. Show it as "The last calibration on <date> failed: <reason>", with Run again.
  - Report what each state shows before and after. If none of them shows an error at start-up, say so; the owner's copied text decides the rest next cycle.

### A5. "Start with Windows" hides write failures (small)

- **Owner check item 32:** the owner had not turned the setting on. The feature itself works, so there is nothing to investigate.
- **Remaining weakness:** the background loop in `gui/src-tauri/src/main.rs:~343-352` ignores the result of `window::startup(&settings)` (`let _ =`).
- **Required:** when writing the Run value fails, show "Windows didn't accept the startup entry: <reason>" next to the toggle, with Copy, and log it once.
- **Test:** a fake registry only. Never write the real Run key.

### A6. `main` CI is red on Windows: the expired-Undo cleanup of a broken record

- **Failure:** Windows CI run 39538012425 on `bc7e10e` failed only `tests/test_p1f2_review.py::test_a1_unreadable_history_folder_undo_and_cleanup[{torn record-expire]`.
  - `jobs/.removing/<id>` still existed after the 13 s wait.
  - The same tree (`2f12d43`) passed CI twice, so the failure is intermittent. Its cause is not established.
- **Two weak points the designer sees in `_schedule_history_removal` (`service/engine.py:~1774-1800`), not yet proven to be the cause:**
  1. **The timer can fire a little early, and then the removal never happens.**
     - The timer waits on the monotonic clock. `expire()` then compares `history_hidden_until` with `time.time()`.
     - On Windows, the wait is rounded to milliseconds, and the two clocks have different resolutions. So `expire()` can run a hair before `history_hidden_until`.
     - It then returns without rescheduling, and nothing removes the record until the next engine start.
     - The same pattern exists for readable records: the record stays hidden and is never removed.
  2. **One failed delete stops the removal for good.**
     - `shutil.rmtree` runs in the timer thread with no error handling. A file briefly held open by another process makes it fail. On Windows, antivirus scanners and the search indexer do this.
     - The exception is lost, and there is no retry.
- **Required:**
  - Establish the root cause with evidence. For example, run the test at least 200 times on Windows with timing and exception logging, and report the failure count before and after.
  - Fix whatever the evidence shows. At least:
    - an early timer reschedules for the remaining time instead of giving up (both the unreadable and the readable paths);
    - a failed delete is logged, retried a few times with a short backoff, and otherwise left for the start-up cleanup.
  - Never skip, quarantine or loosen the test. Do not only lengthen the wait.
- **Test:** inject an early timer fire and a delete that fails twice and then succeeds. The folder is gone afterwards, and no other file is touched.

### A7. Flaky GUI e2e test `gui/tests/e2e/p1f2-review.spec.ts:68`

- **Failure:** on hosted Windows CI (seen on draft PR #8), the poll `expect.poll(() => app.clipboardText()).toContain("Parse error:")` fails intermittently after Copy details on the unreadable record. The cause is not established.
- **Possible causes (unproven):**
  - the system clipboard is shared and slow on hosted runners;
  - the Copy details click lands before the dialog shows the unreadable-record state;
  - the poll's default 5 s timeout.
- **Required:**
  - Establish the cause with evidence, for example 50 or more repeated runs with timing logs.
  - Fix the cause in the test or the app. One possible fix: read the copied text through the app's own copy path in e2e builds, instead of the shared system clipboard.
  - Never skip or quarantine the test. Do not only lengthen the timeout.
  - B1 changes Copy behaviour, so the fix must cover the new "Copied" flow too.

## 4. Part B: owner requests

### B1. Every error can be copied, with a "Copied" confirmation

- **Copy button:** every error or warning text gets a Copy button (an icon, with the accessible name "Copy message"). It copies the full text, plus details (path, code) when the message has them. This covers:
  - the shared `Notice` component, used in 20 places;
  - inline reasons: Add dialog rows, link cards, History failure reasons, Settings fields;
  - the error boundary.
- **"Copied" popup:** after any copy in the app, show a small "Copied" popup next to the button for 1.5 s, then fade it out (`role="status"`). "Any copy" means Copy details, Copy diagnostics and Copy message.
  - Replace the existing "Diagnostics copied." text with the same popup.
  - If copying fails, show "Couldn't copy: <reason>".

### B2. Errors fade out by themselves (owner decision 2026-10-21: action errors only)

- **Rule:**
  - An error from an action the user took fades out after 8 s, with a 1 s fade. Examples: Save, Install, Remove or Quit failed.
    - It stays while the pointer is over it or it has keyboard focus.
    - × still closes it at once.
  - A notice about a condition that is still true does not fade. Examples: the engine is not running, Smart App Control blocks the app, a deletion guard, an unsupported job.
  - Inline reasons in rows do not fade.
- **Report:** a table classifying each `Notice` use as "action error" or "condition", with file and line.

## 5. Part C: link coverage (owner decision 2026-10-21: keep the current scope)

- The owner asked for every site and video that FetchV, Video DownloadHelper and ReClip handle.
- After the designer's comparison, the owner chose to try the current link feature first:
  - yt-dlp's supported sites plus direct links;
  - still no sign-in, live, DRM, HDR or above-1080p.
- **Do not change the link scope in this cycle.** The owner will report which sites fail. A browser extension or browser sign-in data is a later decision.

## 6. Do not change

- The default pipeline output: G5 strict equality.
- The P1f decoder decisions: strict timestamp check, per-job decoder choice, one retry. A2 extends the choice to the thumbnail pass and does not loosen any check.
- HEVC as the default output; the M1 media path with 1 MiB responses; the MP4 audio rule.
- The Part R limits:
  - sources up to 1080 (short side);
  - outputs Keep, 1080 and 1440.
- The T6 rules; the generic reuse rule from L2.
- The A1 broken-record handling from P1f-2.

## 7. Working rules and constraints (unchanged)

- Never report a test as passed if it did not run. Report every run of a gated measurement.
- **Not test data:** the owner's queue, settings, videos, models, Recycle Bin, `D:\my-workspace\VideoEnhancer\AppData` and `D:\my-workspace\VideoEnhancer\VE-check`. Use a separate engine home for every test. The only exception is the A2 sample in section 8.
- **No system or registry changes** during development. This includes the Run key (A5).
- **Network:**
  - CI uses no third-party site, only local servers with synthetic media.
  - Local real-network tests may use only sources that allow downloading (Wikimedia Commons, Internet Archive).
  - Never download from YouTube, TikTok, Instagram or X in tests.
- **Size limits:** no source above 1080 and no output above 1440 is processed. Small CPU-made fixtures above 1080p are allowed only for refusal, probe and playback tests.
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

## 8. The owner's sample file for A2 (approved by the owner 2026-10-21)

- Before hand-over, the owner copies the failing file into `D:\my-workspace\VideoEnhancer\work\owner-sample\`. That folder is outside the repository.
- Codex uses that copy only:
  - never moves, renames, edits or deletes it;
  - never reads any other file of the owner's.
- **Never in Git:** the file, its name, its path and its metadata.
  - In the report and logs that go to Git, call it "the owner's sample".
  - Keep screenshots of it out of Git.
- Do not count its size toward the cycle's growth. List it under "For the owner to delete" at the end.

## 9. Acceptance

- Every A item (A1-A7), B1 and B2 has a test that failed on the start commit (or evidence that it does not reproduce) and passes now.
- **Python:** `ruff`, `ruff format --check`, `pyright`, the CPU suite, and the local real-tool link bundle.
- **GUI:** lint, typecheck, unit tests, build and e2e.
- **Rust:** fmt, clippy (default and e2e) and unit tests.
- **GPU:** the suite `-m "gpu and not soak"`.
- **P2 cold start:** 5 launches. G1 Home-ready median ≤ 765 ms, first-paint median ≤ 1.0 s.
- **Package:** rebuilt at `work\package\VideoEnhancer`, with an isolated startup smoke and its SHA-256.
- **CI:** Windows and Ubuntu green on the final commit.

## 10. GUI checks (screenshots outside the repository, 1280x800, dark and light)

- The Japanese-named fixture in the Add dialog, Home, History and details.
- An action error with Copy, the "Copied" popup, and the fade.
- A condition notice with Copy.
- The calibration area in the three A4 states.
- The "Start with Windows" failure text (fake registry).

## 11. Report (`.ai/LAST_REPORT.md`)

- A table with every item (A1-A7, B1, B2, P2 gate): done / partial / not reproduced / NOT RUN, with test names and evidence files.
- The failing output on the start commit and the passing output after, for each item.
- **A1:** the list of changed call sites and the file-I/O audit.
- **A2:** the root cause, and the GPU memory and speed numbers.
- **B2:** the `Notice` classification table.
- **Disk:**
  - the dependency restore size;
  - growth for the rest of the cycle;
  - the size of `work\scratch` at the end;
  - free space on C and D.
- "Questions for the designer", each with the default you chose.
- The package path and its SHA-256; exact reproduction steps.
