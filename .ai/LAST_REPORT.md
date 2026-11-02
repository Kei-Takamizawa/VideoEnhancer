Task ID / Cycle: VE-R0c
Status: COMPLETED

## Outcome

Implemented the approved spike changes; all required final automated checks pass. Real iPad re-checks and
Apple delivery are NOT_RUN in this cycle, as assigned to the operator/owner.

## Scope and environment

Windows PowerShell, branch `claude/project-thread-yyrl3q`, HEAD `fece91257d89239243564f783b5c609cde5fa228`.
The elevated read-only pre-edit Git status was clean. CURRENT_TASK.md was read
fully and retained unchanged. No Git mutations, commits, pushes or remote updates.

## Changes

- `spikes/ipad/server.py`: shared scheduled/self-test push sender; public project
  HTTPS subject by default, `--vapid-subject`, explicit endpoint-origin audience,
  12-hour expiry. HTTP status, sanitized Apple reason and apns-id are recorded on
  failures; no endpoint path, key, JWT or exception message is logged. Errors
  without an HTTP response use null diagnostics. Self-test opens no listeners
  and preserves the stored subscription, paired device and signing key.
- Installed py-vapid rejects HTTPS contact paths with its strict regex. This was
  reproduced before HTTP dispatch. The sender validates the URI itself and
  disables only that legacy subject regex on its local Vapid instance. Actual
  generated Authorization JWT fields are decoded by a unit test. Reference:
  https://www.rfc-editor.org/rfc/rfc8292.html#section-2.1
- `spikes/ipad/static/app.js`, `static/index.html`: T6 offers A (`target=_blank`),
  B (Blob then separately tapped file share) and C (original attachment with a
  visible trapping warning). Both 500 MB and 1 GB are selectable. Run IDs, variant,
  size, start time, observable completion and owner return/usability observations
  are recorded. Persisted in-flight B loads report possible memory termination
  after reload; the cause cannot be proven in JavaScript. File arrival remains
  an explicit owner observation, separate from transfer/share completion.
- `spikes/ipad/test_server.py`, `test_browser_logic.cjs`: JWT, diagnostic privacy,
  self-test parsing/preservation, Blob failure and variant/result correlation.
- `spikes/ipad/verify_pc.py`: current T6 selector and VE-R0c evidence folder.
- `spikes/ipad/OWNER_CHECK.md`, `README.md`: short re-check and operator commands.
- `.ai/LAST_REPORT.md`: this report; all prior report sections retained below.

## Validation

| Check | Result | Measured result |
| --- | --- | --- |
| Spike unit final | PASS | 26 passed |
| Spike JavaScript final | PASS | 8 passed |
| `uv run ruff check .` | PASS | All checks passed |
| `uv run ruff format --check .` | PASS | 220 files already formatted |
| JS syntax (app and service worker) | PASS | Both exit 0 |
| WebKit synthetic T6 | PASS | Load, share call, owner return and reload recovery; 9 bytes, mocked sharing |
| Initial CPU suite in sandbox | FAIL / interrupted | Failure markers; Git/FFmpeg unavailable; stalled at 92% in test_storage.py and was interrupted; no completed summary |
| CPU with tools and approved execution | PASS | 740 passed, 24 skipped, 102 deselected; 371.87 s |
| Legacy desktop E2E | NOT_RUN | Explicitly excluded by task |
| Large-media full PC verifier | NOT_RUN | No new 1 GB fixture or playback qualification; only its current selector adapted |
| Real Apple send / iPad T3 and T6 | NOT_RUN | Operator/owner re-check required |

Initial red: Python 23 passed/2 failed (missing new helpers), JS 5 passed/1 failed
(missing startDownload). Interim VAPID test failed before HTTP due to py-vapid's
contact regex. A JS memory-error test initially lacked File in its VM harness;
adding the real Node File global corrected that harness. The first synthetic
WebKit reload check overwrote localStorage without updating page state and timed
out; the corrected fixture sets both in-memory and persisted state, and passed.
Initial formatting/lint findings were corrected without disabling checks.
Git initially was absent from PATH and then denied by the sandbox; approved
read-only Git checks succeeded. Process inventory using CIM was denied; no
bypass or system change was attempted.

Commands (from repo, after `. .\local-env.ps1`; PYTHONDONTWRITEBYTECODE=1):

```powershell
& ..\cache\ipad-venv\Scripts\python.exe -m pytest -c spikes\ipad\pytest.ini spikes\ipad\test_server.py -q --basetemp D:\my-workspace\VideoEnhancer\work\scratch\r0c-unit-final -o cache_dir=D:\my-workspace\VideoEnhancer\work\scratch\r0c-cache
node --test spikes\ipad\test_browser_logic.cjs
node --check spikes\ipad\static\app.js
node --check spikes\ipad\static\sw.js
uv run ruff check .
uv run ruff format --check .
$env:PATH = "D:\my-workspace\VideoEnhancer\work\cache\r0b-ffmpeg;<installed Git cmd directory>;" + $env:PATH
$env:VE_DEV_M3_MEDIA = '0'
$env:VE_HOME = 'D:\my-workspace\VideoEnhancer\work\scratch\r0c-cpu-final-home'
uv run pytest -m "not gpu and not soak" --basetemp=D:\my-workspace\VideoEnhancer\work\scratch\r0c-cpu-final -o cache_dir=D:\my-workspace\VideoEnhancer\work\scratch\r0c-cpu-final-cache
```

