# CURRENT_TASK: VE-R1c (Mac browser support, library thumbnails, seek-bar preview)

> Follow `AGENTS.md` and `CLAUDE.md` on `main` for the workflow. This file defines only the work.

- **Task ID:** VE-R1c
- **Date:** 2026-11-03
- **Author:** Claude (designer and reviewer)
- **Implementer:** Codex
- **Branch:** `claude/project-thread-yyrl3q` at the commit that adds this file, on top of `main` 739db33 (PR #18, VE-R1b, merged). A new draft PR follows.
- Write a new `.ai/LAST_REPORT.md` for VE-R1c; keep the older reports below it.
- Same workspace and isolation rules as VE-R1b. The owner's real remote service runs from this checkout. Do not start, stop, install or restart it, and do not touch its home, library, task or firewall rules. If a dependency change is needed, stop and report BLOCKED (the operator must stop the service first).
- Record a disk baseline at the start and report growth at the end.

## 1. Owner requests (2026-11-03)

1. The owner wants to use the same web app from a **Mac** on the home network, in addition to the iPad.
2. The **Library** shows each video as a **thumbnail** instead of a text list.
3. While **dragging the seek bar** (touch or mouse) and while **hovering** over it with a mouse, a **small preview window** above the bar shows the frame at that time.

This reverses the earlier "no thumbnails or previews" decision for the library only. Processing still keeps nothing outside the library: sources, intermediates and job records are deleted at job end as now.

## 2. Work

### 2.1 Mac (Safari first; Chrome on macOS as a second browser)

1. **Setup page** (`http://<PC>.local:8080/`): detect macOS (a Mac desktop browser, not an iPad that reports "Macintosh"; use `navigator.maxTouchPoints` on the client side). For a Mac, show these steps: download the CA profile, open **System Settings > General > Device Management** (or **Profiles**, depending on the macOS version), install it, and confirm that HTTPS opens without a warning. Keep the iPad steps unchanged. If installing the profile does not make Safari trust the CA, show the Keychain Access fallback ("Always Trust" for SSL). Verify the real wording on the owner's macOS version only if a Mac is reachable; otherwise write the steps from Apple's documentation and mark them unverified in the report.
2. **Pairing in a normal browser tab:** on a Mac, the Home Screen requirement does not apply. Allow pairing from a normal Safari or Chrome tab (the cookie lives in that browser). "Add to Dock" in Safari is optional, so mention it in one line. A Mac claims through the same 2-minute window that "Redo pairing" opens, and each paired device gets its own cookie. The device label distinguishes "Mac, Safari N", "Mac, Chrome N" and "iPad, Safari N" (use a client hint sent at claim time; the server still validates it).
3. **Wording:** replace "this iPad" with "this device" where the text is shared, or pick the word per platform. The Settings tab lists the paired devices (label and paired date). Device removal is still R2.
4. **Download on a Mac:** use a normal file download (the existing one-time `/dl/<token>` link with `Content-Disposition: attachment`) for every size. Do not use `navigator.share` or the Safari hand-off on a Mac.
5. **Add on a Mac:** the file picker works as on the iPad. Also accept **drag and drop** of one video file onto the Add tab. Upload limits and resume are unchanged.
6. **Notifications on a Mac:** Safari on macOS uses `web.push.apple.com` (already allowed). Also allow Chrome's push service (`fcm.googleapis.com`, HTTPS, the same strict endpoint checks as now). Other push hosts stay refused.
7. **Keyboard on a Mac:** in the player, Space plays and pauses, and Left and Right seek 5 seconds.

### 2.2 Thumbnails and preview images (library sidecar)

1. For each library video, create:
   - a **poster** JPEG (short side 270 px, frame at 10 % of the duration, but not a black frame: skip ahead up to 3 times if the mean luma is below 16);
   - a **storyboard** for the seek preview: frames every `max(2 s, duration / 200)` seconds, each 160 px wide (height kept to the aspect ratio), packed into JPEG sheets of at most 10 x 10 tiles, plus a small JSON index (interval, tile size, sheet count).
2. Store them in a hidden folder inside the library, `<library>/.videoenhancer/<item id>/`. The library list skips this folder. Use the item id the library already uses. Delete the sidecar when the video is deleted, and remove orphaned sidecars (no matching video) at service start.
3. Generate them **after** a job publishes its video and **after** its Ready notification, so the notification is not delayed. Also generate them in the background for videos that have none (existing videos, or videos copied into the folder by hand), one at a time, at low priority, never while a job is running a GPU segment. Use FFmpeg on the CPU with keyframe-only decoding where it is good enough (`-skip_frame nokey`); fall back to full decoding for videos with sparse keyframes (keyframe gap larger than the storyboard interval). Cap the storyboard at 8 MB per video.
4. **API** (device cookie required): `GET /api/library/{id}/poster.jpg`, `GET /api/library/{id}/storyboard.json`, `GET /api/library/{id}/storyboard/{n}.jpg`. Send `Cache-Control: private, max-age=86400` and an ETag from the video's signature. Return 404 while the image is not ready; the client shows a neutral placeholder.

### 2.3 Library grid

1. Replace the list with a responsive grid of cards: poster (16:9 box, letterboxed, black background), title (two lines at most), duration and size. Tapping or clicking a card opens the player as now. Keep the storage bar and the "in progress" line above the grid.
2. Lazy-load posters (`loading="lazy"`) and keep the page usable with 500 videos.

### 2.4 Player with seek preview

1. Use custom controls over the `<video>` element: play or pause, the current time and the duration, a seek bar, volume (Mac only; iPadOS has no volume control in the page), and full screen.
2. **Seek preview:** while dragging the seek bar (touch or mouse), and while hovering over it with a mouse, show a small window above the pointer with the storyboard tile for that time and the time text. Keep the window inside the player edges. Without a storyboard, show only the time text.
3. Full screen: on a Mac, use the Fullscreen API on the player container so the custom controls stay. On the iPad, `webkitEnterFullscreen` on the video is acceptable (native controls take over in full screen). Say in the report which one each platform uses.
4. Range streaming, the Download button and Delete stay as they are.

## 3. Tests

- Python: poster and storyboard generation on generated clips (landscape, portrait 1080x1920, a black first second, sparse keyframes), the 8 MB cap, the sidecar is hidden from the list and deleted with the video, orphan cleanup, the background generator waits while a GPU segment runs, the image routes need the cookie and send the ETag and cache headers, the Chrome push endpoint is accepted and other hosts are refused, the device-label hint is validated.
- JavaScript: platform detection (iPad that reports Macintosh vs real Mac), the tile and position maths for a given time and bar width, keeping the preview window inside the edges, drag-and-drop accepting one video file, and the download path chosen per platform.
- Browser: WebKit and Chromium smoke tests at a Mac-like viewport (1440x900, mouse) and an iPad viewport (1180x820, touch): the grid renders posters, hover and drag show the preview, and the keyboard shortcuts work. On Windows WebKit, video playback is a known platform limit (see VE-R1a), so check the controls and the preview with a paused or poster-only video.
- `ruff check`, `ruff format --check`, the CI CPU pytest command, the node tests and the desktop E2E suite.

## 4. Allowed files

`src/videoenhancer/remote/**`, minimal hooks in `src/videoenhancer/service/engine.py` (GPU-busy signal for the background generator only), `tests/**`, `docs/REMOTE.md`, `docs/API.md`, `.ai/LAST_REPORT.md`.

## 5. Done when

Sections 2 and 3 pass, the diff contains only allowed files, and the report lists test counts, the time and size of thumbnail generation for a 10-minute 1080p video, the disk baseline and growth, and the exact owner check steps for the iPad and the Mac.

## 6. Operator after the commit (run only after designer review)

1. `ve remote restart` on the real home. Confirm the paired device count is unchanged, and report `ve remote status`.
2. Report how many existing library videos have their poster and storyboard after 10 minutes.
3. The owner then checks on the iPad (grid, scrub preview) and pairs and checks the Mac (setup, pairing, grid, hover preview, download, one upload, notification).
