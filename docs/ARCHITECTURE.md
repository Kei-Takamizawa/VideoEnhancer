# Architecture

VideoEnhancer is organized as a local conversion engine. A job is probed and normalized into a frame timeline, split into resumable segments, processed by ordered stages, then assembled with its original audio. The P0 stages are resize and frame blending; neural restoration is out of scope for conversion and appears only in the optional benchmark.

The media layer owns probing, decode, color conversion, encode and mux. Pipeline stages consume batches of RGB tensors. Job storage owns the manifest and atomic segment state. The scheduler decides when segments may run, while the estimator uses a per-machine profile plus observed job timings. These boundaries are intended to support a later desktop interface without adding a network service.

CUDA decode, processing and encode are hardware-dependent. CPU support exists for deterministic development and CI. Reports must distinguish measured hardware results from skipped or uncalibrated paths.
