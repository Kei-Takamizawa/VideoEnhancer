# VideoEnhancer on an iPad

The Windows PC runs the engine without a visible window. Use the iPad Home Screen
web app on the same home Wi-Fi to browse, play, save and permanently delete videos
in the PC's library. Add a video by pasting its URL or choosing a video from
Photos or Files. The PC uses the saved processing defaults and starts immediately;
the iPad has no processing progress screen or job history. Notifications announce
completed or failed videos.

## Install and manage the service

Run these commands from the engine checkout using its `.venv`. Set `VE_HOME` to
the active engine home first. Installation changes only the current user's
Scheduled Task and Start-menu shortcut without administrator rights. Firewall
setup asks for one UAC approval; declining it does not prevent installation.

```powershell
$env:VE_HOME = '<active engine home>'
& .\.venv\Scripts\ve.exe remote install
& .\.venv\Scripts\ve.exe remote status
& .\.venv\Scripts\ve.exe remote pair
```

`remote install` creates a local certificate authority and server certificate,
enables the gateway, registers the **VideoEnhancer** task at sign-in, creates
**VideoEnhancer - Redo pairing**, starts the service through that Scheduled Task
and opens pairing for two
minutes. Running installation again updates the same task and shortcut. The
task uses this checkout's `.venv\Scripts\pythonw.exe`, so keep the checkout and
virtual environment in place. Failed starts are retried three times, one minute
apart.

Installation also adds a **VideoEnhancer (iPad)** inbound TCP allow rule for the
gateway and setup ports, limited to the **Private** profile and the actual
windowless Python image behind the virtual environment launcher. It removes
only Block rules named **Python** or **pythonw.exe** for that exact program and
lists the removed rules. Other programs' rules and the network profile are left
alone. Status includes connected interface profiles, the matching allow rule
and Block rules for that program, or an explicit status-read error. If the active
network is Public, set it to Private in **Settings > Network & internet**.

`remote pair` opens another two-minute pairing window without removing existing
devices. The Start-menu shortcut does the same and displays one message box with
the setup address and closing time. That message closes automatically when the
window expires. `remote status` shows service and gateway
availability, addresses, certificate expiry, device count and pairing state.

`ve remote stop` gracefully shuts down the service through its authenticated
loopback endpoint. `ve remote restart` stops it, waits for shutdown and starts
the Scheduled Task again. These commands preserve paired devices, sources,
unfinished jobs, certificates and the library. They do not reinstall the task
or change firewall rules. Installation also uses the task, rather than leaving
the service attached to the installation shell.

For a foreground diagnostic run, use `ve serve --remote`. Ordinary `ve serve`
keeps its existing behavior unless the saved `remote_enabled` setting is true.
The desktop may connect to the same service until it is retired. Closing the
desktop leaves a remote-enabled service running.

```powershell
& .\.venv\Scripts\ve.exe remote uninstall
# Also revoke every paired device, while keeping certificates and the library:
& .\.venv\Scripts\ve.exe remote uninstall --forget-devices
```

Uninstall removes the task, shortcut and only the **VideoEnhancer (iPad)** firewall
rule (with UAC approval), and stops the service. It never deletes
library files. Without `--forget-devices`, existing devices remain paired when
the service is installed again.

## First iPad setup

1. Open the printed setup address in Safari at any time, normally
   `http://<COMPUTERNAME>.local:8080/`.
2. Download the **VideoEnhancer Local CA** configuration profile. In Settings,
   open **General > VPN & Device Management**, select the downloaded profile and
   tap **Install**.
3. Open **Settings > General > About > Certificate Trust Settings** and enable
   full trust for **VideoEnhancer Local CA**.
4. Follow the setup page's HTTPS link, normally
   `https://<COMPUTERNAME>.local:8443/`. In Safari choose **Share > Add to Home
   Screen**, leaving **Open as Web App** on.
5. Open that Home Screen app and tap **Pair this iPad**. If the two-minute window
   closed, run **VideoEnhancer - Redo pairing** on the PC and try again.

Pair inside the Home Screen app: Safari and the Home Screen app have separate
cookie storage. The first accepted claim closes the pairing window immediately.
An open window permits a device on the home network to claim pairing, so open it
only when setting up an intended device. The HTTP setup page also offers the
plain CA certificate at `/ca.cer` for manual inspection.
The setup page and certificate stay available when pairing is closed. Only the
claim needs an open window. When you are ready to pair, click
**VideoEnhancer - Redo pairing** on the PC, then tap **Pair this iPad** within
2 minutes. **Try again** on the unpaired screen rechecks the pairing state.

