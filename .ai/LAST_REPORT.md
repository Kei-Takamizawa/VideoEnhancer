# VE-P1c-4 report

- Task ID / Cycle: VE-P1c-4
- Date: 2026-10-11 (Asia/Tokyo)
- Status: COMPLETED within the owner-feedback scope.
- Two optional entries omitted under the task's qualification rules.
- Branch: p1c-redesign. No merge or push to main.
- Starting HEAD: 85a04c90ec766ba11e483b62896cc30ed3001598, matching fetched origin.
  This was the packaging report after the task's referenced db8585c.
- Full final instructions saved unchanged in CURRENT_TASK.md and committed as 778618d.
- Owner queue untouched. Evidence, synthetic media, model weights and packages stay outside Git.
- Native Computer Use is unavailable on this host; GUI verification used actual Electron
  and Playwright. No manual owner visual check is claimed.

## Changes and expected / actual behavior

F1: the old FFmpeg AV1 probe used 128×128 and failed the encoder's minimum-size
check. The new probe uses the production CUDA encoder at 1920×1080 and flushes
two frames through the muxer. Health logs and exposes av1_unavailable_reason;
Add and Settings show the same disabled AV1 option and one-line reason when
unavailable. Encoder start/write/flush failures name the codec and never fallback.
During GPU verification, 180 AV1 frames initially muxed as 7.2 seconds rather than
3 seconds because stream-copy kept IVF packet timestamps. The AV1-only setts
filter now assigns the pipeline's exact rational CFR. HEVC/H.264 retiming is unchanged.

M2/F3: optional qualified manifests, measured catalog speeds and short English
summaries; versioned pinned RIFE IFNet variants; tiled single-frame restoration;
DRUNet quality-factor strength map; learned size after cleanup before resize/RIFE.
Existing C1, RIFE 4.25 and Standard resize remain the defaults. DRUNet strengths
share one card/file; selectors stay within the existing card layout. Public license
metadata is refreshed without changing an installed job's frozen resume identity.
Archive downloads verify the archive and extracted checkpoint and never copy model
folder Python. All optional downloads require explicit consent. Restricted torch
weights loading is retained. No custom CUDA build was used.

C2/F2: keys include source path/size/mtime, CFR range, settings, model ID/SHA and
companion stage identities. Cached Original/models publish immediately; a fully
cached request needs no GPU lease. New compares cancel earlier waiting/running
compares, leaving trials/jobs alone. POST compare/range returns the busiest five
seconds from saved per-frame motion analysis; old/missing/stale analysis falls
back to the middle. Fast cleanup remains explicitly rejected.

E: trial states persist UTC time, elapsed processing time and percent at two-second
intervals, plus a terminal sample. Waiting for an active segment is separate from
running-trial progress. Only the requested two short G2 trials were repeated,
with a short synthetic job for the during-job condition.

## F1 GPU evidence

Expected: portrait 1080×1920 and landscape 1920×1080, AV1, 180 frames, DONE.

| Job | State | ffprobe codec_name | Dimensions | Read frames |
|---|---|---|---|---:|
| portrait | done | av1 | 1080×1920 | 180 |
| landscape | done | av1 | 1920×1080 | 180 |

Actual: both match. The realistic probe returned (True, None).
Evidence: av1-results.json; .tmp/p1c4/av1-gpu3.log.
Timestamp reference: https://ffmpeg.org/ffmpeg-bitstream-filters.html#setts.

## M2 qualification

One fixed synthetic reference: 150 frames / 5 s, 720×1280 at 30 fps, output
1080×1920 at 60 fps. Restoration and size: Standard; motion: Fast. FPS excludes
model loading. Torch peaks reset after setup. Budget = rendering PID dedicated
plus shared GPU memory sampled at one-second deadlines, decimal GB. Median
interval 1.000 s, maximum observed gap 1.016 s. These samples do not prove the
absolute peak between samples; device-wide NVML is not used for acceptance.
Normal jobs retain their 30-second sampling. Hardware RTX 4060 Ti 8GB.

Steps 1–5 are source, license, load, reference measurement, and real GPU Compare.
Step 6 is the shared strict C1/RIFE tensor-equality and existing CPU/D2 fixtures.
Temporary measurement IDs map to the public IDs below without changing weights,
adapter parameters or tensor processing. No model was registered before its
budget and comparison passed.

