# VE-P1e-3a implementation and verification report

- Task ID / Cycle: VE-P1e-3a / P1e-3a.
- Status: PARTIAL - final report. CPU/DASH, GUI, Rust, package and P2 checks are complete; A4 sampler-cost scope, C17 legacy EOF compatibility and refused scratch cleanup remain unresolved.
- Windows x64 / PowerShell, 2026-10-22. Branch `claude/project-thread-6lra47`, resumed HEAD `06b3a16a103ec82185f9459776c837827d66c4b3`.
- CURRENT_TASK.md was reread completely, including designer answers in section 11, and left unchanged. The committed partial implementation was preserved. No Git mutation, commit, push, merge, owner sample, owner home, system/driver setting change or external media download.
- Evidence paths below are relative to `work/evidence/VE-P1e-3a`; generated media and test homes are isolated under scratch. The prior report is retained as `first-run-report.md` so its failed runs and unexecuted checks are not erased.

## Decisions and questions for the designer

1. C3 is resolved by section 11.2: refuse input above 10 bits with the exact required copyable reason. No p016le conversion added. Previously finished jobs remain intact; unfinished unsupported jobs fail at their next start.
2. D is resolved by section 11.3: the historical page-closure cause remains unknown. The old job log shows a closed target during `page.evaluate`; no artifacts existed. No clipboard-causality claim is made. Failure-only trace/app/engine artifacts and e2e lifecycle timestamps now provide future evidence.
3. C9 default: refuse a second Move until the preceding old copy is removed, preserving the original `previous` record.
4. A2 default: keep child-local `expandable_segments:True` when no allocator option was explicitly supplied. Do not keep stage empty-cache changes: their reduction was much smaller, and the combined option was not measured.
5. If the allocator control is unsupported, run the part without a cap and record the reason; the cap itself must not prevent a runnable part.

6. A4 pending: does the <=50 ms target cover the direct PDH query alone or the entire ancillary-statistics record? Default: retain the existing statistics, report both costs, and leave A4 partial.
7. C17 pending: may the native first-pass decoder replace SimpleDecoder's duplicated EOF metrics? Default: preserve the legacy two-pass results; leave both optimization failures visible and C17 partial.

## Implementation

- Per-part free-dedicated budget, measured 330,301,440-byte reserve, existing half-clip retry followed by one uncapped rerun, and explicit statistics. WDDM requires the minimum of NVML device-free and CUDA free: the first competing-load experiment proved CUDA free alone was unchanged by another process.
- Direct ctypes PDH sampling every second, PowerShell only on direct-query failure, sticky spill detection, watchdog wall-limit scaling with no-frame timeout retained, exclusion from timing learning/calibration, and a persistent copyable details notice.
- Guarded startup JSON reads, independent damaged-record isolation, once-per-file diagnostic notices, session defaults, and refusal to overwrite damaged settings/control/cache records. Strict History behavior retained.
- Runtime decoder preservation, exact high-depth admission, strict native counts and evaluation of first-decode thumbnails (C17 deferred after EOF mismatch), resumable downloaded-video analysis, case-insensitive post-rename recovery, rounded reuse width, eligible audio selection, same verified tool bytes, refreshed link estimates and unreadable-folder dates.
- Storage eligibility/recovery/unavailable-drive messages, progress, plain result sentences with Copy details, second-Move refusal, metadata-only confirmation followed by one hash pass.
- e2e-only copy capture retained; real native clipboard round trip remains tested. Native close/destroy and CDP close/crash/exit events include timestamps. CI failure evidence is bounded below 100 MB and retained seven days; no retries, skips or changed failure status.

## Validation results

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

## GPU evidence and failed experiments

A1: five configurations use a synthetic 120-second 1920x1080 30-fps source. Per-stage harness uses 15 frames; real whole parts use 30 frames. The initial stage harness omitted inference mode, retained autograd graphs, spilled and eventually hit RIFE OOM. Its `*-stages-clean.*` files are invalid for reserve selection. The corrected `*-stages-inference.*` runs all passed. Earlier ten overlapping first-run measurements remain historical only and are not used for the reserve.

Reserve: maximum simultaneous process dedicated minus Torch reserved in valid isolated whole runs was 329,269,248 bytes; round upward to a full MiB: **330,301,440 bytes**. This is conservative and includes process memory outside Torch. Display allocations are already excluded by current free-device memory.

A2 strict SHA-256 equality passed for both Standard 1080 2x and Standard 1440 2x. Reserved peaks: 7.397 -> 6.036 GB and 7.474 -> 6.392 GB with expandable segments. Stage empty-cache trials gave 7.367 and 7.179 GB, and were not kept. Wall times remained about 36.0 / 37.3 seconds.

