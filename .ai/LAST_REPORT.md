# VE-P1e-3a final implementation and verification report

- Task ID / Cycle: VE-P1e-3a / P1e-3a.
- Status: COMPLETED. A4 accepted; C17 follows the explicitly authorized two-pass/defer branch in section 12.2. Only final Windows/Ubuntu CI remains for the operator.
- Windows x64 / PowerShell. Branch claude/project-thread-6lra47, resumed HEAD db6b392c9047cbf1b13b38868120921746b07c50. Existing uncommitted work preserved. No Git mutation, commit, push or merge.
- AGENTS.md and the complete CURRENT_TASK.md, especially section 12, were reread. CURRENT_TASK.md was not edited. Evidence names below are relative to work/evidence/VE-P1e-3a. Prior full reports are retained as section12/pre-section12-report.md and pre-ci-report.md; old partial conclusions are superseded here.

## Final verification

| Check | Actual result | Evidence |
|---|---|---|
| Full Windows CPU, CI command and base handling | 690 PASS / 3 SKIP / 101 deselected / 0 FAIL / 0 ERROR; 597.22 s, exit 0 | section12/ci-cpu-final.log |
| DASH and other real local link-download cases in full CPU | All 14 PASS, including test_direct_download_remux[dash] | Same full CPU log; link-download module has 14 PASS markers and no skip/failure |
| Related memory/model/trial/source-index regressions | 60 PASS / 15 GPU deselected; 32.37 s | section12/ci-related.log |
| Ruff / format | PASS; 162 files formatted | section12/ci-python-static-final.log |
| Pyright Windows target / Linux target | Both PASS, 0 errors/warnings | Same static log; --pythonplatform Linux is a local static check, not an Ubuntu runtime run |
| Full final GPU, gpu and not soak | 101 passed, 693 deselected in 16845.45s (4:40:45) | section12/gpu-ci-final.log; gpu-checkpoint.json; gpu-session-result.json |
| Rebuilt package and isolated startup/renderer/shutdown smoke | Build PASS; 1 test PASS in 6.0 s | section12/ci-package-build.log; ci-package-smoke.log; ci-package-delivery.json |
| Hosted Windows / Ubuntu CI | PENDING operator commit/push | No hosted green claim |

CPU command exactly matches CI: `uv run pytest -m "not gpu and not soak" --basetemp=.venv/testtmp`. The latest user's explicit CI-base requirement overrides the usual scratch-only basetemp for this verification. Per-test TEMP/TMP/implicit home remain outside the repository under scratch; fixtures themselves use pytest's requested CI base. UV_NO_SYNC=1 retains installed GPU extras without dependency synchronization. Verified cached tools and a synthetic localhost certificate enable real local DASH/TLS tests. Three genuine skips are the Linux-only death boundary and two prohibited owner-sample cases. One nonfatal stale pytest-cache permission warning was retained; that cache was subsequently removed in the sandbox. No test was weakened or skipped to pass.

GPU command: `.venv/Scripts/python.exe -u -B -m pytest -m "gpu and not soak" -vv -p no:cacheprovider --basetemp=../scratch/p1e3a-section12/gpu-ci-final`, with its own VE_HOME. All 101 ran fresh after the CI fixes; source/test fingerprints were checked throughout. The initial-helper run stopped deliberately at 16 PASS, and the next run was interrupted by the operator launcher's exit at 17 PASS around 20:47 (not a usage limit). Neither contributed acceptance nodes; diagnostics and interruption/cleanup JSON remain.

## CI failures, fixes and failed attempts

1. Linux-target pyright reproduced exactly five unknown api/counters attribute errors (ci-linux-pyright-before.log). Explicit class declarations for api, query and counters make them visible when the Windows-only initializer is unreachable. Windows behavior is unchanged.
2. CI-style basetemp reproduced existing unsafe parameter-name setup errors: 7 PASS / 5 ERROR in focused manifest cases (ci-path-before.log). Sanitize only the folder basename to A-Z/a-z/0-9/_/-, bound it to 50 characters, and keep pytest's numbered uniqueness. Slash, backslash, colon and quote IDs/test bodies remain unchanged.
3. The first CI-shaped full run then exposed another helper issue: 13 FAIL / 677 PASS / 3 SKIP in 596.51 s (ci-cpu-first.log). TEMP inside .venv put trial outputs inside the repository, correctly triggering the product's protection. Keep that guard; place TEMP and implicit home in scratch and clean both owned roots. The new full CPU run passes all 690.
4. Earlier naive fixture teardown: 690 assertion PASS / 3 SKIP / 94 teardown ERROR (93 open-log WinError32, one still-mocked os.walk TypeError), section12/cpu-full.log. Run cleanup after all finalizers/monkeypatch restoration and close only test-owned FileHandlers. Corrected scratch-base full CPU: 690 PASS / 3 SKIP in 606.37 s (cpu-final.log), superseded for final CI-base acceptance by ci-cpu-final.log. Initial related run before the trial-temp correction: 43 PASS / 2 deselected, ci-related-first.log.

