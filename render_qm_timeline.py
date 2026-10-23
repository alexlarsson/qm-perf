"""Build the grouped, self-contained boot timeline and its reference statistics."""

import json
import math
import re
import statistics
from pathlib import Path

SERVICES = [
    "mount-sysroot.service",
    "systemd-udevd.service",
    "systemd-journal-flush.service",
    "systemd-vconsole-setup.service",
    "NetworkManager.service",
    "systemd-logind.service",
    "systemd-hostnamed.service",
    "sshd-keygen@rsa.service",
    "sshd.service",
    "qm.service",
    "user-runtime-dir@0.service",
    "user@0.service",
]


def boot_phases(boot):
    """Use the system manager's default target, never the user manager's target."""
    offset = boot["offset"]
    records = boot["data"]["boot_logs"]
    phases = {e["name"]: e for e in records if e["source"] == "systemd-dbus"}
    targets = []
    for event in boot["journal"]:
        match = re.match(r"^systemd\[1\]: Queued start job for default target (\S+?)\.$", event["name"])
        if match and match[1] != "initrd.target":
            targets.append(match[1])
    target = targets[-1] if targets else "graphical.target"
    reached = next((e for e in boot["journal"] if e["name"].startswith(f"systemd[1]: Reached target {target} ")), None)
    unit = next((e for e in records if e["source"] == "saplot" and e["name"] == target), None)
    if reached and reached["activating"] / 1e6 > offset:
        target_time = reached["activating"] / 1e6 - offset
        target_source = "host systemd journal"
    elif unit:
        target_time = unit["activated"] / 1e6 - offset
        target_source = "systemd unit activation record"
    else:
        target_time, target_source = None, "not recorded"
    network = next((e for e in boot["journal"] if e["name"].startswith("systemd[1]: Reached target network-online.target ")), None)
    network_unit = next((e for e in records if e["source"] == "saplot" and e["name"] == "network-online.target"), None)
    if network and network["activating"] / 1e6 > offset:
        network_time = network["activating"] / 1e6 - offset
        network_source = "host systemd journal: network-online.target"
    elif network_unit:
        network_time = network_unit["activated"] / 1e6 - offset
        network_source = "systemd unit activation: network-online.target"
    else:
        network_time, network_source = None, "not recorded"
    kernel_end = phases["Kernel"]["activated"] / 1e6 - offset
    initrd_end = phases["InitRD"]["activated"] / 1e6 - offset
    observed_end = max(e["activating"] for e in boot["journal"]) / 1e6 - offset
    assert 0 <= kernel_end <= initrd_end <= network_time <= target_time <= observed_end
    return {"kernel_end": kernel_end, "initrd_end": initrd_end,
            "network_online": network_time, "network_source": network_source,
            "target_reached": target_time, "observed_end": observed_end,
            "target": target, "target_source": target_source}


def service_intervals(boot, unit):
    """Retain attempts and reconcile buffered/synthetic journal timestamps."""
    offset = boot["offset"]
    pending, attempts = None, []
    for event in boot["journal"]:
        name = event["name"]
        timestamp = event["activating"] / 1e6 - offset
        if re.match(rf"^systemd\[1\]: Starting {re.escape(unit)}(?: - |\.\.\.)", name):
            pending = timestamp
        elif re.match(rf"^systemd\[1\]: (Started|Finished) {re.escape(unit)}(?: - |\.)", name):
            if pending is not None:
                attempts.append({"start": pending, "end": timestamp, "status": "started", "source": "journal start/completion"})
                pending = None
        elif name.startswith(f"systemd[1]: {unit}: start operation timed out.") or re.match(rf"^systemd\[1\]: Failed to start {re.escape(unit)}(?: - |\.)", name):
            if pending is not None:
                attempts.append({"start": pending, "end": timestamp, "status": "failed", "source": "journal start/timeout or failure"})
                pending = None
    record = next((e for e in boot["data"]["boot_logs"] if e["source"] == "saplot" and e["name"] == unit), None)
    qm_failure = unit == "qm.service" and any(a["status"] == "failed" for a in attempts)
    if record and record["time"] > 0 and not qm_failure:
        start = record["activating"] / 1e6 - offset
        span = {"start": start, "end": start + record["time"] / 1e6,
                "status": "started", "source": "unit activating + startup duration"}
        closest = min(range(len(attempts)), key=lambda i: abs(attempts[i]["start"] - start), default=None)
        if closest is not None and (abs(attempts[closest]["start"] - start) < 0.2 or len(attempts) == 1):
            # A failed hostnamed activation is a failure even if the unit span
            # has a positive duration. QM's failed spans were excluded above.
            span["status"] = attempts[closest]["status"]
            attempts[closest] = span
        else:
            attempts.append(span)
    return sorted((a for a in attempts if a["start"] >= 0 and a["end"] >= a["start"]), key=lambda a: a["start"])


