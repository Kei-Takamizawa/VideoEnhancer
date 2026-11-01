Task ID: VE-P1e-3d2c
Status: COMPLETED
Cycle: 1 - Windows

## Result

Implemented worker/log lifetime fixes and the conditional, bounded History sharing-violation retry. Final HTTP repetition: 20 PASS / 0 FAIL / 0 SKIP. Full CPU: 740 PASS, 24 existing SKIP, 102 GPU deselected (422.57 s). Focused GPU: 1 PASS. G5 output SHA-256 matches the P1e-3d1 reference. All required checks passed. Three empty cache directories need owner deletion after sandbox ACL refusal; no refused delete was retried.

## Execution and scope

Windows PowerShell; local-env.ps1 was dot-sourced before every test/check. Initial read-only Git confirmed a clean tree on claude/project-thread-6lra47 at 1c16d76. Git was initially absent from the sandbox PATH, and its explicit executable was denied; approved read-only escalation succeeded. No Git mutation, commit, push, merge, calibration or additional gate jobs. CURRENT_TASK.md is unchanged. All explicit generated media, test homes, TEMP, pytest caches and evidence are within work. No owner normal app, media, queue or Recycle Bin was used.

## Cause and implementation

_child_run retained its Python log stream, CRT stdout/stderr duplicates and Windows native standard-output handles after a successful part. A reusable child can remain idle while those handles prevent Windows log deletion. Warm-child results are buffered until _child_run returns; cleanup now disables the part faulthandler target, flushes the log, restores Python/CRT/native streams, closes all saved descriptors and the log, and restores the inherited fault handler before publishing that result. Missing pythonw standard descriptors are preserved.

The scheduler previously retained the last successful part's worker through finalization and publication of done, closing it on a later loop. It now closes the worker when the final part completes, before saving completion or calling the next scheduler boundary. The no-pending-parts finalization entry also closes it defensively. Worker-parts metadata resets to zero. Existing worker identity, reuse count, invalidation, watchdog and retry rules are unchanged.

The first post-fix HTTP loop found a distinct WinError 32 on manifest.lock (run 10/20); it did not involve a part log. This is the measured reason for using task item 3. History removal/staging retries only WinError 32, at most five attempts with waits 0.05/0.10/0.20/0.40 s (0.75 s total). Other permission errors propagate immediately; persistent sharing failures propagate at the fifth attempt. This does not replace worker/log cleanup or change output preservation.

## Changed files

- src/videoenhancer/schedule/controller.py: per-part log handle cleanup; final-worker shutdown before boundary/finalization.
- src/videoenhancer/service/engine.py: measured optional History WinError 32 retry.
- tests/test_warm_worker.py: deterministic finalization/boundary regression, real log unlink checks, CUDA reuse/byte-identity coverage.
- tests/test_service.py: six removal/staging retry-bound/error/output-preservation cases.
- docs/part-worker-lifecycle.md: two lifecycle clarifications.
- .ai/LAST_REPORT.md: this report; the previous report and gate results remain below verbatim in content.

## Tests and evidence

Evidence root: evidence/VE-P1e-3d2c (private local artifacts, not staged).

| Check/run | Result | Evidence |
| --- | --- | --- |
| Preliminary sandbox HTTP loop | NOT_RUN as reproduction: 20 SKIP, FFmpeg unavailable | before-*.log |
| Real pre-fix HTTP loop | PASS 20/20; failure rate 0/20 | real-before-*.log, reproduction-summary.json |
| First added-test attempt | FAIL: incorrect quality-module fixture import; fixed before production edit | red.log |
| Corrected deterministic pre-fix regression | Expected FAIL: worker alive at boundary, assembly and done | red2.log |
| Real pre-fix regressions | Expected FAIL: lifecycle assertion and WinError 32 unlinking seg_00000.log | red-real.log |
| Focused post-fix CPU plus pythonw | PASS 19; 1 GPU deselected | green.log |
| Added GPU case, initial fixture | FAIL: NVENC initialization rejected tiny/lossless fixture | gpu.log |
| Corrected GPU worker case | PASS 1; 87 deselected | gpu2.log |
| First post-fix HTTP loop | FAIL overall: 19 PASS / 1 FAIL on manifest.lock | after-*.log |
| Retry regressions before implementation | Expected FAIL 4; 2 non-sharing cases PASS | retry-red.log |
| Retry regressions after implementation | PASS 6 | retry-green.log |
| Final HTTP loop | PASS 20/20, 0 FAIL, 0 SKIP | final-after-*.log, reproduction-summary.json |
| Full CPU: pytest -m "not gpu" | PASS 740; SKIP 24; 102 GPU deselected; 422.57 s | cpu.log, cpu.xml |
| Ruff check . | PASS | ruff-final.log |
| Ruff format --check . | PASS, 214 files already formatted | ruff-format-final.log |
| Pyright | PASS, 0 errors/warnings | pyright-final.log |
| Read-only independent code review | No actionable findings; no tests or edits by reviewer | review.txt |
| G5 | PASS, output SHA-256 identical; zero remaining children | g5-frozen.log, d2c-frozen-land-std-h264-g5.json |

The full CPU skips are unchanged environment requirements: 18 explicit verified standalone link tools, 3 OpenSSL/TLS fixtures, 2 private sample fixtures, and 1 Linux-only parent-death test. No test was disabled, skipped or weakened to obtain green. The added GPU case uses a supported 256x144 normal H.264 encode; the existing CPU lossless fixture and cold/warm byte-equality assertions remain intact. No other controller-related case has a GPU marker; the scoped GPU invocation did not run the full GPU suite. The full CPU suite reran the lifecycle, pythonw and retry cases on final code.

All pytest basetemp/cache paths were absolute work/scratch paths. Reproduction: after dot-sourcing local-env.ps1, run python -m pytest tests/test_service.py::test_cpu_queue_sse_controls_and_completed_output -q with a fresh contained --basetemp and -o cache_dir for each of 20 invocations. Focused GPU command selected test_warm_worker.py plus controller/finalization/reliability-related files with -m "gpu and not soak". The scoped GPU count was one.

## G5 byte identity

The 30 s 1920x1080/30fps testsrc2 + AAC fixture was recreated from the P1e-3d1 recipe. Input SHA-256 matched 0a9ce09ffa9f9f64a99f6768825675893d66c2a0fe1a0aeb0012e6c91d8c67e1. Standard, H.264, 2x output, batch 2 and both model identities match the historical reference.

The initial attempt was cancelled before completion because current automatic planning generated four parts; the P1e-3d1 reference used six. It is not a hash PASS or a speed measurement (g5.log and d2c-land-std-h264-g5.json retain the cancellation and zero remaining children). The qualified harness paused processing during preparation and used only the historical fixture's six boundaries: 0/162/324/486/648/810/900. Product planning was not changed. Reference hash/settings/models/boundaries are retained in g5-reference.json; the old report is archived at 9677557:.ai/LAST_REPORT.md. Qualified output SHA-256: 82cacf0478a6c6ee8704ee3b16c34efe48108960b3300fb5739793dc4b500679. It equals the P1e-3d1 reference. Output: 162184891 bytes; elapsed 911.708574 s (diagnostic only, not a performance gate); shutdown 0.000471 s; remaining child PIDs: [].

## GUI, warnings and intentional omissions