Other historical full CPU attempts remain failed, not acceptance: 11 FAIL / 505 PASS / 176 SKIP in 367.12 s (sandbox tool/process availability), and 688 PASS / 1 FAIL / 3 SKIP (native fallback-reason regression, fixed before the 690-PASS safe-default run). Full original details remain in section12/pre-section12-report.md. The report whitespace check initially found a new blank line at EOF after final generation; trimmed to one terminating newline and rechecked, with no source/test change.

## Section 12 decisions and cleanup cause

A4 is done under 12.1: counter-only direct PDH maximum .8811 ms meets <=50 ms; whole-record 95.0115 ms is accepted on the sampler thread. Both stats remain. No sampling behavior was changed by the annotation fix.

C17 adoption failed: the indexed-VFR fixture has no deterministic differences, but a 120-second 1920x1080 SDR HEVC hard cut at frame 3598 changes scene_cuts from [] to [3598] and scene_scores. Last-15-frame Standard 1080 2x G5 bytes also differ: old SHA 3c7f7c6d06c93fe48cb091a554a5ea8a69eb1167ecf5ba3e4c1d3ad69d80e44e, candidate eb0a5340273b77acbad29963929dfb2448c7f966786f9191ad98bff4a4018f39. Both adoption conditions fail. Keep the two-pass product default, delete precisely the two nonshipping one-pass cases, and defer C17 to P1e-3d as 12.2 directs. Remaining exhaustive candidate/G5 comparisons were NOT RUN after the decisive failure; no every-fixture claim. Full analysis/plan/stats diff: section12/c17-adoption-gate.json; indexed-vfr-comparison.json.

Historical cleanup failures were caused by private creator ACLs retained by staged model manifests from TemporaryDirectory(mode 0o700), deliberately protected discovery tokens, and retained Windows log handles. Reproduced manifest/token files were not read-only and had one link; no general hard-link claim. Product credential ACLs remain unchanged. Controlled trial contexts inherit ACLs; per-test dirs use inherited permissions, isolate temp/home, and are deleted by their creator after all finalizers release handles. Private-file/token and open-log probes PASS, folder absent from sandbox; final full CPU/GPU have zero cleanup errors. Ignored local-env.ps1 creates configured TEMP before Python starts, preventing fallback to owner temp after scratch was emptied.

CI's framework-private .venv/testtmp was empty (0 bytes, 0 children) after exit and was removed on its first creator-account attempt; sandbox read access had been denied, not a deletion attempt. No refused delete was retried, escalated or bypassed.

## Retained GUI/Rust/P2 evidence and package

No GUI/Rust source changed since 59a4897; retain the accepted checks under 12.3: GUI lint/typecheck/unit/build PASS (66 unit tests in 13 files), full e2e 21 PASS / 13 existing opt-in SKIP, whole unreadable-record spec 50 repetitions =100 PASS, no retry. Rust fmt/clippy default and e2e PASS, 28 unit tests PASS in each configuration. Baseline native red tests failed compilation against missing helpers (E0425), not runtime assertions. P2 remains exactly five idle launches: Home median 729.040039 ms <=765 ms, first paint 729.722168 ms <=1000 ms. These were not represented as new executions.

Because delivered Python source changed, the package was rebuilt with fixed offline dependencies; candidate smoke passed before replacement. Current package: 2 files, 5,764,162 bytes; EXE 5,764,096 bytes, SHA-256 c821eb70e314e2e587ec0c06a04b8f7bb4915462c16b3ce502c0a88710b598ec. Duplicate candidate removed. Nonfatal warnings: frontend chunk size, Node NO_COLOR/FORCE_COLOR; PowerShell renders Cargo stderr as NativeCommandError records despite successful exit 0. No new behavior/UI/native test hook was added.

## Per-item acceptance