def auxiliary_intervals(boot):
    journal, offset = boot["journal"], boot["offset"]
    result = {}
    ptp = next((e for e in journal if "s32-dwmac " in e["name"] and "end0: registered PTP clock" in e["name"]), None)
    link = next((e for e in journal if "s32-dwmac " in e["name"] and "end0: configuring for fixed/rgmii-id" in e["name"]), None)
    if ptp and link:
        result["NIC bring-up"] = [{"start": ptp["activating"] / 1e6 - offset,
            "end": link["activating"] / 1e6 - offset, "status": "observed", "source": "driver milestone messages"}]
    network_patterns = [
        ("Bridge observed", r"manager: \(podman0\): new Bridge device"),
        ("Bridge activated", r"device \(podman0\): Activation: successful"),
        ("Veth bridge port", r"^kernel: podman0: port \d+\(veth\d+\) entered blocking state"),
        ("Veth observed", r"manager: \(veth\d+\): new Veth device"),
        ("Veth carrier connected", r"device \(veth\d+\): carrier: link connected"),
        ("Bridge carrier connected", r"device \(podman0\): carrier: link connected"),
        ("Veth forwarding", r"^kernel: podman0: port \d+\(veth\d+\) entered forwarding state"),
    ]
    starts = [i for i, e in enumerate(journal) if e["name"] == "systemd[1]: Starting qm.service..."]
    network_spans = []
    for attempt, start_index in enumerate(starts, 1):
        end_index = starts[attempt] if attempt < len(starts) else len(journal)
        entries = journal[start_index:end_index]
        initialized = next((i for i, e in enumerate(entries) if re.match(r"^podman\[\d+\]:.* container init ", e["name"])), None)
        setup_entries = entries[:initialized] if initialized is not None else entries
        milestones = []
        for label, pattern in network_patterns:
            entry = next((e for e in setup_entries if re.search(pattern, e["name"])), None)
            if entry:
                milestones.append({"label": label, "time": entry["activating"] / 1e6 - offset,
                                   "message": entry["name"]})
        if milestones:
            milestones.sort(key=lambda m: m["time"])
            network_spans.append({"start": milestones[0]["time"], "end": milestones[-1]["time"],
                "status": "observed", "source": "first to last observed bridge/veth setup milestone",
                "qm_attempt": attempt, "milestones": milestones,
                "note": "These messages bracket visible interface setup, not every Podman networking operation. " +
                        ("A container init event follows in this attempt." if initialized is not None else "No container init event is recorded for this attempt; setup completion is unconfirmed.")})
    result["Podman network setup"] = network_spans
    accepted = next((e for e in journal if "Accepted publickey" in e["name"]), None)
    if accepted:
        pid = re.match(r"sshd-session\[(\d+)\]", accepted["name"])[1]
        pam = next((e for e in journal if e["name"].startswith(f"sshd-session[{pid}]: pam_unix(sshd:session): session opened")), None)
        if pam:
            result["First SSH session"] = [{"start": accepted["activating"] / 1e6 - offset,
                "end": pam["activating"] / 1e6 - offset, "status": "observed",
                "source": f"accepted key to PAM session, sshd PID {pid}", "pid": pid}]
    return result


def summarize_spans(spans):
    starts = [a["start"] for a in spans]
    durations = [a["end"] - a["start"] for a in spans]
    start, duration = statistics.mean(starts), statistics.mean(durations)
    summary = {"start": start, "end": start + duration, "duration": duration,
            "samples": len(spans), "start_min": min(starts), "start_max": max(starts),
            "duration_min": min(durations), "duration_max": max(durations),
            "status": "average", "source": "arithmetic mean of first observed successful interval per included boot"}
    milestone_labels = dict.fromkeys(m["label"] for span in spans for m in span.get("milestones", []))
    if milestone_labels:
        summary["milestones"] = []
        for label in milestone_labels:
            values = [m["time"] for span in spans for m in span.get("milestones", []) if m["label"] == label]
            summary["milestones"].append({"label": label, "time": statistics.mean(values), "samples": len(values)})
        summary["milestones"].sort(key=lambda m: m["time"])
        summary["note"] = "Mean observed bridge/veth milestones; this does not measure every Podman networking operation."
    return summary


def seat_announcements(boot):
    markers = []
    for event in boot["journal"]:
        match = re.match(r"^systemd-logind\[(\d+)\]: New seat (\S+)\.$", event["name"])
        if match:
            markers.append({"time": event["activating"] / 1e6 - boot["offset"], "seat": match[2],
                "title": "Seat announced: " + match[2], "source": event["name"],
                "tokens": ["systemd-logind[" + match[1] + "]", "New seat " + match[2]]})
    return markers


def session_announcements(boot):
    markers = []
    for event in boot["journal"]:
        match = re.match(r"^systemd-logind\[(\d+)\]: New session (\S+) of user (.+)\.$", event["name"])
        if match:
            markers.append({"time": event["activating"] / 1e6 - boot["offset"],
                "kind": "session", "session": match[2], "user": match[3],
                "title": f"Session announced: {match[2]} (user {match[3]})", "source": event["name"],
                "tokens": ["New session " + match[2] + " of user " + match[3]]})
    return markers


