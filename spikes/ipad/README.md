# iPad browser spike (VE-R0)

This disposable measuring tool tests HTTPS, first-device pairing, notifications,
upload, playback, downloads, sharing and reconnect behavior. It imports no product
code. Results from desktop WebKit do not establish iPadOS Safari support.

Run from the repository in PowerShell. All commands use session-only environment
variables. The operator, not Codex, starts the owner session and leaves it running.

```powershell
. .\local-env.ps1
$env:PYTHONDONTWRITEBYTECODE = '1'
uv venv ..\cache\ipad-venv --python .venv\Scripts\python.exe
uv pip install --python ..\cache\ipad-venv\Scripts\python.exe -r spikes\ipad\requirements.txt
& ..\cache\ipad-venv\Scripts\python.exe -m playwright install webkit
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\generate_samples.py
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\server.py --redo-pairing
```

On subsequent starts, omit environment creation and package/browser installation.
Regenerate samples after cycle cleanup. Generation temporarily uses about 1.6 GB;
desktop verification can temporarily add another 1 GB download and uploads.
Samples are synthetic 1080p60, SDR, 8-bit, silent MP4s with `moov` before `mdat`.
The large files repeat the H.264 source using FFmpeg stream copy, without padding
or downloading media. Actual file sizes are in scratch `sample-metadata.json`.

Default home: `work/scratch/ipad-spike`. CA private key, leaf key, VAPID key,
pending claim hash, token hash, subscription and media live there. Treat that
directory as private. It is deleted at the end of this cycle. Do not publish it.
The HTTP claim page necessarily carries an unencrypted one-time secret: use only
trusted home Wi-Fi. A LAN peer can claim the first-device window, as specified.
Access logs are disabled so claim links and tokens are not logged.

`--redo-pairing` reopens the 120-second window; `--pair-seconds` changes its length
for tests. Stop the server with Ctrl+C before restarting. A claim closes the window
immediately, persists across restarts, and replaces the prior device record.
The claim expires after 30 minutes and is consumed once. Only hashes of the
claim and long-lived device token are stored. HTTPS sets a one-year
`Secure; HttpOnly; SameSite=Strict` cookie. There is no product account system.

Default listeners bind this PC's RFC1918 IPv4 addresses, HTTP 8080 and HTTPS 8443.
`--bind` may be repeated for selected local private addresses. Loopback is allowed
for automated measurements. `--no-mdns` is only for isolated tests. The leaf SAN
contains `videoenhancer.local`, the PC name plus `.local`, and all discovered
private IPv4 addresses. DHCP changes require a restart. The same root is reused
until scratch is cleaned; a new root requires reinstalling the iPad profile.

HTTP exposes only `/pair`, `/ca.mobileconfig` and `/ca.crt`. The fixed PWA static
files and `/api/pair/finish` are the only unauthenticated HTTPS surfaces; finish
requires the one-time secret. All other requests require the token. Hostnames and
HTTPS Origins are checked. There are no CORS grants. Files have fixed sample
names; upload IDs are SHA-256 digests. Uploads are limited to 8 GB per file and
4 MiB chunks. Do not use this single-device spike on an untrusted network.

## Checks

```powershell
. .\local-env.ps1
$env:PYTHONDONTWRITEBYTECODE = '1'
& ..\cache\ipad-venv\Scripts\python.exe -m pytest -c spikes\ipad\pytest.ini spikes\ipad\test_server.py -q --basetemp D:\my-workspace\VideoEnhancer\work\scratch\r0-pytest -o cache_dir=D:\my-workspace\VideoEnhancer\work\scratch\r0-pytest-cache
node --test spikes\ipad\test_browser_logic.cjs
node --check spikes\ipad\static\app.js
node --check spikes\ipad\static\sw.js
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\generate_samples.py --home D:\my-workspace\VideoEnhancer\work\scratch\ipad-pc-check
& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\verify_pc.py
```

Stop an owner server before `verify_pc.py`. The verifier temporarily starts the
real listeners on LAN and loopback, advertises mDNS, redoes pairing and removes
only its synthetic uploads inside the separate `work/scratch/ipad-pc-check` home. Never run it during
the owner check. It tests a real 1 GB foreground browser download, compares its
hash, and measures TLS-verified loopback transfers. Results and a screenshot go
to `work/evidence/VE-R0b`. Browser-generated JSONL records include `automated:true`.

