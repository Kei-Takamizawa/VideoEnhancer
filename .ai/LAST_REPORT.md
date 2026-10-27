Task ID: VE-P1e-3c2 / Run 4 / section 11.4
Status: COMPLETED

## Outcome and scope

The failure is a test-fixture cancellation assumption exposed by the new Windows
yt-dlp binary's larger Python file-write buffer. The fixture now interrupts an
unfinished transfer after a nonempty prefix is actually saved. All original
assertions remain, with stronger prefix-integrity and exact Range-resume checks.
Final local validation passed. Hosted CI remains for the operator after commit/push.

Accepted runs remain by reference: **2d996bc** (Run 1), **0fd7293** (Run 2),
**3cc4333** (Run 3). Their player, visual, timing, packaging, Compare and other
accepted results were not repeated. Initial branch `claude/project-thread-6lra47`,
clean HEAD `60e854a`. CURRENT_TASK.md is unchanged. No Git mutations or supervisor
changes. No product code, tool update policy, GUI or package changes.

## Root cause

The original callback cancelled at reported downloaded bytes >100,000. That counter
includes data accepted into the downloader's user-space write buffer. At the
reproduced cancellation point, **130,048 network bytes / 0 file bytes** were recorded.
The product's existing forced process-tree termination then discards the unflushed
buffer; checking the file later cannot recover those bytes.

The old standalone binary embeds Python 3.10.11; the CI-matching binary embeds
Python 3.14.10. Their default binary I/O buffer constants are **8 KiB /128 KiB**.
130,048 bytes fit entirely inside the new 131,072-byte buffer. Both versions'
HTTP/common downloader files are byte-identical, and sanitize_open is identical.
It opens a buffered file, writes data, then reports progress without a per-packet
flush. Source hashes/comparisons and checkpoint data:
`work/evidence/VE-P1e-3c2/run4/source-and-checkpoint-evidence.json`.