def build_model(boots, events, by_boot):
    tracked = SERVICES + ["NIC bring-up", "Podman network setup", "First SSH session"]
    spans, phases, seats, sessions = {}, {}, {}, {}
    for key, boot in boots.items():
        phases[key] = boot_phases(boot)
        spans[key] = {unit: service_intervals(boot, unit) for unit in SERVICES}
        spans[key].update(auxiliary_intervals(boot))
        seats[key] = seat_announcements(boot)
        sessions[key] = session_announcements(boot)
    clean_keys = sorted(set(boots) - set(by_boot))
    assert clean_keys
    reference_services = {}
    for unit in tracked:
        first = [spans[key][unit][0] for key in clean_keys if spans[key].get(unit) and spans[key][unit][0]["status"] != "failed"]
        if first:
            reference_services[unit] = [summarize_spans(first)]
    mean_phase = {field: statistics.mean(phases[key][field] for key in clean_keys)
                  for field in ["kernel_end", "initrd_end", "network_online", "target_reached", "observed_end"]}
    phase_durations = {
        "kernel": mean_phase["kernel_end"],
        "initrd": mean_phase["initrd_end"] - mean_phase["kernel_end"],
        "startup": mean_phase["target_reached"] - mean_phase["initrd_end"],
        "startup_before_network_online": mean_phase["network_online"] - mean_phase["initrd_end"],
        "network_online_to_default": mean_phase["target_reached"] - mean_phase["network_online"],
        "observed_after_target": mean_phase["observed_end"] - mean_phase["target_reached"],
    }
    reference_seats = []
    for seat in sorted({m["seat"] for key in clean_keys for m in seats[key]}):
        # Average matching first announcements; later announcements remain
        # individual points on actual boot rows rather than being conflated.
        values = [next(m["time"] for m in seats[key] if m["seat"] == seat)
                  for key in clean_keys if any(m["seat"] == seat for m in seats[key])]
        reference_seats.append({"time": statistics.mean(values), "seat": seat,
            "title": "Mean first seat announcement: " + seat, "source": "mean first matching seat announcement per included boot",
            "stats": {"samples": len(values), "time_min": min(values), "time_max": max(values)}})
    first_sessions = [sessions[key][0]["time"] for key in clean_keys if sessions[key]]
    reference_sessions = [{"time": statistics.mean(first_sessions), "kind": "session", "session": "first",
        "title": "Mean first session announcement", "source": "mean first logind session announcement per included boot",
        "note": "Only the first session announcement in each boot contributes. Later session IDs are not matched across boots.",
        "stats": {"samples": len(first_sessions), "time_min": min(first_sessions), "time_max": max(first_sessions)}}] if first_sessions else []
    reference = {"key": "reference", "label": "Average reference", "reference": True,
        "sample_count": len(clean_keys), "phases": {**mean_phase, "target": "graphical.target", "target_source": "mean host target reach time", "network_source": "mean host network-online.target reach time"},
        "services": reference_services, "seat_announcements": reference_seats, "session_announcements": reference_sessions, "events": [], "logs": []}
    rows = [reference]
    for key, subset in sorted(by_boot.items()):
        boot = boots[key]
        # Each boot's journal is embedded once. Popups select exact intervals
        # from it at interaction time rather than duplicating long excerpts.
        rows.append({"key": f"{key[0]}/{key[1]}", "label": f"Run {key[0]} · boot {key[1]}",
            "run": key[0], "boot": key[1], "reference": False,
            "phases": phases[key], "services": spans[key], "seat_announcements": seats[key], "session_announcements": sessions[key], "events": subset,
            "logs": [{"t": e["activating"] / 1e6 - boot["offset"], "message": e["name"]} for e in boot["journal"]]})
    max_time = max([row["phases"]["observed_end"] for row in rows] + [e["end_kernel_s"] or e["start_kernel_s"] for e in events])
    return {"rows": rows, "tracked": tracked, "axis_max": math.ceil(max_time / 10) * 10,
            "reference": {"boot_count": len(clean_keys), "excluded_count": len(by_boot),
                "selection": "All recorded boots with no detected observation in the stall inventory, including moderate observations.",
                "included_boots": [f"{r}/{b}" for r, b in clean_keys],
                "phase_boundaries": mean_phase, "phase_durations": phase_durations,
                "seat_announcements": reference_seats,
                "session_announcements": reference_sessions,
                "services": {unit: value[0] for unit, value in reference_services.items()}}}


def render_report(out, boots, events, by_boot):
    model = build_model(boots, events, by_boot)
    payload = json.dumps(model, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    template = Path(__file__).with_name("qm_timeline_template.html").read_text()
    assert template.count("@@MODEL@@") == 1
    (out / "stall-timeline.html").write_text(template.replace("@@MODEL@@", payload))
    (out / "timeline-reference.json").write_text(json.dumps(model["reference"], indent=2) + "\n")
    return model
