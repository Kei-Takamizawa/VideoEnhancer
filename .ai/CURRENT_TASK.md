# CURRENT_TASK: Cycle P1e-2 (finish P1e: live finish time, finalization, 2160 output, streaming player)

- **Task ID:** VE-P1e-2
- **Date:** 2026-10-13 (section 10 added 2026-10-14)
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:**
- Continue on branch `p1d-ui-v2` (draft PR #5, head `ad6b1f7`). If `origin/main` has moved, merge it in with a merge commit.
- Save this file as `.ai/CURRENT_TASK.md` and commit it. At the end, write `.ai/LAST_REPORT.md` (English, UTF-8 written once, ASCII punctuation, under 60 KB), and update it after the final CI run.
- Do not push to `main`.
- Section 10 ("Owner feedback", added 2026-10-14) is part of this cycle. Its order is in working rule 2.

## Working rules

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option, and continue.
2. Order: Part E (live finish time, with O8) → O1 (removal freeze) → O2 (unreadable video blanks the window) → O3 (YouTube files) → Part F (finalization) → Part R (2160 output) → Part P (player) → O4 to O7 (install progress, Compare, History, other screens) → Part L (small fixes) → Part Q (re-measure) → O9 (speed measurements) → Part G.
3. Never report a test as passed if it did not run. Report every run of a gated measurement.
4. The owner's queue, settings, videos and Recycle Bin are not test data. Use a separate engine home for every test, and keep benchmark outputs inside it. P1e left a stray file outside the isolated home.

## 0. Status after P1e (review of `ad6b1f7`)

- **Accepted as done:** Parts B, Q, V, H, M, C, S and O. CI is 4 of 4 green.
- **Accepted results:**
  - Theme switch: medians of 27–39 ms.
  - Warm screens: at most 71.5 ms. Cold History: 137.9 ms.
  - The 4K files behave as specified.
  - Native B1: the output and original are both recycled and restored with identical SHA-256 values.
  - The decoder and manifest costs no longer grow with file length (decoder open at 120 min: 1.45 s → 0.012 s; manifest: 18.4 MB → 2 KB).
- **Part E is PARTIAL.**
  - The first estimate (−2.7%) and the first finish time (−2.7%) passed.
  - The live finish time at 50% was 662 s early (−17.28%, gate ±5%). The corrected code was not run again.

Designer answers to your questions:
1. **Live finish time.** Your diagnosis is right, but the review found two more faults. Part E fixes them, then reruns the full gate.
2. **Install on every Models card.** The owner explicitly asked for a large Install button. Keep it. "One primary per screen" applies to page-level actions, and a repeated card action may use the primary style.
3. **History player.** Fetching the whole file is not acceptable for multi-GB outputs: there is also a 30 s GET timeout. Part P switches to streaming.
4. **2160 output.** The owner's only long job had 2160 output and took 1.96x its reconstructed estimate. Every calibration point is at 1080 output. Part R measures 2160.
5. **Physical touchpad, Windows scaling and real clicks.** The owner checks these with `P1e_owner_check.md`.

## 1. Part E: live finish time

**Findings from the review:**
- **The progress packet drops fields.** The `_progress` whitelist (`engine.py:222-238`) omits `correction_factor`, `position`, `created_at` and `analysis_seconds`, and `progress_message` plans from that reduced dict. So in the GUI's live finish time:
  - pending parts use correction 1.0;
  - the running job sorts after queued jobs (default position 10**9, `planner.py:24`).

  The `queue()` snapshot plan uses full manifests and is not affected.
- **The live rate is noisy.** It is the change between two consecutive progress updates (`engine.py:213-218`), a window of about 4 s with a 2 s heartbeat.
- **Start-up is undercounted.** Per-part overhead in the estimate is about 4.0 s, but the measured start-up is about 5.5 s: parent + IPC about 2.3 s, child entry 1.4 s, model loads about 1.8 s.
  - Parent + IPC is not a named term.
  - Local learning replaces the 2.0 s constant with child + decoder start-up only (`local.py:94-100`), which makes the term smaller, not larger.

**Do:**
1. Plan the live finish time from the same full job data as the snapshot plan. Add a test that the packet path and the snapshot path give the same finish time within 1 s, for a multi-job queue.
2. For the active part, use the cumulative rate since the part started (frames done / elapsed). Until 20% of the part, or 15 s, has passed, blend it with the part's prediction.
3. Make the full measured per-part start-up a named term: parent + IPC, child entry, decoder open and model loads. Learn it locally as the median of recent parts.
4. Rerun the P1e gate job: the same 10-minute portrait Standard C1, 1080x1920/60 HEVC, isolated home, test hours with a 15-minute gap.
   - **Gate:** the first estimate within ±10%, the first finish time within ±10%, and the live finish time at 50% within ±5%.
   - Also report the live finish time at 25% and 75% (no gate).
   - **Place the gap in the second half of the job**, so the live finish time must count a future gap.

## 2. Part F: finalization

**Findings from the review:**
- The built-in finalization coefficients are a linear fit on 8 tiny clips: at most 28 MB and 900 frames, no audio, no quality aggregation.
- For the gate job they predicted 4.2 s; the actual was 19.1 s.
- For the P1e passthrough measurements the model gives about 5.5 s at 30 min (measured 10–13 s) and about 21 s at 120 min (measured 78–102 s).
- Admission reserves only the predicted time (`admission.py:16`), and finalization is aborted at the end of the window (`controller.py:641-655`). It then restarts from the beginning in the next window, which can push the finish time back by hours.

**Do:**
1. Report the per-step finalization times of the gate job (concat, mux, faststart, validation, quality aggregation), so the dominant step is known.
2. Measure finalization on realistic synthetic outputs: 1, 30 and 120 minutes, with the real part count for Standard, audio and quality aggregation. **Do not use the 10-minute gate job.**
   - Replace the built-in finalization model with one fitted to these points. It may be non-linear.
   - Keep local learning, but by output length, not as one scalar for every length.
3. **Admission:** start finalization only if `1.5 × prediction + 60 s` fits before the end of the window.
   - If an abort is still needed, keep the finished steps (for example the joined file) so the next window resumes, unless that is unsafe. Then say why.
4. **Gate:** the gate job's finalization prediction is within ±25% of the actual.

## 3. Part R: 2160 output

**Findings from the review:**
- All calibration data is 720x1280 → 1080x1920.
- Colour, encode, resize and RIFE are scaled linearly with output pixels, with no measured point above 1080.
- The size-model delta is applied unscaled to every output size.
- The correction is keyed by preset only, not by output size.

**Do:**
1. Measure the reference pipeline at 2160x3840 output (from the 5 s 720x1280 reference clip) for Standard and Fast, as part of calibration. Add these points to the built-in RTX 4060 Ti profile.
   - Report RIFE's peak memory at 2160, and any out-of-memory retries.
2. **Estimates:**
   - Between measured output sizes, interpolate each stage.
   - Above the largest measured size, mark the estimate "uncalibrated" with ±25%. Never extrapolate silently.
   - Key the local correction by preset and output size class (≤1080, ≤1440, ≤2160).
3. **Gate:** a fresh home with the built-in profile runs a 30 s portrait Standard C1 job with 2160x3840/60 output. Its first estimate is within ±15% of the actual.

## 4. Part P: streaming player

**Findings from the review:**
- `HistoryDetail.tsx:20-21` fetches the whole file into a Blob before playback.
- GET requests time out after 30 s (`api.ts:19-21`).
- The media endpoint (`server.py:177-195`) has no HTTP Range support.

**Do:**
1. **Service:** the media endpoint serves only recorded job files and supports `Range` (206 Partial Content).
2. **Electron:** the main process streams media through the existing `app://` protocol (or a new privileged scheme). It adds the token header and passes `Range` through.
   - The renderer gets a plain media URL, never the token. Update the CSP `media-src` to match.
   - No whole-file fetch, and no timeout on media streams.
3. **Gate,** with a synthetic 4 GB output in an isolated home:
   - playback starts within 1 s;
   - a seek to 90% shows a frame within 1 s;
   - the renderer's memory grows by at most 200 MB.

## 5. Part L: small fixes from the review

1. **Records hidden for good.** `pause-undo` sets `history_hidden_until` about 10 years ahead (`engine.py:1249`). If the app quits while the toast is paused, the record stays hidden for good.
   - At the next start, finish that removal (purge the record). The user did not choose Undo.
   - Files are not touched.
2. **A missing `analysis.json`** must not make a manifest unloadable.
   - A queued job runs analysis again.
   - A finished job shows its details without the per-frame data.
3. **`record_completed`** catches only `OSError` (`local.py`). Any exception must be logged and must not skip the segment and original-deletion cleanup that follows.

## 6. Part Q: re-measure what P1e changed

P1e changed the event stream and the GUI. Run again, with the same methods and gates as P1d-3:
- real-engine progress cadence on the GPU;
- service CPU with 1,000 diagnostic-rich records (gate ≤5%);
- 5,000 records (report).

## 7. Part G: acceptance

- **G1:** screenshots of anything this cycle changes (Settings calibration with 2160 points, if shown), at both sizes and in both themes. Store them outside the repository and list their paths.
- **G2:** CI tests:
  - the packet path equals the snapshot path;
  - the cumulative active-part rate;
  - Range requests (206, bounds, out-of-range 416, refused for non-job paths);
  - the purge of paused-undo records at start-up;
  - a missing sidecar.
- **G3: GPU and real PC:**
  - the Part E gate job;
  - the Part F measurements and gate;
  - the Part R measurements and gate;
  - the Part P gate;
  - Part Q.
- **G4:** all GPU-marked tests. The default pipeline output must not change; strict equality as before.
- **G5:**
  - `ruff`, `ruff format --check`, `pyright`, CPU tests and D2;
  - GUI lint, typecheck, unit tests, build, e2e and package;
  - Windows and Ubuntu CI green on the final commit.
- **Package:** build it and give its path.

## 8. Constraints

Same as P1e:
- English for code, comments, UI text and docs.
- **Never commit:**
  - media, weights, previews or generated videos;
  - `node_modules` or build output;
  - screenshots;
  - the owner's logs or private names.
- **User videos** are never deleted permanently. Recycle Bin only, behind the guard. Never change the owner's Recycle Bin settings.
- No new catalog entries. No telemetry, no auto-update. Keep the localhost token model: the token must never reach the renderer through a media URL.
- New dependencies: open-source licences only, named in the report.
- Update `docs/GUI.md`, `docs/API.md` and `docs/TROUBLESHOOTING.md`.

## 9. Report (`.ai/LAST_REPORT.md`)

- A table per part (E, F, R, P, L, Q, Owner feedback, G): done / partial / NOT RUN / BLOCKED, with evidence.
- The Part E gate numbers at 25%, 50% and 75%.
- The finalization step table.
- The 2160 measurements and memory peaks.
- The package path.
- "Questions for the designer", each with the default you chose.

Never report a test as passed if it did not run.

## 10. Owner feedback (owner check of `ad6b1f7`, 2026-10-14)

The owner ran `P1e_owner_check.md` on the P1e package. Items 1 to 5, 7 to 10, 14, 17 and 19 passed. The fixes and requests are below.
- The findings come from reading `ad6b1f7`, and line numbers refer to that commit.
- "Confirmed" means read in the code. "Inferred" means not reproduced.

### O1. Removing with files freezes the app (items 12 and 13). Do this first after Part E.

**What the owner saw:**
- **Bulk remove.** In Select mode the owner picked two cards and chose **Remove from history**, with "Also move the finished videos to the Recycle Bin" ticked.
  - The request timed out and the UI froze.
  - After a restart both records were still there, and only one of the two outputs was in the Recycle Bin.
- **Clear history** with the file options on removed nothing and timed out. Without the file options it works.

**Cause (confirmed): a lock-order deadlock.**
- `dispatch` runs the POST under `Engine.lock` (`engine.py:1778`). `history_action` takes it again (`1221`).
- After each file, `history_action` calls `refresh_terminal_files` (`1279`), which takes `_event_lock` (`660`).
- About once a second, the event-stream thread calls `event_message`. It takes `_event_lock` (`746`) and then `Engine.lock` (`703`).
- So the first file is recycled, and then the two threads wait for each other forever. As a result:
  - The record is never saved or hidden, and the second file is never tried.
  - The event stream stops, so the GUI shows "Reconnecting" and disables its controls.
  - Every later POST waits on `Engine.lock`.
  - GET `health` still answers, so Electron never restarts the service.
- Single-record **Delete video files…** works only because `history/delete-files` does not take `Engine.lock` (`1770-1776`).
- No test drives this path over HTTP with a live event stream.

**Do:**
1. **Locks.**
   - Define one lock order for the whole service and document it.
   - Never do file I/O, a shell call or `deletion.delete` while holding `Engine.lock` or `_event_lock`.
   - Add a test-mode lock-order check (or an equivalent) that fails tests on an inversion.
2. **Event stream.** It never waits on a mutation.
   - Snapshots read data that a mutation publishes when it finishes, or take a short copy under a lock that is never held across I/O.
   - Heartbeats keep flowing during any operation.
3. **Background operation.** Removing or clearing with files runs in the background.
   - The POST returns at once with an operation id.
   - The dialog shows per-file progress ("Moving 2 of 5 to the Recycle Bin…") and then the result.
   - No 30 s client timeout applies.
4. **Commit per record.**
   - Save each file's outcome as soon as it is known.
   - Hide each record once its own files are settled.
   - Always return and stream which records were hidden, so Undo appears.
   - If a file is kept (the guard refused, or the file is in use), its record stays visible with ⚠︎ and the reason.
5. **Start-up.** Copy finished journal outcomes back into their records: a file that is already in the Recycle Bin shows as "In the Recycle Bin", not "missing". Never restore a file that the Recycle Bin already holds.
6. **Watchdog.** While a lock has been held for more than 5 s, log a warning with the holder's stack, without waiting for the lock to be released.
7. **Electron.** A service whose health check answers but whose event stream has sent nothing for 30 s counts as unhealthy. Show "The engine stopped responding" with **Restart**, instead of "Reconnecting" forever.
8. **The owner's two records.** After the update, the two records left by item 12 behave correctly and can be removed normally:
   - The recycled output shows as "In the Recycle Bin".
   - If the journal has no entry for it, it shows as missing.

**Tests:**
- **Remove at the HTTP level, with a live event-stream client.** Use three records, each with an output and an original, and a fake recycle that takes 2 s per file. Check that:
  - the operation finishes;
  - events keep arriving at least once every 2 s throughout;
  - the records are hidden;
  - Undo brings them back.
- **Clear with files:** the same test for all records.
- **Lock-order regression:** the inversion above fails the test.
- **Windows opt-in test with the real shell file operation.** Use files that the test creates in an NTFS folder inside the isolated home.
  - Recycle three files one after another in one process, then three in one bulk operation.
  - Check each item in the Recycle Bin through the guard identity, then restore it.
  - Touch only the items this test created.

### O2. A file the engine cannot read blanks the whole window (item 6)

The owner dropped a 4K SDR video (not HDR), and the whole UI disappeared.

**Cause (confirmed):**
- When one file's estimate fails, the engine returns `{"error": …}` with no `media` (`engine.py:958-959`).
- The Add dialog checks only that the preview exists, then reads `previews[items[0]].media.cfr_fps` (`Queue.tsx:146-149`). That throws during render.
- There is no error boundary (`main.tsx:4`), so React unmounts the whole app.
- Any first file whose estimate fails does this, not only 4K.
- **Which error the owner's file raised is not known.** The most likely one is "Unsupported SDR color matrix bt2020nc" (`probe.py:160-163`), from a 4K SDR file tagged BT.2020 (inferred).

**Do:**
1. **Error boundaries.**
   - Add one at the app root. It shows "Something went wrong on this screen" with **Reload** and **Copy details**, and never leaves a blank window.
   - Add one for each screen and each dialog.
   - Log the error and the component stack.
2. **Per-file errors.** In the Add dialog, each file's preview holds either media or an error.
   - A file with an error shows the reason on its own row, with **Remove it**.
   - The other files can still be added.
   - The summary line uses the first file that has media.
3. **SDR tagged BT.2020 is accepted.** This covers matrix `bt2020nc` with transfer `bt709`, `bt2020-10` or `bt2020-12`.
   - Decode with the BT.2020 matrix and process the video.
   - Tag the output with the source's primaries, matrix and transfer. Do no gamut conversion.
   - HDR stays blocked with today's message until the HDR cycle.
4. **Replace the size warning.** "The chosen size is smaller than the source…" (`engine.py:1006-1013`) is wrong, because the output is never shrunk (`timing.py:24-26`). Show this as information instead: "This video is larger than 1080p, so the output keeps its size (2160p)."
5. **Disk space.** When the source is larger than the chosen size, base the estimate on the real output size. Today `store.py:119-129` assumes a downscale, which makes the estimate about 4x too small for 4K.
6. **Measure 4K Standard on 8 GB, then guard it.**
   - On the GPU, in an isolated home, run 10 s synthetic Standard jobs at 3840x2160/30 and 2160x3840/30.
   - Report the fps, peak VRAM, out-of-memory retries, and whether RIFE fell back to blending.
   - If Standard cannot finish at a size, the Add dialog says so before the file is added: "Standard can't run at this size on this GPU yet. Fast works." It also offers Fast. A job must never fail hours later for this reason.
   - The real fix (for example tiled restoration) is planned for P1e-3. Report the numbers it needs.
7. **The blending fallback is reported.** RIFE's fallback to blending (`models/stages.py:130-132`) must not happen silently.
   - Record it for each part.
   - Show ⚠︎ on the record with "Frame doubling used a simpler method for N parts".
   - List it in the job details.

**Tests:**
- GUI: the first file's estimate fails. The dialog stays open, the row shows the reason, and the other files can still be added.
- An error-boundary test.
- Probe tests for SDR BT.2020.
- A synthetic 4K SDR estimate test in which every estimate field is a number.

### O3. YouTube videos fail ("all YouTube videos errored")

The owner's error text is not available yet (see step 0).

**Most likely cause (inferred from the code, not reproduced):**
- Files saved by common YouTube download tools are usually VP9 or AV1 in WebM/MKV with Opus audio. Some are MP4 with AV1, VP9 or H.264 and AAC.
- Analysis decodes the whole file in order (`analyze.py:33-51`) and passes, so the job is added.
- Segments then read frames by index with `SimpleDecoder(..., need_scanned_stream_metadata=False)` (`decode.py:99-107`, `138`).
- Matroska stores no frame count. The PyNvVideoCodec 2.x decoder reference says that without scanning, the length "may be approximate or 0", and that indexing outside it raises `IndexError`.
- So segments probably fail with "Segment 1 failed: IndexError …", or read the wrong frames.

**Other candidates:**
- **Audio check.** The original audio duration is taken from the container (the longest track, `probe.py:180`) and checked at assembly (`mux.py:185-198`). A WebM whose video is more than about 20 ms longer than its audio fails after all the work is done.
- **Saved interpolation model.** A saved non-default interpolation model makes 50/60 fps inputs fail when they are added (`engine.py:901-909`, `registry.py:525-535`).
- **FFmpeg build.** An FFmpeg build without software AV1 decoding reports an unknown pixel format (`decode.py:78-81`).

**Test coverage:** every test uses libx264/libx265 MP4 files only.

**Do:**
0. **The owner's failed jobs.** First read the permission line at the end of O3, and act only if it says YES:
   - Copy the manifests and logs of the owner's failed jobs (`jobs/<id>/manifest.json`, `job.jsonl` and `logs/seg_*.log` under the owner's engine home) to a scratch folder outside the repository.
   - Read only the copies.
   - Report each failure's stage and exception, anonymised: no file names, titles or paths.
   - Never open, copy or change the videos.
   - If the line says NO, skip this step and use the synthetic files in step 6.
