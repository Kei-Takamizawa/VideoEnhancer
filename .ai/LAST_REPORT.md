Task ID: VE-P1e-3c2-F1
Status: PARTIAL

## Scope and environment

Windows implementation/check cycle, 2026-10-26 local / 2026-10-27 UTC.
Branch `claude/project-thread-6lra47`, starting HEAD
`76c6e64836b9c023ae60d1204aa2beee7c0dc983`; initial working tree clean.
Read-only Git initially failed with `Program 'git.exe' failed to run: Access is denied`;
the escalated read-only status/HEAD check succeeded. No Git mutations were run.
CURRENT_TASK was already present in full and was preserved. The operator owns
commit/push. The accepted OC run remains referenced by `7288e34`; its passing
items have not been promoted to fresh measurements.

Evidence below is relative to `work/evidence/VE-P1e-3c2-F1/`. Only synthetic
clips and the isolated `scratch/owner-check/home` were used. Installation,
build and test shells sourced `repo/local-env.ps1`. Existing owner data and
the normal installed package were not accessed.

## Implementation and evidence limits

### Before/After request completion

Static inspection found a lost-completion path in host.rs: PLAYBACK_RESTART
was retained only when the native command acknowledgement had already arrived
and the last observed master position was within 0.1 seconds of the seek
request's fixed target. If either observation was unavailable at that one
restart event, later follower alignment could not complete the request. A
playing clock also keeps advancing while the follower catches up. The previous
host had a second, separate completion path inside the restart handler.

The host now retains acknowledgement and playback restart independently for
each pending frame command. It evaluates completion after draining master events
and polling/synchronizing the follower. It no longer samples the moving master
against an obsolete fixed seek position at the restart instant. Paused steps
retain their native acknowledgement, new-render, changed-position and follower
alignment requirements. The 10-second timeout has not been increased. Timeout
errors distinguish missing native acknowledgement, missing decoded-frame
readiness, incomplete frame stepping and original-frame alignment. Diagnostics
include request ID/type, completion state and both clocks; the error banner is
still shown.

`FrameCompletion` was extracted with the old acknowledgement-gated restart
behavior. The event-order regression failed (1 failed, 1 passed) in
`completion-before.log`. After retaining restart independently, it passes in
the final helper tests. This proves the isolated event-order failure, **not**
the exact event sequence of the production OC timeout. No production request
was observed timing out this cycle, because foreground input was withheld.
The production reproduction requirement and the causal attribution of the OC
banner remain unverified.