Playwright does not expose a per-context root CA store for Windows WebKit. The
verifier separately checks the actual certificate using Python's CA-specific SSL
context and verifies default WebKit rejects the untrusted CA. Its browser flow
uses `ignore_https_errors` in one disposable context restricted to the selected
LAN host. **This diagnostic does not satisfy the requested browser CA-trust gate.**
No Windows certificate store or setting is modified. A failing H.264 gate makes
the verifier exit nonzero, after retaining available measurements.

## Interpreting measurements

- T1 is the owner's observation, separate from the PC certificate-field tests.
- T3 uses VAPID and only accepts HTTPS Apple push endpoints. Web Push requires
  outbound internet even though the app server is LAN-only. At 10 and 60 seconds
  the server sends notifications. The service worker displays each and attempts
  an authenticated receipt POST. Delivery or receipt failure with a private CA
  must be measured on the real iPad. No subscription endpoints are in reports.
- T4 computes a whole-file WebCrypto hash, then sends 4 MiB buffers. Whole-file
  hashing can run out of memory on a large iPad video. An actual observed fetch
  abort plus subsequent transferred bytes is required for `resume_ok`. Already
  uploaded files are hash-checked but do not count as resume evidence. A hash
  mismatch is retained for diagnosis; regenerate the disposable home to reset it.
- T5 records canplay, first rendered frame and completed seeks. Media errors and
  timeouts are failures. The codec support of Windows WebKit is not iPad support.
- T6 uses a native attachment link, not a JavaScript-buffered 1 GB download. The
  server records bytes queued, elapsed time, rate and disconnects. These are not
  proof that Files finished saving. Correlate the run ID with owner observations
  and visibility intervals. A transfer finished before backgrounding does not
  establish background support. Observation elapsed time includes the owner's
  wait and is not used as transfer throughput.
- T7 deliberately materializes each file to test Web Share memory/size limits.
  A share promise resolving does not prove Save Video worked: tap the separate
  Photos observation button. An OS process kill may prevent a final result;
  record the failure manually when reopening.
- T8 never saves the pasted URL in results. A declared manifest share target is
  not proof the OS offers it. Record absence explicitly on the iPad.
- T9 records a received SSE event after the page becomes visible, or a 20-second
  recovery failure. The owner must actually lock for one minute. It measures
  usable status recovery, which can reuse an existing connection.

Failed network result POSTs stay in a local queue and retry on reconnection or
the next result. A single drain prevents concurrent-result loss. Delivery is
at-least-once: if a POST is accepted but its response is lost, a retry may duplicate
it. This spike does not create a product history or engine log.

## References checked

- [Apple TLS requirements](https://support.apple.com/en-us/103769): RSA at least
  2048 bits, SHA-2 signatures, SAN DNS names and serverAuth EKU. Leaf lifetime is
  397 days plus five minutes, below this task's 398-day limit.
- [Apple lifetime policy](https://support.apple.com/en-us/102028): 398-day rule
  applies to preinstalled roots; manually installed roots are excluded from that
  particular policy. The stricter task limit is still followed here.
- [WebKit Web Push on iOS/iPadOS](https://webkit.org/blog/13878/): Home Screen web
  apps and user-gesture permission requests, iOS/iPadOS 16.4 or later.
- [Playwright browsers](https://playwright.dev/python/docs/browsers): media codecs
  depend on the OS; macOS is closer to Safari for video playback.


R0b: in the installed Home Screen app, an unauthorized session shows **Pair this
app**. Have the operator start `server.py --redo-pairing`, then tap that button
within two minutes. The HTTPS claim sets the cookie inside this app without
leaving it. Safari's separate session is replaced. HTTP remains available for
CA setup and the optional legacy Safari claim, using the same pairing window.
Automated records go to `pc-results.jsonl`; owner records to `ipad-results.jsonl`.
Request diagnosis is in `owner-server.log` (route templates, never query strings,
file names, cookie values or tokens). `unknown` means no display-mode header;
`server` on a record means it originated on the PC rather than in a page.


For repository-wide CPU/desktop checks on this workstation, this cycle verified
portable FFmpeg/ffprobe from the publisher SHA-256 and kept only those binaries
under `work/cache/r0b-ffmpeg`. Add that folder to the current shell PATH when
running CI-equivalent checks; do not change Windows PATH or settings. Read-only
Git checks also need the operator's installed Git on the session PATH. Desktop
CDP tests required reviewed execution outside the filesystem sandbox, still with
absolute isolated homes under `work/scratch`. The spike's dedicated environment
and its bundled FFmpeg remain sufficient for sample generation and spike tests.
