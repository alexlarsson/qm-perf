# QM startup comparison

A subsequent [network-focused analysis](network-report.md) localizes one slow
NetworkManager boot to NIC bring-up, distinguishes another local D-Bus timeout,
and records two additional soft-lockup reports found during that pass.

The six failures occur at different points in Podman startup, and five coincide
with delayed host user-session startup. Similar long delays affect other host
services in boots where QM starts successfully. This broadens the investigation
to shared host dependencies, scheduling, and kernel behavior; the logs do not
identify a single blocked function or prove that every delay has one cause.

## Dataset and timing

Boot numbers below are zero-based JSON array indexes, matching `query.jq`.
There are **299 recorded boots**, not 300: run 1 has 100, run 2 has 99, and
run 3 has 100. Run 2's `boot_samples_completed` is also 99. All six supplied
failure indexes are confirmed, giving 293 successful initial starts and six
timeouts (2.0%). The top-level `boot_samples_failed=0` field is not a reliable
indicator of whether QM timed out.

Durations below use differences in journal records' exported `activating`
timestamps, in microseconds. These are exported journal event times, not
measurements of how long an individual function executed. Clock corrections
and log delivery can affect them. Some records are out of timestamp order around
clock corrections. Absolute wall-clock dates in message text were not used to
compare boots. Podman's process-local `m=+...` values corroborate the long
create-to-init interval in run 3 boot 62.

Only the first QM start attempt counts toward the success statistics. In
particular, run 2 boot 83 fails initially and succeeds on a later automatic
restart. Failed `saplot` QM unit records have misleading duration/state fields,
so the analysis uses journal start/started/timeout messages instead.

**The 30-second startup timeout censors the stalled attempts. Its expiration
does not measure the natural duration of the stall and is not evidence of a
fixed-duration underlying operation.**

## Successful starts

| Run | Recorded boots | Initial timeouts | Successful QM start median | Successful maximum |
| --- | ---: | ---: | ---: | ---: |
| 1 | 100 | 2 | 3.861 s | 7.023 s |
| 2 | 99 | 2 | 3.865 s | 8.780 s |
| 3 | 100 | 2 | 3.845 s | 6.953 s |

Across all 293 successful initial starts, service startup takes 3.608–8.780 s,
median 3.863 s. The median `container create` to `container init` interval is
1.788 s; its maximum is 4.087 s. The failure population is clearly separated
from the normal startup variation in this dataset.

## Failure stages

All event offsets are seconds after the first `Starting qm.service...`.
An absent pre-timeout event is shown as a dash.

| Run / boot | Refresh before timeout | Create before timeout | What the logs establish |
| --- | ---: | ---: | --- |
| 1 / 15 | — | — | No Podman event before timeout; host session registration and user manager start are late. |
| 1 / 42 | — | — | No Podman event before timeout; first SSH acceptance and user-session startup are late. |
| 2 / 66 | 1.655 | 2.016 | Bridge appears, but veth setup and user-runtime directory completion are delayed until timeout handling. No init event appears. |
| 2 / 83 | — | — | No Podman event before timeout; late user-session startup. A subsequent automatic restart succeeds. |
| 3 / 26 | — | — | An overlay compatibility mount is cleaned up at +1.028 s, so some storage probing happened. User-runtime directory setup stalls; QM reports 32.359 s aggregate CPU use. |
| 3 / 62 | 4.116 | 4.794 | Bridge/veth setup completes around +5.4 s. Init occurs at +38.576 s and start at +38.602 s, during timeout handling. |

In run 3 boot 62, create-to-init takes **33.782 s**, with **33.780 s** measured
independently by subtracting Podman's process-local `m=+...` timestamps. Thus
there is a real long interval between Podman events, rather than just a long
gap before systemd records failure. Init-to-start then takes about 28 ms in
Podman's timestamps. The container starts after systemd has begun terminating
the service and is subsequently killed during stop handling; that later stop
timeout is a consequence to keep separate from the original startup problem.

The four pre-event failures do not establish that Podman never executed or
that it blocked specifically in refresh. Run 3 boot 26 has early storage-probe
evidence. Late refresh events appear after termination and have small
process-local `m=+...` values; they may come from a cleanup invocation. Without
the generated service's ExecStart/ExecStop/ExecStopPost and process tracking,
they should not be assigned to the original startup process.

## Host-side correlations

Five failures have late first user-manager startup: runs 1/15, 1/42, 2/66,
2/83, and 3/26. The exact point varies:

- Run 1 boot 15 accepts an SSH public key at +15.117 s, but the first SSH PAM
  session opens at +35.027 s. Further SSH attempts accumulate in between.
- Run 2 boot 66 starts `user-runtime-dir@0.service` at +2.239 s and finishes it
  at +34.818 s, a 32.579 s interval.
