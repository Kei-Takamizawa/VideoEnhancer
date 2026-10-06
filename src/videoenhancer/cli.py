"""English command-line interface for local video conversion jobs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ve", description="VideoEnhancer conversion engine")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", help="Inspect a video")
    probe.add_argument("input", type=Path)

    def add_video_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("input", type=Path)
        command.add_argument("-o", "--output", type=Path)
        command.add_argument(
            "--preset",
            choices=("passthrough", "resize", "p0-test", "fast", "standard"),
            default="standard",
        )
        command.add_argument(
            "--short-side", choices=("keep", "1080", "1440", "2160"), default="1080"
        )
        command.add_argument("--fps", choices=("off", "2x"), default="2x")
        command.add_argument("--codec", choices=("hevc", "h264", "av1"), default="hevc")
        command.add_argument("--backend", choices=("auto", "cpu", "cuda"), default="auto")
        command.add_argument("--batch-size", type=int, default=2, metavar="N")
        command.add_argument("--segment-seconds", type=float, default=180.0, metavar="SECONDS")
        command.add_argument("--keep-segments", action="store_true")
        command.add_argument("--lossless", action="store_true", help=argparse.SUPPRESS)

    add_video_options(commands.add_parser("add", help="Analyze and queue a video"))
    add_video_options(commands.add_parser("enhance", help="Queue and process this video now"))

    commands.add_parser("queue", help="Show queued jobs")
    move = commands.add_parser("move", help="Move a job to a queue position")
    move.add_argument("job")
    move.add_argument("position", type=int)
    for name in ("pause", "resume", "cancel"):
        command = commands.add_parser(name, help=f"{name.title()} a job")
        command.add_argument("job")
    plan = commands.add_parser("plan", help="Show the day-by-day work plan")
    plan.add_argument("--days", type=int, default=14)

    schedule = commands.add_parser("schedule", help="Manage operating hours")
    schedule_commands = schedule.add_subparsers(dest="schedule_command", required=True)
    schedule_commands.add_parser("show", help="Show operating hours")
    weekly = schedule_commands.add_parser("set-weekly", help="Replace weekly windows")
    weekly.add_argument("--window", action="append", default=[], metavar="DAYS@HH:MM-HH:MM")
    weekly.add_argument("--days", metavar="MON,TUE,...")
    weekly.add_argument("--start", metavar="HH:MM")
    weekly.add_argument("--end", metavar="HH:MM")
    exception = schedule_commands.add_parser("add-exception", help="Replace one date's windows")
    exception.add_argument("--date", required=True)
    exception.add_argument("--window", action="append", default=[], metavar="HH:MM-HH:MM|off")
    exception.add_argument("--off", action="store_true")
    remove = schedule_commands.add_parser("remove-exception", help="Remove a date exception")
    remove.add_argument("--date", required=True)
    schedule_commands.add_parser("enable", help="Enforce the saved schedule")
    schedule_commands.add_parser("disable", help="Allow processing at any time")
    override = schedule_commands.add_parser("override", help="Temporarily ignore the schedule")
    override.add_argument("--until", required=True, metavar="ISO|job-complete|off")

    run = commands.add_parser("run", help="Process the queue in the foreground")
    run.add_argument("--ignore-schedule", action="store_true")
    bench = commands.add_parser("bench", help="Measure local engine performance")
    bench.add_argument("--calibrate", action="store_true")
    bench.add_argument("--models", default=None, metavar="all|NAMES")
    bench.add_argument("--output-dir", type=Path)
    return parser


def _emit(value: Any, human: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, default=str))
    else:
        print(human)


def _duration(seconds: float) -> str:
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _progress(job: dict[str, Any]) -> float:
    segments = job.get("segments", [])
    total = sum(max(0, int(segment["end"]) - int(segment["start"])) for segment in segments)
    done = sum(
        int(segment["end"]) - int(segment["start"])
        for segment in segments
        if segment.get("state") == "done"
    )
    return 100 * done / total if total else 0.0


def _window_label(window: dict[str, str], date: str) -> str:
    start = datetime.fromisoformat(window["start"])
    end = datetime.fromisoformat(window["end"])
    end_text = (
        "24:00" if end.date().isoformat() != date and end.hour == 0 else end.strftime("%H:%M")
    )
    return f"{start:%H:%M}–{end_text}"


def format_plan(plan: dict[str, Any]) -> str:
    lines = ["Date        Windows                         Run    Job progress"]
    for entry in plan["days"]:
        day = datetime.fromisoformat(entry["date"])
        windows = ", ".join(_window_label(item, entry["date"]) for item in entry["windows"])
        jobs = []
        for progress in entry["jobs"]:
            text = (
                f"{str(progress['job_id'])[:8]}: {progress['start_percent']:.0f}% "
                f"→ {progress['end_percent']:.0f}%"
            )
            if progress.get("completion"):
                completion = datetime.fromisoformat(progress["completion"])
                text += f" (done ~{completion:%H:%M})"
            jobs.append(text)
        lines.append(
            f"{day:%a %m/%d}   {(windows or '—'):<31} "
            f"{entry['run_hours']:>4.1f}h  {', '.join(jobs) or '—'}"
        )
    return "\n".join(lines)


def _schedule_payload(home: Path) -> dict[str, Any]:
    path = home / "schedule.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": 1}


def _save_schedule(home: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from videoenhancer.schedule.windows import Schedule

    checked = Schedule.from_dict(payload).to_dict()
    target = home / "schedule.json"
    temporary = home / f"schedule.{uuid.uuid4().hex}.tmp"
    home.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(checked, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return checked


def _clock_pair(value: str) -> dict[str, str]:
    start, separator, end = value.partition("-")
    if not separator or not start or not end:
        raise ValueError(f"Invalid window {value!r}; use HH:MM-HH:MM")
    return {"start": start, "end": end}


def _schedule_command(args: argparse.Namespace, home: Path, as_json: bool) -> int:
    from videoenhancer.schedule.windows import Schedule

    payload = _schedule_payload(home)
    action = args.schedule_command
    if action == "show":
        schedule = Schedule.from_dict(payload)
        shown = schedule.to_dict()
        weekly = [
            f"{','.join(item['days'])}@{item['start']}-{item['end']}" for item in shown["weekly"]
        ]
        human = (
            f"Schedule: {'enabled' if shown['enabled'] else 'disabled'}\n"
            f"Weekly: {', '.join(weekly) or 'none'}\n"
            f"Exceptions: {len(shown['exceptions'])}\n"
            f"Override: {shown['override_until'] or 'none'}"
        )
        _emit(shown, human, as_json)
        return 0
    if action == "set-weekly":
        windows = []
        for item in args.window:
            days, separator, hours = item.partition("@")
            if not separator:
                raise ValueError("Weekly windows must use mon,tue@HH:MM-HH:MM")
            windows.append({"days": days.lower().split(","), **_clock_pair(hours)})
        if any(value is not None for value in (args.days, args.start, args.end)):
            if not all(value is not None for value in (args.days, args.start, args.end)):
                raise ValueError("Use --days, --start and --end together")
            windows.append(
                {"days": args.days.lower().split(","), "start": args.start, "end": args.end}
            )
        payload["weekly"] = windows
    elif action == "add-exception":
        datetime.fromisoformat(args.date)
        windows = (
            "off"
            if args.off or args.window == ["off"]
            else [_clock_pair(item) for item in args.window]
        )
        if args.off and args.window:
            raise ValueError("Use --off or --window off, not both with other windows")
        exceptions = [item for item in payload.get("exceptions", []) if item["date"] != args.date]
        exceptions.append({"date": args.date, "windows": windows})
        payload["exceptions"] = exceptions
    elif action == "remove-exception":
        payload["exceptions"] = [
            item for item in payload.get("exceptions", []) if item["date"] != args.date
        ]
    elif action == "enable":
        payload["enabled"] = True
    elif action == "disable":
        payload["enabled"] = False
    elif action == "override":
        if args.until not in {"off", "job-complete"}:
            datetime.fromisoformat(args.until)
        payload["override_until"] = None if args.until == "off" else args.until
    checked = _save_schedule(home, payload)
    _emit(checked, f"Schedule {action} saved.", as_json)
    return 0


def _jobs_plan(jobs: list[dict[str, Any]], home: Path, days: int = 14) -> dict[str, Any]:
    from videoenhancer.schedule.planner import build_plan
    from videoenhancer.schedule.windows import Schedule

    schedule = Schedule.from_file(home / "schedule.json")
    return build_plan(jobs, schedule, datetime.now(schedule.zone), days=days)


def _add(args: argparse.Namespace, home: Path, as_json: bool, run_now: bool) -> int:
    from videoenhancer.estimate import estimate_job
    from videoenhancer.jobs.store import JobStore, add_job
    from videoenhancer.media.decode import choose_backend

    if args.segment_seconds <= 0:
        raise ValueError("Segment target must be greater than zero seconds")
    backend = choose_backend(args.backend)
    settings = {
        "preset": args.preset,
        "short_side": "keep" if args.short_side == "keep" else int(args.short_side),
        "fps": args.fps,
        "codec": args.codec,
        "backend": backend,
        "keep_segments": args.keep_segments,
        "batch_size": min(4, max(1, args.batch_size)),
        "lossless": args.lossless,
    }
    manifest = add_job(
        args.input,
        settings,
        output=args.output,
        home=home,
        target_segment_seconds=args.segment_seconds,
    )
    estimate = estimate_job(manifest).to_dict()
    comparisons = {}
    for preset in ("fast", "standard"):
        if isinstance(manifest.get("settings"), dict):
            alternate = {**manifest, "settings": {**manifest["settings"], "preset": preset}}
            comparisons[preset] = estimate_job(alternate).to_dict()
        elif preset == "standard":
            comparisons[preset] = estimate
        else:
            comparisons[preset] = estimate
    plan = _jobs_plan([manifest], home)
    result: dict[str, Any] = {
        "job_id": manifest["id"],
        "output": manifest["output"],
        "segments": len(manifest["segments"]),
        "estimate": estimate,
        "preset_estimates": comparisons,
        "plan": plan,
    }
    if run_now:
        from videoenhancer.schedule.controller import run_queue

        run_queue(ignore_schedule=True, home=home, job_ids={manifest["id"]})
        finished = JobStore(home).load(manifest["id"])
        result["state"] = finished["state"]
        if finished["state"] != "done":
            raise RuntimeError(
                f"Job {manifest['id']} ended in state {finished['state']}; check its job log"
            )
        human = f"Enhanced video: {finished['result']}"
    else:
        human = (
            f"Added job {manifest['id']} ({len(manifest['segments'])} segments).\n"
            f"Estimated remaining time: {_duration(estimate['seconds'])}"
            f"{' (calibrated)' if estimate['calibrated'] else ' (uncalibrated)'}\n"
            f"Fast: {_duration(comparisons['fast']['seconds'])}; "
            f"Standard: {_duration(comparisons['standard']['seconds'])}\n"
            f"Output: {manifest['output']}\n{format_plan(plan)}"
        )
    _emit(result, human, as_json)
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in arguments
    arguments = [argument for argument in arguments if argument != "--json"]
    parser = _parser()
    args = parser.parse_args(arguments)
    from videoenhancer.config import get_home

    home = get_home()
    try:
        if args.command == "probe":
            from videoenhancer.media.probe import probe

            info = probe(args.input, count_frames=True)
            data = info.to_dict()
            human = (
                f"File: {data['path']}\n"
                f"Video: {data['display_width']}×{data['display_height']} "
                f"({data['width']}×{data['height']} coded, rotation {data['rotation']}°)\n"
                f"Codec: {data['codec']} {data['profile']}; {data['bit_depth']}-bit\n"
                f"Frame rate: {data['average_fps']} (target CFR {data['cfr_fps']}); "
                f"{'VFR' if data['is_vfr'] else 'CFR'}\n"
                f"Frames: {data['frame_count']}"
                f"{' estimated' if data['frame_count_estimated'] else ''}; "
                f"duration {_duration(data['duration'])}\n"
                f"Color: {data['color_matrix']}, {data['color_range']}; "
                f"audio streams: {len(data['audio_streams'])}"
            )
            _emit(data, human, as_json)
        elif args.command in {"add", "enhance"}:
            return _add(args, home, as_json, args.command == "enhance")
        elif args.command == "schedule":
            return _schedule_command(args, home, as_json)
        elif args.command == "bench":
            from videoenhancer.bench.runner import run_bench

            report = run_bench(args.calibrate, args.models, args.output_dir)
            target = args.output_dir or Path.cwd()
            _emit(
                report,
                f"Benchmark written to {target / 'bench_report.md'} "
                f"and {target / 'bench_report.json'}",
                as_json,
            )
        else:
            from videoenhancer.jobs.store import JobStore

            store = JobStore(home)
            if args.command == "queue":
                jobs = store.list_jobs()
                plan = _jobs_plan(jobs, home)
                completion = {item["job_id"]: item["completion"] for item in plan["jobs"]}
                summary = [
                    {
                        "id": job["id"],
                        "state": job["state"],
                        "progress_percent": _progress(job),
                        "eta": completion.get(job["id"]),
                        "output": job["output"],
                    }
                    for job in jobs
                ]
                lines = ["Job       State       Progress  ETA"]
                lines.extend(
                    f"{item['id'][:8]:<9} {item['state']:<11} {item['progress_percent']:>5.1f}%    "
                    f"{item['eta'] or 'unknown'}"
                    for item in summary
                )
                _emit(summary, "\n".join(lines) if jobs else "Queue is empty.", as_json)
            elif args.command == "move":
                store.move(args.job, args.position)
                _emit(
                    {"job_id": args.job, "position": args.position},
                    f"Moved job {args.job} to position {args.position}.",
                    as_json,
                )
            elif args.command in {"pause", "resume", "cancel"}:
                state = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[args.command]
                job = store.set_state(args.job, state)
                _emit(
                    {"job_id": job["id"], "state": state}, f"Job {job['id']} is {state}.", as_json
                )
            elif args.command == "plan":
                plan = _jobs_plan(store.list_jobs(), home, args.days)
                _emit(plan, format_plan(plan), as_json)
            elif args.command == "run":
                from videoenhancer.schedule.controller import run_queue

                candidates = {
                    job["id"] for job in store.list_jobs() if job["state"] in {"queued", "running"}
                }
                run_queue(ignore_schedule=args.ignore_schedule, home=home)
                outcomes = {
                    job["id"]: job["state"] for job in store.list_jobs() if job["id"] in candidates
                }
                _emit(outcomes, "Queue processing stopped.", as_json)
                return 0 if all(state == "done" for state in outcomes.values()) else 1
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, ImportError) as error:
        if as_json:
            print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
