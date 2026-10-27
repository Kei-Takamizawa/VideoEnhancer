Task ID: VE-P1e-3c2-OC
Status: PARTIAL

## Scope and environment

Windows check cycle, 2026-10-26 local / 2026-10-27 UTC. Branch:
`claude/project-thread-6lra47`; HEAD:
`8af841686f5d8121ff97ce3d52981fba407930ed`. Initial read-only Git status was clean.
The sandbox denied Git execution; the escalated read-only check succeeded.
No Git mutations, product changes, test-feature builds, CDP or test hooks were used.
The existing CURRENT_TASK was retained in full without modification.

Only the production candidate was used for checklist measurements. All test data
was under `work/scratch/owner-check/home`. Normal package and owner data were not
accessed. All shell testing sourced `local-env.ps1` first.

Evidence references below are relative to `work/evidence/VE-P1e-3c2-OC/`.
Captures use Windows.Graphics.Capture with an explicit HWND. Input uses SendInput
only after verifying that the foreground HWND belongs to a recorded spawned
process tree. PID creation times are checked to guard against PID reuse.
No desktop capture was performed.

## Checklist

| # | Item | Verdict | Expected / actual and evidence |
| --- | --- | --- | --- |
| 1 | Hover landscape, then click | NOT_RUN | Playback verified: `warm-open-00.png` frame 10, `warm-open-01.png` frame 18. The 200 ms poster gate is unmeasured: WGC's first observation was 402.654 ms after input. This cannot prove either compliance or failure before 200 ms. See timing limitations below. |
| 2 | Close, click without hover waiting | PASS | `cold2-open.json`: visible video in `cold2-open-01.png` at 555.574 ms, below 600 ms; frame 5. No deliberate hover dwell was inserted. Pointer movement immediately preceded the click, as with a normal click. |
| 3 | Title and round close button | PASS | Filename at top and upper-right close control match the reference appearance in `landscape-paused.png`, `portrait-paused.png`; title is `landscape_enhanced.mp4` / `portrait_enhanced.mp4`. Round control has a transparent background, as in the mockup. |
| 4 | Controller layout | PASS | `preview-middle.png`: seek on separate row; icons below; large round accent play button. Visually compared with existing `VE-P1e-3c2/run3/mockup-landscape-hover-rgb.png`. This is an arrangement check, not a pixel equality claim across different window sizes. |
| 5 | Portrait layout | PASS | `portrait-paused.png`, `portrait-edge-middle.png`: seek above two control rows; controls remain inside the 722 x 1039 captured window without overlap. |
| 6 | Transparency and letterbox | PASS | `landscape-paused.png` shows moving-picture colors behind title and controls. `portrait-edge-middle.png` shows black side bars outside the portrait picture; `before-on.png` shows black space outside the fitted comparison picture. |
| 7 | Back/forward 10 seconds, clamps | PASS | `seek-start.png`: frame 0 / 0.000 s; `seek-forward10.png`: 300 / 10.000 s; `seek-back10.png`: 0 / 0.000 s. Repeated back clamps to frame 0; forward at end clamps to frame 599 / 19.967 s (`seek-clamp-*.png`). `steps-contact.png` groups burned-in readings. |
| 8 | Paused frame steps, 10 each direction | PASS | Baseline 150; forward captures 151 through 160; backward captures 159 through 150. Every change exactly one frame. `step-baseline.png`, `step-forward-1..10.png`, `step-back-1..10.png`, `steps-contact.png`, `steps.json.result.json`. |
| 9 | Hover previews, edges and middle | PASS | Landscape: `preview-left.png`, `preview-middle.png`, `preview-right.png`. Portrait: corrected bar coordinates in `portrait-edge-left.png`, `portrait-edge-middle.png`, `portrait-edge-right.png`. Images and time labels appear above the bar inside the window. Approximate physical image dimensions 200 x 113 / 113 x 200 at 125% scaling are consistent with 160 x 90 / 90 x 160 CSS px. No DOM measurement was used. Initial `portrait-preview-*` attempts targeted below the bar; those are not preview proof. |
| 10 | Volume, speed, Details | NOT_RUN | Mute state, 1.25x label and open Details verified in `volume-speed-details.png`. Speed-specific elapsed playback was not measured: initial Space input remained on a focused frame-step button and activated that button. Therefore the full speed gate is not passed. |
| 11 | Autohide and cursor | FAIL | Retest with focus off buttons: controls disappear while playback advances, but cursor remains visible in `autohide-retest-hidden.png` after the 2.3 s wait plus capture overhead. Paused controls remain in `autohide-retest-paused.png`. WGC cursor capture was enabled; independent physical cursor observation was not performed. Exact hide transition at 2.000 s was not measured. |
| 12 | Space, arrows, fullscreen, Esc | PASS | With blank surface focused, Space starts playback (retest captures advance to frame 123 / 4.100 s) and pauses it. Home + Right produced frame 150 / 5.000 s in `step-baseline.png`. Fullscreen capture is 1920 x 1080; Esc returns to 1282 x 759 (`fullscreen.png`, `fullscreen-exit.png`, `controls.json.result.json`). Initial Space on a focused button correctly activated that button; it was not a valid global-shortcut test. |
| 13 | Before/After enabled | PASS | `before-on.png`, `divider-timed-00.png`: Original at upper left, Enhanced at upper right. Left burned-in source and right encoded-output time agree within one frame in the sampled comparison captures. |
| 14 | Divider during playback | HUMAN | Twenty alternating slider positions 900 / 400 recorded while playing; `divider-timed-00..19.png` and `divider-timing.json`. Destination thumb pixel was checked before saving each frame. Input-to-observed-capture median 54.510 ms, worst 67.341 ms. Supporting capture latency only; no claim about perceived smoothness or display photons. Owner must judge feel. |
| 15 | 60 seconds comparison sync | PASS | `soak.json`: 21 captures at 3.015 through 63.015 s. Maximum inferred difference 1 frame. `sync-readings.json`, `sync-contact.png`, `sync-00..20.png`. Original frame indices are derived from its drawn timestamp at known 30 fps because the error banner obscures its small frame-number row; enhanced indices are read directly. Source indices 101,190,281,370,461,22,112,202,292,382,472,53,142,232,322,412,502,82,172,262,352; output differs only at samples 0 and 11, by -1. The 20 s clip was returned to start with Home every 17 s while playing, rather than inventing a longer fixture. An error banner persisted despite advancing video; see findings. |
| 16 | Zoom then Reset | PASS | `zoom-on.png`: Zoom 182%; `zoom-reset.png`: normal framing restored and zoom chip removed. `volume-speed-details.png` independently shows Details Zoom 100% before zoom. Reset used the documented 0 shortcut. |
| 17 | Close player, History accepts input | PASS | `history-after-close.png`; subsequent History click opens portrait (`portrait-paused.png`). `retest.json.result.json`. |
| 18 | Another video opens and closes | PASS | Portrait opened as PID 26228 / HWND 1115944 and closed with Esc. `portrait-edges.json.result.json` shows only main-app visible windows after 35 seconds. |
| 19 | No player process at 35 seconds | NOT_RUN | The 35 s check recorded visible HWNDs, not executable names. It is insufficient to prove process absence at that exact check. Later final creation-time-validated process check reports zero remaining recorded processes (`process-final.json`). Do not promote the HWND check to an executable-process PASS. |
| 20 | Settings licences (optional) | NOT_RUN | Settings button was clicked; `settings-bottom.png`, `licences.png`, `licences-loaded.png`. The implementation opens THIRD_PARTY_NOTICES.md in an external viewer. No viewer window appeared in the recorded spawned tree, so it was not captured or driven. In-app readability and the external viewer's state remain unverified. |
| 21 | No-DLL fallback (optional) | NOT_RUN | Candidate copied to `scratch/owner-check/candidate-nodll`; only libmpv-2.dll, libspirv-cross-c-shared.dll and libwinpthread-1.dll removed from the copy. Copy started as PID 10620. Both attempts to foreground its main HWND 197504 failed; input was withheld, as required. `fallback-first.png` shows Home, not fallback playback. Copy and home were cleaned afterward. |

