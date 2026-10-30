Task ID: VE-P1e-3d1
Status: COMPLETED

## Result and execution

Implementation and all requested speed measurements are complete. Every Compare
speed target and the warm-worker startup target passed. The selected C1 residency
change and warm worker matched c28b461 on all nine G5 fixtures. The divider fix
recorded zero gaps after reproducing the defect, and fallback Escape tests pass.
All requested local checks passed, final owned scratch was removed, and no
application/worker/FFmpeg process remains in the final recorded scan. The
24 existing CPU skips are explicitly excluded from PASS counts below.

Windows, NVIDIA GeForce RTX 4060 Ti (8188 MiB; observed driver 621.01).
Branch: claude/project-thread-6lra47. HEAD: 736897acab74baa0161e32def36a1a769db6f501.
The initial working tree was clean. Existing cycle changes were protected during
all resumptions; CURRENT_TASK remains unchanged. AGENTS assigns all Git mutations
to the operator: no staging, commit, push, PR or merge was performed. Read-only
Git required approved escalation. Only synthetic media and isolated homes under
work/scratch were used; local-env.ps1 was sourced before builds/tests.

## Part A: profile, implementation and targets

The apparent slow decode was predominantly pipeline backpressure, not 19 seconds
of decoder work. In profile-idle-2.json, the serial instrumented Compare took
49.554550 s. The following times are relative to pipeline entry and overlap;
they must not be summed.