| Item | Status | Before / after evidence |
|---|---|---|
| A1 | done | Historical overlapping and invalid autograd harness attempts disclosed; corrected isolated five-configuration stage/whole tables above. |
| A2 | done | Both allocator trials SHA-identical; expandable segments kept, empty-cache stage trial not kept. Whole reserved peaks and every run above. |
| A3 | done | c84ce1a memory-test collection fails (budget module absent); current fake OOM-order/budget/unsupported-cap tests PASS, capped GPU runs PASS. |
| A4 | done | Counter latency max .8811 ms; whole-record ancillary-statistics outlier 95.011 ms disclosed. Spill/watchdog/learning/details tests PASS. Calibration tests: c84ce1a 2 FAIL, current 2 PASS (`baseline-calibration.log`, `resume-calibration-final.log`). Section 12.1 accepts both timings; the <=50 ms gate applies to the counter query only. |
| A5 | done | Two idle cap parts no spill and <=1.3x predicted, two strict G5 SHA matches; first competing adaptation FAIL preserved, corrected 2 GB-load adaptation PASS; helpers exited 0. |
| B | done | c84ce1a startup 31 FAIL/5 PASS; current 36 PASS, including full Engine.start and unchanged damaged bytes. Native pointer red tests fail to compile on baseline; current native suite PASS. |
| C1 | done | New cap path tests restore/half-clip, RIFE and decoder-retried OOM; one uncapped rerun; pipeline decoder retry decision retained. |
| C2 | done | Runtime FFmpeg/reason preserved; baseline focused regression FAIL, current PASS (`baseline-resume-tests.log`, `resume-focused.log`). |
| C3 | done | Synthetic 12-bit accepted by baseline analysis, refused now with exact reason; 8/10-bit accepted. Add-preview/API and legacy next-start/unchanged finished History: 10 current tests PASS (`resume-admission-final.log`). |
| C4 | done | Removal eligibility rejects empty/protected/changed/missing files; current Rust test PASS. Baseline lacks eligibility helper (compile-time red test). |
| C5 | done | Recovered-location reason differs from legacy reason; current Rust test PASS; baseline helper absent. |
| C6 | done | Sentence result and separate Copy details; current native sentence test PASS; baseline helper absent. |
| C7 | done | Unavailable drive returns without clearing pointer; native drive test PASS; baseline helper absent. |
| C8 | done | Per-file and byte progress callback; native callback test PASS; final CPU e2e real storage operations PASS. Baseline progress helper absent. |
| C9 | done | Refuse second Move, preserve previous record; native test PASS; baseline guard helper absent. |
| C10 | done | Metadata-only confirmation and one hash pass; native hash-count test PASS; baseline helper/hook absent. |
| C11 | done | Same verified byte buffer installed; substitution regression baseline FAIL/current PASS in link-tool tests. |
| C12 | not reproduced | Existing guard already refuses install/uninstall during link checks and downloads; both cases tested, code left in force. |
| C13 | done | Bad audio alternative baseline FAIL/current PASS. Follow-up pre-fix HEAD real DASH + metadata regressions 2 FAIL; preserved fix yields real downloader 13 PASS/1 SKIP, video-links 23 PASS, final CPU 690 PASS/3 SKIP. |
| C14 | done | Pre-rename durable identity and case-insensitive finished-name recovery; baseline FAIL/current PASS (`baseline-extra.log`, `resume-finalfocused.log`). |
| C15 | done | Downloaded-analysis interruption returns to resumable downloading state and preserves finished input; baseline FAIL/current PASS in resume tests. |
| C16 | done | Reuse compares same rounded width; baseline FAIL/current PASS in resume tests. |
| C17 | done / deferred per 12.2 | New 120-second 1080p counterexample changes scene cuts and G5 bytes. Keep two-pass; delete the two nonshipping one-pass cases; defer optimization to P1e-3d. Full diff and SHA hashes: section12/c17-adoption-gate.json. |
| C18 | done | Baseline GUI title is raw ID and test FAIL; current dated Unreadable title and ID Copy test PASS. |
| C19 | done | Timing-observation stamp invalidates link estimate cache; baseline FAIL/current PASS in focused minor tests. |
| D | done | Historical closure unknown accepted by 11.3; internal copy path plus real clipboard unit retained. Whole spec repeated 50 times: 100 PASS. Failure-only bounded CI artifacts and e2e close/crash/exit timestamps added. |
| P2 | done | Exactly 5 idle launches; Home-ready median 729.040 ms, first paint 729.722 ms; both gates PASS. |

Native baseline evidence is explicitly a compile failure of new regression tests against missing helpers, not executed runtime assertions. Full CPU e2e: 21 PASS/13 pre-existing opt-in SKIP. Opt-in owner/GPU/visual fixtures were not represented as PASS. Hosted final Windows/Ubuntu CI remains pending operator commit/push.


