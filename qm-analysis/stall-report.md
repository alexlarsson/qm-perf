# Boot timing and kernel-message sweep

## What this establishes

The affected operations span multiple boot phases. There is no single absolute
boot time or single newly starting host service common to all the observed
delays. The earliest large interval is in the initrd; some later intervals
begin after QM and the ordinary host daemons are already active. This is
consistent with a shared lower-level problem, but the logs do not prove that
every delay has one cause or that the entire machine stopped executing.

The full inventory contains 65 observations in 38 boots: 19 service-duration
outliers, two slow service shutdowns, six initial QM timeouts, 19 delayed SSH logins in 13 boots, four long
completed SSH session lifetimes in four boots, eleven
chronyd forward-jump reports, two soft-lockup reports, one NIC milestone gap,
and one minor hrtimer diagnostic. Multiple observations can describe the same
episode. Twenty-six boots have a long interval or watchdog/clock-jump signal;
the remainder have smaller startup variation or the microsecond diagnostic.
This is an inventory of candidates, not 65 confirmed physical CPU lockups.

## Time coordinate and uncertainty

Tables use **seconds from the reconstructed Linux kernel-start origin**:

```text
t = activating / 1,000,000 - metadata.cntvct_offset_us / 1,000,000
```

The offset is approximately 3–4 seconds and varies by boot. In all 299 records,
the CNTVCT and wall-clock offset metadata agree. CSV output also retains the
unadjusted exported coordinate for direct comparison with the JSON.
For example, the run 1 boot 81 watchdog appears at exported 60.266918 s;
subtracting that boot's 4.096802 s offset gives 56.170116 s.

An operation's start is **not the exact onset of a kernel stall**. The bar ends
at observed completion or timeout handling. QM intervals end at its configured
timeout, so they are censored observations. Watchdog and chronyd markers are
report times. Original raw journal monotonic/realtime fields and scheduling
traces are absent; a timekeeping fault could affect these reconstructed times.

Some journal entries have synthetic zero timestamps. Unit activation spans
were used to reconcile missing completion timestamps where possible. The
`activated` field can also be stale after service state changes; for example,
run 2 boot 31's runtime-directory duration and journal completion agree, but
its exported `activated` precedes `activating`. That interval is reconstructed
as `activating + time`, rather than using the stale endpoint.

## The principal startup-delay boots on one timeline

| Run / index | Observed interval(s), seconds since kernel start | Services and phase around the affected operation |
| --- | --- | --- |
| 2 / 35 | Root mount **1.128–33.495** | Initrd PID 1, `mount-sysroot`; root-system NetworkManager, sshd and QM have not started. |
| 1 / 63 | NetworkManager 11.255–45.422; hostnamed **11.765–45.101** | D-Bus, journald, udev and auditd already started; chronyd/logind start around this phase. NM explicitly waits for local hostname-service activation. |
| 1 / 1 | NetworkManager 11.196–45.750; NIC milestones **13.274–45.731** | NetworkManager is starting; hostnamed, logind, chronyd, D-Bus, journald and udev have started. QM and sshd start after the delay. |
| 1 / 15 | QM attempt **13.504–46.183**, ending at timeout | NetworkManager and hostnamed have started. Dispatcher, sshd and user-session permission service start alongside QM. SSH PID 453 later waits 28.622–48.531 for its session. |
| 1 / 42 | QM attempt **13.422–46.136**, ending at timeout | Same broad root-service startup phase: NM/hostnamed active; dispatcher, sshd and user-session permission service starting. |
| 2 / 66 | QM attempt 13.477–48.255; runtime directory **15.715–48.294** | Timeout notification precedes runtime completion by 39 ms; main-process exit is later, at 49.597 s. [Detailed recovery trace](ssh-run-2-boot-66.md). |
| 2 / 83 | QM attempt **13.537–46.399**, ending at timeout | NM/hostnamed active; dispatcher, sshd and user-session permission service starting. Later automatic restart is a separate attempt. |
| 3 / 26 | QM attempt 13.614–45.785; runtime directory **15.259–45.916** | NM/hostnamed active; QM in progress when root runtime-directory setup starts. SSH session opening is also delayed. |
| 3 / 62 | QM attempt **13.542–43.579**, ending at timeout; create-to-init **18.336–52.118** | NetworkManager, hostnamed, sshd and root user manager have started. Bridge/veth are visible around 18.7–18.9 s; several SSH sessions open during the later Podman interval. |
| 2 / 31 | Runtime directory **18.228–49.891** | QM already started at 17.350 s. User-manager startup follows, then three SSH sessions open together. [Detailed dependency trace](ssh-run-2-boot-31.md). |