Use the address printed by `remote status`. The PC name with `.local`, its plain
computer name and its current private IPv4 addresses are certificate names.
A fixed `videoenhancer.local` alias is not used. If the PC address changes, restart
the service so its certificate includes the new address. The CA is retained;
renewing the server certificate does not require a new iPad profile.

## Library and saving videos

The library includes regular `.mp4`, `.m4v` and `.mov` files directly inside its
folder. Hidden files, temporary files, subfolders and symbolic links or Windows
reparse points are excluded. The default folder is
`D:\VideoEnhancer\完成動画` when drive D exists; otherwise it is
`%USERPROFILE%\Videos\VideoEnhancer`. The folder is created on first use. An
absolute `library_folder` setting overrides this location; changing it from the
iPad is planned for R2.

Videos appear newest first. Opening an item streams it with the browser's normal
video controls. An unreadable file remains listed with **Can't read this video**
and can still be deleted. There are no thumbnails or posters.

**Download** loads the entire file into one Blob, shows byte progress, then
**Save video** opens the iPad share sheet so you can choose **Save Video** or
**Save to Files**. The File is built from that single Blob; a separate response
counter updates progress without retaining chunks.
Cancelling the share sheet is harmless. The iPad needs enough memory for the
complete file; a system-terminated app cannot reliably diagnose its own memory
failure. Load/share failures show the error name beneath the message and send
bounded diagnostics without the video name.

Above `share_limit_bytes` (default **900,000,000 bytes**, configurable in the
engine settings), the app offers **Save to Files with Safari** directly. The same
option appears when sharing fails. It creates a one-time HTTPS attachment link
valid for 10 minutes and tries `x-safari-https://` to open Safari. If that does
not open Safari, use **Copy link** and paste into Safari to save to Files. This
does not navigate to an HTTPS attachment inside the Home Screen app. Actual
iPadOS scheme support and the large-video save need the owner's check.

**Delete** asks for confirmation with the video's name and size. Deletion is
permanent and bypasses the Recycle Bin. The service refuses deletion while it is
actively transferring that file. Stop playback or wait for the download to finish
before retrying.

The storage bar describes the drive holding the library: library video bytes,
other used space and free space. Its labels use decimal GB. Settings shows the
PC name and address, certificate expiry, this device's pairing date and app
version; there are no settings controls in R1a.

## HTTPS gateway API

All paths below use the HTTPS port. API responses have `Cache-Control: no-store`.
JSON timestamps are either the documented Unix seconds for library modification
times or ISO 8601 UTC strings for session and certificate dates.

| Method and path | Result |
| --- | --- |
| `GET /` and fixed shell assets | Public app shell; it renders the pairing screen until authorized. |
| `GET /api/session` | Unpaired: `{paired:false,pairing_open}`. Paired: `{paired:true,device_label,paired_at,pc_name,addresses,cert_expires,version,share_limit_bytes}`. |
| `POST /api/pair/claim` | Claim the open pairing window; sets the device cookie. No existing cookie required. |
| `GET /api/library` | `{items:[...]}` newest first. Items contain `id`, `name`, `filename`, `mime`, `size`, `modified` (Unix seconds), `duration` (seconds), `width`, `height`, `codec`, and optional `error`. Probe failures use null metadata. |
| `GET /api/library/{id}/video` | Video bytes; accepts one `Range: bytes=...` range, including suffix ranges. |
| `HEAD /api/library/{id}/video` | The same video response headers without a body. |
| `POST /api/library/{id}/download-link` | Device cookie and Origin required; returns `{url}` for a one-time, 10-minute HTTPS attachment. |
| `GET /dl/{token}` (also `HEAD`) | Token authorizes the download without a cookie. Supports Range; UTF-8 `Content-Disposition` filename. |
| `POST /api/client-event` | Device cookie and Origin required; JSON body at most 2,048 bytes. Logs `{kind,error_name,error_message,size_bytes,can_share,phase}`; names and URLs are excluded. |
| `DELETE /api/library/{id}` | Permanently deletes the item; returns `{deleted:true}`. |
| `GET /api/storage` | `{total,free,library_bytes,drive_label}`; capacities are bytes. |

Except for session discovery and pairing claims, API requests require a valid
`ve_device` cookie. Every state-changing request also requires an exact same-origin
HTTPS `Origin` header. Responses use ordinary HTTP status codes: `401` unpaired,
`403` wrong/missing Origin, `409` closed pairing window or active transfer,
`421` wrong Host, `429` claim/link limit, `413` oversized diagnostics, and `416` unsatisfiable Range. A `416`
response includes `Content-Range: bytes */<size>`. Video responses include
`Accept-Ranges`, the correct content length and MIME type, and `Content-Range`
with status `206` for a valid range. Invalid identifiers are rejected rather than
interpreted as filesystem paths.

