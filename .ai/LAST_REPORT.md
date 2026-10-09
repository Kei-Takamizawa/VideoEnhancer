# VE-P1c — Queue reliability groundwork

Task ID / Cycle: VE-P1c / P1c. Date: 2026-10-09 (Asia/Tokyo).
Status: BLOCKED. This is a partial implementation, not P1c acceptance.
Branch: p1c-redesign, created from origin/main
8e1a051cde59a9ca43e23657b4ee7283b7b2331e.
PR #3 was verified merged through GitHub and origin was fetched before branching.
Initial working tree was clean. No subagents, merges, main pushes or history rewrites.
The complete pasted task was copied byte-for-byte to CURRENT_TASK.md; SHA-256:
`b8c7e1a41223cc3b0917dc77033f37620008cb7d5dd18ad77169c445717a68cd`.

## Blocking decision for Claude

S4 requires analysis of only the Trial range while retaining identical Standard
frames, including VFR inputs. The current contract stores the whole source
presentation timeline and `cfr_map` of absolute source-frame indices.
`trial.py:56` calls whole-file `analyze`; `media/analyze.py` decodes the full
source for scene analysis; `media/decode.py:137` uses `self.decoder[index]`
for CUDA. A bounded packet read does not itself supply the absolute source index
needed by this decoder. No alternative range-decoding contract is specified.

Please decide how a local excerpt timeline must map to the original source and
its CFR lattice. Options for review are a reusable source-index cache (with an
explicit first-use latency policy) or an excerpt/time-based decoding contract
with exact VFR/context equivalence requirements. These are alternatives for the
designer, not implemented choices. Whole-file Trial analysis remains unchanged.
No bounded-start claim, architecture replacement or preset-output change was made.
U/M/C were not started because the S/W gate is not satisfied.

## Implementation by part

- S0: read-only inspection of the owner's actual engine home; see evidence below.
- S1, PARTIAL: two-second frame/step/memory heartbeats; service live percent/fps;
  at-most-ten-second heartbeat manifest writes; first-frame, frame-stall and wall
  watchdogs; one fresh-child stall retry; 15-second result/exit grace; child tree
  termination; bounded segment diagnostics; Copy details tail. Memory sampling
  is configured at 30 seconds with PID/RSS and available dedicated/shared Windows
  GPU counters, logged as samples arrive. OS counter queries add sampling latency.
  Live remaining-work/plan ETA is not yet adjusted for partially completed segments.
- S2, PARTIAL: service/job tracebacks and `{time, job_id, message}` last_error;
  five/30-second per-job controller backoff and failure after two attempts;
  input sharing-error message; permission retries at 0.2/0.5/1/2/4 seconds for
  atomic persistence and finishing publication; recovery of every running job.
  Persistent manifest-lock failure can still escape before/inside error recovery
  and restart the controller; durable quarantine of that case is not implemented.
- S3, PARTIAL: next-unit admission checks other jobs in owner order; oversized
  units can be admitted within 30 seconds of window start and finish beyond it;
  repeated wait events are limited to reason changes or ten-minute intervals.
  Waiting health text is `Waiting for your hours`, with the existing next-change
  timestamp. The requested overrun UI caption and a matching planner rewrite are
  not implemented; schedule/queue plan predictions retain the previous planner.
- S4, PARTIAL/BLOCKED: owner-requested Trials ignore operating hours, retain the
  between-segment lease, update waiting text from live segment elapsed time, show
  queued work paused for a preview, persist operation state, recover interrupted
  operations, and have a max(600 seconds, four times prediction) hard timeout.
  Range-only analysis, long-file startup measurement, real GPU preview admission
  and hard-timeout integration measurement are NOT RUN/pending the decision above.
- S5, PARTIAL: adding returns a durable preparing job and performs analysis and
  model checks in a background thread; pause/cancel/resume remain coherent during
  preparation. Snapshots/estimates/thumbnails do not hold the broad mutation lock;
  other mutation holds over 500 ms are logged. SSE errors remain in-stream and
  retry. Renderer silence detection/retries/heartbeats retain the last snapshot,
  refresh discovery after reconnect and reconnect on window focus/restore.
  Estimates/thumbnails still return through their HTTP request threads; no new
  asynchronous operation response contract is introduced for them.
- S6: engine stderr pipes are drained continuously into a last-64-KiB buffer.
  Existing streaming callers consume that buffer instead of reading an undrained
  pipe. The common proc module adds CREATE_NO_WINDOW on Windows. This also provides
  W2 groundwork; it does not establish console-free Electron startup.
- S7: added 18 CPU reliability tests plus two renderer fake-timer tests. These
  cover the cases listed below but do not replace the missing owner GPU checks.
- W, NOT RUN beyond shared S6/W2 groundwork: Electron still selects python.exe;
  pythonw cold start, console-window observation and full W3/W4 acceptance are
  outstanding. Child logs handle missing Python streams, but pythonw spawn was
  not exercised. W2 static subprocess-routing test passed.