- Run 3 boot 26 starts that unit at +1.646 s and finishes at +32.303 s, a
  30.657 s interval.
- Run 3 boot 62 is the exception: the first SSH PAM session opens at +6.315 s,
  and additional sessions open while QM is stalled. This is not a complete
  machine freeze or a necessary dependency on the first root login.

These correlations do not establish which process is causing the delay or
whether they are waiting on one shared resource. They do make an isolated
container application startup problem a less satisfactory explanation.

Other boots provide useful comparisons without QM timeout censoring:

| Run / boot | QM initial start | Separate host delay |
| --- | ---: | --- |
| 1 / 1 | 3.807 s | NetworkManager takes 34.554 s to start. |
| 1 / 63 | 3.678 s | NetworkManager takes 34.166 s; systemd-hostnamed times out before QM starts. |
| 2 / 31 | 3.843 s | First user-runtime directory setup takes 31.663 s, after QM has started. |
| 2 / 35 | 3.727 s | `saplot` attributes 32.367 s to initrd `mount-sysroot.service`; journal output is buffered and does not independently locate that interval. |

The successful durations in this table are rounded from journal records;
other unit durations come from `saplot` where noted or the corresponding unit
records. QM's successful status alone does not mean the rest of the boot was
free of long delays.

## Other candidate explanations

- **Physical network/DHCP:** NetworkManager reports startup complete within
  0.154–0.540 s after QM starts in all six failures. This does not explain the
  later stall as a wait for initial DHCP completion; it does not rule out a
  later NIC or kernel networking problem. Podman network setup itself progresses to different points in
  the two post-create failures, so the logs do not isolate one network call.
- **Initial entropy seeding:** Every failed boot records `random: crng init
  done` approximately 7.5–7.6 s before QM starts. A late initial CRNG seed is
  therefore not supported by these records.
- **Overlay compatibility cleanup:** Similar cleanup messages occur in healthy
  boots; they are not themselves an error or a failure-specific signature.
  Their late appearance in some failures may be a consequence of cleanup.
- **CPU use:** Run 3 boot 26 reports 32.359 s for the service, versus 1.385 s in
  run 2 boot 66 and 4.867 s in run 3 boot 62 (including its later stop handling).
  The data do not support treating every case as the same idle wait. These are
  service-wide accounted totals, not a stack trace or proof of a specific
  spinning thread; a timekeeping problem could also affect accounting.
- **Time adjustment:** `chronyd: Forward time jump detected!` appears in two
  failed boots and nine boots where QM starts successfully. In the latter,
  it appears after QM startup, approximately +36.8–42.2 s. It is an interesting
  host-side symptom but neither necessary nor sufficient for QM failure.
  Smaller ordinary clock steps also occur; message ordering alone cannot
  establish that chronyd caused a stall.

The boot logs show PREEMPT_RT kernel `6.12.0-251.el10iv.aarch64`, a switch from
`arch_sys_counter` to `timer@4011c000`, and registrations of 32-bit scheduler
clock timers. These settings occur in healthy boots too. Given the broader
host symptoms, inspecting the platform timer and scheduling implementation is
a reasonable secondary lead, not a demonstrated diagnosis. Clock sources,
clock events, and `sched_clock()` serve distinct timekeeping and scheduling
roles, as described in the [kernel timekeeping documentation](https://docs.kernel.org/timers/timekeeping.html).
No timer rollover defect is inferred from the configured service timeout.

## Most useful next capture

1. Capture the generated `qm.service`, original `qm.container`, Podman/crun/
   conmon package versions, and `podman info --debug`. Establish every command
   and PID involved, including cleanup commands.
2. Enable Podman debug logging on the original service invocation. Trace child
   processes as well as the main process; the two post-create cases stall
   before the same event but at different visible network stages.
3. Arm a local collector before reboot, because SSH itself may be delayed.
   During a stall collect thread CPU usage, wait channels, kernel stacks and
   process trees for Podman, its children, `systemd-user-runtime-dir`, and PID 1.
   System-wide sampled stacks or a short trace covering scheduling and blocking
   syscalls would distinguish CPU execution, lock contention, I/O and IPC waits.
4. Preserve raw journal JSON with boot IDs, monotonic and realtime timestamps.
   The current export lacks the original fields needed to resolve time changes
   and delivery delays precisely. Log local process/uptime observations against
   an external collector clock if investigating timekeeping.

## Reproduction

From the workspace root:

```sh
python3 analyze_qm.py
```

This regenerates `qm-analysis/boots.csv`, `summary.json`, and
`failed-boot-timelines.txt`. The latter includes all nearby journal messages,
not just messages emitted by QM. `report.md` is the accompanying interpretation.
The separate September 24–25 debug logs are not included in the counts above.
