# Architecture

VideoEnhancer is organized as a local conversion engine. A job is probed and normalized into a frame timeline, split into resumable segments, processed by ordered stages, then assembled with its original audio. The production presets share one bounded decode → compute → encode streaming runner. `fast` uses Practical-RIFE motion interpolation; `standard` uses BasicVSR++ restoration, resize, then Practical-RIFE.

The media layer owns probing, decode, color conversion, encode and mux. Standard restoration is split into overlapping clips. Clips stop at hard scene cuts; overlap frames are emitted once by the clip in which the frame is farthest from an edge (ties go to the later clip). A bounded frame buffer supplies context across segment boundaries and releases frames after their final clip use. Interpolated frames belong to the left source frame. Job storage owns the manifest and atomic segment state. The scheduler decides when segments may run, while the estimator uses a per-machine profile plus observed job timings.

CUDA decode, processing and encode are hardware-dependent. CPU support exists for deterministic development and CI. Reports must distinguish measured hardware results from skipped or uncalibrated paths. P1a GPU validation is recorded in `.ai/LAST_REPORT.md`; its short clip measurements do not establish long-job stability or visual quality.

Model selection uses data-only `model.json` manifests under `VE_HOME/models/<id>`.
The Standard release model is `basicvsrpp-ntire21-decompress` (C1); interpolation
uses `rife-4.25`. The built-in C1 manifest prefers 15-frame clips with 2-frame
overlap, validated against the memory, speed and seam requirements.
Repository adapters expose load/warmup/process/release; Spandrel
restoration processes one frame at a time. Source code is never imported from
model folders. Pinned upstream architecture sources live in `VE_HOME/adapter-sources`.
Jobs record model version, weight hash and manifest digest and validate them at
resume and each segment. See [adding models](ADDING_MODELS.md).

Frame anomaly checks compare neighbors on the same source-scene side. A RIFE
inserted frame before a cut belongs to the left scene and references its left
source frame. Cut boundaries remain eligible for corruption detection; they are
not simply masked out. Reports distinguish unique pre-repair compute indices (including clip context
within the segment) from final owned post-repair flags. Persistent inserted-frame anomalies use a 50/50 blend of the
source-aligned output endpoints; restored-frame anomalies use that same decoded
source frame through the preset resize path. Repairs are checked again.
Context frames are also validated and repaired so their corruption cannot leak
into an owned midpoint. A repair is re-checked for newly exposed anomalies.

Completed Fast/Standard jobs store post-encode PSNR-Y/SSIM-Y mean/minimum, flicker
and clip/segment seam ratios in `quality`. Fidelity uses downscaled, source-aligned
even outputs; temporal metrics include inserted frames. The seam formula includes
non-cut joints for its pass/fail value. Joints within +/-1 source frame of a detected
cut are excluded, counted, and retained in per-joint output/source relative diagnostics.
No non-cut joint means N/A. These values are measurements,
not automatic perceptual quality judgments. Undefined ratios/infinite PSNR use JSON null.