GUI: NOT_RUN, not requested for this engine lifecycle cycle. No GUI or owner app was launched. No full GPU suite, calibration, prediction gate, performance gate, package build or extra feature was run. No commit/push was made; the operator owns Git writes.

Early default pytest-cache creation printed sandbox ACL warnings. Later checks used dedicated contained scratch cache paths. An intermediate static check flagged two added test lines for formatting/line length; formatting was corrected, then all final static checks passed. Git diff --check passed; Git noted the expected docs LF-to-CRLF normalization warning.

## Workspace, cleanup and unresolved items

| Additional cleanup candidate | Logical bytes before removal |
| --- | ---: |
| scratch\home | 0 |
| scratch\videoenhancer.jsonl | 14902 |

Measured before removal; hard-linked model sizes are logical lengths, not allocated or additional storage.

| Cleanup candidate | Logical bytes before removal |
| --- | ---: |
| scratch\d2c-after-1 | 0 |
| scratch\d2c-after-10 | 0 |
| scratch\d2c-after-11 | 0 |
| scratch\d2c-after-12 | 0 |
| scratch\d2c-after-13 | 0 |
| scratch\d2c-after-14 | 0 |
| scratch\d2c-after-15 | 0 |
| scratch\d2c-after-16 | 0 |
| scratch\d2c-after-17 | 0 |
| scratch\d2c-after-18 | 0 |
| scratch\d2c-after-19 | 0 |
| scratch\d2c-after-2 | 0 |
| scratch\d2c-after-20 | 0 |
| scratch\d2c-after-3 | 0 |
| scratch\d2c-after-4 | 0 |
| scratch\d2c-after-5 | 0 |
| scratch\d2c-after-6 | 0 |
| scratch\d2c-after-7 | 0 |
| scratch\d2c-after-8 | 0 |
| scratch\d2c-after-9 | 0 |
| scratch\d2c-before-1 | 0 |
| scratch\d2c-before-10 | 0 |
| scratch\d2c-before-11 | 0 |
| scratch\d2c-before-12 | 0 |
| scratch\d2c-before-13 | 0 |
| scratch\d2c-before-14 | 0 |
| scratch\d2c-before-15 | 0 |
| scratch\d2c-before-16 | 0 |
| scratch\d2c-before-17 | 0 |
| scratch\d2c-before-18 | 0 |
| scratch\d2c-before-19 | 0 |
| scratch\d2c-before-2 | 0 |
| scratch\d2c-before-20 | 0 |
| scratch\d2c-before-3 | 0 |
| scratch\d2c-before-4 | 0 |
| scratch\d2c-before-5 | 0 |
| scratch\d2c-before-6 | 0 |
| scratch\d2c-before-7 | 0 |
| scratch\d2c-before-8 | 0 |
| scratch\d2c-before-9 | 0 |
| scratch\d2c-cpu | 0 |
| scratch\d2c-cpu-cache | 0 |
| scratch\d2c-final-after-1 | 0 |
| scratch\d2c-final-after-10 | 0 |
| scratch\d2c-final-after-11 | 0 |
| scratch\d2c-final-after-12 | 0 |
| scratch\d2c-final-after-13 | 0 |
| scratch\d2c-final-after-14 | 0 |
| scratch\d2c-final-after-15 | 0 |
| scratch\d2c-final-after-16 | 0 |
| scratch\d2c-final-after-17 | 0 |
| scratch\d2c-final-after-18 | 0 |
| scratch\d2c-final-after-19 | 0 |
| scratch\d2c-final-after-2 | 0 |
| scratch\d2c-final-after-20 | 0 |
| scratch\d2c-final-after-3 | 0 |
| scratch\d2c-final-after-4 | 0 |
| scratch\d2c-final-after-5 | 0 |
| scratch\d2c-final-after-6 | 0 |
| scratch\d2c-final-after-7 | 0 |
| scratch\d2c-final-after-8 | 0 |
| scratch\d2c-final-after-9 | 0 |
| scratch\d2c-g5 | 803807877 |
| scratch\d2c-gpu | 0 |
| scratch\d2c-gpu2 | 0 |
| scratch\d2c-green | 0 |
| scratch\d2c-pytest-cache | 0 |
| scratch\d2c-pytest-gpu-cache | 0 |
| scratch\d2c-real-before-1 | 0 |
| scratch\d2c-real-before-10 | 0 |
| scratch\d2c-real-before-11 | 0 |
| scratch\d2c-real-before-12 | 0 |
| scratch\d2c-real-before-13 | 0 |
| scratch\d2c-real-before-14 | 0 |
| scratch\d2c-real-before-15 | 0 |
| scratch\d2c-real-before-16 | 0 |
| scratch\d2c-real-before-17 | 0 |
| scratch\d2c-real-before-18 | 0 |
| scratch\d2c-real-before-19 | 0 |
| scratch\d2c-real-before-2 | 0 |
| scratch\d2c-real-before-20 | 0 |
| scratch\d2c-real-before-3 | 0 |
| scratch\d2c-real-before-4 | 0 |
| scratch\d2c-real-before-5 | 0 |
| scratch\d2c-real-before-6 | 0 |
| scratch\d2c-real-before-7 | 0 |
| scratch\d2c-real-before-8 | 0 |
| scratch\d2c-real-before-9 | 0 |
| scratch\d2c-red | 0 |
| scratch\d2c-red-real | 0 |
| scratch\d2c-red2 | 0 |
| scratch\d2c-retry-green | 0 |
| scratch\d2c-retry-red | 0 |
| scratch\tmp | 5895136 |
| scratch\jobs | 0 |
| scratch\p1e3c2-native | 0 |
| evidence\VE-P1e-3d1 | 162013132 |

| Disk metric (decimal GB) | First readable snapshot | End |
| --- | ---: | ---: |
| C free | 346.570441 | 346.562896 |
| D free | 876.163748 | 876.332007 |
| package logical size | 0.125289 | 0.125289 |
| evidence/VE-P1e-3d2c logical size | 0.001613 | 0.004516 |
| scratch logical size | 0.048233 | 0.042232 |
| cache logical size | 11.385460 | 11.385460 |

The first readable snapshot was taken after preliminary reproduction/setup, not before any command. End evidence size excludes only this tiny final inventory/report metadata. Conservative persistent growth upper bound (complete current-cycle evidence plus positive package/cache deltas): 0.004516 GB, below 1 GB. This deliberately does not credit old evidence deletion. Evidence is below 300 MB, cache below 40 GB, and only VE-P1e-3d2 / VE-P1e-3d2b / VE-P1e-3d2c cycle evidence remains.

Measured logical bytes removed: 971731047. Each removed item's independently measured byte count equals its inventory row above, with individual outcomes in cleanup-results.json and cleanup-additional-results.json. Hard-linked model names contribute logical lengths without implying equivalent recovered physical space. The removed oldest evidence directory was 162013132 bytes; its required report remains in Git at 9677557 and the G5 reference is retained in this cycle. Drive-wide free-space changes are not attributed to these deletions.

### For the owner to delete

| Exact path | Remaining bytes | Reason |
| --- | ---: | --- |
| D:/my-workspace/VideoEnhancer/work/scratch/d2c-cpu-cache | 0 | WinError 5: Access is denied |
| D:/my-workspace/VideoEnhancer/work/scratch/d2c-pytest-cache | 0 | WinError 5: Access is denied |
| D:/my-workspace/VideoEnhancer/work/scratch/d2c-pytest-gpu-cache | 0 | WinError 5: Access is denied |