A5 idle cap runs: Standard 1080 Keep whole-wrapper wall time 29.422 s / 28.242 predicted = 1.042x; Standard 1440 2x 34.542 s / 32.109 = 1.076x. Both no spill, no OOM half retries, no uncapped reruns, and exact SHA equality with uncapped outputs. Peaks and raw SHA values follow in the memory table.

Competing helper held exactly 2,000,000,000 bytes. First experiment: processing succeeded but adaptation FAILED, because CUDA free stayed unchanged; shared peak 0.920 GB and spill detected. Corrected NVML/CUDA-minimum experiment: free budget input fell from 7,418,675,200 to 5,776,781,312 bytes; cap fraction .825649 -> .634402; no spill, no OOM retries, no uncapped rerun, 36.296 s whole-wrapper wall time (1.130x idle prediction). Both helpers exited with code 0. These different source-part outputs are not used as G5 comparators.

Direct profiler maximum sample cost across valid isolated stage/whole baseline measurements was 1.602 ms (target <=50 ms). Production counter source was PDH ctypes in capped acceptance runs. Measured runs originally used 256 MiB above the first available processing sample; the final tracker uses exactly 256,000,000 bytes (256 decimal MB), matching the task wording. Replaying all four saved real GPU counter streams through the final tracker preserves every observed spill decision (`spill-threshold-replay.json`).

## Unresolved acceptance and intentional exclusions

- A4: direct PDH cost meets 50 ms; the whole record, including ancillary statistics, has a 95.011 ms outlier. The chosen default preserves those statistics pending clarification of the measurement scope.
- C17: the two new one-pass GPU regressions remain FAIL. Native analysis keeps the established two-pass metrics pending approval to change legacy duplicated EOF behavior. No failing assertion was skipped or weakened.
- Scratch: deletion refusals leave the exact paths/capacities listed below. No deletion retry, permission change or cleanup escalation was performed. The empty-scratch/growth gates are not met.
- Final Windows/Ubuntu CI remains pending the operator's commit/push. Owner samples and soak tests were intentionally not run, as instructed. No Git mutation.

## Disk checkpoint

Dependency restore: gui/node_modules 191,884,396 bytes (reported separately from growth). Earlier inventory: package 5,775,421 bytes, cache 6,596,230,561 bytes, cycle evidence 1,230,320 bytes. Initial C free 294,821,023,744; D free 1,005,503,242,240 bytes. Final measured sizes, growth and exact cleanup outcomes are recorded below. This first detailed baseline was already after dependency restore/initial work, so it is not a complete cycle-start baseline.

# Isolated GPU measurements



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

| standard-1440-2x-capped-competing.json | PASS | 6.329205 | 5.891129 | 0.920199 | True | True | 0 | 0 | 39.102 | cc4002cd796548960fcc97431b62fce1ee29eea6f0da0d7586dea779828d47a8 |


## Historical first-run measurements (not used for the reserve)


All GPU measurements used synthetic footage and individual scratch homes with development-model hard links. No cap was active. Clip length 15, overlap 2, HEVC output. These are 30-frame parts, not complete two-minute jobs. The first five runs used the unchanged production pipeline. Its original PowerShell sampler remained active; a separate external PDH sampler recorded process memory every second.

| Configuration | Torch allocated peak GB | Torch reserved peak GB | Process dedicated peak GB | Process shared peak GB | Part seconds |
| --- | --- | --- | --- | --- | --- |
| Standard 1080 Keep | 5.749 | 7.126 | 7.394 | 0.126 | 32.939 |
| Standard 1080 2x | 5.947 | 7.086 | 7.355 | 0.126 | 36.037 |
| Standard 1440 Keep | 5.875 | 7.147 | 7.476 | 0.146 | 32.458 |
| Standard 1440 2x | 6.198 | 7.554 | 7.816 | 0.213 | 37.928 |
| Fast 1440 2x | 2.057 | 2.863 | 3.177 | 0.146 | 7.193 |

Values are decimal GB and sampled process peaks; sampled peaks are not guaranteed continuous maxima. Raw JSON is authoritative if rounding differs. All ten processing calls completed and reported zero BasicVSR OOM retries. G5 and predictions were not compared.

A second instrumentation pass reset global Torch peaks at compute-stage boundaries and added simultaneous Torch reserve to each external PDH sample. This affects the meaning of the returned aggregate Torch peak: the v2 stats' final peak must not be interpreted as a whole-part peak. Stage entry/exit records are retained. Decode and encode windows were not separately instrumented, and overlapping workers prevent interpreting the recorded stage windows as exclusive stage allocations. Consequently A1's required complete per-stage table is **NOT AVAILABLE**.