1. **Frame-exact decoding for every accepted container.**
   - Each decoded frame is the analysed frame at that index, checked by timestamp.
   - Seeking to a segment start gives the same frames as decoding in order.
   - Choose the method: scanned metadata, decoding forward from the nearest keyframe, or remuxing the video stream to MP4 without re-encoding during preparation. If you remux, count its disk space in admission and remove it after the job.
   - Report which method you chose and what it costs for a 2-hour file.
2. **Audio checks** use the audio stream's own duration and start, measured from its packets, not from the container. The tolerance allows for Opus being re-encoded to AAC (codec frame size and priming).
3. **A saved interpolation model** is ignored when 2x is not active for that input, with a note in the details, instead of failing.
4. **FFmpeg check at start-up.** Check that the bundled FFmpeg can decode VP9 and AV1 in software, because probe and analysis rely on it. If it cannot, say so in Settings and in the Add dialog for those files.
5. **Plain-word failures.** Name the stage and what to try, for example "Couldn't read frame 1,234 of this WebM file. …". The raw exception goes only into **Copy details**.
6. **Test files.**
   - Generate them with FFmpeg from synthetic patterns when the tests run. Never download them, never commit them. Each is 10 s long.
   - Formats:
     - VP9 + Opus in WebM;
     - AV1 + Opus in WebM;
     - AV1 + AAC in MP4;
     - VP9 + Opus in MKV;
     - H.264 + AAC in MP4, as the control.
   - Variants:
     - 1080x1920/30, 1920x1080/60 and 25 fps;
     - start_time ≠ 0;
     - video 100 ms longer than audio;
     - no audio;
     - VFR.
   - If CI's FFmpeg lacks an encoder, skip that case with the reason, and run it on the GPU PC.
   - On the GPU PC, run each file end to end through Standard and Fast. Check:
     - the frame count and timestamps;
     - audio sync within ±20 ms;
     - every NVDEC-decoded frame equals FFmpeg's CPU-decoded frame at the same index (bit-exact for 8-bit).