Totals: **14 PASS, 1 FAIL, 1 HUMAN, 5 NOT_RUN**. PARTIAL follows the task's
explicit completion rule. PASS here applies only to each stated criterion, not
to acceptance of the entire player.

## Findings, errors and measurement limits

- During the first long comparison run, the overlay displayed **"The player did
  not respond."** (`sync-00..20.png`, `autohide-retest-hidden.png`). Video still
  advanced and sync stayed within the stated sampled limit. The later comparison
  run in a fresh player did not show this banner in `divider-timed-00.png`.
  Reproduction sequence is preserved in `steps.json`, `controls.json`,
  `compare.json`, then `soak` in the script. Root cause is unknown; no product
  repair was attempted in this check-only cycle.
- Initial ordinary sandbox launch produced only two internal 14 px windows
  (PID 10712). It was stopped. Escalated launch produced the normal GUI.
  Subsequent own-window checks needed escalation to access that process and home.
- `pip` was absent. Ordinary `uv pip install windows-capture` could not connect
  to PyPI (OS error 10013); escalated install succeeded: windows-capture 2.0.1,
  opencv-python 5.0.0.93. These are local venv dependencies, not manifest changes.
- The first queue request used invalid 720/original settings and returned HTTP
  400. Corrected to supported Fast / keep / off / HEVC before queueing both clips.
