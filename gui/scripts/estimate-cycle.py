"""Contained, resumable measurement entry points for VE-P1e-3d2."""

import argparse
import copy
import json
import os
import shutil
import statistics
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil

WORK = Path(__file__).resolve().parents[3]
ROOT = WORK / "scratch/p1e3d2"
EVIDENCE = WORK / "evidence/VE-P1e-3d2"


def contained(path):
    path = path.resolve()
    if not path.is_relative_to(WORK) or str(WORK).lower() != (
        "D:\\my-workspace\\VideoEnhancer\\work".lower()
    ):
        raise ValueError(f"Output must stay under the absolute work root: {path}")
    return path


def save(path, value):
    contained(path).write_text(json.dumps(value, indent=2), encoding="utf-8")


def prepare_home(home):
    contained(home).mkdir(parents=True, exist_ok=False)
    cache = contained(Path(os.environ["VE_GPU_TEST_MODEL_HOME"]))

    def copy(source, target):
        if Path(source).suffix.lower() in {".pth", ".pkl", ".pt", ".zip"}:
            os.link(source, target)
        else:
            shutil.copy2(source, target)
        return target

    for name in ("models", "adapter-sources"):
        shutil.copytree(cache / name, home / name, copy_function=copy)


def summarize_calibration():
    labels = [f"calibration-fixed-{i}" for i in (1, 2, 3)]
    profiles = [
        json.loads((EVIDENCE / f"{label}-bench.json").read_text())["profile"] for label in labels
    ]
    old = json.loads((EVIDENCE / "profile-before.json").read_text())

    def median(values, key=""):
        first = values[0]
        if key in {"stats", "identity", "samples"}:
            return copy.deepcopy(first)
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            return statistics.median(values)
        if isinstance(first, dict):
            return {
                k: median([v[k] for v in values], k) for k in first if all(k in v for v in values)
            }
        if isinstance(first, list) and all(len(v) == len(first) for v in values):
            return [median([v[i] for v in values]) for i in range(len(first))]
        return copy.deepcopy(first)

    profile = median(profiles)
    tiny = profile["finalization"]["tiny_clip_fit"]
    profile["finalization"] = {**copy.deepcopy(old["finalization"]), "tiny_clip_fit": tiny}
    profile["analysis_seconds_per_frame"] = old["analysis_seconds_per_frame"]
    profile["source"] = "builtin"
    profile["provenance"] = (
        "2026-10-30: median of three independent full synthetic calibrations on "
        "main 38b41ae + task HEAD 69b0450a5b881a18f75a30bc99c7c2276a1dc463 + "
        "VE-P1e-3d2 Parts A/B; real reusable ProcessExecutor startup; unchanged "
        "P1e-2 long-output finalization points/samples. No gate-job tuning."
    )
    for entry in profile["reference_pipelines"].values():
        entry.pop("stats", None)
    for model in ("basicvsrpp-ntire21-decompress", "rife-4.25"):
        assert all(p["models"][model]["status"] == "measured" for p in profiles)
    assert profile["max_measured_output_pixels"] == 1440 * 2560
    for component in ("decode", "encode", "color", "resize", "blend2x"):
        assert all(
            isinstance(p["components"][component]["seconds_per_pixel_frame"], (int, float))
            for p in profiles
        ), f"Cannot publish a profile with an unmeasured {component} coefficient."
    for preset in ("standard", "fast"):
        assert len(profile["pipeline_size_points"][preset]) >= 2
        assert set(profile["startup_by_preset"][preset]) == {"cold", "warm"}

    def coefficients(value, prefix=""):
        result = {}
        if isinstance(value, dict):
            for key, item in value.items():
                path = f"{prefix}.{key}" if prefix else key
                if key in {"seconds_per_pixel_frame", "load_seconds", "factor", "cold", "warm"}:
                    if isinstance(item, (int, float)):
                        result[path] = item
                elif key not in {"stats", "identity", "finalization", "reference_pipelines"}:
                    result.update(coefficients(item, path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                result.update(coefficients(item, f"{prefix}[{index}]"))
        return result

    measured = [coefficients(p) for p in profiles]
    old_values = coefficients(old)
    for preset, value in old["startup_by_preset"].items():
        for kind in ("cold", "warm"):
            old_values[f"startup_by_preset.{preset}.{kind}"] = value
    rows = []
    for key in measured[0]:
        values = [run[key] for run in measured]
        center = statistics.median(values)
        spread = (max(values) - min(values)) / center * 100 if center else 0
        rows.append(
            dict(
                term=key,
                old=old_values.get(key),
                runs=values,
                median=center,
                minimum=min(values),
                maximum=max(values),
                spread_percent=spread,
            )
        )
    save(
        EVIDENCE / "calibration-summary.json",
        dict(
            coefficients=rows,
            wall_seconds=[p["calibration_wall_seconds"] for p in profiles],
            startup_stages_seconds=[
                p["calibration_stages_seconds"]["Worker startup"] for p in profiles
            ],
        ),
    )
    save(WORK / "repo/src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json", profile)
    print("Published three-run median profile; coefficients with spread above 10%:", flush=True)
    print(json.dumps([row for row in rows if row["spread_percent"] > 10], indent=2), flush=True)


def gate(label, home):
    from videoenhancer import proc
    from videoenhancer.config import executable
    from videoenhancer.estimate.model import predict_finalization, predict_segment
    from videoenhancer.estimate.startup import cold_parts
    from videoenhancer.service.engine import Engine
    from videoenhancer.service.settings import write_json

    name = label.split("-attempt")[0]
    duration, geometry, preset, size, codec = {
        "G-10": (600, "720x1280", "standard", 1080, "hevc"),
        "G-1440": (30, "720x1280", "standard", 1440, "hevc"),
        "G-Fast": (120, "1920x1080", "fast", 1080, "h264"),
    }[name]
    source = home / "synthetic.mp4"
    command = [
        executable("ffmpeg"),
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={geometry}:rate=30:duration={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=48000:duration={duration}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-b:v",
        "1M",
        "-maxrate",
        "1M",
        "-bufsize",
        "2M",
        "-threads",
        "2",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(source),
    ]
    save(EVIDENCE / f"{label}-recipe.json", command)
    proc.run(command, check=True, capture_output=True)
    engine = Engine(home)
    request = dict(
        file=str(source),
        output_folder=str(home / "output"),
        settings=dict(
            preset=preset,
            backend="cuda",
            short_side=size,
            fps="2x",
            codec=codec,
            output_folder=str(home / "output"),
            cleanup_working_files=False,
        ),
    )
    report = dict(label=label, samples=[], source_bytes=source.stat().st_size)
    path = EVIDENCE / f"{label}-gate.json"
    try:
        if name == "G-10":
            preview = engine.estimate(request)["presets"][preset]
            now = datetime.now(UTC)
            approximate = now + timedelta(seconds=preview["seconds"] * 0.65)
            gap = approximate.replace(second=0, microsecond=0)
            gap += timedelta(minutes=(-gap.minute) % 15)
            gap_end = gap + timedelta(minutes=15)
            if gap.date() != now.date() or gap_end.date() != gap.date():
                raise ValueError("Choose a start time whose gap stays within one UTC day.")
            schedule = dict(
                schema_version=1,
                timezone="UTC",
                enabled=True,
                weekly=[
                    dict(
                        days=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                        start="00:00",
                        end="00:00",
                    )
                ],
                exceptions=[
                    dict(
                        date=gap.date().isoformat(),
                        windows=[
                            dict(start="00:00", end=gap.strftime("%H:%M")),
                            dict(start=gap_end.strftime("%H:%M"), end="00:00"),
                        ],
                    )
                ],
            )
            write_json(home / "schedule.json", schedule)
            report["schedule"] = schedule
            report["gap"] = dict(start=gap.isoformat(), end=gap_end.isoformat())
        assert not (home / "timing-observations.json").exists()
        engine.start()
        began = time.perf_counter()
        added_at = datetime.now(UTC)
        job = engine.add(request)
        report.update(
            added_at=added_at.isoformat(),
            job_id=job["id"],
            initial_estimate_seconds=job["initial_estimate_seconds"],
            initial_finish_at=job["initial_finish_at"],
        )
        save(path, report)
        first_manifest = None
        milestones = set()
        deadline = time.monotonic() + 8 * 3600
        while time.monotonic() < deadline:
            current = engine.store.load(job["id"])
            if current.get("segments") and first_manifest is None:
                first_manifest = current
                report["first_finalization_prediction"] = predict_finalization(current)
                save(EVIDENCE / f"{label}-first-manifest.json", current)
            if current["state"] in {"done", "failed", "cancelled"}:
                report["job"] = current
                report["elapsed_seconds"] = time.perf_counter() - began
                report["finished_at"] = datetime.now(UTC).isoformat()
                if current["state"] != "done":
                    raise RuntimeError(current.get("error", current["state"]))
                break
            if current.get("segments"):
                row = next(row for row in engine.queue()["jobs"] if row["id"] == job["id"])
                percent = row["progress_percent"]
                for milestone in (25, 50, 75):
                    if percent >= milestone and milestone not in milestones:
                        milestones.add(milestone)
                        report["samples"].append(
                            dict(
                                milestone=milestone,
                                percent=percent,
                                at=datetime.now(UTC).isoformat(),
                                elapsed_seconds=time.perf_counter() - began,
                                finish_at=row["eta"],
                                estimate=row["estimate"],
                            )
                        )
                        save(path, report)
            time.sleep(2)
        else:
            raise TimeoutError("Gate did not finish within eight hours")
        final = report["job"]
        initial = first_manifest or final
        assignments = cold_parts(initial)
        report["parts"] = [
            dict(
                index=part["index"],
                startup_kind=part["stats"].get("startup_kind"),
                initial_kind="cold" if assignments[part["index"]] else "warm",
                initial_prediction=predict_segment(
                    final["media"],
                    final["settings"],
                    part["end"] - part["start"],
                    initial.get("machine_profile"),
                    cold=assignments[part["index"]],
                ),
                admitted_prediction=part.get("predicted_seconds"),
                actual_seconds=part.get("actual_seconds"),
                startup_seconds=part["stats"].get("per_part_startup_seconds"),
            )
            for part in final["segments"]
        ]
        observation = final["timing"]["finalization_observation"]
        report["actual_processing_seconds"] = (
            sum(p["actual_seconds"] for p in final["segments"])
            + final.get("analysis_seconds", 0)
            + observation["actual"]
        )
        report["finalization"] = observation
        if name == "G-10":
            engine.close()
            from videoenhancer.bench.runner import run_bench

            calibration = run_bench(
                calibrate=True,
                output_dir=home / "after-gate-calibration",
                progress=lambda phase, pct: print(phase, pct, flush=True),
            )
            # Use raw calibration: local finalization learning must not conceal a lost curve.
            profile = calibration["profile"]
            report["G-Cal"] = dict(
                predicted=predict_finalization(final, profile),
                actual=observation["actual"],
                points_unchanged=profile["finalization"]["points"]
                == initial["machine_profile"]["finalization"]["points"],
            )
            save(EVIDENCE / f"{label}-after-calibration.json", calibration)
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        engine.close()
        save(path, report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("calibrate", "gate", "startup", "summarize"))
    parser.add_argument("label")
    parser.add_argument("--source-root", type=Path, default=WORK / "repo")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    if args.mode == "summarize":
        summarize_calibration()
        return
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    home = contained(ROOT / args.label)
    os.environ["VE_HOME"] = str(home)
    os.environ["APPDATA"] = str(home / "roaming")
    os.environ["LOCALAPPDATA"] = str(home / "local")
    os.environ["TEMP"] = os.environ["TMP"] = str(contained(WORK / "scratch/tmp"))
    source_root = contained(args.source_root)
    sys.path.insert(0, str(source_root / "src"))
    record = dict(
        label=args.label,
        start=datetime.now(UTC).isoformat(),
        pid=os.getpid(),
        home=str(home),
        source_root=str(source_root),
        status="running",
    )
    path = EVIDENCE / f"{args.label}-run.json"
    save(path, record)
    prepare_home(home)
    stop = threading.Event()
    seen = set()

    def heartbeat():
        while not stop.is_set():
            children = psutil.Process().children(recursive=True)
            seen.update(p.pid for p in children)
            save(
                EVIDENCE / f"{args.label}-processes.json",
                dict(
                    pid=os.getpid(),
                    children=sorted(seen),
                    live=[p.pid for p in children],
                    time=datetime.now(UTC).isoformat(),
                ),
            )
            stop.wait(5)

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    began = time.perf_counter()
    try:
        if args.mode == "calibrate":
            from videoenhancer.bench.runner import run_bench

            report = run_bench(
                calibrate=True,
                output_dir=home / "bench",
                progress=lambda phase, percent: print(phase, percent, flush=True),
            )
            save(EVIDENCE / f"{args.label}-bench.json", report)
        elif args.mode == "startup":
            from videoenhancer.bench.startup import calibrate_startup

            save(
                EVIDENCE / f"{args.label}-startup.json",
                calibrate_startup(home / "bench/startup", "cuda"),
            )
        else:
            gate(args.label, home)
        record["status"] = "done"
    except BaseException as error:
        record.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            error=repr(error),
        )
        raise
    finally:
        stop.set()
        thread.join(timeout=10)
        record["elapsed_seconds"] = time.perf_counter() - began
        record["children"] = sorted(seen)
        children = psutil.Process().children(recursive=True)
        _, alive = psutil.wait_procs(children, timeout=5)
        record["remaining_before_cleanup"] = [p.pid for p in alive]
        for child in alive:
            if child.is_running():
                child.terminate()
        _, remaining = psutil.wait_procs(alive, timeout=5)
        record["terminated_pids"] = [p.pid for p in alive]
        record["remaining_pids"] = [p.pid for p in remaining]
        save(path, record)


if __name__ == "__main__":
    main()