| Stage | Start (s) | End (s) | Wall (s) | Wait for upstream (s) | Wait for downstream (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Decode | 2.972061 | 22.257891 | 19.285830 | - | 18.302698 |
| Compute | 2.972393 | 23.267165 | 20.294772 | 0.502083 | 0.000225 |
| Encode | 2.972675 | 23.613265 | 20.640590 | 18.672815 | - |

Restore calls took 9.965047 s, RIFE 8.994190 s, and actual encode calls 1.406343 s.
Original transcode was 13.148373 s; the model preview transcode was 8.834903 s.
The separately accumulated decode-call metric was 19.285693 s, including the
same downstream wait; it is not an independent CPU/NVDEC utilization measure.

Original transcode now runs alongside the model pipeline. A persistent isolated
Compare worker retains model sessions and a decoded CPU cache. The cache owns
clones, retains at most two ranges and 1,000,000,000 bytes including reservations
and pinned borrowers, and invalidates changed source size/mtime. A smaller model
context can reuse a covered range. Original preview files are reused too. Both
models/cache are released before processing needs GPU memory; GPU admission and
preemption rules are unchanged. Repeated CPU pictures are converted once.
For H.264 Compare, an observer tees the unchanged NVENC packets through a
fragmented-MP4 pipe into the unchanged preview encoder, overlapping its work.
Other encoding paths retain their previous behavior.

| Exploratory run (one run each, not repeated medians) | Complete (s) | Interpretation |
| --- | ---: | --- |
| Serial instrumented | 49.554550 | Profile reference |
| CPU thread limit alone | 50.8283 | No observed gain alone |
| Parallel Original/model | 36.7871 | Reduced serialized work |
| Streaming preview | 30.5803 | Reduced final transcode tail |

The intermediate session/cache implementation (A2) had a three-run idle median
30.372870 s and first tile 8.239808 s: the 30 s target was still unmet then.
The final C1 candidate below improved the complete time. These observations
are separate experiments, not additive or independently controlled speed-ups.

Fixture: 6 s, 512x288, 30 fps synthetic source; 5 s Compare; Standard C1 + RIFE,
1080 short side, 2x fps, H.264. Baseline is a separate c28b461 scratch export.
All following values are medians of three complete runs.

| Measure | c28b461 (s) | Final candidate (s) | Target | Result |
| --- | ---: | ---: | --- | --- |
| Idle first tile | 16.331586 | 8.462429 | <=9 s | PASS |
| Idle complete | 48.456944 | 29.101077 | <=30 s | PASS |
| Another model first tile | 0.162309 | 0.150856 | <=6 s | PASS |
| Busy first tile | 44.129035 | 34.992401 | <=105% of baseline | PASS |
| Busy complete | 76.139646 | 55.888741 | <=105% of baseline | PASS |

First tile means first available firstlook/Original readiness observed by the
profiling client, not a measurement of GUI paint or completion of the new model.
The other-model click used basicvsrpp-denoise. Its cached Original can appear
immediately. The complete operation and every preview hash were also checked;
no failed second click is counted. A2 recorded one decoded-cache hit, two misses,
one range and 268075008 retained bytes on that click.

The final measurements used the exact C1 snapshot that passed G5. Production was
verified against the warm fingerprint before applying its selected diff. The only
subsequent adjustment clears incomplete CPU buffers before returning their cache
reservation, on abort cleanup; it does not change completed renders. The final
CPU/cache tests and GPU checks use that final source. Hash provenance is in
variants.json and final-source-hashes.json. Completed measurements were reused.

Every final preview in all repetitions matched all baseline repetitions,
including the second model (final-measurement-validation.json):

| Preview | SHA-256 |
| --- | --- |
| Original | 3503a34520d4133920a0d896f40b4726ee116cff983b8a51138e89c4d8f0a0b7 |
| C1 cleanup | 1a5ffd8ae5d54a1bead7ff6b4ab8f72b4802a861a9687433d1d23dd56158bcab |
| C2 denoise | cad5a436b2e4bbc8426762422f3b748abf9442edb39b632326652b876f84b4ee |

## Part B: warm worker and replacement safety

One isolated worker belongs to a job/settings/model/input/effective-batch key.
It verifies weights and loads models once, resets part counters and stage state,
and reuses successful parts up to 50. Failure, watchdog, OOM/half-clip/uncapped
retry, spill (including progress-only spill), pause, abort, key change and part
limit discard it. Retry ordering and one processing unit per GPU are unchanged.
The Windows kill-on-close job is installed before admitting work. Heartbeat
shutdown precedes the buffered result, preventing late progress after completion.
Cooperative exit has bounded tree-kill fallback. The lifecycle is documented in
docs/part-worker-lifecycle.md.

Three uninterrupted 120 s 1080p Standard jobs per version, 22 parts per job:

| Startup statistic | Baseline (s) | Warm (s) | Result |
| --- | ---: | ---: | --- |
| Part 1, median across jobs | 4.375063 | 3.864636 | Measured |
| Parts 2-N, pooled median | 4.541607 | 0.149121 | PASS: 3.283437% of baseline, <=40% |

Startup is the existing per_part_startup_seconds sum, including parent/IPC
residual; it is not a pure hardware first-frame latency. Stage/setup terms are
retained in per-run JSON. The full-job median fell from 3722.245252 s to
3617.291695 s (2.819630%); all three outputs were identical. The first reference
job used 22 distinct part-worker PIDs; the first warm job reused PID 2140.
Normal warm engine shutdown measured 0.370474 s in that job with no remaining
child. Later profilers record shutdown and remaining PID fields; the oldest
baseline profiler lacked those fields, so no value is invented for it.

Final CPU tests cover reuse, every replacement event above, 50 parts, effective
batch changes, protection failures, global/per-job pause and abort. Real CPU
worker tests cover error retirement, a successful restart, cancel and shutdown
within 5 s without a surviving child. Fakes exercise events not reliably forced
on a real GPU; they are not reported as physical OOM/spill experiments.

## Part C: candidates and byte-identity gates

Full 120 s job, three uninterrupted runs each, on top of warm. Gain is relative
to the warm median, not to the historical single-run O9 numbers.

| Variant | Three full-job seconds | Median (s) | Gain vs warm | Byte gate / decision |
| --- | --- | ---: | ---: | --- |
| baseline | 3746.702309, 3721.916039, 3722.245252 | 3722.245252 | - | Reference |
| warm | 3617.291695, 3617.944603, 3616.921797 | 3617.291695 | - | 9/9 G5; shipped |
| c1-gpu | 3590.170368, 3589.983774, 3589.330661 | 3589.983774 | 0.754927% | 9/9 G5; shipped |
| trim-context | 3540.097307, 3541.609811, 3541.794776 | 3541.609811 | 2.092225% | DIFFERENT bytes; rejected |
| cuda-streams | 3619.634423, 3619.385570, 3619.099818 | 3619.385570 | -0.057885% | 9/9 G5; no measured gain, not shipped |

Only C1 residency is applied: the built-in C1 weights stay on CUDA within their
session. No weights, model selection, manifests or defaults changed. CUDA streams
passed identity but its median was slower, so it is not applied. Trimmed context
failed an early middle-part pixel probe and every full speed output; it cannot
ship. Its full output SHA is
344a71d8be370fefe7df154ff2113450cfb5e81731861b0ce90620c80adab524;
the early probe SHA was
1f0cd9dd19dfa7218b5eb85943754655fabdd8289bea339e751c9b741c49dd02
versus reference
896b96117ac2dae121828779ca3dde63e81d1e3867c92055550fc2844517e983.
Its nine-fixture G5 was intentionally not pursued after this rejection, while
all three requested full speed runs were still measured.

Warm, C1 residency and CUDA streams all matched each reference below. The final
combined source equals the tested C1 snapshot exactly, so its nine completed
G5 cases were reused rather than rerun (combined_g5_reused=c1-gpu).

| G5 fixture | Reference / identical output SHA-256 |
| --- | --- |
| land-std-h264-2x | 82cacf0478a6c6ee8704ee3b16c34efe48108960b3300fb5739793dc4b500679 |
| land-std-hevc-off | e58ae6268609a1c011e933e52cc516494faea6b5a05e444e288a43f8ec2bc53f |
| port-std-h264-off | 8951bc3ec3edd935c4cec0326d73b4516c7f7d65cdac5b0e02791f44ab6825af |
| land-fast-hevc-off | 3e0754f2a05564f74a7305623785f5ff60b04bbce06472f55975a021542288a3 |
| port-fast-hevc-2x | 9eb0103ce768dd607ab1a43a181688dd224709122fd3d47febced43f274e98a2 |
| port-fast-h264-off | 183c1af156b24b60c40d60fe04b18c140fafc0a7495d7181c869711746e39946 |
| cut | b15d9e01236f3f787e56c7953cfe998518f91e41f81520ced5b4e6a2e337db1b |
| vfr | ae933fbb5a730c7630ad29cec83ab629596cbf37e88ed81725cefe45f78b11a8 |
| long | b01e6d912e400201e527a0e89a2904c5e709c0990a4e2621a8b65b8a54f80182 |

The six 30 s combinations include landscape/portrait, Standard/Fast,
H.264/HEVC, 2x fps/off; cut and VFR sources complete the nine-fixture matrix.
Fixtures, final full-file hashes, settings, per-part stats and source snapshots'
fingerprints are in the per-run JSON and speed-cycle-summary.json. Hashes cover
encoded final files, not only decoded images or a short probe.

## Part D: player behavior, Expected / Actual

The reproduced gap came from independently rasterized clip edges at fractional
fit/scaling. With the unfriendly 1117x703 window and divider steps of 7/1000 at
60 Hz, the two clipped surfaces could expose a one-physical-pixel background gap.
Enhanced now remains an opaque full-width underlay; only Original is clipped,
using original width times the fraction. There is no unpainted region between
independently rounded boundaries. Unit arithmetic cases cover scales, offsets,
fractions and endpoints. The existing HTML picture-edge presentation is retained.

| Own-window WGC run | Received frames | Gap frames | Max gap pixels | Capture errors | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Initial normal-size control | 3581 | 0 | 0 | 0 | Colors not yet asserted; not the final gate |
| Validated normal-size control | 3593 | 0 | 0 | 0 | All frames contain both synthetic colors |
| Unfriendly stepped, before | 3593 | 10 | 1 | 0 | Defect reproduced |
| Same window/steps, fixed | 3598 | 0 | 0 | 0 | PASS over 60.000195 s |

WGC inspected every received frame of the owned red/blue synthetic player window
at display rate, using its center row, not the desktop. The fixed run received
both colors in all 3598 frames and sent 3600 commands. Helper PID 19616 exited;
remaining children were empty. Before/fixed helper SHA values and QPC times are
in divider-stepped-unfriendly.json and divider-stepped-fixed.json. This evidence
establishes the measured seam condition, not all possible media/display setups.

Escape is captured before focused HTML video controls. Repeats cannot close the
dialog immediately after leaving fullscreen. When fullscreen, it explicitly exits
fullscreen and retains the dialog; the next Escape closes it and restores focus.
Vitest covers both paths. Final Playwright exercised playing/focused fallback
video in all four helper-failure modes and fullscreen Escape in both window
sizes/themes. Expected and actual behavior match; all seven cases passed after
the final native underlay edit. No Computer Use was required by this task.

## Build and test results

| Check | Result / evidence |
| --- | --- |
| Final full CPU: pytest -m "not gpu" | PASS: 702 passed, 24 existing skips, 101 deselected, 427.18 s; check-cpu-final.log |
| Final GPU: pytest -m "gpu and not soak" | PASS: 101 unique cases = 19 retained + 82 resumed; zero missing/duplicate IDs; gpu-final-coverage.json |
| Ruff check src tests gui/scripts | PASS; ruff-final-source.log |
| Ruff format --check src tests gui/scripts | PASS; ruff-format-final-source.log |
| Pyright | PASS, no errors; pyright-final-source.log |
| GUI lint and build | PASS; gui-lint-final.log / gui-build-final.log, reused on unchanged GUI source |
| Vitest | PASS: 86; vitest-final.log |
| Final player Playwright | PASS: 7, 1.5 min; check-player-final.log |
| Rust player tests, default / test-faults | PASS: 10 / 9; rust-final-default.log, rust-final-faults.log |
| Rust clippy, both configurations, all targets, -D warnings | PASS; clippy-final-default.log, clippy-final-faults.log |
| Final Tauri native test build | PASS; tauri-build-final-native.log |
| Compare targets and every preview hash | PASS; final-measurement-validation.json |
| Warm/C1 nine-fixture G5 and three full speed hashes | PASS; speed-cycle-summary.json |
| Divider 60 s zero-gap gate | PASS; divider-stepped-fixed.json |

The 24 CPU skips retain their existing reasons: private sample fixtures were not
provided, Linux-only parent-death behavior, optional verified standalone tools,
and local TLS fixtures requiring OpenSSL/certificates. Skips are not PASS results;
no tests were disabled or loosened. All requested implementation paths have
executed regression coverage. Final Python source was frozen for CPU/GPU checks.
Earlier completed GUI/Rust checks were reused because their source was unchanged.

## Errors, interruptions and reproduction

- a-baseline-idle-1: C1 completed, but the different-model click failed because
  built-in denoise.pth was absent. Not counted in the repeated gate. The existing
  built-in model was fetched through ModelRegistry into the isolated cache and
  subsequent three-run baseline/candidate clicks completed; no model was changed.
- baseline-standard-120-1: preparation was interrupted by the initial harness's
  add/start order. The harness was corrected to start before add. It is a failed
  attempt, not a timing result; reference run 2 and later repetitions completed.
- Initial real-worker fixture used an unstored job ID; its setup was corrected.
  Initial fullscreen Escape e2e exposed that stopping propagation also prevented
  browser fullscreen exit; explicit exitFullscreen fixed it. Missing jsdom
  fullscreen descriptors were added to the test fixture. Final tests passed.
- The first check-runner smoke failed on a relative Windows executable path
  (WinError 2). Absolute executable resolution fixed it; smoke 2 passed with all
  sampled PIDs gone. Early lint/type issues were corrected before final gates.
- A usage interruption stopped an early CPU run and a baseline G5 job after two
  parts. G5 resumed those complete parts for quality only; resumed elapsed time
  is excluded from speed medians. The full CPU suite later completed.
- A model-capacity stop interrupted baseline speed repetition 3 at 21/22 parts.
  Its partial manifest/log were retained as interrupted-1, home inventoried and
  removed, and only that repetition was rerun continuously to completion.
- The desktop update at 18:55 UTC externally killed C1-GPU repetition 3 (not a
  usage limit). Its partial log/manifest were separately retained, the home was
  inventoried (628213382 logical / 319976073 nonshared bytes) and removed, and
  only that interrupted repetition was rerun. Its partial timing is excluded.
- A later capacity stop killed the final GPU suite after 19 PASS cases. Those
  exact IDs and source hashes were retained, no Python/FFmpeg/app process remained,
  and only the interrupted/remaining 82 cases were resumed. The original partial
  log/PID ledger has separate interrupted-1 names. Final identity coverage is
  checked against the independently collected 101 GPU node IDs.
- A first mixed-source GPU attempt was deliberately interrupted before final
  verification; it is NOT_RUN as a completion gate. It is not counted as PASS.
- The GUI build printed a nonfatal plugin timing advisory; Vitest printed
  expected native-rejection fixture diagnostics and a jsdom timing advisory.
- Sandbox CIM/read-only Git/private pytest-cache reads were denied; approved
  reads worked. One earlier pytest-cache warning and Git CRLF conversion warnings
  were observed. No delete refusal was retried or bypassed.

Every completed measurement's raw JSON/log is retained under evidence/VE-P1e-3d1;
measurement-errors-index.json indexes result-level failures. Interrupted logs are
not successful attempts. Completed tests and measurements were not repeated on
resume. Reproduction tools are gui/scripts/compare-profile.py, job-profile.py,
speed-fixtures.py, optimization-probe.py, speed-cycle.py and player-seam-profile.py.
Use local-env.ps1, fresh absolute work/scratch homes and the recorded synthetic
recipes/settings; the baseline must be a separate c28b461 export. Source hashes
and candidate patches are preserved; scratch source/media copies were deleted.

## Processes and cleanup

Final CPU and player sampled process ledgers report exit 0 and no remaining PID,
without cleanup needing to terminate a child. The wrapper records PID plus
creation time at 100 ms intervals; it is a sampled owned-process ledger, not an
OS-wide trace. Measurement profilers record PIDs before close and remaining
children. The resumed GPU root exited 0 with no remaining child; final source
hashes still matched. gpu-final-coverage.json proves the union of 101 distinct
PASS IDs, not a claimed uninterrupted full-suite run. The resumed 82 cases took
9846.31 s. final-process-inventory.json records 2165 observed check PIDs and
confirms no matching owned identity is alive. The first broad scan saw transient
Python PID 25136, already gone at independent CIM recheck; its exact ownership
was not captured. The final scan records/excludes the inventory utility ancestor
chain and finds no application, worker or FFmpeg process. No owner
application/data was used. All normal exits and interrupted-run inspections are
reported with their actual scope.

Per-measurement homes were inventoried before their one-attempt cleanup. The
45 finished measurement artifacts below were removed successfully, totaling
2512166626 logical bytes / 628573166 nonshared bytes. Shared weight hardlinks
remain in cache; logical lengths are not allocated disk bytes. Final-check scratch
was subsequently inventoried and removed (842877906 bytes). Additional isolated
model-copy home and TEMP generator output were also inventoried and removed
(281869919 bytes), all created after this cycle log began. No delete was refused.
The cycle root and default test home are absent, TEMP is empty, and only the
pre-existing owner-check files and old videoenhancer.jsonl remain (42238391
bytes). Their timestamps predate this cycle. Empty pre-existing tmp/native
folders and unrelated owner-check-trial evidence are protected.

| Measurement artifact below work/scratch | Logical bytes removed |
| --- | ---: |
| p1e3d1/baseline | 4274253 |
| p1e3d1/baseline-idle-1 | 283442592 |
| p1e3d1/baseline-standard-120-1 | 272230005 |
| p1e3d1/baseline.zip | 1200414 |
| p1e3d1/cache-unit | 0 |
| p1e3d1/compare-unit | 0 |
| p1e3d1/compare-worker | 0 |
| p1e3d1/cpu | 0 |
| p1e3d1/cpu-final | 0 |
| p1e3d1/cpu-final-source | 269176 |
| p1e3d1/cpu-release | 0 |
| p1e3d1/cpu-resumed | 24962 |
| p1e3d1/e2e | 193419100 |
| p1e3d1/e2e-final | 185979716 |
| p1e3d1/enhanced | 0 |
| p1e3d1/hard-cut-6.mp4 | 5341 |
| p1e3d1/jobs | 1 |
| p1e3d1/landscape-30.mp4 | 15742025 |
| p1e3d1/parallel-idle-1 | 283445778 |
| p1e3d1/pause-unit | 0 |
| p1e3d1/portrait-30.mp4 | 15644418 |
| p1e3d1/profile-idle-1 | 272225347 |
| p1e3d1/profile-idle-2 | 283445085 |
| p1e3d1/pytest-cache | 65061 |
| p1e3d1/safety-unit | 0 |
| p1e3d1/seam-blue.mp4 | 162479 |
| p1e3d1/seam-red.mp4 | 54522 |
| p1e3d1/shutdown-cache | 617 |
| p1e3d1/shutdown-unit | 0 |
| p1e3d1/stream-idle-1 | 283446825 |
| p1e3d1/stream-unit | 0 |
| p1e3d1/synthetic-1080-120.mp4 | 60397505 |
| p1e3d1/synthetic-512x288-30.mp4 | 384431 |
| p1e3d1/threads-idle-1 | 283445084 |
| p1e3d1/variants | 4807331 |
| p1e3d1/vfr-6.mp4 | 2258378 |
| p1e3d1/videoenhancer.jsonl | 13343 |
| p1e3d1/warm-real | 0 |
| p1e3d1/warm-real2 | 0 |
| p1e3d1/warm-unit | 0 |
| p1e3c2-native/pair-original.mp4 | 16447596 |
| p1e3c2-native/pair-enhanced.mp4 | 16448259 |
| p1e3c2-native/review-original-720.mp4 | 16428217 |
| p1e3c2-native/review-output-1080.mp4 | 16415390 |
| p1e3c2-native/review-poster.jpg | 43375 |

Older evidence was inventoried before deletion after verifying its report in Git.
Current d1 plus F3 and F2 remain; unrelated owner-check-trial remains.

| Removed development evidence | Logical bytes removed | Retained report revision |
| --- | ---: | --- |
| VE-P1e-3b | 62640230 | 188bcdc |
| VE-P1e-3c1 | 47090780 | 284ed93 |
| VE-P1e-3c2 | 198162316 | abd4dff |
| VE-P1e-3c2-F1 | 67000979 | 0da3344 |
| VE-P1e-3c2-OC | 77323025 | 7288e34 |

## Disk and final housekeeping

All values are decimal GB; final-disk.json is the recorded end snapshot.

| Item | Start | End |
| --- | ---: | ---: |
| C free | 328.725159936 | 329.988984832 |
| D free | 976.491843584 | 876.266708992 |
| Current package, logical | 0.125288579 | 0.125288579 |
| Cycle evidence, logical | 0.000192412 | 0.161987256 |
| All scratch, logical | 0.047713058 | 0.042238391 |
| Complete cache, logical | 11.345288802 | 11.385460991 |

The initial inventory followed small initial writes, so is not an exact pre-write
baseline. Measured persistent table growth (package + cache + cycle evidence)
is 0.201967033 GB. Even conservatively charging the entire changed text-file
sizes and final report/index writes as new data, growth stays below 0.210 GB
(<1 GB). Cache is below 40 GB and evidence below 0.300 GB. The evidence value
is a snapshot; small index/reporting logs continue to grow during final reporting.
All cycle-created scratch files were removed; pre-existing unrelated scratch
is not part of the cleanup authorization. The first oversized source
(169792258 bytes) was inventoried and replaced by a 60397505-byte input.
No cycle media, screenshots, weights, packages or build output were added to Git.
Free-space changes are volume-wide, not equated with logical lengths or attributed
to this task. Nothing outside work was inspected to explain those changes.
Per-cleanup measurements below and their JSON retain the independently measured
lengths; repeated/shared hardlink lengths must not be treated as physical freed
space or added to the volume free-space difference.

## Unresolved items / For the owner to delete

None for this cycle. Every required local gate completed, no owned application
process remains, and no delete was refused. The 24 existing optional/platform CPU
skips remain explicitly unexecuted coverage, not passing tests. Future calibration
and remote publication remain separate responsibilities, as listed below.

## Questions for the designer and intentional exclusions

Default chosen: ship only a byte-identical candidate with a positive measured
median gain; keep the original behavior for rejected trim-context and slower
CUDA streams. Reuse exact-source completed gates rather than repeat them.
No new architecture or product decision is requested. Calibration/estimates are
P1e-3d2, C17 remains dropped, and defaults, model manifests/weights, memory caps,
admission/preemption, packaging, CI workflows and the LGPL build were not changed.
Owner-media checks, production deployment, remote CI and Git publication were
NOT_RUN by Codex. The operator performs Git recording/publication; stop after
this one implementation/verification/report cycle.

## Changed files

- .ai/LAST_REPORT.md
- docs/part-worker-lifecycle.md
- gui/scripts/check-profile.py
- gui/scripts/compare-profile.py
- gui/scripts/job-profile.py
- gui/scripts/optimization-probe.py
- gui/scripts/player-seam-profile.py
- gui/scripts/profile_cleanup.py
- gui/scripts/speed-cycle.py
- gui/scripts/speed-fixtures.py
- gui/src/HistoryDetail.tsx
- gui/src-tauri/player/src/capture.rs
- gui/src-tauri/player/src/composition.rs
- gui/src-tauri/player/src/host.rs
- gui/src-tauri/player/src/lib.rs
- gui/tests/e2e/history-player.spec.ts
- gui/tests/e2e/native-player-fallback.spec.ts
- gui/tests/player-fallback.test.tsx
- src/videoenhancer/media/encode.py
- src/videoenhancer/models/basicvsr.py
- src/videoenhancer/pipeline/runner.py
- src/videoenhancer/pipeline/session.py
- src/videoenhancer/schedule/controller.py
- src/videoenhancer/service/compare.py
- src/videoenhancer/service/compare_cache.py
- src/videoenhancer/service/compare_stream.py
- src/videoenhancer/service/compare_worker.py
- src/videoenhancer/service/engine.py
- tests/test_compare_cache.py
- tests/test_compare_worker.py
- tests/test_pipeline.py
- tests/test_warm_worker.py

## Final-check scratch cleanup candidates (inventoried before deletion)

| Path below work/scratch | Logical bytes |
| --- | ---: |
| p1e3d1/checks | 842877906 |

## Additional cycle scratch candidates (before deletion)

The cycle log began at 2026-10-29T01:21:21 UTC. This isolated model-copy home and every TEMP child/file below were created later. The older tmp directory itself, owner-check and videoenhancer.jsonl are preserved.

| Path below work/scratch | Logical bytes |
| --- | ---: |
| home | 272225347 |
| tmp/Microsoft | 43686 |
| tmp/msedge_chrome_Unpacker_BeginUnzipping24180_612291899 | 3807 |
| tmp/node-compile-cache | 9363768 |
| tmp/playwright-tracing-0KQ9wS | 0 |
| tmp/playwright-tracing-0mv3YI | 0 |
| tmp/playwright-tracing-0ybKZh | 0 |
| tmp/playwright-tracing-1N039N | 0 |
| tmp/playwright-tracing-23xlzD | 0 |
| tmp/playwright-tracing-2a3auS | 0 |
| tmp/playwright-tracing-2NmK73 | 0 |
| tmp/playwright-tracing-9QAfmf | 0 |
| tmp/playwright-tracing-bWZRAv | 0 |
| tmp/playwright-tracing-gAmjPX | 0 |
| tmp/playwright-tracing-GxOZI8 | 0 |
| tmp/playwright-tracing-HFbN3B | 0 |
| tmp/playwright-tracing-ihPBwY | 0 |
| tmp/playwright-tracing-K69D6B | 0 |
| tmp/playwright-tracing-lJkxwj | 0 |
| tmp/playwright-tracing-loTGv0 | 0 |
| tmp/playwright-tracing-NTyqll | 0 |
| tmp/playwright-tracing-obSG6o | 0 |
| tmp/playwright-tracing-OVIPU0 | 0 |
| tmp/playwright-tracing-PKp7we | 0 |
| tmp/playwright-tracing-qsSqJk | 0 |
| tmp/playwright-tracing-SkATtT | 0 |
| tmp/playwright-tracing-smzfbf | 0 |
| tmp/playwright-tracing-vUxb5p | 0 |
| tmp/playwright-tracing-WDgjQH | 0 |
| tmp/playwright-tracing-wkSgWx | 0 |
| tmp/playwright-tracing-xcRobo | 0 |
| tmp/playwright-tracing-yEWjQf | 0 |
| tmp/playwright-transform-cache | 231333 |
| tmp/torchinductor_pro | 0 |
| tmp/VSFaultInfo | 1978 |

## PID records

Main check roots are listed here; all sampled child PIDs and creation times are in the linked-by-name process ledgers under evidence/VE-P1e-3d1. Interrupted roots have no final exit code in their partial ledger; their absence was checked at resume and again at final inventory. Historical numeric PIDs can be reused, so no process was killed by a stale numeric PID.

- check-cpu-final-processes.json: root PID 18204; recorded exit 0; final matching-identity survivors: none.
- check-gpu-final-interrupted-1-processes.json: root PID 3316; recorded exit None; final matching-identity survivors: none.
- check-gpu-resume-1-processes.json: root PID 15136; recorded exit 0; final matching-identity survivors: none.
- check-harness-smoke-2-processes.json: root PID 25884; recorded exit 0; final matching-identity survivors: none.
- check-player-final-processes.json: root PID 19604; recorded exit 0; final matching-identity survivors: none.

Own-window helper PIDs: 11256 (initial control), 6804 (validated control), 15052 (unfriendly reproduction), 19616 (fixed gate). All recorded remaining children are empty. Part-worker PIDs and Compare child PIDs are retained per measurement; the following index preserves recorded measurement PID values without implying that an unrecorded historical process was traced.
See measurement-pid-index.json and final-process-inventory.json.

## Per-measurement automatic cleanup records

Each profiler inventoried its own contained home before deleting it. Rows are independent attempts; shared weight hardlinks remain in cache. These lengths are not allocated disk bytes. The manual batch cleanup tables above are separate artifacts, not parent totals overlapping these homes.

| Cleanup record | Home below work/scratch | Logical bytes removed | Nonshared file bytes |
| --- | --- | ---: | ---: |
| a-baseline-idle-1-cleanup.json | p1e3d1/a-baseline-idle-1 | 283442601 | 14357821 |
| a2-baseline-busy-1-cleanup.json | p1e3d1/a2-baseline-busy-1 | 349934320 | 41697011 |
| a2-baseline-busy-2-cleanup.json | p1e3d1/a2-baseline-busy-2 | 349934375 | 41697066 |
| a2-baseline-busy-3-cleanup.json | p1e3d1/a2-baseline-busy-3 | 349935018 | 41697709 |
| a2-baseline-idle-1-cleanup.json | p1e3d1/a2-baseline-idle-1 | 331996468 | 23759159 |
| a2-baseline-idle-2-cleanup.json | p1e3d1/a2-baseline-idle-2 | 331996492 | 23759183 |
| a2-baseline-idle-3-cleanup.json | p1e3d1/a2-baseline-idle-3 | 331996450 | 23759141 |
| a2-current-busy-1-cleanup.json | p1e3d1/a2-current-busy-1 | 349940778 | 41703469 |
| a2-current-busy-2-cleanup.json | p1e3d1/a2-current-busy-2 | 349939671 | 41702362 |
| a2-current-busy-3-cleanup.json | p1e3d1/a2-current-busy-3 | 349939703 | 41702394 |
| a2-current-idle-1-cleanup.json | p1e3d1/a2-current-idle-1 | 332003422 | 23766113 |
| a2-current-idle-2-cleanup.json | p1e3d1/a2-current-idle-2 | 332003390 | 23766081 |
| a2-current-idle-3-cleanup.json | p1e3d1/a2-current-idle-3 | 332003437 | 23766128 |
| baseline-cut-g5-cleanup.json | p1e3d1/baseline-cut-g5 | 311557200 | 3319891 |
| baseline-land-fast-hevc-off-g5-cleanup.json | p1e3d1/baseline-land-fast-hevc-off-g5 | 342468986 | 34231677 |
| baseline-land-std-h264-2x-g5-cleanup.json | p1e3d1/baseline-land-std-h264-2x-g5 | 477093518 | 168856209 |
| baseline-land-std-hevc-off-g5-cleanup.json | p1e3d1/baseline-land-std-hevc-off-g5 | 402010347 | 93773038 |
| baseline-long-perf-2-cleanup.json | p1e3d1/baseline-long-perf-2 | 972108742 | 663871433 |
| baseline-long-perf-3-cleanup-interrupted-1.json | p1e3d1/baseline-long-perf-3 | 944992575 | 636755266 |
| baseline-long-perf-3-cleanup.json | p1e3d1/baseline-long-perf-3 | 972107391 | 663870082 |
| baseline-port-fast-h264-off-g5-cleanup.json | p1e3d1/baseline-port-fast-h264-off-g5 | 339168511 | 30931202 |
| baseline-port-fast-hevc-2x-g5-cleanup.json | p1e3d1/baseline-port-fast-hevc-2x-g5 | 381206500 | 72969191 |
| baseline-port-std-h264-off-g5-cleanup.json | p1e3d1/baseline-port-std-h264-off-g5 | 413057655 | 104820346 |
| baseline-probe-1-cleanup.json | p1e3d1/baseline-probe-1 | 320364961 | 12127652 |
| baseline-probe-2-cleanup.json | p1e3d1/baseline-probe-2 | 320364961 | 12127652 |
| baseline-probe-3-cleanup.json | p1e3d1/baseline-probe-3 | 320364961 | 12127652 |
| baseline-standard-120-2-cleanup.json | p1e3d1/baseline-standard-120-2 | 932967713 | 663882933 |
| baseline-vfr-g5-cleanup.json | p1e3d1/baseline-vfr-g5 | 323099066 | 14861757 |
| c1-gpu-cut-g5-cleanup.json | p1e3d1/c1-gpu-cut-g5 | 311552184 | 3314875 |
| c1-gpu-land-fast-hevc-off-g5-cleanup.json | p1e3d1/c1-gpu-land-fast-hevc-off-g5 | 342469839 | 34232530 |
| c1-gpu-land-std-h264-2x-g5-cleanup.json | p1e3d1/c1-gpu-land-std-h264-2x-g5 | 476543022 | 168305713 |
| c1-gpu-land-std-hevc-off-g5-cleanup.json | p1e3d1/c1-gpu-land-std-hevc-off-g5 | 401974740 | 93737431 |
| c1-gpu-long-g5-cleanup.json | p1e3d1/c1-gpu-long-g5 | 971921094 | 663683785 |
| c1-gpu-long-perf-2-cleanup.json | p1e3d1/c1-gpu-long-perf-2 | 971932292 | 663694983 |
| c1-gpu-long-perf-3-cleanup-interrupted-1.json | p1e3d1/c1-gpu-long-perf-3 | 628213382 | 319976073 |
| c1-gpu-long-perf-3-cleanup.json | p1e3d1/c1-gpu-long-perf-3 | 971946923 | 663709614 |
| c1-gpu-port-fast-h264-off-g5-cleanup.json | p1e3d1/c1-gpu-port-fast-h264-off-g5 | 339169324 | 30932015 |
| c1-gpu-port-fast-hevc-2x-g5-cleanup.json | p1e3d1/c1-gpu-port-fast-hevc-2x-g5 | 381207351 | 72970042 |
| c1-gpu-port-std-h264-off-g5-cleanup.json | p1e3d1/c1-gpu-port-std-h264-off-g5 | 413022376 | 104785067 |
| c1-gpu-probe-1-cleanup.json | p1e3d1/c1-gpu-probe-1 | 320364961 | 12127652 |
| c1-gpu-probe-2-cleanup.json | p1e3d1/c1-gpu-probe-2 | 320364961 | 12127652 |
| c1-gpu-probe-3-cleanup.json | p1e3d1/c1-gpu-probe-3 | 320364961 | 12127652 |
| c1-gpu-vfr-g5-cleanup.json | p1e3d1/c1-gpu-vfr-g5 | 323096977 | 14859668 |
| cuda-streams-cut-g5-cleanup.json | p1e3d1/cuda-streams-cut-g5 | 311558049 | 3320740 |
| cuda-streams-land-fast-hevc-off-g5-cleanup.json | p1e3d1/cuda-streams-land-fast-hevc-off-g5 | 342469898 | 34232589 |
| cuda-streams-land-std-h264-2x-g5-cleanup.json | p1e3d1/cuda-streams-land-std-h264-2x-g5 | 476563829 | 168326520 |
| cuda-streams-land-std-hevc-off-g5-cleanup.json | p1e3d1/cuda-streams-land-std-hevc-off-g5 | 401989796 | 93752487 |
| cuda-streams-long-g5-cleanup.json | p1e3d1/cuda-streams-long-g5 | 972007513 | 663770204 |
| cuda-streams-long-perf-2-cleanup.json | p1e3d1/cuda-streams-long-perf-2 | 972010393 | 663773084 |
| cuda-streams-long-perf-3-cleanup.json | p1e3d1/cuda-streams-long-perf-3 | 971996802 | 663759493 |
| cuda-streams-port-fast-h264-off-g5-cleanup.json | p1e3d1/cuda-streams-port-fast-h264-off-g5 | 339169366 | 30932057 |
| cuda-streams-port-fast-hevc-2x-g5-cleanup.json | p1e3d1/cuda-streams-port-fast-hevc-2x-g5 | 381204427 | 72967118 |
| cuda-streams-port-std-h264-off-g5-cleanup.json | p1e3d1/cuda-streams-port-std-h264-off-g5 | 413039889 | 104802580 |
| cuda-streams-probe-1-cleanup.json | p1e3d1/cuda-streams-probe-1 | 320364961 | 12127652 |
| cuda-streams-probe-2-cleanup.json | p1e3d1/cuda-streams-probe-2 | 320364961 | 12127652 |
| cuda-streams-probe-3-cleanup.json | p1e3d1/cuda-streams-probe-3 | 320364961 | 12127652 |
| cuda-streams-vfr-g5-cleanup.json | p1e3d1/cuda-streams-vfr-g5 | 323099946 | 14862637 |
| final-compare-busy-1-cleanup.json | p1e3d1/final-compare-busy-1 | 349936065 | 41698756 |
| final-compare-busy-2-cleanup.json | p1e3d1/final-compare-busy-2 | 349936006 | 41698697 |
| final-compare-busy-3-cleanup.json | p1e3d1/final-compare-busy-3 | 349936803 | 41699494 |
| final-compare-idle-1-cleanup.json | p1e3d1/final-compare-idle-1 | 332002069 | 23764760 |
| final-compare-idle-2-cleanup.json | p1e3d1/final-compare-idle-2 | 332002073 | 23764764 |
| final-compare-idle-3-cleanup.json | p1e3d1/final-compare-idle-3 | 332002088 | 23764779 |
| gpu-cleanup.json | p1e3d1/gpu | 517106270 | 517106270 |
| trim-context-long-perf-1-cleanup.json | p1e3d1/trim-context-long-perf-1 | 970383487 | 662146178 |
| trim-context-long-perf-2-cleanup.json | p1e3d1/trim-context-long-perf-2 | 970383183 | 662145874 |
| trim-context-long-perf-3-cleanup.json | p1e3d1/trim-context-long-perf-3 | 970386167 | 662148858 |
| trim-context-probe-1-cleanup.json | p1e3d1/trim-context-probe-1 | 320318775 | 12081466 |
| trim-context-probe-2-cleanup.json | p1e3d1/trim-context-probe-2 | 320318775 | 12081466 |
| trim-context-probe-3-cleanup.json | p1e3d1/trim-context-probe-3 | 320318775 | 12081466 |
| warm-cut-g5-cleanup.json | p1e3d1/warm-cut-g5 | 311557918 | 3320609 |
| warm-land-fast-hevc-off-g5-cleanup.json | p1e3d1/warm-land-fast-hevc-off-g5 | 342469841 | 34232532 |
| warm-land-std-h264-2x-g5-cleanup.json | p1e3d1/warm-land-std-h264-2x-g5 | 476564004 | 168326695 |
| warm-land-std-hevc-off-g5-cleanup.json | p1e3d1/warm-land-std-hevc-off-g5 | 401992911 | 93755602 |
| warm-long-g5-cleanup.json | p1e3d1/warm-long-g5 | 971992841 | 663755532 |
| warm-long-perf-2-cleanup.json | p1e3d1/warm-long-perf-2 | 972010486 | 663773177 |
| warm-long-perf-3-cleanup.json | p1e3d1/warm-long-perf-3 | 972007329 | 663770020 |
| warm-port-fast-h264-off-g5-cleanup.json | p1e3d1/warm-port-fast-h264-off-g5 | 339169340 | 30932031 |
| warm-port-fast-hevc-2x-g5-cleanup.json | p1e3d1/warm-port-fast-hevc-2x-g5 | 381207301 | 72969992 |
| warm-port-std-h264-off-g5-cleanup.json | p1e3d1/warm-port-std-h264-off-g5 | 413036939 | 104799630 |
| warm-probe-1-cleanup.json | p1e3d1/warm-probe-1 | 320364961 | 12127652 |
| warm-probe-2-cleanup.json | p1e3d1/warm-probe-2 | 320364961 | 12127652 |
| warm-probe-3-cleanup.json | p1e3d1/warm-probe-3 | 320364961 | 12127652 |
| warm-vfr-g5-cleanup.json | p1e3d1/warm-vfr-g5 | 323099903 | 14862594 |

## Final Git verification

Read-only branch/HEAD/status and diff --check passed. The changed-file set exactly matches the 32 listed text/code files; AGENTS and CURRENT_TASK are unchanged. No Git mutation was run. final-git-readonly.json records exit codes, output and the nonfatal CRLF warnings.

## Owner summary

比較は初回8.46秒・完了29.10秒で目標を達成し、出力ハッシュも一致しました。
後続パートの起動は0.149秒です。C1常駐だけを採用し、出力が変わる処理は不採用にしました。
CPU702件・GPU101件などの検証がPASSしました。CPUの既存24件はSKIPとして区別しています。
分割線は60秒・3,598フレームで隙間0件、Escの動作も確認済みです。
今回の作業用ファイルは削除済みです。規約に従いcommit・pushは実施していません。
