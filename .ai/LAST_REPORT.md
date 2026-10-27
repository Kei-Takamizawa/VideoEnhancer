Task ID: VE-P1e-3c2-F1 / run 2
Status: PARTIAL

## Scope

Windows desktop Computer Use re-check only, 2026-10-26 (America/Los_Angeles).
Starting branch: claude/project-thread-6lra47. HEAD: b792261f41053ab491c2e019b6cd5a107b7d2220.
Initial working tree clean. Product code unchanged. Run 1 is retained by reference
to 1a61dae; the prior OC remains 7288e34. CURRENT_TASK already contains the full
instructions, including section 7, and was preserved. No commit, push or Git mutation.
Evidence: work/evidence/VE-P1e-3c2-F1/run2 (outside Git).

All launches used the specified isolated home. It was empty at the initial inventory,
so the same supplied landscape/portrait synthetic clips were requeued through the
candidate's authenticated engine API. Both completed. No owner media was used.
Shells performing tests sourced local-env.ps1. Normal sandbox launch PID 10980 exited
without a targetable window; reviewed escalation launched candidate PID 24656.

## Re-check results

| Item | Verdict | Expected / actual and evidence |
| --- | --- | --- |
| 1 warm poster | PASS by reference to 0fd7293 | Accepted capture-free prewarmed 190 ms. No remeasurement. |
| 10 speed | PASS | Picture surface focused; 1.25x selected. speed-21 to speed-31: drawn 2.200 to 14.700 seconds over approximately 10 seconds. Measured wall interval 10.0003053 s, ratio 1.24996184 media seconds/wall second (allowed 1.20..1.30). speed.json and measurements.json. |
| 11 controls/cursor | NOT_RUN (full gate); hide/pause subchecks PASS | Cursor capture enabled in WGC. cursor-200.png shows playing video with hidden controls and no cursor. GetCursorInfo: flags=0, hCursor=null, foreground=target HWND 1509278. cursor-timed.json first hidden sample has idle_ms=2047. Paused samples retain flags=1/hCursor=65541; pointer is unchanged. Controls remain visible while pointer is over playback controls in the comparison runs. Computer Use screenshots draw a pointer indicator even when native GetCursorInfo and WGC show hidden; they were not used alone to judge hiding. |
| 13 Before/After | PASS | Original label left, Enhanced right; split rendered over the same synthetic frame. final-sync captures show comparison on; 24 paired readings below. |
| 14 divider feel | HUMAN | Two drags during playback moved the divider left and back to center. Action-through-refresh durations 596 and 462 ms (median 529, worst 596); these include the entire drag/tool/capture operation and are supporting observations only, not physical input-to-paint latency. Human feel remains unjudged. |
| 15 comparison/Home | PASS | Final 63.008 s observation; Home at 17.067, 34.061, 51.056 s. No error banner observed. final-sync-14..37 provide 24 paired drawn readings, maximum difference 1 frame. Player log contains navigation success and no timeout entry. |
| 19 no helper at 35 s | PASS | After closing native player through Computer Use, waited to 35.011 s; executable-name process query returned zero VideoEnhancer-Player.exe. player-after35.json records process creation-time inventory, not window absence alone. |
| 20 licences | FAIL | THIRD_PARTY_NOTICES.md names libmpv, FFmpeg and libplacebo and contains the three-year written source offer for sources.tar.zst. Settings button started OpenWith PID 22788, not a confirmed viewer. No external viewer or picker was driven or captured. viewer-start.json. |
| 21 no-DLL fallback | NOT_RUN | Temporary copy excludes exactly the three specified DLLs; launched PID 15708 with the same isolated home. Computer Use could read the Home tree, but guarded input failed before a clip could open. No HTML5 playback evidence. nodll-files.json and nodll-launch.json. |

Cursor limitation: no separate native sampling of movement-only restoration or a
pointer outside the player was performed. The positive timed hide, paused visibility,
and controls-hover observations above do not establish every possible cursor state.

## Measurements and attempts

First 63-second comparison: Home at 17.066 / 34.056 / 51.055 s, no banner.
Its WGC recording began during setup, so some frames are paused preparation frames;
it was not used alone as the full synchronization gate. An additional recording
(comparison-*.png) included divider drags; the third Home occurred at 53.201 s
with divider focus and changed the slider rather than seeking. It is excluded
from the protocol gate. The final sequence above restored center and play-button
focus and repeated all three seeks. All attempts are retained, not overwritten.

24 original/enhanced drawn frame readings from final-sync-14..37, respectively:
28/28, 89/88, 149/148, 209/209, 269/268, 329/328, 389/389, 449/448,
509/508, 56/56, 116/116, 176/176, 236/236, 296/296, 356/356, 416/416,
476/476, 27/26, 87/87, 147/146, 207/207, 267/266, 327/326, 387/387.
These compare the original's burned-in counter at top left to the enhanced-side
counter at the center split. sync-readings.png is a crop sheet for inspection;
original full HWND captures are retained. All 24 differ by at most one frame.

Computer Use initially refused a candidate click because another process was over
the point; activating and refreshing recovered the production candidate. A licence
button attempt was offscreen and was not sent; scrolling revealed it and the
subsequent click started OpenWith. Fallback attempts reported:
`coordinate input geometry is unavailable`, then
`point (1550, 50) is over claude.exe "Chrome Legacy Window", not target window VideoEnhancer.exe "VideoEnhancer"; activate the target or take a fresh screenshot before retrying`.
Binding/activation was refreshed and the retry returned the same guarded refusal.
No alternate injected input or security/settings change was used. A fallback
window capture unexpectedly included surrounding non-target desktop pixels; no
surrounding content was inspected, saved as project evidence, or acted on.