| Additional run | Processing result | Part seconds | Maximum external direct-PDH sample cost ms |
| --- | --- | --- | --- |
| Standard 1080 Keep v2 | PASS | 32.537 | 0.734 |
| Standard 1080 2x v2 | PASS | 36.087 | 9.078 |
| Standard 1440 Keep v2 | PASS | See raw JSON | 1.003 |
| Standard 1440 2x v2 | PASS | See raw JSON | 1.291 |
| Fast 1440 2x v2 | PASS | 7.255 | 0.667 |

The last four v2 runs overlapped the CPU GUI e2e run, whose engine can probe GPU hardware. They are unsuitable as isolated GPU performance/reserve evidence and must be rerun before choosing a reserve. No reserve was chosen. The external direct query ran through ctypes PDH, not a PowerShell fallback. Its measured samples were below 50 ms; this is not a production-sampler acceptance result. The original production sampler still took about 3 seconds in the retained logs. The multi-run PowerShell wrapper returned exit 1 despite each JSON recording processing completion; do not relabel that wrapper exit as zero.

Evidence under `work/evidence/VE-P1e-3a`: `profile_baseline.py`, ten `*-baseline*.json` files, corresponding logs, and `measurement-summary.json`. Original manifest evidence filenames were reused by the second instrumentation pass; original processing stats/logs remain intact. Output media and model links were cleanup candidates, not Git content.


## Package delivery checkpoint

Candidate smoke PASS (1 test). SHA-256: ee794f37b9682c715c8dd09b32b93f075796b00af466b9a4826c866ccd3d6064. Candidate folder scheduled for deletion after copying its two verified files: work/package/p1e3a-candidate, 5764162 bytes. Replaced current package: 5775421 bytes.

## Usage-limit resume and DASH follow-up

The previous turn stopped at a Codex usage limit. Current uncommitted changes were preserved. Read-only Git confirmed HEAD remains `06b3a16a103ec82185f9459776c837827d66c4b3`. The unfinished GPU suite had no surviving process or final output, so it was restarted with unbuffered verbose per-case logging; no prior GPU suite PASS is claimed. Completed 50-run e2e, full CPU e2e, builds and memory experiments were not repeated.

**DASH reproduction:** exporting the exact pre-fix HEAD sources outside the checkout and executing the real synthetic DASH test plus the new metadata regression produced **2 FAIL** (`resume-dash-before.log`). The DASH video packets matched but audio stream 1 was empty. The unit test showed `acodec` changed from `none` to `aac`.

**Cause:** probing a DASH manifest for missing geometry/duration sees the complete manifest, including a separate audio representation. `item.update(extra)` overwrote the extractor's explicit video-only `acodec: none`. C13 correctly skips separate audio for a video that already contains audio, so that overwritten value selected only the video representation.

**Fix:** retain the extractor's explicit video-only audio value when enriching metadata. Separate audio is still selected and downloaded; formats already carrying audio retain the C13 behavior. The five-line guard already present in the preserved current tree was retained, and `test_manifest_probe_keeps_video_only_representation_and_separate_audio` now fixes this contract without network access. No assertions were weakened.

**After:** real local-server downloader suite **13 PASS / 1 SKIP**, including exact video and audio packet hashes for DASH (`resume-link-download2.log`). Video-links unit suite **23 PASS** (`resume-dash-unit.log`). Fresh full CPU suite with verified standalone tools completed: **680 PASS / 6 SKIP / 103 deselected in 599.36 s** (`resume-cpu-dash-final.log`); the new unit was also run separately because it was added after full-suite collection.

**Other before/after evidence:** startup regression suite on c84ce1a: 31 FAIL / 5 PASS (`baseline-startup-all.log`), current: 36 PASS (`resume-startupstart.log`). New notification/title GUI regressions: 2 FAIL against exported c84ce1a frontend (`baseline-gui-unit.log`), PASS in the current 66-test GUI unit run. Six new native regression tests injected unchanged into exported c84ce1a Rust fail to compile because the required helpers/hooks do not exist (16 E0425 diagnostics, `baseline-native-regressions.log`); this is compile-time red-test evidence, not a claim of six executed runtime failures. Current native suites: 28 PASS each. Memory regression collection against c84ce1a fails because the new budget module is absent (`baseline-memory-regressions.log`); current focused memory/resume tests: 21 PASS.

**Sampler timing disclosure:** direct PDH query measured 60 one-second samples against the active GPU process; maximum **0.8811 ms** (`direct-counter-cost-active.json`). Valid isolated stage/whole profiler maximum was 1.602 ms. Production *whole record* time, which also reads Torch allocator/NVML statistics, reached 28.119 ms in idle 1440 acceptance and **95.011 ms** in the corrected competing-load run. These are different measurements; the 95.011 ms result is retained and is not presented as meeting a 50 ms whole-record limit. `counter_sample_seconds` now records the direct-counter portion separately from total `sample_seconds`. Default: retain existing ancillary memory metrics and disclose both costs for designer review.

