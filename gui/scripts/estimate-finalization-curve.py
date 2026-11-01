"""Independent synthetic Standard part replay through real finalization services."""

import copy
import json
import shutil
import statistics
import time
from pathlib import Path

import psutil

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.estimate.model import predict_segment
from videoenhancer.jobs.segments import plan_segments
from videoenhancer.jobs.store import JobStore, add_job, input_identity
from videoenhancer.media.mux import assemble
from videoenhancer.media.probe import probe
from videoenhancer.pipeline.inline_quality import aggregate_quality
from videoenhancer.schedule.controller import FinalizationTimer, ProcessExecutor, SystemClock


def run(home, save, evidence):
    executor = ProcessExecutor(SystemClock(), reuse=True)
    try:
        _run(home, save, evidence, executor)
    finally:
        executor.close()


def _run(home, save, evidence, executor):
    source = home / "independent-source.mp4"
    proc.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=720x1280:rate=30:duration=60",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=523:sample_rate=48000:duration=60",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-b:v",
            "1M",
            "-threads",
            "2",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    store = JobStore(home)
    template = add_job(
        source,
        dict(preset="standard", short_side=1080, fps="2x", codec="hevc", backend="cuda"),
        home=home,
    )
    # Render every distinct production-planned part length, including tails.
    per_frame = (
        predict_segment(template["media"], template["settings"], 300, template["machine_profile"])
        / 300
    )
    templates = {}
    fixtures = evidence / "curve-fixtures.json"
    if fixtures.exists():
        for length, record in json.loads(fixtures.read_text()).items():
            path = Path(record["path"]).resolve(strict=True)
            assert path.is_relative_to(home.parents[1]) and path.stat().st_size == record["bytes"]
            templates[int(length)] = (path, record["stats"])

    prime_length = plan_segments(template["media"], [], predicted_seconds_per_frame=per_frame)[0][
        "end"
    ]
    prime_path = store.job_dir(template["id"]) / "resident-prime.mp4"
    prime = executor.run(
        template, dict(index=0, start=0, end=prime_length), prime_path, lambda: False, batch_size=2
    )
    assert prime.status == "done" and prime.stats and not prime.stats.get("spilled"), prime
    resident = psutil.Process(prime.stats["memory_samples"][-1]["pid"])
    resident_created = resident.create_time()
    save(
        evidence / "curve-resident-prime.json",
        dict(pid=resident.pid, created=resident_created, stats=prime.stats),
    )
    templates.setdefault(prime_length, (prime_path, prime.stats))

    def rendered(length):
        if length not in templates:
            part = dict(index=0, start=0, end=length)
            path = store.job_dir(template["id"]) / f"independent-standard-part-{length}.mp4"
            result = executor.run(template, part, path, lambda: False, batch_size=2)
            assert result.status == "done" and result.stats and not result.stats.get("spilled"), (
                result
            )
            templates[length] = (path, result.stats)
            save(
                evidence / f"curve-template-{length}.json",
                dict(part=part, stats=result.stats, bytes=path.stat().st_size),
            )
        return templates[length]

    records = evidence / "curve-runs.json"
    rows = json.loads(records.read_text()) if records.exists() else []
    points = []
    for minutes in (1, 10, 30, 120):
        completed = [row for row in rows if row["minutes"] == minutes]
        fields = (
            "output_frames",
            "output_bytes",
            "parts",
            "concat_seconds",
            "mux_seconds",
            "faststart_seconds",
            "checkpoint_validation_seconds",
            "validation_seconds",
            "aggregation_seconds",
        )
        if len(completed) == 3:
            points.append({key: statistics.median(row[key] for row in completed) for key in fields})
            save(evidence / "curve-points.json", points)
            continue
        duration = minutes * 60
        full_source = home / f"source-{minutes}.mp4"
        proc.run(
            [
                executable("ffmpeg"),
                "-v",
                "error",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(source),
                "-t",
                str(duration),
                "-c",
                "copy",
                str(full_source),
            ],
            check=True,
            capture_output=True,
        )
        media = probe(full_source, read_timeline=False).to_dict()
        media.update(cfr_fps="30", frame_count=duration * 30)
        segments = plan_segments(media, [], predicted_seconds_per_frame=per_frame)
        for segment in segments:
            rendered(segment["end"] - segment["start"])
        point_rows = completed[:]
        for repeat in range(3):
            if any(row["repeat"] == repeat for row in completed):
                continue
            job = copy.deepcopy(template)
            job.update(
                id=f"curve-{minutes}-{repeat}",
                state="running",
                input=input_identity(full_source),
                output=str(home / f"output-{minutes}-{repeat}.mp4"),
                media=media,
                cfr_map=list(range(duration * 30)),
                source_pts=[i / 30 for i in range(duration * 30)],
                scene_cuts=[],
                timing={"observations": []},
                segments=[],
            )
            folder = store.job_dir(job["id"])
            folder.mkdir(parents=True)
            for planned in segments:
                index, start, end = planned["index"], planned["start"], planned["end"]
                template_path, stats = rendered(end - start)
                target = folder / f"seg_{index:05d}.mp4"
                shutil.copyfile(template_path, target)
                shifted = copy.deepcopy(stats)
                quality = shifted["inline_quality"]
                for field, factor in (("source", 1), ("output", 2)):
                    partial = quality[field]
                    partial["first_index"] += start * factor
                    partial["last_index"] += start * factor
                    for joint in partial["joints"]:
                        joint["frame_index"] += start * factor
                shifted["clip_joints"] = [i + start for i in shifted.get("clip_joints", [])]
                shifted["output_bytes"] = target.stat().st_size
                job["segments"].append(
                    dict(
                        index=index,
                        start=start,
                        end=end,
                        state="done",
                        stats=shifted,
                    )
                )
            store.save(job)
            assert resident.is_running() and resident.create_time() == resident_created
            io_before = psutil.disk_io_counters()
            processes = {}
            for process in psutil.process_iter(["name"]):
                name = (process.info["name"] or "").lower()
                if name in {"videoenhancer.exe", "python.exe", "ffmpeg.exe", "msmpeng.exe"}:
                    processes[name] = processes.get(name, 0) + 1
            environment = dict(
                resident_worker_pid=resident.pid,
                resident_worker_created=resident_created,
                resident_worker_rss_bytes=resident.memory_info().rss,
                available_memory_bytes=psutil.virtual_memory().available,
                process_counts=processes,
                io_before=io_before._asdict() if io_before else None,
            )
            # Newly written distinct files remain in the OS cache, as at completion
            # of the synthetic processing replay; do not reuse assembled checkpoints.
            timer = FinalizationTimer(store, job["id"], SystemClock())
            began = time.perf_counter()
            timer.begin("assembling")
            output = assemble(job, folder, validation_started=timer.validation)
            steps = copy.deepcopy(job["timing"]["finalization_steps"])
            timer.end()
            identity = input_identity(output)
            timer.begin("aggregating")
            current = store.load(job["id"])
            current.setdefault("timing", {})["finalization_steps"] = steps
            aggregation = time.perf_counter()
            current["quality"] = aggregate_quality(current)
            current["detector"] = dict(
                raw_flag_count=sum(
                    s["stats"].get("raw_flag_count", 0) for s in current["segments"]
                ),
                final_flag_count=sum(
                    s["stats"].get("final_flag_count", 0) for s in current["segments"]
                ),
            )
            steps["quality_aggregation_seconds"] = time.perf_counter() - aggregation
            store.save(current)
            timer.end()
            current = store.load(job["id"])
            seconds = time.perf_counter() - began
            events = current["timing"]["events"]
            row = dict(
                minutes=minutes,
                repeat=repeat,
                output_frames=duration * 60,
                output_bytes=identity["size"],
                parts=len(job["segments"]),
                seconds=seconds,
                **steps,
                aggregation_seconds=next(
                    e["elapsed_seconds"] for e in events if e["step"] == "aggregating"
                ),
                assembling_seconds=next(
                    e["elapsed_seconds"] for e in events if e["step"] == "assembling"
                ),
                validating_seconds=next(
                    e["elapsed_seconds"] for e in events if e["step"] == "validating"
                ),
                manifest_bytes=(folder / "manifest.json").stat().st_size,
                cache_state="fresh distinct writes, resident part worker, no cache flush",
                audio=media.get("audio_streams"),
                events=events,
                environment=environment,
                io_after=psutil.disk_io_counters()._asdict(),
            )
            rows.append(row)
            point_rows.append(row)
            save(evidence / "curve-runs.json", rows)
            output.unlink()
            candidates = list(folder.glob("seg_*.mp4")) + [folder / "assembled.tmp.mp4"]
            save(
                evidence / f"curve-{minutes}-{repeat}-cleanup.json",
                [dict(path=str(p), bytes=p.stat().st_size) for p in candidates if p.exists()],
            )
            for candidate in candidates:
                assert candidate.resolve().is_relative_to(home.resolve())
                candidate.unlink(missing_ok=True)
            print(json.dumps(row), flush=True)
        fields = (
            "output_frames",
            "output_bytes",
            "parts",
            "concat_seconds",
            "mux_seconds",
            "faststart_seconds",
            "checkpoint_validation_seconds",
            "validation_seconds",
            "aggregation_seconds",
        )
        points.append({key: statistics.median(row[key] for row in point_rows) for key in fields})
        save(evidence / "curve-points.json", points)
        save(
            evidence / f"curve-source-{minutes}-cleanup.json",
            dict(path=str(full_source), bytes=full_source.stat().st_size),
        )
        full_source.unlink()
    assert len(rows) == 12 and len(points) == 4