Owner permission to read failed-job logs (copies only, read-only, anonymised report): **YES (the owner answered on 2026-10-14).**

### O4. Model install progress (item 16)

**What the owner saw:**
- Install stays at 0% for a long time while showing "4:22 left".
- Sometimes it waits at 0% and then jumps to 100%.

**What the owner asked for:** a light tint that fills the Install button from left to right while the model installs.

**Cause (confirmed):**
- **The install waits for the running part.**
  - A new install is created as `waiting`, with `remaining_seconds` set to the predicted time of the running part (`engine.py:1415-1427`).
  - It starts only between parts (`engine.py:1507-1520`, `controller.py:818`).
  - So while a job runs, the card shows "0% · 4:22 left", and the number does not count down.
- **A fake percentage blocks the real one.** The first poll writes a fake `elapsed/60` percentage (`engine.py:1602`, `1675`), so real progress is not used until it passes 1%.
- **Some downloads report no progress.** Archive models, RIFE models and blend weights download with no progress callback (`registry.py:329-352`, `386-388`). They stay near 0% until verification and then jump.
- **Plain-URL models are hashed twice** (`basicvsr.py:69`, `registry.py:378`).

**Do:**
1. **Downloads start at once**, even while a job runs, because they use only the network and the disk.
   - Only steps that need the GPU wait for the current part.
   - While waiting, the card says "Waiting for the current part to finish · about M:SS", with a live countdown.