Package delivered at `work/package/VideoEnhancer`: SHA-256 `ee794f37b9682c715c8dd09b32b93f075796b00af466b9a4826c866ccd3d6064`, executable 5,764,096 bytes. The separate candidate passed startup/engine discovery/renderer isolation smoke (1 PASS) before replacing the previous package. Candidate temporary folder was then removed successfully; no owner data was used.

C3 final admission coverage: 10 PASS / 2 GPU deselected (`resume-admission-final.log`), including the exact local Add-preview/API refusal, unfinished legacy failure on next start, and byte-preserved completed History/source. These additional tests ran separately after full CPU collection. DASH follow-up is locally verified; hosted CI remains pending operator push.

## Per-item evidence checkpoint

| Item | Status | Before / after evidence |
|---|---|---|
| A1 | done | Historical overlapping and invalid autograd harness attempts disclosed; corrected isolated five-configuration stage/whole tables above. |
| A2 | done | Both allocator trials SHA-identical; expandable segments kept, empty-cache stage trial not kept. Whole reserved peaks and every run above. |
| A3 | done | c84ce1a memory-test collection fails (budget module absent); current fake OOM-order/budget/unsupported-cap tests PASS, capped GPU runs PASS. |
| A4 | partial | Counter latency max .8811 ms; whole-record ancillary-statistics outlier 95.011 ms disclosed. Spill/watchdog/learning/details tests PASS. Calibration tests: c84ce1a 2 FAIL, current 2 PASS (`baseline-calibration.log`, `resume-calibration-final.log`). Designer review of whole-record cost remains. |
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
| C17 | partial | Both new GPU equality cases FAIL: legacy SimpleDecoder duplicates the last batch. Safer default restores the established second native decode; final 8/10-bit diagnostics preserve legacy metrics and strict count (2 PASS). No failing optimization test was skipped, weakened or relabeled. Designer decision required before changing the legacy EOF metrics. |
| C18 | done | Baseline GUI title is raw ID and test FAIL; current dated Unreadable title and ID Copy test PASS. |
| C19 | done | Timing-observation stamp invalidates link estimate cache; baseline FAIL/current PASS in focused minor tests. |
| D | done | Historical closure unknown accepted by 11.3; internal copy path plus real clipboard unit retained. Whole spec repeated 50 times: 100 PASS. Failure-only bounded CI artifacts and e2e close/crash/exit timestamps added. |
| P2 | done | Exactly 5 idle launches; Home-ready median 729.040 ms, first paint 729.722 ms; both gates PASS. |

Native baseline evidence is explicitly a compile failure of new regression tests against missing helpers, not executed runtime assertions. Full CPU e2e: 21 PASS/13 pre-existing opt-in SKIP. Opt-in owner/GPU/visual fixtures were not represented as PASS. Hosted final Windows/Ubuntu CI remains pending operator commit/push.

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

## Additional CPU coverage and intentional exclusions

The full CPU run's six skipped nodes were mapped from its status stream against the collected node list (`cpu-skipped-nodes.json`). Three needed local TLS fixtures; after generating a scratch-only localhost certificate, all **3 PASS** (`resume-tls-final.log`). The initial fixture setup could not import cryptography; dependencies were installed only under scratch/tls-deps, not into the product venv, and no certificate store changed. These three tests used synthetic local servers only. The remaining three exclusions are the Linux-only hard-parent-death test on Windows and two owner-sample tests; owner samples are explicitly forbidden in this cycle.

Two extra calibration fake-stage tests both FAIL against c84ce1a (spilled samples were accepted) and both PASS now, including sampler cleanup. The new tests ran separately after full CPU collection. Final Python checks: ruff PASS, ruff format --check PASS (162 files), pyright PASS (0 errors/warnings).

### Sampler question for designer review

Does the <=50 ms target include ancillary Torch allocator/NVML record construction, or only the direct process-counter query? Direct PDH maximum is .8811 ms over 60 samples; the largest existing whole-record measurement is 95.011 ms under the competing load. **Safer default chosen:** preserve existing auxiliary GPU statistics, expose separate counter and whole-record timings, retain this failed whole-record result, and continue every other cycle item. No unapproved sampling architecture change was made. A4 remains partial pending this review; it does not block the other gates.