## Implementation

- Per-part free-dedicated budget, measured 330,301,440-byte reserve, existing half-clip retry followed by one uncapped rerun, and explicit statistics. WDDM requires the minimum of NVML device-free and CUDA free: the first competing-load experiment proved CUDA free alone was unchanged by another process.
- Direct ctypes PDH sampling every second, PowerShell only on direct-query failure, sticky spill detection, watchdog wall-limit scaling with no-frame timeout retained, exclusion from timing learning/calibration, and a persistent copyable details notice.
- Guarded startup JSON reads, independent damaged-record isolation, once-per-file diagnostic notices, session defaults, and refusal to overwrite damaged settings/control/cache records. Strict History behavior retained.
- Runtime decoder preservation, exact high-depth admission, strict native counts and evaluation of first-decode thumbnails (C17 deferred after EOF mismatch), resumable downloaded-video analysis, case-insensitive post-rename recovery, rounded reuse width, eligible audio selection, same verified tool bytes, refreshed link estimates and unreadable-folder dates.
- Storage eligibility/recovery/unavailable-drive messages, progress, plain result sentences with Copy details, second-Move refusal, metadata-only confirmation followed by one hash pass.
- e2e-only copy capture retained; real native clipboard round trip remains tested. Native close/destroy and CDP close/crash/exit events include timestamps. CI failure evidence is bounded below 100 MB and retained seven days; no retries, skips or changed failure status.


## Accepted isolated GPU measurements (prior execution, retained)



Decimal GB; 15-frame stage harness, 30-frame production parts from the same synthetic 120-second 1080p source. No concurrent GPU workload during these measurements. Peaks of different counters need not occur at the same instant. Non-Torch is the maximum simultaneous dedicated minus reserved, floored at zero.



| Configuration | Stage | Allocated GB | Reserved GB | Dedicated GB | Shared GB | Non-Torch GB | Seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| fast-1440-2x | decode | 0.375343 | 0.471859 | 0.602812 | 0.079692 | 0.130953 | 0.274 |
| fast-1440-2x | resize | 1.223492 | 1.224737 | 1.355694 | 0.079692 | 0.130957 | 0.041 |
| fast-1440-2x | rife | 2.146023 | 3.577741 | 3.710816 | 0.081789 | 0.133075 | 1.474 |
| fast-1440-2x | encode | 0.809222 | 0.836764 | 0.969822 | 0.081789 | 0.133059 | 0.507 |
| standard-1080-2x | decode | 0.375343 | 0.471859 | 0.602812 | 0.079692 | 0.130953 | 0.280 |
| standard-1080-2x | restore | 5.264183 | 5.280629 | 5.428400 | 0.081789 | 0.147771 | 10.163 |
| standard-1080-2x | resize | 0.195144 | 0.499122 | 0.646865 | 0.081789 | 0.147743 | 0.002 |
| standard-1080-2x | rife | 1.252985 | 2.006974 | 2.156827 | 0.081789 | 0.149852 | 0.673 |
| standard-1080-2x | encode | 0.462638 | 0.499122 | 0.648962 | 0.081789 | 0.149840 | 0.372 |
| standard-1080-keep | decode | 0.375343 | 0.471859 | 0.602812 | 0.079692 | 0.130953 | 0.278 |
| standard-1080-keep | restore | 5.264183 | 5.280629 | 5.428400 | 0.081789 | 0.147771 | 10.172 |
| standard-1080-keep | resize | 0.195144 | 0.499122 | 0.646865 | 0.081789 | 0.147743 | 0.001 |
| standard-1080-keep | encode | 0.276014 | 0.499122 | 0.646865 | 0.081789 | 0.147743 | 0.299 |
| standard-1440-2x | decode | 0.375343 | 0.471859 | 0.602812 | 0.079692 | 0.130953 | 0.274 |
| standard-1440-2x | restore | 5.264183 | 5.280629 | 5.428400 | 0.081789 | 0.147771 | 10.157 |
| standard-1440-2x | resize | 1.231989 | 1.537212 | 1.684963 | 0.081789 | 0.147751 | 0.038 |
| standard-1440-2x | rife | 2.152610 | 3.321889 | 3.471745 | 0.081789 | 0.149856 | 1.350 |
| standard-1440-2x | encode | 0.815841 | 1.163919 | 1.313763 | 0.081789 | 0.149844 | 0.505 |
| standard-1440-keep | decode | 0.375343 | 0.471859 | 0.602812 | 0.079692 | 0.130953 | 0.276 |
| standard-1440-keep | restore | 5.264183 | 5.280629 | 5.428400 | 0.081789 | 0.147771 | 10.160 |
| standard-1440-keep | resize | 1.231989 | 1.537212 | 1.684963 | 0.081789 | 0.147751 | 0.038 |
| standard-1440-keep | encode | 0.484377 | 0.499122 | 0.646865 | 0.081789 | 0.147743 | 0.370 |
| fast-1440-2x | whole | 2.129534 | 2.862612 | 3.177165 | 0.146350 | 0.314552 | 7.419 |
| standard-1080-2x | whole | 5.946309 | 7.396655 | 7.664943 | 0.140657 | 0.268288 | 36.234 |
| standard-1080-keep | whole | 5.749339 | 7.067402 | 7.335686 | 0.126312 | 0.268284 | 32.207 |
| standard-1440-2x | whole | 6.198569 | 7.474250 | 7.803519 | 0.146350 | 0.329269 | 37.331 |
| standard-1440-keep | whole | 5.874337 | 6.197084 | 6.526353 | 0.146350 | 0.329269 | 32.492 |



