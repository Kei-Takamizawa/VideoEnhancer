# VE-P1c-3 implementation report

- Task ID / Cycle: VE-P1c-3
- Date: 2026-10-10 JST; timestamps below explicitly use UTC or UTC-07.
- Status: **PARTIAL**. U-rest, catalog controls, comparison engine/viewer and substantial GPU acceptance are delivered. Optional publisher models, DRUNet, learned size and several Compare interactions remain incomplete. This is not completed P1c acceptance.
- Branch: p1c-redesign; draft [PR #4](https://github.com/Kei-Takamizawa/VideoEnhancer/pull/4).
- Initial clean HEAD: 9ff4bb0fd3ff263c9cfc182da40e450151a3696e; fetched origin.
- Full instructions committed as edef0aa; CURRENT_TASK SHA-256: 079ccd1e83a37d25429285873a0bc4a133e6c4733478cbd8f73b3f0a05a1da36.
- Synthetic footage and isolated homes only; copied verified weights. No owner queue edits, subagents, merge, main push, media, weights or build artifacts in Git.

## Implemented

**U-rest:** Change mode re-estimates prepared, unstarted jobs without altering their frame partition. Preparing rows wait. Problem opens details before Copy. Seen failures persist and accumulate; actual History-card visibility or banner dismissal acknowledges them. Add has output summary and installed cleanup/motion choices. Compare Use this updates the still-open Add dialog. History has relative dates and Compare again; removal preserves output.

Schedule has best/worst bounds, progress/finish tooltips, block context menus, direct exception edits and Add a day. Multiple exception windows are retained/editable. Every save restarts the eight-second Undo timer; Undo restores the preceding saved schedule. Settings uses Defaults, App, Advanced, Diagnostics, About. Closing Preview result or quitting cancels real CPU encoding, removes partial files and preserves durable output; the next preview uses a fresh operation id. Both cases were tested.

**M foundation:** validated catalog blocks for existing C1/RIFE, category cards, explicit licence consent, verification, Details, new-job defaults and guarded removal. Built-in removal deletes weights while retaining its card. Queue use also protects CLI removal. Defaults are captured before preparation; Fast does not inherit cleanup. Catalog metadata is excluded from the resumable identity hash. Unknown speed says “Not measured here”; no paper speeds or unsupported memory peaks were published.

**C foundation:** POST compare accepts up to three installed models of one category. It renders Original once, shares one index/range analysis, publishes individual previews progressively, reports measured fps/projected time, uses the between-segment lease and runs outside hours. Required missing weights are refused before admission. Trial API remains. Completed sessions retain at most five/2 GB, oldest first; job previews are removed with the job.

Compare opens from Models, Add, queue menus and History. It has category chips, licence consent, side-by-side/swipe, Left/Right, zoom, common panning, arrow steps, Space, Loop, captions, Use this and defaults. Started jobs cannot adopt another model. Four WebCodecs streams draw only matching actual decoded indexes; landscapes use 2x2 and portraits a row.

Still missing: draggable thumbnail box, automatic range/selection rerender, reuse of only missing rendered models, install-then-auto-select, learned size comparisons and a measured three-different-model GPU comparison. Fast cleanup is disabled to retain its specified no-cleanup behavior.

## Acceptance

| Criterion | Status | Evidence / limitation |
| --- | --- | --- |
| A2 / G1 | PASS | Standard percent and Work left moved within 13.97 s of segment start. |
| A3 / G2 | PARTIAL | All three jobs and both Trials finished. Jobs moved within 13.98 s. Continuous Trial percent history was not retained; complete no-zero-for-60-s condition is not claimed. |
| A4 / G3 | PASS automated | Final packaged cold start, install, Standard, Fast, Trial, Compare, Quit: 935 polls / 93.5 s, no unexpected visible windows. Owner visual confirmation NOT RUN. |
| A5 | PARTIAL | U-rest checks and real Add -> Now processing -> Finished -> History passed. Remaining Compare interactions prevent complete Part U acceptance. |
| A6 / M | NOT RUN qualification | Optional entries and required reference measurements omitted. |
| A7 / C | PARTIAL | Four synthetic streams: 100 random seeks, 300 observed played frames, 0 mismatches. Real single-model GPU Compare passed; three different GPU models NOT RUN. |
| A8 | PARTIAL pending CI | Local checks passed below; confirm Windows/Ubuntu after push. |
| A9 | PASS capture set | All seven screens, both sizes/themes, 125/150% scaling; synthetic Compare fixtures do not prove model performance. |

## Catalog models and omissions

| Entry | Result |
| --- | --- |
| Gentle cleanup / C1 | Existing default retained; real Standard jobs and single-model GPU Compare passed. No qualifying 5 s 720x1280 catalog compare/true process peak; reference_speed omitted. |
| Smooth motion / RIFE 4.25 | Existing default retained; real Fast jobs/Trial passed. Qualifying catalog reference measurement NOT RUN; reference_speed omitted. |
| Standard resize | Existing non-learned default retained; no download. |
| Track 1; Track 2; denoise | NOT RUN: download/hash, adapter load and qualifying GPU measurements incomplete; all omitted. |
| DRUNet Light / Medium / Strong | NOT RUN: wrapper and qualifications incomplete; three choices omitted. |
| SCUNet; FBCNN; 1xDeH264_realplksr | NOT RUN: complete adapter/load/hash/GPU qualification not performed this cycle; omitted. |
| RIFE 4.26 / 4.25 lite | NOT RUN: archive handling and compatibility with pinned adapter unvalidated; omitted. |
| SPAN; realesr-general-x4v3 blend | NOT RUN: learned size stage/blend and qualifications incomplete; omitted. |

These are uncompleted qualifications, not measured failures or claims that these models cannot work.
Publisher references checked: [Practical-RIFE](https://github.com/hzwer/Practical-RIFE), [OpenMMLab](https://github.com/open-mmlab/mmagic/tree/main/configs/basicvsr_pp), [KAIR](https://github.com/cszn/KAIR). RIFE explicitly describes linked weights as MIT; C1's separate weight terms remain unstated.

## GPU measurements

RTX 4060 Ti 8 GB. G2: 720x1280, 30 fps -> 1080x1920, 60 fps HEVC, lossless off, fresh p1c3-gpu/home. Started early while GPU idle. Its parent started before later catalog/GUI edits; final service/GUI also received a separate packaged GPU-flow run.

| Sequential job | Wall seconds | First positive from job start | Segment pipeline fps |
| --- | ---: | ---: | ---: |
| Standard 30 s | 486.226323 | 13.976405 | 2.164–2.289 |
| Fast 30 s | 66.960090 | 7.989191 | 12.206–15.274 |
| Standard 120 s | 1627.737630 | 13.666378 | 2.231–2.300 |

Standard 30 s wall time includes the admitted between-segment Trial. Entire run including both Trials: **2255.578 s**. Both Trials finished, with pipeline fps 2.076887 and 2.079695. Outside-hours schedule was enabled with no allowed windows.

G1 segment-start log: 2026-10-10T10:40:49.602480+00:00 (JST 19:40:49.602480).
First positive: 2026-10-10T10:41:03.575376+00:00 (JST 19:41:03.575376):
**1.444444%**, Work left **536.961187 s**, difference **13.972896 s**.

Observed maximum same-record dedicated+shared process GPU memory: **4,805,832,704 bytes / 4.805833 GB**. Samples every 30 s, per PID and record. This is an observed sample maximum, **not a true peak**, cross-restart growth, or proof of the strict catalog 5 GB budget. Device-wide NVML usage was not treated as per-process memory.

## Executed builds and tests

| Check | Result |
| --- | --- |
| ruff check . / format --check . | PASS; 98 files formatted |
| pyright | PASS; 0 errors / warnings |
| CPU suite, excluding gpu/soak | PASS; 241 passed, 3 skipped, 30 deselected; 309.61 s |
| Service/preview/compare subset | PASS; 19 tests, 39.38 s |
| Final mode/consent/compare subset | PASS; 9 tests, 22.67 s |
| D2 CPU and CUDA | PASS; 26 tests, 189.50 s |
| GUI lint / typecheck | PASS |
| GUI component tests | PASS; 27 tests, 5 files |
| GUI build / unsigned x64 package | PASS; isolated external package |
| Electron CPU e2e + packaged smoke | PASS; latest desktop 59.4 s, smoke 2.5 s |
| Four-stream sync | PASS; 100 random seeks, 300 played frames, 0 decoded-index mismatches |
| G3 packaged GPU/window flows | PASS final fixed-period run; 935 polls / 93.5 s; 0 extra windows |
| C1/RIFE strict legacy tensor equality | PASS; 2 tests / 31 deselected, 7.50 s; isolated copied home |

GUI automation used real Electron/Playwright, not native manual Computer Use. Owner visual acceptance remains NOT RUN. No unexecuted test is reported successful.

## G3 window evidence

Final fixed-period full-flow run: **935 polls / 93.5 s**, 100 ms deadlines, **0 unexpected visible windows**. Exact BrowserWindow native handles are excluded, including Electron child-owned app windows. ConsoleWindowClass, CASCADIA_HOSTING_WINDOW_CLASS and other app-tree windows are monitored. Sub-interval flashes cannot be excluded. Evidence: p1c3-gui/windows-flows-1791631844871/windows.json and flows.json.

## Evidence and reproduction

External root: C:\Users\pro\.codex\visualizations\2026\10\09\01a12000-750a-7813-9ea1-6bc265708fb5

- p1c3-gpu/result.json, progress.json, acceptance-summary.json and home/jobs/*/job.jsonl: G1/G2.
- p1c3-gui/{home,history,schedule,models,settings,add,compare}-{dark,light}-{1280x800,1100x700}.png: screen matrix.
- p1c3-gui/now-processing-synthetic.png, settings-{125,150}-percent.png, four-stream-sync.json.
- p1c3-gui/windows-flows-*/windows.json, flows.json, gpu-compare.png: per-attempt G3. Only completed successful attempts count.
- p1c3-package/VideoEnhancer-win32-x64/VideoEnhancer.exe: unsigned package, external engine.
- Local check logs: .tmp/p1c3/ (ignored).

CPU: use fresh basetemp and pytest -m "not gpu and not soak". D2: pytest tests/test_source_index.py.
Screenshots/sync: build and npm run test:e2e -- desktop with external VE_GUI_EVIDENCE.
G3: fresh copied verified models/adapters; retain C1's verified legacy copy and remove only that home's installed C1 weights. Set VE_GUI_WINDOWS_FLOWS_HOME, VE_GUI_PACKAGE_EXE and VE_GUI_EVIDENCE; run npm run test:e2e -- windows-flows. Never use the owner home.

## Errors / warnings and resolution

- Initial Electron launch collided with owner single-instance lock. Tests now use isolated --user-data-dir; owner app was not quit.
- Default packaging failed EBUSY because the old package was open. Rebuilt with VE_GUI_PACKAGE_OUT outside Git. Old app.asar remained present; no owner process was killed.
- Corrected unsupported testing-library exact option, Windows drawtext font selection, and outdated built-in removal expectations; subsequent checks passed.
- Unfiltered registry invocation selected GPU tests against default home and failed source-path protection before loading. Isolated final GPU rerun is recorded separately; no production result inferred from the failure.
- First G3 lacked discovery readiness; second reused an output name. Fixed readiness and distinct synthetic names, then completed the full-flow run. Failed attempts do not count as successful G3.
- npm NO_COLOR/FORCE_COLOR and Git LF/CRLF notices only.

## Questions for the designer / unresolved work

1. Optional model qualification, DRUNet and learned size remain unfinished. Chosen default: omit unqualified entries, preserve existing outputs.
2. Thumbnail-box dragging, automatic rerender, missing-only reuse and install-then-select remain unfinished. Chosen default: explicit render button, middle fallback, full selected-model rerender.
3. Fast has no cleanup stage to replace. Chosen default: disable cleanup comparison in Fast; please confirm.
4. Trial percent history was not retained for G2. Chosen default: report completions/job timing, do not claim the full no-zero criterion.
5. Four synthetic decoded streams are transport evidence, not three qualified publisher models.

Intentionally NOT RUN: optional-model downloads/benchmarks, true process peak instrumentation, private footage, owner queue work, owner visual confirmation, signing/installer, merge, next-cycle improvements.

## Changed files

- .ai/CURRENT_TASK.md, .ai/LAST_REPORT.md; README.md.
- docs/API.md, GUI.md, ADDING_MODELS.md, TROUBLESHOOTING.md.
- GUI src/App.tsx, Home.tsx, Pages.tsx, Queue.tsx, ScheduleView.tsx, Trial.tsx, style.css, types.ts; scripts/package.mjs.
- GUI tests/add-models.test.tsx, home-schedule.test.tsx, pages.test.tsx; e2e/desktop.spec.ts, gpu.spec.ts, packaged.spec.ts, windows-flows.spec.ts.
- src/videoenhancer/jobs/store.py; models/registry.py and both built-in manifests; proc.py; schedule/planner.py.
- src/videoenhancer/service/compare.py, engine.py, operation.py, preview.py, server.py, settings.py.
- scripts/window_monitor.py; tests/test_p1c3.py, test_compare.py, test_model_registry.py.

## CI / Git

Implementation commit/push and Windows/Ubuntu CI pending at initial report writing.
Update with verified run before ending. A final report-only commit receives another CI run; confirm final HEAD after push and provide its run URL to the owner. Do not merge or push main.