Final threshold boundary verification: fake counter tests use 256,000,000 bytes exactly, including equality (no spill) and one byte above (spill). All memory tests PASS (`resume-memory-threshold.log`). The active full GPU suite was started before this constant-only adjustment; its pipeline/G5 checks are supplemented by the final boundary test and real counter-stream replay. No completed GPU processing measurement was repeated.

## Section 11.5 reauthorized old test-folder cleanup

Preflight checks found that the 17 named old trees are not all empty: they retain generated test JSON and probe artifacts. The first two preflight checks stopped before any deletion. Actual sizes were then inventoried, and every resolved target/link check stayed inside the explicitly reauthorized scratch test roots. No owner folder is included. Exact candidates before deletion:

- work/scratch/tmp/ve-av1-probe-_xi4sfg7: 0 bytes
- work/scratch/tmp/ve-av1-probe-f0c3_tym: 0 bytes
- work/scratch/tmp/ve-av1-probe-g6559_ug: 0 bytes
- work/scratch/tmp/ve-av1-probe-hi2mqpiq: 0 bytes
- work/scratch/tmp/ve-av1-probe-ik688tfd: 0 bytes
- work/scratch/tmp/ve-av1-probe-v3x36_wl: 0 bytes
- work/scratch/tmp/ve-av1-probe-ypjqwybd: 0 bytes
- work/scratch/tmp/ve-av1-probe-ysm88dej: 0 bytes
- work/scratch/VE-P1e-3a/minor-after: 29050 bytes
- work/scratch/VE-P1e-3a/minor-after2: 31529 bytes
- work/scratch/VE-P1e-3a/minor-before: 21652 bytes
- work/scratch/VE-P1e-3a/startup-after: 8878 bytes
- work/scratch/VE-P1e-3a/startup-after2: 17311 bytes
- work/scratch/VE-P1e-3a/startup-after3: 380270 bytes
- work/scratch/VE-P1e-3a/startup-after4: 420311 bytes
- work/scratch/VE-P1e-3a/startup-before: 621 bytes
- work/scratch/VE-P1e-3a/startup-debug: 324280 bytes

Result: 17/17 authorized old test trees removed inside the sandbox (1233902 independently measured bytes), one deletion attempt per target and no escalation or retry.

## Historical GPU interruption checkpoint (superseded by final results)

During the interrupted validation, the suite was logged per case in resume-gpu-restart.log. gpu-checkpoint.json records exact PASSED node IDs and a product-source fingerprint; it is refreshed while monitoring. The interruption recovery recipe was: if a usage limit interrupts that unfinished suite, resume_remaining_gpu.ps1 refuses a duplicate active run, verifies the source fingerprint, and runs only nodes without recorded PASS in a new isolated home/log. This is a recovery recipe, not evidence that remaining tests passed. No passed case needs to be repeated after an interruption.

## Older product-cycle evidence retention

Before deletion: work/evidence/P1f-2, 1143883 bytes. Its completed report was verified in Git at 2f12d43:.ai/LAST_REPORT.md. The 50-run repeat used the existing test default for two storage screenshots in that older folder; current final full-e2e screenshots are separately saved under this cycle, and the overwritten old images are not treated as historical proof.

Deletion result: True. No retry or escalation. Retained product-cycle evidence: VE-P1f-3, VE-P1f-3b, VE-P1e-3a. The separate 420,478-byte VE-MIG-1 workspace bootstrap audit remains unchanged; it is not represented as new runtime proof.

## Current-tree continuation (2026-10-22, 16:47 PDT)

The interrupted second GPU attempt retained 43 exact PASS nodes, no failure. No pytest process remained at resume. The next isolated invocation deselects only those 43 recorded PASS nodes and executes the remaining 60 cases. gpu_checkpoint.py now merges original and continuation logs by exact node ID. No completed test was repeated.

Two additional high-depth recovery regressions reproduce on exported c84ce1a: 2 FAIL (baseline-recovery-final.log); current related admission/startup/size tests: 56 PASS (resume-recovery-final.log). These guards affect unsupported >10-bit/recovery paths; completed valid 8/10-bit GPU processing cases remain applicable. A subsequent import-only ruff fix does not affect behavior. Final ruff check/format PASS, pyright 0 errors/warnings; the first ruff attempt found one import grouping issue, then it was corrected.

A sandbox-only CPU invocation omitted the explicit verified link-tool fixture and could not resolve installed FFmpeg; it produced many SKIPs and failures. Its raw output is retained as resume-cpu-current.log and is not treated as acceptance. The corrected full CPU invocation uses the same existing verified tools plus scratch-only localhost TLS fixtures; it runs in resume-cpu-delivery.log.