| Entry (public ID) | Result / failing step | Input fps | Torch allocated / reserved bytes | Sampled process peak bytes (GB) | Tile / halo | Exact license |
|---|---|---:|---|---|---|---|
| basicvsrpp-ntire21-decompress | QUALIFIED, steps 1–6 | 2.472708 | 2886402048 / 3978297344 | 4342366208 (4.342366) | none / none | Code Apache-2.0; the weights' terms are not stated |
| basicvsrpp-track1 | QUALIFIED, steps 1–6 | 2.486314 | 2887180288 / 4286578688 | 4650647552 (4.650648) | none / none | Code Apache-2.0; the weights' terms are not stated |
| basicvsrpp-track2 | QUALIFIED, steps 1–6 | 2.483696 | 2886516736 / 4003463168 | 4367532032 (4.367532) | none / none | Code Apache-2.0; the weights' terms are not stated |
| basicvsrpp-denoise | QUALIFIED, steps 1–6 | 5.219462 | 2073742848 / 3860856832 | 3925020672 (3.925021) | none / none | Code Apache-2.0; the weights' terms are not stated |
| scunet-real-psnr | QUALIFIED, steps 1–6 | 0.587473 | 1081937408 / 1373634560 | 1741873152 (1.741873) | 256 / 32 | Apache-2.0 |
| fbcnn-color | QUALIFIED, steps 1–6 | 1.517374 | 1194374144 / 1562378240 | 1930616832 (1.930617) | 256 / 32 | Apache-2.0 |
| rife-4.25 | QUALIFIED, steps 1–6 | 16.430267 | 1154199040 / 1595932672 | 1964171264 (1.964171) | none / none | MIT |
| rife-4.26 | QUALIFIED, steps 1–6 | 16.419470 | 1154681344 / 1595932672 | 1964171264 (1.964171) | none / none | MIT |
| rife-4.25-lite | QUALIFIED, steps 1–6 | 16.662634 | 1146762240 / 1457520640 | 1823662080 (1.823662) | none / none | MIT |
| drunet-deblock | QUALIFIED, steps 1–6 | 1.135053 | 1176314880 / 1539309568 | 1909645312 (1.909645) | 256 / 32 | MIT |
| span-liveaction-2x | QUALIFIED, steps 1–6 | 1.394593 | 2891815936 / 4227858432 | 4565143552 (4.565144) | 256 / 32 | Apache-2.0 |
| Standard resize | DEFAULT, no learned stage/download | n/a | n/a | n/a | n/a | none |
| 1xDeH264_realplksr | OMITTED, step 2: ambiguous publisher license | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Literal CC-BY-0.4; CC BY 4.0 unconfirmed |
| Real-ESRGAN 0.2 Faithful | OMITTED, step 4: above 5.0 GB; step 5 NOT RUN | 1.611152 | 4938035712 / 6526337024 | 6890418176 (6.890418) | 256 / 32 | BSD-3-Clause |
| Real-ESRGAN 0.6 Cleaner | OMITTED, step 4: above 5.0 GB; step 5 NOT RUN | 1.612309 | 4937344512 / 6530531328 | 6865252352 (6.865252) | 256 / 32 | BSD-3-Clause |

DRUNet variants (one checkpoint/card), publisher map (100-QF)/100:

| Choice | QF / channel | fps | Torch allocated / reserved bytes | Sampled PID peak bytes |
|---|---|---:|---|---:|
| light | 50 / 0.5 | 1.133105 | 1175909376 / 1598029824 | 1968365568 |
| medium | 30 / 0.7 | 1.135053 | 1176314880 / 1539309568 | 1909645312 |
| strong | 10 / 0.9 | 1.136166 | 1176139776 / 1562378240 | 1932713984 |

DRUNet uses FP32, tile 256 + halo 32. The blend wrapper follows the publisher's
strength*main + (1-strength)*wdn formula. Both specified blend points failed the
budget, so no Real-ESRGAN built-in card/download is offered.

### Source, bytes and SHA-256