CPU logs: `work/evidence/VE-R0c/cpu-tests.log` (initial interrupted run) and
`cpu-final.log` (approved rerun). WebKit reproducer: `verify-webkit.py`, result
`webkit-t6.json` and screenshot `webkit-t6.png` in the same private evidence folder.
The WebKit script has no real push endpoint or owner data. It starts no server.
Expected/actual: required request/claim fields and download result transitions
match automated expectations. An observed Done button, Apple acceptance/delivery,
500 MB/1 GB memory capacity and normal iPad return remain unmeasured here.

## Exact operator commands

From `D:\my-workspace\VideoEnhancer\work\repo`:

```powershell
. .\local-env.ps1
$env:PYTHONDONTWRITEBYTECODE = '1'
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\server.py --home D:\my-workspace\VideoEnhancer\work\scratch\ipad-spike
# In a second shell, after the owner has subscribed:
. .\local-env.ps1
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\server.py --home D:\my-workspace\VideoEnhancer\work\scratch\ipad-spike --push-selftest
```

Stop with Ctrl+C after the owner finishes. Omit `--redo-pairing` to keep the
existing paired device and subscription. If the home was removed, regenerate
samples, start with `--redo-pairing`, reinstall/trust the new CA as necessary,
and tap Pair this app. Self-test records status/reason in
`work/evidence/VE-R0c/ipad-results.jsonl`; exit 0 means send accepted, not delivery.
Optional subject override on both commands:
`--vapid-subject https://github.com/Kei-Takamizawa/VideoEnhancer`.

## Disk and cleanup

| Item (decimal GB) | Start | End |
| --- | ---: | ---: |
| C free | 345.816076 | 345.812673 |
| D free | 878.414852 | 878.414381 |
| work/package | 0.125288579 | 0.125288579 |
| work/evidence/VE-R0c | 0.000194981 | 0.000610147 |
| work/scratch | 2.650840802 | 2.650868083 |
| work/cache | 12.232878736 | 12.232878736 |

The initial inventory was captured after the first small test additions, before
implementation. Sizes are logical file lengths, not allocated space; nested rows
are not summed. Scratch's final restricted cache was measured separately by an
approved read: 68,704 bytes. Other inventory read errors: 0.
Managed persistent-folder growth plus a conservative upper bound for all changed
tracked text and final report overhead is at most 0.001 GB (limit 1 GB).
The whole ignored checkout had no initial size baseline; drive-wide free-space
changes are not attributed to this cycle. No packages/tools were installed.
This cycle's evidence is below 300 MB; existing older evidence was retained
rather than deleting unrelated prior-cycle artifacts during this spike fix.

Cleanup inventory (each size measured before removal; bytes are not inferred
from drive-free changes):

| Removed path under work/scratch | Bytes removed |
| --- | ---: |
| r0c-cache | 1964 |
| r0c-cpu | 180 |
| r0c-cpu-final | 0 |
| r0c-cpu-final-home | 0 |
| r0c-unit | 40501 |
| r0c-unit-final | 41529 |
| r0c-unit2 | 40990 |
| r0c-unit3 | 41233 |
| r0c-unit4 | 41523 |
| r0c-unit5 | 41523 |
| r0c-browser.py | 2978 |
| r0c-edit.py | 4830 |
| r0c-encoding.py | 239 |
| r0c-fix.py | 1503 |
| r0c-guard.py | 478 |
| r0c-inventory.py | 504 |
| r0c-report-fix.py | 749 |
| r0c-report.py | 7420 |
| r0c-testfix.py | 586 |
| r0c-ui.py | 8732 |
| r0c-verify-edit.py | 342 |

### For the owner to delete

- `D:\my-workspace\VideoEnhancer\work\scratch\r0c-cpu-final-cache`:
  68,704 bytes. Sandbox inventory and deletion were denied. No deletion retry,
  escalation to delete, ownership change or other workaround was attempted.
  A later approved read-only measurement supplied the size above.

The pre-existing paired `scratch/ipad-spike` home is intentionally preserved
for the task's explicit re-check. Other pre-existing scratch items are retained.
Scratch is therefore not claimed empty. No synthetic file was generated above
100 MB in this cycle. This cycle's transient scripts and unit-test homes were
removed; private browser evidence and its reproducer remain under evidence.

## Unresolved / questions for the designer

No new product or architecture decision is required. Owner must run the R0c
addendum, report T3 delivery and select the usable T6 variant. A page kill is
recorded as a possible memory failure, since the browser cannot prove its cause.
No owner server was started by Codex. Commit/push belong to the operator.

## Previous: VE-R0b

Task ID / Cycle: VE-R0b
Status: PARTIAL

## Outcome

Implemented the approved spike changes. The local CI-equivalent all-pass gate
is not met: the final CPU suite passed, but two existing desktop E2E cases still
failed in the reviewed full run and one sequential targeted follow-up. Real Home Screen, Apple push, background download and Photos
checks remain for the owner. No Windows settings or product code were changed.