2. **Phases with honest progress:**
   - Downloading, measured in bytes.
   - Checking, measured in bytes hashed, done once.
   - Testing on the GPU, measured against its predicted time.
   - Weight the overall percentage by each phase's predicted time. Never derive a percentage from elapsed time alone.
3. **Every download path reports bytes.** Put the expected size of every file and archive in its manifest, so the total is known before the first byte arrives.
4. **Time left** comes from the measured speed, smoothed over at least 3 s. Show it after 2 s of data; before that, show "Starting…".
5. **Look:**
   - The Install button becomes a progress bar. A light tint fills it from left to right as the overall percentage grows, with "Downloading 42% · 1:10 left" on it.
   - Text contrast is at least 4.5:1 on both the filled and unfilled parts, in both themes.
   - With reduced motion, nothing animates between updates.
   - When the install finishes, the button becomes **Uninstall**.
6. **Gate:** a local test server throttled to 2 MB/s serves a 100 MB file. Test the archive, RIFE and plain-URL paths. For each:
   - progress updates at least once per second;
   - it is never stuck at 0% for more than 2 s after the first byte;
   - the percentage only goes up;
   - the time left is within ±20% of the actual after 10 s.

### O5. Compare screen (item 18)

**What the owner said:**
- Compare takes a very long time.
- For finished videos, they want to compare just the original with the result, with no model loading.
- Touchpad pinch zoom does not work.
- Nothing should show on the video at the divider.
- Double-clicking the video selects the text "Seek frame".