| Entry | Original publisher URL | Checkpoint bytes | Computed SHA-256 |
|---|---|---:|---|
| basicvsrpp-ntire21-decompress | https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth | 176414092 | 6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a |
| basicvsrpp-track1 | https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track1_20210223-7b2eba02.pth | 176414076 | 7b2eba02a24989bfbf8b2ed4a06c8e6fd5dbeb193b1178ef7171cd1c455ddb0f |
| basicvsrpp-track2 | https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track2_20210314-eeae05e6.pth | 176414076 | eeae05e655b9849d57a7bb732004ebeb75d376cb0bf76792f18ca0f9eb491774 |
| basicvsrpp-denoise | https://www.dropbox.com/sh/gopo637rbutlxde/AACGnXDlvQMjwfCey3m2g34za?dl=1 | 39152529 | 28f6920c4681bd8468a831d479459872c7f020d95c40eb3ced4745670bf2d596 |
| scunet-real-psnr | https://github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_psnr.pth | 71982841 | fa78899ba2caec9d235a900e91d96c689da71c42029230c2028b00f09f809c2e |
| fbcnn-color | https://github.com/jiaxi-jiang/FBCNN/releases/download/v1.0/fbcnn_color.pth | 287755111 | 8b0e4ef23d59cf7ac934a342cb31a17619e4fa4a0b3374a9d78c5174312387e8 |
| rife-4.25 | https://drive.google.com/uc?id=1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg | 24636301 | 6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2 |
| rife-4.26 | https://drive.google.com/uc?id=1gViYvvQrtETBgU1w8axZSsr7YUuw31uy | 24636301 | 45c7f74156704769dc9f85cfcaf8552e1e926f9399dcfa3a553dee88fac6f53f |
| rife-4.25-lite | https://drive.google.com/uc?id=1zlKblGuKNatulJNFf5jdB-emp9AqGK05 | 24467405 | 81cdba223fe72a120130cc8552e5d2ecac824259d406f0c15323b3decf96b8b1 |
| drunet-deblock | https://github.com/cszn/KAIR/releases/download/v1.0/drunet_deblocking_color.pth | 130590513 | b26323e888230b1b5b58957add8dc9b9ea7fa2f69bdf6a0c3cca9db82167209f |
| span-liveaction-2x | https://raw.githubusercontent.com/jcj83429/upscaling/main/2xLiveActionV1_SPAN/2xLiveActionV1_SPAN_490000.pth | 8947821 | 8b166c75831ea7f694d9058ee9c8df8148af8cc1d2b57e69e6581b15cab572f7 |
| deh264 | https://github.com/Phhofm/models/releases/download/1xDeH264_realplksr/1xDeH264_realplksr.safetensors | 29486580 | 91f054af6308e37b81c261ecf775a58be5fa1d37a816709db5d0fea6fceb24b8 |
| esrgan | https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth | 4885111 | 8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292 |
| esrgan-wdn | https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth | 4885111 | 1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca |

Denoise publisher zip: 463593013 bytes,
9ebecdddd2367058b96b043032efe27bdbe1471651c66e02629d724fcb146f41;
member basicvsr_plusplus_denoise-28f6920c.pth. A second independent download
had identical bytes/hash (denoise-repeat.json). RIFE 4.26 archive SHA:
c2452dd2b244947d4be580156bbead60d6b72af5736860f7d6b3f99648c9c4cc;
4.25 lite archive SHA:
e84366c23e0eb1a637a55aad2e4f3442ec2bf4c388043b4aabbf590be289e6e8.
Exact license sources and archive handling are in docs/THIRD_PARTY_MODELS.md.

### Per-entry lifecycle and GPU Compare

Install was called through the consent-guarded service endpoint and the actual
isolated operation subprocess. Verify again re-hashed the downloaded file.
Make default changed the appropriate Settings key; a new selection captured it.
Remove deleted the built-in checkpoint after clearing that default. No owner
queue was involved. RIFE downloads reused the already verified publisher archive
cache; other checkpoint downloads used the original URLs.

| Entry | Consent required | Install | Verify again | Make default | Remove |
|---|---|---|---|---|---|
| basicvsrpp-denoise | True | PASS | PASS | PASS | PASS |
| basicvsrpp-ntire21-decompress | True | PASS | PASS | PASS | PASS |
| basicvsrpp-track1 | True | PASS | PASS | PASS | PASS |
| basicvsrpp-track2 | True | PASS | PASS | PASS | PASS |
| drunet-deblock | True | PASS | PASS | PASS | PASS |
| fbcnn-color | True | PASS | PASS | PASS | PASS |
| rife-4.25 | True | PASS | PASS | PASS | PASS |
| rife-4.25-lite | True | PASS | PASS | PASS | PASS |
| rife-4.26 | True | PASS | PASS | PASS | PASS |
| scunet-real-psnr | True | PASS | PASS | PASS | PASS |
| span-liveaction-2x | True | PASS | PASS | PASS | PASS |

