# VideoEnhancer on an iPad

The Windows PC runs the engine without a visible window. Use the iPad Home Screen
web app on the same home Wi-Fi to browse, play, save and permanently delete videos
in the PC's library. R1a provides Library and read-only Settings; adding processing
jobs and notifications come later.

## Install and manage the service

Run these commands from the engine checkout using its `.venv`. Set `VE_HOME` to
the active engine home first. Installation changes only the current user's
Scheduled Task and Start-menu shortcut; it does not need administrator rights.

```powershell
$env:VE_HOME = '<active engine home>'
& .\.venv\Scripts\ve.exe remote install
& .\.venv\Scripts\ve.exe remote status
& .\.venv\Scripts\ve.exe remote pair
```

`remote install` creates a local certificate authority and server certificate,
enables the gateway, registers the **VideoEnhancer** task at sign-in, creates
**VideoEnhancer - Redo pairing**, starts the service and opens pairing for two
minutes. Running installation again updates the same task and shortcut. The
task uses this checkout's `.venv\Scripts\pythonw.exe`, so keep the checkout and
virtual environment in place. Failed starts are retried three times, one minute
apart.

`remote pair` opens another two-minute pairing window without removing existing
devices. The Start-menu shortcut does the same and displays one message box with
the setup address and closing time. `remote status` shows service and gateway
availability, addresses, certificate expiry, device count and pairing state.

For a foreground diagnostic run, use `ve serve --remote`. Ordinary `ve serve`
keeps its existing behavior unless the saved `remote_enabled` setting is true.
The desktop may connect to the same service until it is retired. Closing the
desktop leaves a remote-enabled service running.

```powershell
& .\.venv\Scripts\ve.exe remote uninstall
# Also revoke every paired device, while keeping certificates and the library:
& .\.venv\Scripts\ve.exe remote uninstall --forget-devices
```

Uninstall removes the task and shortcut and stops the service. It never deletes
library files. Without `--forget-devices`, existing devices remain paired when
the service is installed again.

## First iPad setup

1. Open the printed setup address in Safari while pairing is open, normally
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

**Download** loads the entire file into a Blob, shows byte progress, then opens
the iPad share sheet so you can choose **Save Video** or **Save to Files**.
Cancelling the share sheet is harmless. The iPad needs enough memory for the
complete file; a system-terminated app cannot reliably diagnose its own memory
failure. Files are never offered through attachment navigation or a new window.

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
| `GET /api/session` | Unpaired: `{paired:false,pairing_open}`. Paired: `{paired:true,device_label,paired_at,pc_name,addresses,cert_expires,version}`. |
| `POST /api/pair/claim` | Claim the open pairing window; sets the device cookie. No existing cookie required. |
| `GET /api/library` | `{items:[...]}` newest first. Items contain `id`, `name`, `filename`, `mime`, `size`, `modified` (Unix seconds), `duration` (seconds), `width`, `height`, `codec`, and optional `error`. Probe failures use null metadata. |
| `GET /api/library/{id}/video` | Video bytes; accepts one `Range: bytes=...` range, including suffix ranges. |
| `HEAD /api/library/{id}/video` | The same video response headers without a body. |
| `DELETE /api/library/{id}` | Permanently deletes the item; returns `{deleted:true}`. |
| `GET /api/storage` | `{total,free,library_bytes,drive_label}`; capacities are bytes. |

Except for session discovery and pairing claims, API requests require a valid
`ve_device` cookie. Every state-changing request also requires an exact same-origin
HTTPS `Origin` header. Responses use ordinary HTTP status codes: `401` unpaired,
`403` wrong/missing Origin, `409` closed pairing window or active transfer,
`421` wrong Host, `429` claim rate limit, and `416` unsatisfiable Range. A `416`
response includes `Content-Range: bytes */<size>`. Video responses include
`Accept-Ranges`, the correct content length and MIME type, and `Content-Range`
with status `206` for a valid range. Invalid identifiers are rejected rather than
interpreted as filesystem paths.

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
- The plain HTTP port serves only setup and certificate downloads while pairing
  is open. When closed it tells the user to run Redo pairing. It serves no API,
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
- Gateway logs contain only method, route template, status and duration. They
  exclude query strings, file names, cookies, tokens and device secrets.
- The app uses a strict Content Security Policy without inline scripts,
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Its service
  worker caches fixed shell files only, never API responses or video content.

If the PC cannot be reached, check its power and Wi-Fi connection and tap
**Retry**. Real iPad cookie retention after restart and after 24 hours, trusted
profile setup and saving a 1 GB file need the owner's device checks; desktop
browser automation does not establish those results.