**Findings:**
- **Pinch.**
  - The pinch listener uses `{passive:false}` (`Trial.tsx:204-215`), but it is attached only to the 320 px `.canvas-viewport`. Electron does not intercept the event.
  - The only test dispatches a synthetic `wheel` event (`p1e.spec.ts:120`), which skips Chromium's touchpad-gesture path.
  - Why pinch failed on the owner's touchpad is not proven.
- **Drawn on the video.** The swipe handle is drawn over the video (`Trial.tsx:427`, `style.css:1251`), and side-by-side mode paints label chips into the picture (`Trial.tsx:315-327`).
- **Text selection.** There is no `user-select` rule anywhere.
- **Speed.** Compare runs a full Standard pipeline for each model in a fresh process: about 65 s per C1 model (P1d-2 report). When a job is running, it also waits for up to one part (about 180 s of work).

**Do in this cycle:**
1. **Nothing on the video at the divider:** no handle, icon, label or line.
   - The split is set with the slider under the video, or by two-finger horizontal scrolling over the video.
   - Labels ("Original" and the model names) sit outside the picture in every mode.
2. **No text selection.** Set `user-select: none` on the Compare dialog and on the player. Text inputs, logs and the Copy details text stay selectable. Double-click keeps its current action.
3. **Pinch zoom works** with the pointer anywhere over the dialog's video area, for both fine touchpad deltas and notched Ctrl+wheel.
   - Test it through Chromium's own gesture path in the e2e suite: CDP `Input.synthesizePinchGesture` with `gestureSourceType: "mouse"` (touchpad).
   - The owner checks a real touchpad.
