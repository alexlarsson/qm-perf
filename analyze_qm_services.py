#!/usr/bin/env python3
"""Summarize per-service activation durations across the recorded boots.

Uses saplot unit timing rather than journal inter-message intervals. A review
candidate exceeds both three times its service median and median + 1 second.
These cutoffs select conspicuous deviations; they are not a statistical test.
QM records on timeout boots are excluded from the aggregate statistics because
their exported spans can include restart/failure state rather than initial
successful activation. The raw CSV retains them and labels the exclusion.
"""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def main():
    groups = defaultdict(list)
    raw = []
    for run in (1, 2, 3):
        path = Path(f"qm-run-{run}.json")
        for index, boot in enumerate(json.loads(path.read_text())[0]["boot_time"]):
            journal = [event for event in boot["boot_logs"] if event["source"] == "journalctl"]
            qm_failed = any("qm.service: start operation timed out." in event["name"] for event in journal)
            for event in boot["boot_logs"]:
                name = event["name"]
                if event["source"] != "saplot" or not name.endswith(".service"):
                    continue
                failure = any(e["name"] == f"systemd[1]: Failed to start {name}." or e["name"].startswith(f"systemd[1]: Failed to start {name} - ") for e in journal)
                row = {
                    "service": name,
                    "file": path.name,
                    "boot_index": index,
                    "duration_s": event["time"] / 1e6,
                    "activating_s": event["activating"] / 1e6,
                    "activated_s": event["activated"] / 1e6,
                    "endpoint_difference_s": (event["activated"] - event["activating"]) / 1e6,
                    "qm_timeout": qm_failed,
                    "unit_start_failure_in_journal": failure,
                    "excluded_from_summary": name == "qm.service" and qm_failed,
                }
                raw.append(row)
                if not row["excluded_from_summary"]:
                    groups[name].append(row)
    summaries = []
    candidates = []
    for name, observations in groups.items():
        values = sorted(row["duration_s"] for row in observations)
        median = statistics.median(values)
        worst = max(observations, key=lambda row: row["duration_s"])
        outliers = [row for row in observations if row["duration_s"] > median * 3 and row["duration_s"] > median + 1]
        for row in outliers:
            candidates.append({**row, "service_median_s": median, "excess_over_median_s": row["duration_s"] - median})
        summaries.append({
            "service": name,
            "samples": len(values),
            "median_s": median,
            "min_s": min(values),
            "max_s": worst["duration_s"],
            "worst_file": worst["file"],
            "worst_boot_index": worst["boot_index"],
            "review_candidate_count": len(outliers),
            "review_candidate_boots": "; ".join(f"{row['file']}:{row['boot_index']} ({row['duration_s']:.6f}s)" for row in outliers),
            "start_failure_boot_count": sum(row["unit_start_failure_in_journal"] for row in observations),
        })
    summaries.sort(key=lambda row: row["max_s"] - row["median_s"], reverse=True)
    candidates.sort(key=lambda row: row["excess_over_median_s"], reverse=True)
    out = Path("qm-analysis")
    out.mkdir(exist_ok=True)
    write_csv(out / "service-starts.csv", raw)
    write_csv(out / "service-summary.csv", summaries)
    write_csv(out / "service-outliers.csv", candidates)
    print(f"{len(summaries)} services, {len(raw)} unit records; {len(candidates)} review candidates")
    for row in summaries:
        if row["review_candidate_count"]:
            print(row["service"], f"median={row['median_s']:.6f}s max={row['max_s']:.6f}s", row["review_candidate_boots"])


if __name__ == "__main__":
    main()
