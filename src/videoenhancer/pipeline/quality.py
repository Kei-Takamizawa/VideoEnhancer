"""Bounded post-encode fidelity and temporal measurements using FFmpeg."""

from __future__ import annotations

import math
import re
import subprocess
import tempfile
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.media.mux import _run
from videoenhancer.media.timing import output_rate


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else (1.0 if numerator == 0 else None)


def _temporal(
    path: Path,
    width: int,
    height: int,
    joints: set[int],
    factor: int = 1,
    abort: Callable[[], bool] | None = None,
    *,
    diagnostic_joints: set[int] | None = None,
    excluded: set[int] | None = None,
    source_rate: str | None = None,
) -> dict[str, Any]:
    diagnostic_joints = diagnostic_joints if diagnostic_joints is not None else joints
    excluded = excluded or set()
    filters = f"scale={width}:{height}:flags=area,format=yuv420p"
    if source_rate is not None:
        filters = f"fps={source_rate}," + filters
    if factor > 1:
        filters = f"select='not(mod(n,{factor}))'," + filters
    filters += ",signalstats,metadata=mode=print:key=lavfi.signalstats.YDIF:file=-"
    command = [
        executable("ffmpeg"),
        "-v",
        "error",
        "-nostdin",
        "-i",
        str(path),
        "-an",
        "-vf",
        filters,
        "-f",
        "null",
        "-",
    ]
    total = joint_sum = regular_sum = 0.0
    count = joint_count = regular_count = 0
    details = []
    with tempfile.TemporaryFile() as errors:
        process = proc.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            assert process.stdout is not None
            for raw in process.stdout:
                if abort and abort():
                    raise InterruptedError("Quality measurement was interrupted.")
                text = raw.decode("utf-8", errors="replace").strip()
                if text.startswith("lavfi.signalstats.YDIF="):
                    difference = float(text.split("=", 1)[1])
                    if count:  # The first frame has no preceding frame.
                        total += difference
                        if count in diagnostic_joints:
                            details.append({"frame_index": count, "difference": difference})
                        if count in joints:
                            joint_sum += difference
                            joint_count += 1
                        elif count not in excluded and count not in diagnostic_joints:
                            regular_sum += difference
                            regular_count += 1
                    count += 1
            if process.wait() != 0:
                errors.seek(0)
                raise RuntimeError(errors.read().decode(errors="replace")[-4000:])
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()
    baseline = regular_sum / regular_count if regular_count else 0.0
    return {
        "frames": count,
        "mean_difference": total / max(1, count - 1),
        "joint_count": joint_count,
        "regular_count": regular_count,
        "non_joint_mean_difference": baseline,
        "joint_details": [
            {**detail, "joint_ratio": _ratio(detail["difference"], baseline)} for detail in details
        ],
        "seam_ratio": _ratio(joint_sum / joint_count, baseline)
        if joint_count and regular_count
        else None,
    }