All three are empty directories. No retry, elevated delete, ACL change or other bypass was attempted. Pre-existing scratch/owner-check (42232471 bytes) was preserved. Every cycle-created file and isolated job home was removed; scratch therefore contains those protected prior fixtures and the three refused empty directories. All started test runners and G5 processes exited; qualified and cancelled G5 reports both show no remaining child PIDs. No designer decision is needed for implementation. No automatic approval rejection occurred.


## Japanese summary

最終パート後にワーカーを終了し、パートごとのPython・CRT・Windowsログハンドルを解放しました。
別途実測したmanifest.lock競合には、WinError 32限定・合計待機0.75秒の再試行を追加しました。
最終HTTP検証20/20、CPU 740件、対象GPU 1件がPASSし、G5のSHA-256も参照値と一致しました。
削除拒否された空のキャッシュ3フォルダーは残し、所有者向け削除対象として記録しました。commit・pushは未実施です。

## Preserved VE-P1e-3d2b report (historical results)

Task ID: VE-P1e-3d2b
Status: COMPLETED
Cycle: 1 - Windows

## Result and scope

Implemented the approved calibration and scheduling-reader fixes, and replaced stale finalization points with independent measurements. The prediction formula, existing 15% margin, model/preset settings, GPU admission and output pipeline are unchanged. Revision remains `p1e3d2-warm1`; no field meaning changed. No gate result supplied a fit point or scaling factor.

Windows PowerShell and repo/local-env.ps1 were used. Initial Git was clean on `claude/project-thread-6lra47` at `5e7c4967e91e2df9310e884d54deb19920a88c18`. Read-only Git needed approved escalation after sandbox denial. No Git mutation, commit, push or merge. CURRENT_TASK.md was preserved. Explicit test homes, media, TEMP and output paths were contained in work; owner app data/media/queue and the Recycle Bin were not accessed.

The usage-limit stop rejected G-Fin launch before execution because approval review could not complete. Resume verified hashes and completed results and did not repeat them. G-Fin was first launched only after that resume.

## Items 1-3 and regression tests

Missing NVDEC samples are synthesized with FFmpeg (H264 720x1280, HEVC 1080x1920) and removed in the temporary-directory lifetime; an eligible VE_SAMPLES_DIR override is preserved. FFmpeg fallback portrait width/height were corrected. P0 now forwards analyzed source_pts and keyframes. Planner and next-unit admission call the shared cold_parts rule; no admission policy changed.

New regression file: 15 PASS, including a no-samples calibration report with a non-null decode coefficient (fake decoder, other benchmark dependencies isolated), override preservation, portrait fallback dimensions, P0 metadata, incomplete-input guards, and Standard/Fast planner/admission predictions within 1 s of estimate_job for worker counts 0/23/49/50. Six original regression cases failed before production fixes; an additional startup-null guard red run had 1 expected failure before correction.

The first full CPU invocation had 1 failure, 732 PASS, 24 SKIP, 101 deselected (401.29 s): an existing fixed-duration test stub did not accept the new approved cold keyword. Only its signature was changed to require that keyword; every assertion, including the hours-gap completion time, is unchanged. The failed case plus the unchanged driver-change test passed (2 PASS, 1.44 s). The final full CPU result is listed below. `test_driver_change_preserves_first_estimate` was not loosened.

## Part A - complete calibration

| Selected run | Benchmark wall s | Root PID | State |
| --- | --- | --- | --- |
| calibration-complete-1retry | 259.856371 | 6072 | done |
| calibration-complete-2 | 259.814330 | 8924 | done |
| calibration-complete-3 | 259.818053 | 20660 | done |

All three selected reports have no skipped section or null component coefficient. H264/HEVC decode, installed models, 1080/1440 reference points, cold/warm startup and P0 end-to-end were measured. Analysis cost is the median of P0 analysis seconds/input frames, rather than an unmeasured retained term. Raw reports are retained separately; selected/aggregate diagnostic arrays are not a fourth calibration.

The incomplete initial calibration-complete-1 attempt skipped HEVC because of synthetic-clip output-option ordering; it was excluded and only that incomplete attempt was rerun. Warm startup spreads above 10% are flagged below (Standard 48.079%, Fast 10.606%). Their absolute ranges are small, but their cause was not established; no valid observation was discarded. Main means the prior 38b41ae baseline; P1e-3d2 is the frozen prior candidate. Unit costs are s/(pixel-frame), analysis s/input-frame, load/startup seconds, factors dimensionless. Null remains visibly unmeasured.