The first three rows are particularly useful controls against the idea that
Podman triggers every incident. In run 2 boot 35, the independent systemd boot
phase timing reports 33.621 s in InitRD. A `cntvct@basic` message later reads
47.681 s, whereas that hardware-counter reading is normally around 15 s; the
large early delay is also visible in that additional timing observation.

The kernel -251 source places run 1 boot 1's PTP and link-mode messages inside
the same interface-open operation. Between them, reducing the configured TX
queue count can call `synchronize_net()` and wait for an RCU grace period.
This gives a concrete kernel-wait candidate; it does not prove an RCU defect
or identify the delayed call without a stack/trace. The dispatcher startup
message near recovery is not a required second trigger in this driver path.
[Version-specific NIC driver trace](nic-driver-run-1-boot-1.md).

[Cross-case source comparison](shared-waits-other-cases.md) additionally finds
kernfs removal and fsnotify/SRCU teardown candidates in user-manager shutdown,
but no demonstrated direct RCU wait in runtime-directory creation or ordinary
SSH session setup. Their D-Bus/job dependencies can propagate a delay. CPU
accounting suggests the RSA key-generation outliers are computation rather
than long sleeping waits; they remain timing candidates, not strong evidence
for the same underlying stall.

Services commonly active in the root-system incidents include journald, udev,
D-Bus, auditd, chronyd, logind and, in later incidents, NetworkManager, sshd,
hostnamed, QM and the user manager. This commonality is expected in an ordinary
boot and is not evidence that one of those daemons caused the stall.
`rcu-normal.service` also completes around 11.3–11.6 s in these root-system
examples, including healthy boots; it is included in the nearby transitions
rather than being assigned causality.

## Late SSH-session delays

The additional boots below have successful initial QM startup but delayed SSH
session opening. Each range covers accepted-key to PAM-open intervals paired
by sshd PID; where multiple delayed connections overlap, their union is shown.
The full CSV retains each PID separately.

| Run / index | SSH interval, seconds | Other signal |
| --- | --- | --- |
| 1 / 20 | 21.446–52.819 | chronyd jump reported 52.774 |
| 1 / 33 | 20.738–50.360 | chronyd jump reported 50.312 |
| 2 / 20 | 28.110–60.635 | RSA key-generation outlier earlier in the boot |
| 2 / 25 | 19.940–50.670 | Session 3 scope completes at 50.662 s; PAM opens 8 ms later. [Detailed trace](ssh-run-2-boot-25.md). |
| 2 / 90 | 21.167–52.703 | No kernel lockup report |
| 2 / 94 | 22.281–55.450 | CPU 7 watchdog reported 53.260 |
| 3 / 10 | 20.836–51.661 | chronyd jump reported 51.611 |
| 3 / 35 | 39.654–52.705 | chronyd jump reported 50.542; shorter measured SSH interval |
| 3 / 42 | 20.777–52.488 | chronyd jump reported 52.343 |

Run 2 boot 31 is in the first table. The other three delayed-session boots
have QM failures and are likewise represented there. In most of these late
examples, the normal host daemons and QM have already completed startup.
Sessions can continue authenticating while other sessions are delayed, which
does not fit a universal absence of all CPU execution or all packet delivery.

## The two watchdog reports

| Run / index | Report time | CPU | Printed watchdog age | Report minus age, heuristic only | QM was started by |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / 81 | **56.170 s** | 0 | 30 s | approximately 26.170 s | 17.310 s |
| 2 / 94 | **53.260 s** | 7 | 32 s | approximately 21.260 s | 17.639 s |