Download links use random 256-bit tokens; only SHA-256 hashes are held in memory.
Restart revokes all links. HEAD and invalid ranges do not consume a link.
Successful byte ranges accumulate until they cover the complete file, then the
link returns 404; expired links also return 404. An overlapping active request
gets 409. A completed transfer means the server wrote and flushed its bytes;
it cannot confirm that the user saved them on the device. Do not share the link:
anyone holding it on the allowed LAN can download until completion or expiry.
At most 256 unexpired links can exist. Diagnostic kinds are `load_failure`,
`share_failure`, and `share_check`; phases are `load`, `playback`, and `share`.
Unknown error names/messages become generic values to keep names out of logs;
messages are at most 200 characters. No arbitrary payload fields are logged.

### Token-authenticated loopback route

`POST /v1/remote/pairing` opens pairing for two minutes on the running gateway.
It uses the existing `serve.json` token, loopback Host and desktop Origin rules;
the HTTPS device cookie does not authorize it. The response contains gateway
status including `setup_address` and `closes_at`. This route is used by
`ve remote pair`. A desktop `POST /v1/shutdown` receives `409` while the remote
gateway is enabled, so closing the desktop cannot shut down the headless service.
The local uninstall command explicitly requests shutdown with
`{"remote_uninstall":true}` in the token-authenticated shutdown body; a normal
desktop shutdown does not send this flag.

## Security and local state

- Both listeners are IPv4-only. Only loopback, `10/8`, `172.16/12`, `192.168/16`
  and `169.254/16` sources are accepted. Other sources are disconnected without
  an HTTP response. Host must match a certificate name and the listener's port.
- The plain HTTP port always serves only setup and public certificate downloads.
  It reports whether pairing is open and how to open it. It serves no API,
  video or device cookies.
- Device cookies contain random 256-bit secrets and are `HttpOnly`, `Secure`,
  `SameSite=Strict`, scoped to `/`, with `Max-Age=34560000`. Only SHA-256 hashes
  are saved alongside device labels and creation/last-seen times. Claims are
  limited to five attempts per minute per source address.
- `VE_HOME/remote/` holds the CA, server certificate and key, devices, pairing
  state and ffprobe cache. Private keys and device state use user-only Windows
  ACLs, or mode `0600` on POSIX. Do not publish or copy this directory into Git.
- The CA lasts ten years. Server certificates last 397 days and are reissued at
  startup when fewer than 30 days remain or the PC's private addresses change.
  CA name constraints are not used because iPadOS acceptance was not established
  by the R0 spike.
- Access logs contain only method, route template, status and duration. They
  exclude query strings, file names, cookies, tokens and device secrets.
  Download routes are logged as `/dl/{token}`. Client diagnostic logs contain
  only the sanitized fields described above. TLS handshakes run in connection
  workers with a 15-second timeout, so a stalled handshake does not block accept.
- The app uses a strict Content Security Policy without inline scripts,
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Its service
  worker caches fixed shell files only, never API responses or video content.

If the PC cannot be reached, check its power and Wi-Fi connection and tap
**Retry**. Real iPad cookie retention after restart and after 24 hours, trusted
profile setup and saving a 1 GB file need the owner's device checks; desktop
browser automation does not establish those results.

## Adding and finishing videos

In **Add**, paste a video URL and tap **Check link**. Clipboard permission is
optional; touch and hold the field to paste when the Paste button is refused.
The app automatically selects the best supported SDR stream with a short side
no larger than 1080 pixels. Playlist entries are checked by default; unavailable
entries cannot be selected. If link tools are missing, **Install link tools**
shows the existing release plan and notices before asking for explicit consent.

Choose a file from Photos or Files to upload it. The PC rejects files over 20 GB
or over 90% of currently available incoming-drive space before accepting bytes.
Chunks are at most 4 MiB; the PC persists the accepted offset and verifies the
complete SHA-256 digest before probing. A refused video above the 1080p class,
HDR input or invalid digest is deleted. Keep the app open during transfer.
The app saves the selected file in device-local IndexedDB for reopening and
resuming. If the browser cannot persist it, the app explicitly asks you to keep
it open; device storage quotas and actual iPad retention need an owner check.

The PC removes abandoned sessions at service start and hourly: unfinished uploads
expire 24 hours after their last accepted chunk, and completed uploads expire
24 hours after verification if they were never added to a job. Uploads belonging
to jobs are preserved. An expired resume shows "This upload expired. Choose the
video again." Network reads and hashing do not hold the shared upload lock;
another update to the same upload is refused until the current update finishes.

Before adding an uploaded video, the app displays the local predicted finish
time, including work already queued. An unstarted URL transfer has no measured
network speed, so its end-to-end finish time is unknown until downloading starts;
processing cost alone is not presented as an end-to-end promise. Unfinished
downloads also make subsequent queue finish times unknown. After admission,
Library displays a compact in-progress summary and a confirmed Cancel action,
without percentages or live processing progress.