Terminal: Windows PowerShell. Branch `claude/project-thread-yyrl3q`, HEAD
`e39c47185db557c8c0dda9b3021bb4e305e1aa39`, confirmed with read-only Git.
Git was initially absent from PATH; the installed executable was denied in the
sandbox. Approved elevated read-only status/branch/HEAD/diff commands succeeded.
The pre-edit working-tree check did not succeed, so no pre-edit clean-tree claim
is made. The successful later status showed only this cycle's spike changes.
No Git mutations, commits, pushes or remote updates were performed, per AGENTS.md.
CURRENT_TASK.md was read completely and retained without modification.

## Changes

- `spikes/ipad/server.py`: HTTPS POST /pair/claim, sharing the existing atomic
  first-claimer window with HTTP /pair. It immediately finishes the claim and
  sets a Secure, HttpOnly, SameSite=Strict cookie in the requesting app. Redo
  replaces the device; only its token hash persists.
- The server logs one JSON line when each response is prepared, including rejected
  requests: UTC time, method, route template, status, cookie presence and display
  mode. Dynamic path components are templates, unmatched paths are redacted,
  and query strings, file names, tokens and cookie values are excluded.
- `spikes/ipad/static/app.js`, `index.html`: any fetch 401 hides the test sections
  and shows Pair this app. Claim stays on the same HTTPS origin. Requests carry
  X-Display-Mode; page results carry display_mode. T3 records notification
  permission, PushManager availability and only the push endpoint host.
- `spikes/ipad/static/sw.js`: tags controlled native media/download/SSE requests
  using the originating page's mode, reports 401 to the page, and tags push
  receipts. No media/authenticated content caching was added.
- Mode is `unknown` when no header/client response is available (including the
  first navigation and static bootstrap before service-worker control); server
  records without a page use `server`. These are not invented standalone proof.
  The already correct manifest start_url and scope are both `/` and unchanged.
- Owner sessions now use evidence/VE-R0b/ipad-results.jsonl. Automation uses
  pc-results.jsonl, including server transfer records. The verifier explicitly
  identifies itself as PC automation while retaining the iPad-sized viewport.
- `spikes/ipad/verify_pc.py`: exercises HTTPS in-app claiming and writes R0b
  evidence. Known Windows WebKit codec/download gates remain enforced.
- `spikes/ipad/test_server.py`, `test_browser_logic.cjs`: claim race/closure,
  expiry, shared HTTP window, redo, cookie flags, redacted success/error logs,
  separated records, mode/permission telemetry and service-worker regressions.
  A further red/green test catches FileResponse 304 being logged as 200; the
  prepare hook now logs the final status (1 failure / 22 passes before the fix).
- `spikes/ipad/generate_samples.py`, server/tests/verifier: Ruff formatting,
  imports, explicit exception chaining and split long strings; no new ignores
  or Ruff configuration changes.
- `spikes/ipad/OWNER_CHECK.md`: requested five-minute R0b re-check addendum.
- `spikes/ipad/README.md`: pairing and separated-evidence instructions.
- `.ai/LAST_REPORT.md`: this report; VE-R0 is preserved below verbatim.

## Verification

Every installing/building/testing shell dot-sourced local-env.ps1. Test homes,
TEMP/TMP and pytest basetemp were under work/scratch. Python bytecode was disabled
for direct spike/verifier/CPU executions. Raw logs are under evidence/VE-R0b and
are not intended for GitHub.

| Command / check | Result | Actual |
| --- | --- | --- |
| Initial uv run ruff check . | FAIL reproduced | 70 existing spike findings |
| Initial new Python regressions | FAIL red | 3 failed, 17 passed before implementation |
| Dedicated spike Python pytest | PASS | 23 passed; isolated r0b-pytest |
| node --test spikes/ipad/test_browser_logic.cjs | PASS | 5 passed |
| node --check app.js / sw.js | PASS | Both parsed |
| uv run ruff check . | PASS | Whole repository; no ignores added |
| uv run ruff format --check . | PASS | 220 files formatted after correcting one interim formatting failure |
| uv run pyright | PASS | 0 errors, 0 warnings |
| uv run pytest -m "not gpu and not soak" --basetemp=work/scratch/r0b-engine -p no:cacheprovider | FAIL | 572 passed, 12 failed, 180 skipped, 102 deselected; 351.40 s |
| Reviewed final CPU suite (same selection, isolated r0b-engine-final) | PASS | 740 passed, 24 skipped, 102 deselected; 398.04 s |
| GUI npm run lint / typecheck | PASS | Both exit 0 |
| GUI npm test | PASS | 86 tests |
| GUI npm run test:payload | PASS | 1 test |
| GUI npm run build | PASS | TypeScript/Vite exit 0 |
| Cargo fmt / clippy -D warnings / test, desktop | PASS | 29 tests |
| Cargo fmt / locked clippy -D warnings / locked test, player | PASS | 10 tests |
| Cargo desktop build --features e2e | PASS | Exit 0 |
| Cargo player build --locked --features test-faults | PASS | Exit 0 |
| Cargo desktop build --release --features cdp | PASS | Exit 0 |
| Initial sandbox Desktop E2E | FAIL | 25 failed, 15 existing skips; FFmpeg EPERM and WebView/CDP failures |
| Reviewed full Desktop E2E with tools | FAIL | 24 passed, 2 failed, 14 existing skips; targeted follow-up below |
| Sequential follow-up of both remaining E2E failures | FAIL | 2 failed, same symptoms; no code/timeout changes |
| Reviewed tooltip E2E | PASS | 1 passed, 1.7 s |
| Cached-tool local synthetic link acceptance | PASS | 13 passed, 1 skipped, 123.38 s |
| Real iPad owner checks | NOT_RUN | No iPad control available |
| Linux CI execution | NOT_RUN | This terminal is Windows |