4. **Show why it is slow.**
   - While Compare waits for the GPU, show "Waiting for the current part of <job> to finish · about M:SS".
   - While models run, show each model's progress and time left.
5. **Not in this cycle:** the quick before/after compare for finished jobs (no models) and Compare speed-ups belong to the new player and the warm worker in P1e-3.

### O6. History and the player (items 10, 11 and the overall comments)

1. **Fullscreen.** The player's expand button does nothing, because the permission handler denies everything (`main.cjs:384-386`), including HTML fullscreen.
   - Allow `fullscreen` for the app's own window only.
   - Keep every other permission denied.
   - Test it.
2. **Remove the Clear history… button.** Add **Select all** in Select mode.
3. **Select** becomes a small button at the right end of the History header.
4. **Badges.** Thumbnails show no "Done" badge.
   - Only records that need attention show ⚠︎: failed, cancelled with no output, output missing or changed, or a part that used the simpler frame doubling.
   - The reason shows on hover and in the popup.
5. **One removal dialog** for one or many records, with three choices:
   - **Remove from History**
   - **Move the finished videos to the Recycle Bin**
   - **Move the originals to the Recycle Bin**

   At least one must be on.
   - Opened from a record's **Delete video files…**, the finished video is on and the others are off.
   - Opened from Select → Remove, Remove from History is on and the others are off.
   - Undo appears whenever a record is removed from History.
