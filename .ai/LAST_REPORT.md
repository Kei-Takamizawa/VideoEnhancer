Task ID: VE-P1e-3c2-F2
Status: PARTIAL

## Scope

Windows / Codex desktop, 2026-10-26 (America/Los_Angeles). Starting branch:
claude/project-thread-6lra47; HEAD 29c64fd0fc45cb1ad298d915ff58c262111cb62b.
Initial working tree clean. Read AGENTS.md, CLAUDE.md, CURRENT_TASK.md and
WORKSPACE.md. CURRENT_TASK already contains the complete instructions and was
preserved. F1 remains referenced to 1a61dae and 0da3344. No Git mutation,
commit, push, fetch or branch change. Evidence: work/evidence/VE-P1e-3c2-F2/.
All test/build shells sourced local-env.ps1. Interactive launches used exactly
work/scratch/owner-check/home, including isolated roaming/local/WebView profiles.
No owner data, VE-check, owner AppData or owner app was used.

## Implementation and regression tests

Settings now displays the complete notices as plain, selectable, scrollable text
inside the main window. Close and Esc return to Settings and restore focus to the
licence button; the heading receives focus on opening. Region/text area have
accessible labels. Show file delegates to the existing reveal / Explorer select
path. It is disabled until a read succeeds. No dependency or Markdown renderer.
The read path no longer calls ShellExecute or opens another program.

The Rust command returns {text, path}. Resolution remains adjacent to the exe,
then gui/THIRD_PARTY_NOTICES.md. Reading is bounded to 2 MiB plus one byte, accepts
exactly 2 MiB, and reports specific oversize, invalid UTF-8 and read errors inside
the view. GUI inspection caught existing Settings CSS overriding HTML hidden;
a specific hidden selector fixes the Settings heading remaining below the view.

Before-fix evidence: both new Vitest cases failed against the original UI
(vitest-before.log). Applying the Rust test to original HEAD commands.rs fails
compilation with E0425, read_notices missing (rust-before-contract.log). This is
compile-red contract evidence, not a pre-fix runtime assertion failure. The first
Rust attempt was blocked by build-script access denial. Final source was restored
in a finally block before final tests. After: Rust covers missing/found/exact limit/
oversize/invalid UTF-8; UI covers text, reveal delegation, Close/Esc, focus return
and specific errors. Desktop mock and contract were updated. No test loosened.

## Candidate

Production npm run build:desktop passed, including TypeScript/Vite. The rebuilt
main exe replaced the candidate main exe only after spawned processes were closed.
Pinned DLLs, notices, licence materials, source archive and engine configuration
were retained. verifyPlayerPayload passed against libmpv.lock.json and the cached
CI payload. The existing F1 production helper was deliberately retained unchanged;
no player source changed. Helper debug builds were for tests only.

| File | Before SHA-256 | Final SHA-256 |
| --- | --- | --- |
| VideoEnhancer.exe | ef5dd2193bd2fd250823298e3fc9261dbd447fc6db940d2d8660b2bd5c99452e | 34f2fe6324bde600127aed353426dfe2619a7ee468d5c80529b4a4b33c0624a0 |
| VideoEnhancer-Player.exe | a76d8a9f641a74bcc06673a52dd1d0ae9c784c0e97c7608a3631d5a6ba66dc6c | a76d8a9f641a74bcc06673a52dd1d0ae9c784c0e97c7608a3631d5a6ba66dc6c |

Build logs and intermediate/final hashes are retained outside Git.

## Re-check results

