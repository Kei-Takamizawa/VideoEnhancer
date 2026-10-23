"""Summarise raw spike samples without discarding failed or earlier runs."""

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "evidence/VE-P1e-3b/section13"


def latency(sample):
    value = sample.get("value", sample.get("result", {}))
    return value.get("latency_ms") if isinstance(value, dict) else None


def describe(values):
    valid = [v for v in values if v is not None]
    return {
        "n": len(valid),
        "median": statistics.median(valid) if valid else None,
        "worst": max(valid) if valid else None,
        "raw": values,
    }


def main():
    rows = []
    for path in sorted(ROOT.glob("bench-*-results.json")):
        result = json.loads(path.read_text())
        samples = result.get("playback_samples", [])
        start, end = result.get("start_properties", {}), result.get("end_properties", {})
        cpu = None
        if len(samples) > 1:
            cpu = (
                100
                * max(0, samples[-1]["cpu_seconds"] - samples[0]["cpu_seconds"])
                / (samples[-1]["at"] - samples[0]["at"])
            )
        if result["mode"] == "HTML5":
            drops = (
                end.get("quality", {}).get("dropped", 0)
                - start.get("quality", {}).get("dropped", 0)
                if samples
                else None
            )
        else:
            drops = (
                int(end["frame-drop-count"]) - int(start["frame-drop-count"]) if samples else None
            )
        decoder = []
        log = path.with_name(path.name.replace("-results.json", ".jsonl"))
        if log.exists():
            for line in log.read_text().splitlines():
                item = json.loads(line)
                if item.get("event") == "media-properties":
                    for prop in item["data"].get("properties", []):
                        if prop["name"] in ("kVideoDecoderName", "kIsPlatformVideoDecoder"):
                            marker = f"{prop['name']}={prop['value']}"
                            if marker not in decoder:
                                decoder.append(marker)
        rows.append(
            {
                "case": path.stem.removesuffix("-results"),
                "mode": result["mode"],
                "clip": result["clip"],
                "first_frame": describe([latency(v) for v in result.get("first_frame", [])]),
                "seek": describe([latency(v.get("sample", v)) for v in result.get("seeks", [])]),
                "gpu_median_mb": statistics.median(v["dedicated_bytes"] for v in samples) / 1e6
                if samples
                else None,
                "gpu_peak_mb": max((v["dedicated_bytes"] for v in samples), default=0) / 1e6
                if samples
                else None,
                "shared_peak_mb": max((v["shared_bytes"] for v in samples), default=0) / 1e6
                if samples
                else None,
                "cpu_one_core_percent": cpu,
                "dropped_60s": drops,
                "sample_count": len(samples),
                "wall_seconds": result.get("playback_wall_seconds"),
                "after_close_mb": [
                    v["dedicated_bytes"] / 1e6 for v in result.get("after_close", [])
                ],
                "hwdec": end.get("hwdec-current") if result["mode"] != "HTML5" else decoder,
                "ready_ms": result.get("ready_ms"),
                "failure": result.get("failure"),
                "unavailable": result.get("playback_unavailable"),
            }
        )
    (ROOT / "measurements-summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(
        json.dumps(
            [
                {
                    "case": r["case"],
                    "first_n": r["first_frame"]["n"],
                    "seek_n": r["seek"]["n"],
                    "samples": r["sample_count"],
                    "failure": r["failure"],
                }
                for r in rows
            ]
        )
    )


if __name__ == "__main__":
    main()