Every qualified entry and its category default produced actual GPU previews.
Cache reuse is explicit below: default previews may be copied from an earlier
successful identical-key render; every candidate was freshly rendered at least
once. FPS in this table includes model setup/encoder finalization and differs
from the load-excluded reference FPS shown on the catalog cards.

| Compare | Model fps (reused flag) | First Original tile seconds | Total seconds |
|---|---|---:|---:|
| three-model | basicvsrpp-ntire21-decompress: 2.266792 (False); track1: 2.333062 (False); track2: 2.345715 (False) | 13.910 | 245.449 |
| basicvsrpp-ntire21-decompress | basicvsrpp-ntire21-decompress: 2.266792 (True) | 0.182 | 0.320 |
| track1 | basicvsrpp-ntire21-decompress: 2.266792 (True); track1: 2.333062 (True) | 0.158 | 0.434 |
| track2 | basicvsrpp-ntire21-decompress: 2.266792 (True); track2: 2.345715 (True) | 0.181 | 0.444 |
| denoise | basicvsrpp-ntire21-decompress: 2.266792 (True); denoise: 4.682312 (False) | 0.148 | 39.677 |
| scunet | basicvsrpp-ntire21-decompress: 2.266792 (True); scunet: 0.557945 (False) | 0.159 | 274.865 |
| fbcnn | basicvsrpp-ntire21-decompress: 2.266792 (True); fbcnn: 1.458753 (False) | 0.163 | 109.196 |
| rife-4.25 | rife-4.25: 12.117497 (False) | 23.543 | 41.186 |
| rife426 | rife-4.25: 12.117497 (True); rife426: 11.866582 (False) | 0.156 | 18.249 |
| rife425lite | rife-4.25: 12.117497 (True); rife425lite: 11.964381 (False) | 0.144 | 17.920 |
| drunet-medium | basicvsrpp-ntire21-decompress: 2.266792 (True); drunet-medium: 1.102742 (False) | 0.157 | 144.001 |
| span | standard-resize: 2.333602 (False); span: 1.354586 (False) | 24.008 | 230.014 |
| drunet-light | basicvsrpp-ntire21-decompress: 2.266792 (True); drunet-light: 1.105367 (False) | 0.146 | 143.708 |
| drunet-strong | basicvsrpp-ntire21-decompress: 2.266792 (True); drunet-strong: 1.104368 (False) | 0.145 | 143.758 |

Three fresh different cleanup models: C1 2.266792 fps, Track 1 2.333062,
Track 2 2.345715. Original ready 13.910 s; model tiles ready 96.730,
174.832, 245.446 s. Total 245.449 s. H.264 previews, real Standard pipeline.
All four outputs were generated; no simulated GPU measurements.

C2 tests exercise immediate all-hit completion without GPU/process creation,
Original/model reuse without encoding, range/settings/source/model-SHA key
invalidation, and cancellation of the old compare only. Busiest/missing-data
selection is unit tested. Four-stream Electron verification: 100 random seeks,
300 played frames, 0 mismatches (e2e/four-stream-sync.json).

## G2 trial histories

Expected: both Standard three-second trials complete, with no running 0% stretch
over 60 seconds. Submission waiting is separate. Actual:

### during-job

State: done; first sampled positive percent at 14.453 s. Operation ce734c0e265f432b86e9db05581af4da.