| Item | Verdict | Expected / actual and evidence |
| --- | --- | --- |
| 20 licences | PASS, with monitoring limit below | Computer Use pressed Settings / Open-source licences on the final candidate. licences-final.png shows libmpv, FFmpeg, libplacebo, sources.tar.zst and the full three-year written offer together. Close returned to Settings (licences-closed.png); Enter reopened from restored focus; Esc returned to Settings. No OpenWith start observed. |
| 21 no-DLL fallback | PASS for H.264 playback; warning below | Copy excludes exactly the three payload DLLs. Computer Use opened landscape in History and pressed HTML5 play. nodll-a.png: frame 229, 7.633 s; nodll-b.png: frame 347, 11.567 s. Capture command starts are 3.9605934 s apart (nodll-times.json). Native browser controls are visible. |
| 11(a) hide within 2.5 s | NOT_RUN to required protocol | Hidden samples exist, but controlled last-movement time was not established. |
| 11(b) movement restore within 300 ms | NOT_RUN | No verified movement-only sequence on an independently bound helper. |
| 11(c) visible while paused | NOT_RUN | No independently verified paused-state sample sequence. |
| 11(d) visible over controls | NOT_RUN | No controlled native controls-hover sequence. |
| 11(e) visible outside player | NOT_RUN | Visible on main was observed, but not a controlled move out of a verified playing helper. |
| 12 keyboard and Esc | NOT_RUN as complete native re-check | Native playback opened, but parent keyboard routing gave unstable/unverified native state. Settings Esc and HTML5 dialog Esc worked; they do not substitute for this gate. |
| 16 zoom and Reset | NOT_RUN | No reliable native Ctrl-scroll/Reset sequence due target binding limitation. |
| 1, 10, 13, 15, 19 | PASS by reference only | Accepted F1 results in 0da3344; not remeasured. |
| 14 | HUMAN | Remains deferred to human judgement. |

Item 21 attempts: initial HEVC output showed unsupported playback. The same supplied
synthetic landscape was requeued via the isolated API with H.264. It plays in
HTML5, but the message "This video can't be played here. Open it in your default
player instead." remains above the playing video. This misleading message is a
real observation, not a claim that HEVC browser support passed. No player fix or
external default-player launch was attempted outside the allowed scope.

### Process-start evidence for 20

Win32_ProcessStartTrace subscription returned Access denied. An elevated psutil
observer compared PID and creation time, with nominal 10 ms sleeps between scans,
for about 120 seconds covering licence open/Close/reopen/Esc. The JSON retains
687 starts including concurrent tests, zero OpenWith.exe starts and no external
licence-viewer child of main PID 17308. Its only direct child during that interval
was the later native helper PID 28868, after licence checks. Polling cannot exclude
a process starting and exiting entirely between scans; kernel event tracing was
not established. Static inspection also confirms the read path starts no process.
See licence-process-starts-poll.json. No Show file click was included in this gate.

### Computer Use and item 11 samples

Clicks used freshly captured maximized candidate windows. Captures sometimes
included 14x14 auxiliary regions; full-size screenshot IDs were selected for input.
Native playback appeared as an owned transient, including advancing synthetic
frames, but sky.list_windows/list_apps and the alternate Computer Use inventory
never exposed an independent helper Window. Parent keyboard attempts could
maximize the owned player, but later observations returned to main History.
No guessed Window or alternate native input injector was used. Captures with
surrounding non-target pixels were discarded, not saved or used for input.
No non-target application was operated.

Recorded tool errors/refusals:
- Computer Use app approval timed out; refreshing selection recovered the main app.
- point (1400, 650) is outside window bounds { originX: 0, originY: 0, width: 14, height: 14 }
- windows getApp requires { windowId } from listApps() or listWindows().
The alternate actual inventory likewise omitted the helper. Initial ordinary-
sandbox candidate PID 14392 lost its window after its launch command; the elevated
isolated relaunch remained usable. No click was sent through a refused geometry.

cursor-native.json contains 1,800 GetCursorInfo samples over 196.631478 s.
The loop slept 100 ms after each read/write; actual median spacing was 109.6614 ms,
maximum 122.5895 ms. cursor-summary.json retains all state segments.

| Relative seconds | Flags | Foreground HWND | Observation |
| --- | ---: | ---: | --- |
| 0.000027 to 11.501137 | 0 | 395056 | Hidden, pointer (330,300); uncontrolled movement origin. |
| 11.603015 | 0 | 68356358 | Foreground transitioned to main. |
| 11.705499 to 53.405349 | 1 | 68356358 | Visible on main, pointer unchanged. |
| 60.231445 onward | 1 | 3278650 | Visible on no-DLL main; later History/browser-control moves. |

These are partial observations and do not prove 11(a-e).

## Section 6 checks

