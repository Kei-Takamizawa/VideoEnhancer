# Third-party models

This table records model sources used in production and optional candidates used by `ve bench`. The repository does not include model source code or weights. BasicVSR++ and Practical-RIFE are production models; CodeFormer, KEEP, and InsightFace are benchmark-only external projects, and their implementations are not copied here.

| Candidate | Code license | Weight terms | Source and weight location | SHA-256 status |
|---|---|---|---|---|
| Practical-RIFE 4.25 | MIT | Upstream states released model files follow the project MIT license | [Project](https://github.com/hzwer/Practical-RIFE), [4.25 weights](https://drive.google.com/file/d/1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg/view) | `6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2` checkpoint; `e63d481b7ae5d4a4e6ad7ac5b410ff78f3bf7be3b51b2e38ca8152747abde5b4` official archive; both pinned before inference. |
| Real-ESRGAN `realesr-general-x4v3` | BSD-3-Clause | Project release checkpoint | [Project](https://github.com/xinntao/Real-ESRGAN), [checkpoint](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth) | `8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292`; captured from the official release asset over HTTPS on 2026-10-04 and pinned before benchmark inference. |
| BasicVSR++ NTIRE 2021 | Apache-2.0 | Weights' terms are not stated; personal use only in this app | [Project](https://github.com/ckkelvinchan/BasicVSR_PlusPlus), [MMagic checkpoint](https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth) | `6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a`; checkpoint hash is also in the publisher filename. |
| CodeFormer | NTU S-Lab License 1.0; non-commercial use applies | Non-commercial | [Project and release](https://github.com/sczhou/CodeFormer), [checkpoint](https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth) | `1009e537e0c2a07d4cabce6355f53cb66767cd4b4297ec7a4a64ca4b8a5684b7`; pinned and verified before inference. |
| KEEP | NTU S-Lab License 1.0; non-commercial use applies | Non-commercial | [Project and releases](https://github.com/jnjaby/KEEP) | No upstream SHA-256 digest found; benchmark skips download and inference. |
| SCRFD 500m (`buffalo_sc`) | InsightFace library code is MIT | Public pretrained model weights are for non-commercial research only | [Model zoo and terms](https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md), [official archive](https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip) | ONNX checkpoint `5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a`; archive `57d31b56b6ffa911c8a73cfc1707c73cab76efe7f13b675a05223bf42de47c72`. |
| BiSeNet face parsing | Candidate repository license does not itself establish checkpoint or dataset rights | Checkpoint and CelebAMask-HQ use terms must be reviewed separately | [Candidate implementation](https://github.com/zllrunning/face-parsing.PyTorch) | No approved checkpoint URL and expected digest selected; benchmark skips download and inference. |

The benchmark requires a pinned expected SHA-256 before inference. When a publisher provides no digest, the initial optional acquisition must come directly from the documented official HTTPS release, and the resulting digest is recorded here and in the adapter before that checkpoint is used for inference. Later downloads are checked against the pinned value before loading. Calculating a hash after downloading an unverified file only identifies that file; it does not verify authenticity. RIFE and SCRFD use upstream inference libraries with external weights. SCRFD uses ONNX Runtime with CUDA FP32 requested at 640x640, while the CPU provider remains enabled as a fallback. Since node placement is not profiled, some operations may run on CPU; its reported NVML memory is device-wide and can include other processes. It is a detector-specific comparison, not a like-for-like replacement for the P0 PyTorch FP16 enhancement stages. The generated report records source and weight URLs, license, digests, loader, inference shape, timing, and available memory data.

Sources were checked against the linked project documentation and release pages on 2026-10-04. The stated licenses describe the linked projects or model providers; they do not grant rights to training datasets or downstream data.

## P1c-4 qualified catalog (2026-10-11, Asia/Tokyo)

The following optional entries passed source, license, adapter load, the synthetic
reference budget and GPU comparison checks. Default tensor/CPU regression checks
are recorded in `.ai/LAST_REPORT.md`. No weights or preview media are distributed
in Git. Downloads require consent. Source sizes and hashes were measured locally.

| Model | Exact license | Original publisher download | Checkpoint bytes | SHA-256 |
|---|---|---|---:|---|
| BasicVSR++ denoise | Code Apache-2.0; the weights' terms are not stated | [Publisher](https://www.dropbox.com/sh/gopo637rbutlxde/AACGnXDlvQMjwfCey3m2g34za?dl=1) | 39152529 | `28f6920c4681bd8468a831d479459872c7f020d95c40eb3ced4745670bf2d596` |
| BasicVSR++ NTIRE21 Track 3 | Code Apache-2.0; the weights' terms are not stated | [Publisher](https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth) | 176414092 | `6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a` |
| BasicVSR++ NTIRE21 Track 1 | Code Apache-2.0; the weights' terms are not stated | [Publisher](https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track1_20210223-7b2eba02.pth) | 176414076 | `7b2eba02a24989bfbf8b2ed4a06c8e6fd5dbeb193b1178ef7171cd1c455ddb0f` |
| BasicVSR++ NTIRE21 Track 2 | Code Apache-2.0; the weights' terms are not stated | [Publisher](https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track2_20210314-eeae05e6.pth) | 176414076 | `eeae05e655b9849d57a7bb732004ebeb75d376cb0bf76792f18ca0f9eb491774` |
| DRUNet deblocking color | MIT | [Publisher](https://github.com/cszn/KAIR/releases/download/v1.0/drunet_deblocking_color.pth) | 130590513 | `b26323e888230b1b5b58957add8dc9b9ea7fa2f69bdf6a0c3cca9db82167209f` |
| FBCNN color | Apache-2.0 | [Publisher](https://github.com/jiaxi-jiang/FBCNN/releases/download/v1.0/fbcnn_color.pth) | 287755111 | `8b0e4ef23d59cf7ac934a342cb31a17619e4fa4a0b3374a9d78c5174312387e8` |
| Practical-RIFE 4.25 lite | MIT | [Publisher](https://drive.google.com/uc?id=1zlKblGuKNatulJNFf5jdB-emp9AqGK05) | 24467405 | `81cdba223fe72a120130cc8552e5d2ecac824259d406f0c15323b3decf96b8b1` |
| Practical-RIFE 4.25 | MIT | [Publisher](https://drive.google.com/uc?id=1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg) | 24636301 | `6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2` |
| Practical-RIFE 4.26 | MIT | [Publisher](https://drive.google.com/uc?id=1gViYvvQrtETBgU1w8axZSsr7YUuw31uy) | 24636301 | `45c7f74156704769dc9f85cfcaf8552e1e926f9399dcfa3a553dee88fac6f53f` |
| SCUNet real PSNR | Apache-2.0 | [Publisher](https://github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_psnr.pth) | 71982841 | `fa78899ba2caec9d235a900e91d96c689da71c42029230c2028b00f09f809c2e` |
| 2xLiveActionV1 SPAN | Apache-2.0 | [Publisher](https://raw.githubusercontent.com/jcj83429/upscaling/main/2xLiveActionV1_SPAN/2xLiveActionV1_SPAN_490000.pth) | 8947821 | `8b166c75831ea7f694d9058ee9c8df8148af8cc1d2b57e69e6581b15cab572f7` |

BasicVSR++ code license: [original repository](https://github.com/ckkelvinchan/BasicVSR_PlusPlus/blob/master/LICENSE).
The checkpoint terms are not stated, and `commercial_use_allowed` stays false.
The denoise checkpoint comes from the folder linked in the original publisher's
README; its zip is pinned separately and only the expected checkpoint is extracted.
RIFE download links denote archives; each extracted checkpoint and archive is
verified before matching IFNet code is loaded.

License sources: [SCUNet](https://github.com/cszn/SCUNet/blob/main/LICENSE),
[FBCNN](https://github.com/jiaxi-jiang/FBCNN/blob/main/LICENSE),
[DRUNet / DPIR](https://github.com/cszn/DPIR/blob/master/LICENSE),
[Practical-RIFE terms](https://github.com/hzwer/Practical-RIFE), and
[SPAN publisher](https://github.com/jcj83429/upscaling).
SPAN's current publisher README and LICENSE say **Apache-2.0**, differing from the
older proposed catalog's CC BY-NC-SA 4.0. The manifest follows the actual publisher.

Omitted: 1xDeH264_realplksr, because its
[publisher release](https://github.com/Phhofm/models/releases/tag/1xDeH264_realplksr)
literally says `CC-BY-0.4`. This cannot establish the proposed CC BY 4.0 terms.
Real-ESRGAN's specified main/WDN blend is implemented and tested but omitted from
the catalog: the 0.2 and 0.6 runs sampled 6.890 and 6.865 GB for their own rendering
PID, exceeding 5.0 GB. Its BSD-3-Clause source remains listed above for benchmark use.
The WDN checkpoint's measured SHA-256 is
`1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca`
and size 4,885,111 bytes; the main checkpoint has the same size.
Neither omitted entry is offered for built-in download.

Reference FPS excludes model loading. Torch peaks reset after setup. Budget
values sum per-PID dedicated and shared GPU memory sampled at one-second intervals,
in decimal GB. They are observed peaks, not guarantees about time between samples.
See [adding models](ADDING_MODELS.md) for tiling and strength mappings, and the
manifests for raw measured bytes, modes and speeds. No new recognition or face
quality claim follows from these measurements.