6. **The new player.** It will be built in P1e-3 from a mockup the owner is reviewing now. In this cycle, Part P's streaming is the only player change.

### O7. Other screens (overall comments)

1. **Settings:** "Show the tour again" becomes a **Tutorial** button, right-aligned in its row.
2. **Models:**
   - "Compare on my video" moves to the right end of the tab row (the category pills, `Pages.tsx:147-166`).
   - "Add my own model…" moves to where "Compare on my video" was (`Pages.tsx:129-131`).
   - On the "Bigger picture" tab, the built-in "Standard resize" card (`Pages.tsx:168-203`) puts facts and buttons on the card. Make it compact like the others: name, summary and "Built in". Its facts and "Make it my default" go in its details popup.
   - The tab count counts real cards (`Pages.tsx:161`).
3. **Errors:**
   - Every persistent error or warning gets an X at its top right. It can be reached with the keyboard and is labelled "Dismiss".
   - This covers:
     - the Problem bar (`App.tsx:457-467`);
     - ConnectionBanner and ControlWarning;
     - failed installs and failed operations;
     - inline errors (`Pages.tsx:143`, `241`, `420`; `Trial.tsx:538`, `901`; `Queue.tsx:354`; `ScheduleView.tsx:229`).
   - Dismissing hides the message until a new error happens. It stays in the logs, and the job keeps its ⚠︎.
   - Dismissing the Problem bar also clears `last_error` in the engine, so it does not come back on reconnect.
4. **Schedule:**
   - Remove the **Turn on** button (`ScheduleView.tsx:170`). The big switch is the only control.
   - "+ Add hours" becomes the Plus icon followed by "Add hours", with no "+" character, like Home's Add videos.
5. **Add dialog:**
   - **Mode descriptions.** Put a short description under **Standard** and under **Fast**, with room to breathe. Suggested text:
     - Standard: "Cleans up compression and doubles the frame rate. Best quality, takes longer."
     - Fast: "Doubles the frame rate without cleanup. Much quicker."

     Show each mode's estimate for the selected files on its card.
   - **Per-file settings.** Today one setting applies to every file (`Queue.tsx:41`, `66`, `383-390`).
     - Each file row gets a one-click **Standard | Fast** switch and a **Settings** expander for that file's other options.
     - The top cards set the default for every file ("Apply to all").
     - Estimates and finish times update for each file, and the total updates too.