CPU failures: eight missing FFmpeg/ffprobe paths; one AV1 test mock rejects the
`job_id` keyword; Git privacy test encounters executable access denial; two
process-tree cancellation/timeout tests time out waiting for their synthetic
parent. Exact test names and tracebacks are in cpu-tests.log. The job_id exception was secondary to missing FFmpeg and did not recur after
setting the tool PATH. These are not spike test failures. No product tests or
expectations were changed to pass them.

## PC verifier and GUI operations

All three complete verifier runs exited 1 for the retained required Windows WebKit
H.264/native-download gates. Logs: pc-verifier.log, pc-verifier-final.log and pc-verifier-release.log.
The final-source third run measured T4 23.52 MB/s and loopback upload/download
161.24 / 460.58 MB/s. All three codecs still returned media error 4 and the native
download timed out. The first run measured T4 23.41 MB/s and loopback 138.49 / 365.31 MB/s.
The second run measured T4 23.80 MB/s, hash matched, AbortError observed and
20,435,975 subsequent bytes transferred; loopback upload 171.83 MB/s and download
514.81 MB/s (1,001,588,796 bytes). Rates are decimal MB/s, same-PC measurements.

Expected: unpaired HTTPS page offers Pair this app and becomes ready without
leaving the origin. Actual: verifier clicked that control, reached Ready and
confirmed the Secure cookie, then exercised upload, all codecs and native
foreground download. All three codecs returned media error 4; download event
still timed out at 15 seconds. These are the documented VE-R0 Windows limitations,
not proof about iPad hardware. Default browser CA trust failed; the diagnostic
browser used its existing LAN-limited ignore_https_errors context. Python
CA-specific TLS verification passed. Fixed mDNS name resolution still failed;
the PC-name fallback resolved. No certificate store was changed.

All 18 records across the three PC runs are in pc-results.jsonl and contain
`display_mode`; no ipad-results.jsonl was created by those runs. Second and third run records
identify PC automation rather than a fabricated iPad user agent. A PC WebKit
screenshot is retained. Actual standalone install, notifications, three-minute
background transfer, Save Video and Photos confirmation are NOT_RUN.

## Exact owner re-check start

