Task ID: VE-P1e-3c1 / CI round 7 Windows artifact acceptance
Status: COMPLETED

## Outcome and scope

Section 11.2 step 4 is complete for the green CI artifact from run 40202006764,
commit b65a4ccb7fb139500b8909031151f4b6c71441e2, on
`claude/project-thread-6lra47`. Initial working tree was clean. Windows PC proof
passes after two small spike-host compatibility fixes. The build artifact was
not modified. Product files and the build workflow/recipes are unchanged.

Step 5 reproducibility is **PENDING**: only run 40202006764 is available under
`cache/mpv-lgpl/ci-build/`. The designer has started the same-branch manual run;
its artifact is not available locally. No second hash or reproducibility claim
is fabricated. The owner explicitly permits this pending item without blocking
step 4. No workflow was dispatched, no Git mutation/commit/push was performed.
Final-commit CI remains the operator/designer's responsibility.

## Part A: DLL proof

- PASS: all 59 SHA256SUMS entries rehashed locally before loading.
- PASS: libmpv properties return `mpv v0.41.0-UNKNOWN`, `mpv-configuration`
  containing `-Dgpl=false`, and `ffmpeg-version=8.0`. There is no standalone
  `options/gpl` runtime property (returns null); proof is mpv-configuration.
- PASS: embedded FFmpeg configuration read from the libmpv binary itself,
  containing `--disable-gpl --disable-nonfree`, no enable-gpl/nonfree/version3.
  No companion ffmpeg.exe was used as configuration proof.
- PASS: local PE import parsing matches each checksum-verified CI objdump receipt.
  Non-system imports are only bundled SPIRV-Cross and winpthread. No Vulkan,
  libstdc++ or libgcc DLL imports. Full lists are in the manifest and evidence.
- PASS: 15 pinned source components with versions, URLs, hashes, licences,
  configure/build commands, recipe changes and toolchain receipts are recorded
  in the generated manifest. The checked-in manifest adds PC proof and retains
  the SHA-256 of the unmodified artifact manifest for provenance.
- PASS: `sources.tar.zst` checksum and archive listing (73 entries): fifteen
  exact source archives, build scripts/cross files, receipts, recipe-change and
  link evidence, and available Ubuntu source/distro patch archives are present.
  Archive size: 70,739,309 bytes. The second clean build is not yet compared.

| DLL | Bytes | SHA-256 |
| --- | ---: | --- |
| libmpv-2.dll | 33266600 | `d7126e232340dcd767f0a2197ec0ab60ac32146aa7a1291bcd172c57c49a5b4c` |
| libspirv-cross-c-shared.dll | 2965767 | `a0d43e62453adfed48e42d152c92ed382facfdf5d38da3615acbdea430d49ef9` |
| libwinpthread-1.dll | 324451 | `fc9f14551f6609dd51801daec2c194579d35345551ef84fe465cbdb3339c2a6f` |

Total: **36,556,818 bytes (36.557 decimal MB)**; 64.0% smaller than the
101,511,680-byte prebuilt. libmpv alone is 33.267 MB, below 40 MB.
SPIRV-Cross and winpthread must remain beside libmpv. Both libmpv and SPIRV-Cross
import winpthread; its `.a` build input is an import library, not proof it was
statically incorporated. GCC/libstdc++ are static under the runtime exception.

`LICENSES.md` now covers this exact build, the LGPL-3.0-or-later combined-library
election for Apache shader dependencies, FreeType FTL attribution, all notices,
Bison and GCC exceptions, exact source delivery, rebuild/relink and DLL
replacement/debugging rights. The product remains MIT and dynamically separate.
The prebuilt is permanently measurement-only. Historical MSYS/MSVC diagnostics
are explicitly distinguished from the successful Ubuntu recipe in the README.

## Five-fixture B1 smoke

Each smoke plays for approximately five seconds. Expected: host exit 0,
`current-vo=libmpv`, positive progressing time-pos and hwdec-current=d3d11va.
Actual on the final host: all five pass, with four telemetry samples per clip.

| Fixture | Result | Actual hwdec |
| --- | --- | --- |
| H.264 1080p30 | PASS | d3d11va |
| HEVC Main10 1440p60 | PASS | d3d11va |
| AV1 10-bit 1440p60 | PASS | d3d11va |
| VP9 1080p60 | PASS | d3d11va |
| HEVC rotation display-matrix fixture | PASS | d3d11va |

Every attempt is retained, including failures:

1. `ci-acceptance`: generation PASS; all five playback launches FAIL with
   LoadLibraryExW error 126 (bundled dependencies not found by the old host).
   The old smoke runner returned shell exit 0 despite child failures; this was
   not treated as PASS.
2. `ci-acceptance-smoke2`: process-local artifact PATH resolves dependencies;
   all five fail with libmpv error -5. Direct option probing isolated
   `load-scripts=no`: absent when scripting is compiled out. Other startup
   options returned 0. Again the old runner's shell exit 0 did not mean PASS.
