"""Bound PyTorch allocations in processing children, with one uncapped rerun."""

from __future__ import annotations

import gc
from collections.abc import Callable
from typing import Any

import torch

# A1: maximum simultaneous process dedicated minus Torch reserved was
# 329,269,248 bytes. Round upward to a complete allocator MiB.
GPU_RESERVE_BYTES = 330_301_440


def budget_fraction(free: int, total: int, reserve: int = GPU_RESERVE_BYTES) -> float:
    if total <= 0 or free < 0 or reserve < 0:
        raise ValueError("GPU memory sizes must be nonnegative, with a positive total.")
    return min(1.0, max(0, free - reserve) / total)


def is_cuda_oom(error: BaseException) -> bool:
    seen = set()
    while id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, torch.cuda.OutOfMemoryError):
            return True
        if (
            "cuda out of memory" in str(error).lower()
            or "exhausted gpu memory" in str(error).lower()
        ):
            return True
        previous = error.__cause__ or error.__context__
        if previous is None:
            return False
        error = previous
    return False


def dedicated_free(cuda: Any) -> tuple[int, int, str]:
    free, total = cuda.mem_get_info()
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            memory = pynvml.nvmlDeviceGetMemoryInfo(
                pynvml.nvmlDeviceGetHandleByIndex(cuda.current_device())
            )
            # On WDDM cudaMemGetInfo may report this process's virtual allowance,
            # unchanged by allocations in a different process. NVML is device-wide.
            return min(free, int(memory.free)), total, "NVML dedicated / CUDA minimum"
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return free, total, "CUDA memory info (NVML unavailable)"


def run_with_budget(
    run: Callable[[Callable[[dict[str, Any]], None]], dict[str, Any]],
    *,
    enabled: bool,
    progress: Callable[[dict[str, Any]], None] | None = None,
    cuda: Any = None,
) -> dict[str, Any]:
    real_cuda = cuda is None
    cuda = torch.cuda if real_cuda else cuda
    samples: list[dict[str, Any]] = []
    oom_retries = 0

    def observe(value: dict[str, Any]) -> None:
        nonlocal oom_retries
        if "memory" in value:
            samples.append(value["memory"])
        oom_retries = max(oom_retries, value.get("oom_retries", 0))
        if progress is not None:
            progress(value)

    budget: dict[str, Any] = {"cap_on": False}
    previous_fraction = None
    reruns = 0
    try:
        if enabled:
            try:
                if real_cuda:
                    free, total, source = dedicated_free(cuda)
                else:
                    free, total = cuda.mem_get_info()
                    source = "test counter"
                previous_fraction = cuda.get_per_process_memory_fraction()
                fraction = budget_fraction(free, total)
                cuda.set_per_process_memory_fraction(fraction)
                budget = dict(
                    cap_on=True,
                    free_bytes=free,
                    total_bytes=total,
                    reserve_bytes=GPU_RESERVE_BYTES,
                    fraction=fraction,
                    source=source,
                )
            except (RuntimeError, AttributeError) as error:
                # Unsupported allocator controls must not prevent an otherwise
                # runnable part. Report the reason alongside its statistics.
                enabled = False
                budget = dict(cap_on=False, unavailable_reason=str(error))
                observe({"step": "GPU memory cap unavailable", "gpu_budget": budget})
        try:
            stats = run(observe)
        except Exception as error:
            if not enabled or not is_cuda_oom(error):
                raise
            reruns = 1
        if reruns:
            # Leave the exception scope before collecting traceback-held tensors.
            cuda.set_per_process_memory_fraction(1.0)
            gc.collect()
            cuda.empty_cache()
            observe({"step": "Retrying without GPU memory cap", "frames_done": 0})
            stats = run(observe)
        stats.update(
            gpu_budget=budget,
            gpu_cap_on=enabled and not reruns,
            uncapped_re_runs=reruns,
            ran_over_gpu_memory=bool(reruns),
            capped_oom_retries=oom_retries,
        )
        if samples:
            stats["memory_samples"] = samples
            known = [s for s in samples if s.get("spilled") is not None]
            stats["spilled"] = any(s.get("spilled") for s in known) if known else None
            for field in ("process_dedicated_gpu_bytes", "process_shared_gpu_bytes"):
                values = [s[field] for s in samples if s.get(field) is not None]
                stats["peak_" + field] = max(values) if values else None
        return stats
    finally:
        if previous_fraction is not None:
            try:
                cuda.set_per_process_memory_fraction(previous_fraction)
            except (RuntimeError, AttributeError):
                # The processing child exits after this part.
                pass