| Term | Main 38b41ae | P1e-3d2 | Run 1 | Run 2 | Run 3 | New median | Spread % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| components.decode.seconds_per_pixel_frame | 5.7699797e-10 | null / unmeasured | 7.6283999e-10 | 7.604924e-10 | 7.7071239e-10 | 7.6283999e-10 | 1.340 |
| components.encode.seconds_per_pixel_frame | 2.5921192e-09 | 2.7027786e-09 | 2.6758415e-09 | 2.7193456e-09 | 2.6618787e-09 | 2.6758415e-09 | 2.148 |
| components.encode.size_points[0].seconds_per_pixel_frame | 2.5921192e-09 | 2.7027786e-09 | 2.6758415e-09 | 2.7193456e-09 | 2.6618787e-09 | 2.6758415e-09 | 2.148 |
| components.encode.size_points[1].seconds_per_pixel_frame | N/A | 2.5814146e-09 | 2.5813106e-09 | 2.5814295e-09 | 2.581288e-09 | 2.5813106e-09 | 0.005 |
| components.color.seconds_per_pixel_frame | 3.9930556e-10 | 3.9996646e-10 | 3.9846709e-10 | 4.003709e-10 | 3.9720447e-10 | 3.9846709e-10 | 0.795 |
| components.color.size_points[0].seconds_per_pixel_frame | 3.9930556e-10 | 3.9996646e-10 | 3.9846709e-10 | 4.003709e-10 | 3.9720447e-10 | 3.9846709e-10 | 0.795 |
| components.color.size_points[1].seconds_per_pixel_frame | N/A | 5.2879654e-10 | 5.2768736e-10 | 5.2932099e-10 | 5.2721716e-10 | 5.2768736e-10 | 0.399 |
| components.resize.seconds_per_pixel_frame | 3.0686969e-10 | 3.0565202e-10 | 3.0536265e-10 | 3.0560378e-10 | 3.0475984e-10 | 3.0536265e-10 | 0.276 |
| components.resize.size_points[0].seconds_per_pixel_frame | 3.0686969e-10 | 3.0565202e-10 | 3.0536265e-10 | 3.0560378e-10 | 3.0475984e-10 | 3.0536265e-10 | 0.276 |
| components.resize.size_points[1].seconds_per_pixel_frame | N/A | 3.012424e-10 | 3.0126953e-10 | 3.0123562e-10 | 3.0156793e-10 | 3.0126953e-10 | 0.110 |
| components.blend2x.seconds_per_pixel_frame | 1.765408e-10 | 1.7678192e-10 | 1.7639612e-10 | 1.763479e-10 | 1.7623939e-10 | 1.763479e-10 | 0.089 |
| components.blend2x.size_points[0].seconds_per_pixel_frame | 1.765408e-10 | 1.7678192e-10 | 1.7639612e-10 | 1.763479e-10 | 1.7623939e-10 | 1.763479e-10 | 0.089 |
| components.blend2x.size_points[1].seconds_per_pixel_frame | N/A | 1.9584825e-10 | 1.9533285e-10 | 1.9537354e-10 | 1.9552951e-10 | 1.9537354e-10 | 0.101 |
| models.basicvsrpp-denoise.load_seconds | N/A | 1.4896891 | 1.4961549 | 1.4662469 | 1.4605389 | 1.4662469 | 2.429 |
| models.basicvsrpp-denoise.seconds_per_pixel_frame | N/A | 9.1263766e-08 | 9.2213723e-08 | 9.2192781e-08 | 9.2256764e-08 | 9.2213723e-08 | 0.069 |
| models.basicvsrpp-ntire21-decompress.load_seconds | 1.6541103 | 0.3333497 | 0.3233299 | 0.3340264 | 0.3285637 | 0.3285637 | 3.256 |
| models.basicvsrpp-ntire21-decompress.seconds_per_pixel_frame | 2.6231761e-07 | 2.5258818e-07 | 2.5642038e-07 | 2.5641761e-07 | 2.5655663e-07 | 2.5642038e-07 | 0.054 |
| models.rife-4.25.load_seconds | N/A | N/A | 0.2052049 | 0.2009442 | 0.196919 | 0.2009442 | 4.123 |
| models.rife-4.25.seconds_per_pixel_frame | N/A | N/A | 2.2554253e-08 | 2.2542643e-08 | 2.2562826e-08 | 2.2554253e-08 | 0.089 |
| models.rife-4.25.size_points[0].seconds_per_pixel_frame | N/A | N/A | 2.2554253e-08 | 2.2542643e-08 | 2.2562826e-08 | 2.2554253e-08 | 0.089 |
| models.rife-4.25.size_points[1].seconds_per_pixel_frame | N/A | N/A | 2.5734287e-08 | 2.5761146e-08 | 2.5770877e-08 | 2.5761146e-08 | 0.142 |
| pipeline_size_points.standard[0].factor | 1.0546985 | 0.98783325 | 0.99517128 | 0.99607463 | 0.99777654 | 0.99607463 | 0.262 |
| pipeline_size_points.standard[1].factor | N/A | 0.99072568 | 0.99941221 | 0.99977281 | 0.99763697 | 0.99941221 | 0.214 |
| pipeline_size_points.fast[0].factor | 1.3839229 | 0.9437582 | 0.99485172 | 0.99022101 | 0.9925303 | 0.9925303 | 0.467 |
| pipeline_size_points.fast[1].factor | N/A | 0.9536644 | 0.98157819 | 0.98035925 | 0.97993291 | 0.98035925 | 0.168 |
| startup_by_preset.standard.cold | 4.4917327 | 3.5047662 | 4.0589475 | 4.0595756 | 4.0525625 | 4.0589475 | 0.173 |
| startup_by_preset.standard.warm | 4.4917327 | 0.09317025 | 0.10280845 | 0.09441735 | 0.0574131 | 0.09441735 | 48.079 FLAG |
| startup_by_preset.fast.cold | 2.5475333 | 1.7486575 | 2.0015829 | 1.9560243 | 2.0334407 | 2.0015829 | 3.868 |
| startup_by_preset.fast.warm | 2.5475333 | 0.2118056 | 0.19093345 | 0.1999446 | 0.2121394 | 0.1999446 | 10.606 FLAG |
| analysis_seconds_per_frame | 0.0010458961 | 0.0010458961 | 0.00303586 | 0.003031696 | 0.003015418 | 0.003031696 | 0.674 |

## Part B - finalization diagnosis and independent curve

| Minutes | Repeat 1 s | Repeat 2 s | Repeat 3 s | Median s | Spread % | Parts | Output GB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2.269619 | 2.358738 | 2.221002 | 2.269619 | 6.068670 | 4 | 0.230381 |
| 10 | 18.999986 | 19.310670 | 19.517600 | 19.310670 | 2.680455 | 41 | 2.303428 |
| 30 | 56.666381 | 56.595501 | 56.595189 | 56.595501 | 0.125792 | 123 | 6.910245 |
| 120 | 370.976045 | 370.371202 | 369.873257 | 370.371202 | 0.297752 | 490 | 27.639137 |

Qualified replay uses genuine independent Standard C1 templates at all five production-planned lengths (198/351/360/441/477 input frames), distinct physical part files, AAC and shifted genuine quality partials. These are finalization fixtures, not 120-minute neural-inference runs. G-10 and its files were not used. A real primed ProcessExecutor worker remained resident for every timed repetition; PID/creation-time and RSS were recorded and checked. Normal OS cache was retained; no system cache flush or filesystem change. Small points had very little machine-wide physical read I/O; 120-minute data exceeded available cache and incurred substantial reads. Counters are machine-wide, not exclusive process attribution.

curve-independent-1 failed before measuring a point (standalone output path lacked real job directory structure). After that fix, curve-independent-2 completed 12 diagnostic samples but closed its worker before finalization. All of that round is preserved as curve-no-resident-*.json and was excluded. The qualified round reused genuine rendered inputs, primed/retained the worker, and measured all 12 points. Neither correction repeated a gate or a completed calibration.

| Historical minutes | Reported parts | Reported output GB | Reported finalization s |
| --- | --- | --- | --- |
| 1.000000 | 5 | 0.241988 | 1.192158 |
| 30.000000 | 125 | 7.266596 | 32.541377 |
| 120.000000 | 499 | 29.066175 | 324.243313 |

| Dataset | Parts | Input part lengths | Scene cuts | Clip joints | Statistics JSON bytes |
| --- | --- | --- | --- | --- | --- |
| G-10 recorded | 40 | [449, 489] | 0 | 1604 | 5974524 |
| independent 10-minute replay | 41 | [360, 441] | 0 | 1592 | 6108028 |

These small count/byte differences do not explain a 12x aggregation event. Recorded G-10 core quality work was 0.350034 s versus its full aggregation event 1.020755 s: 0.670721 s was surrounding durable orchestration. The old modeled aggregation term was about 0.080180 s. Current independent 10-minute core time is much smaller than the recorded G-10 core; its exact historical CPU/execution-context cause is not established.

| Independent payload | Manifest bytes (median) | Core s | Event s | Full begin/end s |
| --- | --- | --- | --- | --- |
| full | 9649409 | 0.034504 | 0.687334 | 1.024592 |
| quality-only | 2839572 | 0.032713 | 0.262994 | 0.392525 |

The ablation asserted identical quality results in every repetition. Large real part statistics increase durable aggregation cost independently of the quality calculation. It is diagnostic only and never entered the fit. Whole-event aggregation values, not just aggregate_quality timing, populate the new curve. Existing frame interpolation, byte-scaled concat/mux/faststart, per-part checkpoint/aggregation scaling and 15% margin are retained; no formula-shape change was necessary. Tiny calibration still preserves the long curve.

Mux/proc/aggregate_quality are text-identical to dc02580; timer/input identity and principal JobStore methods are AST-identical. Historical reports recorded D as exFAT shortly after P1e-2; current C/D are NTFS. Exact old per-sample filesystem/cache/co-tenancy records were not retained, and their absence was already documented at 5e7ca8c. Current independent I/O reproduces the slower G-10 scale, but filesystem, cache and Defender contributions to the historical gap cannot be uniquely separated. A pre-existing VideoEnhancer process and Defender were observed via process counters only; no owner process was closed or data opened, and current activity is not proof of historical activity.

