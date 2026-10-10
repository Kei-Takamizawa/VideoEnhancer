# Adding restoration models

C1 (BasicVSR++ NTIRE 2021 decompression) remains the first-release restoration
model. Adding a model does not change the default. No training code is included.

## Model folders

Use **model.json** only. Installed folders live at
`%VE_HOME%/models/<id>/`. The installer copies the manifest and its weights,
verifies SHA-256, and ignores unrelated files. Python files in these folders
are never imported. Built-in weights download on first use; listing does not download.
Architecture code comes from repository adapters and pinned, hash-verified upstream
sources cached separately under `%VE_HOME%/adapter-sources/`.

Create a folder containing your checkpoint and this example manifest. Replace the
hash with the complete lowercase SHA-256 of your actual weights. IDs must be unique.

```json
{
  "id": "my-basicvsr-finetune",
  "display_name": "My BasicVSR++ fine-tune",
  "version": "1",
  "description": "Same-size restoration with my fine-tuned weights",
  "task": "restore",
  "architecture": "basicvsrpp",
  "architecture_params": {"mid_channels": 128, "num_blocks": 25},
  "weights": {"filename": "weights.pth", "sha256": "REPLACE_WITH_64_HEX_DIGITS"},
  "licence": "REPLACE_WITH_THE_ACTUAL_WEIGHT_LICENCE_AND_CONDITIONS",
  "commercial_use_allowed": false,
  "scale": 1,
  "temporal": true,
  "clip_length": 15,
  "clip_overlap": 2,
  "precision": "fp16",
  "vram_estimate_mb": {}
}
```

```powershell
(Get-FileHash C:\MyModels\finetune\weights.pth -Algorithm SHA256).Hash.ToLower()
ve models add C:\MyModels\finetune
ve models list
ve enhance input.mp4 -o custom.mp4 --restore-model my-basicvsr-finetune
ve models remove my-basicvsr-finetune
```

BasicVSR++ accepts a tensor state dictionary, or a dictionary containing
`state_dict`. Keys may have the original `generator.` prefix. The network loads
strictly: channel/block counts must match, all parameters must be present, and
extra parameters are rejected. `step_counter` is ignored. Full pickled model
objects and executable training checkpoints are unsupported; all three adapters
use `torch.load(..., weights_only=True)`. This is an inference-only loader.

`weights.url` is optional and must use HTTPS. `models add` requires local weights;
first-use downloading applies to models already installed as data folders. An
existing file with a wrong hash is refused, not silently replaced.

Temporal manifests require `clip_length > 2 * clip_overlap >= 0`. Precision is
`fp16` or `fp32`; CPU inference uses FP32. VRAM estimates, if provided, map named
size classes to nonnegative MB values. They are declarations, not measured limits.
Only scale 1 restoration/interpolation is supported in this cycle.

The licence field is mandatory. Third-party weight licences, training-data rights,
and permission for your intended use are your responsibility. A supplied boolean
does not establish legal permission. The built-in licence descriptions reference
[OpenMMLab's Apache-2.0 licence](https://github.com/open-mmlab/mmagic/blob/main/LICENSE)
and [Practical-RIFE's MIT licence](https://github.com/hzwer/Practical-RIFE/blob/bbfd2ea90910789a860ea3e2b32a240cd577b75e/LICENSE).

## Spandrel models

Install the `models` dependency extra. Use `architecture: "spandrel"`,
`architecture_params: {}`, `task: "restore"`, `temporal: false`, `scale: 1`,
and the checkpoint's actual hash/licence. Omit clip length/overlap. The adapter
processes one frame at a time and preserves dimensions and timestamps.

Only Spandrel single-image RGB-to-RGB descriptors with scale 1 are accepted.
FP16 declarations require descriptor FP16 support. Unsupported architectures,
upscalers, and geometry/non-finite failures give errors rather than changing the
pipeline. Architecture recognition uses
[Spandrel's state-dictionary API](https://chainner.app/spandrel/spandrel.ModelLoader.html),
after restricted Torch deserialization; no loader is taken from your folder.

## Repository adapters

For a new architecture, add a reviewed module under `src/videoenhancer/models/`.
Subclass `Stage`: implement `setup`, `process(FrameBatch)`, and `teardown`.
The common interface exposes `load`, `warmup(sample)`, `process`, and `release`;
warmup runs a caller-supplied representative batch and discards its output.
Restoration stages must have `name="restore"`, bounded `clip_length`,
`clip_overlap`, `context_before`, and `context_after`. Preserve frame indices,
timestamps, and geometry. Interpolation adapters must follow the existing RIFE
2x index/timestamp and scene-cut contract.

Register a factory from repository code with
`register_adapter("architecture-name", "restore", factory)`. A factory receives
`(manifest, verified_weights_path, settings, input_rate, source_cut_indices)` and
returns a stage. Registration never imports a module named in a manifest.
Add schema checks for architecture-specific parameters and CPU/GPU tests.
Pipeline changes are unnecessary for new weights of an already registered architecture.

## Compare with C1

Keep private inputs and generated videos outside Git. Use anonymized aliases.
Generate matched degradations with the existing script:

```powershell
python scripts/make_degraded.py --input-dir C:\Evaluation\sources --output-dir C:\Evaluation\degraded
ve enhance C:\Evaluation\degraded\A_D2.mp4 -o C:\Evaluation\c1.mp4 --restore-model basicvsrpp-ntire21-decompress --short-side keep --fps off
ve enhance C:\Evaluation\degraded\A_D2.mp4 -o C:\Evaluation\custom.mp4 --restore-model my-basicvsr-finetune --short-side keep --fps off
```

Use the aligned windows and PSNR-Y/SSIM-Y/flicker method in
[the existing benchmark report](BENCHMARK_DEGRADED.md). Existing cycle scripts
(`complete_p1a5.py` and `review_and_tables_p1a5.py`) remain external evaluation
tools; they are not distributed CLI commands and their candidate lists are fixed.
To compare your output, use their existing aligned metric/render pass on the
two files, with identical limited-range BT.709 conversion. The retained P1a-5
helper is at `%USERPROFILE%/Documents/VideoEnhancer-P1a-5/complete_p1a5.py` on
the evaluation machine. Its `quality` function measures exactly 150 frames at
720x1280; prepare aligned files of that size with at least 150 frames. For example,
run this in a separate Python process with the model dependencies installed:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "VideoEnhancer-P1a-5"))
from complete_p1a5 import quality

reference = Path("C:/Evaluation/matched-original-720x1280.mp4")
for name in ("c1", "custom"):
    print(name, quality(reference, Path(f"C:/Evaluation/{name}.mp4"), first=0))
```

This calls the existing metric helper only; it does not run its fixed candidate
sweep. That external helper is not included in a fresh repository clone.
Do not claim a quality
gain from fidelity against the degraded input alone: the degradation benchmark
must compare with the matched original. Report speed, memory, and visual review
separately. This cycle adds no benchmark candidates or training procedure.

Jobs record model ID, version, weight SHA-256 and a canonical manifest digest.
Resume and every segment refuse a changed selection, manifest, or weights.
Install a new version under a new ID and create a new job; do not edit a model
between segments. P0 jobs with no model stages retain their existing resume path.

## P1c-2 catalog status

The additional cleanup, motion and size catalog proposed for P1c-2 is not yet
implemented. Existing built-ins and compatible local-folder models remain
available. No optional entry is advertised with unmeasured speed or memory.
The current trial viewer supports Original/Enhanced rather than three model
variants. See `.ai/LAST_REPORT.md` for the implemented scope and pending checks.