| Check | Final result | Actual |
| --- | --- | --- |
| ESLint | PASS | Final npm run lint, exit 0. |
| Python lint | PASS | Ruff, all checks passed. |
| TypeScript / Vite | PASS | Final production build, exit 0. Initial new-test typing option error fixed. |
| Vitest | PASS | Final 18 files, 83 tests. Initial mock promise error fixed. |
| CPU unit/integration tests | PASS | pytest -m 'not gpu and not soak' --basetemp ../scratch/f2-pytest-retry -q: 676 passed, 24 skipped, 101 deselected; 484.48 s; existing .pytest_cache access warning. |
| Main Rust tests | PASS | Final 29 passed, including licence regression. |
| Main clippy | PASS | --all-targets --locked -- -D warnings. |
| Helper Rust default / all features | PASS | 9 / 8 tests; none ignored. |
| Helper clippy default / all features | PASS | Both --all-targets --locked -- -D warnings. |
| Payload lock / Node unit test | PASS | Complete pinned payload verification and 1 test. |
| Player Playwright | PASS | Final-source build, all 7 tests, 1.5 min; all opt-in player gates enabled. |
| Read-only diff --check | PASS | No whitespace errors; LF-to-CRLF advisory warnings only. |

Earlier attempts retained: ordinary-sandbox Rust builds failed at player/build.rs
canonicalization with WinError 5; elevated reruns passed. Ordinary-sandbox
Playwright failed all seven at CDP attachment. Elevated retry passed five and
failed native-product (missing payload/fixtures) and native-startup (missing
review-poster.jpg). Verified cached DLLs and synthetic fixtures made all seven
pass, twice, including final source. No test was edited or disabled to pass.
The ordinary-sandbox CPU run showed failures and stalled around 30%. After the
complete elevated suite passed, its exact pytest process tree was terminated
(exit 15); pytest.log retains incomplete output. No completed failure summary
exists, so failing names or main-baseline equivalence are not invented.
There are no final check failures requiring a main environmental exception.
Initial cargo fmt hit path-canonicalization denial; only changed commands.rs was
formatted directly with rustfmt under the approved execution mode.

## Changed files

- gui/src-tauri/src/commands.rs
- gui/src/Pages.tsx
- gui/src/Licences.tsx (new)
- gui/src/types.ts
- gui/src/style.css
- gui/tests/setup.ts
- gui/tests/desktop-contract.test.tsx
- gui/tests/licences.test.tsx (new)
- gui/scripts/owner-check-auto.py (F2 evidence path only)
- .ai/LAST_REPORT.md

Player files and all other tracked files are unchanged.

## Process closure and decisions

Candidate root PIDs: 14392, 12228, 17308. No-DLL root: 26420. Recorded helpers
include 28868, 10792 and 23664. All recorded descendants were checked against
creation times and closed. close-first.json, close-native.json and
close-fallback.json report remaining=[]; session.json retains full PID/creation
pairs. Post-test dedicated-home process inventory is empty. Final name checks
found zero VideoEnhancer, VideoEnhancer-Player and OpenWith processes. No owner
process was terminated or restarted. normal-pytest-stopped.json records only
this run's terminated ordinary-sandbox test tree.

Questions for the designer / defaults chosen without stopping:
- Review the licence fix with polling evidence; kernel process-start tracing was unavailable.
- Finish 11/12/16 in a session exposing an independently targetable helper. No product workaround was introduced for the tool limitation.
- H.264 was chosen for browser playback. Decide separately whether to fix its misleading fallback warning. Player files were intentionally preserved.
- Retain the accepted production helper; preserve supplied clips; delete only this cycle's generated copies and outputs.

Intentionally not done: Git commit/push/merge, owner-app restart, new tool downloads,
owner-data access, external viewer/Explorer UI operation, calling incomplete native
gates PASS, and unrelated historical evidence retention cleanup. F1/OC evidence
needed by the accepted references was preserved.

## Cleanup and final workspace disk table

All cleanup paths were inventoried before deletion and resolved inside work.
Deletion ran inside the normal sandbox. No refusal and nothing for the owner to
delete. The home and no-DLL copy no longer exist (zero bytes). Original supplied
clips and pre-existing scratch data remain; scratch as a whole is not empty.
This cycle's Node/Playwright temp folders and generated fixture copies were removed.
Reusable Rust dependency/build caches remain below 40 GB. Obsolete final debug
executables and copied DLLs were removed after tests to meet the growth gate;
rebuild them before rerunning those e2e commands. Production candidate is retained.