3. `ci-acceptance-smoke3`: final rebuilt host, no artifact PATH workaround:
   all five child exits 0 and telemetry confirms d3d11va playback.
4. `ci-acceptance-smoke4`: confirmation after adding automated telemetry
   assertions and failure exit codes to smoke.py. All five PASS, shell exit 0.
   Fixtures were reused for attempts 2-4, not regenerated.

The loader now uses DLL_LOAD_DIR | DEFAULT_DIRS against the canonical absolute
DLL path. Only MPV_ERROR_OPTION_NOT_FOUND (-5) for `load-scripts=no` is tolerated;
all other option failures remain fatal. Builds without scripting cannot load
scripts; builds with scripting still receive load-scripts=no.

## B1 H.264 comparison: one successful run per DLL

Same synthetic 65-second H.264 file, same rebuilt host and machine, D3D11VA,
capture/profiling off, five loadfile samples and twenty exact seeks at Random(1337)
targets, timed to MPV_EVENT_PLAYBACK_RESTART after render/present handling.
These are software event timings, not physical display photon measurements or
cold process-start measurements. The `timing` phase uses the existing bench
sampling loop, stopping before stepping/capture/CPU sampling.

| DLL | First-frame median / 5 ms | Seek median / 20 ms | Seek maximum ms |
| --- | ---: | ---: | ---: |
| source | 34.1226 | 155.6909 | 235.1891 |
| prebuilt | 38.1102 | 159.8737 | 230.0736 |

Both meet first-frame <=150 ms, seek median <=200 ms and maximum <=400 ms.
Source medians are lower; its seek maximum is 5.12 ms higher. One run per DLL
cannot establish statistical equivalence or claim every individual seek is
faster. All 25 successful samples per DLL report D3D11VA and no sample errors.
Prebuilt SHA-256: b9f3ddd1ef2d43d6424addb835824ddb4e1e5f72c067e2816f0e09b19a6c4752.

Failed timing setup attempts are also retained:
`ci-h264-source` timed out waiting for the JavaScript control bridge before
collecting timing samples; `ci-h264-prebuilt` returned WebView ExecuteScript
0x8007139F before samples. Native playback itself was running. Both are FAIL,
not valid measurements, despite host exit 0. The new timing-only path avoids
unneeded JavaScript control setup and uses native load/seek commands. The
successful labels are `ci-h264-source2` and `ci-h264-prebuilt2`; no full Part B
matrix was rerun and failed raw logs were not overwritten.

## Validation and commands

Every test/build shell dot-sourced local-env.ps1. TEMP/TMP/VE_HOME, GUI roaming
and local app data, and WebView profiles were isolated under work/scratch.

| Check | Result |
| --- | --- |
| cargo build --offline --locked --manifest-path spikes/mpv/Cargo.toml | PASS |
| cargo fmt --check --manifest-path spikes/mpv/Cargo.toml | PASS |
| cargo clippy --offline --locked --manifest-path spikes/mpv/Cargo.toml -- -D warnings | PASS |
| ruff check spikes/mpv | PASS |
| ruff format --check spikes/mpv | PASS, 11 files |
| python -m unittest discover -s spikes/mpv/ci-build -p test_driver.py | PASS, 60 tests |
| Product build/tests; full Part B/C, alpha/capture recheck | NOT_RUN, outside this continuation's scope |
| Final-commit Windows/Ubuntu CI | NOT_RUN locally; operator pushes/checks |
| Second workflow artifact comparison | PENDING, artifact unavailable locally |
| git diff --check | PASS (read-only) |

Smoke reproduction (from work/repo, after session isolation):
`python spikes/mpv/smoke.py --approaches B1 --dll <artifact>/libmpv-2.dll --label unique`
After fixtures exist, add --skip-generate. For the bounded timing pair set
VE_MPV_DLL per DLL and VE_MPV_CAPTURE=0, then run
`python spikes/mpv/measure.py --mode B1 --phase timing --clip h264-1080p30.mp4 --label unique`.
No input was sent to other applications. These tests drove only the spike's
native command interface. No screenshots, manual visual/DPI checks or physical
screen timing were performed. Previously accepted Part B and Part C remain
accepted historical work, not new proof in this report.

Warnings: a CIM disk query was denied (0x80041003); Python disk_usage provided
actual free-space values. Read-only escalated Git status/diff succeeded; Git
reported LF-to-CRLF conversion warnings for Python/Rust working files. No new
downloads or dependency restores were needed. No PC MSYS2 tool was executed or
modified; its tree was enumerated only for aggregate disk accounting.

## Changed files

- spikes/mpv/src/mpv.rs: bundled DLL loading and scripting-disabled compatibility.
- spikes/mpv/smoke.py: DLL/label/reuse options, hardware-playback assertions and failure exit.
- spikes/mpv/measure.py: bounded native-only timing phase using bench samples.
- spikes/mpv/source-manifest.json: actual generated CI manifest plus PC supplement.
- spikes/mpv/LICENSES.md: replace obsolete OPEN/prebuilt audit with this build's inventory/obligations.
- spikes/mpv/README.md: successful route, proof and bounded validation commands.
- .ai/LAST_REPORT.md: this report.

