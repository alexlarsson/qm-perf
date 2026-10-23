#!/usr/bin/env python3
"""Network-focused comparison. Run from the directory containing qm-run-*.json.

Offsets and durations use exported activating microseconds. Per-PID SSH pairs
prevent unrelated connections from being mistaken for authentication timing.
Events for initial Podman network setup stop at the next QM start attempt.
"""

import csv
import json
import re
from pathlib import Path

from analyze_qm import START, TIMEOUT, describe, first


def analyze(path, index, boot):
    events = [e for e in boot["boot_logs"] if e["source"] == "journalctl"]
    starts = [i for i, e in enumerate(events) if e["name"] == START]
    origin = events[starts[0]]["activating"]
    attempt = events[: starts[1]] if len(starts) > 1 else events

    def find(pattern, subset=None):
        return first(events if subset is None else subset, lambda n: re.search(pattern, n))

    def elapsed(a, b):
        return (b["activating"] - a["activating"]) / 1e6 if a and b else None

    def at(pattern, subset=None):
        event = find(pattern, subset)
        return (event["activating"] - origin) / 1e6 if event else None

    def duration(a, b):
        return elapsed(find(a), find(b))

    accepted = [e for e in events if "Accepted publickey" in e["name"]]
    ssh_pairs = []
    for event in accepted:
        pid = re.match(r"sshd-session\[(\d+)\]", event["name"])[1]
        pam = find(rf"^sshd-session\[{pid}\]: pam_unix\(sshd:session\): session opened")
        ssh_pairs.append({"pid": int(pid), "accepted_s": (event["activating"] - origin) / 1e6, "accepted_to_pam_s": elapsed(event, pam)})
    row = {
        "file": path.name,
        "boot_index": index,
        "qm_timeout": bool(find(re.escape(TIMEOUT), attempt)),
        "nm_start_duration_s": duration(r"^systemd\[1\]: Starting NetworkManager.service", r"^systemd\[1\]: Started NetworkManager.service"),
        "hostnamed_start_duration_s": duration(r"^systemd\[1\]: Starting systemd-hostnamed.service", r"^systemd\[1\]: Started systemd-hostnamed.service"),
        "ptp_to_fixed_link_s": duration(r"s32-dwmac .* end0: registered PTP clock", r"s32-dwmac .* end0: configuring for fixed/rgmii-id"),
        "fixed_link_to_link_up_s": duration(r"s32-dwmac .* end0: configuring for fixed/rgmii-id", r"s32-dwmac .* end0: Link is Up"),
        "physical_link_up_s": at(r"s32-dwmac .* end0: Link is Up"),
        "dhcp_to_offer_acd_s": duration(r"dhcp4 \(end0\): activation: beginning transaction", r"dhcp4 \(end0\): state changed new lease,.*acd pending"),
        "dhcp_to_lease_s": duration(r"dhcp4 \(end0\): activation: beginning transaction", r"dhcp4 \(end0\): state changed new lease, address=[0-9.]+$"),
        "dhcp_final_lease_s": at(r"dhcp4 \(end0\): state changed new lease, address=[0-9.]+$"),
        "physical_network_activated_s": at(r"device \(end0\): Activation: successful"),
        "nm_startup_complete_s": at(r"manager: startup complete"),
        "network_online_target_s": at(r"Reached target network-online.target"),
        "podman_create_s": at(r"^podman\[.* container create ", attempt),
        "bridge_seen_s": at(r"manager: \(podman0\): new Bridge device", attempt),
        "bridge_activated_s": at(r"device \(podman0\): Activation: successful", attempt),
        "veth_seen_s": at(r"manager: \(veth0\): new Veth device", attempt),
        "veth_forwarding_s": at(r"podman0: port 1\(veth0\) entered forwarding state", attempt),
        "veth_carrier_s": at(r"device \(veth0\): carrier: link connected", attempt),
        "container_init_s": at(r"^podman\[.* container init ", attempt),
        "sshd_started_s": at(r"^systemd\[1\]: Started sshd.service"),
        "first_ssh_accepted_s": ssh_pairs[0]["accepted_s"] if ssh_pairs else None,
        "first_ssh_accepted_to_pam_s": ssh_pairs[0]["accepted_to_pam_s"] if ssh_pairs else None,
        "max_ssh_accepted_to_pam_s": max((pair["accepted_to_pam_s"] for pair in ssh_pairs if pair["accepted_to_pam_s"] is not None), default=None),
        "ntp_source_selected_s": at(r"^chronyd\[.*Selected source"),
        "soft_lockup": bool(find(r"BUG: soft lockup")),
        "hostnamed_proxy_timeout": bool(find(r"hostnamed not used as proxy creation failed")),
        "nic_link_down": bool(find(r"s32-dwmac .*Link is Down|device \(end0\): carrier: link disconnected")),
        "nm_warning_error": bool(find(r"^NetworkManager\[.*<(warn|error)>")),
        "nic_dma_tx_error": bool(find(r"NETDEV WATCHDOG|s32-dwmac .*([Ee]rror|[Ff]ailed|[Tt]imed out)|DMA.*([Ee]rror|[Ff]ailed)")),
    }
    nic_lines = [e["name"] for e in events if e["name"].startswith("kernel: s32-dwmac ")]
    nm = [e for e in events if e["name"].startswith("NetworkManager[")]
    gaps = []
    for left, right in zip(nm, nm[1:]):
        gap = elapsed(left, right)
        if gap > 5:
            # Embedded NM realtime values offer a separate check of message gaps.
            clock_values = [re.search(r"\[(\d+\.\d+)\]", e["name"]) for e in (left, right)]
            clock_gap = float(clock_values[1][1]) - float(clock_values[0][1]) if all(clock_values) else None
            gaps.append({"export_gap_s": gap, "nm_realtime_gap_s": clock_gap, "from": left["name"], "to": right["name"]})
    return row, {"file": path.name, "boot_index": index, "ssh_pairs": ssh_pairs, "nm_gaps": gaps, "nic_messages": nic_lines}