## Part C - gate results

Saved first-estimate reconstruction matched all three old values exactly (0 seconds difference). Recomputed rows retain the recorded actual times. The old live-50% record lacks the full progress snapshot required for exact recomputation, so a fresh G-10 is used only for that gate. New milestone snapshots preserve complete forecast inputs. Errors are (prediction/actual - 1); live error uses actual remaining wall time, including any gap.

Saved live forecasts reconstructed with their original schedule and timestamp: 25% difference 0.0 s; 50% difference 0.0 s; 75% difference 0.0 s.

| Gate | Old prediction s | New prediction s | Actual s | Error % | Limit % | Result |
| --- | --- | --- | --- | --- | --- | --- |
| G-10 first estimate | 7031.175321 | 7171.102949 | 7231.999843 | -0.842048 | 10 | PASS |
| G-10 first finish time | 8135.560352 | 8185.410483 | 8325.686472 | -1.684858 | 10 | PASS |
| G-10 finalization raw curve | 12.071394 | 20.115408 | 19.322049 | 4.105977 | 25 | PASS |
| G-1440-attempt2 first estimate | 419.621055 | 428.702457 | 431.469408 | -0.641286 | 15 | PASS |
| G-Fast first estimate | 241.563686 | 238.802022 | 221.467330 | 7.827200 | 10 | PASS |
| G-Fin first estimate | N/A | 3587.638332 | 3683.269546 | -2.596368 | 10 | PASS |
| G-Fin finalization raw curve | N/A | 10.246754 | 10.015149 | 2.312547 | 25 | PASS |
| G-10 live finish at 50% (fresh run) | N/A | 4661.570461 | 4688.767990 | -0.580057 | 5 | PASS |

### Archived G-10 first estimate part data

| Part | Input frames | Actual startup kind | Old first prediction s | New first prediction s | Actual s |
| --- | --- | --- | --- | --- | --- |
| 0 | 449 | cold | 178.178334 | 181.266641 | 182.493363 |
| 1 | 449 | warm | 174.766738 | 177.302111 | 179.261055 |
| 2 | 449 | warm | 174.766738 | 177.302111 | 179.132681 |
| 3 | 449 | warm | 174.766738 | 177.302111 | 179.006893 |
| 4 | 449 | warm | 174.766738 | 177.302111 | 179.113368 |
| 5 | 449 | warm | 174.766738 | 177.302111 | 179.032539 |
| 6 | 449 | warm | 174.766738 | 177.302111 | 178.960810 |
| 7 | 449 | warm | 174.766738 | 177.302111 | 179.017324 |
| 8 | 449 | warm | 174.766738 | 177.302111 | 178.983175 |
| 9 | 449 | warm | 174.766738 | 177.302111 | 179.146343 |
| 10 | 449 | warm | 174.766738 | 177.302111 | 178.904486 |
| 11 | 449 | warm | 174.766738 | 177.302111 | 179.080779 |
| 12 | 449 | warm | 174.766738 | 177.302111 | 179.021717 |
| 13 | 449 | warm | 174.766738 | 177.302111 | 178.975100 |
| 14 | 449 | warm | 174.766738 | 177.302111 | 178.939388 |
| 15 | 449 | warm | 174.766738 | 177.302111 | 179.298984 |
| 16 | 449 | warm | 174.766738 | 177.302111 | 178.941024 |
| 17 | 449 | warm | 174.766738 | 177.302111 | 179.167673 |
| 18 | 449 | warm | 174.766738 | 177.302111 | 179.030486 |
| 19 | 449 | warm | 174.766738 | 177.302111 | 179.198260 |
| 20 | 449 | warm | 174.766738 | 177.302111 | 179.061221 |
| 21 | 449 | warm | 174.766738 | 177.302111 | 179.128606 |
| 22 | 449 | warm | 174.766738 | 177.302111 | 179.050233 |
| 23 | 449 | warm | 174.766738 | 177.302111 | 179.311385 |
| 24 | 449 | warm | 174.766738 | 177.302111 | 179.273441 |
| 25 | 449 | cold | 174.766738 | 177.302111 | 183.248517 |
| 26 | 449 | warm | 174.766738 | 177.302111 | 179.179485 |
| 27 | 449 | warm | 174.766738 | 177.302111 | 179.315682 |
| 28 | 449 | warm | 174.766738 | 177.302111 | 178.913555 |
| 29 | 449 | warm | 174.766738 | 177.302111 | 179.044989 |
| 30 | 449 | warm | 174.766738 | 177.302111 | 179.327860 |
| 31 | 449 | warm | 174.766738 | 177.302111 | 178.979803 |
| 32 | 449 | warm | 174.766738 | 177.302111 | 179.034494 |
| 33 | 449 | warm | 174.766738 | 177.302111 | 178.791855 |
| 34 | 449 | warm | 174.766738 | 177.302111 | 178.970856 |
| 35 | 449 | warm | 174.766738 | 177.302111 | 178.896603 |
| 36 | 449 | warm | 174.766738 | 177.302111 | 179.249167 |
| 37 | 449 | warm | 174.766738 | 177.302111 | 179.204827 |
| 38 | 449 | warm | 174.766738 | 177.302111 | 178.946758 |
| 39 | 489 | warm | 190.327858 | 193.088988 | 194.606623 |

### Archived G-1440-attempt2 first estimate part data

| Part | Input frames | Actual startup kind | Old first prediction s | New first prediction s | Actual s |
| --- | --- | --- | --- | --- | --- |
| 0 | 381 | cold | 179.032912 | 182.390890 | 183.072591 |
| 1 | 381 | warm | 175.621316 | 178.426360 | 179.822894 |
| 2 | 138 | warm | 63.670294 | 64.687089 | 65.037236 |

### Archived G-Fast first estimate part data

| Part | Input frames | Actual startup kind | Old first prediction s | New first prediction s | Actual s |
| --- | --- | --- | --- | --- | --- |
| 0 | 1800 | cold | 119.352984 | 114.451517 | 106.666962 |
| 1 | 1800 | warm | 117.816132 | 112.649879 | 104.718223 |

### G-Cal

| Number | Seconds / result |
| --- | --- |
| before_raw | 10.246754 |
| predicted | 10.246754 |
| before_with_local_learning | 10.015149 |
| with_local_learning | 10.015149 |
| actual | 10.015149 |
| raw_unchanged | True |
| points_unchanged | True |
| samples_unchanged | True |

Calibration ran in the same home after G-Fin. The learned number is a separate diagnostic from the just-completed job; it does not establish the raw-curve gate.

### G-Fin part data