## Disk and cleanup (decimal GB)

No restores: 0 bytes. Artifact was already downloaded before this continuation.
Source/build and artifact rows overlap cache; do not sum them.

| Item | GB |
| --- | ---: |
| repo | 3.528863222 |
| package | 0.005764162 |
| evidence/VE-P1e-3c1 | 0.047015708 |
| scratch | 0.273792461 |
| cache | 9.020108695 |
| cache/msys2 | 0.856811931 |
| cache/mpv-lgpl/source-build | 0.036575903 |
| cache/mpv-lgpl/ci-round1-sources | 0.064181348 |
| cache/mpv-lgpl/ci-round6-sources | 0.002760957 |
| cache/mpv-lgpl/ci-build/40202006764 | 0.114551559 |
| C free at first Python measurement | 354.791964672 |
| D free at first Python measurement | 979.943776256 |

The successful Linux source/build trees live on the GitHub runner, not this PC.
The retained artifact includes its 70.739 MB source archive; older local failed
build/download trees are retained unchanged. Before/after measurements do not
attribute drive-wide free-space variation to this task. An exact initial folder
baseline was not captured. A conservative current-file-length upper bound for
persistent files modified since 07:49 local (before this continuation) is
131,977,363 bytes (0.131977 GB), including overwrites; it is not exact net growth. The final inventory uses PowerShell -Force; earlier Python
logical traversal totals are retained as their own measurement, not net deltas.
Cache is under 40 GB; evidence is under 300 MB; D stays above 200 GB free.

Cleanup candidates measured independently before deletion (all created by this
continuation; initial scratch was empty):

- work/scratch/ci-appdata: 0 bytes.
- work/scratch/mpv-spike: 273,788,059 bytes (fixtures and isolated profiles).
- work/scratch/tmp: 5,644 bytes.

Cleanup PASS: all three verified paths were deleted with native PowerShell;
273,793,703 logical bytes removed from the measured items. Scratch is empty
(0 bytes). No deletion refusal and nothing left for the owner to delete.

Final C free: 354.78372352 GB; D free: 979.828097024 GB.
Final package: 0.005764162 GB; cycle evidence:
0.046722017 GB; cache: 9.069357625 GB.
Recorded spike host PIDs were all exited before cleanup. No final test recreated scratch.

## Questions for the designer and deferred work

- No design question blocks this proof. Default: complete step 4 under 11.3;
  leave second-run hash comparison PENDING as the owner requested.
- Review/attach the second manual-run artifact when available. No waiting loop
  or additional dispatch was performed.
- Product packaging/integration and ensuring the released app preserves the
  documented LGPL rights belong to P1e-3c2. No app/package change was made.
- Previous owner-managed cleanup candidates were intentionally not touched.

## Raw timing arrays (ms)

source first_frame: `[21.3357, 38.6769, 34.122600000000006, 32.495000000000005, 40.5377]`

source seeks: `[92.5006, 203.2388, 171.8624, 47.5225, 91.37950000000001, 187.7642, 186.4296, 127.5216, 115.275, 71.8765, 210.3716, 155.983, 154.69740000000002, 93.44919999999999, 225.48319999999998, 186.0374, 220.22990000000001, 155.3988, 235.18910000000002, 138.2529]`

prebuilt first_frame: `[22.6815, 46.178200000000004, 39.0712, 38.1102, 36.0676]`

prebuilt seeks: `[81.4255, 207.38590000000002, 171.8665, 45.5649, 79.75319999999999, 185.7217, 193.3751, 132.4169, 109.8292, 75.2992, 208.7168, 149.5206, 158.0689, 91.3659, 230.0736, 180.1201, 216.61849999999998, 161.6785, 223.2561, 139.3355]`

Raw successful/failed NDJSON, stderr, result JSON, audit, local import tables,
source archive listing, disk and cleanup inventories remain outside Git under
work/evidence/VE-P1e-3c1 (ci-acceptance and smoke2/3/4 subdirectories). No private
media, compiled binaries, profiles or screenshots are added to Git.

## Designer closure note (2026-10-25)

- Review: accepted. Part A step 4 passed: gpl=false, embedded FFmpeg `--disable-gpl --disable-nonfree`, strict imports, five-fixture d3d11va smoke, and B1 H.264 timing within targets. The DLLs total 36.6 MB against the 101.5 MB prebuilt. Parts B and C were already accepted.
- Step 5, reproducibility: the designer started workflow_dispatch run 40203859946 on b65a4cc and it succeeded. The operator downloaded both artifacts (60 files, 114,551,559 bytes each) and compared their `SHA256SUMS`: they match exactly, so the build reproduces byte for byte. Codex did not run this comparison; the operator did, outside Git.
- Carried to P1e-3c2: product packaging of the three DLLs (libmpv-2, SPIRV-Cross, winpthread) with LICENSES.md and the source offer, and the player integration.