There are **no newly starting services within one second of those heuristic
watchdog reference points** after reconciling missing journal completion
timestamps. The usual host daemons, QM and root user manager have started.
This is different from a particular daemon beginning startup and immediately
provoking the warning.

In run 1 boot 81, SSH sessions open normally at 20.435 and 20.957 s. The
dispatcher deactivates at 26.014 s. Configuration-file messages from PID 1
continue during part of the watchdog's printed age interval. The warning
appears at 56.170 s; hostnamed deactivates successfully at 56.209 s.

In run 2 boot 94, the first SSH session opens at 20.009 s. Another connection
authenticates at 22.281 s but its session opens only at 55.443 s. A later
connection authenticates at 43.174 s. PID 1 begins stopping the old user manager
at 52.227 s and starts a replacement at 53.399 s. Thus user-manager stop/start
activity near the warning is later than the heuristic 21.260 s heartbeat
reference and is not evidence that the restart initiated the problem.

Both traces contain `default_idle_call`, `cpuidle_idle_call`, and `do_idle`.
The watchdog checks whether its scheduling heartbeat was updated and prints
the current stack at detection. The printed age is not a precise fault-onset
timestamp, and that current idle frame does not identify code executing earlier
in the interval. Timer/interrupt delivery, scheduling and timekeeping therefore
remain investigation targets alongside networking.
[Kernel watchdog documentation](https://docs.kernel.org/admin-guide/lockup-watchdogs.html)

## Careful kernel sweep

All **118,925 kernel journal messages** were scanned, covering every recorded
boot. After normalizing volatile dates, audit sequence numbers, UUIDs, pointer
addresses and small available-memory variation, there are 415 message
signatures. Original examples and every signature's boot membership are saved
in `kernel-signatures.csv`; the stack traces remain in the context export.

The exceptional messages are:

| Message group | Boot count | Interpretation supported by these records |
| --- | ---: | --- |
| Soft-lockup warning and its register/stack dump | 2 | Exactly the reports at 1/81 and 2/94. No additional lockup reports found. |
| `hrtimer: interrupt took 7799 ns` | 1 | Run 3 boot 34 at **32.525 s**. This reports 7.799 microseconds, not a seconds-long stall; no QM timeout in that boot. |
| RTC POR/reset, power-loss/invalid-time, unreadable hardware clock | 60 | Three related messages per affected boot; a recurring pattern, described below. |
| `audit: type=1130 ... systemd-update-done ... res=success` | 1 | Run 2 boot 10; successful audit event, not a kernel fault. |
| Veth unregister/allmulticast/promiscuous cleanup | 2 | Runs 2/66 and 3/62, during cleanup after QM failure. |

Other differences are normal deferred-page initialization timing (20 versus
30 milliseconds), small available-memory variation, register values in the two
watchdog dumps, and the presence/absence of ordinary bridge/veth setup messages.
Bridge messages are absent in three early-failed boots and can appear after
restart or during timeout handling in others.

There are **zero** additional `WARNING:` reports, RCU-stall reports, hung-task
reports, oops/panic reports, NETDEV WATCHDOG reports, matching storage I/O errors,
or clocksource-unstable diagnostics. This statement applies to the captured
records, not to execution outside the collection windows.

All 299 boots log `watchdog: NMI not fully supported` and `Hard watchdog
permanently disabled`. Absence of hard-lockup reports is consequently not
reassuring evidence. The clocksource switch to `timer@4011c000`, its timer
registrations, missing optional NIC IRQ messages, and dummy regulator warning
also occur in every boot; there is no failure-specific configuration difference
in those messages.

## RTC and other clock signals

Sixty boots contain the sequence:

```text
rtc-pcf85063 ... POR issue detected, sending a SW reset
rtc rtc0: Power loss detected, invalid time
rtc-pcf85063 ... hctosys: unable to read the hardware clock
```

Each run has twenty affected records. The pattern is approximately every fifth
record, with occasional shifts in index. The remaining 239 boots have a normal
RTC system-clock-setting message. It is a real difference worth recording, but:

- None of the six QM-timeout boots has this RTC-invalid sequence.
- Neither soft-lockup boot has it.
- Among the 26 boots with long intervals or watchdog/chronyd signals, only run
  1 boot 63 has it. Other RTC-invalid boots have smaller startup outliers.

Therefore invalid RTC state is not a necessary condition for the principal
stalls and is not positively associated with them in this inventory. The logs
do not identify what causes that roughly periodic RTC reset pattern; it should
not be assigned to a particular reboot/power-control mechanism without the
test harness details.

Chronyd's eleven forward-jump reports occur at:

```text
1/15 46.125   1/20 52.774   1/33 50.312   1/95 51.472   1/97 52.263
2/16 56.017   2/83 46.299
3/8  52.012   3/10 51.611   3/35 50.542   3/42 52.343
```

Many accompany a burst of delayed session/service activity, which makes them
useful recovery-side markers. They do not establish whether a clock change
caused the delay, resulted from it, or reflects a shared timekeeping problem.
None of these eleven boots has the RTC-invalid sequence either.

## Established SSH session lifetimes

All authenticated SSH connections are tracked, including ones whose login is
healthy. Matching PAM open and close messages by sshd PID gives 620 completed
lifetimes. A lifetime is flagged when it exceeds max(1 second, Q3 + 3 × IQR),
which is 1.000 s for these records. The 616 below that threshold have median
0.222597 s and maximum 0.544616 s. The four outliers are:

| Run / boot | SSH connection number | Open-to-close interval | Duration |
| --- | ---: | --- | ---: |
| 1 / 97 | 2 | 20.915675–52.309143 s | 31.393468 s |
| 2 / 11 | 3 | 22.638092–53.047816 s | 30.409724 s |
| 2 / 16 | 3 | 21.567842–54.327423 s | 32.759581 s |
| 3 / 8 | 3 | 20.633689–51.248431 s | 30.614742 s |

Connection numbers follow accepted-key order; logind session IDs use a different
sequence. Boot 2/11 is newly included by this criterion. The other three boots
already had chrony signals. Long lifetimes include command execution and client
waiting and do not, on their own, prove a stall. Another 299 sessions have no
recorded close, so their observed extents end with the captured log and are
excluded from detection. [Boot 97 details](ssh-run-1-boot-97.md).

## Late extra SSH connection in run 2 boot 41

The fourth reference connection previously came solely from run 2 boot 41.
That boot has a long `user@0.service` shutdown: 30.269394–51.739810 s,
**21.470416 s**, despite normal initial service startup and short completed
SSH lifetimes. The user manager reaches `exit.target` at 30.289866 s;
the next journal records are two accepted SSH keys at 51.662054/51.662059 s.
A replacement user manager starts at 51.892123 s and is ready at 53.989588 s.
The fourth connection authenticates at 54.470708 s.

Explicit host service shutdowns exceeding 10 seconds are now included in the
inventory and drawn in amber on the service's existing row. The shutdown can
include process exit, teardown and job-completion waiting; it does not identify
where execution was delayed. This criterion adds boot 2/41 independently of its
unusual SSH count. It also identifies a 19.611081-second stop in already listed
run 3 boot 35 (31.107250–50.718331 s), ending at the same recovery burst as
its chrony warning and delayed SSH login. All 17 boots with more than three authenticated connections
are now outside the reference, leaving 261 boots with exactly three each.
[Detailed trace](ssh-run-2-boot-41.md).

A complete `user@0.service` sweep found 303 completed starts/restarts and four
completed shutdowns. Every start/restart takes 1.898–2.845 s. The only shutdowns
over 10 s are 2/41 and 3/35; the others take 1.156 s (2/94) and 0.167 s (2/20).
No additional user-manager outliers were found in the captured journals.
[Complete user-manager sweep](user-manager-report.md),
[all measured intervals](user-manager-intervals.csv).

## Files and reproduction

A strict absolute cutoff was also checked across all recorded service starts,
restarts and explicit shutdowns: 14 startup attempts and two shutdowns exceed
10 seconds, all already in this inventory. No additional service types or boots
were found. [Complete >10-second service sweep](service-over-10s-report.md),
[measured intervals](service-over-10s.csv).

- `stall-timeline.html`: one interactive graph per affected boot, grouping all
  65 observations in 38 boot rows. The top row is an arithmetic-mean reference
  from the other 261 boots, which have no detected observations in this report.
  Boot phase backgrounds mark kernel startup, initrd, host startup before
  `network-online.target`, network-online time before the host default target,
  and time after the host default target (`graphical.target`). Cyan switches
  to pink at the host network-online milestone, then to green at its default
  target. The average row uses the same split. User-manager target
  messages do not control these backgrounds. The top legend explains every
  color and line style. Thin dashed intervals show the recorded problematic
  services in every displayed boot, even when their startup is healthy, plus
  logind startup, NIC milestones and observed Podman bridge/veth setup. Every
  SSH connection has a separate numbered row showing accepted-key-to-PAM-open
  login (gray dashes) and PAM-open-to-close lifetime (teal dashes). Amber dashed intervals show explicit service shutdowns, with a solid amber
  bar for shutdowns exceeding 10 seconds. A solid
  purple bar marks a long login; a solid teal bar marks a long completed
  lifetime. An arrow extends an incomplete lifetime only to capture end;
  incomplete lifetimes never trigger outlier detection. Connection numbers
  follow authentication order and are not logind session IDs.
  Orange seat-announcement dots and teal new-session
  announcement dots sit on the logind startup row. Every recorded new session
  is shown on individual boots; the reference averages only the first session
  announcement per boot. The network-setup popup details list each bridge/veth milestone; its
  interval does not imply every Podman networking operation has completed.
  Missing records are labeled rather
  than represented as zero. Repeated service attempts remain separate.
  Clicking a timeline mark or background phase opens service context and
  highlighted journal lines across the relevant interval. Popups stay open
  until closed with Close, Escape, or an outside click; Enter/Space also opens them.
  Run, search and moderate-observation filters preserve the reference cohort.
- `timeline-reference.json`: the exact 261-boot reference cohort, mean phase
  boundaries/durations and per-service means, ranges and contributing counts.
  RSA key generation has 84 observations in this cohort; the other displayed
  service/reference tracks, mean first seat0 announcement and mean first session
  announcement have 261. SSH means are grouped by connection order and show
  contributing counts. Where closes are missing, the reference averages the
  observed extent rather than claiming a completed mean lifetime. Reference
  popups show these statistics rather
  than fabricating a log excerpt for an averaged boot. Post-target reference
  coverage ends at the mean last-record time; hatching marks unobserved time.
- `stall-events.csv`: both absolute time coordinates, interval semantics,
  service context, and the uncertainty attached to each observation.
- `stall-boots.csv`: all 38 candidate boots, grouped by boot.
- `service-stop-intervals.csv`: explicit host service shutdown intervals.
- `ssh-connections.csv`: all 919 SSH connections, including login, PAM open,
  PAM close where recorded, and the capture boundary.
- `ssh-session-lifetimes.csv`: the 620 completed lifetimes used for detection.
- `stall-context.txt`: nearby original log messages and service snapshots.
- `kernel-signatures.csv`: every normalized kernel signature and boot count.
- `kernel-findings.csv`: the exceptional/RTC/cleanup messages with timestamps.
- `stall-inventory.md`: compact complete observation table.

Service context means nominal systemd lifecycle state reconstructed from unit
timings and journal transitions. It does **not** show which thread was running
on a CPU or which process held a lock. No single lifecycle event is common to
all the cases. Resolving a shared kernel cause needs per-CPU scheduling,
timer/interrupt and blocked-stack evidence during an incident, with a hardware
counter sampled after as well as before the suspect interval.

Run `python3 analyze_qm_services.py` followed by `python3 analyze_qm_stalls.py`
from the workspace root to regenerate the data and interactive timeline.
The grouped renderer is in `render_qm_timeline.py`, with the self-contained
HTML/CSS/JavaScript template in `qm_timeline_template.html`.