Sandbox-only CPU attempt ended: **11 FAIL, 505 PASS, 176 SKIP, 103 deselected**, 367.12 s (resume-cpu-current.log). Failures include unavailable FFmpeg/Git and denied process-tree operations; this is not the verified-tool acceptance run. C17 baseline now reproduces both 8-bit and 10-bit second-decode regressions: **2 FAIL**, assertion `Analysis decoded the native source twice.` (baseline-native-analysis.log). Current real-GPU equality tests remain pending in the ongoing suite.

Pre-C17-safe-default full CPU result: **689 PASS, 3 SKIP, 103 deselected in 610.75 s**, no failure. `tests/test_link_download.py::test_direct_download_remux[dash]` explicitly PASSED within this full run; direct and HLS also PASSED. Scratch-only TLS tests are now included in that same run. Only the Windows-inapplicable hard-parent-death test and the two prohibited owner-sample tests remain skipped.

## C17 GPU failure and safe default

The remaining GPU invocation ended with **58 PASS, 2 FAIL, 735 deselected in 6806.70 s**. Together with the 43 preserved PASS nodes before interruption, all 103 collected GPU nodes were executed: **101 PASS, 2 FAIL**. Both failures are new C17 tests (8/10-bit); there are no skipped GPU nodes. These are prototype-run results, not a green claim for the final fallback tree.

The one-pass observer matched the old motion metrics through frame 20. The old SimpleDecoder then returned PTS [667, 667, 667, 667] ms (1/1000 time base) for its final four-frame batch, whereas the strict native packet scan has distinct final presentation times. Legacy motion deltas at frames 21-23 were zero, while the first-pass decoder produced nonzero values. Diagnostics for both depths are saved in c17-native-eof-diagnostic.json/log, with a reproducible script. This is a real legacy-result difference, not a reason to loosen the equality assertion.

**Safer default under section 11.1:** preserve the existing native second-thumbnail pass, its FFmpeg fallback on an incomplete pass, and strict timestamp/count checks. The optimization prototype is retained outside Git as analyze-onepass-prototype.py. A separate final-default diagnostic verifies identical legacy motion metrics for 8/10 bits, exactly 24 frames, and refusal of an intentionally missing packet (c17-safe-default-verification.json; 2 PASS). C17 remains PARTIAL and its two optimization regressions remain unresolved. No quality/decoder-decision change was independently approved.

Question for the designer: may C17 replace legacy SimpleDecoder's duplicated EOF metrics with the strict decoder's distinct final frames? Default chosen: **no; retain the established two-pass result** until explicitly approved. This question did not stop P2 or the remaining CPU/static/disk checks.

## P2 final measurement

Exactly five independent isolated package profiles were launched after all GPU/CPU processes exited. Home-ready median **729.040039 ms** (limit 765), first-paint median **729.722168 ms** (limit 1000): both PASS. Every measured app process exited. This is the established prestarted synthetic Node-engine/1000-History-row harness with WinEvent + navigation timing; it is not a claim about cold Python-engine startup. No failed launch was discarded and no sixth launch was performed.

Final static checks after the safe-default change: ruff and format PASS (162 files), pyright PASS (0 errors/warnings). Read-only git diff --check PASS; Git emitted only existing LF-to-CRLF normalization warnings. No Git mutation.

### Final safe-default regression checks

The first CPU run during safe-default restoration ended **688 PASS, 1 FAIL, 3 SKIP** (resume-cpu-final-safe.log): the restored empty-thumbnail reason omitted the numeric count required by the existing regression. The established reason and complete two-attempt native/FFmpeg fallback were restored. The regression now covers both zero frames and a partial two-of-four-frame native pass: **2 PASS** (resume-native-fallback-final.log). No assertion was weakened; the partial-pass case adds coverage. A fresh final full CPU invocation includes both cases (resume-cpu-delivery-safe.log).

The two C17 optimization tests were explicitly rerun against the final safer default: **2 FAIL** at the no-second-decode assertion (resume-c17-safe-default.log), as the optimization remains deferred. This is an unresolved acceptance failure, not a skipped test. The separate legacy-metric/strict-count diagnostic passed for both bit depths. The 101 other GPU PASS results above belong to the earlier prototype invocation; the complete GPU suite was not repeated after restoring legacy thumbnail behavior.

The current test collection still has 103 GPU nodes; the additional CPU partial-pass case increases total collection to 796. Final static checks are saved in resume-final-safe-static.log.

Final safe-default full CPU result: **690 PASS, 3 SKIP, 103 deselected in 594.21 s**, no failures. DASH explicitly PASSED within this same invocation. Zero-frame and partial-frame native thumbnail fallback both PASSED. The three skips remain Windows-inapplicable parent-death coverage and the two forbidden owner-sample checks.

