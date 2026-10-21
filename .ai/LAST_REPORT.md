# VE-P1f-2 review fixes

Status: COMPLETED — implementation, local acceptance, packaging and cleanup.
Final-head CI is the post-push delivery gate: its actual run outcome is recorded on PR #7 and in the closing response, after this report is committed.
Cycle: VE-P1f-2, 2026-10-19. Start: 05dbf72bebef3fd24929dae2ea6131c6fdd7a51f.
Branch: p1f-links. Existing draft [PR #7](https://github.com/Kei-Takamizawa/VideoEnhancer/pull/7), base p1t-tauri.
Private evidence: D:\my-workspace\VideoEnhancer\work\evidence\P1f-2.
No owner queue, media, model installation, AppData, VE-check or Recycle Bin was used.

## Changes and item-by-item evidence

The baseline archive was extracted from Git 05dbf72 and imported from its own
absolute src path. review-isolated-05dbf72-actual.log reports 30 FAIL / 6 PASS.
The six passes include five pre-existing invalid chunk rejections and the
pre-existing all-formats estimate case; they do not establish the positive
chunk preservation behavior. Earlier source-replay and GUI/Rust baseline logs
remain available. review-isolated-05dbf72.log accidentally tested current code
after archive extraction failed: INVALID as baseline evidence.

| Item | Status / implementation | Failing baseline or permitted alternative | After / evidence |
| --- | --- | --- | --- |
| P2 | Done / PASS, exactly one five-launch measurement | Historical P1f Home-ready 694.6 ms vs Electron 420.9 ms remains FAIL. Relative gate retired by designer. | Home-ready median 718.287 ms <=765; first paint median 720.128 ms <=1000. p2-five-launches.json; all five processes/children exited. |
| A1 | Done: null unknown media, legacy zero interpretation, pre-analysis link rows, per-record isolation/log once; bad JSON uses whole-folder staging plus 10-second Undo. | test_a1_legacy_placeholders_and_bad_record_isolation, test_a1_bad_projection_or_json_keeps_other_rows_and_safe_removal and GUI History zero-width baseline FAIL. | test_a1_unknown_media_snapshots; real HTTP R2 refusal retains file and GET queue 200 (http-r2.log); unreadable-tests6.log 42 PASS. Raw invalid JSON and invalid UTF-8: byte-identical Undo, expiry, startup cleanup, outside video untouched, file-choice refusal, parse/path details. |
| A2 | Done: abort missing fragments; compare known duration, keep incomplete file. | test_a2_fragment_abort_flag and test_a2_incomplete_duration_is_kept_and_refused FAIL. | real-hls2.log 2 PASS: once-failed middle segment retries to complete 180 frames; persistent HTTP 500 exhausts four attempts. Unit duration test PASS. |
| A3 | Done: exact unfinished job MKV removed before each attempt. | test_a3_partial_remux_removed_before_attempt FAIL. | real-remux.log 1 PASS: actual FFmpeg remux suspended/killed, resumed to complete 240-frame file. |
| B1 | Done: entry URL plus --no-playlist, identity still checked. | test_b1_entry_rechecked_once FAIL. | real-playlist.log PASS: three real local direct-file checks embedded in playlist fixture; three single-video checks and three transfers, no whole-playlist recheck. |
| B2 | Done: nested/missing-URL cards have plain reasons. | test_b2_nested_or_missing_url_gets_plain_reason FAIL. | Unit and actual GUI nested-list card PASS. |
| B3 | Done: only exact HTTP-whitelist failure gets encryption refusal. | test_b3_non_http_whitelist_failure_falls_back FAIL. | real-tls2.log PASS: AES-128 HLS crypto failure follows fallback. Proxy whitelist unit PASS. |
| B4 | Done: format and fragment URL/path/base encryption checks, including relative URL resolution. | test_b4_http_fragments_refused FAIL. | real-tls2.log PASS: HTTPS metadata with HTTP MPD fragments refused before transfer. |
| B5 | Done: storage_busy excludes storage mutations; storage_moving alone disconnects engine commands until recovery finishes. | b5-baseline-actual.log: old connected condition fails connected().is_ok(). | Rust 20 PASS; real GUI video/play/seek and shared tray Quit handler during long verification/removal PASS, gui-e2e-final.log and storage screenshots. Physical tray click NOT RUN. |
| B6 | Done: queue and transfer reserve work/output/download/remux space with one 10% margin per volume. | test_b6_queue_checks_working_space and same-drive boundary FAIL. | Unit insufficient output disk PASS; output 1000 B/download 500 B: 4399 B fails, 4400 B passes. Unknown download sizes cannot be reserved exactly. |
| B7 | Done: hardware/profile cache, shared engine hardware data, job profiles, changed-entry-only estimate requests. | test_b7_estimates_do_not_reprobe_hardware FAIL; old LinkPanel request test FAIL. | b7-process-starts.json: 20 jobs, first 60 s actual starts 1137 -> 0; GUI unit request isolation PASS. |
| B8 | Done: --cache-dir inside engine home/tools/yt-dlp/cache. | test_b8_cache_is_inside_engine_home FAIL. | Real 99-test bundle PASS; USERPROFILE/.cache/yt-dlp before/after files 0/0, new/changed 0/0 (b8-profile-cache-guard.json). |
| B9 | Done: reuse selected initially; Download again remains available. | Old LinkPanel default-reuse unit FAIL. | LinkPanel unit and actual GUI both themes PASS. |
| B10 | Done: preserve only positive integer http_chunk_size, excluding bool. | test_b10_preserves_only_positive_chunk_size FAIL; invalid values already rejected. | Positive preservation and five invalid-value cases PASS. Real YouTube NOT RUN (prohibited). |
| B11 | Done by permitted measurement; no decoder/pipeline change. | Second decode observed directly, no defect claim requiring behavior change. | 10-minute synthetic 1080p30, 18000 frames: NVDEC verification 16.034 s; second thumbnail decode 17.416 s; full analysis 40.701 s, b11-analysis-time.json. |
| B12 | Not reproduced; no HEVC playback code change. | Same existing codec support code tested after owner's extension installation. | HEVC Video Extensions 2.5.48.0; actual packaged M1 playback/seek PASS at 1080 and 1440, b12-hevc-playback.json. |
| B13 | Done: HTTP only for original HTTP, public IP validation for every redirect and pinned public address connection to prevent DNS rebind. | Private thumbnail and redirect tests FAIL. | Loopback/private/redirect/rebind refusal tests PASS before network connection. |
| B14 | Done: Cancel removes only unfinished exact .ve-<id>. files; Pause retains resumable partials. | test_b14_cancel_removes_only_own_partial_files FAIL. | real-cancel.log PASS with actual throttled transfer; unrelated similar prefix remains. Finished source never removed. |

The designer's A1 decision is appended verbatim to CURRENT_TASK.md. Existing completion timestamps are retained in pre-analysis/error History rows. No damaged
manifest is repaired, rewritten or partially interpreted. Valid JSON with bad
values follows the existing History removal workflow. Unparseable records move
inside the engine home and restore unchanged; video options are hidden with the
specified message. Copy details includes parse error and path. Windows job-log
handlers are closed before staging, as already done by normal permanent removal.

B7's measured baseline made 29 refreshes in 61.141 s and started 569 nvidia-smi
plus 568 FFmpeg processes in the first 60 s. The fixed code made 60 refreshes in
60 s and started no processes during refresh. Startup hardware initialization is
excluded from both counts. These are actual launches, not a theoretical count.

B11 is one observation under concurrent local validation, not an isolated speed
gate. The generated source was deleted by the measurement recipe. No scene-cut
or decoder architecture was changed.

B12 actual canPlayType was "probably" at both sizes. 1080 codec
hvc1.1.6.L120.90: first frame 119.6 ms, seek 58.3 ms. 1440 codec
hvc1.1.6.L150.90: first frame 58.6 ms, seek 46.6 ms. These are single functional
observations, not ten-run medians. The app's existing hev1 probe was also
"probably". CDP was enabled only in the instrumentation build.

## Validation

| Check | Result |
| --- | --- |
| Python Ruff / format / Pyright | PASS, ruff-final.log, ruff-format-final.log, pyright-final.log (0 errors/warnings). |
| GUI lint / typecheck / build | PASS; existing >500 kB bundle warning remains. |
| GUI unit | 56 PASS, gui-unit-final5.log; includes hidden video-choice rejection for unreadable records in both dialog modes. |
| Rust fmt / clippy default and e2e / units | PASS; 20 unit tests, rust-*-final.log. |
| Real verified tools bundle | 99 PASS in 218.54 s, real-bundle-final.log; synthetic loopback media only. |
| Latest A1 scoped unit suite | 42 PASS in 34.82 s, unreadable-tests6.log. |
| CPU complete suite | PASS: 582 PASS / 24 SKIP / 101 deselected, 801.34 s, cpu-final3.log. Previous position regression fixed; previous restart test omitted startup recovery and was corrected. |
| GPU suite | PASS: 101 tests, 583 deselected, 15354.82 s (4:15:54), gpu-suite.log. |
| Actual GUI suite | PASS: 16 PASS / 13 SKIP, gui-e2e-final2.log (2.7 min). Corrected locator and final GUI guard included. |
| Feature-free package smoke | PASS: final candidate and again after cache deletion, featurefree-smoke-final.json / featurefree-smoke-after-cleanup.json. Expected isolated engine home and no remote-debugging argument. |
| P2 five-launch measurement | PASS: 718.287 ms Home-ready / 720.128 ms first paint medians; one measurement, all other suites finished. |
| Final-head Windows / Ubuntu CI | Post-push gate, required green before delivery; live results and run IDs on existing draft PR #7. No pre-push result is claimed. |

Failures and warnings are retained, not erased:
- The first baseline's missing basetemp parent was an execution error, not a product failure.
- Initial real HLS fixture requested missing interpolation model after transfer;
  corrected to FPS off/keep, both real HLS tests then passed.
- Initial TLS tests skipped because OpenSSL was unavailable. A local certificate
  was generated for the successful tests; no certificate dependency added to the project.
- Early focused tests included sandbox process-tree permission errors, an outdated
  hardware-probe expectation and an obsolete disk mock. Scoped reruns are recorded.
- Broken-JSON staging initially failed because Windows log handles were open.
  Closing those handles fixed folder rename. A restart unit initially omitted
  Engine.start/_recover; corrected to invoke the exact startup recovery method.
- A full GUI attempt used an ambiguous Copy details locator (health notice and
  dialog). The test was scoped to the Video details dialog; no UX workaround.
- One preliminary A1 test used full Engine.start, leaving a hardware-probe
  temporary file locked at interpreter exit. It passed 42 assertions but emitted
  cleanup warnings. The final focused test calls startup recovery directly and
  avoids unrelated background hardware probes.
- NO_COLOR/FORCE_COLOR and the existing JS bundle-size warnings are informational.
- Dependency restoration had sandbox network/OUT_DIR and launcher-cache errors.
  Retried normal installs/builds under reviewed escalation. Locked all-extras uv
  sync restored exact dependency versions; no lockfile or dependency spec changed.

## GUI operations and visual evidence

The actual Tauri app was opened at 1280x800, switched between dark/light themes,
and exercised Home unknown media, failed History, bad-record details, reuse,
nested lists, Remove/Undo, and storage verification/removal while video and seek
continued. Screenshots remain private under evidence/P1f-2/gui (not Git).
The shared tray Quit command handler was called through the test API; a physical
notification-area click is not claimed. B12 actual playback screenshots are
under evidence/P1f-2/hevc.

## Reproduction

Run from D:\my-workspace\VideoEnhancer\work\repo and dot-source local-env.ps1.
All homes, APPDATA/LOCALAPPDATA and WebView profiles must be isolated under scratch.
Use .venv/Scripts/python.exe explicitly (the system Python alias is unavailable).

1. Restore with uv sync --locked --all-extras and npm ci in gui.
2. Run Ruff, Ruff format --check, python -m pyright; pytest -m "not gpu".
3. Run pytest -m "gpu and not soak" with VE_GPU_TEST_MODEL_HOME under work/cache.
   No owner home is allowed. Legacy >1080 source/>1440 output GPU tests stay excluded.
4. Prepare verified optional tools using scripts/prepare_link_test_tools.py.
   Run the real link bundle with VE_LINK_TEST_TOOLS_HOME and local TLS cert/key;
   recipes/real-bundle.py records the external cache guard.
5. In gui, run lint/typecheck/test/build; cargo fmt, clippy, tests and e2e build.
   npm run test:e2e launches isolated real Tauri instances.
6. Build release CDP only for package isolation/HEVC/P2 instrumentation.
   recipes/hevc-playback.mjs and recipes/p2-five-launches.mjs contain exact fixtures.
7. Build feature-free release, smoke the candidate before replacing the prior package.

## Scope and unresolved issues

Questions for the designer: none after the A1 decision. No independent product,
architecture or decoder changes were made. B11 used the explicitly permitted
measurement alternative. HEVC default, M1 1 MiB responses, MP4 audio rules,
strict decoder selection/retry, and Part R are unchanged. M3 remains disabled.

Intentionally NOT RUN: designer-deferred Part 6 work, real YouTube or prohibited
sites, physical OS tray click, owner acceptance/reboot checks, legacy GPU tests
using sources above 1080 or outputs above 1440. CPU oversized refusal metadata
fixtures remain permitted. Historical AV1 memory failures and retired P2
Electron-relative failure remain historical; this cycle does not relabel them.

## Package, disk and cleanup

Final package: D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer (2 files, 5771327 B).
Executable SHA-256: b000b13204770842f51d7b4ba1df5e812ac822ccd3c88b82f63a0cf1e22ebd9a.
Both final candidate and post-cache-cleanup smoke passed.

Start (disk-start.json):
C free 307950469120 B (307.950 GB); D free 1009745002496 B (1009.745 GB).
Cache 2302190682 B; package 5770811 B; repo 3540169703 logical B; scratch 0 B.

Restored dependency directories measured at dependency-restore-inventory.json:
uv 350049003 B; npm 44801706 B; Cargo registry 354978876 B; Rust target
3308300845 B; node_modules 191885182 B; GUI dist 576436 B. These were absent
after P1f cleanup. First measured dependency restore: 4250592048 B (4.250592 GB). Final regenerated dependency/build directories before cleanup: 4292760393 B (4.292760 GB); do not count
the entire pre-existing .venv as new restoration. Hard links mean logical file
lengths are not allocated disk space, and drive free-space differences are not
attributable exclusively to this cycle.

For the owner to delete: none. All listed cleanup candidates were inventoried by exact path and bytes before deletion, and all were removed. No automatic approval-review rejection occurred.
The old Electron package and empty Electron cache were already successfully
removed after the owner's retry authorization in P1f (05dbf72 report); they are
not restored by this cycle.

## Changed files

Only this cycle's code, tests, docs, CURRENT_TASK and this report are committed; no media, caches, packages or private screenshots.

- .ai/CURRENT_TASK.md
- .ai/LAST_REPORT.md
- docs/API.md
- docs/GUI.md
- docs/TROUBLESHOOTING.md
- gui/src-tauri/src/commands.rs
- gui/src-tauri/src/main.rs
- gui/src-tauri/src/storage.rs
- gui/src/HistoryDetail.tsx
- gui/src/HistoryRemoval.tsx
- gui/src/Home.tsx
- gui/src/LinkPanel.tsx
- gui/src/history.ts
- gui/src/types.ts
- gui/tests/e2e/p1f2-review.spec.ts
- gui/tests/history-removal.test.tsx
- gui/tests/home-schedule.test.tsx
- gui/tests/link-panel.test.tsx
- src/videoenhancer/jobs/store.py
- src/videoenhancer/service/engine.py
- src/videoenhancer/service/link_jobs.py
- src/videoenhancer/service/video_links.py
- tests/p1f2_gui_seed.py
- tests/test_link_jobs.py
- tests/test_p1f2_real_links.py
- tests/test_p1f2_review.py
- tests/test_service.py


Package replacement inventory before cleanup (candidate smoke PASS):
- D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer: 5770811 B; 2 files. Old current will be deleted; candidate renamed to current.
- D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-candidate: 5771327 B; 2 files. Old current will be deleted; candidate renamed to current.
Package replacement PASS: removed old 5770811 B after candidate smoke; current package 5771327 B (2 files), SHA-256 d7750517c0f74d8d8776268bec0ef021d3ed2e1e325786c2426d8dc4991881d5.

Retention cleanup candidate, measured before deletion: D:\my-workspace\VideoEnhancer\work\evidence\P1e-2b: 15587115 B; 265 files. Its report remains in Git dc02580; retaining P1t, P1f and P1f-2 only.
Retention cleanup PASS: removed the inventoried P1e-2b evidence, 15587115 B. Its historical report remains at dc02580.

Final package replacement inventory before cleanup (new guard unit PASS, candidate smoke PASS):
- D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer: 5771327 B; 2 files.
- D:\my-workspace\VideoEnhancer\work\package\VideoEnhancer-candidate: 5771327 B; 2 files.
Final replacement PASS: removed the prior intermediate package (5771327 B) after final candidate smoke. Current package 5771327 B, SHA-256 b000b13204770842f51d7b4ba1df5e812ac822ccd3c88b82f63a0cf1e22ebd9a.

Final cleanup inventory, measured before any deletion (logical bytes):
- D:\my-workspace\VideoEnhancer\work\scratch: 57052604858 B; 105538 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\uv: 350049003 B; 7939 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\npm: 44801511 B; 400 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\cargo\registry: 354978876 B; 12504 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\tauri-target: 3350469054 B; 7856 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\gui\node_modules: 191885251 B; 10814 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\gui\dist: 576698 B; 3 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\gui\test-results: 3985542 B; 39 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\.pytest_cache: 65990 B; 5 files; read errors 0.
First scratch cleanup stopped on an open log in an older failed GUI fixture. Authenticated health verified PID 14264 used scratch/P1f-2/gui/records-1792449277161/home; its normal shutdown returned stopped=true. Other live discoveries were checked only inside scratch and stopped only after exact reported-home verification; see stale-engines.json. No approval-review rejection occurred.

Final cleanup inventory, measured before any deletion (logical bytes):
- D:\my-workspace\VideoEnhancer\work\scratch: 1523970391 B; 89292 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\uv: 350049003 B; 7939 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\npm: 44801511 B; 400 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\cargo\registry: 354978876 B; 12504 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\cache\tauri-target: 3350469054 B; 7856 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\gui\node_modules: 191885251 B; 10814 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\gui\dist: 576698 B; 3 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\gui\test-results: 3985542 B; 39 files; read errors 0.
- D:\my-workspace\VideoEnhancer\work\repo\.pytest_cache: 65990 B; 5 files; read errors 0.
Scratch retry cleanup PASS: removed the remaining inventoried 1523970391 B after verified test-engine shutdown. Initial scratch snapshot was 57052604858 B; final scratch 0 B. Do not sum the overlapping initial and retry snapshots. Log writes between snapshots are not attributed as additional removed bytes.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\cache\uv; 350049003 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\cache\npm; 44801511 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\cache\cargo\registry; 354978876 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\cache\tauri-target; 3350469054 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\repo\gui\node_modules; 191885251 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\repo\gui\dist; 576698 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\repo\gui\test-results; 3985542 inventoried B removed.
Cleanup PASS: D:\my-workspace\VideoEnhancer\work\repo\.pytest_cache; 65990 inventoried B removed.
Post-cache-cleanup smoke PASS (featurefree-smoke-after-cleanup.json); final SHA-256 b000b13204770842f51d7b4ba1df5e812ac822ccd3c88b82f63a0cf1e22ebd9a. New scratch cleanup candidate: D:\my-workspace\VideoEnhancer\work\scratch; 17153327 B; 186 files, measured before deletion.
Post-cleanup smoke fixture cleanup PASS: removed 17153327 B; scratch is empty again. No further build or test is claimed after deleting regeneration dependencies; the final package smoke after cache removal passed.


## Final acceptance and disk summary

P2 Home-ready runs (ms): 855.228, 713.317, 738.832, 718.287, 712.720.
The specified gate uses the median, 718.287 ms (PASS); the first launch is retained,
not discarded. First-paint median 720.128 ms (PASS). The prestarted Node G1
fixture has 1000 History records; this is the same shell measurement, not a cold
Python engine launch. Instrumentation uses the release CDP build; the delivered
package has neither CDP nor e2e features. No second P2 run was made.

The final GUI unit addition first reproduced a hidden file-choice bug in the
files-only removal dialog (55 PASS / 1 FAIL). The unreadable-record selection
initialization was fixed; 56 PASS followed. The final full GUI E2E passed.
An attempted final package smoke while the full GUI suite was still running
exited immediately; a single-instance interaction is inferred, not proven.
After the GUI suite ended, final candidate and post-cache-cleanup smoke passed.

The media, pipeline and decoder implementation files are unchanged from 05dbf72.
The GPU suite passed. A separate before/after default-output hash benchmark was
NOT RUN in this cycle; P1f's measured strict equality remains historical evidence,
not a new measurement claimed here. No decoder/scene-cut optimization was made.

The initial scratch snapshot was 57052604858 B; an open log caused a partial
cleanup, then its verified isolated engine was shut down and the remaining
1523970391 B were removed. These are overlapping snapshots, not additive.
Post-cleanup smoke created another 17153327 B, inventoried and removed afterwards.
Regeneration caches/build outputs removed: 4296811925 B. Replaced package copies
removed: 5770811 B and 5771327 B. Retired P1e-2b evidence removed: 15587115 B.
Total initial inventoried development files removed across non-overlapping cleanup
items: 61393699363 B (61.393699 GB logical). Logs could change between snapshots;
no extra log bytes or allocated disk reclamation are inferred from that sum.

Dependencies were restored for verification, then regenerable caches were removed
again to honor the owner's space-minimization request. The .venv, managed Python,
Node/Rust runtimes, verified optional test tools and isolated GPU model cache are
retained. Another rebuild requires restoring npm/Cargo/uv caches normally. No
post-cleanup build is claimed; the package startup after cleanup was tested.

| Decimal GB / logical unless drive free | Start | End |
| --- | ---: | ---: |
| C free | 307.950469 | 307.803292 |
| D free | 1009.745002 | 1009.771368 |
| cache | 2.302191 | 2.302191 |
| package | 0.005771 | 0.005771 |
| scratch | 0.000000 | 0.000000 |
| repo | 3.540170 | 3.525380 |
| evidence\P1t | — | 0.182310 |
| evidence\P1f | — | 0.012832 |
| evidence\P1f-2 | — | 0.001887 |

Persistent ordinary growth from the independently measured roots, including this
cycle's evidence and the removed retired evidence: -28488882.0 B (-0.028489 GB),
PASS against <=1 GB. This is the pre-commit inventory; later Git/CI/report metadata
is not included. All inventory reads completed without errors. Cache is 2.302 GB,
below 40 GB; each retained evidence cycle is below 300 MB, exactly three cycles
remain; scratch is 0 B. Drive-wide free-space changes include unrelated host and
Windows-managed activity and are not equated with the logical cleanup totals.
No owner directory or Recycle Bin was inspected or cleaned.