| UTC time | Processing elapsed seconds | Percent |
|---|---:|---:|
| 2026-10-11T03:37:00.702625+00:00 | 0.000 | 0.000 |
| 2026-10-11T03:37:02.806291+00:00 | 2.109 | 0.000 |
| 2026-10-11T03:37:04.857916+00:00 | 4.156 | 0.000 |
| 2026-10-11T03:37:06.935317+00:00 | 6.234 | 0.000 |
| 2026-10-11T03:37:08.963710+00:00 | 8.265 | 0.000 |
| 2026-10-11T03:37:11.013299+00:00 | 10.312 | 0.000 |
| 2026-10-11T03:37:13.089524+00:00 | 12.390 | 0.000 |
| 2026-10-11T03:37:15.158556+00:00 | 14.453 | 14.444 |
| 2026-10-11T03:37:17.227664+00:00 | 16.531 | 14.444 |
| 2026-10-11T03:37:19.303347+00:00 | 18.609 | 26.667 |
| 2026-10-11T03:37:21.369337+00:00 | 20.672 | 26.667 |
| 2026-10-11T03:37:23.442993+00:00 | 22.734 | 38.889 |
| 2026-10-11T03:37:25.524343+00:00 | 24.828 | 38.889 |
| 2026-10-11T03:37:27.565722+00:00 | 26.859 | 51.111 |
| 2026-10-11T03:37:29.606546+00:00 | 28.906 | 51.111 |
| 2026-10-11T03:37:31.665269+00:00 | 30.968 | 63.333 |
| 2026-10-11T03:37:33.722104+00:00 | 33.015 | 63.333 |
| 2026-10-11T03:37:35.781102+00:00 | 35.078 | 75.556 |
| 2026-10-11T03:37:37.867796+00:00 | 37.172 | 75.556 |
| 2026-10-11T03:37:39.906804+00:00 | 39.203 | 75.556 |
| 2026-10-11T03:37:41.991112+00:00 | 41.297 | 87.778 |
| 2026-10-11T03:37:44.028468+00:00 | 43.328 | 87.778 |
| 2026-10-11T03:37:46.167513+00:00 | 45.468 | 100.000 |
| 2026-10-11T03:37:48.227436+00:00 | 47.531 | 100.000 |
| 2026-10-11T03:37:50.309662+00:00 | 49.609 | 100.000 |
| 2026-10-11T03:37:52.386765+00:00 | 51.687 | 100.000 |
| 2026-10-11T03:37:54.465341+00:00 | 53.765 | 100.000 |
| 2026-10-11T03:37:56.516695+00:00 | 55.812 | 100.000 |
| 2026-10-11T03:37:58.569280+00:00 | 57.875 | 100.000 |
| 2026-10-11T03:38:00.611366+00:00 | 59.906 | 100.000 |
| 2026-10-11T03:38:14.276582+00:00 | 73.578 | 100.000 |
### outside-hours

State: done; first sampled positive percent at 12.437 s. Operation b4d5af0c11814561b4d1a524f23409c4.

| UTC time | Processing elapsed seconds | Percent |
|---|---:|---:|
| 2026-10-11T03:38:59.666807+00:00 | 0.015 | 0.000 |
| 2026-10-11T03:39:01.758449+00:00 | 2.109 | 0.000 |
| 2026-10-11T03:39:03.824351+00:00 | 4.172 | 0.000 |
| 2026-10-11T03:39:05.879499+00:00 | 6.219 | 0.000 |
| 2026-10-11T03:39:07.935571+00:00 | 8.281 | 0.000 |
| 2026-10-11T03:39:10.028831+00:00 | 10.375 | 0.000 |
| 2026-10-11T03:39:12.094684+00:00 | 12.437 | 14.444 |
| 2026-10-11T03:39:14.167415+00:00 | 14.515 | 14.444 |
| 2026-10-11T03:39:16.256955+00:00 | 16.609 | 26.667 |
| 2026-10-11T03:39:18.320439+00:00 | 18.672 | 26.667 |
| 2026-10-11T03:39:20.383421+00:00 | 20.734 | 26.667 |
| 2026-10-11T03:39:22.444212+00:00 | 22.797 | 38.889 |
| 2026-10-11T03:39:24.540063+00:00 | 24.890 | 38.889 |
| 2026-10-11T03:39:26.620330+00:00 | 26.969 | 51.111 |
| 2026-10-11T03:39:28.670470+00:00 | 29.015 | 51.111 |
| 2026-10-11T03:39:30.723365+00:00 | 31.062 | 63.333 |
| 2026-10-11T03:39:32.800152+00:00 | 33.140 | 63.333 |
| 2026-10-11T03:39:34.867131+00:00 | 35.219 | 75.556 |
| 2026-10-11T03:39:36.903640+00:00 | 37.250 | 75.556 |
| 2026-10-11T03:39:38.963076+00:00 | 39.312 | 87.778 |
| 2026-10-11T03:39:41.039836+00:00 | 41.390 | 87.778 |
| 2026-10-11T03:39:43.106786+00:00 | 43.453 | 100.000 |
| 2026-10-11T03:39:45.196745+00:00 | 45.547 | 100.000 |
| 2026-10-11T03:39:47.246115+00:00 | 47.594 | 100.000 |
| 2026-10-11T03:39:49.326822+00:00 | 49.672 | 100.000 |
| 2026-10-11T03:39:51.381102+00:00 | 51.734 | 100.000 |
| 2026-10-11T03:39:53.420123+00:00 | 53.765 | 100.000 |
| 2026-10-11T03:39:55.444951+00:00 | 55.797 | 100.000 |
| 2026-10-11T03:39:57.536665+00:00 | 57.875 | 100.000 |
| 2026-10-11T03:39:59.604083+00:00 | 59.953 | 100.000 |
| 2026-10-11T03:40:12.638192+00:00 | 72.984 | 100.000 |