From work/repo in PowerShell (reuse the owner's existing trusted CA/home):

```powershell
. .\local-env.ps1
$env:PYTHONDONTWRITEBYTECODE = '1'
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\generate_samples.py
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\server.py --redo-pairing
```

Ctrl+C stops the server. Pair within 120 seconds; restart with --redo-pairing
if closed. Follow the R0b section of OWNER_CHECK.md: replace the Home Screen icon,
open as a web app, pair inside it, run T2/T3, T6 background three minutes and T7
500 MB Save Video, checking Photos. No spike server is left running by Codex.

## Questions for the designer / unresolved

Two desktop E2E failures remain, both reproduced after CPU/earlier runners
exited: P1f-3 fresh History video did not reach readyState > 1 within 5 seconds;
release renderer isolation could not attach CDP because the process exited 0.
See gui-e2e-final.log and gui-e2e-followup.log. Root causes remain unconfirmed.
The allowed files exclude these product tests/implementation; designer/operator
must decide a separate correction/validation cycle. No all-local-CI PASS claim. Owner
checks must establish real standalone cookie storage, push delivery, background
behavior and Photos saving. No current iPad pass is inferred from the supplied
historical Safari observations.

No test was disabled, loosened or deleted. No Windows settings, product feature,
external video download, owner media/queue, deployment, commit or push occurred.
Optional native/GPU owner gates retain their existing skips. A networked optional-tool preparation command was rejected by automatic
approval review because of possible ambient GITHUB_TOKEN transmission and
executable installation. A boolean-only check confirmed GITHUB_TOKEN was absent.
The rejected command was not executed or retried; instead the local synthetic
link tests use the existing verified tool cache without downloads/authentication.
Read-only Git and isolated desktop test escalations succeeded.

## Final verification, disk and cleanup appendix

All final spike Python (23), JS (5), whole-repo Ruff check/format and pyright
checks passed. Final reviewed CPU: 740 passed, 24 skipped, 102 deselected.
Full reviewed desktop E2E: 24 passed, 2 failed, 14 skipped (3.8 minutes).
Sequential follow-up of the two failures after other runners exited: both failed
again with the same symptoms. Thus Status remains PARTIAL. Product E2E expected
video readiness and a CDP-attached release window; actuals were readyState timeout
and process exit 0. No causal diagnosis or unrelated fix is claimed.

Tools: portable FFmpeg/ffprobe 9.0.2 from the
[publisher](https://www.gyan.dev/ffmpeg/builds/), archive SHA-256 checked:
`60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`.
Only ffmpeg.exe and ffprobe.exe remain in cache/r0b-ffmpeg (210,644,992 B).
The archive was removed. No system installation or persistent PATH change.
Fresh optional-tool preparation was NOT_RUN after automatic rejection; existing
verified yt-dlp 2026.10.26 / Deno 2.9.8 cache passed 13 synthetic link tests,
1 skipped. Linux-only stub execution and real owner/GPU gates were NOT_RUN.
The desktop builds' existing e2e/cdp/debug startup guard prevents Run-key writes.

Disk first snapshot was after initial test/edit activity, so the exact full-cycle
start cannot be reconstructed. Sizes are logical lengths, not allocated sizes.

| Measurement (decimal GB) | First measured | End |
| --- | ---: | ---: |
| C free | 345.828237312 | 345.816842240 |
| D free | 878.647513088 | 878.415224832 |
| package | 0.125288579 | 0.125288579 |
| evidence/VE-R0b | 0.000228902 | 0.009117644 |
| scratch | 2.641360235 | 2.650793091 |
| cache | 12.021960869 | 12.232878736 |

Measured persistent delta (disjoint repo/package/cache/cycle-evidence rows) is
219,822,657 B (0.219822657 GB), below 1 GB from the first measured snapshot.
No full-cycle baseline claim is made. Cache is below 40 GB; cycle evidence is
below 300 MB. Existing older evidence was not pruned or reclassified.

Cleanup candidates were inventoried, resolved under work/scratch and checked
for reparse points before native PowerShell removal. Removed 2,620,994,022 logical
bytes independently measured (not inferred from drive-wide free-space changes).

| Removed path under work/scratch | Bytes removed |
| --- | ---: |
| ipad-pc-check | 1,671,941,456 |
| r0b-pytest | 40,512 |
| r0b-engine | 0 |
| r0b-engine-final | 0 |
| r0b-e2e | 256,784,923 |
| r0b-e2e-results | 520,386 |
| r0b-e2e-review | 11,120,831 |
| r0b-e2e-review-results | 45 |
| r0b-e2e-final | 559,886,741 |
| r0b-e2e-final-results | 39,305 |
| r0b-e2e-followup | 50 |
| r0b-e2e-followup-results | 39,919 |
| r0b-release | 5,851,714 |
| r0b-links | 0 |
| r0b-tools | 114,768,140 |

No initial listed deletion was refused. A later combined cleanup proposal was
rejected by automatic approval review because deleting scratch/home had not been
proved disposable and could destroy an existing owner environment. Under
WORKSPACE.md, rejection is final: no retry, escalation or alternate deletion was
attempted. That rejected script did not execute.

### For the owner to delete / review

- `work/scratch/home`: 0 logical bytes; proposed empty-folder deletion rejected.
- `work/scratch/tmp`: 9,464,882 logical bytes of remaining temp/trace/cache files;
  its proposed cleanup did not execute as part of the rejected command.
  Exact child paths/sizes are saved privately in evidence/VE-R0b/remaining-cleanup.json.
  A pre-existing zero-byte setuptools lock is included in inventory and preserved.
- Pre-existing `work/scratch/ipad-spike` (2,599,089,810 B) and
  `work/scratch/owner-check` (42,232,471 B) were preserved, not inspected or proposed
  for deletion. Do not delete the owner's trusted CA/home as cycle cleanup.

All cycle-specific r0b-* test roots and the generated ipad-pc-check home listed
above were removed. Scratch is not empty; the report does not claim otherwise.
No spike server is running: verifier cancellation completed and loopback ports
8080/8443 rejected connections. Every runner launched by this cycle has exited.

Operator: review the allowed-file diff and perform any Git recording separately.
Designer: decide the next cycle for the two unresolved desktop E2E failures.
Owner: perform the R0b re-check in OWNER_CHECK.md. Cleanup needing approval is
limited to the explicitly listed remaining temp/empty-folder artifacts.


## Previous: VE-R0

Task ID / Cycle: VE-R0
Status: PARTIAL

## Outcome

Built the isolated Python/Aiohttp LAN spike, PWA T1-T9, synthetic sample generator,
tests, verifier, README and English OWNER_CHECK.md. No product code/dependencies
or CURRENT_TASK.md changed. Section 3 is **not passed**: Windows WebKit failed
playback and native download; browser-context-specific CA trust is unmet. All
real-iPad results remain pending. Do not treat this report as a completion gate.

Terminal: Windows PowerShell. Reading `.git/HEAD` and its ref confirmed branch
`claude/project-thread-yyrl3q` and ref hash
`9aaaf55d7a165c386cf68601552152703073bc92`. These are file observations, not
successful Git commands. Git was absent from PATH even after local-env.ps1;
Git status/HEAD checks were NOT_RUN, and a clean working tree is not claimed.
The operator owns Git work under AGENTS.md. No Git mutations were attempted.

## Implementation

- RSA-2048 root CA and SHA-256 leaf, lifetime 397 days plus five minutes, DNS/IP
  SANs, KeyUsage, serverAuth EKU, non-CA leaf. Root mobileconfig, keys and tokens
  remain in scratch. Restart reissues the leaf for current private IPv4 addresses.
- HTTP 8080 exposes only first GET claim and two CA downloads. HTTPS 8443 serves
  static PWA files plus authenticated API/media. Binds RFC1918 local interfaces,
  not wildcard; TLS minimum 1.2. Host and HTTPS Origin are checked.
- First GET closes the 120-second window immediately. Device and hashed claim
  state persist across restart. Secret expires after 30 minutes or first use.
  HTTPS finish sets `Secure; HttpOnly; SameSite=Strict` cookie; only its token
  hash is stored. A new claim replaces the prior device record. Redo is explicit.
- VAPID subscription, pushes at 10/60 seconds, visible service-worker notification
  and authenticated receipt POST. Only HTTPS Apple push endpoints are accepted.
- Four-MiB buffered upload chunks, offset resume, observed abort followed by
  transferred bytes, SHA-256 checking, guarded paths, serialized writes and
  per-file size limit. An existing completed upload is not resume evidence.
- Fixed-name MP4 streaming, HEAD, 206/416, bounded/open/suffix ranges and native
  attachment links. T6 separates server bytes/rate from the owner's Files and
  background observations. Server bytes queued are not proof that Files saved it.
- PWA manifest/share target, service worker, T1-T9 controls, queue for failed
  result POSTs, video timings, share-size/Photos observations, paste and SSE
  recovery. JSONL records timestamp and user agent. PC records have automated:true.
  A single queue drain prevents concurrent-result loss. Delivery is at-least-once:
  a lost response after successful POST can still lead to a duplicate retry.
- Separate homes: PC verification uses work/scratch/ipad-pc-check; the later owner
  session uses work/scratch/ipad-spike. The verifier never deletes owner uploads.

## Exact owner-session start

From the repository, with the already installed dedicated environment:

```powershell
. .\local-env.ps1
$env:PYTHONDONTWRITEBYTECODE = '1'
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\generate_samples.py
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\server.py --redo-pairing
```

Ctrl+C stops it; the same last command reopens the two-minute window. The operator
starts and leaves it running for the later owner check. No server is intentionally
left running by Codex. Cycle cleanup removes generated media/keys/state, so
regenerate first. README contains bootstrap and exact automated-check commands.
OWNER_CHECK.md covers the complete iPad sequence and temporary CA removal.

## Section 3 results

| Check | Result | Actual |
| --- | --- | --- |
| Python spike suite | PASS | 17 passed; saved final log in evidence/VE-R0/unit-final.log |
| JS regression suite | PASS | 2 passed, final execution 76.36 ms |
| Python / JS syntax | PASS | All 4 Python files parsed; app.js and sw.js checked by Node |
| Certificate fields | PASS | Issuer, lifetime, SHA-256, key size, SAN DNS/IP, EKU, KeyUsage and CA constraints asserted |
| Pairing/auth/upload/Range | PASS | Window/claim/close/expiry/redo/restart, second claimer, token hash persistence, cookie flags, Host/Origin, unpaired 401, resume/hash, bounded/open/suffix/unsatisfiable ranges |
| CA-specific LAN TLS | PASS | Python SSL trusted generated CA; page and codec byte ranges verified |
| Browser-context CA trust | NOT_RUN | No supplied per-context root-store option in Windows WebKit; default context rejected the CA. Diagnostic flow used ignore_https_errors in one LAN-restricted disposable context. This is not CA-trust proof |
| WebKit iPad Pro 11 pairing | PASS diagnostic | HTTP claim, HTTPS finish, Secure cookie; CA caveat above applies |
| WebKit T4 | PASS diagnostic | 24,630,279 B / 0.922 s = 26.71 MB/s; 4,194,304 B chunks; AbortError observed, 20,435,975 B subsequently transferred, SHA-256 matched |
| WebKit T5 H.264 / HEVC / AV1 | FAIL | Each produced Media error 4; no canplay/frame/seek timings. canPlayType said probably for each, which did not predict successful playback |
| WebKit T6 | FAIL | No download event in 15 s; no browser media HTTP responses observed; no browser 1 GB completion/hash claim |
| Loopback upload | PASS | 53,387,967 B / 0.31404 s = 170.00 MB/s, includes final hash check |
| Loopback download | PASS | 1,001,588,796 B / 1.99341 s = 502.45 MB/s, consumed client-side, CA-verified TLS |
| Synthetic generation | PASS after correction | FFmpeg 7.1; 1080p60 yuv420p silent MP4; H.264 24,630,279 B, HEVC 4,787,546 B, AV1 8,771,203 B; large files 53,387,967 / 500,746,225 / 1,001,588,796 B |
| Faststart / LAN media | PASS | moov before mdat in all six MP4s; authenticated LAN 206 payloads matched first 1,024 bytes of each codec sample |
| Fixed mDNS name | FAIL / unresolved | Registration returned without bind/name-conflict error, but Windows videoenhancer.local lookup failed and separate zeroconf query timed out after 3 s |
| PC-name fallback | PASS on PC | PC-name.local resolved and served CA-verified HTTPS 200; iPad remains pending |

Rates are decimal MB/s. Same-PC LAN-address access is not Wi-Fi throughput.
Windows WebKit cannot establish real iPad hardware decode, Home Screen install,
Apple push, Photos/Files pickers or background behavior. Exact causes of browser
playback/download failure and mDNS failure remain unresolved; these failures do
not prove iPad incompatibility. Windows settings were not changed to force PASS.

### Every browser gate run

All seven runs exited nonzero. Evidence retains each run, including failures.

| Log | Result |
| --- | --- |
| pc-verification.log | Test helper used eval, blocked by CSP; replaced with locator assertions without loosening CSP |
| pc-verification-2.log | T4 hash mismatch, repeated first chunk; changed to buffered chunk payloads; T5/T6 not reached |
| pc-verification-3.log | T4 31.38 MB/s PASS; all codecs FAIL; native download timeout 30 s |
| pc-verification-4.log | T4 31.42 MB/s PASS; same codec/download failures after direct native anchor change |
| pc-verification-5.log | T4 24.53 MB/s PASS; codecs/download FAIL; loopback 167.25 / 510.99 MB/s |
| pc-verification-6.log | Diagnostic route now permits same-origin blob URLs; T4 24.58 MB/s PASS; codecs/download FAIL; loopback 165.13 / 510.98 MB/s |
| pc-verification-final.log | Separate PC home; T4 26.71 MB/s PASS; codecs/download FAIL; loopback 170.00 / 502.45 MB/s. Exit 1 enforces required gates |

Initial pytest collection failed because server.py did not yet exist. Red/green
regressions reproduced missing download measurement (1 failure/15 passes),
concurrent result loss and false resume evidence (2 JS failures), and lost claim
state on restart (1 failure/16 passes). Final suites pass after fixes.
The first generation failed because bundled FFmpeg lacks SVT-AV1; encoder
inventory identified libaom-av1, used successfully in the final recipe.

Initial dependency download hit forbidden outbound sockets (10013); reviewed
escalated installation succeeded. WebKit download was also reviewed and succeeded.
Get-NetIPAddress was denied; socket discovery succeeded. An ad hoc name probe had
a shell quoting syntax error; the corrected verifier recorded name resolution.
No automatic approval rejection occurred and no denied delete was bypassed.

## T1-T9

| ID | PC automated result | iPad result |
| --- | --- | --- |
| T1 | PASS certificate fields/Python TLS; browser trust NOT_RUN | pending owner check |
| T2 | NOT_RUN real Home Screen install; manifest/layout supplied | pending owner check |
| T3 | NOT_RUN Apple permission/subscription/delivery; scheduler/UI supplied | pending owner check |
| T4 | PASS synthetic Files upload, actual abort, subsequent transfer and hash; Photos picker NOT_RUN | pending owner check |
| T5 | FAIL Windows WebKit codecs; PASS Range and faststart | pending owner check |
| T6 | FAIL browser download; PASS 1 GB loopback; background NOT_RUN | pending owner check |
| T7 | NOT_RUN OS sharing/Save Video; all sample sizes generated | pending owner check |
| T8 | NOT_RUN real clipboard/share target; controls/manifest supplied | pending owner check |
| T9 | NOT_RUN actual lock/unlock; SSE recovery implementation supplied | pending owner check |

## GUI operations / Expected versus Actual

Playwright used exactly iPad Pro 11 on Windows WebKit against the LAN IP: opened
HTTP claim, followed HTTPS finish, selected synthetic Files video, clicked three
codec tests and 1 GB foreground download. Full-page screenshot was generated and
visually inspected: T1-T9 controls and result text visible without clipping.
This is not a physical iPad or native-window owner check.

Expected claim/resumed upload: observed success in the diagnostic context.
Expected codec frame/seek and native download: observed failures above.
Expected fixed mDNS lookup: failed; PC-name fallback worked.
Expected iPad tests: intentionally pending the owner's later session.

## Known limits / Questions for the designer

1. Decide how to satisfy the browser CA-trust/video/download gates within the
   Windows-settings restriction, or explicitly approve a different validation
   platform. Python TLS success is not a substitute for the requested gate.
2. mDNS registration did not establish resolution. Windows responder conflict
   versus multicast/firewall filtering is not established. Recheck after the
   owner's Private firewall permission; use PC-name fallback for diagnosis.
3. Private-CA push, iPad background downloads and OS share-target availability
   require owner measurements. Push needs outbound Apple internet access. AV1
   decode depends on the real iPad.
4. Check whether Safari's paired cookie carries into the Home Screen app. The
   sheet instructs reporting setup failure if not; no new pairing UX was invented.
5. Whole-file WebCrypto hashing and T7 sharing can exhaust iPad memory. A process
   kill cannot guarantee a final POST. T7 saves load-start and selected size so
   the owner can report after reopening. Native download needs Files observation.
6. First HTTP GET can be claimed/intercepted by trusted-LAN peers, as specified;
   this is a disposable measuring tool, not production authentication.

Official references checked: [Apple TLS requirements](https://support.apple.com/en-us/103769)
(RSA >=2048, SHA-2, SAN, serverAuth), [Apple lifetime policy](https://support.apple.com/en-us/102028)
(the 398-day preinstalled-root rule excludes manually installed roots; task's
stricter bound is still followed), [WebKit push](https://webkit.org/blog/13878/)
and [Playwright OS codec differences](https://playwright.dev/python/docs/browsers).
Documentation is not treated as runtime proof.

## Changed files

- `.ai/LAST_REPORT.md`
- `spikes/ipad/server.py`
- `spikes/ipad/generate_samples.py`
- `spikes/ipad/verify_pc.py`
- `spikes/ipad/test_server.py`
- `spikes/ipad/test_browser_logic.cjs`
- `spikes/ipad/pytest.ini`
- `spikes/ipad/requirements.txt`
- `spikes/ipad/README.md`
- `spikes/ipad/OWNER_CHECK.md`
- `spikes/ipad/static/index.html`
- `spikes/ipad/static/app.js`
- `spikes/ipad/static/sw.js`
- `spikes/ipad/static/manifest.json`
- `spikes/ipad/static/style.css`
- `spikes/ipad/static/icon.svg`

Fresh reviewer found queue concurrency loss, false resume evidence, an unenforced
H.264 gate and nonpersistent claim state. All four were fixed. Queue/resume/claim
have red/green regressions; final verifier exits 1 for observed required-gate
failures. No second reviewer pass is claimed.

## Disk / cleanup

First disk snapshot was after environment/bootstrap downloads, not before them.
Full cycle-start free space and exact full-cycle growth cannot be reconstructed.
Sizes below are logical file bytes, not allocated space or drive-space deltas.

Before deletion, candidates were inventoried and recorded here:

| Contained development path | Measured bytes | Purpose |
| --- | ---: | --- |
| work/scratch/ipad-pc-check | 1,671,941,455 | Generated media/uploads, CA/keys/device hashes, PC test state |
| work/scratch/r0-pytest | 29,774 | Isolated pytest homes |
| work/scratch/r0-pytest-cache | 1,487 | Spike pytest cache |

Pre-existing work/scratch/owner-check is 42,232,471 B; contents were not read and
will not be deleted. Preserving other-session artifacts takes precedence over
assuming ownership; all of scratch is therefore not empty. Existing scratch/tmp
was zero bytes. No older-cycle evidence/cache was pruned. Dedicated retained spike
cache: 407,064,025 B (environment, WebKit, FFmpeg, winldd). Shared uv-cache bootstrap
growth is not fully attributed.

Final disk table (decimal GB; first snapshot is after bootstrap):

| Measurement | First measured | End |
| --- | ---: | ---: |
| C free | 345.847656448 | 345.838391296 |
| D free | 881.249169408 | 881.247227904 |
| Current package | 0.125288579 | 0.125288579 |
| This cycle evidence | 0.000182857 | 0.002145802 |
| Scratch | 0.042261476 | 0.042232471 |
| Cache (complete) | 12.021960869 | 12.021960869 |

All three listed cleanup candidates were removed successfully: respectively
1,671,941,455 / 29,774 / 1,487 logical bytes, total 1,671,972,716 bytes. Each target
was resolved under work/scratch and checked for reparse points before native
PowerShell deletion. No deletion was refused. No generated media, CA, keys,
subscriptions, tokens or PC-test homes remain. Pre-existing owner-check remains
untouched, so the entire scratch-empty rule is not claimed satisfied.

Measured persistent-folder delta since the late first snapshot (repo + package +
cycle evidence + cache, disjoint rows) is +1,957,796 bytes, about 0.001958 GB.
Dedicated bootstrap additions are 0.407064025 GB, already present at that first
snapshot. Shared uv-cache/bootstrap changes before that snapshot are not fully
attributed, so the exact full-cycle 1 GB growth gate is NOT_PROVEN rather than
silently passed. The complete cache is below its 40 GB cap and cycle evidence
is below 300 MB. Drive-wide free changes are not used to infer cleanup bytes.
Evidence/report writes after the table can add a few KB; the table is a snapshot.

## For the owner

- Operator: perform Git status/diff checks, review/stage/commit/push only the
  listed source/report files. Codex performed no commit or push.
- Designer: review remaining section-3 failures and validation-platform decision;
  this is not COMPLETED.
- Operator: regenerate samples, start server with --redo-pairing and leave it
  running for the owner. Restart if two minutes pass.
- Owner only: allow the Windows firewall prompt on **Private networks only**.
  Codex changed no firewall, network profile or Windows certificate-store setting.
- Owner only: every iPad action in OWNER_CHECK.md; remove the temporary CA profile,
  Home Screen app and synthetic Files/Photos videos afterwards.
- Preserve or independently review pre-existing scratch/owner-check. It belongs
  to no confirmed VE-R0 generated artifact and was left untouched.

## Intentionally not performed

No product changes, engine-service implementation, deployment, Windows settings
changes, model/video-site downloads, iPad operations, native desktop app launch,
Git mutations, broad product test/build or unrelated cleanup. No tests were
skipped/disabled/loosened to make failures green. This Python/static spike has
no packaging build beyond the syntax and execution checks above.