| Cleanup item | Independently measured logical bytes removed |
| --- | ---: |
| scratch/owner-check/home | 173752823 |
| scratch/owner-check/candidate-nodll | 11756919 |
| scratch/f2-e2e | 160129036 |
| scratch/f2-e2e-final | 187923698 |
| scratch/f2-e2e-results | 318273 |
| scratch/f2-e2e-results-final | 45 |
| scratch/f2-e2e-results-retry | 58537 |
| scratch/f2-e2e-results-source-final | 45 |
| scratch/f2-e2e-retry | 170076396 |
| scratch/f2-e2e-source-final | 187460776 |
| scratch/f2-pytest | 278803 |
| scratch/f2-pytest-retry | 0 |
| scratch/p1e3c2-native/pair-original.mp4 | 21083325 |
| scratch/p1e3c2-native/pair-enhanced.mp4 | 21083325 |
| scratch/p1e3c2-native/review-original-720.mp4 | 21083325 |
| scratch/p1e3c2-native/review-output-1080.mp4 | 21083325 |
| scratch/p1e3c2-native/review-poster.jpg | 49436 |
| cache/tauri-target/debug/VideoEnhancer.exe | 18451456 |
| cache/tauri-target/debug/VideoEnhancer-Player.exe | 3683328 |
| cache/tauri-target/debug/libmpv-2.dll | 33266600 |
| cache/tauri-target/debug/libspirv-cross-c-shared.dll | 2965767 |
| cache/tauri-target/debug/libwinpthread-1.dll | 324451 |
| scratch/tmp: 43 generated Node/Playwright folders, exact per-path inventory in temp-cleanup-results.json | 9695076 |

Total independently inventoried removal: 1044524765 bytes.
Logical lengths are not allocated disk space; drive free changes are not used as
removed-byte measurements.

Decimal GB, nonoverlapping rows first:

| Folder / metric | Purpose | Start GB | End GB |
| --- | --- | ---: | ---: |
| C free | Drive free space | 351.277002752 | 351.222767616 |
| D free | Drive free space | 977.461612544 | 976.552239104 |
| package | Portable package and source delivery | 0.125284483 | 0.125288579 |
| evidence | All retained cycle evidence | 0.452220081 | 0.458309500 |
| scratch | Temporary data and supplied clips | 0.042235317 | 0.042238391 |
| cache | Reusable build/tool caches | 10.316078835 | 11.286228517 |
| repo | Checkout and existing dependencies; partial inventory | 3.841524939 | 3.843647084 |
| package/VideoEnhancer-candidate | Overlapping subset; excluded from growth sum | Not separately measured | 0.048313737 |
| evidence/VE-P1e-3c2-F2 | Overlapping subset; excluded from growth sum | Not separately measured | 0.006089998 |

Inventoried nonoverlapping retained growth: 0.978368416 GB before this
final report append and small final evidence writes; more than 20 MB margin below
1 GB. Cycle evidence is 0.006089998 GB, below 0.3 GB.
The repo inventory excludes inaccessible .pytest_cache on both measurements;
its full size is unknown. Tests warned that cache writes were refused, and no
cleanup or permission workaround was attempted for it. Therefore the full repo
size/growth is not independently attributable. Existing historical evidence is
retained for accepted F1/OC references; no unrelated cycle was deleted.

## Owner summary (Japanese)

ライセンスをアプリ内で表示し、全文・書面によるソース提供申し出・Close／Escを確認しました。
候補を再ビルドし、プレイヤーexeは変更していません。Vitest 83件、Python 676件、Rust・clippy・player e2e 7件はPASSです。
DLLなしのH.264再生は時刻7.633秒から11.567秒への進行を確認しましたが、誤った再生不可メッセージが残りました。
ネイティブプレイヤーを独立したComputer Use対象にできず、項目11・12・16は未完了のためPARTIALです。
起動プロセス残存0、隔離ホーム・DLLなしコピー・今回の一時ファイルは削除済みです。commit・pushは行っていません。