Maximum direct profiler sample cost: 1.602 ms.



## Whole-part option and cap runs



| Evidence | Status | Reserved GB | Dedicated GB | Shared GB | Spilled | Cap | OOM half retries | Uncapped reruns | Seconds | SHA-256 |
|---|---|---:|---:|---:|---|---|---:|---:|---:|---|
| fast-1440-2x-whole-clean.json | PASS | 2.862612 | 3.177165 | 0.146350 | n/a | off | 0 | 0 | 7.419 | 7b2d5d1c3182e7608ff37c8a491bf01b1d8080fecf4c40482be31378b0efe13c |
| standard-1080-2x-whole-clean.json | PASS | 7.396655 | 7.664943 | 0.140657 | n/a | off | 0 | 0 | 36.234 | b87fd4d5e3ccd448a9019644be2221457c9d2d4a77e68548416fd0517f954f6e |
| standard-1080-2x-whole-empty-cache.json | PASS | 7.367295 | 7.635583 | 0.126312 | n/a | off | 0 | 0 | 36.227 | b87fd4d5e3ccd448a9019644be2221457c9d2d4a77e68548416fd0517f954f6e |
| standard-1080-2x-whole-expandable.json | PASS | 6.035603 | 6.303883 | 0.126312 | n/a | off | 0 | 0 | 36.246 | b87fd4d5e3ccd448a9019644be2221457c9d2d4a77e68548416fd0517f954f6e |
| standard-1080-keep-whole-clean.json | PASS | 7.067402 | 7.335686 | 0.126312 | n/a | off | 0 | 0 | 32.207 | 108e09d66b71f68bc623c051003baaca2d3b9cd57d53409fbdd6eedf1a78267a |
| standard-1440-2x-whole-clean.json | PASS | 7.474250 | 7.803519 | 0.146350 | n/a | off | 0 | 0 | 37.331 | de24189345bed2d98063afc9e2cc1d9d1f05cfc357d4006b724cf383102a1c59 |
| standard-1440-2x-whole-empty-cache.json | PASS | 7.178551 | 7.507821 | 0.146350 | n/a | off | 0 | 0 | 37.280 | de24189345bed2d98063afc9e2cc1d9d1f05cfc357d4006b724cf383102a1c59 |
| standard-1440-2x-whole-expandable.json | PASS | 6.392119 | 6.721389 | 0.146350 | n/a | off | 0 | 0 | 37.497 | de24189345bed2d98063afc9e2cc1d9d1f05cfc357d4006b724cf383102a1c59 |
| standard-1440-keep-whole-clean.json | PASS | 6.197084 | 6.526353 | 0.146350 | n/a | off | 0 | 0 | 32.492 | 9a0224e93c5afaa8859f46e63c3727fcb3d636d3da683a0bf95adce513101f7e |
| standard-1080-keep-capped-acceptance.json | PASS | 5.878317 | 6.146593 | 0.126312 | False | True | 0 | 0 | 29.422 | 108e09d66b71f68bc623c051003baaca2d3b9cd57d53409fbdd6eedf1a78267a |
| standard-1440-2x-capped-acceptance.json | PASS | 6.308233 | 6.637502 | 0.146350 | False | True | 0 | 0 | 34.542 | de24189345bed2d98063afc9e2cc1d9d1f05cfc357d4006b724cf383102a1c59 |
| standard-1440-2x-capped-competing-v2.json | PASS | 5.446304 | 5.735055 | 0.146350 | False | True | 0 | 0 | 36.296 | 143c0e4cc87c703e2bd7092c48a9a902dbcba07ddebfc106174378c8cf5beaf6 |
| standard-1440-2x-capped-competing.json | processing completed; adaptation FAIL | 6.329205 | 5.891129 | 0.920199 | True | True | 0 | 0 | 39.102 | cc4002cd796548960fcc97431b62fce1ee29eea6f0da0d7586dea779828d47a8 |



