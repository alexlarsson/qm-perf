#!/usr/bin/env python3
"""Compare first qm.service starts; indexes match jq --arg boot N -f query.jq.

Run: python3 analyze_qm.py [qm-run-1.json qm-run-2.json qm-run-3.json]
Outputs CSV, summary JSON, and failure timelines in qm-analysis/.
Only journalctl records are used for event timing. The exported activating
field is in microseconds; wall-clock adjustments and journal delivery can
affect it. Failed saplot qm.service durations are deliberately not used.
"""

import csv
import json
import re
import statistics
import sys
from pathlib import Path


START = "systemd[1]: Starting qm.service..."
READY = "systemd[1]: Started qm.service."
FAILED = "systemd[1]: Failed to start qm.service."
TIMEOUT = "qm.service: start operation timed out."


def first(events, predicate):
    return next((event for event in events if predicate(event["name"])), None)


def event_match(kind):
    return lambda name: bool(re.match(r"podman\[\d+\]:.* " + kind, name))


def describe(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def analyze(path, index, boot):
    journal = [e for e in boot["boot_logs"] if e["source"] == "journalctl"]
    positions = [i for i, event in enumerate(journal) if event["name"] == START]
    if not positions:
        raise ValueError(f"{path}: boot {index}: no qm start")
    begin = positions[0]
    end = positions[1] if len(positions) > 1 else len(journal)
    attempt = journal[begin:end]
    origin = attempt[0]["activating"]
    timeout = first(attempt, lambda n: TIMEOUT in n)
    failure = first(attempt, lambda n: n == FAILED)
    ready = first(attempt, lambda n: n == READY)
    before_timeout = attempt[: attempt.index(timeout)] if timeout else attempt
    create = first(before_timeout, event_match("container create "))
    refresh = first(before_timeout, event_match("system refresh$"))
    init = first(attempt, event_match("container init "))
    if create:
        pid = re.match(r"podman\[(\d+)\]", create["name"])[1]
        init = first(attempt, lambda n: n.startswith(f"podman[{pid}]:") and " container init " in n)

    def relative(event):
        return (event["activating"] - origin) / 1e6 if event else None

    def at(predicate):
        return relative(first(journal, predicate))

    runtime_start = first(journal, lambda n: "Starting user-runtime-dir@0.service" in n)
    runtime_end = first(journal, lambda n: "Finished user-runtime-dir@0.service" in n)
    cpu = first(attempt, lambda n: "qm.service: Consumed " in n)
    cpu_match = re.search(r"Consumed ([\d.]+)s CPU", cpu["name"]) if cpu else None
    row = {
        "file": path.name,
        "boot_index": index,
        "date": boot["date"],
        "initial_outcome": "timeout" if timeout else "started" if ready else "failed_or_incomplete",
        "phase_at_timeout": ("after_create_before_init" if create else "before_first_event") if timeout else "",
        "qm_start_export_s": origin / 1e6,
        "initial_ready_s": relative(ready) if ready and not timeout and not failure else None,
        "timeout_s": relative(timeout),
        "failure_reported_s": relative(failure),
        "refresh_before_timeout_s": relative(refresh),
        "create_before_timeout_s": relative(create),
        "init_first_attempt_s": relative(init),
        "create_to_init_s": relative(init) - relative(create) if init and create else None,
        "first_ssh_accepted_s": at(lambda n: "Accepted publickey" in n),
        "first_logind_session_s": at(lambda n: "New session " in n),
        "first_ssh_pam_open_s": at(lambda n: "pam_unix(sshd:session): session opened" in n),
        "user_runtime_duration_s": relative(runtime_end) - relative(runtime_start) if runtime_start and runtime_end else None,
        "user_manager_start_s": at(lambda n: "Starting user@0.service" in n),
        "network_startup_complete_s": at(lambda n: "manager: startup complete" in n),
        "crng_ready_s": at(lambda n: "crng init done" in n),
        "first_forward_jump_s": at(lambda n: "Forward time jump detected!" in n),
        "reported_qm_cpu_s": float(cpu_match[1]) if cpu_match else None,
        "qm_start_count": len(positions),
    }
    timeline = [f"{path.name}, boot index {index}; times relative to first qm start"]
    if timeout:
        for event in journal:
            elapsed = relative(event)
            if -0.1 <= elapsed <= 80:
                timeline.append(f"{elapsed:10.6f}  {event['name']}")
    return row, "\n".join(timeline)


def main():
    paths = [Path(p) for p in sys.argv[1:]] or [Path(f"qm-run-{r}.json") for r in (1, 2, 3)]
    out = Path("qm-analysis")
    out.mkdir(exist_ok=True)
    rows, timelines, inputs = [], [], []
    for path in paths:
        document = json.loads(path.read_text())[0]
        inputs.append({"file": path.name, "boot_records": len(document["boot_time"]), "completed_metadata": document.get("boot_samples_completed")})
        for index, boot in enumerate(document["boot_time"]):
            row, timeline = analyze(path, index, boot)
            rows.append(row)
            if row["initial_outcome"] == "timeout":
                timelines.append(timeline)
    successes = [r for r in rows if r["initial_outcome"] == "started"]
    failures = [r for r in rows if r["initial_outcome"] == "timeout"]
    summary = {
        "inputs": inputs,
        "total_boot_records": len(rows),
        "successful_initial_starts": len(successes),
        "timed_out_initial_starts": len(failures),
        "successful_start_duration_s": describe(r["initial_ready_s"] for r in successes),
        "successful_create_to_init_s": describe(r["create_to_init_s"] for r in successes),
        "failures": failures,
        "successful_boots_with_forward_jump": [r for r in successes if r["first_forward_jump_s"] is not None],
        "successful_boots_with_late_qm_start": [r for r in successes if r["qm_start_export_s"] > 25],
        "successful_boots_with_slow_user_runtime": [r for r in successes if r["user_runtime_duration_s"] is not None and r["user_runtime_duration_s"] > 20],
    }
    with (out / "boots.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "failed-boot-timelines.txt").write_text("\n\n".join(timelines) + "\n")
    print(f"{len(rows)} boots: {len(successes)} successful first starts, {len(failures)} timeouts")
    print("Successful start duration (s):", summary["successful_start_duration_s"])
    print("Successful create-to-init (s):", summary["successful_create_to_init_s"])
    for row in failures:
        print(row["file"], row["boot_index"], row["phase_at_timeout"])


if __name__ == "__main__":
    main()