def main():
    rows, details, selected_timelines = [], [], []
    for run in (1, 2, 3):
        path = Path(f"qm-run-{run}.json")
        document = json.loads(path.read_text())[0]
        for index, boot in enumerate(document["boot_time"]):
            row, detail = analyze(path, index, boot)
            rows.append(row)
            details.append(detail)
            if row["qm_timeout"] or row["nm_start_duration_s"] > 10 or row["soft_lockup"]:
                lines = [f"{path.name} boot {index}"]
                origin = next(e["activating"] for e in boot["boot_logs"] if e["name"] == START)
                for event in boot["boot_logs"]:
                    name = event["name"]
                    if event["source"] == "journalctl" and re.search(r"NetworkManager|sshd|s32-dwmac|hostnamed|chronyd|podman\[|qm.service|user-runtime-dir|New session|BUG: soft lockup|kernel: (?:Call trace|default_idle|cpuidle|do_idle|pc :|lr :)", name):
                        lines.append(f"{(event['activating'] - origin) / 1e6:10.6f}  {name}")
                selected_timelines.append("\n".join(lines))
    metrics = ["nm_start_duration_s", "ptp_to_fixed_link_s", "dhcp_to_offer_acd_s", "dhcp_to_lease_s", "first_ssh_accepted_to_pam_s"]
    summary = {"record_count": len(rows)}
    for label, subset in [("qm_success", [r for r in rows if not r["qm_timeout"]]), ("qm_timeout", [r for r in rows if r["qm_timeout"]])]:
        summary[label] = {metric: describe(r[metric] for r in subset) for metric in metrics}
    summary["failures"] = [r for r in rows if r["qm_timeout"]]
    summary["slow_nm"] = [r for r in rows if r["nm_start_duration_s"] > 10]
    summary["soft_lockups"] = [r for r in rows if r["soft_lockup"]]
    summary["nic_message_sequences_identical"] = all(d["nic_messages"] == details[0]["nic_messages"] for d in details)
    out = Path("qm-analysis")
    out.mkdir(exist_ok=True)
    with (out / "network-boots.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (out / "network-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "network-details.json").write_text(json.dumps(details, indent=2) + "\n")
    (out / "network-timelines.txt").write_text("\n\n".join(selected_timelines) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("failures", "slow_nm", "soft_lockups")}, indent=2))
    for row in summary["failures"] + summary["slow_nm"]:
        print(row["file"], row["boot_index"], "timeout:", row["qm_timeout"], "PTP/link:", row["ptp_to_fixed_link_s"], "DHCP:", row["dhcp_to_lease_s"], "SSH post-auth:", row["first_ssh_accepted_to_pam_s"])


if __name__ == "__main__":
    main()