The during-job trial was submitted while a synthetic job segment was running;
the outside-hours schedule was enabled with an empty weekly list. The fixture
job completed. Histories persist in the isolated operation state files, copied
into g2-results.json. A first positive sample gives an upper bound on the initial
running 0% interval; neither trial returned to 0% afterward.

## Builds and tests

| Check | Result | Evidence |
|---|---|---|
| Ruff | PASS | .tmp/p1c4/ruff-final.log |
| Ruff format --check | PASS, 101 files | .tmp/p1c4/format-final.log |
| Pyright | PASS, 0 errors / 0 warnings | .tmp/p1c4/pyright-final.log |
| Final CPU suite | PASS: 257 passed, 3 skipped, 30 deselected; 307.35 s | .tmp/p1c4/cpu-release.log |
| Strict CUDA C1/RIFE tensor equality | PASS: 2 passed, 31 deselected; 9.80 s | .tmp/p1c4/legacy-final.log |
| D2 CPU + CUDA suite | PASS: 26 passed; 189.25 s | .tmp/p1c4/d2-final.log |
| GUI lint | PASS | .tmp/p1c4/gui-lint.log |
| GUI typecheck | PASS | .tmp/p1c4/gui-typecheck.log |
| GUI unit tests | PASS: 29 tests / 5 files | .tmp/p1c4/gui-unit.log |
| GUI production build | PASS | .tmp/p1c4/gui-build.log |
| Electron e2e | PASS: 1 actual CPU-service test; 4 opt-in tests skipped | .tmp/p1c4/gui-e2e.log |
| Generated package startup | PASS: 1 test, 3.3 s | .tmp/p1c4/packaged-test.log |
| Windows / Ubuntu CI | PASS on implementation f50d353, both jobs SUCCESS | https://github.com/Kei-Takamizawa/VideoEnhancer/actions/runs/38109438547 |

Built unsigned Windows x64 package with `VE_GUI_PACKAGE_OUT=.tmp/p1c4/package`;
artifact `.tmp/p1c4/package/VideoEnhancer-win32-x64/VideoEnhancer.exe` is ignored
and points to this repository's external Python engine. It was launched in a
fresh isolated home by the packaged test, with service connection, renderer
isolation and shutdown verified. This does not replace or stop an owner package.

GUI operations: Add/Settings AV1 reason unit checks; DRUNet three choices on one
card; actual CPU service, synthetic Add → completion → History, four-stream
WebCodecs seek/play and close survival; generated package startup, renderer
isolation and service shutdown. Existing e2e also captured incidental synthetic
screenshots outside Git; these do not qualify A9's new-card screenshots.

## Errors, warnings and unresolved items

- Initial AV1 GPU renders failed duration validation; corrected IVF timestamps,
  rerun portrait/landscape both DONE with ffprobe evidence.
- One new CPU cache test initially tried unavailable production weights and a
  96×64 restoration geometry; the fixture now bypasses those unrelated production
  checks while testing actual cache files and transport. Targeted rerun passed.
- GUI build initially reported a missing gpu field on strength-specific speed
  metadata; the tooltip now uses the shared reference GPU. Rebuild passed.
- Driver-only quoting/encoding/path invocation errors were corrected. They are
  not reported as application passes. No test failure was ignored.
- Playwright emitted NO_COLOR/FORCE_COLOR warning. Git emitted CRLF normalization
  warnings. Neither changed runtime results. Large artifacts are not staged.
- Native Computer Use unavailable; no manual desktop check claimed.
- Windows and Ubuntu CI passed for implementation f50d353 on PR run 38109438547.
  This final report update changes no executable code. Its final-head checks are
  verified again before handoff and tracked on draft PR #4; no merge requested.

## Questions for the designer