Primary sources: [old CPython buffer constant](https://github.com/python/cpython/blob/v3.10.11/Modules/_io/_iomodule.h),
[new constant](https://github.com/python/cpython/blob/v3.14.10/Modules/_io/_iomodule.h),
[yt-dlp HTTP write/progress ordering](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/downloader/http.py),
[file opening](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/utils/_utils.py).

The PR's product download/cancel/resume path is unchanged against the checked-out
origin/main ref and accepted2d996bc: video_links.py, link_jobs.py, link_tools.py,
proc.py and schedule/controller.py have no diff. Only the already accepted CI
setup script differs in that selected path inventory. This run changes the fixture.
Saved nonempty prefixes resume correctly with both real tool releases. Early
cancellation before any buffered data is written can still leave an empty file;
the fixture now deliberately exercises cancellation of an existing resumable prefix.

## Tool versions and provenance

CI versions were read from the actual setup status output, not inferred from
today's latest release. Both failing runs used the same tool versions and hashes:

- [CI40413928231, 0fd7293](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/40413928231)
- [CI40414055381, c3e712c](https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/40414055381)

| Environment | yt-dlp | Deno | Bundled Python |
| --- | --- | --- | --- |
| Both failing CI setup logs | 2026.10.26 | 2.9.8 | Binary hash matches the measured PC binary below |
| PC original cached tools | 2026.08.19 | 2.9.7 | 3.10.11 |
| PC exact CI-matching tools | 2026.10.26 | 2.9.8 | 3.14.10 |

PC versions were executed using --version; bundled Python was measured with
--verbose against a closed loopback port. That diagnostic's connection error is
intentional. No external media site was contacted. Full CLI/version/status records:
`pc-tools-before.json`, `pc-tools-ci-matching-versions.json`, `*-runtime.log`,
`ci-tools-status.txt`, `ci-c3e-tools-status.txt`.

Exact CI releases were installed through the existing official-publisher,
published-SHA256-verifying ToolManager into
`work/cache/link-tools/yt-2026.10.26-f5389d36-deno-2.9.8-92439780`.
Existing cached tools are untouched. No system installation or environment change.

| Official release asset | Download bytes | Published SHA-256 |
| --- | ---: | --- |
| [yt-dlp2026.10.26](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26), yt-dlp.exe | 23,575,744 | `f5389d3698ecde4ef06f4e6b1ce0294fe9ac1396228c8990b8d3416d6d177a7d` |
| [Deno2.9.8](https://github.com/denoland/deno/releases/tag/v2.9.8), Windows x64 ZIP | 42,917,472 | `cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf` |

Extracted deno.exe:98,081,568 bytes; SHA256
`924397800533d3eb0ed0c889b20ad70e18b970d93acd8135bc043f425e528266`.
The installer removed its temporary ZIP after verification. Retained executables
and metadata are recipe-keyed cache artifacts, never Git/package content.

## Fix and expected/actual behavior

The cancel callback keeps the existing100,000-byte lower bound and also requires
unfinished network progress and an actual nonempty, unfinished .part file.
It records that checkpoint once and cancels immediately. No sleep, retry, larger
arbitrary byte threshold, tool downgrade or timeout relaxation was added.

Unchanged checks: InterruptedError on cancel, no final file before retry, nonempty
partial, positive Range on the next attempt, completed file and180 output frames.
Added checks: the saved bytes equal the source's exact prefix, that prefix remains
unfinished, the cancellation checkpoint survives, and resume requests an offset
equal to the complete saved partial size.

| Case | Expected | Actual |
| --- | --- | --- |
| Original test, old tools | Resume a saved prefix | PASS1 |
| Original test, exact CI tools | Nonempty partial | FAIL:0 bytes |
| Diagnostic repeat, original cancel condition | Capture counter/file relationship | FAIL again:130,048 reported /0 saved |
| Fixed test, exact CI tools | Cancel/disconnect preserve and resume correct prefix | PASS2 |
| Five additional independent CI-tool pairs | Same assertions every run | PASS10; all five exits0 |
| Fixed test, old tools | Backward compatibility | PASS2 |
| Fixed cancel checkpoint, new/old tools | Saved prefix while transfer is unfinished | 261,120 /130,048 bytes respectively |

Logs: `repro-old.log`, `repro-ci-tools.log`, `buffer-diagnostic.log`,
`fixed-ci.log`, `repeat-1.log` through `repeat-5.log`,
`repeat-results.txt`, `fixed-old.log`. These were independent fixed-count
executions; the stability loop stops on its first failure. All earlier failures remain recorded.

## Final checks

| Check | Result |
| --- | --- |
| Ruff lint | PASS; ruff-final.log |
| Ruff format | PASS;186 files; format-final.log |
| Pyright configured src scope | PASS;0 errors/warnings; pyright-final.log |
| Full CPU suite with exact CI tools enabled | PASS694 /SKIP6 /deselected101;635.52s; pytest-final.log |
| GUI/Rust/e2e/package/GPU/visual checks | NOT_RUN this run; accepted3cc4333, unchanged by this fixture-only fix |
| Hosted final Windows/Ubuntu CI | NOT_RUN; operator commits/pushes/checks |

The full CPU suite includes local synthetic link-media acceptance with the real
CI tools:13 PASS /1 SKIP in test_link_download.py. The existing local TLS fixture
is skipped because OpenSSL is unavailable; the full suite has6 existing skips in
total. No skip or assertion was loosened.

Reproduction command (from repo; the tool home is retained):

```powershell
. .\local-env.ps1
$env:VE_LINK_TEST_TOOLS_HOME = (Resolve-Path '..\cache\link-tools\yt-2026.10.26-f5389d36-deno-2.9.8-92439780').Path
.\.venv\Scripts\python.exe -m pytest tests/test_link_download.py::test_cancelled_transfer_resumes_partial_file -vv -s --basetemp=../scratch/p1e3c2-run4-manual -p no:cacheprovider
```

Use unmodified60e854a test source to reproduce the original failure; this worktree
contains the corrected fixture. All media is generated locally under scratch.

## Changed files

- `tests/test_link_download.py`: persisted-prefix cancellation checkpoint and stronger resume checks.
- `.ai/LAST_REPORT.md`: Run4 evidence/report.

No product source, workflow, dependency lock, CURRENT_TASK.md, owner data or accepted
GUI/package material changed. All logs/tools/fixtures stay outside Git.

## Disk and cleanup

Start/end decimal GB, logical file lengths rather than allocation. Overlapping evidence subsets are not summed.

| Item | Start GB | Final GB |
| --- | ---: | ---: |
| C free | 351.306736 | 351.295730 |
| D free | 978.752106 | 978.638320 |
| `cache` | 9.505453 | 9.627114 |
| `scratch` | 0.008649 | 0.000000 |
| `package` | 0.125281 | 0.125281 |
| `evidence/VE-P1e-3c2` | 0.197390 | 0.198147 |
| Run4 evidence (cycle subset) | 0 | 0.000645 |
| New verified tool recipe (cache subset) | 0 | 0.121660 |

All14 cleanup candidates listed below were removed, **14,556 measured logical bytes**. Test fixtures had already cleaned their media/outputs; manual cleanup removed remaining caches/empty test roots. Per-item outcomes: cleanup-results.json. No new refusal. Scratch has no files at final inventory; empty parent/tmp directories remain. The inherited-profile disappearance is separately attributed below.

Measured net change across the four inventoried work folders: **0.113768 GB**. Adding all current checkout files modified since start as a conservative bound (36,211 bytes, including .venv runtime caches) and restoring 8,648,980 bytes of unattributed inherited-profile decrease to avoid taking credit for it gives **0.123 GB** retained logical growth, rounded up to a whole MB. It is not a drive-wide allocation delta. Growth <=1GB, cache <40GB, whole-cycle evidence <300MB and D free >200GB: PASS. The package is unchanged. Disk-start.json /disk-final.json retain exact bytes.

No dependency restore; existing .venv reused.
Only the verified tool releases above were downloaded. Start inventory:
`work/evidence/VE-P1e-3c2/run4/disk-start.json`.

Prior owner cleanup items were excluded from this run's manual plan and never retried:
`scratch/p1e3c2-native/h264-bench-two-0` (start1,712 bytes) and
`scratch/p1e3c2-native/visual-proof` (start8,647,268 bytes). Both were already absent
at final inspection; their parent remained empty. The removing actor/cause was not
established. This disappearance is not counted in our14,556-byte removal total or
credited toward the conservative growth bound. No new refused deletion or known
owner cleanup action remains. The test teardown only removes its UUID-owned roots;
the manual plan/results contain no inherited profile or ancestor.

## Remaining actions / owner check

No new manual GUI check or design decision is required for this test-fixture fix.
Retain the owner checklist from3cc4333. The operator should review the unchanged
original assertions, commit only the two listed files, push the authorized branch,
and verify Windows local-media acceptance on the new commit. Hosted CI is not
reported green before that happens. Product early cancellation and update policy
remain unchanged.

## Cleanup inventory (recorded before deletion)

Logical bytes per candidate; inherited refused profiles and their ancestors are excluded.

| Candidate under work | Logical bytes |
| --- | ---: |
| `scratch/p1e3c2-run4-buffer-diagnostic` | 0 |
| `scratch/p1e3c2-run4-final-cpu` | 0 |
| `scratch/p1e3c2-run4-fixed-ci` | 0 |
| `scratch/p1e3c2-run4-fixed-old` | 0 |
| `scratch/p1e3c2-run4-repeat-1` | 0 |
| `scratch/p1e3c2-run4-repeat-2` | 0 |
| `scratch/p1e3c2-run4-repeat-3` | 0 |
| `scratch/p1e3c2-run4-repeat-4` | 0 |
| `scratch/p1e3c2-run4-repeat-5` | 0 |
| `scratch/p1e3c2-run4-repro-ci` | 0 |
| `scratch/p1e3c2-run4-repro-old` | 0 |
| `scratch/tmp` | 0 |
| `scratch/videoenhancer.jsonl` | 3098 |
| `repo/.ruff_cache` | 11458 |