- U/M/C: NOT RUN. No redesigned screens, History, optional catalog, size stage or
  multi-model Compare. No model downloads or new licence/speed/memory claims.
- Docs: API/GUI/troubleshooting reflect shipped partial behavior and limitations.
  README's duplicated developer-guide link was removed. ADDING_MODELS.md was not
  changed because no manifest/category or adapter contract changed.

## S0 evidence and classification

Inspection began 2026-10-09T09:33:14Z (18:33:14 JST). The sandbox's LOCALAPPDATA
differs from the owner's; the actual owner's home was explicitly read without
modification. Private source names/paths and raw owner logs are not copied or
committed. Inventory: 32 jobs (30 done, one failed, one paused), four operations.
No running/queued job or segment temporary was present. Active stuck case:
NOT FOUND. schedule.json, settings.json and serve.json were absent. Health GET
and last_error could not be obtained without starting/mutating the owner's service.

| ID | Observed facts | Classification and limits |
| --- | --- | --- |
| 3852dcf09e71458cacf111e2205aa43c | Failed segment 0; manifest 2026-10-06T12:15:27.109053Z, last job event 12:15:27.111054Z; caught CUDA error; control queued generation 0 | Already failed, not a current stuck case. H1/H2 are not established by this caught error. |
| a1dfc20e35bd4f95b18d77515e880f15 | Paused; two pending segments; control paused generation 10; manifest 2026-10-09T08:27:29.926783Z, last job event 08:27:29.931784Z; six abort events | Explicit paused control, not a running 0-percent job. Prior aborts alone do not prove H1-H5. |
| 91446f2a31b243e2b7a8623000999747 | Five-second Standard Trial; request exists, operation.log 0 bytes, no state.json/result.json; original 28,835,888 bytes, enhanced 6,455,011 bytes | H3 persistence gap confirmed; whether the render was cancelled, interrupted or hung is UNKNOWN. H1 is not proven. |

The incomplete Trial folder was listed at 09:46:22.5594937Z and
09:47:22.5685694Z, 60.009 seconds apart: every file size/mtime was unchanged.
No raw segment file was present. Its original file mtime was 07:59:12.6867608Z;
enhanced mtime was 07:59:03.4104958Z. Three other operation folders had results.
Job logs, manifests, available controls, operation request/result inventory,
global log and service-start log were inspected locally. No monotonic progress
samples or persisted operation state exist to distinguish H1/H5 in that case.
H2 repeated controller error, H4 starvation and H5 healthy live-frame progression
were NOT CONFIRMED in owner evidence. Counts: zero confirmed active hangs,
one confirmed operation-persistence gap, zero confirmed H1/H2/H4/H5 causes.

## Acceptance (complete-criterion status)

| Criterion | Status | Evidence / remaining requirement |
| --- | --- | --- |
| A1 | FAIL | Read-only inventory and 60-second observation complete; active stuck job NOT FOUND. Incomplete Trial cannot be causally classified beyond the H3 persistence gap. |
| A2 | FAIL | CPU watchdog/progress tests pass; GPU 30-second Standard observation and the complete S7 integration set are not completed. |
| A3 | NOT RUN | No three-job RTX run, active-job Trial or outside-hours real GPU timing. |
| A4 | NOT RUN | W2 static PASS; no pythonw Electron cold start or physical console-flash check. |
| A5 | NOT RUN | U not started; existing GUI regression tests/e2e pass. |
| A6 | NOT RUN | No catalog entries added/downloaded/measured; defaults untouched. |
| A7 | NOT RUN | No three-model compare or 100-seek/300-frame four-stream check. |
| A8 | FAIL | All local checks below pass; CI for this commit not yet observed at report creation. Full P1c acceptance is not green. |
| A9 | NOT RUN | Only existing P1b-screen synthetic e2e screenshots; no redesigned dark/light screen set. |

## Builds/tests actually executed

The existing pinned .venv executables were used directly because uv was not on
PATH; GUI commands used `node .tmp/npm-bootstrap/package/bin/npm-cli.js` as npm.
No dependency or model version was changed.

| Check | Result | Actual |
| --- | --- | --- |
| ruff check . | PASS | All checks passed |
| ruff format --check . | PASS | 89 files already formatted |
| pyright | PASS | 0 errors, 0 warnings |
| CPU pytest, not gpu/not soak | PASS | 210 passed, 3 skipped, 18 deselected; 161.49 seconds |
| Additional reliability tests (included above) | PASS | 18 tests: deadlines before/after result, progress, stall retry/next job, input/replace/controller errors, permission retry delays, oversize admission, second-job admission, startup recovery, SSE recovery, >1-MB stderr, static subprocess routing |
| CPU fixture before/after SHA-256 | PASS | All six files byte-identical; 60 synthetic frames, passthrough/resize/p0-test, H.264/HEVC. Not a real Standard GPU comparison. |
| GUI lint | PASS | eslint . |
| GUI typecheck | PASS | tsc --noEmit |
| GUI unit | PASS | 14 tests in two files, 2.82 seconds; two fake-timer heartbeat/silence/discovery tests included |
| GUI build | PASS | tsc/Vite successful; no source-output warning |
| Electron CPU e2e | PASS | One real CPU synthetic add/completion/close/restore/Quit test, 15.4 seconds; three opt-in tests skipped |
| Windows package build | PASS | Unsigned win32-x64 folder generated from final GUI code |
| Packaged Electron smoke | PASS | One start/isolation/graceful-quit test, 4.1 seconds |
| git diff --check | PASS | No whitespace errors; Git LF/CRLF notices only |
| GPU/long-file/console-flash/catalog/compare/soak | NOT RUN | No acceptance or measured performance claim |