Cleanup read-only preflight: 84 exact candidates, 84,622,043,625 logical bytes, zero inventory errors. Two previously refused parent roots are inventory-only; no deletion retry will be made for them. The remaining development artifacts will each receive at most one sandbox deletion attempt after their paths and sizes are appended below.

## Final sandbox cleanup inventory

Exact development artifacts inventoried before deletion; logical bytes exclude junction targets. One deletion attempt per eligible target; no escalation or retry. Previously refused scratch/tmp and scratch/VE-P1e-3a roots are inventoried only and will NOT be retried. Section 11.5 separately reauthorized 17 children, already removed; it did not reauthorize the refused parent roots.

- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\admission-final`: 38247 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\analysis.json`: 174564 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baseline`: 2264378 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baseline-native-analysis`: 47650 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baseline-recovery`: 743 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baseline-startup`: 198800 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baseline-tests`: 61701 bytes; 1 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baselineextra`: 14244 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\c17-final-default`: 47650 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\calibration-before`: 0 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\calibration-final`: 0 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-current`: 171492670 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-dash-final`: 477509194 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-dash-final-home`: 34008 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-delivery`: 477634191 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-delivery-home`: 34000 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-delivery-safe`: 477657868 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-delivery-safe-home`: 34020 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-final`: 447720153 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-final-home`: 33988 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-final-safe`: 477641027 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-final-safe-home`: 34008 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-suite`: 446034764 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-suite-home`: 34278 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu2`: 447107463 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu2-home`: 33968 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\dash-before`: 970531 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\dash-unit`: 362 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\extra`: 14236 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\fast-1440-2x-stages-clean`: 272400447 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\fast-1440-2x-stages-inference`: 274212501 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\fast-1440-2x-whole-clean`: 276290615 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\finalfocused`: 14260 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\focused-resume`: 277071 bytes; 1 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-remaining-20261022-164416`: 23749842575 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-remaining-20261022-164416-home`: 1451 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-restart`: 29750130295 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-restart-home`: 448639439 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-suite`: 9758912544 bytes; 1 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-suite-home`: 448639439 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gui-full`: 414362202 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\links`: 19189992 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\links2`: 19223081 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\load`: 44 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\load-1792674979075141300`: 44 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\memory-threshold`: 17 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\native-fallback`: 12946 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\p2-cold-start`: 60743805 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\package-smoke`: 11322493 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\pre-dash-fix`: 883030 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\recovery-final`: 1541823 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\source.mp4`: 58624849 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-2x-stages-clean`: 274614222 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-2x-stages-inference`: 274614222 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-2x-whole-clean`: 276971400 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-2x-whole-empty-cache`: 276971400 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-2x-whole-expandable`: 276971400 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-keep-capped-acceptance`: 275244971 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-keep-stages-clean`: 273828386 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-keep-stages-inference`: 273828386 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1080-keep-whole-clean`: 275244971 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-capped-acceptance`: 278849674 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-capped-competing`: 278940525 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-capped-competing-v2`: 278939170 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-stages-clean`: 272400688 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-stages-inference`: 275532624 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-whole-clean`: 278849674 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-whole-empty-cache`: 278849674 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-2x-whole-expandable`: 278849674 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-keep-stages-clean`: 274291013 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-keep-stages-inference`: 274291013 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\standard-1440-keep-whole-clean`: 276153475 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\startupfinal`: 459272 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\startupstart`: 978968 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\tls-deps`: 11339911 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\tls-final`: 86856 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\tls-fixture`: 2770 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\videoenhancer.jsonl`: 24976 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\P1f-2`: 9556400733 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\scratch\tmp`: 343911816 bytes; 14 inventory errors; prior refusal: NO DELETE ATTEMPT
- `D:\my-workspace\VideoEnhancer\work\scratch\VE-P1e-3a`: 0 bytes; 0 inventory errors; prior refusal: NO DELETE ATTEMPT
- `D:\my-workspace\VideoEnhancer\work\repo\gui\node_modules`: 191885386 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\repo\gui\dist`: 582661 bytes; 0 inventory errors
- `D:\my-workspace\VideoEnhancer\work\repo\gui\test-results`: 45 bytes; 0 inventory errors

Cleanup result: 71 targets completely removed, 11 new deletion refusals, and 2 previously refused parent roots not retried. Complete per-target attempts/errors are retained in final-cleanup-resume-results.json. Exact remaining sizes were subsequently measured read-only; no further deletion was attempted.

## Final disk audit and cleanup result

All GB values are decimal logical file sizes. Junction targets are excluded. Complete read-only post-cleanup inventory has no access errors (final-disk-resume.json; owner-delete-final.json). No data or permissions were changed by that inventory.

| Item | First detailed inventory GB | End GB |
|---|---:|---:|
| Package | 0.005775421 | 0.005764162 |
| Cycle evidence | 0.001230320 | 0.019725988 |
| Scratch | 1.162565781 | 39.110744834 |
| Cache | 6.596230561 | 6.618638007 |
| C free | 294.821023744 | 299.791159296 |
| D free | 1005.503242240 | 966.043721728 |

Dependency restore was **191,884,396 bytes (0.191884396 GB)** for gui/node_modules, reported separately and excluded from the growth calculation. node_modules, gui/dist and gui/test-results are now absent. The dependency/cache restore was not falsely counted as feature growth.

Measured package/evidence/scratch/cache growth since that first detailed post-restore baseline is **37,989,070,908 bytes (37.989070908 GB)**. This exceeds 1 GB: **growth gate FAIL**, with 39.110744834 GB of refused development scratch still present. A complete true cycle-start baseline was not retained, so whole-cycle attribution remains NOT ESTABLISHED. Cache is below 40 GB and cycle evidence is below 300 MB. Drive-wide free-space changes are not used to infer cleanup bytes.

This final cleanup stage removed **45,511,298,791 logical bytes (45.511298791 GB)**, calculated from independent before/after inventories of the nonoverlapping target paths. It includes partially removed trees; the earlier fully-removed-only subtotal was 41,517,445,538 bytes. The separately documented 17-folder and older-evidence cleanups are not added again here.

### For the owner to delete

The following exact post-cleanup sizes remain. Eleven targets received one sandbox deletion attempt and were refused; two older refused parent roots were not retried. No chmod, force-delete retry, cleanup escalation or alternative deletion route was used. Read-only final sizing does not retry deletion.

| Exact path | Remaining bytes | Result |
|---|---:|---|
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\baseline-tests` | 61,701 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-dash-final` | 472,197,871 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-delivery` | 477,491,882 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-delivery-safe` | 450,579,566 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-final` | 381,408,605 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-final-safe` | 461,111,787 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu-suite` | 445,848,664 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\cpu2` | 434,824,869 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\focused-resume` | 277,071 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-restart` | 25,884,118,458 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\p1e3a-resume\gpu-suite` | 9,758,912,544 | Delete refused; no retry |
| `D:\my-workspace\VideoEnhancer\work\scratch\tmp` | 343,911,816 | Previous refusal; NOT RETRIED |
| `D:\my-workspace\VideoEnhancer\work\scratch\VE-P1e-3a` | 0 | Previous refusal; NOT RETRIED |

