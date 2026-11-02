# iPad check — about 15 minutes, plus transfer time

Use your home Wi-Fi. Have a short non-private video available in Photos and
another in Files. Do not use cellular or a guest Wi-Fi network. The operator
starts the PC test server; no PC window needs to stay visible to you.

1. Ask the operator to generate the samples and start the server using the
   commands in README.md. If Windows asks about the firewall, the owner allows
   **Private networks only**. Codex must not change this setting.
2. Within two minutes, open Safari on the iPad and visit
   **http://videoenhancer.local:8080/pair**. Do not let another device open it
   first. Keep this tab open. If the name does not work, ask the operator for the
   PC-name `.local` address or its private IPv4 address and use that same name
   throughout the check. Do not switch between names after pairing.
3. If the page says **Pairing is closed**, ask the operator to stop the server
   with Ctrl+C and run this again from the repository:
   `& ..\cache\ipad-venv\Scripts\python.exe spikes\ipad\server.py --redo-pairing`.
   Open the address within two minutes. Refreshing a claimed page does not give
   the secret back: retain the original tab, or redo pairing.
4. On the claimed page, tap **CA profile** and allow the profile download.
   Open **Settings > General > VPN & Device Management** (or **Profile
   Downloaded**). Install **VideoEnhancer Local CA (spike)**. Enter your iPad
   passcode if asked. This is a temporary test profile.
5. Open **Settings > General > About > Certificate Trust Settings**. Turn on
   full trust for **VideoEnhancer Local CA (spike)** and confirm.
6. Return to the original Safari tab. Tap **finish pairing** within 30 minutes.
   You should see **Paired. Ready to test.** Do not bypass a certificate warning:
   retain what you saw for T1. If setup does not finish, tell the operator; do
   not install anything else to work around it.
7. In Safari, use Share > **Add to Home Screen** (it may be under More). Add the
   app, close Safari and open **VE spike** from its Home Screen icon. If it says
   to pair again, tell the operator: cookie transfer into the installed app is
   itself a result to investigate. T1: tap the warning/no-warning observation.
   T2: tap **Check Home Screen install**.
8. T3: tap **Allow notifications and send two pushes** and allow notifications.
   Close the app immediately. Wait 75 seconds. Look for notifications around
   10 seconds and 60 seconds. Reopen the app and tap whether both appeared.
   Record missing permission or notifications as failures, not successes.
9. T4: choose a video with **Choose from Photos**, selecting Photos in the picker.
   Wait for the result. Repeat with **Choose from Files**, selecting Files.
   The test aborts one request automatically and resumes. For real Wi-Fi loss,
   try a larger video: turn Wi-Fi off during upload, restore it, reopen the app
   and tap **Retry selected upload**. Keep the same file selected. Very short
   files may finish before a resume is possible; use a video larger than 8 MB.
10. T5: tap **Play H.264**, wait for its result, then repeat with **HEVC** and
    **AV1**. Seeking is automatic. Do not switch codec until a result appears.
    A playback error is a useful test result; it does not imply all iPads fail.
11. T6: tap the foreground 1 GB download and choose Files when Safari asks.
    Check the download indicator and final file. Tap whether it arrived.
    Repeat using the **background 30 s** link: switch away for 30 seconds, return,
    check Files and record the observation. Repeat with **background 3 min**,
    waiting three minutes. If a download completed before you switched away,
    it does not test background continuation; tell the operator. Server timing
    is saved automatically. Wait for each download before starting another.
12. T7: tap **Load 50 MB**, wait, then **Share loaded video**. Choose **Save
    Video** if offered. Check Photos, then tap **Save Video succeeded** or
    **Save Video missing or failed**. Repeat for 500 MB and 1 GB. If the app
    reloads or closes during a large file, reopen it and tap the failed
    observation (the last selected size is restored); tell the operator the size.
13. T8: copy a harmless web address, paste it into the URL field and tap
    **Record pasted URL**. Also try **Read clipboard**. In Safari, use Share on
    a harmless URL and look for **VE spike**. Select it if offered. If absent,
    return to this app and tap **App was not in the share sheet**. The actual
    URL is not saved in the measurement results.
14. T9: tap **Start sleep test**, lock the iPad for one minute, then unlock and
    return to this app. Wait up to 20 seconds for its result. The reconnect
    time is saved automatically. Leave the app open on Wi-Fi briefly so queued
    results can reach the PC.
15. Tell the operator you are finished. The results are already on the PC;
    there is no screenshot or file upload step. Mention any crash, reload,
    missing button or warning that prevented recording a result.
16. Remove the temporary trust afterwards: **Settings > General > VPN & Device
    Management > VideoEnhancer Local CA (spike) > Remove Profile**. Confirm the
    certificate is gone from Certificate Trust Settings. Remove the Home Screen
    app and the synthetic downloads/Photos videos if you no longer need them.
    The operator stops the server and removes its disposable scratch home.


## R0b re-check, about 5 minutes

1. Delete the old Home Screen icon. Open the HTTPS address in Safari, then
   Share > Add to Home Screen with **Open as Web App** on.
2. Open the app from the Home Screen. Ask the operator to start the server with
   `--redo-pairing`, then tap **Pair this app** within two minutes.
3. Run T2, then T3: allow notifications, close the app, and wait for both pushes
   (10 and 60 seconds). Reopen after 75 seconds and record what you saw.
4. Run T6 with **background 3 min**. Confirm whether the file arrived and whether
   transfer continued while backgrounded; an early completion is not that proof.
5. For T7 load **500 MB**, share, choose **Save Video**, then open Photos and
   confirm the video is present before recording success.

The operator uses `work/evidence/VE-R0b/owner-server.log` for request diagnosis;
owner records are in `ipad-results.jsonl`, PC automation in `pc-results.jsonl`.
