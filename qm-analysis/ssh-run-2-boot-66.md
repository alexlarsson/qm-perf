# Run 2 boot 66: QM timeout coincides with runtime-directory recovery

This boot reproduces the runtime-directory/user-manager/SSH dependency pattern
from run 2 boot 31, with an additional interrupted Podman network setup.
Times use the reconstructed kernel-start origin, subtracting the boot metadata
offset of 4.074315 seconds.

## Timeline

| Time | Observation |
| ---: | --- |
| 11.251546 s | D-Bus launcher reports Ready. |
| 12.657123 s | Logind service has started; its process is PID 348. |
| 13.476618 s | QM service begins startup. |
| 15.492586 s | Original Podman PID 390 emits container create. |
| 15.540972 s | SSH PID 467 accepts the public key. |
| 15.692897 s | Logind announces session 1. |
| 15.715583 s | Runtime-directory service starts. |
| 15.879935 s | NetworkManager reports the Podman bridge activated. |
| 18.757200 s | Chronyd selects an NTP source. |
| Around 19–20 s | Chronyd corrects wall time backward by 1.255375 s; some exported messages are out of timestamp order around this adjustment. |
| 25.979349 s | PID 1 reports dispatcher deactivation, during the long interval. |
| **48.232716 s** | PID 1 reports hostnamed deactivated successfully. |
| **48.254841 s** | PID 1 reports QM startup timed out and begins termination. |
| **48.294313 s** | Runtime-directory service finishes successfully. |
| **48.305853 s** | First veth bridge-port setup message appears. |
| 48.311808 s | NetworkManager sees the veth device. |
| 48.311850 s | Root user-manager service starts. |
| 48.385593 s | Logind announces session 2, during user-manager startup. |
| 48.476159 s | Veth carrier becomes connected. |
| 48.480884 s | Veth enters forwarding state. |
| 48.687715 s | Another SSH connection, PID 502, authenticates during recovery. |
| **49.596744 s** | QM's main process is reported exited with status 1. |
| 50.424562 s | Root user manager finishes startup. |
| 50.437366 s | Session 1's scope is reported started. |
| 50.447099 s | The original SSH PAM session opens. |
| 50.453512 s | The later SSH PAM session opens. |
| 51.122794 s | A cleanup Podman process, PID 561, reports container removal. |
| **51.228712 s** | PID 1 reports final failure to start QM. |

The original Podman invocation has no container init or container start event
in the captured journal. The resumed veth work is followed by teardown, not
an observed successful container startup.

## What actually coincides

The red QM interval in the interactive report ends at **timeout detection**,
not at main-process exit or completion of cleanup. Distinguishing these gives:

```text
hostnamed deactivation → QM timeout notification     22.125 ms
QM timeout notification → runtime-directory finish  39.472 ms
runtime-directory finish → first veth setup message 11.540 ms
QM timeout notification → main-process exit          1.341903 s
runtime-directory finish → main-process exit         1.302431 s
```

Thus there is a tight group of recovery/timeout notifications across several
components, but Podman's main process exits substantially later than runtime
directory completion. This does not establish which event caused another.

Two hypotheses remain compatible with much of the sequence: a shared resource
or execution path becomes available and pending operations proceed together;
or QM termination/cancellation releases a resource needed elsewhere. The first
visible item in the group, hostnamed deactivation, precedes the timeout message
by 22 ms, so it is not justified to assign the entire recovery solely to QM's
termination. Event and signal tracing is needed to distinguish these cases.

## Comparison with boot 31

| Measurement | Run 2 boot 31 | Run 2 boot 66 |
| --- | ---: | ---: |
| Runtime-directory activation, journal interval | 31.663023 s | 32.578730 s |
| Subsequent user-manager activation | 2.203444 s | 2.112712 s |
| First SSH accepted-key-to-PAM wait | 34.066098 s | 34.906127 s |
| Scope Started to first SSH PAM open | 9.754 ms | 9.733 ms |
| QM initial result | Started successfully | Timed out |

The runtime helper is the long interval in the observed SSH dependency path;
the user-manager activation afterward is ordinary. There is one long-stalled
authenticated SSH connection in boot 66. A later one authenticates after the
recovery group begins and waits 1.765797 s for the same user-manager startup.
Three other attempts report Broken pipe before authentication during recovery;
their initial connection times are not recorded.

Both boots have PID 1 activity during the long runtime interval, notably
dispatcher deactivation at about 26 s. Neither proves uninterrupted blockage
of PID 1 or all CPUs. Chronyd also makes progress before the recovery.

## Logind and possible shared dependencies

Logind was ready before the incident and handled session 1 just before the
runtime service starts. It has no further messages until 48.385593 s, a
32.692696-second gap, and retains PID 348 without a recorded restart.
Its first post-gap session announcement is 91.280 ms after runtime-directory
completion. As with boot 31, there are no D-Bus method traces identifying the
helper's property request/reply times.

Upstream systemd's runtime-directory helper performs local bus queries to
logind in addition to its credential, directory, tmpfs and labeling work.
That leaves logind/broker interaction among the candidates; it does not prove
which step waited. The user manager is ordered after the runtime-directory
unit, which accounts for the downstream SSH delay.
[Runtime helper](https://raw.githubusercontent.com/systemd/systemd/v257/src/login/user-runtime-dir.c),
[user-manager unit](https://raw.githubusercontent.com/systemd/systemd/v257/units/user@.service.in).

QM is not merely waiting to start after the runtime-directory service: it
has already created its container before that service begins. Its network
setup therefore supplies an additional stalled path to compare with the
helper/login path. The logs do not establish that they share a particular
lock, kernel subsystem or D-Bus request.

## Measurement limits and next capture

The runtime unit record reports 32.578744 s, agreeing with the independent
journal interval within 14 microseconds. The long runtime interval is not
explained solely by the earlier 1.255375-second wall-clock correction. Nearby
48-second notifications have a coherent ordering, but message timestamps do
not provide exact signal-delivery or lock-release times.

There is no soft-lockup or RCU-stall report in this boot. QM's aggregate CPU
accounting is 1.385 s, which does not suggest continuous CPU execution for the
whole startup interval, but does not identify the blocked operation.

The most discriminating capture would collect PID 1, logind, the runtime helper,
Podman and its network helper's stacks/syscalls together, plus the actual QM
termination-signal timing. This would test whether a shared wait ends before
timeout handling or whether cancellation releases a resource that allows the
other paths to proceed.