The 17 individually reauthorized old folders were all removed earlier. The empty old parent and the prior-refused tmp parent remain as listed. Remaining media/model copies are synthetic development artifacts under work/scratch; their presence is an explicit cleanup failure/owner exception, not a claim of compliance with the no-retained-large-fixture rule.

## Expected / actual and final handoff

- DASH: expected both video and audio packet hashes to match the local synthetic reference; actual PASS in the final full CPU run. Explicit video-only extractor metadata is preserved during manifest enrichment.
- Startup/admission: expected damaged bytes to remain unchanged, unaffected records to load, settings saves to refuse damaged files, and >10-bit inputs to use the exact reason; current CPU regressions PASS.
- GUI: automated Tauri/Playwright operations covered unreadable History details/Copy, Storage Move/Remove/result/progress and the full configured CPU e2e flows. Whole p1f2 spec: 50 repetitions / 100 PASS; full CPU e2e: 21 PASS / 13 existing opt-in SKIP. No manual physical-owner check is claimed.
- P2: expected median Home-ready <=765 ms and first paint <=1000 ms; actual 729.040039 / 729.722168 ms, PASS over exactly five idle launches.
- C17: expected unchanged motion metrics with no second decode; the prototype differs at the legacy EOF batch. Actual optimization tests FAIL twice; the final safer default preserves legacy metrics and strict counts (two GPU diagnostics PASS). Designer approval is still needed.
- Disk: expected empty scratch and <=1 GB growth; actual refused scratch remains, so these gates are not met.

Current package: 5,764,162 bytes in two files; EXE 5,764,096 bytes. Final read-back SHA-256 is `ee794f37b9682c715c8dd09b32b93f075796b00af466b9a4826c866ccd3d6064`, matching the smoke-tested delivery. The package was not rebuilt or retested unnecessarily after completed checks.

The final tree preserves the existing uncommitted work plus these task-related changes. Exact file lists are in changed-files-final.json: 55 cycle files versus c84ce1a (including the designer's already committed CURRENT_TASK.md) and 49 current uncommitted files. HEAD remains 06b3a16a103ec82185f9459776c837827d66c4b3 on claude/project-thread-6lra47. Operator Git recording/push and hosted CI are pending. This cycle ends with PARTIAL, not BLOCKED or a completion claim.