Gateway processing bypasses the saved schedule for that service session; it does
not rewrite the schedule. Sources are isolated under `VE_HOME/remote/incoming/`.
Outputs initially have hidden `.partial.mp4` names in the library. Only completed
files are published, with Windows-safe titles of at most 120 UTF-16 code units,
` (enhanced).mp4`, and ` 2`, ` 3`, etc. before the extension on collisions.
Publication never overwrites another file. After completion, failure or
cancellation, the source folder, job/segment files, previews and job record are
deleted. A durable finishing journal retries interrupted cleanup after restart;
unfinished processing retains its source and uses the existing engine recovery.

Only the nameless completion summary is retained in `remote/activity.log`: UTC
time, outcome, preset, input resolution/duration, output bytes, processing
seconds and a fixed failure category. The log is capped at 1,000,000 bytes by
dropping old lines. Remote job diagnostics are suppressed; transfer access logs
use route templates. The PC requests system wakefulness during remote processing
and transfers, without holding the display on. Upload wakefulness has a 60-second
idle lease so a disconnected browser cannot keep the PC awake forever.

## Notifications

On the iPad Home Screen app, tap **Turn on notifications** in Library. Permission
is requested directly from that tap. Settings shows the current iPad's status
and **Send a test notification**. Subscription secrets are stored with the paired
device using the existing private-file permissions. VAPID keys are generated
once in `VE_HOME/remote/vapid.pem`; the subject is
`https://github.com/Kei-Takamizawa/VideoEnhancer`.

Done notifications say **Ready** and open the completed library item. Failures
say **Couldn't finish** with a generic plain sentence. Payloads are encrypted by
Web Push and remain eligible for delivery for 24 hours; test notifications expire
after one hour. Payloads, endpoints and keys are never logged. The push sender accepts
only HTTPS Apple Web Push subscriptions, does not follow redirects or use
environment proxies, and removes subscriptions on HTTP 404 or 410. Gateway logs
record only HTTP status and an allowlisted Apple reason. Real iPad permission,
delivery and notification tap behavior remain device checks.

### R1b device-cookie routes

All routes below require a paired device cookie. Writes require an exact HTTPS
Origin and one decimal Content-Length, with no Transfer-Encoding. JSON bodies
are limited to 65,536 bytes and must be objects; upload chunk bodies are streamed
without whole-file buffering. Operation and upload identifiers are device-owned.

| Route | Request / response |
| --- | --- |
| `POST /api/links/check` | `{url}` -> `{id,state}`; missing tools -> `{state:"tools_required",tools_required:true}`. |
| `GET /api/links/check/{id}` | `{id,state,entries?}`; entries include key, title, duration, selected dimensions/format, estimate or a safe error. |
| `GET /api/link-tools` | `{available}`. |
| `POST /api/link-tools/check` | `{}` -> operation ID; fetch its result to display the release plan. |
| `GET /api/link-tools/{id}` | `{id,state,result?,error?}`. |
| `POST /api/link-tools/install` | `{consent:true,plan_id}` -> operation ID; existing verified installation flow. |
| `POST /api/uploads` | `{name,size}` -> `{id,name,size,offset,ready}`. |
| `GET /api/uploads/{id}` | Current durable upload offset and readiness, plus probed media when ready. |
| `PUT /api/uploads/{id}/chunk?offset=N` | Raw bytes, maximum 4 MiB. Offset must match; retry from GET status after a dropped response. |
| `POST /api/uploads/{id}/finish` | `{sha256}` -> ready status and media; mismatch or refused input deletes the session. |
| `POST /api/estimate` | `{upload_id}` or `{check_id,entry_keys:[...]}` -> `{entries:[...]}` with `{finish,seconds,low?,high?}` estimates. Null finish/seconds means unknown. |
| `POST /api/jobs` | Same selection as estimate -> `{added:[{id}]}`. Client paths and output/settings overrides are not accepted. |
| `GET /api/jobs/active` | `{jobs:[{id,title,finish,seconds}]}` for this device; no percentages. |
| `POST /api/jobs/{id}/cancel` | `{}` -> `{cancelled:true}` after requesting engine cancellation; cleanup follows when work releases its handles. |
| `POST /api/push/subscribe` | PushSubscription JSON -> `{ok:true}`. |
| `POST /api/push/test` | `{}` -> `{ok,status}`. |

Authenticated `GET /api/session` also includes `push_key` (base64url P-256 public
key) and `notifications_on`. Unknown/malformed selections return 400, oversized
bodies return 413, and an unavailable processing engine returns 503.
