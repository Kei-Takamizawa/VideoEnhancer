# CURRENT_TASK: Cycle P1c-4 (qualify the optional models, finish Compare, close P1c)

- **Task ID:** VE-P1c-4
- **Date:** 2026-10-10
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** continue on branch `p1c-redesign` (draft PR #4, last commit `db8585c`, CI green on Windows and Ubuntu). Save this file as `.ai/CURRENT_TASK.md`, commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Do not push to `main`. If the owner adds an "Owner feedback" addendum below, treat it as part of this task. Its items come before Part M2.

## Working rules (unchanged)

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option that keeps existing outputs unchanged (or skip only that item), and continue. Stop early only if every remaining item is blocked.
2. Order: Owner feedback (if any) → Part M2 (model qualification) → Part C2 (Compare interactions) → Part E (evidence gaps). Long GPU measurements run whenever the GPU is free.
3. If time runs out, finish earlier items completely and mark the rest NOT RUN. Never report a test as passed if it did not run.

## 0. Status after P1c-3 (review of `db8585c`)

Accepted as done (keep, do not redo):

- **Part U:** done, including U-rest.
- **Model catalog foundation:**
  - catalog blocks for C1 and RIFE 4.25, and category cards;
  - consent, verification, Details, defaults captured before preparation, and guarded removal.
- **Compare foundation:**
  - `POST compare` with up to three models;
  - shared index and range analysis, progressive previews, and the 5-session / 2 GB cache;
  - four-stream WebCodecs viewer with side by side, swipe, zoom, shared pan, frame step and Use this.
- **GPU acceptance:**
  - G1: percent and Work left moved 13.97 s after segment start.
  - G2: three jobs and two trials finished, the whole run took 2,255.6 s.
  - G3: 935 window polls with no unexpected window.
- **Four-stream sync:** 100 random seeks and 300 played frames with 0 mismatches.

**Designer decision on Question 3 (Fast has no cleanup stage):** confirmed, Fast does not compare cleanup models.
- When Compare opens for a Fast job or a Fast Add dialog, the Cleanup category chip is disabled with the note "Fast does not clean up. Switch this video to Standard to compare cleanup models."
- When the job has not started, the note includes a "Switch to Standard" button that changes the mode, re-estimates, and enables the chip.
- Smoother motion and Bigger picture stay available in Fast.

## 1. Part M2: qualify every optional catalog entry

The catalog design (M1 to M3 in Appendix A) is unchanged. This cycle completes the **qualification** of each entry in the M2 table. Work in this order:
1. The BasicVSR++ variants (Track 1, Track 2, denoise), which use the existing adapter.
2. The spandrel single-frame models (SCUNet real PSNR, FBCNN, 1xDeH264_realplksr).
3. RIFE 4.26 and RIFE 4.25 lite.
4. The DRUNet strength wrapper (Light / Medium / Strong).
5. The `size` stage with 2xLiveActionV1_SPAN and Real-ESRGAN realesr-general-x4v3 (with the `wdn` blend).

**Qualification of one entry** (all steps must pass, otherwise the entry stays omitted with the failing step in the report):

1. **Source.** Download from the original publisher's URL listed in M2. Use a mirror only if it serves a byte-identical file. Record the URL, byte size and SHA-256 you computed.
2. **Licence.** Copy the exact licence string from the publisher's repository or model page. For weights whose terms are not stated (the BasicVSR++ files), write "Code Apache-2.0; the weights' terms are not stated" and keep `commercial_use_allowed: false`. This is a personal, non-commercial app, so such entries are allowed.
3. **Load.** The file loads through its adapter with no custom CUDA build. For RIFE 4.26 and 4.25 lite, unpack the publisher archive and check that the pinned RIFE adapter loads the matching IFNet version. If it needs a different IFNet definition, add it as a versioned adapter variant without changing 4.25's behaviour.
4. **Reference measurement on the RTX 4060 Ti.**
   - Use one fixed synthetic 5 s clip, 720×1280 at 30 fps, rendered to 1080×1920, with the model in its real pipeline position.
   - Record input fps over the whole clip, without model loading.
   - Record the Torch peaks: `torch.cuda.max_memory_allocated` and `max_memory_reserved`, reset before the run.
   - Record the process GPU memory peak, dedicated plus shared, sampled **every 1 s** during the run. This 1 s sampling is the budget measurement for this cycle. The 30 s job sampling stays for normal jobs.
   - The entry passes the budget when the sampled process peak is at most 5.0 GB. Single-frame models may use tiling with overlap to get there; record the tile size.
   - Write `reference_speed` (fps, Torch peaks, sampled process peak, tile size) into the manifest's catalog block.
   - Measure **C1 (Gentle cleanup)** and **RIFE 4.25 (Smooth motion)** the same way, so every card shows a measured speed.
5. **Compare check.** Run a real 5 s compare on the GPU with the entry and the category default. Both previews render, and the card shows the measured speed.
6. **Defaults unchanged.** The default pipeline (C1, RIFE 4.25, non-learned resize) produces byte-identical output before and after this cycle, using the existing strict C1/RIFE tensor-equality test and the CPU fixtures.

DRUNet wrapper:
- Spandrel's default call fixes the noise level, so pass the strength map yourself.
- Pick the three strengths from the publisher's documented deblocking setting, which is a quality-factor map for JPEG-style deblocking.
- For Light, Medium and Strong, use quality factors 50, 30 and 10, unless the publisher's code defines the map differently. In that case, follow the publisher and report the mapping.
- Show the three choices as one card with a three-way selector, not three cards.

Size stage:
- The stage runs after cleanup and before the final resize and RIFE.
- With "Standard resize", the pipeline is exactly today's (byte-identical).
- The Real-ESRGAN blend uses the publisher's documented interpolation of the `x4v3` and `wdn-x4v3` weights. Offer two fixed points, "Faithful" (denoise strength 0.2) and "Cleaner" (0.6), as a two-way selector on the card.

## 2. Part C2: finish the Compare interactions

1. **Range box.** The 5 s box on the thumbnail strip can be dragged with the mouse and moved with the arrow keys (1 s per step, Shift for 5 s). The default range is the busiest 5 s from the analysis data. The middle of the video is the fallback only when that data is missing.
2. **Automatic re-render.** Changing the range or the model selection starts a new render 800 ms after the last change. The new render cancels any render still running, and the tiles show "Making preview" again. The explicit Render button stays as a fallback for errors.
3. **Reuse rendered models.**
   - The cache key is the source identity (path, size, mtime), the CFR range, the stage settings, the model id and the model's SHA-256.
   - A model whose preview exists for the same key is shown at once, not rendered again.
   - The Original preview is reused the same way.
4. **Install, then select.** Installing a model from a dashed "+ Name" chip selects it after verification. If three models are already selected, it replaces the last one. The render starts automatically.
5. **Three different models on the GPU.** One measured compare with three different qualified models of the same category, for example Gentle cleanup, Crisper cleanup and All-round cleaner. Report each model's fps, the time to the first tile, and the total time.
6. **Fast and cleanup:** see the decision in section 0.

## 3. Part E: evidence gaps

- **G2 trial progress:**
  - Keep each trial's percent history (time and percent, at most every 2 s) in its operation state.
  - Rerun only the two G2 trials (one while a job runs, one outside operating hours).
  - Show that neither stays at 0% for more than 60 s.
- **Owner visual check:** the owner runs `/mnt/project-files/design/P1c_owner_check.md` (Japanese) on this branch. You do not need to run it. Keep the owner's queue untouched.

## 4. Acceptance criteria

- **A6:** every M2 entry is either qualified (all six steps) or omitted, with the failing step and its evidence. C1 and RIFE 4.25 have measured `reference_speed`. Install, Verify again, Make it my default and Remove work for each qualified entry. The default pipeline output is unchanged.
- **A7:** the three-model GPU compare is done (C2 item 5). The four-stream sync test still passes. Range drag, auto re-render, reuse and install-then-select all have component tests and one Electron e2e test with synthetic previews.
- **A3:** the G2 trial rerun shows no 0% stretch longer than 60 s.
- **A8:** checks are green: `ruff`, `ruff format --check`, `pyright`, CPU tests, the D2 suite, GUI lint, typecheck, unit tests, build and e2e. Windows and Ubuntu CI is green for the final commit.
- **A9:** Models and Compare screenshots with synthetic footage at 1280×800 in dark and light, showing the qualified entries.

## 5. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs in English.
- Never commit media, weights, previews, generated videos, `node_modules`, build output, the owner's logs, or private sample names. Screenshots use synthetic footage only and stay outside the repository.
- No models that add skin texture and no GAN real-world video models. Do not add entries beyond the M2 table.
- Keep the service security model. No telemetry, no auto-update.
- Update `docs/ADDING_MODELS.md`, `docs/THIRD_PARTY_MODELS.md` (licence and source per qualified model), `docs/GUI.md` and `docs/API.md`.

## 6. Report (`.ai/LAST_REPORT.md`, English)

- A table per M2 entry: qualified or omitted, URL, SHA-256, licence, fps, Torch peaks, sampled process peak, tile size, and the failing step if any.
- The C2 results and the three-model compare timings.
- The G2 trial percent histories.
- A section "Questions for the designer", each with the default you chose meanwhile.
- Exact reproduction steps.

Never report a test as passed if it did not run.

## Owner feedback

Added 2026-10-11 after the owner ran `P1c_owner_check.md`. Items 1 to 7, 10, 11, 13 and 14 passed. The owner is now redesigning the whole GUI (cycle P1d: bottom dock, compact layout, numeric schedule input, new History actions). That changes this cycle as follows.

**F1. AV1 must be available for every video (do this first).**
- Today the Add dialog offers AV1 only when `health.av1_supported` is true, and the owner sees videos where AV1 is missing. The RTX 4060 Ti supports AV1 hardware encoding, so the probe is the suspect (not verified).
- Find the root cause. Probe the same encoder path the pipeline uses, at a realistic size (at least 1920×1080), not a tiny lavfi frame. Log the failure reason and expose it as `av1_unavailable_reason` in `health`.
- The Add dialog and Settings must use the same availability. If AV1 is unavailable, show the reason in one line instead of hiding the option silently.
- If an AV1 job fails at encode time, fail it with a clear message. Never switch codecs silently.
- Evidence: a unit test with the probe mocked; on the GPU, AV1 outputs for a portrait job (720×1280 in, 1080×1920 out) and a landscape job (1920×1080 in and out). Report `ffprobe` `codec_name=av1` and the frame counts.

**F2. Defer the GUI parts of Part C2 to P1d.** The new design will replace these screens, so do not build UI that will be thrown away.
- Do: C2 item 3 (reuse by cache key), the service side of item 2 (a new render request cancels the running one), the service side of item 1 (an API that returns the busiest 5 s range), and item 5 (the three-model GPU compare).
- Skip and mark **DEFERRED to P1d** (not failed): the draggable range box, the 800 ms automatic re-render in the GUI, and install-then-select in the GUI, with their component and e2e tests.
- A7 now means: item 5 done, reuse and cancellation have service tests, and the four-stream sync test still passes.
- A9 screenshots: DEFERRED to P1d.

**F3. Model descriptions for the new Models cards.** The new design shows a one-line description on each card and the details after a click. If the catalog block has no such field, add `summary` (English, at most 90 characters, plain words) next to the existing long description, and fill it for every qualified entry, C1 and RIFE 4.25. Do not change the Models screen layout in this cycle.

**F4. Not in this cycle (planned for P1d, listed so you do not start them):** schedule input and its performance, the faster first trial result, History multi-select and file deletion, deleting the original after a verified output, the dock, zoom and the new colours.

Order for this cycle: F1 → Part M2 → C2 (F2 scope) → Part E.

## Appendix A. Part M specification (unchanged)

Work order inside Part M: (1) the `catalog` manifest block, the Models screen (M3) and the entries that run on the existing `basicvsrpp`, `rife` and `spandrel` adapters; (2) the DRUNet strength wrapper; (3) the `size` stage. If time runs out, the `size` stage goes last.

### M1. What the catalog is

Built-in manifests gain a `catalog` block so the Models screen can describe each model in plain words. Every catalog model is optional: nothing downloads without the owner's consent, and the current defaults (BasicVSR++ NTIRE21 Track 3 for cleanup, RIFE 4.25 for motion, the non-learned resize for size) keep producing exactly what they produce today.

Suggested manifest additions (names are suggestions):

```json
"catalog": {
  "category": "cleanup",
  "title": "Gentle cleanup",
  "description": "Removes blockiness and smeared detail using neighbouring frames. Keeps faces and the filtered look as they are.",
  "look_change": "very_little",
  "invents_detail": "low",
  "flicker": "none",
  "default": true,
  "licence_plain": "Code free for any use; the weights' terms are not stated",
  "reference_speed": {"gpu": "RTX 4060 Ti 8GB", "input": "720x1280", "output": "1080x1920", "fps": 2.38, "peak_memory_gb": 4.7}
},
"weights": {"url": "...", "mirrors": ["..."], "sha256": "...", "bytes": 0}
```

- `category`: `cleanup` (1x restoration), `motion` (frame interpolation), `size` (learned enlarging before the final resize). `faces` is reserved for P2 and shown as a disabled tab "Faces · coming later".
- `look_change`: very_little / little / noticeable. `invents_detail`: low / medium / high (from the training type: fidelity-trained = low, perceptual or unknown losses = medium, GAN = high). `flicker`: none (video models) / possible (single-frame models).
- `reference_speed` and memory are **measured by you** on the owner's RTX 4060 Ti (720×1280 input, 1080×1920 output, the model in its real pipeline position). Never copy speeds from papers. After a compare on the owner's PC, the GUI shows the speed measured there.
- SHA-256 and size are computed by you from the downloaded file. Prefer the original publisher's URL; a mirror is allowed only if it serves a byte-identical file (same SHA-256).
- `licence` keeps the exact licence string; `licence_plain` is the short text for the card ("Free for any use", "Free with credit (CC BY 4.0)", "Personal use only (non-commercial)").

### M2. Catalog for this cycle

Only models that run on the existing adapters (`basicvsrpp`, `rife`, `spandrel`), plus one small wrapper for DRUNet. Models that need a new adapter (FTVSR, EDVR, FastDVDnet, IFRNet, EMA-VFI) are out of scope for P1c.

| Category | Card title | Model and weights (verify) | Licence | Character for the card | Look / invents detail / flicker |
| --- | --- | --- | --- | --- | --- |
| cleanup | **Gentle cleanup** (default, already installed) | BasicVSR++ NTIRE21 decompression Track 3 (`basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth`) | Apache-2.0 code; weights' terms not stated | Removes blockiness and smeared detail using neighbouring frames. Keeps faces and the filtered look as they are. | very little / low / none |
| cleanup | **Cleanup, other training** | BasicVSR++ NTIRE21 Track 1 (fixed-quality x265 training), existing adapter | Same | Same idea, trained on a different kind of compression. Usually looks almost the same; sometimes calmer. | very little / low / none |
| cleanup | **Crisper cleanup** | BasicVSR++ NTIRE21 Track 2 (`..._ntire_decompress_track2_20210314-eeae05e6.pth`), existing adapter | Same | Trained to look sharper rather than to match the original exactly. Can add a little artificial sharpness. | little / medium / none |
| cleanup | **Grain and noise calmer** | BasicVSR++ denoise (`basicvsr_plusplus_denoise-28f6920c.pth`, mid 64, 15 blocks), existing adapter | Same | Calms grain and noise across frames. Not made for blockiness; may soften very fine edges slightly. Faster than Gentle cleanup. | little / low / none |
| cleanup | **Adjustable deblock** (Light / Medium / Strong) | DRUNet deblocking (`github.com/cszn/KAIR/releases/download/v1.0/drunet_deblocking_color.pth`) through spandrel with your own wrapper that passes the strength map (spandrel's default call fixes it); three catalog choices share one weights file | MIT | Smooths blocks and ringing on each picture without adding detail. Strong can look waxy. | little / low / possible |
| cleanup | **All-round cleaner** | SCUNet real PSNR (`github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_psnr.pth`) | Apache-2.0 | Cleans mixed noise and compression on each picture. Calm, slightly smoothing. | little / low / possible |
| cleanup | **Picture deblock** | FBCNN (already used as a benchmark candidate) | Apache-2.0 | Cleans each picture on its own. Good for calm clips; can flicker a little on moving ones. | little / low / possible |
| cleanup | **H.264 remover (community)** | 1xDeH264_realplksr (`github.com/Phhofm/models/releases/download/1xDeH264_realplksr/1xDeH264_realplksr.safetensors`) | CC BY 4.0 | Made by the community for H.264 blockiness. Crisper, slower, and less predictable. | noticeable / medium / possible |
| motion | **Smooth motion** (default, already installed) | RIFE 4.25 | MIT | Makes new in-between frames. Recommended by its author for most scenes. | very little / low / none |
| motion | **Smooth motion, newest** | RIFE 4.26 (from the Practical-RIFE release; verify the source) | MIT | The newest version. Sometimes better on fast motion, sometimes not. | very little / low / none |
| motion | **Smooth motion, faster** | RIFE 4.25 lite | MIT | Faster, slightly less accurate on fast motion. | very little / low / none |
| size | **Standard resize** (default, no download) | the existing non-learned resize | none | Makes the picture bigger without AI. Never changes the look. | very little / low / none |
| size | **Faithful 2× enlarger** | 2xLiveActionV1_SPAN (from `github.com/jcj83429/upscaling`) | CC BY-NC-SA 4.0 (personal use only) | Enlarges real-life video and tidies compression edges and halos. Keeps grain and colours. Can over-sharpen a little. | little / medium / possible |
| size | **Sharper detail** | Real-ESRGAN realesr-general-x4v3 (and the `wdn` version for a blend) | BSD-3-Clause | Makes edges crisper. Can invent texture that was not there, so it may change skin and hair. | noticeable / medium / possible |

Rules:

- Do not add models that add skin texture or are GAN real-world video models (for example h264Texturize, SkinDiffDetail, RealBasicVSR). The product keeps the beauty-filter look and never redraws faces.
- Every model must stay within the memory budget from P1a-6 (process total under 5 GB at 720×1280 → 1080×1920); single-frame models may use tiling with overlap. A model that cannot meet it, cannot be downloaded, or whose licence cannot be confirmed is left out, with the reason in the report.
- The `size` stage runs after cleanup and before the final resize to the chosen size and before RIFE. With "Standard resize" the pipeline is exactly today's.

### M3. Models screen (U6)

```
| Models                                       [Add my own model…] [Compare on my video] |
| (Cleanup · 8) (Smoother motion · 3) (Bigger picture · 3) (Faces · coming later)        |
| +--------------------------------+ +--------------------------------+ +-------------+ |
| | Gentle cleanup        [Default]| | Crisper cleanup                | | Adjustable  | |
| | BasicVSR++ · compressed video  | | BasicVSR++ · perceptual        | | deblock     | |
| | Removes blockiness and smeared | | Trained to look sharper rather | | ...         | |
| | detail using neighbouring ...  | | than to match the original...  | |             | |
| | Speed      Changes the look  Licence                             | |             | |
| | Slow       Very little       Free   | ...                        | |             | |
| | 176 MB                [Installed]| | 176 MB              [Install] | |             | |
| +--------------------------------+ +--------------------------------+ +-------------+ |
```

- Tabs per category with counts; Faces is disabled. Card grid (cards at least 320 px wide): title (17 px / 650), technical name (12 px, text-3), Default badge, description (14 px, text-2), three small facts (Speed: Fast / Medium / Slow / Very slow from the measured fps, with "about N h per hour of video" in the tooltip; Changes the look; Licence plain text), size, and one button: Install (accent) or Installed. The ⋯ menu has Make it my default, Verify again, Details (exact licence, source URL, SHA-256, measured speed and memory), Remove (refused for a model used by queued jobs: "Used by 2 videos in the queue").
- Install opens the licence dialog from P1b (licence name and source URL, explicit agreement, consent recorded), then shows download progress and the SHA-256 result on the card.
- "Make it my default" sets the default model of that category in Settings; Standard uses the cleanup default, both modes use the motion and size defaults. New jobs pick up defaults; queued jobs keep their settings.
- The Add dialog's More options lists installed models per category (Cleanup model, Smoother motion, Bigger picture).
- "Add my own model…" keeps the P1b validation; user models choose their category in their manifest (`docs/ADDING_MODELS.md` explains the new fields).

## Appendix B. Part C specification (unchanged)

### C1. Engine

- `POST compare` with `{file, start, seconds (3/5/10, default 5), models: [up to 3 model ids of the same category], settings}` returns one operation. It renders the source excerpt once ("Original", resized with the pipeline's own resize to the output size) and then each model through the real pipeline with that model in place of the stage it belongs to (other stages as in the settings). Previews are H.264 8-bit, as the Trial previews are.
- Per model: progress, measured speed, and "about X h Y m for this video" from the measured speed and the estimator. Each model's preview is available as soon as it is done.
- Scheduling as in S4 and analysis as in D1 (one source index and one range scene analysis per compare, shared by all models). A model that is not installed is installed first, only after its licence dialog.
- Keep previews of the last 5 compare sessions (at most 2 GB, oldest removed first); previews tied to a job are removed with the job. Outside Git, under the engine home.
- The P1b Trial (`POST trial`) stays for the API, and the GUI's Trial becomes Compare with one model (classic Original vs result). The Compare preview cache (last 5 sessions, at most 2 GB) is implemented here.

### C2. Compare screen

```
| [<]  Compare models                                                     [Change video…] |
|      beach_walk.mp4 · 5 seconds from 0:42                                              |
| 0:42 – 0:47   Picked a part with lots of motion. Drag the box to choose other seconds.   |
| [▒▒▒▒[■]▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒]   (thumbnail strip)   |
| Compare (Original) (✓ Gentle cleanup) (✓ Cleanup, alternative) (✓ Picture deblock)       |
|         (+ Sharper detail · installs 5 MB)        [All side by side|Swipe two] [Fit|2×|4×] |
| +----------+  +----------+  +----------+  +----------+                                  |
| | Original |  | Gentle   |  | Cleanup, |  | Picture  |                                  |
| |          |  | cleanup  |  | altern.  |  | deblock  |                                  |
| |   9:16   |  |          |  |          |  |  Making  |                                  |
| |          |  |          |  |          |  |  preview |                                  |
| |          |  |          |  |          |  |  · 64%   |                                  |
| +----------+  +----------+  +----------+  +----------+                                  |
| Your file     Default       Calmer, a     Each frame                                   |
| as it is      About 2 h 40m bit softer    on its own                                    |
|               [Chosen]      [Use this]    Measuring speed…                              |
| [|<] [▶] [>|]  ───────●───────────────  0:44.2 / 0:47.0  [Loop]  All pictures stay in step, frame by frame. |
```

- Top: a thumbnail strip of the whole source with a draggable box for the chosen seconds. The default range is the busiest part (most motion from the analysis data), else the middle. Changing the range renders again.
- A small "Comparing: Cleanup ▾" selector before the chips picks the category (Cleanup, Smoother motion, Bigger picture); the other stages stay as in the job's settings.
- Chips: Original is always shown; up to 3 installed models of one category can be selected (selected = filled chip with a check). Models not installed appear as dashed chips "+ Name · installs N MB" (opens the licence dialog, then installs and adds it). Changing the selection renders only what is missing.
- Layouts: **All side by side** (portrait sources: up to 4 in one row, about 240 px wide each at 1280×800; landscape sources: a 2×2 grid) and **Swipe two** (one large picture with a draggable divider and a "Left"/"Right" picker for any two of the shown items; zoom 2× by default).
- Zoom Fit / 2× / 4×, nearest neighbour when zoomed, with synchronized panning (drag any picture to move all of them). Frame step with buttons and the arrow keys, Play/Pause with Space, Loop, a position slider and "0:44.2 / 0:47.0".
- Synchronization: extend the P1b WebCodecs frame clock to up to 4 streams; draw only when every visible stream has the same frame index.
- Each tile: name label on the picture; two caption lines (character, "About 2 h 40 m for this video" or "Measuring speed…"); "Use this" sets the model for the job (only before it starts) or for the open Add dialog. For a job that already started the button is disabled with "Already started. Remove it and add it again to use another model." The chosen tile has an accent border and the button reads "Chosen". The tile's ⋯ menu has "Make it my default".
- Opened from: Models "Compare on my video" (pick a file), Add dialog "Try models first", Home and Up next row menus, History "Compare again". The back button returns to where it was opened.