## Prior validation attempts (historical, not new proof)



| Check | Result | Evidence |
|---|---|---|
| Baseline focused regressions against exported c84ce1a source | 18 FAIL, 13 PASS (expected reproduction failures) | baseline-resume-tests.log |
| Initial focused current regressions | 36 PASS | resume-focused.log |
| Additional admission/recovery/cancellation/tool guards | 9 PASS, 2 GPU cases deselected | resume-extra.log |
| CPU full suite first run | 19 FAIL, 637 PASS, 24 SKIP, 101 deselected | resume-cpu-suite.log |
| CPU full suite second run | 656 PASS, 24 SKIP | resume-cpu-suite2.log |
| CPU final before DASH follow-up | 662 PASS, 24 SKIP | resume-cpu-final.log |
| CPU with verified link tools after DASH fix | 680 PASS, 6 SKIP, 103 deselected (599.36 s) | resume-cpu-dash-final.log |
| Pre-C17-safe-default CPU, including TLS and new regressions | 689 PASS, 3 SKIP, 103 deselected (610.75 s); DASH PASS | resume-cpu-delivery.log |
| **Final safe-default full CPU** | **690 PASS, 3 SKIP, 103 deselected (594.21 s)**; DASH and zero/partial native fallback PASS | resume-cpu-delivery-safe.log |
| GPU first full-suite attempt | INTERRUPTED at usage limit; no final result, log empty | resume-gpu-suite.log |
| GPU resumed suite, aggregate across interrupted/remaining invocations | **101 PASS, 2 FAIL**, no SKIP; failed C17 8/10-bit legacy-metric comparisons | resume-gpu-restart.log; resume-gpu-remaining-20261022-164416.log |
| GUI lint / typecheck / build | PASS; build chunk-size warning | command results |
| GUI unit | 66 PASS, 13 files | command results |
| Rust fmt / clippy default and e2e | PASS | command results |
| Rust unit default / e2e | 28 PASS each after final Storage changes | resume-rust-default.log; resume-rust-e2e.log |
| Release candidate build | PASS | command results |
| Whole p1f2 spec 50 repetitions (100 tests) | 100 PASS; no retry or skip | resume-repeat.log |
| Full CPU e2e | 21 PASS, 13 existing opt-in SKIP | resume-full-e2e.log |
| Package isolated smoke | 1 PASS; current package replaced after candidate PASS | resume-package-smoke.log; package-delivery.json |
| P2 idle five launches | **PASS**: Home-ready 729.040 ms <=765; first paint 729.722 ms <=1000; exactly 5 launches | p2-five-launches-resume.json; resume-p2.log |
| Windows / Ubuntu final CI | Pending operator commit/push | no Git mutation authorized |

The first CPU suite exposed Windows path-length failures caused by verbose names in the new scratch fixture; names were shortened without weakening assertions. It also exposed the empty-native-frame fallback regression; the final safe default retains the established incomplete-native-pass fallback to FFmpeg. All failed output is retained. The second complete CPU run passed; the final pre-DASH run also passed 662 tests. The completed verified-tool CPU run after the DASH fix passed 680 tests. The final safe-default run includes all subsequent high-depth recovery, TLS and incomplete-native-pass regressions: 690 PASS / 3 SKIP (resume-cpu-delivery-safe.log).




## Expected / actual, failures and limits