| Part | Actual startup kind | Initial prediction s | Admitted prediction s | Actual s | Startup s |
| --- | --- | --- | --- | --- | --- |
| 0 | cold | 178.109266 | 178.109266 | 181.771535 | 3.711321 |
| 1 | warm | 174.144735 | 175.218961 | 179.467719 | 0.258501 |
| 2 | warm | 174.144735 | 176.493588 | 179.025680 | 0.207460 |
| 3 | warm | 174.144735 | 177.253216 | 179.049223 | 0.078672 |
| 4 | warm | 174.144735 | 177.792018 | 178.956212 | 0.082620 |
| 5 | warm | 174.144735 | 178.141276 | 179.081374 | 0.041164 |
| 6 | warm | 174.144735 | 178.423306 | 179.098238 | 0.066323 |
| 7 | warm | 174.144735 | 178.625785 | 179.329788 | 0.225825 |
| 8 | warm | 174.144735 | 178.836986 | 179.295002 | 0.188940 |
| 9 | warm | 174.144735 | 178.974391 | 179.393719 | 0.257024 |
| 10 | warm | 174.144735 | 179.100189 | 179.379466 | 0.180178 |
| 11 | warm | 174.144735 | 179.183972 | 179.234753 | 0.084856 |
| 12 | warm | 174.144735 | 179.199207 | 179.189174 | 0.127860 |
| 13 | warm | 174.144735 | 179.196197 | 179.289853 | 0.138537 |
| 14 | warm | 174.144735 | 179.224294 | 179.419338 | 0.240512 |
| 15 | warm | 174.144735 | 179.282807 | 179.114443 | 0.091916 |
| 16 | warm | 174.144735 | 179.232298 | 179.324745 | 0.157227 |
| 17 | warm | 174.144735 | 179.260032 | 179.206784 | 0.070132 |
| 18 | warm | 174.144735 | 179.244058 | 179.229184 | 0.238663 |
| 19 | warm | 174.144735 | 179.239595 | 179.329327 | 0.280845 |
| 20 | warm | 71.135364 | 73.227529 | 73.062698 | 0.190899 |

Finalization steps: `{"checkpoint_validation_seconds": 0.24295299999357667, "concat_reused": false, "concat_seconds": 2.6275056000013137, "faststart_seconds": 2.261398000002373, "mux_seconds": 2.6065633999969577, "quality_aggregation_seconds": 0.011477600011858158, "validation_seconds": 0.9241088999988278}`.

### G-10 fresh live run part data

| Part | Actual startup kind | Initial prediction s | Admitted prediction s | Actual s | Startup s |
| --- | --- | --- | --- | --- | --- |
| 0 | cold | 178.109266 | 178.109266 | 181.536687 | 3.579687 |
| 1 | warm | 174.144735 | 175.150075 | 179.538165 | 0.252554 |
| 2 | warm | 174.144735 | 176.466502 | 179.323858 | 0.267048 |
| 3 | warm | 174.144735 | 177.323709 | 179.007291 | 0.031409 |
| 4 | warm | 174.144735 | 177.828783 | 179.131422 | 0.109808 |
| 5 | warm | 174.144735 | 178.219575 | 179.255414 | 0.078559 |
| 6 | warm | 174.144735 | 178.530327 | 179.258766 | 0.021898 |
| 7 | warm | 174.144735 | 178.748858 | 179.198477 | 0.065521 |
| 8 | warm | 174.144735 | 178.883744 | 179.006594 | 0.110296 |
| 9 | warm | 174.144735 | 178.920599 | 179.322956 | 0.050125 |
| 10 | warm | 174.144735 | 179.041306 | 179.191670 | 0.041202 |
| 11 | warm | 174.144735 | 179.086415 | 178.921975 | 0.034705 |
| 12 | warm | 174.144735 | 179.037083 | 179.067920 | 0.169880 |
| 13 | warm | 174.144735 | 179.046334 | 179.257894 | 0.028445 |
| 14 | warm | 174.144735 | 179.109802 | 179.298713 | 0.188813 |
| 15 | warm | 174.144735 | 179.166475 | 179.196174 | 0.145772 |
| 16 | warm | 174.144735 | 179.175385 | 179.374981 | 0.188363 |
| 17 | warm | 174.144735 | 179.235264 | 179.631562 | 0.268383 |
| 18 | warm | 174.144735 | 179.354153 | 178.997599 | 0.101200 |
| 19 | warm | 174.144735 | 179.247187 | 179.278478 | 0.104297 |
| 20 | warm | 174.144735 | 179.256574 | 179.378656 | 0.243996 |
| 21 | warm | 174.144735 | 179.293199 | 179.367026 | 0.307696 |
| 22 | warm | 174.144735 | 179.315347 | 179.241192 | 0.268250 |
| 23 | warm | 174.144735 | 179.293100 | 179.269367 | 0.166201 |
| 24 | warm | 174.144735 | 179.285980 | 179.255407 | 0.177553 |
| 25 | warm | 174.144735 | 179.276808 | 179.341560 | 0.219275 |
| 26 | warm | 174.144735 | 179.296234 | 179.237002 | 0.122629 |
| 27 | warm | 174.144735 | 179.278464 | 178.953540 | 0.063690 |
| 28 | warm | 174.144735 | 179.180987 | 179.318461 | 0.289523 |
| 29 | cold | 174.144735 | 183.302352 | 183.588800 | 3.970245 |
| 30 | warm | 174.144735 | 179.306251 | 179.182114 | 0.127587 |
| 31 | warm | 174.144735 | 179.269010 | 179.458621 | 0.174940 |
| 32 | warm | 174.144735 | 179.325893 | 179.113071 | 0.218426 |
| 33 | warm | 174.144735 | 179.262046 | 179.304389 | 0.234746 |
| 34 | warm | 174.144735 | 179.274749 | 179.247261 | 0.186686 |
| 35 | warm | 174.144735 | 179.266503 | 179.055830 | 0.044322 |
| 36 | warm | 174.144735 | 179.203301 | 179.197655 | 0.124580 |
| 37 | warm | 174.144735 | 179.201607 | 179.188317 | 0.141498 |
| 38 | warm | 174.144735 | 179.197620 | 179.151124 | 0.040824 |
| 39 | warm | 174.144735 | 179.183671 | 179.429900 | 0.393120 |
| 40 | warm | 142.176310 | 146.350537 | 145.138208 | 0.242477 |

Finalization steps: `{"checkpoint_validation_seconds": 0.07205360000079963, "concat_reused": false, "concat_seconds": 5.237645699991845, "faststart_seconds": 4.53523559999303, "mux_seconds": 5.166391500009922, "quality_aggregation_seconds": 0.03574279999884311, "validation_seconds": 1.761484799993923}`.

| Milestone | Actual sampled % | Finish error s | Remaining-time error % |
| --- | --- | --- | --- |
| 25 | 25.058106 | -29.710410 | -0.455379 |
| 50 | 50.058862 | -27.197529 | -0.580057 |
| 75 | 75.050255 | -18.232620 | -0.977707 |

Archived per-part old/new predictions and actuals are retained in recomputed-gates.json, including cold/warm kinds; no failed gate was retuned or rerun on its result.

G-Fin's first saved segmented-manifest finalization prediction was 2.478800 s, before actual output bytes were available. The raw finalization gate uses the production finalization-entry prediction with known part output sizes, as for the archived G-10 gate. It is not replaced by the learned value. The earlier prediction is disclosed separately and is not claimed to meet the finalization gate.

### Output audits

G-Fin: `[{"avg_frame_rate": "60/1", "codec_name": "hevc", "codec_type": "video", "duration": "300.000000", "height": 1920, "nb_read_packets": "18000", "width": 1080}, {"avg_frame_rate": "0/0", "codec_name": "aac", "codec_type": "audio", "duration": "300.000000", "nb_read_packets": "14064"}]`. FFprobe packet-count audit; audio and final assembly also passed production validation.

