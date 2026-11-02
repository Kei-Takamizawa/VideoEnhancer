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