- Expected DASH video plus audio: actual test_direct_download_remux[dash] PASS in the new full CPU run. The manifest probe had overwritten an explicit acodec:none with another representation's audio metadata; preserving the explicit video-only value keeps the separate audio download. Prior pre-fix regression 2 FAIL; real downloader after fix 13 PASS / 1 SKIP and link tests 23 PASS. Both native zero-frame and partial-frame fallback cases also PASS.
- Expected creator-owned cleanup: final CPU 0 teardown errors and zero remaining per-test directories. Initial naive helper run had 690 assertion PASS / 3 SKIP / 94 teardown ERROR (93 open-log WinError32; one mocked os.walk TypeError). Correct teardown runs after all finalizers and closes only test-owned handlers. No product credential ACL was weakened. Sandbox deletion of the 2,464,446-byte failed-run remnants succeeded after process exit on its first manual attempt.
- Expected C17 unchanged derived decisions/G5: actual FAIL on the synthetic EOF cut; this is an optimization rejection, handled exactly by 12.2, not a failing retained test. Indexed-VFR comparison has no deterministic differences. Remaining exhaustive candidate comparisons are NOT RUN after this decisive counterexample.
- A1 reserve: maximum simultaneous dedicated-minus-Torch-reserved 329,269,248 bytes, rounded up to MiB = 330,301,440 bytes. Invalid autograd profiling used 18 GB shared and hit RIFE OOM; those attempts are retained but excluded. Earlier overlapping stage windows were not exclusive stage attribution and are excluded; corrected isolated-stage and whole-part tables above are authoritative.
- A5 idle cap wall/prediction: 29.4220863/28.2415158 =1.0418 and 34.5421129/32.1089943 =1.0758, both <1.3; no spill/OOM/uncapped rerun, strict SHA equality. First 2 GB competing-load trial failed adaptation and spilled (0.920199 GB shared). Corrected minimum(NVML free, CUDA free) adapts fraction .825649 to .634402 as free falls 7.4186752 to 5.776781312 GB. Corrected wall 36.29579/32.10899 =1.1304, shared .14635008 GB, no spill/OOM/rerun; helper exited 0. Per-stage profiler maximum 1.6017 ms; separate direct-counter query maximum .8811 ms; whole-record maximum 95.0115 ms, accepted by 12.1.
- D historical page-close cause remains unknown, explicitly accepted by 11.3: no trace existed. Future failure-only synthetic e2e logs/traces are capped at 100 MB and retained seven days; e2e close/destroy events include time/reason when known. No unsupported clipboard-causality claim.
- Public report contains synthetic-test evidence only. No owner media, owner homes, system settings, external-platform downloads, commit or push. Real Windows/Ubuntu CI is pending the operator's final commit/push.


## Final disk and cleanup (decimal GB)

Operator cleanup removed all previous 39.11 GB and the initial section-12 scratch listing was empty, resolving the earlier growth/empty-scratch gates under 12.3. Current work was separately inventoried and removed below. Logical file lengths are not allocated disk bytes; do not sum overlapping rows or infer removed bytes from free-space changes. The Python version alias cache/py/cpython-3.12-windows-x86_64-none points to cpython-3.12.15-windows-x86_64-none in the same cache; its target is counted once. No access errors or unexplained exclusions (cache-aliases.json).

| Artifact | Final bytes | Final GB |
|---|---:|---:|
| cache | 6,618,668,578 | 6.618668578 |
| package | 5,764,162 | 0.005764162 |
| cycle_evidence | 23,724,541 | 0.023724541 |
| gui_node_modules | 0 | 0.000000000 |
| gui_dist | 0 | 0.000000000 |
| gui_test_results | 0 | 0.000000000 |
| scratch | 0 | 0.000000000 |

Persistent retained-category growth versus the prior measured reference: 4,029,124 bytes (0.004029124 GB), <=1 GB. Cache <40 GB, cycle evidence <300 MB. Offline dependency restore measured independently: 191,884,396 bytes / 10,813 files / 194 packages; removed after package smoke, no retained dependency growth. Conservative total extra-growth bound: 8,041,741 bytes (0.008041741 GB), adding the entire measured tracked checkout and local-env plus a 1 MB final-report allowance. This is an upper bound, not an allocated-disk claim. No venv dependency synchronization.

| Drive free | First available section-12 snapshot GB | Final GB |
|---|---:|---:|
| C | 299.783372800 | 299.234914304 |
| D | 1004.280098816 | 1005.166575616 |

The first available snapshot was after C17 preparation/test launch, not a pristine cycle-start measurement. Earliest detailed post-restore cycle snapshot: C 294.821023744 GB, D 1005.503242240 GB; exact pre-work free space was not recorded. Final scratch has zero bytes and zero children.

| Cleanup item | Independently measured bytes removed | Result |
|---|---:|---|
| D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-section12\cpu-full | 2,464,446 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-section12\gpu-full | 475,760,906 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-section12\gpu-final | 284,814,544 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\repo\gui\node_modules | 191,884,396 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\repo\gui\dist | 582,661 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\repo\gui\test-results | 45 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\repo\.pytest_cache | 3,856 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\repo\.venv\testtmp | 0 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-section12 | 840,075,222 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\scratch\pytest-temp | 0 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\scratch\tmp | 3,870,607 | first attempt SUCCESS |
| D:\my-workspace\VideoEnhancer\work\repo\.ruff_cache | 9,918 | first attempt SUCCESS |
| Duplicate package candidate | 5,764,162 | first sandbox attempt SUCCESS after smoke |