- Opening-time observations, all reported: first warm attempt 507.793 ms;
  later warm attempt 402.654 ms; cold attempt first frame black at 435.886 ms,
  visible at 725.251 ms; final cold attempt black at 446.990 ms and visible at
  555.574 ms. First warm capture names were reused by the later warm attempt;
  those initial raw images are not retained, and no 200 ms conclusion is drawn.
  The library was moved to initialize before the click for later measurements.
  A separate warm attempt withheld input when hover changed foreground.
- First divider timing measured merely the next captured frame, median about
  33.6 ms / worst 35.291 ms; that could precede the thumb update and is invalid
  as response evidence. The final pixel-confirmed run replaces that method:
  20 observations, median 54.510 ms / worst 67.341 ms. No gated result was tuned
  by changing the application.
- Automatic foreground checks withheld all fallback input; no input was sent
  to another app. An external licence viewer may have been invoked by the app;
  its independent/shared process state was not established or manipulated.

## Clips, processes and cleanup

The supplied clips were copied into the isolated home's inputs folder. They
entered History through the **normal authenticated engine API**, not by editing
job records. Both jobs used Fast, original size and original frame rate:
landscape job e64e7fa81d2c428e9fb11aa252a7f51f completed in 6.412040 s;
portrait job 3b52c07b0a544af5a8b30810a0da96c7 completed in 5.541892 s.
Original clips in `scratch/owner-check/clips` were kept unchanged.

App roots: 10712 (sandbox attempt), 23916 (production check), 10620 (no-DLL
copy). Player roots observed: 25908, 26228, 14540, 1804, 20904, 6172.
All recorded descendants and their creation times are in `session.json`;
all recorded PIDs and the final empty remaining list are in `process-final.json`.
Main windows received WM_CLOSE; remaining recorded children were terminated
after a five-second grace period. Final **remaining recorded processes: []**.
This does not claim control over a shared external licence viewer.

Before cleanup, resolved paths were verified inside `scratch/owner-check` and
independently measured (`cleanup-before.json`):

