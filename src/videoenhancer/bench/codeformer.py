"""Measure externally cached CodeFormer; no S-Lab source is vendored here."""

import logging
import statistics
from typing import Any

from videoenhancer.bench.external import (
    Registry,
    isolated_modules,
    load_module,
    module_stub,
    verified_asset,
    verified_source,
)

SOURCE_COMMIT = "b33cc7d639d6545bfcccc7e0bc6ae51f24e79c2b"
SOURCE_SHA256 = "a67033e34186f05599caed7ae24abea1b18335ca21591741f1d66f1ccc592eae"
WEIGHTS_URL = "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth"
WEIGHTS_SHA256 = "1009e537e0c2a07d4cabce6355f53cb66767cd4b4297ec7a4a64ca4b8a5684b7"


def bench_codeformer(torch: Any) -> dict[str, Any]:
    common: dict[str, Any] = {
        "name": "CodeFormer",
        "license": "NTU S-Lab License 1.0 (non-commercial)",
        "source_url": "https://github.com/sczhou/CodeFormer",
        "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCE_SHA256,
        "weights_url": WEIGHTS_URL,
        "sha256": WEIGHTS_SHA256,
        "precision": "float16",
        "fidelity_weight": 0.7,
        "torch_inference_mode": True,
        "checksum_provenance": "Pinned after first acquisition from the official HTTPS publisher.",
    }
    try:
        source = verified_source(
            f"https://codeload.github.com/sczhou/CodeFormer/zip/{SOURCE_COMMIT}",
            SOURCE_SHA256,
            "codeformer-code.zip",
            f"CodeFormer-{SOURCE_COMMIT}",
        )
        weights = verified_asset(WEIGHTS_URL, WEIGHTS_SHA256, "codeformer.pth")
        with isolated_modules("basicsr"):
            module_stub("basicsr")
            module_stub("basicsr.archs")
            module_stub(
                "basicsr.utils", get_root_logger=lambda: logging.getLogger("external.codeformer")
            )
            module_stub("basicsr.utils.registry", ARCH_REGISTRY=Registry())
            vqgan = load_module("basicsr.archs.vqgan_arch", source / "basicsr/archs/vqgan_arch.py")
            architecture = load_module(
                "basicsr.archs.codeformer_arch", source / "basicsr/archs/codeformer_arch.py"
            )

            def embedding_lookup(self: Any, indices: Any, shape: Any) -> Any:
                # Equivalent embedding lookup keeps the pretrained weights in FP16.
                features = torch.nn.functional.embedding(indices.reshape(-1), self.embedding.weight)
                return (
                    features.reshape(shape).permute(0, 3, 1, 2).contiguous()
                    if shape is not None
                    else features
                )

            vqgan.VectorQuantizer.get_codebook_feat = embedding_lookup
            network = architecture.CodeFormer().eval()
            state = torch.load(weights, map_location="cpu", weights_only=True)
            network.load_state_dict(state["params_ema"], strict=True)
            del state
            network = network.cuda().half()
            variants = []
            for batch in (1, 4, 8):
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                sample = (
                    torch.rand((batch, 3, 512, 512), device="cuda", dtype=torch.float16) * 2 - 1
                )
                try:
                    with torch.inference_mode():
                        for _ in range(5):
                            result = network(sample, w=0.7, adain=True)[0]
                        if not bool(torch.isfinite(result).all()):
                            raise RuntimeError("CodeFormer produced non-finite output in FP16.")
                        del result
                        timings = []
                        begin, end = (
                            torch.cuda.Event(enable_timing=True),
                            torch.cuda.Event(enable_timing=True),
                        )
                        for _ in range(50):
                            begin.record()
                            result = network(sample, w=0.7, adain=True)[0]
                            end.record()
                            end.synchronize()
                            timings.append(begin.elapsed_time(end))
                            del result
                    variants.append(
                        {
                            "status": "measured",
                            "batch_size": batch,
                            "median_ms": statistics.median(timings),
                            "p90_ms": sorted(timings)[44],
                            "iterations": 50,
                            "peak_vram_bytes": torch.cuda.max_memory_reserved(),
                        }
                    )
                except torch.cuda.OutOfMemoryError:
                    variants.append(
                        {
                            "status": "skipped",
                            "batch_size": batch,
                            "reason": "CUDA out of memory on this GPU.",
                        }
                    )
                finally:
                    del sample
            measured = [v for v in variants if v["status"] == "measured"]
            if not measured:
                raise RuntimeError("No requested CodeFormer batch size fits this GPU.")
            largest = max(measured, key=lambda item: item["batch_size"])
            del network
        torch.cuda.empty_cache()
        return {
            **common,
            **largest,
            "variants": variants,
            "largest_tested_working_batch": largest["batch_size"],
            "input_shape": [largest["batch_size"], 3, 512, 512],
            "adapter": (
                "External original network; FP16 embedding lookup replaces "
                "its float32 one-hot multiply."
            ),
        }
    except Exception as error:
        torch.cuda.empty_cache()
        return {
            **common,
            "status": "skipped",
            "reason": f"External CodeFormer benchmark failed: {type(error).__name__}: {error}",
        }