For the owner to delete: none. Full inventory/access attribution: section12/final-disk.json; cleanup inputs/results remain in section12. No private media/weights/synthetic fixtures remain in scratch or Git. Cache retains approved reusable recipes/models. Retained product cycles are VE-P1f-3, VE-P1f-3b and VE-P1e-3a; the separate VE-MIG-1 workspace bootstrap audit is unchanged. Previously completed retention cleanup is not repeated.

## Questions, exclusions and handoff

No designer decision remains for this cycle. A4 is accepted; C17 uses the explicit defer branch. C9 retains the accepted second-Move refusal. C12 is not reproduced with guard coverage. Historical D page-closure cause remains unknown, accepted by 11.3; future failure-only trace/app/engine artifacts are capped at 100 MB and retained seven days. Owner-sample tests, unsupported platform runtime checks, the rejected optimization's remaining adoption experiments and final hosted CI are not labeled PASS. No owner home, owner media, system environment, driver setting or external media platform was touched.

The operator commits/pushes the existing authorized branch and checks Windows/Ubuntu CI. No next cycle was started.

## Additional changes in this continuation

- src/videoenhancer/jobs/pdh.py: explicit cross-platform-visible attribute types; runtime behavior retained.
- tests/conftest.py: safe CI basenames; outside-repository temp/home with CI base; inherited scratch ACLs; creator cleanup after finalizers/owned logs close.
- tests/test_quality_trial.py and tests/test_source_index.py: inherited-ACL trial temporary contexts.
- tests/test_p1e3a_resume.py: delete only the two nonshipping C17 optimization cases per 12.2.
- .ai/LAST_REPORT.md: this final evidence-aware report. CURRENT_TASK.md unchanged by Codex.
- Ignored local-env.ps1: create configured TEMP before Python starts, session only. Build/evidence/media/dependencies excluded from Git.

## Changed files (cycle versus c84ce1a, including preserved partial work)

- .ai/CURRENT_TASK.md
- .ai/LAST_REPORT.md
- .github/workflows/ci.yml
- docs/API.md
- docs/GUI.md
- docs/TROUBLESHOOTING.md
- gui/src-tauri/src/commands.rs
- gui/src-tauri/src/engine.rs
- gui/src-tauri/src/main.rs
- gui/src-tauri/src/storage.rs
- gui/src/HistoryDetail.tsx
- gui/src/Home.tsx
- gui/src/Storage.tsx
- gui/src/types.ts
- gui/tests/desktop.ts
- gui/tests/e2e/p1f2-review.spec.ts
- gui/tests/p1e3a.test.tsx
- scripts/collect_e2e_failure.py
- src/videoenhancer/bench/calibration.py
- src/videoenhancer/bench/reference.py
- src/videoenhancer/config.py
- src/videoenhancer/damaged_json.py
- src/videoenhancer/estimate/local.py
- src/videoenhancer/files.py
- src/videoenhancer/jobs/checks.py
- src/videoenhancer/jobs/gpu_budget.py
- src/videoenhancer/jobs/gpu_memory.py
- src/videoenhancer/jobs/pdh.py
- src/videoenhancer/jobs/store.py
- src/videoenhancer/logging.py
- src/videoenhancer/media/admission.py
- src/videoenhancer/media/analyze.py
- src/videoenhancer/media/decode.py
- src/videoenhancer/media/encode.py
- src/videoenhancer/media/probe.py
- src/videoenhancer/models/registry.py
- src/videoenhancer/pipeline/runner.py
- src/videoenhancer/schedule/controller.py
- src/videoenhancer/schedule/windows.py
- src/videoenhancer/service/av1_cache.py
- src/videoenhancer/service/engine.py
- src/videoenhancer/service/link_jobs.py
- src/videoenhancer/service/link_tools.py
- src/videoenhancer/service/settings.py
- src/videoenhancer/service/storage.py
- src/videoenhancer/service/video_links.py
- tests/conftest.py
- tests/test_link_tools.py
- tests/test_p1e3a_calibration.py
- tests/test_p1e3a_memory.py
- tests/test_p1e3a_minor.py
- tests/test_p1e3a_resume.py
- tests/test_p1e3a_startup.py
- tests/test_p1f3_review.py
- tests/test_video_links.py

CURRENT_TASK.md is the operator/designer's committed instruction update and was not edited during implementation. Only task-related product/test/docs changes remain uncommitted; no Git mutation was performed.
