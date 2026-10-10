# VE-P1c-2 implementation report

- Task ID / Cycle: VE-P1c-2
- Date: 2026-10-10
- Status: **PARTIAL**. D and the CPU-tested S/W implementation are delivered; U is partially implemented. M and C were not reached. This is not completed P1c acceptance.
- Branch: `p1c-redesign`; draft PR [#4](https://github.com/Kei-Takamizawa/VideoEnhancer/pull/4). No merge or main push.
- Initial worktree was clean; fetched origin. Saved the full instruction byte-for-byte and committed it as `a4bd555`. Task SHA-256: `e0ee7d61f5bdc5807a1cc00d3673bf7382e1a51bc50c778a70da877f66020609`.
- All execution used synthetic footage and separate homes. The owner's queue was not modified. Existing verified C1/RIFE assets were copied read-only into the isolated GPU home.

## Implementation by part

### D: source index and range analysis

Added demux-only indexing with matching job-manifest precedence, path/size/mtime cache identity, atomic writes and a 1 GB oldest-first limit. Kept existing packet parsing rather than introducing a new combined interpretation. Metadata probing itself reads a timeline, so a fresh index currently makes three demux passes in total. It does not decode the whole source.

Trials analyze the required source span and two-second/temporal-context margin with unchanged cut scoring, absolute indices and CFR mapping. CPU seeks from the preceding keyframe; CUDA uses indexed SimpleDecoder frames. Count mismatches/decoder errors log why and fall back to full analysis. Full-job analysis is unchanged. Reading progress is coarse demux milestones (0/33/67/100%), not packet/byte progress.

Operation progress is persisted and displayed. Trial preflight avoids an extra timeline scan when existing metadata suffices. The child reads the job manifest directly instead of embedding large timestamp arrays in operation/SSE snapshots.

### S: reliability

- Live frame counts reduce active-step remaining work and forecast finish times in queue, plan and schedule preview.
- Three actual five-second manifest-lock timeouts write lock-free atomic quarantine. Other jobs continue. Retry reacquires the lock, removes quarantine and retains done segments.
- Planner/controller share admission rules, including the oversized-step opening-window exception and safety reserve. Later jobs can run when an earlier next step does not fit. Active work outside hours remains forecast; overruns have durations/captions.
- A test-only constructor flag creates a genuinely stuck trial child. A five-second injected deadline kills its process tree and returns the exact timeout message. Normal runs retain production deadlines; request data cannot enable this injection.
- Added failed-job Retry and queue-complete override endpoints; the older job-complete override remains supported.

### W: windowless executable

Electron selects the Windows sibling pythonw, preserves configured pythonw, and logs fallback to hidden console Python only when the sibling is absent. Service/segment logs record the executable. A real pythonw parent with None stdout/stderr ran an actual CPU segment child successfully. CLI output behavior was unchanged.

This does not establish no visible flash in every production flow. A4 is unverified. The executable choice follows [Node's documented detached Windows child behavior](https://nodejs.org/api/child_process.html).

### U: delivered subset

- New dark/light tokens, 88 px icon rail, Home default, History and bottom Settings; removed runtime Queue/Plan navigation and status footer.
- Home current progress, work left, finish/start, overruns, thumbnails, next-job ordering/actions, attention banner, five-day summary and recent outputs.
- Authenticated cached JPEGs preserve source/output orientation; done jobs use output thumbnails.
- Preview result CPU-encodes a durable segment/final output comparison without rerunning restoration or taking the GPU lease.
- Add has Standard/Fast cards, incremental estimates, More options, installed cleanup choices and retained dialog state across the existing Trial viewer.
- History filters/search, terminal cards, wall-time/size metadata, Play/folder/Retry/diagnostics and confirmed removal retaining the output.
- Schedule has seven dated tracks, presets, edge/middle drag, empty-track add, Delete/arrows, 600 ms autosave, eight-second Undo, exact Custom editor, exceptions and queue/time overrides. Preview throttle: 150 ms.
- Settings retains its controls and About information with new tokens; exact grouping is unfinished.

U is incomplete. Models remains the existing table and the comparison has two streams. README and GUI/API/Adding Models/Troubleshooting now describe delivered behavior and missing catalog/Compare scope.

### M and C

NOT RUN. No additional catalog entries, unverified download/licence metadata, model-default changes or multi-model comparison were shipped. Existing default pipeline retained.

## D2 fixture results

| Fixture | CPU start / middle / end | CUDA start / middle / end |
| --- | --- | --- |
| CFR | PASS / PASS / PASS | PASS / PASS / PASS |
| Irregular VFR | PASS / PASS / PASS | PASS / PASS / PASS |
| B-frames | PASS / PASS / PASS | PASS / PASS / PASS |
| Trailing short frame | PASS / PASS / PASS | PASS / PASS / PASS |

Each case checks index/media equality, range cut equality and byte-identical paired trial outputs. Fixtures use the existing placeholder model to isolate mapping/render equivalence. CUDA images are 256x256: initial 96x64 fixtures failed NVENC initialization. Real Standard weights were separately tested below. Injected short-count fallback and cache/manifest precedence/invalidation/eviction tests passed. No natural fixture mismatch occurred.

## Long-source GPU measurements

RTX 4060 Ti; synthetic portrait 720x1280, 30 fps H.264 on local disk. A repeated five-second source was stream-copied to long durations; measured bitrate approximately 3.39 Mbps. These are synthetic results, not measurements of an owner video.

| Duration | Frames | Bytes | Fresh index | Cached index |
| --- | ---: | ---: | ---: | ---: |
| 30 min | 54,000 | 762,967,458 | 2.626 s | 0.0165 s |
| 2 h | 216,000 | 3,051,867,318 | 10.061 s | 0.0485 s |

Real five-second Standard trial at the two-hour source's middle, C1 BasicVSR++ plus RIFE, 1080x1920 output:

- Index lookup 0.0464 s; range scene analysis 1.7918 s.
- Start to first frame written to the encoder: 15.7754 s.
- Combined input throughput: 1.9028 fps; not an individual-model speed.
- Whole-file-analysis Standard trial produced matching decoded-frame hashes for both previews. SHA-256 of FFmpeg frame-MD5 reports: Original `e87f30e2d7a38471e948430982779d497c531bcbf0c2202e97a29b853f2ed495`; Enhanced `009eeab614976e075c8a217b6d6d382d8964f18e384ac493fb507e1d3b660a05`.
- Maximum observed same-PID dedicated plus shared GPU sample: 4,791,087,104 bytes, PID 13604. Approximately 30-second samples are not a true peak or proof of the strict process-total 5 GB limit. Missing counters were not zeroed; no cross-PID growth conclusion.

## Executed builds and tests

| Check | Result |
| --- | --- |
| ruff check / format check | PASS; 94 formatted files |
| pyright | PASS; 0 errors / warnings |
| Full CPU pytest, not gpu/not soak | PASS: 232 passed, 3 skipped, 30 deselected, 284.86 s on the final engine revision |
| New reliability tests, including real lock, stuck child, pythonw, result preview, Retry/override | PASS: 8 passed, 33.66 s |
| GPU D2 | PASS: 12 passed, 14 deselected, 99.95 s |
| Real long-source GPU trial/hash checks | PASS as qualified above |
| GUI lint / typecheck | PASS |
| GUI unit tests | PASS: 19 tests, 4 files |
| GUI build | PASS; approximately 462.41 kB JS / 14.45 kB CSS |
| GUI package | PASS; unsigned Windows x64 folder |
| Electron e2e plus generated-package smoke | PASS: 2 passed, 2 opt-in GPU skipped, 19.7 s |
| Final desktop screenshot-capture rerun | PASS: 1 passed, 17.2 s; physical zoom capture waits for renderer paint |
| Final-revision Windows/Ubuntu remote CI | NOT RUN / unconfirmed before push |
| Native manual Computer Use / exhaustive physical flash check | NOT RUN; actual Electron automation used Playwright |

New components cover active/terminal separation and preview readiness, History search/quarantine/Retry, and Schedule keyboard preview/autosave/Undo/override. This is incomplete A5 interaction coverage.

## GUI operations, expected and actual

Actual Electron launched a real service in an isolated home, added two-second synthetic footage, observed completion in History, visited all five available pages, saved both themes, resized, closed/reopened the window and requested Quit. A request fixture selected existing CPU passthrough because that home has no restoration weights.

Expected: output finishes, service survives window close, no renderer page exceptions, renderer isolation enabled, Quit removes discovery state. Actual: all these assertions PASS. The very short CPU job's visible Now processing interval is not asserted; its component state is tested. GPU moving-progress acceptance is outstanding.

Captured five available pages and Add at logical content sizes 1280x800 and 1100x700, both themes, plus 125%/150% renderer zoom. Windows display scaling is 125%, so PNG pixels exceed logical dimensions. Long pages scroll vertically. The legacy Models table scrolls internally horizontally at 150%; its catalog redesign is pending.

## A1–A9 acceptance

| Criterion | Status | Evidence / missing work |
| --- | --- | --- |
| A1 | PASS for executed synthetic checks | 24 fixture/range cases, fallback/cache and real Standard long-source hashes; source qualifications above |
| A2 | NOT RUN in full | CPU reliability PASS; GPU Standard percent/Work left within 30 s not recorded |
| A3 | NOT RUN | Three-job Standard/Fast/Standard queue and in-job/outside-hours GPU trials absent |
| A4 | NOT RUN | Pythonw selection/real CPU child PASS; all-flow physical flash observation absent |
| A5 | NOT RUN in full | Partial U, components and CPU Electron test; missing interactions below |
| A6 | NOT RUN | Catalog and per-model budget/speed/licence verification absent |
| A7 | NOT RUN | Three-model GPU Compare / 100 seeks / 300 played-frame synchronization absent |
| A8 | NOT RUN in full | Local matrix results above; fresh Windows/Ubuntu remote CI unconfirmed |
| A9 | NOT RUN in full | Available pages/Add captured; requested catalog/Compare screens do not exist |

## Catalog measurements / omissions

No catalog-specific FPS/true-peak metadata added. All 14 requested table entries remain pending as catalog entries: Gentle cleanup; Cleanup other training; Crisper cleanup; Grain and noise calmer; Adjustable deblock (three strengths); All-round cleaner; Picture deblock; H.264 remover community; Smooth motion; Smooth motion newest; Smooth motion faster; Standard resize; Faithful 2x enlarger; Sharper detail.

C1, RIFE 4.25 and non-learned resize remain in the original pipeline. Do not assign the combined Standard measurement to a model. Other entries were not evaluated or rejected as incompatible: their implementation/verification was not reached. No new weights were installed in the owner's home.

## Unresolved items / exact reproduction

1. U2: Open an unstarted job menu: Change mode is absent. Problem chip copies diagnostics instead of opening details. Open Home with failed jobs: banners/dots do not track already viewed failures.
2. U3/C: Open Add then Try models first: output summary line and Compare Use this are absent; existing two-stream Trial opens. Add remains available during initial Preparing, with server validation.
3. U4: Open History: existing concrete-date formatter is used instead of Today/Yesterday wording; terminal menu says Try models on this video instead of Compare again. Retry now has its own failed-job endpoint.
4. U5: Open Schedule: best/worst header range and percentage tooltip absent; direct exception edit requires Custom. Only on date is a row button rather than block menu. Rows may scroll. A successive save does not restart an already visible toast's timer. Full drag/add/delete/exception test coverage remains.
5. U8: Open Settings: some P1b grouping/order remains; About is present.
6. Preview result: closing its dialog does not cancel CPU encoding; its renderer does not consume the generic cancel flag. Quit during preview and source/output finalization races have not been explicitly tested. Part C's last-five/2 GB preview-cache contract is not implemented.
7. M/C: Category cards, defaults snapshots, learned size-stage selection, multi-model render/cache, four-stream pan/swipe viewer and synchronization suite absent. Current Models/Trial must not be treated as those features.
8. Owner acceptance: A2/A3/A4/A6/A7 and opt-in GPU/resume Electron tests not executed. Their selectors were updated for the shell; GPU execution remains unverified.

## Errors / warnings

Corrected initial test failures: expecting packet durations in a manifest that omits them; unsupported 96x64 NVENC geometry; missing persisted pythonw test manifest; wrong fake-clock window; old planner A-before-B expectation conflicting with shared admission; PID-exit race requiring bounded wait; Retry test passed route string instead of path parts; GUI fixture omitted required step_percent. Reran affected tests without changing product design to bypass failures.

Windows default pytest temp access was denied; fresh ignored basetemp folders used. A whole-upstream-source copy hit Windows long paths; isolated home instead received required verified model folders/adapter archives only. Playwright warns NO_COLOR is ignored with FORCE_COLOR. Git warns of configured LF-to-CRLF conversion. Extra documentation EOF whitespace was removed; diff check passes.

## Logs / evidence / reproduction

Ignored logs under `.tmp/p1c2/`: `full-cpu-release.log`, `reliability-final2.log`, `gpu-d2-sized.log`, `long-index.log`, `e2e-final.log`, `desktop-capture-final.log`; earlier failing/diagnostic runs retained there.

External root: `C:\Users\pro\.codex\visualizations\2026\10\09\01a12000-750a-7813-9ea1-6bc265708fb5`.

- `p1c2-long-bench/measurements.json`: exact timings/hashes; synthetic videos/previews external.
- `p1c2-e2e/<home|history|schedule|models|settings|add>-<dark|light>-<1280x800|1100x700>.png`.
- `p1c2-e2e/settings-125-percent.png`, `settings-150-percent.png`.

Reproduce equivalence: `pytest -q tests/test_source_index.py -m "not gpu"` and `pytest -q tests/test_source_index.py -m gpu`. Reliability: `pytest -q tests/test_p1c2_reliability.py`. Full CPU: `pytest -q -m "not gpu and not soak"`. Use fresh basetemp and isolated VE_HOME.

In gui, run lint/typecheck/test/build/package; set VE_GUI_PACKAGE_EXE to the generated Windows executable and VE_GUI_EVIDENCE to an external folder, then `npm run test:e2e`. No GPU opt-in home variables were set in the recorded e2e run.

## Changed files

- `.ai/CURRENT_TASK.md`, `.ai/LAST_REPORT.md`.
- Under src/videoenhancer: media/source_index.py, media/probe.py, trial.py, estimate/model.py, jobs/store.py, schedule/admission.py, controller.py, planner.py, windows.py, service/engine.py, operation.py, preview.py, server.py.
- gui/electron: main.cjs, python.cjs, preload.cjs. gui/src: App.tsx, Home.tsx, ScheduleView.tsx, Pages.tsx, Queue.tsx, style.css, types.ts.
- tests: test_source_index.py, test_p1c2_reliability.py, test_planner.py. gui/tests: home-schedule.test.tsx, python.test.tsx, setup.ts, four e2e specs.
- README.md, docs/GUI.md, API.md, ADDING_MODELS.md, TROUBLESHOOTING.md.

## Questions for the designer

No new design decision blocks delivered D/S/W. Unfinished U/M/C follow the existing task; they were not independently redesigned. Safe current behavior retains original defaults/two-stream Trial and omits unverified entries. This partial report does not claim the remaining work is blocked.

## Intentionally not executed / Git handoff

No subagents, owner-queue jobs, main push, merge, history rewrite, private-media publication, weight/build-artifact commit. Long GPU queue/catalog/sync/flash checks and fresh remote CI not executed. Stop after committing only task work and verifying branch push; no next cycle afterward.

Implementation/report commit and push verification are pending when the report is prepared. Final chat will state the verified SHA/outcome.