6. **Responsiveness while processing.**
   - Run the segment child and FFmpeg at Below Normal process priority, so the PC stays responsive.
   - Report the throughput change on the reference job. None is expected when the PC is otherwise idle.

### O8. The owner's estimate check (item 15)

**What the owner reported** for a 5–10 minute Standard job:
- the Add dialog predicted 00:30;
- Home predicted 00:17 at about 50%;
- it finished at 00:20.

The early live estimate matches Part E's findings.

**Do (in Part E):**
- Reconstruct this job from a read-only copy of its manifest. The owner allowed this for finished jobs on 2026-10-12.
- Report, anonymised:
  - its first estimate;
  - its live estimate at 50%, with the old code and with the new code;
  - its actual finish time.

### O9. Speed: measurement only

The owner said that "model loading and processing are slow and heavy."
- Nothing that ships changes in this cycle. The owner decides afterwards, from the numbers.
- Keep the GPU time for this under 2 hours, in an isolated home.

**Measure:**
1. **GPU busy share.**
   - Sample GPU utilisation at 10 Hz with NVML during:
     - the 5 s reference clip in Standard;
     - the same clip in Fast;
     - a 60 s Standard job.
   - Report the busy share, and the idle gaps by cause: part start-up, decode, synchronisation, encode, analysis and finalization.
2. **Per-part start-up.**
   - Break it down:
     - parent and IPC;
     - child entry;
     - CUDA initialisation;
     - weight verification;
     - model loads;
     - the first memory sample (the PowerShell `Get-Counter` runs, `gpu_memory.py:48-78`).
   - Estimate what a warm worker, with models kept loaded across parts, would save on a 2-hour Standard job and on each Compare click.
3. **Candidate speed-ups on the reference clip.** For each, report the fps, the speed-up, the peak VRAM, and the difference from today's output: maximum absolute difference and PSNR, in 8-bit RGB, over all frames.
   - **Expected to be bit-identical.** Say whether each one is.
     - Keep C1 on the GPU between clips, with no per-clip move or `empty_cache` (`models/basicvsr.py:70-93`).
     - Use fewer RIFE syncs (`models/rife.py:66-86`).
     - Skip resize and RIFE on overlap frames that are not kept (`runner.py:495-501`).
     - Overlap decode and encode with inference on separate CUDA streams.
   - **Expected to change the output slightly:**
     - `cudnn.benchmark`;
     - `torch.compile`;
     - channels-last;
     - TensorRT through Torch-TensorRT (say so if C1's deformable convolution prevents it);
     - clip lengths 21/2 and 30/2.
4. **Report** the results as a table. Recommend only what the numbers show.

### O10. Acceptance additions for section 10

- **G1 screenshots:**
  - the O2 error row and the error screen;
  - the O4 install fill, in both themes;
  - Compare without the handle;
  - the History header and the removal dialog;
  - the Models tab row;
  - the Tutorial button;
  - Schedule;
  - the Add dialog with rows for each file.
- **G2 CI tests:** the tests listed in O1 to O5.
- **G3 GPU and real PC:**
  - the O1 Windows shell test;
  - the O2 4K measurements;
  - the O3 end-to-end runs;
  - O8;
  - O9.
- **Report:**
  - One row for each of O1 to O9 in the part table.
  - The O3 decode method and its cost.
  - The O2 4K numbers.
  - The O9 table.
  - The O4 gate numbers.


## Additional owner instruction

直近のログも調べてください。処理が止まってしまいました。安定して動画処理ができるよう原因追求と工夫を考えてください。

Owner clarification: progress stopped and later showed an error. The affected input is 960x540 in Standard mode. Owner later confirmed MP4, H.264, 29.97 fps, and 1440p output.

Additional owner request (2026-10-15):

4k出力の場合でも安定して処理できるか確かめてほしいです。

Verification scope: add an isolated 1440p reproduction, then synthetic approximately two-minute 960x540 H.264 MP4 at 30000/1001 fps through Standard and Fast with 3840x2160 output. Keep these GPU jobs sequential. Record completion, stalls, retries, interpolation fallbacks, per-PID sampled GPU memory, Torch peaks and output video/audio validation. Do not infer stability for all long videos from these bounded runs.
