"""Sequential, resumable GPU measurements for VE-P1e-3d1; no Git mutation."""

import argparse
import difflib
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
REPO = WORK / "repo"
ROOT = WORK / "scratch/p1e3d1"
EVIDENCE = WORK / "evidence/VE-P1e-3d1"
SCRIPTS = REPO / "gui/scripts"
OLD_GUARD = "            with torch.inference_mode():\n                fn()\n"
STREAM_GUARD = (
    "            with torch.inference_mode(), (\n"
    "                torch.cuda.stream(torch.cuda.Stream())\n"
    '                if backend == "cuda"\n'
    "                else contextlib.nullcontext()\n"
    "            ):\n                fn()\n"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_hashes(root):
    return {str(p.relative_to(root)): digest(p) for p in sorted((root / "src").rglob("*.py"))}


def compact_job(result):
    """Keep full per-run evidence once, rather than duplicating it in the summary."""
    job = result["job"]
    parts = []
    for part in job["segments"]:
        stats = part.get("stats", {})
        parts.append(
            dict(
                index=part["index"],
                seconds=part.get("actual_seconds"),
                startup=stats.get("per_part_startup_seconds"),
                startup_terms=stats.get("startup_terms_seconds"),
                pids=sorted({s["pid"] for s in stats.get("memory_samples", []) if "pid" in s}),
                spilled=stats.get("spilled"),
                oom_retries=stats.get("oom_retries"),
                uncapped_re_runs=stats.get("uncapped_re_runs"),
            )
        )
    return dict(
        label=result["label"],
        pid=result.get("pid"),
        state=job["state"],
        elapsed_seconds=result["elapsed_seconds"],
        sha256=result["sha256"],
        output_bytes=result.get("output_bytes"),
        parts=parts,
        remaining_pids=result.get("remaining_pids"),
        resumed=result.get("resumed", False),
        shutdown_seconds=result.get("shutdown_seconds"),
    )


def prepare():
    variants = ROOT / "variants"
    provenance = EVIDENCE / "variants.json"
    if provenance.exists():
        saved = json.loads(provenance.read_text())
        for name, hashes in saved.items():
            assert code_hashes(variants / name) == hashes, f"Changed snapshot: {name}"
        assert code_hashes(REPO) == saved["warm"], "Production source changed after snapshot"
        return saved
    (variants / "warm").mkdir(parents=True, exist_ok=False)
    shutil.copytree(
        REPO / "src", variants / "warm/src", ignore=shutil.ignore_patterns("__pycache__")
    )
    for name in ("c1-gpu", "trim-context", "cuda-streams"):
        shutil.copytree(variants / "warm", variants / name)
    c1 = variants / "c1-gpu/src/videoenhancer/models/basicvsr.py"
    text = c1.read_text()
    old = "                self.model = self.model.cpu()\n"
    assert text.count(old) == 1
    c1.write_text(
        text.replace(
            old,
            "                if self.weight_sha256 != WEIGHTS_SHA256:\n"
            "                    self.model = self.model.cpu()\n",
        )
    )
    trim = variants / "trim-context/src/videoenhancer/pipeline/runner.py"
    text = trim.read_text()
    old = (
        "    source_start, source_end = max(0, start - context_before), "
        "min(count, end + context_after)"
    )
    assert old in text
    text = text.replace(old, "    source_start, source_end = start, end")
    text = text.replace('    count = len(manifest["cfr_map"])\n', "")
    text = text.replace("    context_before = sum(s.context_before for s in stages)\n", "")
    trim.write_text(text)
    streams = variants / "cuda-streams/src/videoenhancer/pipeline/runner.py"
    text = streams.read_text().replace("import logging\n", "import contextlib\nimport logging\n")
    old = OLD_GUARD
    assert text.count(old) == 1
    text = text.replace(
        old,
        STREAM_GUARD,
    )
    streams.write_text(text)
    saved = {
        name: code_hashes(variants / name)
        for name in ("warm", "c1-gpu", "trim-context", "cuda-streams")
    }
    provenance.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    for name in ("c1-gpu", "trim-context", "cuda-streams"):
        lines = []
        for relative in saved["warm"]:
            before, after = variants / "warm" / relative, variants / name / relative
            if digest(before) != digest(after):
                lines.extend(
                    difflib.unified_diff(
                        before.read_text().splitlines(True),
                        after.read_text().splitlines(True),
                        fromfile=f"warm/{relative}",
                        tofile=f"{name}/{relative}",
                    )
                )
        (EVIDENCE / f"{name}.patch").write_text("".join(lines), encoding="utf-8")
    return saved


def run(script, label, options):
    result_file = EVIDENCE / f"{label}.json"
    if result_file.exists():
        result = json.loads(result_file.read_text())
        if result.get("error"):
            raise RuntimeError(f"Previous failed measurement must be reviewed: {label}")
        print("RESUME", label, flush=True)
        return result
    if (EVIDENCE / "stop-benchmarks").exists():
        raise InterruptedError("Measurement stopped by the operator")
    command = [sys.executable, str(SCRIPTS / script), "--label", label, *map(str, options)]
    if script == "job-profile.py" and label.endswith("-g5"):
        command.append("--resume-g5")
    old_log = EVIDENCE / f"{label}.log"
    if old_log.exists():
        number = 1
        while (EVIDENCE / f"{label}-interrupted-{number}.log").exists():
            number += 1
        old_log.rename(EVIDENCE / f"{label}-interrupted-{number}.log")
    with (EVIDENCE / f"{label}.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        began, next_update = time.monotonic(), 0.0
        print("START", label, "pid", process.pid, flush=True)
        while process.poll() is None:
            elapsed = time.monotonic() - began
            if elapsed >= next_update:
                state = ""
                paths = list((ROOT / label / "jobs").glob("*/manifest.json"))
                if paths:
                    try:
                        job = json.loads(paths[0].read_text())
                        parts = job.get("segments", [])
                        done = sum(p["state"] == "done" for p in parts)
                        state = f" {job['state']} parts={done}/{len(parts)}"
                    except (OSError, ValueError):
                        pass
                print(f"RUN {label} {elapsed:.0f}s{state}", flush=True)
                next_update = elapsed + 30
            time.sleep(1)
        if process.returncode:
            raise RuntimeError(f"Measurement {label} exited {process.returncode}; see its log")
    return json.loads(result_file.read_text())


def job(variant, spec, suffix="g5"):
    key, filename, preset, codec, fps = spec
    if variant == "baseline" and key == "long" and suffix == "g5":
        result = json.loads((EVIDENCE / "baseline-standard-120-2.json").read_text())
        assert result["job"]["state"] == "done" and result["sha256"]
        return compact_job(result)
    repo = ROOT / "baseline" if variant == "baseline" else ROOT / "variants" / variant
    return compact_job(
        run(
            "job-profile.py",
            f"{variant}-{key}-{suffix}",
            [
                "--repo",
                repo,
                "--source",
                ROOT / filename,
                "--preset",
                preset,
                "--codec",
                codec,
                "--fps",
                fps,
                "--cleanup",
            ],
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    provenance = prepare()
    if args.prepare:
        print("Prepared immutable source snapshots", flush=True)
        return
    summary = {"variants": provenance, "probes": {}, "g5": {}, "performance": {}}
    summary_path = EVIDENCE / "speed-cycle-summary.json"

    def save():
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    try:
        # Fast middle-part probes reject pixel-changing experiments before long jobs.
        for name in ("baseline", "warm", "c1-gpu", "trim-context", "cuda-streams"):
            repo = ROOT / "baseline" if name == "baseline" else ROOT / "variants" / name
            summary["probes"][name] = [
                run("optimization-probe.py", f"{name}-probe-{i}", ["--repo", repo])
                for i in range(1, 4)
            ]
            save()
        reference = summary["probes"]["baseline"][0]["part_1"]["sha256"]
        for name, rows in summary["probes"].items():
            summary["probes"][name] = dict(
                runs=rows, identical=all(r["part_1"]["sha256"] == reference for r in rows)
            )
        assert summary["probes"]["warm"]["identical"], "Warm worker failed the early pixel gate"
        assert summary["probes"]["baseline"]["identical"], "Baseline probe is not reproducible"
        save()
        candidates = [
            name
            for name in ("c1-gpu", "trim-context", "cuda-streams")
            if summary["probes"][name]["identical"]
        ]
        specs = [
            ("land-std-h264-2x", "landscape-30.mp4", "standard", "h264", "2x"),
            ("land-std-hevc-off", "landscape-30.mp4", "standard", "hevc", "off"),
            ("port-std-h264-off", "portrait-30.mp4", "standard", "h264", "off"),
            ("land-fast-hevc-off", "landscape-30.mp4", "fast", "hevc", "off"),
            ("port-fast-hevc-2x", "portrait-30.mp4", "fast", "hevc", "2x"),
            ("port-fast-h264-off", "portrait-30.mp4", "fast", "h264", "off"),
            ("cut", "hard-cut-6.mp4", "standard", "h264", "2x"),
            ("vfr", "vfr-6.mp4", "standard", "h264", "2x"),
            ("long", "synthetic-1080-120.mp4", "standard", "h264", "2x"),
        ]
        references = {}
        for spec in specs:
            references[spec[0]] = job("baseline", spec)
            summary["g5"].setdefault("baseline", {})[spec[0]] = references[spec[0]]
            save()
        passed = []
        for name in ("warm", *candidates):
            summary["g5"][name] = {}
            valid = True
            for spec in specs:
                result = job(name, spec)
                summary["g5"][name][spec[0]] = result
                if result["sha256"] != references[spec[0]]["sha256"]:
                    valid = False
                    summary["g5"][name]["rejected"] = spec[0]
                    save()
                    break
                save()
            if valid:
                passed.append(name)
            elif name == "warm":
                raise RuntimeError("Warm worker failed G5; no dependent speed change may ship")
        long = specs[-1]
        # Measure all three requested O9 experiments, including rejected pixel
        # changes. Their synthetic outputs never become production candidates.
        for name in ("baseline", "warm", "c1-gpu", "trim-context", "cuda-streams"):
            first = summary["g5"].get(name, {}).get("long")
            if not first or first.get("resumed"):
                first = job(name, long, "perf-1")
            rows = [first, job(name, long, "perf-2"), job(name, long, "perf-3")]
            identical = all(r["sha256"] == references["long"]["sha256"] for r in rows)
            if name in {"baseline", "warm"}:
                assert identical, f"Nonidentical performance repetition: {name}"
            summary["performance"][name] = dict(
                runs=rows,
                median_seconds=statistics.median(r["elapsed_seconds"] for r in rows),
                identical=identical,
            )
            save()
        warm_seconds = summary["performance"]["warm"]["median_seconds"]
        selected = []
        for name in ("c1-gpu", "trim-context", "cuda-streams"):
            if name in summary["performance"]:
                gain = 1 - summary["performance"][name]["median_seconds"] / warm_seconds
                summary["performance"][name]["gain_vs_warm"] = gain
                if gain > 0 and name in passed and summary["performance"][name]["identical"]:
                    selected.append(name)
        summary["selected"] = selected
        combined = ROOT / "variants/combined"
        shutil.copytree(ROOT / "variants/warm", combined, dirs_exist_ok=True)
        for name in selected:
            for relative, sha in provenance[name].items():
                if sha != provenance["warm"][relative]:
                    destination = combined / relative
                    # Both stream and context experiments affect runner.py; compose
                    # only selected, independently verified edits on the warm base.
                    if name == "cuda-streams" and destination.exists():
                        text = destination.read_text().replace(
                            "import logging\n", "import contextlib\nimport logging\n"
                        )
                        text = text.replace(
                            OLD_GUARD,
                            STREAM_GUARD,
                        )
                        destination.write_text(text)
                    else:
                        shutil.copy2(ROOT / "variants" / name / relative, destination)
        summary["combined_code"] = code_hashes(combined)
        equivalent = next(
            (name for name in passed if provenance[name] == summary["combined_code"]), None
        )
        if equivalent is not None:
            # An exact source copy has already completed these gates. Preserve
            # its run labels rather than claim another execution or repeat it.
            summary["g5"]["combined"] = summary["g5"][equivalent]
            summary["combined_g5_reused"] = equivalent
            save()
        elif selected:
            summary["g5"]["combined"] = {}
            for spec in specs:
                result = job("combined", spec)
                summary["g5"]["combined"][spec[0]] = result
                assert result["sha256"] == references[spec[0]]["sha256"], (
                    f"Combined G5 mismatch: {spec[0]}"
                )
                save()
        for busy in (False, True):
            for i in range(1, 4):
                options = [
                    "--repo",
                    combined,
                    "--scratch",
                    ROOT,
                    "--evidence",
                    EVIDENCE,
                    "--cleanup",
                ]
                if busy:
                    options.append("--busy")
                else:
                    options += ["--second-model", "basicvsrpp-denoise"]
                run(
                    "compare-profile.py", f"final-compare-{'busy' if busy else 'idle'}-{i}", options
                )
        summary["measurements_complete"] = True
        save()
    except BaseException as error:
        summary["error"] = repr(error)
        save()
        raise


if __name__ == "__main__":
    main()