def measure_quality(
    job: dict[str, Any], output: Path, *, abort: Callable[[], bool] | None = None
) -> dict[str, Any]:
    """Compare source-aligned even output frames; keep all files outside the repository."""
    media, settings = job["media"], job["settings"]
    width, height = int(media["display_width"]), int(media["display_height"])
    rate = str(media["cfr_fps"])
    factor = int(output_rate(settings, media) / Fraction(rate))
    source = Path(job["input"]["path"])
    clip_joints = {
        factor * int(frame)
        for segment in job.get("segments", [])
        for frame in segment.get("stats", {}).get("clip_joints", [])
    }
    segment_joints = {factor * int(segment["start"]) for segment in job.get("segments", [])[1:]}
    with tempfile.TemporaryDirectory(prefix="ve-quality-", dir=output.parent) as temporary:
        directory = Path(temporary)
        graph = (
            f"[0:v]fps={rate},scale={width}:{height}:flags=area,format=yuv420p,"
            "split=2[r1][r2];"
            f"[1:v]select='not(mod(n,{factor}))',setpts=N/({rate}*TB),"
            f"scale={width}:{height}:flags=area,format=yuv420p,split=2[o1][o2];"
            "[r1][o1]psnr=stats_file=psnr.log:shortest=1[p];"
            "[r2][o2]ssim=stats_file=ssim.log:shortest=1[s]"
        )
        # Relative log names avoid platform-specific filter escaping of drive paths.
        command = [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(source),
            "-i",
            str(output.resolve()),
            "-filter_complex_threads",
            "2",
            "-filter_complex",
            graph,
            "-map",
            "[p]",
            "-map",
            "[s]",
            "-an",
            "-f",
            "null",
            "-",
        ]
        # mux._run provides the existing cancellation/timeout process contract.
        _run(command, abort, cwd=directory)
        psnr, ssim = [], []
        for line in (directory / "psnr.log").read_text(encoding="utf-8").splitlines():
            match = re.search(r"psnr_y:([\w.+-]+)", line)
            if match:
                psnr.append(float(match[1]))
        for line in (directory / "ssim.log").read_text(encoding="utf-8").splitlines():
            match = re.search(r"Y:([\w.+-]+)", line)
            if match:
                ssim.append(float(match[1]))
        if not psnr or len(psnr) != len(ssim):
            raise RuntimeError("Quality measurement did not produce matching fidelity frames.")
    # Seam/flicker use consecutive output frames, including inserted frames.
    all_joints = clip_joints | segment_joints
    cuts = set(job.get("scene_cuts", []))
    source_cut_neighborhood = {
        frame for cut in cuts for frame in (cut - 1, cut, cut + 1) if frame >= 0
    }
    excluded_positions = {
        frame * factor + phase for frame in source_cut_neighborhood for phase in range(factor)
    }
    excluded_joints = all_joints & excluded_positions
    eligible_joints = all_joints - excluded_joints
    source_joints = {frame // factor for frame in all_joints}
    source_temporal = _temporal(
        source,
        width,
        height,
        set(),
        abort=abort,
        diagnostic_joints=source_joints,
        excluded=source_cut_neighborhood,
        source_rate=rate,
    )
    enhanced_temporal = _temporal(
        output,
        width,
        height,
        eligible_joints,
        abort=abort,
        diagnostic_joints=all_joints,
        excluded=excluded_positions,
    )
    source_details = {detail["frame_index"]: detail for detail in source_temporal["joint_details"]}
    joint_details = []
    for detail in enhanced_temporal["joint_details"]:
        index = detail["frame_index"]
        original = source_details.get(index // factor, {})
        source_ratio, output_ratio = original.get("joint_ratio"), detail["joint_ratio"]
        relative = (
            _ratio(output_ratio, source_ratio)
            if source_ratio is not None and output_ratio is not None
            else None
        )
        joint_details.append(
            {
                **detail,
                "source_frame_index": index // factor,
                "source_joint_ratio": source_ratio,
                "relative_seam": relative,
                "excluded_for_scene_cut": index in excluded_joints,
                "clip_joint": index in clip_joints,
                "segment_joint": index in segment_joints,
            }
        )

    def group_ratio(joints: set[int]) -> float | None:
        differences = [
            detail["difference"]
            for detail in joint_details
            if detail["frame_index"] in joints - excluded_joints
        ]
        return (
            _ratio(
                sum(differences) / len(differences), enhanced_temporal["non_joint_mean_difference"]
            )
            if differences and enhanced_temporal["regular_count"]
            else None
        )

    mean_psnr = sum(psnr) / len(psnr)
    return {
        "fidelity_frames": len(psnr),
        "psnr_y_mean_db": mean_psnr if math.isfinite(mean_psnr) else None,
        "psnr_y_min_db": min(psnr) if math.isfinite(min(psnr)) else None,
        "ssim_y_mean": sum(ssim) / len(ssim),
        "ssim_y_min": min(ssim),
        "flicker_ratio": _ratio(
            enhanced_temporal["mean_difference"], source_temporal["mean_difference"]
        ),
        "seam_ratio": enhanced_temporal["seam_ratio"],
        "clip_seam_ratio": group_ratio(clip_joints),
        "segment_seam_ratio": group_ratio(segment_joints),
        "clip_joint_count": len(clip_joints),
        "segment_joint_count": len(segment_joints),
        "excluded_joint_count": len(excluded_joints),
        "noncut_joint_count": len(eligible_joints),
        "joint_diagnostics": joint_details,
        "method": "Full-resolution 8-bit Y; area downscale; fidelity uses even outputs; "
        "temporal metrics include inserted frames; source uses CFR normalization; "
        "YDIF joint mean / non-joint mean excluding cuts within +/-1 source frame; "
        "relative diagnostic = output joint ratio / source joint ratio at native rates; "
        "null if undefined (including infinite PSNR).",
    }