| Cleanup item | Logical bytes removed | Result |
| --- | ---: | --- |
| owner-check/home contents | 163106127 | Empty directory remains; zero entries |
| owner-check/candidate-nodll | 11749239 | Directory absent |

No deletion was refused. For the owner to delete: none of these test artifacts.
Unrelated scratch content and the supplied clips were retained as directed.

## Workspace and disk table

Decimal GB, logical file sizes, not allocated space. Drive free-space changes
are not used as a cleanup measurement. First retained inventory was taken after
dependency installation and the initial sandbox launch; it is not a pre-install
baseline. A later launch overwrote disk-start.json; the first numbers below are
transcribed from that command's actual output, not inferred from the later file.

| Folder / metric | Purpose | First inventory GB | Final inventory GB |
| --- | --- | ---: | ---: |
| C free | Drive free space | 351.370039296 | 351.348858880 |
| D free | Drive free space | 978.460880896 | 978.397904896 |
| repo | Checkout / existing venv | Not inventoried | Not inventoried |
| package/VideoEnhancer-candidate | Production candidate | 0.048306057 | 0.048306057 |
| package/VideoEnhancer | Owner package | Not accessed | Not accessed |
| evidence/VE-P1e-3c2-OC | This cycle captures and measurements | 0.000370954 | 0.077271682 |
| scratch | Isolated temporary test data | 0.056426035 | 0.042232471 |
| cache | Reusable tools and dependencies | 9.747365006 | 9.747365006 |

Evidence remains below 0.300 GB; cache is below 40 GB. Final evidence gains a
few KB for inventory metadata after this snapshot. Measured retained evidence
growth from first inventory is 0.076900728 GB. Exact total persistent growth is
**NOT_RUN** because venv/dependency-cache sizes were not measured before install.
The 1 GB gate therefore has no complete before/after proof; no build, model
download or package generation was performed. No historical evidence was pruned
because this task permits repository changes only to the script and report and
specifies cleanup of this check's home and copy.

## Changed files and validation

- `gui/scripts/owner-check-auto.py` (new): own-process tracking, guarded native
  input, HWND WGC capture, fixture queueing, measurement and cleanup support.
- `.ai/LAST_REPORT.md` (replaced): this report.

Initial script Ruff check: FAIL (import order and line lengths). Formatting
check: FAIL. Import ordering and formatting corrected. Final targeted
`ruff check` and `ruff format --check`: **PASS**.
The script was executed throughout the real production checks; its individual
command failures are disclosed above. No separate unit-test suite, product
build, lint suite, integration suite or CI: **NOT_RUN**, check-only scope.
No tests were disabled or weakened.

## Questions for the designer / intentionally not done

No questions were used to stop this cycle. Defaults: Fast / keep / off / HEVC;
system 125% pixel scaling; repeat the supplied short clip using Home for the
63-second observation. Require a preinitialized capture of the warm player's
actual surface to establish the 200 ms gate. Recheck speed using a blank-surface
focus, executable absence at 35 seconds, and fallback when foreground activation
is available. Investigate the response-error banner and captured cursor.

No product changes, test-feature diagnosis, owner media, external viewer
automation, commits, pushes or merges were performed. The operator owns Git.

## Owner summary (Japanese)

14項目PASS、1項目FAIL、1項目HUMAN、5項目NOT_RUNのためPARTIALです。
10秒シーク・端のクランプ・前後各10回の1フレーム送りを確認しました。
比較再生63秒・21枚の左右差は描画時刻から換算して最大1フレームでしたが、応答エラー表示も記録しました。
自動非表示後も撮影にカーソルが残ったためFAILです。比較スライダーの操作感は本人の目での確認が必要です。
200ms表示、速度の実時間、35秒時点のプロセス不在、ライセンス表示、DLLなし再生は判定未完了です。
記録した起動プロセスはすべて終了し、隔離ホーム内容とDLLなしコピーは削除済みです。