1. DeH264 release says CC-BY-0.4 rather than CC BY 4.0. Can the publisher clarify?
   Default meanwhile: omitted at license step 2; no download card/inference.
2. SPAN publisher now states Apache-2.0 rather than the proposed CC BY-NC-SA 4.0.
   Default meanwhile: exact current publisher license, documented commercial flag.
3. Both Real-ESRGAN blends exceed the 5.0 GB sampled budget with tile 256/halo 32.
   Default meanwhile: omitted at step 4; Standard resize stays default. No new
   memory policy, architecture or quality policy introduced.

## Intentionally deferred / not run

DEFERRED to P1d per F2: draggable range box, GUI 800 ms re-render,
install-then-select, their GUI component/e2e tests, and A9 qualified-model dark/light
screenshots. The GUI Switch to Standard control belongs to that deferred redesign.
F4 schedule/dock/colors/History changes were not started. Owner visual checklist
is owner-run. DeH264 steps 3–5 NOT RUN after license failure. Real-ESRGAN step 5
NOT RUN after budget failure. No long G1/G3 soak or prior three-job G2 rerun.
No architecture/UX redesign, added non-M2 entry, model training, telemetry or update.

## Related files and reproduction

Changed: .ai/CURRENT_TASK.md and LAST_REPORT.md; media/{encode,analyze}.py;
models/{registry,spandrel,rife,rife_variants}.py and qualified manifests;
bench/rife.py; pipeline/{presets,runner}.py; service/{engine,settings,compare}.py;
jobs/store.py; scripts/reference_measure.py; tests/{test_compare,test_p1c4}.py;
gui/src/{App,Pages,Queue,types}; gui/tests/add-models.test.tsx;
docs/{ADDING_MODELS,THIRD_PARTY_MODELS,GUI,API}.md.

Evidence root (synthetic/private artifacts, not Git):
C:/Users/pro/.codex/visualizations/2026/10/09/01a12000-750a-7813-9ea1-6bc265708fb5/p1c4.
Raw *-measurement.json files include every PID/time/memory sample and runner
statistics. *-compare.json files retain real timing/reuse metadata. Lifecycle,
G2, AV1, sample intervals and Electron sync have separate JSON evidence.
Local logs and orchestration scripts are in .tmp/p1c4 (ignored).

```powershell
$env:VE_HOME = 'C:\Evaluation\p1c4-home' # isolated from the owner queue
ffmpeg -v error -f lavfi -i testsrc2=size=720x1280:rate=30 -t 5 -c:v libx264 -preset ultrafast -threads 2 reference-5s.mp4
# Install via the Models consent dialog, then prepare a Standard (motion: Fast)
# CUDA job at 1080 / 2x / HEVC with the selected model. Use its prepared manifest:
python scripts/reference_measure.py prepared-job.json measured.mp4
# POST compare: file=reference-5s.mp4, start=0, seconds=5, models=[default,candidate].
# POST compare with [C1, basicvsrpp-track1, basicvsrpp-track2] for the three-model run.
# For G2 use Standard trials with seconds=3, once during a synthetic job and once
# after PUT schedule {enabled:true, weekly:[], timezone:'Asia/Tokyo'}.
ruff check .
ruff format --check .
pyright
pytest -m 'not gpu and not soak' --basetemp=.tmp/p1c4/cpu-repro
pytest tests/test_model_registry.py -m gpu --basetemp=.tmp/p1c4/legacy-repro
pytest tests/test_source_index.py --basetemp=.tmp/p1c4/d2-repro
cd gui
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

On this host npm was invoked through the retained .tmp/npm-bootstrap/package/bin/npm-cli.js
because the npm executable is unavailable; commands above are their normal equivalents.
GPU reproduction additionally requires the documented model/GPU dependencies,
matching pinned external source archives, and explicit original-source downloads.
No private owner video is required.

## Git record

- Full instruction commit: 778618d.
- Implementation and local acceptance report: f50d353e21f0f6e25a137aa46d6c5e7ce4d047a3.
- Push to origin/p1c-redesign succeeded; ls-remote matched that exact SHA.
- PR #4 remains draft: https://github.com/Kei-Takamizawa/VideoEnhancer/pull/4.
- Implementation PR CI run 38109438547: Windows SUCCESS, Ubuntu SUCCESS.
- Final report-only commit records these verified results. Its source tree is
  unchanged; final-head remote checks and origin equality are checked before
  stopping. No merge, history rewrite or push to main occurred.
