# Architecture

VideoEnhancer is organized as a local conversion engine. A job is probed and normalized into a frame timeline, split into resumable segments, processed by ordered stages, then assembled with its original audio. The production presets share one bounded decode → compute → encode streaming runner. `fast` uses Practical-RIFE motion interpolation; `standard` uses BasicVSR++ restoration, resize, then Practical-RIFE.

The media layer owns probing, decode, color conversion, encode and mux. Standard restoration is split into overlapping clips. Clips stop at hard scene cuts; overlap frames are emitted once by the clip in which the frame is farthest from an edge (ties go to the later clip). A bounded frame buffer supplies context across segment boundaries and releases frames after their final clip use. Interpolated frames belong to the left source frame. Job storage owns the manifest and atomic segment state. The scheduler decides when segments may run, while the estimator uses a per-machine profile plus observed job timings.

CUDA decode, processing and encode are hardware-dependent. CPU support exists for deterministic development and CI. Reports must distinguish measured hardware results from skipped or uncalibrated paths. P1a GPU validation is recorded in `.ai/LAST_REPORT.md`; its short clip measurements do not establish long-job stability or visual quality.