## Run 1 implementation and checks by reference

No product change or test rerun in run 2, as section 7 directs. Run 1's accepted
per-command ack/restart completion fix and explicit cursor idle-state transport,
including before-failing/after-passing regressions, remain referenced to 1a61dae.
The exact cause/event ordering of the original OC production timeout remains
unproven; current candidate seeks completed in the observed sequences.

Run 1 PASS by reference: ESLint, TypeScript/Vite/production builds, Vitest 81,
helper Rust default 9/all features 8, clippy default/all features, fmt,
main Rust tests 28, Ruff and pinned payload verification.
Run 1 FAIL retained: CPU pytest 512 passed/11 failed/177 skipped/101 deselected;
player Playwright six failures. Hosted CI decides those environmental failures
per section 7. Hosted CI was NOT_RUN/not inspected here, and no new PASS is claimed.

## Candidate hashes

No rebuild or executable replacement in this run. Current hashes match run 1 final:

| File | SHA-256 |
| --- | --- |
| VideoEnhancer.exe | ef5dd2193bd2fd250823298e3fc9261dbd447fc6db940d2d8660b2bd5c99452e |
| VideoEnhancer-Player.exe | a76d8a9f641a74bcc06673a52dd1d0ae9c784c0e97c7608a3631d5a6ba66dc6c |

## Cleanup plan and process outcome

Authenticated shutdown returned HTTP 200 for the isolated engines. Recorded PIDs
were checked against creation times before termination. process-final.json reports
zero remaining recorded processes. Candidate PID 24656, helper PID 19884,
fallback PID 15708; all descendant PID/creation pairs are retained in processes.json.
OpenWith PID 22788 had already exited when cleanup checked it. Initial failed
launch PID 10980 also exited. No owner process was terminated.

Inventoried cleanup targets, confined to the resolved work/scratch/owner-check root:

| Target | Logical bytes before cleanup |
| --- | ---: |
| home | 153275468 |
| candidate-nodll | 11752823 |

Cleanup results and final disk inventory follow below after execution.
Supplied source clips and unrelated scratch artifacts are preserved.

## Changed files and questions for the designer

Only repo/.ai/LAST_REPORT.md changed. Private evidence and helper measurement scripts
are outside the checkout. No product files, tests, packages or captures staged.
Default: keep section 7's existing task document and requeue the same supplied clips
because the isolated home began empty. Do not change tests, file associations or
product behavior. Designer decision needed: how to complete the licence-viewer gate
when Markdown opens the system OpenWith picker, and how to recheck fallback input
when Computer Use cannot verify the foreground. No product fix attempted this round.

Intentionally not done: rebuild, lint/test reruns, CI polling, downloads, poster
remeasurement, owner normal-app restart, Git recording/push, external-viewer UI,
and cleanup of unrelated scratch/source clips.


## Final cleanup and workspace disk table

Both approved cleanup targets were removed completely: home 153275468 bytes,
candidate-nodll 11752823 bytes. Remaining bytes: zero for both. No refusal and
nothing from these targets is left for the operator to delete. cleanup-results.json.
The supplied clips and unrelated scratch are retained, so all of scratch is not empty.

Decimal GB; logical file lengths, not allocated space. Start/end inventories cover
this run only; earlier cycle evidence was retained and included in the evidence row.

| Folder / metric | Purpose | Start GB | End GB |
| --- | --- | ---: | ---: |
| C free | Drive free space | 351.323652096 | 351.285444608 |
| D free | Drive free space | 977.528905728 | 977.461624832 |
| package/VideoEnhancer-candidate | Production candidate | 0.048309641 | 0.048309641 |
| evidence/VE-P1e-3c2-F1 | Complete cycle evidence including run 1 | 0.001289632 | 0.067000425 |
| scratch | Temporary data and supplied clips | 0.042235317 | 0.042235317 |
| cache | Existing reusable cache | 10.381381464 | 10.381381464 |
| scratch/owner-check/home | Isolated home, overlapping scratch | 0 | 0 |
| scratch/owner-check/candidate-nodll | Temporary copy, overlapping scratch | 0 | 0 |

Nonoverlapping inventoried retained growth: 0.065710793 GB, plus this report and
small final JSON writes. Below 1 GB with over 0.9 GB margin. Full repo size was not
inventoried; the only checkout change is this report. Evidence remains below 0.3 GB;
cache below 40 GB. Drive-wide free changes are not attributed to this cycle and are
not used as removed-byte measurements. No unrelated retention cleanup was performed.

## Owner summary (Japanese)

run 2 の製品候補で1.25倍速、比較表示、24組の同期差0～1フレームを確認しました。
63秒間の比較再生でHomeを17秒間隔に入力し、エラーバナーは観察されませんでした。
カーソル非表示は2.047秒で実測しましたが、移動復帰・ウィンドウ外の独立測定は未実施です。
ライセンスはOpenWith起動、DLLなし再生は前面入力拒否で未確認のためPARTIALです。
起動プロセスは残存0、隔離ホームと一時コピーは削除済み。コード変更・commit・pushはありません。

Final read-only Git verification: diff --check PASS; status shows only
.ai/LAST_REPORT.md modified. Git warns that LF will be replaced by CRLF next time
Git touches the report; no whitespace error was reported. No Git mutation executed.
