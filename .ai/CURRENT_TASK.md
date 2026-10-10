# CURRENT_TASK: Cycle P1c-3 (finish the redesigned GUI, model catalog, compare, and the GPU acceptance checks)

- **Task ID:** VE-P1c-3
- **Date:** 2026-10-10
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Repository:** https://github.com/Kei-Takamizawa/VideoEnhancer

**Start condition:** continue on branch `p1c-redesign` (draft PR #4, last commit `9ff4bb0`, CI green on Windows and Ubuntu). Save this file as `.ai/CURRENT_TASK.md` (it replaces the P1c-2 text, which stays in Git history), commit it, and write `.ai/LAST_REPORT.md` (English) at the end. Do not push to `main`.

## Working rules (same as P1c-2)

1. Do not stop the cycle for one blocked item. Write the question under "Questions for the designer", choose the safest option that keeps existing outputs unchanged (or skip only that item), and continue. Stop early only if every remaining item is blocked.
2. Order: Part U-rest → Part M → Part C → Part G (GPU acceptance). Part G's long runs may run whenever the GPU is free, for example overnight or during long builds. They must not wait for the end of the cycle if the GPU is idle earlier.
3. If time runs out, finish earlier parts completely and mark the rest NOT RUN. Never report a test as passed if it did not run.

## 0. Status after P1c-2 (review of `9ff4bb0`)

Accepted as done (keep, do not redo):

- **Part D:** source index (manifest first, then a cache keyed by path, size and mtime, 1 GB limit) and range scene analysis. The D2 fixture suite passed on CPU and CUDA: 24 cases. On the RTX 4060 Ti with a synthetic 2-hour, 3.39 Mbps file: a fresh index took 10.06 s and a cached one 0.05 s; the first frame reached the encoder after 15.78 s; frame hashes matched the whole-file trial. Three demux passes for a fresh index are acceptable at this speed.
- **Part S:**
  - live remaining work and finish times;
  - manifest-lock quarantine with Retry;
  - shared admission rules for planner and controller;
  - a stuck-trial fault injection that test code alone can enable;
  - Retry and `queue-complete` override endpoints.
- **Part W (code):** `pythonw.exe` selection, logging of the executable, and a real `pythonw.exe` parent that runs a CPU segment child.
- **Part U (delivered subset):**
  - tokens and themes, the 88 px rail, and Home with its attention banner;
  - cached thumbnails, and Preview result without the GPU;
  - the Add dialog mode cards and More options;
  - History with filters, search and Retry;
  - Schedule tracks, presets, drag, autosave and Undo, exceptions and overrides;
  - Settings in the new tokens.
- **Designer decision on an open point:** Add to queue may be pressed while files are still preparing. The job enters Up next as "Preparing…" and the server validates it. Keep this.

## 1. Part U-rest: finish the redesigned screens

Each item below comes from the P1c-2 report's "Unresolved items". Appendix A (sections U0 to U9) stays the full specification. This list says only what is missing, plus the designer's decisions.

1. **Home (U2)**
   - "Change mode" appears in the Up next row menu for jobs that have not started. It re-estimates the job and updates its row.
   - The "Problem" chip opens a small details panel: the plain-English message, time, job, and a Copy details button. It must not copy straight away.
   - The attention banner and the rail dot count only failures the owner has not seen. A failure counts as seen once its History card has been shown or the banner has been dismissed. Store the seen job ids with the GUI settings.
2. **Add dialog (U3)**
   - Show the output summary line: "Output: 1080p · 60 fps · HEVC · Saved next to the original, in "enhanced"", with More options at its right.
   - "Try models first" opens the new Compare (Part C). "Use this" there sets the dialog's model for that category.
3. **History (U4)**
   - Use relative wording: "Today 06:42", "Yesterday 23:18", and a weekday with date for older items ("Mon 10/06 04:55").
   - The menu item is "Compare again", opening Part C.
4. **Schedule (U5)**
   - The header range reads "could be Thu 23:10 – Fri 06:00", taken from the plan's best and worst scenarios.
   - Hovering or focusing a planned-work bar shows a tooltip: "evening_talk.mp4 62% → 100%, done 02:10".
   - Exceptions can be edited in place in the Exceptions card: click an exception to switch it between Off and hours, or to delete it. **Add a day** opens a date picker with Off or hours, without going through Custom.
   - "Only on Thu 10/09" moves from the row button into the block's context menu. The menu opens by right-click, by a small ⋯ on the selected or focused block, and by the Menu key.
   - Every save restarts the 8 s "Saved · Undo" timer. Undo restores the schedule from before the most recent save.
   - Rows may scroll when the window is shorter than 800 px.
   - Add component tests for drag, add, delete, keyboard edges, exception edit, Undo and override.
5. **Settings (U8):** group the settings into Defaults, App, Advanced (a disclosure), Diagnostics and About, in that order.
6. **Preview result**
   - Closing its dialog cancels the CPU encoding and deletes the partial files.
   - Quit during a preview leaves nothing that a later preview would reuse.
   - Test both.

## 2. Part M: optional model catalog (unchanged from P1c)

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

## 3. Part C: compare models on the owner's video (unchanged from P1c-2)

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

## 4. Part G: acceptance on the owner's PC (RTX 4060 Ti)

Use fresh `VE_HOME` folders with copied, verified model folders, never the owner's queue. Use synthetic or authorized clips, and never publish private sample names or frames of people.

- **G1 (A2):** a Standard job shows a changing percent and "Work left" within 30 s of its first segment start. Report the log timestamps.
- **G2 (A3):** run three jobs in a row (Standard 30 s, Fast 30 s, Standard 2 min), then a trial while a job runs, then a trial outside operating hours. All must finish, and no job or trial may stay at 0% for more than 60 s. Report the timings.
- **G3 (A4, automated part):** while the packaged app runs these flows, poll top-level windows every 100 ms with Win32 `EnumWindows` and record any new visible window of the classes `ConsoleWindowClass` or `CASCADIA_HOSTING_WINDOW_CLASS` (Windows Terminal), or any window owned by a process in the app's process tree other than the app's own windows. The flows:
  - a cold start with the engine not running;
  - adding a Standard job and a Fast job;
  - a trial, a compare and a model install;
  - Quit.

  The test passes when no such window appears. The owner then confirms by eye (section 9).
- **G4 (A6, A7):** the catalog and compare checks from Parts M and C.

## 5. Constraints

- Windows 11, no WSL. All code, comments, UI text and docs in English.
- Never commit media, weights, previews, generated videos, `node_modules`, build output, the owner's logs, or private sample names. Screenshots use synthetic footage only and stay outside the repository.
- Do not change what the existing presets produce: the CPU fixture outputs stay byte-identical. A trial or compare for a given source range and settings produces the same frames as the whole-file trial. The D2 suite must keep passing.
- Keep the service security model (localhost only, token, Host/Origin checks). No telemetry, no auto-update.
- The CLI keeps working on the same store.
- README (for non-engineers): "Using the app" covers Home, History, Schedule and comparing models. No technical terms beyond "NVIDIA RTX graphics card".
- Update `docs/API.md`, `docs/GUI.md`, `docs/ADDING_MODELS.md` and `docs/TROUBLESHOOTING.md` for everything that changed.

## 6. Acceptance criteria

- **A2, A3, A4:** Part G (G1, G2, G3).
- **A5:** Part U complete (the U-rest list plus Appendix A). Component tests cover:
  - Home: now processing, up next, Change mode, the Problem panel, and seen-failure tracking;
  - History: filters, search, relative dates, Retry, Compare again, and that Remove keeps the file;
  - Schedule: drag edges, add, delete, keyboard, autosave and Undo, exception edit, the block menu, and the override;
  - the Add dialog.

  One Electron e2e test adds a synthetic file, sees it in Now processing, sees it finish, and sees it in History.
- **A6:** Part M. Every catalog entry has:
  - a verified URL and SHA-256, and its exact licence;
  - a successful load through its adapter;
  - a 5 s compare on the RTX 4060 Ti within the memory budget;
  - its measured fps and peak memory in its manifest and in the report.

  An entry that fails any of these is left out, with the reason. Install, Verify again, Make it my default and Remove work from the GUI. The default pipeline output is unchanged.
- **A7:** Part C. Compare with 3 models on the GPU. An automated sync test uses synthetic clips with the frame number drawn in: for 100 random seeks and 300 played frames, all visible streams show the same frame index.
- **A8:** checks are green. Engine: `ruff`, `ruff format --check`, `pyright`, CPU tests and the D2 suite. GUI: lint, typecheck, unit tests, build and e2e. CI is green on Windows and Ubuntu for the final commit; confirm it after pushing and record the run in the report.
- **A9:** screenshots with synthetic footage of every screen, including Models and Compare, at 1280×800 and 1100×700, in dark and light, plus one at 150% scaling.

## 7. Checks to run

- Engine: `ruff check`, `ruff format --check`, `pyright`, `pytest -m "not gpu and not soak"`, `pytest tests/test_source_index.py` (CPU and GPU).
- GUI: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`, `npm run package`, the packaged smoke test, and G3.
- Owner hardware: G1 to G4.

## 8. GUI checks for the owner after the PR

1. Open the app: no black console window appears, now or while it works.
2. Drop a video on the window: the dialog shows Standard and Fast with their done times; Add to queue.
3. Home shows the video large with a percent that starts moving within about half a minute.
4. When a video finishes, it leaves Home and appears in History; Play opens it.
5. On Schedule, drag the edge of an hours block: the finish time at the top changes, and "Saved · Undo" appears.
6. Start a trial outside your hours: it starts at once.
7. On Models, install one optional model, then "Compare on my video" with three models and switch between All side by side and Swipe two.



## 9. Report (`.ai/LAST_REPORT.md`, English)

- A summary per part, and A2 to A9 with PASS / FAIL / NOT RUN and their evidence.
- Measured speed and memory for each catalog model, plus the omitted entries and why.
- The G3 window log summary.
- Screenshot paths (outside the repository).
- A section "Questions for the designer", each with the default you chose meanwhile.
- Known issues and exact reproduction steps.

Never report a test as passed if it did not run.

## Appendix A. Part U specification (unchanged from P1c)

The owner approved the design canvas "VideoEnhancer UI Redesign" (screens Home, Add videos, History, Schedule, Models, Compare). You cannot open it, so this part is the complete specification. Replace the P1b look and layout; keep every P1b capability unless this part removes it. The wireframes below show structure; follow the tokens and the rules in the text for the exact look.

### U0. Design tokens

| Token | Dark (default) | Use |
| --- | --- | --- |
| ground | `#0E1014` | window background |
| surface-1 | `#161920` | cards |
| surface-2 | `#1D212A` | buttons, selected nav item, inputs |
| placeholder | `#232833` | thumbnails while loading |
| border | `#22262F` | card borders |
| border-strong | `#2A2F3A` | button and input borders |
| text | `#ECEEF2` | main text |
| text-2 | `#C9CED8` | descriptions |
| text-3 | `#A0A8B6` | meta and captions |
| accent | `#5EEAD4` | primary buttons, progress, focus ring; text on accent is `#0E1014` |
| success | `#7EE2B8` | "Finished" |
| warning | `#F5B84B` | "Needs attention" |
| danger | `#F28B82` | destructive confirmations only |

- Light theme (System/Dark/Light setting stays): same structure with ground `#F6F7F9`, surface-1 `#FFFFFF`, surface-2 `#EEF0F4`, borders `#DDE1E8`/`#CDD2DB`, text `#14171C`/`#3A414D`/`#5A6372`, accent `#0F766E` with white text. All text at WCAG AA (4.5:1; 3:1 at 24 px and larger).
- Font: `Segoe UI Variable Text`, `Segoe UI`, system-ui. Page title 28 px / 650. The current job's percent 64 px / 650 with tabular numbers; finish time 20 px / 650; card titles 17 px / 650; body 14 px; meta 12 to 13 px.
- Radius: cards 18 px (the Now processing card 24 px), buttons 10 px, chips and filter pills fully round. Spacing on a 4 px grid; page padding 28 px top, 36 px sides; gaps 16 to 22 px.
- No gradients, no shadows beyond a subtle one on dialogs, no decorative animation. Icons are simple 1.8 px stroke icons (one icon set, for example Lucide). No emoji.
- Focus: 2 px accent ring with 2 px offset on every interactive element. Touch targets at least 36 px high (44 px for the main buttons).

### U1. Shell

```
+------+------------------------------------------------------------------+
| [VE] |  page                                                            |
|      |                                                                  |
| Home |                                                                  |
| Hist.|                                                                  |
| Sched|                                                                  |
| Model|                                                                  |
|      |                                                                  |
|  ⚙   |                                                                  |
+------+------------------------------------------------------------------+
```

- Left rail 88 px wide with a right border: a 40 px "VE" tile in accent, then Home, History, Schedule, Models (22 px icon above a 12 px label; item 72 px wide, 12 px radius; current page = surface-2 background and text color, others text-3). Settings is a gear button at the bottom of the rail. Home shows a small warning dot when something needs attention.
- Removed: the Plan page (its content moves to Schedule and to Home's "This week") and the bottom status strip (its content moves to the Home header chip).
- Dropping files anywhere in the window shows an overlay "Drop to add N videos" and opens the Add dialog.
- Minimum window 1100×700. Under 1280 px wide, the right column of Home and Schedule moves below the main column. Works at 125% and 150% scaling.
- Tray, single instance, Quit and Start with Windows behave as in P1b.

### U2. Home (replaces Queue)

```
| Home  (● Working · 15.7 fps · pauses at 08:00)            [Pause all] [+ Add videos] |
| +--------------------------------------------------+  +------------------------------+ |
| | +------+  Now processing                         |  | This week          Edit hours | |
| | |      |  evening_talk.mp4                       |  | Thu ██████████░░░░░   10 h    | |
| | | 9:16 |  720 × 1280 · 30 fps · 1:52:03 ·        |  | Fri ████░░░░░░░░░░░   3.7 h   | |
| | | thumb|  Standard → 1080p · 60 fps              |  | Sat                   off     | |
| | |      |  62%                 Segment 14 of 23   |  | Sun                   free    | |
| | |      |  ██████████████████░░░░░░░░░░░          |  | Everything finishes Fri 10/10| |
| | |      |  Finishes Thu 10/09 · 02:10   Work left |  | · 03:40                      | |
| | +------+                              8 h 15 m   |  +------------------------------+ |
| |           [Pause] [Preview result] [⋯]           |  | Recently finished All history| |
| +--------------------------------------------------+  | [t] cafe_vlog.mp4       Open | |
| Up next          2 videos · all done Fri 10/10 · 03:40 | [t] dance_clip.mp4      Open | |
| ⋮⋮ [t] beach_walk.mp4      0:12:40 · Fast      Starts Thu 22:00  Done Thu 23:10  [⋯] | |
| ⋮⋮ [t] live_stream_p2.mp4  0:45:10 · Standard  Starts Thu 23:10  Done Fri 03:40  [⋯] | |
| [ +  Drop videos anywhere in this window, or click to add ]   (dashed border)          |
```

- **Header chip** (round, surface-1, colored dot): "Working · 15.7 fps · pauses at 08:00", "Waiting for your hours · starts Thu 22:00", "Paused", "Finishing evening_talk.mp4", "Paused for a preview", "Idle · nothing to do", "Reconnecting…", or "Problem · details" (warning color; opens the engine error with Copy details). **Pause all** toggles to **Resume all**. **Add videos** is the primary button.
- **Now processing card** (the running job, or the next job when waiting): thumbnail in the video's own orientation (150×266 portrait, 266×150 landscape) from a new endpoint that returns a cached JPEG of the source at 10% of its duration; file name; one meta line; the percent (64 px) and "Segment k of N"; a 10 px progress bar; "Finishes" with a concrete date and time and "Work left" with the remaining work time. During finalization: "Finishing: assembling / checking" with its own step progress. When waiting for hours: "Starts Thu 22:00" in place of the finish time. Buttons: Pause/Resume; **Preview result** (enabled after the first finished segment: opens the Compare viewer with Original and the result for 5 s that are already processed; it must not use the GPU or disturb the job; CPU transcode to H.264 previews is fine); ⋯ menu: Cancel (confirm), Show log, Copy details, Open output folder.
- **Up next**: compact rows (min height 56 px): drag handle and keyboard reorder (Alt+Up/Down and a menu item), small thumbnail, name, duration · mode, "Starts …", "Done …". Row ⋯ menu: Move to top, Pause/Resume, Try models on this video (Compare), Change mode (only before the job starts), Remove (confirm), Show log, Copy details. A paused row says "Paused". A preparing row says "Preparing…".
- **Finished, failed and cancelled jobs leave Home at once** and appear in History. When there are failures the owner has not seen, Home shows a warning banner: "1 video needs attention · Open History". When the engine reports an error (`last_error`), Home shows a banner in plain English with Copy details.
- **Right column:** "This week": one row per day for the next 5 days, a bar of planned working hours (from the engine plan) and the hours text ("10 h", "off", "free"), a summary line, and "Edit hours" (to Schedule). "Recently finished": the last 3 History items with Open (plays the file in the default player) and "All history".
- Empty state: "Nothing in the queue. Add a video to see when it will be ready." with the Add button.

### U3. Add videos dialog

```
| Add 2 videos                                                              [x] |
| (beach_walk.mp4 · 0:12:40)  (live_stream_part2.mp4 · 0:45:10)                 |
| Choose a mode                                                                 |
| +----------------------------------+  +----------------------------------+   |
| | Standard                         |  | Fast                             |   |
| | Cleans up blockiness and noise,  |  | Only makes motion smoother and   |   |
| | then makes motion smoother.      |  | resizes. No cleanup.             |   |
| | Keeps the original look.         |  |                                  |   |
| | About 7 h of work                |  | About 1 h of work                |   |
| | Done Fri 10/10 · 03:40           |  | Done Thu 10/09 · 23:10           |   |
| +----------------------------------+  +----------------------------------+   |
| Output: 1080p · 60 fps · HEVC · Saved next to the original, in "enhanced"  More options |
| [Try models first]                                              [Add to queue] |
```

- Opens on Add, drop, or a click on the drop area; one dialog for several files. The two mode cards are large buttons (selected = 2 px accent border, `aria-pressed`); the default comes from Settings. The done time is 20 px / 650.
- Estimates fill in as each file finishes preparing ("Preparing…" until then); the dialog never blocks. Warnings (HDR, disk space with exact numbers, Smart App Control) appear as one line each above the buttons.
- **More options** reveals: Size (1080 recommended / Keep original / 1440 / 2160), Frame rate (Double recommended / Keep original), Cleanup model (installed restoration models; default the preset's model), File format (HEVC / H.264 / AV1 when supported), Output folder.
- **Try models first** opens Compare for the first file with the dialog's settings; returning keeps the dialog state; "Use this" in Compare sets the dialog's Cleanup model.
- Enter = Add to queue. From a drop to a queued job is one click.

### U4. History

- Header "History" and a search field ("Search by file name"). Filter pills with counts: All, Standard, Fast, Needs attention.
- Card grid (cards at least 240 px wide): thumbnail of the output (72×128 portrait or 128×72 landscape), name, when it ended ("Today 06:42", "Yesterday 23:18", "Mon 10/06 04:55"), "Standard · took 3 h 05 m · 412 MB", and a status line: Finished (success color), "Needs attention: the file could not be read" (warning color, one line), Cancelled (text-3).
- Actions: Finished → Play, Show in folder. Needs attention → Retry (re-queues from the last valid segment), Copy details. ⋯ menu → Compare again, Show log, Remove from history (confirm; never deletes the output).
- Footnote: "Finished and failed jobs move here automatically. Removing an item from History never deletes the video file."
- Engine additions: `finished_at`, `took_seconds` (wall time), output size and the thumbnail for done/failed/cancelled jobs, and a Retry endpoint (failed → queued, keeping valid segments).

### U5. Schedule (replaces Schedule and Plan)

```
| Schedule   Everything finishes Fri 10/10 · 03:40   (could be Thu 23:10 – Fri 06:00)  [● Only work during my hours] |
| (Weeknights 22:00–08:00 + weekends) (Every night 22:00–08:00) (While I'm at work 09:00–18:00) (Custom…)          |
| +-------------------------------------------------------------------+  +---------------------------+ |
| |               00      06      12      18      24                   |  | Exceptions                | |
| | Thu 10/09 today [▓▓▓▓▓▓░░░            |now          ░░▓▓]   10 h   |  | Sat 10/11   Off all day   | |
| | Fri 10/10       [▓▓▓░░░░                            ░░░░]   3.7 h  |  | Wed 10/15   13:00–18:00   | |
| | Sat 10/11       [                                       ]   off    |  | [Add a day]               | |
| | Sun 10/12       [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   free   |  +---------------------------+ |
| | Mon 10/13       [░░░░░░░                            ░░░░]   free   |  | Need it sooner?           | |
| | Tue 10/14       [░░░░░░░                            ░░░░]   free   |  | Ignore your hours and keep| |
| | Wed 10/15       [                  ░░░░░░░░             ]   free   |  | working. Everything would | |
| | ░ Allowed hours (drag the edges to change)   ▓ Planned work   | Now |  | finish Thu 10/09 · 23:10. | |
| +-------------------------------------------------------------------+  | [Run now until the queue  | |
|                                                                        |  is done]                 | |
|                                                                        | [Run now until a time…]   | |
```

- Seven rows, starting today. Each row is a 24 h track (rounded, surface-2): allowed hours as translucent accent blocks (about 22% opacity), planned work as solid accent bars from the engine plan (hover or focus shows "evening_talk.mp4 62% → 100%, done 02:10"), and a vertical "now" line on today. The note on the right: planned hours, "free" (allowed, nothing planned) or "off".
- Editing: drag a block's edges in 15-minute steps with a live time label, drag its middle to move it, click an empty part of a track to add a 2 h block there, and remove a block with its × or the Delete key. Editing a weekday row changes that weekday's weekly rule (the row label shows "Every Thu" while editing); a block's menu offers "Only on Thu 10/09" to make it a date exception instead. Keyboard: arrow keys move a focused edge by 15 minutes.
- Quick choices replace the weekly rule (with Undo). **Custom…** opens the exact-time list editor from P1b.
- Changes save automatically 600 ms after the last edit, with a toast "Saved · Undo" for 8 s. Validation messages appear in plain English next to the block. The header finish time updates live while dragging (schedule preview, throttled).
- Switch off = always allowed; the tracks show full-day allowed blocks and the note "Working any time".
- Exceptions card: upcoming dates with "Off all day" or hours, edit and delete; **Add a day** opens a date picker with Off or hours.
- Need it sooner card: shows the finish time the override would give. Buttons: "Run now until the queue is done" (add an override value for the whole queue, for example `until='queue-complete'`) and "Run now until a time…" (time picker). With an active override the card shows "Working now until 18:00 · Stop".
- The header range "could be … – …" comes from the plan's best and worst scenarios.

### U6. Models and U7. Compare

See Part M and Part C. Both use the shell, tokens and card style above.

### U8. Settings (gear at the bottom of the rail)

Same content as the P1b Settings page in the new style, grouped as: Defaults (mode, size, frame rate, file format, output folder), App (Start with Windows, theme), Advanced (behind a disclosure), Diagnostics (Copy diagnostics, log folder with Open, Run speed calibration), About (version, licence notes including non-commercial models).

### U9. Words

English, short, no jargon on the main screens. Times are always concrete ("Done Thu 23:10", "8 h 15 m"), never only a percent. Use "mode" (Standard / Fast), "cleanup", "smoother motion", "your hours".