G-10-attemptlive: `[{"avg_frame_rate": "60/1", "codec_name": "hevc", "codec_type": "video", "duration": "600.000000", "height": 1920, "nb_read_packets": "36000", "width": 1080}, {"avg_frame_rate": "0/0", "codec_name": "aac", "codec_type": "audio", "duration": "600.000000", "nb_read_packets": "28126"}]`. FFprobe packet-count audit; audio and final assembly also passed production validation.

## Required checks and process closure

| Check | Result | Root PID | Wall s | Evidence |
| --- | --- | --- | --- | --- |
| Full CPU suite | PASS | 3448 | 397.030488 | check-cpu-final.log |
| Full GPU suite: gpu and not soak | PASS | 16088 | 13585.586829 | check-gpu-final.log |
| Pyright | PASS | 16212 | 11.175699 | check-pyright.log |
| GUI lint | PASS | 7196 | 13.740270 | check-gui-lint.log |
| Vitest | PASS | 21168 | 26.981752 | check-vitest.log |

Ruff check PASS; Ruff format --check PASS (171 files). Final CPU: 733 PASS, 24 existing SKIP, 101 GPU deselected, 395.87 s; unchanged driver-change test PASS. GUI lint/Pyright/Vitest remain valid on unchanged production/GUI source (Vitest 86 tests / 18 files). Existing skips are not counted as PASS. Actual GUI/Computer Use, packaging, frontend build and CI were NOT_RUN because not requested; no GUI change was made.

CPU skip reasons: 18 require explicitly supplied verified standalone link tools; 3 require a local TLS/OpenSSL fixture; 1 is a Linux parent-death test; 2 require private VE_SAMPLES_DIR clips. No skip was introduced. Vitest printed a jsdom environment performance advisory; no configuration was changed to silence it.

Final read-only Git verification: HEAD remains 5e7c4967e91e2df9310e884d54deb19920a88c18; only the 13 listed task files differ (7 tracked, 6 new). git diff --check exited 0. Git printed the existing LF-to-CRLF conversion advisory for docs/estimate-startup.md; no whitespace error was reported. No media, models, packages, caches or runtime output were added to Git.

GPU final: 101 PASS, 0 FAIL/error, 0 SKIP across 101 cases; single uninterrupted invocation recorded in check-gpu-final.log and gpu-final.xml.

- G-Fin: root 15484, state done, sampled children [468, 2132, 2564, 2624, 3848, 4068, 5044, 8944, 9108, 9292, 9320, 11040, 11464, 13556, 16168, 20104, 20856, 22240, 22292], remaining [].
- G-10-attemptlive: root 22020, state done, sampled children [3028, 9404, 10992, 11412, 12656, 14048, 14340, 14552, 14928, 15728, 17344, 17852, 18352, 19884, 20680, 22016], remaining [].
- curve-resident-1: root 13520, state done, sampled children [300, 1844, 2164, 2796, 3080, 3220, 4120, 4168, 4584, 5456, 5668, 6016, 6192, 6308, 7064, 7148, 7196, 7908, 8076, 8516, 9388, 9820, 9884, 10552, 10620, 10836, 11388, 11476, 11492, 11496, 12540, 13952, 14420, 14456, 14800, 15020, 15160, 15248, 15332, 15412, 15476, 15900, 16092, 16112, 16224, 16240, 16368, 16480, 16532, 17424, 18428, 18752, 20552, 20604, 20680, 20756, 20872, 21308], remaining [].

All cycle-run process ledgers (including unsuccessful attempts):

| Run | Root PID | Result | Remaining PIDs |
| --- | --- | --- | --- |
| calibration-complete-1 | 8772 | done | [] |
| calibration-complete-1retry | 6072 | done | [] |
| calibration-complete-2 | 8924 | done | [] |
| calibration-complete-3 | 20660 | done | [] |
| curve-independent-1 | 6768 | failed | [] |
| curve-independent-2 | 13968 | done | [] |
| curve-resident-1 | 13520 | done | [] |
| G-10-attemptlive | 22020 | done | [] |
| G-Fin | 15484 | done | [] |


Earlier calibration/diagnostic/check ledgers preserve all starts, homes, PIDs and outcomes. Python curve-resident-1 exit 0 was captured by a live Windows process wait (monitor PID 5712). PowerShell *> incorrectly marks its pipeline false on stderr even with Python exit 0 (synthetic probe preserved). Outer tool exits were 1 for the earlier standalone calibration/curve commands; their old native exits were NOT_CAPTURED, so those outer commands are not relabeled exit 0. Selected complete component reports remain usable data. Compound calibration-2/3 and static check commands exited 0. Future gates explicitly save LASTEXITCODE; no bypass of automatic review occurred.

## Disk, cleanup and retention

All sizes below are decimal GB from logical file lengths, not allocated storage. Overlapping rows are not added. Hardlink unlinking is not claimed to free the same physical byte count.

The initial disk-start PowerShell probe returned null; pristine task-start free space is NOT_CAPTURED. The earliest valid inventory was taken after calibration began (inventory-start.json), so it is explicitly a delayed reference. No historical numbers were reconstructed.

| Drive | At task start | Earliest valid delayed reference GB | End free GB |
| --- | --- | --- | --- |
| C | NOT_CAPTURED | 348.563509 | 346.585113 |
| D | NOT_CAPTURED | 876.223648 | 876.170416 |

| Folder | Before cleanup GB | End GB |
| --- | --- | --- |
| package | 0.125289 | 0.125289 |
| evidence/VE-P1e-3d2b | 0.065205 | 0.065225 |
| scratch | 8.176024 | 0.048139 |
| cache | 11.385460 | 11.385460 |

Cycle-end permanent cleanup candidates and results (recorded in LAST_REPORT.md before deletion):

| Contained path | Bytes before | GB before | Confirmed removed logical bytes | Result |
| --- | --- | --- | --- | --- |
| scratch\p1e3d2b | 8127110451 | 8.127110 | 8127110451 | REMOVED |
| scratch\p1e3d2b-baseline | 774442 | 0.000774 | 774442 | REMOVED |
| scratch\p1e3d2b-focused | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-focused2 | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-focused3 | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-green2 | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-guard-green | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-presets | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-pytest | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-pytest-green | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-report-test | 0 | 0.000000 | 0 | REMOVED |
| scratch\p1e3d2b-tests | 0 | 0.000000 | 0 | REMOVED |
| scratch\jobs\aa383b494c3841c1957ca36446a430d6 | 1 | 0.000000 | 1 | REMOVED |
| evidence\VE-P1e-3c2-F3 | 2013029 | 0.002013 | 2013029 | REMOVED |

The old VE-P1e-3c2-F3 report was verified at Git 937e937 before removing its private evidence. The three retained development cycles are VE-P1e-3d1, VE-P1e-3d2, VE-P1e-3d2b; owner-check-trial is separate pre-existing owner-check evidence and was preserved.

Earlier finalization replay cleanup was recorded per file before unlinking; the following batches are independent of the final directory cleanup. Generated outputs were separately measured in their run rows, unlinked immediately, and are not included twice in the final directory inventory.

