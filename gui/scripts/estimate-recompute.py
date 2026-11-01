"""Recompute recorded first estimates without changing recorded job actuals."""

import copy
import json
from datetime import datetime
from pathlib import Path

from videoenhancer.estimate.model import estimate_job, predict_finalization, predict_segment
from videoenhancer.estimate.startup import cold_parts
from videoenhancer.jobs.segments import plan_segments
from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule

WORK = Path(__file__).resolve().parents[3]
EVIDENCE = WORK / "evidence/VE-P1e-3d2b"
PREVIOUS = WORK / "evidence/VE-P1e-3d2"


def preview(first, profile):
    media, settings = first["media"], first["settings"]
    count = media["frame_count"]
    return dict(
        id="preview",
        state="queued",
        media=media,
        settings=settings,
        input=first["input"],
        estimated_output_bytes=first["estimated_output_bytes"],
        segments=plan_segments(
            media,
            [],
            predicted_seconds_per_frame=predict_segment(media, settings, count, profile) / count,
        ),
        machine_profile=profile,
        correction_factor=1,
    )


def main():
    profile = json.loads(
        (WORK / "repo/src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json").read_text()
    )
    points = json.loads((EVIDENCE / "curve-points.json").read_text())
    assert len(points) == 4 and points == profile["finalization"]["points"]
    rows = []
    for label, limit in (("G-10", 10), ("G-1440-attempt2", 15), ("G-Fast", 10)):
        recorded = json.loads((PREVIOUS / f"{label}-gate.json").read_text())
        first = json.loads((PREVIOUS / f"{label}-first-manifest.json").read_text())
        baseline = preview(first, first["machine_profile"])
        old_recomputed = estimate_job(baseline).seconds
        assert abs(old_recomputed - recorded["initial_estimate_seconds"]) < 1, (
            label,
            old_recomputed,
            recorded["initial_estimate_seconds"],
        )
        new = preview(first, profile)
        prediction = estimate_job(new).seconds
        actual = recorded["actual_processing_seconds"]
        row = dict(
            gate=label + " first estimate",
            old=recorded["initial_estimate_seconds"],
            old_recomputed=old_recomputed,
            new=prediction,
            actual=actual,
            error_percent=100 * (prediction / actual - 1),
            limit_percent=limit,
        )
        row["result"] = "PASS" if abs(row["error_percent"]) <= limit else "FAIL"
        assignments = cold_parts(first)
        row["parts"] = [
            dict(
                index=s["index"],
                startup_kind=s.get("stats", {}).get("startup_kind"),
                frames=s["end"] - s["start"],
                actual=s.get("actual_seconds"),
                old=predict_segment(
                    first["media"],
                    first["settings"],
                    s["end"] - s["start"],
                    first["machine_profile"],
                    cold=assignments[s["index"]],
                ),
                new=predict_segment(
                    first["media"],
                    first["settings"],
                    s["end"] - s["start"],
                    profile,
                    cold=assignments[s["index"]],
                ),
            )
            for s in recorded["job"]["segments"]
        ]
        rows.append(row)
        if label == "G-10":
            added = datetime.fromisoformat(recorded["added_at"])
            schedule = Schedule(recorded["schedule"])
            plan = build_plan([new], schedule, added, days=2)
            finish = datetime.fromisoformat(plan["jobs"][0]["completion"])
            seconds = (finish - added).total_seconds()
            old_finish = (
                datetime.fromisoformat(recorded["initial_finish_at"]) - added
            ).total_seconds()
            actual_elapsed = recorded["elapsed_seconds"]
            error = 100 * (seconds / actual_elapsed - 1)
            rows.append(
                dict(
                    gate="G-10 first finish time",
                    old=old_finish,
                    new=seconds,
                    actual=actual_elapsed,
                    error_percent=error,
                    limit_percent=10,
                    result="PASS" if abs(error) <= 10 else "FAIL",
                )
            )
            final = copy.deepcopy(recorded["job"])
            for key in (
                "finalization_correction",
                "finalization_corrections",
                "finalization_scenario_factor",
            ):
                assert key not in profile
            prediction = predict_finalization(final, profile)
            actual = recorded["finalization"]["actual"]
            error = 100 * (prediction / actual - 1)
            rows.append(
                dict(
                    gate="G-10 finalization raw curve",
                    old=recorded["finalization"]["predicted"],
                    new=prediction,
                    actual=actual,
                    error_percent=error,
                    limit_percent=25,
                    result="PASS" if abs(error) <= 25 else "FAIL",
                    steps=final["timing"]["finalization_steps"],
                )
            )
    (EVIDENCE / "recomputed-gates.json").write_text(json.dumps(rows, indent=2))
    for row in rows:
        print(json.dumps({k: v for k, v in row.items() if k not in {"parts", "steps"}}))


if __name__ == "__main__":
    main()