Expected: watchdogs stop hangs, next jobs remain runnable, live percent advances,
stderr cannot deadlock, SSE survives a failed snapshot, preparing work cannot
start early, completed jobs reach 100%, restart makes interrupted work retryable.
Actual: the tested CPU/fake-clock/renderer cases above satisfy those expectations.
The implementation gaps listed under S1-S5 remain; do not generalize CPU tests
to GPU throughput, stability, long-file latency or all Windows sharing failures.

GUI operations: launch real Electron/service in an isolated synthetic home;
open Add, enqueue CPU footage, observe Running and Done; visit existing pages;
close/show window with the engine alive; check layout at 125/150% scaling; Quit;
launch generated package and inspect renderer isolation; graceful Quit. These
are automation checks, not a physical tray/Explorer/console-flash observation.

Related logs, ignored and local: `.tmp/p1c/cpu-final.log`,
`reliability.log`, `gui-tests-final.log`, `gui-lint-final.log`,
`gui-typecheck-final.log`, `gui-build-final.log`, `gui-e2e-final.log`,
`gui-package-final.log`, `gui-packaged-e2e.log`, `fixture-final.log`,
`before-hashes.json`, `after-hashes.json`, `s0-observation.json`.
Screenshots are outside Git under
`%CODEX_HOME%/visualizations/2026/10/09/01a12000-750a-7813-9ea1-6bc265708fb5/p1c-e2e/`:
add-synthetic.png, queue-synthetic.png, plan-synthetic.png,
schedule-synthetic.png, models-synthetic.png, settings-synthetic.png,
settings-125-percent.png, settings-150-percent.png. Initial e2e default output
was moved out of the repository; the final run explicitly used the external folder.

Errors corrected during validation: a dispatch dedent error, closed Windows pipe
polling, preparation/control transition races, and inherited test assumptions
about synchronous add and operating-hours Trial admission. Initial sandbox
checks failed on temporary-file access/localhost sockets; normal host checks
supersede those failures. An initial GUI sandbox transform-cache lookup failed;
host GUI unit checks pass. No failed attempt is counted as a pass. GUI runners
emit an existing NO_COLOR/FORCE_COLOR warning. gh auth status was unavailable/
reported an invalid token in the sandbox; no credentials were modified or bypassed.

## Reproduction and files

Run the engine check commands above with the pinned environment. CPU pytest:
`pytest -m "not gpu and not soak" --basetemp=.tmp/p1c/recheck`.
`pytest tests/test_reliability.py` reproduces injected deadlines and job isolation.
Use npm lint/typecheck/test/build/package; set VE_GUI_EVIDENCE outside the repo
before `npm run test:e2e`. Set VE_GUI_PACKAGE_EXE to the generated executable for
the packaged smoke. Use fresh VE_HOME values, never the owner's existing queue.
For the unresolved range issue, inspect run_trial's analyze call and the CUDA
absolute-index decoder; a long source still requires complete analysis. No long
source latency was measured. For the remaining lock issue, hold manifest.lock
past the five-second timeout and observe exceptions escaping recovery; no
successful persistent-lock quarantine test is claimed.

Changed files: CURRENT_TASK.md, LAST_REPORT.md, README.md; docs/API.md, GUI.md,
TROUBLESHOOTING.md; gui/src/{App.tsx,Queue.tsx,api.ts,types.ts},
gui/tests/events.test.tsx; new src/videoenhancer/{proc.py,files.py};
estimate/model.py, jobs/{gpu_memory.py,store.py}, logging.py,
media/{analyze.py,decode.py,encode.py,mux.py,probe.py},
pipeline/{quality.py,runner.py}, schedule/{controller.py,planner.py,windows.py},
service/{engine.py,server.py,settings.py}, cli.py, bench/{finalization.py,runner.py};
tests/{test_reliability.py,test_service.py,test_service_models.py}.

Intentionally not performed: U/M/C, new adapter or excerpt-timeline architecture,
new models/downloads, owner queue mutations, real GPU acceptance/benchmarks,
telemetry/security changes, dangerous authentication workarounds, CI pass claims,
merge or main push. The current work is prepared for a draft PR; publication
identifiers/results are verified in the final response. If commit/push fails,
record that failure here and stop. No further implementation cycle starts.