| Per-file cleanup ledger | Recorded bytes | GB | All paths absent |
| --- | --- | --- | --- |
| curve-1-0-cleanup.json | 229812471 | 0.229812 | True |
| curve-1-1-cleanup.json | 229812471 | 0.229812 | True |
| curve-1-2-cleanup.json | 229812471 | 0.229812 | True |
| curve-10-0-cleanup.json | 2297762546 | 2.297763 | True |
| curve-10-1-cleanup.json | 2297762546 | 2.297763 | True |
| curve-10-2-cleanup.json | 2297762546 | 2.297763 | True |
| curve-120-0-cleanup.json | 27568475781 | 27.568476 | True |
| curve-120-1-cleanup.json | 27568475781 | 27.568476 | True |
| curve-120-2-cleanup.json | 27568475781 | 27.568476 | True |
| curve-30-0-cleanup.json | 6892578696 | 6.892579 | True |
| curve-30-1-cleanup.json | 6892578696 | 6.892579 | True |
| curve-30-2-cleanup.json | 6892578696 | 6.892579 | True |
| curve-no-resident-1-0-cleanup.json | 229812471 | 0.229812 | True |
| curve-no-resident-1-1-cleanup.json | 229812471 | 0.229812 | True |
| curve-no-resident-1-2-cleanup.json | 229812471 | 0.229812 | True |
| curve-no-resident-10-0-cleanup.json | 2297762546 | 2.297763 | True |
| curve-no-resident-10-1-cleanup.json | 2297762546 | 2.297763 | True |
| curve-no-resident-10-2-cleanup.json | 2297762546 | 2.297763 | True |
| curve-no-resident-120-0-cleanup.json | 27568475781 | 27.568476 | True |
| curve-no-resident-120-1-cleanup.json | 27568475781 | 27.568476 | True |
| curve-no-resident-120-2-cleanup.json | 27568475781 | 27.568476 | True |
| curve-no-resident-30-0-cleanup.json | 6892578696 | 6.892579 | True |
| curve-no-resident-30-1-cleanup.json | 6892578696 | 6.892579 | True |
| curve-no-resident-30-2-cleanup.json | 6892578696 | 6.892579 | True |
| curve-no-resident-source-1-cleanup.json | 8079394 | 0.008079 | True |
| curve-no-resident-source-10-cleanup.json | 80759334 | 0.080759 | True |
| curve-no-resident-source-120-cleanup.json | 968994656 | 0.968995 | True |
| curve-no-resident-source-30-cleanup.json | 242262118 | 0.242262 | True |
| curve-source-1-cleanup.json | 8079394 | 0.008079 | True |
| curve-source-10-cleanup.json | 80759334 | 0.080759 | True |
| curve-source-120-cleanup.json | 968994656 | 0.968995 | True |
| curve-source-30-cleanup.json | 242262118 | 0.242262 | True |

| curve-runs.json output | Removed logical bytes | GB |
| --- | --- | --- |
| 1m repeat 0 | 230380848 | 0.230381 |
| 1m repeat 1 | 230380848 | 0.230381 |
| 1m repeat 2 | 230380848 | 0.230381 |
| 10m repeat 0 | 2303427647 | 2.303428 |
| 10m repeat 1 | 2303427647 | 2.303428 |
| 10m repeat 2 | 2303427647 | 2.303428 |
| 30m repeat 0 | 6910244954 | 6.910245 |
| 30m repeat 1 | 6910244954 | 6.910245 |
| 30m repeat 2 | 6910244954 | 6.910245 |
| 120m repeat 0 | 27639136892 | 27.639137 |
| 120m repeat 1 | 27639136892 | 27.639137 |
| 120m repeat 2 | 27639136892 | 27.639137 |

| curve-no-resident-runs.json output | Removed logical bytes | GB |
| --- | --- | --- |
| 1m repeat 0 | 230380848 | 0.230381 |
| 1m repeat 1 | 230380848 | 0.230381 |
| 1m repeat 2 | 230380848 | 0.230381 |
| 10m repeat 0 | 2303427647 | 2.303428 |
| 10m repeat 1 | 2303427647 | 2.303428 |
| 10m repeat 2 | 2303427647 | 2.303428 |
| 30m repeat 0 | 6910244954 | 6.910245 |
| 30m repeat 1 | 6910244954 | 6.910245 |
| 30m repeat 2 | 6910244954 | 6.910245 |
| 120m repeat 0 | 27639136892 | 27.639137 |
| 120m repeat 1 | 27639136892 | 27.639137 |
| 120m repeat 2 | 27639136892 | 27.639137 |

Persistent-growth attribution: a pristine pre-task allocation inventory is unavailable. A conservative upper bound counts all retained evidence and all remaining scratch (including pre-existing content), full repo file lengths created/modified since the earliest cycle evidence timestamp, and the larger of positive delayed-reference growth or full new/modified file lengths for cache/package, plus 1 MB for final reports. This is an attribution bound, not an exact drive allocation delta.

| Upper-bound term | Bytes | GB |
| --- | --- | --- |
| all_retained_evidence | 255931559 | 0.255932 |
| all_remaining_scratch | 48139467 | 0.048139 |
| repo_new_or_modified | 277549 | 0.000278 |
| measurement_report_allowance | 1000000 | 0.001000 |
| cache | 0 | 0.000000 |
| package | 0 | 0.000000 |
| Total | 305348575 | 0.305349 |

| Budget / closure | Result |
| --- | --- |
| evidence | PASS |
| cache | PASS |
| persistent_growth | PASS |
| retention | PASS |
| cycle_scratch_empty | PASS |
| inventory_complete | PASS |

All cycle-owned scratch roots are removed when cycle_scratch_empty is PASS. Global scratch is not empty: pre-existing/shared entries were preserved to protect other work. Remaining entries:

| Shared/pre-existing scratch | Bytes | GB |
| --- | --- | --- |
| scratch/jobs | 0 | 0.000000 |
| scratch/owner-check | 42232471 | 0.042232 |
| scratch/p1e3c2-native | 0 | 0.000000 |
| scratch/tmp | 5895136 | 0.005895 |
| scratch/videoenhancer.jsonl | 11860 | 0.000012 |

Inventory errors: `[]`. No refused deletion was retried or bypassed.

### For the owner to delete

None of this cycle's confirmed cleanup targets remain.

## Questions for the designer / deliberate boundaries

Use current independent measurements and the existing formula/revision, preserving historical uncertainty rather than guessing an exact cache/Defender cause. Keep failed and unqualified attempts visible. No model/manifest/preset/default, GPU policy, player, Compare, GUI, packaging/CI/LGPL or C17 change. Source/profile freeze is verified. Git actions remain the operator's responsibility.

## Changed files

- .ai/LAST_REPORT.md
- docs/estimate-startup.md
- src/videoenhancer/bench/runner.py
- src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json
- src/videoenhancer/schedule/controller.py
- src/videoenhancer/schedule/planner.py
- gui/scripts/estimate-complete-check.py
- gui/scripts/estimate-complete-cycle.py
- gui/scripts/estimate-finalization-curve.py
- gui/scripts/estimate-recompute.py
- gui/scripts/estimate-aggregation-cost.py
- tests/test_complete_calibration.py
- tests/test_p1e.py

## Owner summary

校正の未測定項目とcold/warm参照を修正し、独立データで最終化曲線を更新しました。
現時点の判定はCOMPLETEDです。未完了項目はPASSとして扱っていません。
失敗・条件不一致の試行と、過去のキャッシュ状態を確認できない点も記録しています。
commit・push・mergeは行っていません。