The official [mpv client API](https://github.com/mpv-player/mpv/blob/master/include/mpv/client.h)
documents PLAYBACK_RESTART as the notification for playback reinitialization
following discontinuities including seeks. Its API contract informed the
completion change; the timing of the old production failure was not inferred
from that documentation.

### Cursor ownership and controls hover

Previously the page changed CSS and the native host set the cursor only inside
WebView2 CursorChanged. There was no native update explicitly tied to the
controls' idle transition. Whether the OC symptom was caused by a missing
CursorChanged notification or a later WM_SETCURSOR reset is **not verified**.

The controls now send an allowlisted `cursor` request when their hidden state
changes. The host explicitly applies the native cursor and refreshes it during
the event loop, including when the pointer is still. CursorChanged uses the
same policy. Changes are restricted to the foreground helper, with the pointer
inside that exact HWND's client rectangle; another window, native frame or
outside pointer is excluded. Movement restores the cursor immediately and
mouse-leave is forwarded to WebView2. Pause restores the native cursor, and the
controls timer keeps the controls visible while the pointer is over controls,
the title, Details or the shortcuts panel.

The new controls regression failed on the old page (1 failed, 8 passed,
`cursor-before-restored.log`), then passed after the change. It checks the idle
native request, movement, controls hover, pause and pointer leave. This is unit
proof of state/transport behavior; it is **not** a GetCursorInfo measurement or
a cursor-capture proof. Production cursor behavior remains unverified.

## Production GUI attempts and limitations

The normal sandbox launch produced only two internal 18px windows. That
process was closed. An escalated launch produced the normal candidate window;
synthetic landscape/portrait jobs were queued through its authenticated engine
API. `baseline-main.png` and `baseline-history.png` capture only that own HWND
with WGC cursor capture enabled. The latter is not proof of reaching History.
Both jobs produced their synthetic outputs.

Both attempted input commands failed before SendInput:
`Cannot verify target as foreground; input withheld`.
Computer Use then refused binding the recorded candidate window with:
`Computer Use was not approved to use videoenhancer`.
No subsequent production GUI input, external viewer automation or alternate
foreground workaround was attempted. No input was sent to an unverified window.
The production candidate sequence, GetCursorInfo sampling and required drawn-time
measurements therefore could not be performed. Test-feature Playwright checks
were attempted separately; they are not production owner-check evidence.

## Re-check table

| Item | Verdict | Expected / actual and evidence |
| --- | --- | --- |
| 1 warm poster | PASS by reference to 0fd7293 | Accepted capture-free prewarmed 190ms measurement; no new poster timing capture. |
| 10 speed | NOT_RUN | No foreground-verified 1.25x drawn-time observation lasting at least 8 seconds. |
| 11 autohide/cursor | NOT_RUN | Unit regression passes; no production hidden-cursor capture or GetCursorInfo measurement. The 2.5-second OS cursor gate is unmeasured. |
| 13 Before/After | NOT_RUN | No fresh candidate comparison observation; OC acceptance remains historical. |
| 14 divider feel | HUMAN | Remains a human judgment. No new divider measurements were performed. |
| 15 comparison/Home soak | NOT_RUN | No 60-second production run or 20 paired drawn-frame samples. No claim of banner absence or within-two-frame sync. |
| 19 helper absent at 35s | NOT_RUN | No production player was opened. Final cleanup absence is not the 35-second process-lifetime gate. |
| 20 licences | NOT_RUN | File inspection confirms libmpv, FFmpeg, libplacebo and the written source offer for sources.tar.zst. Viewer-start half of the requirement was not run. No external viewer was driven/captured. |
| 21 no-DLL fallback | NOT_RUN | No production no-DLL copy was created this cycle. Automated fallback tests failed during synthetic fixture generation, before playback. |

## Checks

No test was disabled, loosened or edited to skip a gate. Existing pytest markers
and its own skips remain distinguished from passes.

| Check | Result | Evidence / details |
| --- | --- | --- |
| Offline npm restore | PASS | npm-ci.log, 194 packages installed; initial Vitest attempt failed because dependencies were absent (cursor-before.log). |
| GUI ESLint | PASS | lint-final.log. |
| GUI TypeScript/Vite build | PASS | ui-build.log and final production build. |
| Vitest | PASS | vitest-final.log, 81/81 across 17 files. |
| Helper Rust tests, default | PASS | helper-default-final2.log, 9 passed. |
| Helper Rust tests, all features | PASS | helper-all-final2.log, 8 passed. Feature-specific test counts differ by cfg. |
| Helper clippy default/all features, all targets, -D warnings | PASS | clippy-default-final2.log, clippy-all-final2.log. Initial runs failed on field_reassign_with_default in the new test; fixed by struct initialization, without suppressions. |
| Helper cargo fmt --check | PASS | format-final2.log. |
| Main Rust unit tests | PASS | main-rust-tests.log, 28 passed. |
| Python Ruff | PASS | ruff.log. |
| CPU pytest (-m 'not gpu and not soak') | FAIL | pytest.log: 512 passed, 11 failed, 177 skipped, 101 deselected, 349.38 seconds. |
| Player Playwright | FAIL | player-e2e.log: 6 failed, zero skipped. Five fail at synthetic fixture generation (selected LGPL FFmpeg lacks libx264); native-product fails while attaching to a WebView that closes. |
| Production main/helper build | PASS | Final build/hashes recorded below. |
| Pinned payload lock verification | PASS | payload-lock.log; original cached source/license payload verified against libmpv.lock.json before rebuilding. |
| Production smoke/owner GUI gates | NOT_RUN | Foreground verification failure and Computer Use refusal described above. |
| GPU suites / CI | NOT_RUN | Not represented as new passing evidence. |

CPU failures: the three `test_p1c4` cases, three `test_p1f2_review` cases,
`test_privacy_hygiene`, and four `test_video_links` cases. Logs include missing
ffmpeg/ffprobe from the shell environment, a resulting error-handler mock
TypeError (`unexpected keyword argument 'job_id'`), Git execution access denied,
and child-process termination waits timing out. No unrelated Python product or
test files were changed; no regression/baseline equivalence claim is made.
The Playwright executable was built with `e2e`, and the helper with `test-faults`;
these builds were separate from the production candidate and were not used as
production measurement evidence. The product test used copies of this cycle's
short synthetic clips, not the deleted historical 65-second fixtures; it failed
before the native-player assertions. No old latency gates were remeasured.

## Candidate

The existing candidate's DLL/source payload was retained. The main executable
was rebuilt with `npm run build:desktop` and the helper with
`cargo build --release --locked --manifest-path src-tauri/player/Cargo.toml`,
without test features. Only the two rebuilt executable files replace their
candidate counterparts. The current normal package was not touched. Candidate
readiness is not claimed until the missing production checks pass.

Original SHA-256 values, also in candidate-before-hashes.json:

| File | Before SHA-256 |
| --- | --- |
| VideoEnhancer-Player.exe | df30aeac27f644be7f427ffab626e38e8ef7443b904408324f1fd146234cde29 |
| VideoEnhancer.exe | 44eb0b8896c427a6fa688545d0211b0593dbe6472101397e65b4873acbb45241 |

Final hashes and the disk table are recorded below.

## Changed files

- gui/src-tauri/player/src/host.rs
- gui/src-tauri/player/src/composition.rs
- gui/src-tauri/player/src/lib.rs
- gui/src/player/Controls.tsx
- gui/tests/player-controls.test.tsx
- gui/scripts/owner-check-auto.py: route evidence/session files to this cycle.
- .ai/LAST_REPORT.md: this report.

## Processes and cleanup plan

Initial sandbox app PID: 25996. Escalated app PID: 11780. Recorded descendants:
26044, 16140, 25460, 14664, 20976, 20528, 7296, 9896, 25992, 5172, 15616,
2812, 7012. Recorded creation times are in session.json. The close command
reported `remaining: []`. A later process scan for this cycle's own isolated
profile/test command lines also found none (owned-processes-before-cleanup.json).
This is not item 19's timed check. Viewer processes were never started by this
cycle's UI operations.

Before deletion, resolved targets and their logical sizes were recorded in
cleanup-before.json. All are disposable artifacts of this cycle:

| Cleanup item | Bytes before deletion |
| --- | ---: |
| scratch/f1-e2e | 99045915 |
| scratch/f1-pytest | 0 |
| scratch/owner-check/home contents | 163904599 |
| scratch/p1e3c2-native/pair-original.mp4 (cycle copy) | 21083325 |
| scratch/p1e3c2-native/pair-enhanced.mp4 (cycle copy) | 18426159 |

The supplied clips in scratch/owner-check/clips are preserved. No no-DLL copy
was created. The first post-build inventory shows cache growth above the
persistent growth gate. After all checks, the listed newly generated debug
compiler artifacts will be removed; the exact per-file paths/sizes are appended
below from build-cleanup-plan.json. Release binaries and pinned payload assets
are retained. Deletion outcomes and final disk inventory follow below.

## Questions for the designer / intentionally not done

Default: implement the demonstrable event-state liveness repair and explicit
native cursor ownership, but do not claim either OC symptom is field-confirmed
fixed. The exact production timeout command/event ordering and the OS-level
cursor cause still need confirmation. Please review the completion change and
rerun the specified production checklist in an approved foreground/capture
session. The Python failures and the FFmpeg/e2e startup environment also prevent
the all-checks gate; files outside the allowed set were not changed to address
them. No question was used to stop implementation.

No new features, product layout changes, owner media, tool/payload downloads, commits,
pushes, merges, external viewer capture or capture-based poster remeasurement.

## Final candidate and cleanup inventory

Final production builds: PASS (production-build-final.log, helper-production-final.log).
Final ESLint and Vitest: PASS, 81 tests across 17 files.
Candidate DLLs and adjacent source archive match the pinned lock (candidate-lock-verification.json).

| File | Final SHA-256 |
| --- | --- |
| VideoEnhancer.exe | ef5dd2193bd2fd250823298e3fc9261dbd447fc6db940d2d8660b2bd5c99452e |
| VideoEnhancer-Player.exe | a76d8a9f641a74bcc06673a52dd1d0ae9c784c0e97c7608a3631d5a6ba66dc6c |

Exact debug-artifact deletion inventory, measured after all checks/builds.
These are compiler outputs of this cycle; no source, tool or payload is included.

| Generated artifact | Logical bytes |
| --- | ---: |
| cache/tauri-target/debug/deps/displaydoc-e92a23a4eaae5f68.pdb | 2641920 |
| cache/tauri-target/debug/deps/libbase64-ce9221534c8e2940.rlib | 514904 |
| cache/tauri-target/debug/deps/libbase64-ce9221534c8e2940.rmeta | 316633 |
| cache/tauri-target/debug/deps/libbase64-e4bd84f82c2d00ce.rmeta | 227964 |
| cache/tauri-target/debug/deps/libbitflags-c924b9d8f5646d59.rmeta | 177062 |
| cache/tauri-target/debug/deps/libdpi-5891117ef91dfd5e.rlib | 219100 |
| cache/tauri-target/debug/deps/libdpi-5891117ef91dfd5e.rmeta | 212136 |
| cache/tauri-target/debug/deps/libdpi-80b4cb7d03aba5f0.rmeta | 133183 |
| cache/tauri-target/debug/deps/libform_urlencoded-f62264ffb245d8e6.rmeta | 27557 |
| cache/tauri-target/debug/deps/libicu_collections-57b1ccf9f2539686.rlib | 1036710 |
| cache/tauri-target/debug/deps/libicu_collections-57b1ccf9f2539686.rmeta | 426785 |
| cache/tauri-target/debug/deps/libicu_collections-c659028211346ca3.rmeta | 302574 |
| cache/tauri-target/debug/deps/libicu_locale_core-4a73333febbd5b05.rmeta | 1381655 |
| cache/tauri-target/debug/deps/libicu_locale_core-9387890bfbfa04df.rlib | 3021936 |
| cache/tauri-target/debug/deps/libicu_locale_core-9387890bfbfa04df.rmeta | 1595439 |
| cache/tauri-target/debug/deps/libicu_normalizer-17e49cc0c46d58dc.rmeta | 441239 |
| cache/tauri-target/debug/deps/libicu_normalizer-51bf13c2f97eed32.rlib | 1569318 |
| cache/tauri-target/debug/deps/libicu_normalizer-51bf13c2f97eed32.rmeta | 591267 |
| cache/tauri-target/debug/deps/libicu_properties-38e2d7a6f5930ec6.rmeta | 2529117 |
| cache/tauri-target/debug/deps/libicu_properties-9e652eb186237a8a.rlib | 4570336 |
| cache/tauri-target/debug/deps/libicu_properties-9e652eb186237a8a.rmeta | 2735852 |
| cache/tauri-target/debug/deps/libicu_provider-87073197e85ce684.rmeta | 358184 |
| cache/tauri-target/debug/deps/libicu_provider-b0eb8d818759cc1a.rlib | 616290 |
| cache/tauri-target/debug/deps/libicu_provider-b0eb8d818759cc1a.rmeta | 429679 |
| cache/tauri-target/debug/deps/libidna-1f235341bf6ccafa.rlib | 1475884 |
| cache/tauri-target/debug/deps/libidna-1f235341bf6ccafa.rmeta | 243759 |
| cache/tauri-target/debug/deps/libidna-a75f4d46d36f3972.rmeta | 144084 |
| cache/tauri-target/debug/deps/libidna_adapter-46caf4958679e9e6.rlib | 77246 |
| cache/tauri-target/debug/deps/libidna_adapter-46caf4958679e9e6.rmeta | 32762 |
| cache/tauri-target/debug/deps/libidna_adapter-b790960b4ab5c135.rmeta | 27917 |
| cache/tauri-target/debug/deps/liblibloading-21999e3592b7817a.rlib | 283154 |
| cache/tauri-target/debug/deps/liblibloading-21999e3592b7817a.rmeta | 145144 |
| cache/tauri-target/debug/deps/liblibloading-3936d0badfbb8987.rmeta | 115826 |
| cache/tauri-target/debug/deps/libmemchr-38089049b4a132d8.rmeta | 992923 |
| cache/tauri-target/debug/deps/libmemchr-44c5c68c2f6ac0c5.rlib | 1776330 |
| cache/tauri-target/debug/deps/libmemchr-44c5c68c2f6ac0c5.rmeta | 1311848 |
| cache/tauri-target/debug/deps/libparking_lot-ae4416f7d9de723d.rmeta | 158387 |
| cache/tauri-target/debug/deps/libparking_lot_core-f9ed022dcf65a17c.rmeta | 114802 |
| cache/tauri-target/debug/deps/libpercent_encoding-08cacb3d06cba4a6.rmeta | 45711 |
| cache/tauri-target/debug/deps/libpng-045f1465d88b15fc.rmeta | 744028 |
| cache/tauri-target/debug/deps/libpotential_utf-1c20a29bc1163643.rmeta | 38524 |
| cache/tauri-target/debug/deps/libpotential_utf-d41965670bbbacf3.rlib | 91972 |
| cache/tauri-target/debug/deps/libpotential_utf-d41965670bbbacf3.rmeta | 45094 |
| cache/tauri-target/debug/deps/libproc_macro2-5b42f80bac7bc596.rlib | 1379190 |
| cache/tauri-target/debug/deps/libproc_macro2-5b42f80bac7bc596.rmeta | 351847 |
| cache/tauri-target/debug/deps/libquote-ed63e26db6dec0b6.rlib | 567456 |
| cache/tauri-target/debug/deps/libquote-ed63e26db6dec0b6.rmeta | 275893 |
| cache/tauri-target/debug/deps/libserde-378d07342e0e486d.rmeta | 526379 |
| cache/tauri-target/debug/deps/libserde-d173d3439c6d2dc5.rlib | 994036 |
| cache/tauri-target/debug/deps/libserde-d173d3439c6d2dc5.rmeta | 842612 |
| cache/tauri-target/debug/deps/libserde_core-e12ff28eead84497.rlib | 5060452 |
| cache/tauri-target/debug/deps/libserde_core-e12ff28eead84497.rmeta | 4849747 |
| cache/tauri-target/debug/deps/libserde_core-f76f9a2a3e98b891.rmeta | 2726536 |
| cache/tauri-target/debug/deps/libserde_json-367ad46f7538a188.rlib | 2626924 |
| cache/tauri-target/debug/deps/libserde_json-367ad46f7538a188.rmeta | 1455007 |
| cache/tauri-target/debug/deps/libserde_json-fe370f977207fe0d.rmeta | 966682 |
| cache/tauri-target/debug/deps/libsmallvec-2ea9b1b53a0d3a97.rmeta | 114305 |
| cache/tauri-target/debug/deps/libsyn-8a3c0f1b68c20174.rlib | 10205954 |
| cache/tauri-target/debug/deps/libsyn-8a3c0f1b68c20174.rmeta | 2810158 |
| cache/tauri-target/debug/deps/libsyn-e12850ffbe1f9970.rlib | 8867340 |
| cache/tauri-target/debug/deps/libsyn-e12850ffbe1f9970.rmeta | 3412031 |
| cache/tauri-target/debug/deps/libsynstructure-3eb5c573a8db6951.rlib | 1246894 |
| cache/tauri-target/debug/deps/libsynstructure-3eb5c573a8db6951.rmeta | 229720 |
| cache/tauri-target/debug/deps/libtao-0af3c24af868a158.rlib | 7598808 |
| cache/tauri-target/debug/deps/libtao-0af3c24af868a158.rmeta | 4353400 |
| cache/tauri-target/debug/deps/libtao-74325bc92a4352a6.rmeta | 3670956 |
| cache/tauri-target/debug/deps/libtao-c72c6bae0e12da59.rlib | 7588828 |
| cache/tauri-target/debug/deps/libtao-c72c6bae0e12da59.rmeta | 4340347 |
| cache/tauri-target/debug/deps/libtauri-fbb3505a67d5f889.rlib | 15965982 |
| cache/tauri-target/debug/deps/libtauri-fbb3505a67d5f889.rmeta | 7193113 |
| cache/tauri-target/debug/deps/libtauri_plugin_single_instance-b41b9134553097e6.rlib | 72728 |
| cache/tauri-target/debug/deps/libtauri_plugin_single_instance-b41b9134553097e6.rmeta | 67017 |
| cache/tauri-target/debug/deps/libtauri_runtime-9b5c30181555dd10.rlib | 665948 |
| cache/tauri-target/debug/deps/libtauri_runtime-9b5c30181555dd10.rmeta | 540961 |
| cache/tauri-target/debug/deps/libtauri_runtime_wry-b919681a9e417043.rlib | 2652312 |
| cache/tauri-target/debug/deps/libtauri_runtime_wry-b919681a9e417043.rmeta | 1965765 |
| cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rlib | 32268 |
| cache/tauri-target/debug/deps/libthiserror-155f01037c14fec3.rmeta | 31224 |
| cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rlib | 356970 |
| cache/tauri-target/debug/deps/libtinystr-0aeabf0762ca4e93.rmeta | 314228 |
| cache/tauri-target/debug/deps/libtinystr-9c819ba187e7ac7d.rmeta | 258492 |
| cache/tauri-target/debug/deps/liburl-3d042123386f1d5a.rmeta | 297701 |
| cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rlib | 1332532 |
| cache/tauri-target/debug/deps/liburl-cdd05d9ecdc0287c.rmeta | 369846 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-1304494e86b92893.rlib | 2138282 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-1304494e86b92893.rmeta | 407633 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-439d427e7144f55e.rlib | 2138990 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-439d427e7144f55e.rmeta | 407585 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-7eddf2ce95085949.rmeta | 0 |
| cache/tauri-target/debug/deps/libVideoEnhancer_Player-80726929358a9182.rmeta | 0 |
| cache/tauri-target/debug/deps/libVideoEnhancer_Player-97e6c93c723bf456.rmeta | 0 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-a82fadec2d016f59.rmeta | 0 |
| cache/tauri-target/debug/deps/libVideoEnhancer_Player-d09e8693a6af886f.rmeta | 0 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-dd6d29417458706f.rmeta | 145449 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-e52895876edb27a2.rlib | 2642106 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-e52895876edb27a2.rmeta | 484836 |
| cache/tauri-target/debug/deps/libvideoenhancer_player-f93eb5faca3dcf21.rmeta | 199206 |
| cache/tauri-target/debug/deps/libVideoEnhancer_Player-fdd9da71531fcc6a.rmeta | 0 |
| cache/tauri-target/debug/deps/libwebview2_com-8b682d394f73e5d6.rmeta | 1538598 |
| cache/tauri-target/debug/deps/libwebview2_com-8edea069f3a2800d.rlib | 10132652 |
| cache/tauri-target/debug/deps/libwebview2_com-8edea069f3a2800d.rmeta | 1976501 |
| cache/tauri-target/debug/deps/libwebview2_com-d614665bff8f16ee.rlib | 10108162 |
| cache/tauri-target/debug/deps/libwebview2_com-d614665bff8f16ee.rmeta | 1976501 |
| cache/tauri-target/debug/deps/libwebview2_com_sys-06b37d7db910eb30.rmeta | 4924254 |
| cache/tauri-target/debug/deps/libwebview2_com_sys-6daa55be7f2aaf0a.rlib | 20333950 |
| cache/tauri-target/debug/deps/libwebview2_com_sys-6daa55be7f2aaf0a.rmeta | 6432800 |
| cache/tauri-target/debug/deps/libwebview2_com_sys-b4e59872734e6b57.rlib | 20333950 |
| cache/tauri-target/debug/deps/libwebview2_com_sys-b4e59872734e6b57.rmeta | 6432800 |
| cache/tauri-target/debug/deps/libwindows-647d1e22f18ff6a7.rlib | 127207218 |
| cache/tauri-target/debug/deps/libwindows-647d1e22f18ff6a7.rmeta | 103104693 |
| cache/tauri-target/debug/deps/libwindows-9c66b4201138050c.rmeta | 81650820 |
| cache/tauri-target/debug/deps/libwindows-d0d23b0371803e71.rlib | 127206660 |
| cache/tauri-target/debug/deps/libwindows-d0d23b0371803e71.rmeta | 103104693 |
| cache/tauri-target/debug/deps/libwindows_collections-16e61cd397ede7b6.rlib | 535676 |
| cache/tauri-target/debug/deps/libwindows_collections-16e61cd397ede7b6.rmeta | 534573 |
| cache/tauri-target/debug/deps/libwindows_collections-f6bf775e70b9e531.rmeta | 328770 |
| cache/tauri-target/debug/deps/libwindows_core-a6fd93327c3eebf8.rmeta | 544067 |
| cache/tauri-target/debug/deps/libwindows_core-d8b0e8288046add1.rlib | 949900 |
| cache/tauri-target/debug/deps/libwindows_core-d8b0e8288046add1.rmeta | 638400 |
| cache/tauri-target/debug/deps/libwindows_future-51be2519e37fe6bb.rlib | 1105168 |
| cache/tauri-target/debug/deps/libwindows_future-51be2519e37fe6bb.rmeta | 757036 |
| cache/tauri-target/debug/deps/libwindows_future-d5b3e9f8b4ec6796.rmeta | 482503 |
| cache/tauri-target/debug/deps/libwindows_numerics-52d223e6577cd14c.rmeta | 97591 |
| cache/tauri-target/debug/deps/libwindows_numerics-dc5a2af46e21e0b7.rlib | 212080 |
| cache/tauri-target/debug/deps/libwindows_numerics-dc5a2af46e21e0b7.rmeta | 112934 |
| cache/tauri-target/debug/deps/libwry-3c8fb3c23e5ded05.rlib | 3215452 |
| cache/tauri-target/debug/deps/libwry-3c8fb3c23e5ded05.rmeta | 1901960 |
| cache/tauri-target/debug/deps/libyoke-5598d26e8733f6ea.rlib | 242478 |
| cache/tauri-target/debug/deps/libyoke-5598d26e8733f6ea.rmeta | 240740 |
| cache/tauri-target/debug/deps/libyoke-9fdfce34d1aff53f.rmeta | 192042 |
| cache/tauri-target/debug/deps/libzerofrom-5765f9eb8d92511e.rlib | 97034 |
| cache/tauri-target/debug/deps/libzerofrom-5765f9eb8d92511e.rmeta | 95994 |
| cache/tauri-target/debug/deps/libzerofrom-f3ecd5c88c7bb243.rmeta | 53717 |
| cache/tauri-target/debug/deps/libzerotrie-b76ea17d16878913.rmeta | 354065 |
| cache/tauri-target/debug/deps/libzerotrie-e3a3b0d50f0096d7.rlib | 541260 |
| cache/tauri-target/debug/deps/libzerotrie-e3a3b0d50f0096d7.rmeta | 454842 |
| cache/tauri-target/debug/deps/libzerovec-27d3ee8e39225a94.rlib | 1174686 |
| cache/tauri-target/debug/deps/libzerovec-27d3ee8e39225a94.rmeta | 1114657 |
| cache/tauri-target/debug/deps/libzerovec-e70d1292a9e90e43.rmeta | 839587 |
| cache/tauri-target/debug/deps/serde_derive-1fc70aa25b5c7f3c.pdb | 3149824 |
| cache/tauri-target/debug/deps/thiserror_impl-58c2e3420988f3e2.pdb | 2789376 |
| cache/tauri-target/debug/deps/VideoEnhancer-5577d2706a2bde48.pdb | 8630272 |
| cache/tauri-target/debug/deps/VideoEnhancer.pdb | 19189760 |
| cache/tauri-target/debug/deps/VideoEnhancer_Player-1bdf1d597c2fa8aa.pdb | 3354624 |
| cache/tauri-target/debug/deps/videoenhancer_player-a60134665ce7835e.pdb | 3715072 |
| cache/tauri-target/debug/deps/videoenhancer_player-b9920489348eb426.pdb | 3657728 |
| cache/tauri-target/debug/deps/VideoEnhancer_Player-d50591bbdbf0df41.pdb | 3321856 |
| cache/tauri-target/debug/deps/VideoEnhancer_Player.pdb | 4714496 |
| cache/tauri-target/debug/deps/webview2_com_macros-1f69e52e334b046e.pdb | 2699264 |
| cache/tauri-target/debug/deps/windows_implement-0821af43d7d56b0f.pdb | 2740224 |
| cache/tauri-target/debug/deps/windows_interface-7fa8aa5af22b897e.pdb | 2936832 |
| cache/tauri-target/debug/deps/yoke_derive-a6dc59e7f7ec7e4d.pdb | 2772992 |
| cache/tauri-target/debug/deps/zerofrom_derive-ed8849b50def564c.pdb | 2830336 |
| cache/tauri-target/debug/deps/zerovec_derive-a38b36fae623d8ef.pdb | 2715648 |

Total inventoried debug compiler artifacts: 864184679 bytes.

Additional independently inventoried cleanup target: `scratch/tmp`, 9586077 logical bytes.
This session-only temporary folder was empty in the retained pre-build baseline and contains this cycle's temporary outputs.

## Cleanup outcomes / for the owner to delete

Cleanup of the isolated home stopped at the first OS refusal:
`[WinError 5] Access is denied` on `work/scratch/owner-check/home/serve.json`.
No retry, elevation, permission change or alternate deletion method was used.
The rest of that home was left in place. The supplied source clips were preserved.

| Item | Logical bytes removed/reduction | Outcome |
| --- | ---: | --- |
| scratch/f1-e2e | 99045915 | Removed |
| scratch/f1-pytest | 0 | Empty directory removed |
| scratch/owner-check/home | 79336109 | Partial logical reduction; 84568490 bytes remain |
| scratch/p1e3c2-native/pair-original.mp4 | 21083325 | Cycle copy removed |
| scratch/p1e3c2-native/pair-enhanced.mp4 | 18426159 | Cycle copy removed |
| Inventoried debug compiler artifacts (154 files) | 864184679 | All listed artifacts removed |
| scratch/tmp | 9586077 | Removed |

**For the owner to delete:** `work/scratch/owner-check/home`, **84568490 bytes**,
including `serve.json` (126 bytes). All remaining per-file paths and sizes are in
owner-cleanup-remaining.json outside Git. This includes test-only settings/logs
and the isolated WebView profile; their contents are not published here.
The partially cleaned home is not counted as fully removed. Scratch is not empty;
the home cleanup requirement is NOT_MET.

Final process-final.json reports zero remaining recorded production processes
(creation-time validated), and zero processes whose executable/command line
matches this cycle's candidate/debug binaries or isolated test profiles.
The Playwright launch failed before its app PID was retained in evidence; a
complete historical PID list for that failed test launch is unavailable.
This is not item 19's timed 35-second check.

## Workspace and disk table

Decimal GB, logical file lengths, not allocated disk space. The first retained
inventory is the second candidate launch, before npm restore/build/test, not an
absolute pre-session drive snapshot. The earlier sandbox launch had already
created an isolated home. No drive-wide free-space change is treated as a
cleanup measurement. Overlapping rows are not summed.

| Folder / metric | Purpose | First retained GB | Final GB |
| --- | --- | ---: | ---: |
| C free | Drive free space | 351.351959552 | 351.342989312 |
| D free | Drive free space | 978.383470592 | 977.444253696 |
| repo | Checkout and existing venv | Not inventoried | Not inventoried |
| package/VideoEnhancer-candidate | Production candidate | 0.048306057 | 0.048309641 |
| evidence/VE-P1e-3c2-F1 | This cycle evidence | 0.000170581 | 0.001224049 |
| scratch | Temporary test data | 0.056455466 | 0.126803807 |
| cache | Reusable tools/build cache | 9.747365006 | 10.381381464 |
| repo/gui/node_modules | Restored dependencies | Not inventoried | 0.191885716 |

Measured nonoverlapping package/evidence/scratch/cache changes, plus the **entire**
final node_modules size as a conservative restoration bound and 1 MB for source/
report changes, give a retained-growth upper estimate of **0.898307567 GB**
from the retained pre-build baseline. This is below 1 GB. Exact full-workspace
growth was not measured because repo had no initial full inventory. This is not
an allocated-space measurement. Evidence is below 0.300 GB and cache below 40 GB.
The inventory JSON adds a small amount after its own snapshot. No historical
evidence was deleted or historical measurements rewritten. Normal package and
owner locations remained unaccessed.

Git diff --check: PASS before final report-only updates. Only the seven listed
files are modified. Git's line-ending warnings are disclosed; no capture,
dependency, package or build output is tracked. The cycle ends PARTIAL; the
production verification, failed checks and refused cleanup remain unresolved.

## Owner summary (Japanese)

比較再生の要求完了状態と、静止中のカーソル更新処理を修正しました。
追加した回帰テストは修正前に失敗し、修正後に成功しました。
製品候補のGUI操作が許可されず、実機での不具合解消は未確認です。
PlaywrightとCPUテストにも失敗があり、完了条件未達のためPARTIALです。
Gitへの記録とpushは行っていません。
