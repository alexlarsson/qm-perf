# Run 2 boot 31: runtime-directory delay propagates to SSH

The long runtime-directory and SSH bars overlap along the observed session
startup path. They are not evidence of two independent 30-second timers.
Times below use the reconstructed kernel-start origin, subtracting this boot's
4.082689-second metadata offset.

| Time | Observation |
| ---: | --- |
| 15.791840 s | sshd started successfully. |
| 17.349687 s | QM started successfully. |
| 17.351880 s | Host default target reached. |
| 18.068268 s | First SSH connection, PID 525, accepts the public key. |
| 18.204319 s | logind announces session 1. |
| 18.228413 s | `user-runtime-dir@0.service` begins activation. |
| 18.839238 s | chronyd selects an NTP source. |
| 20.265599 s | chronyd selects another source. |
| 25.945476 s | PID 1 reports dispatcher deactivation. |
| 28.834155 s | SSH PID 558 accepts a public key. |
| 40.791813 s | SSH PID 562 accepts a public key. |
| 49.789530 s | PID 1 reports hostnamed deactivation. |
| 49.835463 s | logind announces session 2. |
| 49.866476 s | logind announces session 3. |
| 49.891436 s | Runtime-directory activation finishes successfully. |
| 49.907805 s | `user@0.service` begins activation. |
| 52.111249 s | Root user manager finishes activation. |
| 52.124612 s | PID 1 reports session 1's scope started. |
| 52.132691 s | PID 1 reports session 2's scope started. |
| 52.134366 s | First SSH PAM session opens. |
| 52.139902 s | Second SSH PAM session opens. |
| 52.140771 s | PID 1 reports session 3's scope started. |
| 52.148714 s | Third SSH PAM session opens. |

## Relationship between the bars

The runtime-directory journal start-to-finish interval is **31.663023 s**.
The subsequent user-manager activation is **2.203444 s**, within its ordinary
range in this dataset. There is only 16.369 ms between runtime-directory
completion and the user-manager Starting message.

The first SSH wait can be accounted for as:

```text
accepted key → runtime-directory start             0.160145 s
runtime-directory activation                     31.663023 s
runtime-directory completion → user-manager start  0.016369 s
user-manager activation                           2.203444 s
user-manager completion → SSH PAM session open     0.023117 s
                                                ------------
first accepted-key-to-PAM wait                    34.066098 s
```

Later connections have shorter waits but open at nearly the same time:

| SSH PID | Key accepted | PAM session opens | Wait |
| ---: | ---: | ---: | ---: |
| 525 | 18.068268 s | 52.134366 s | 34.066098 s |
| 558 | 28.834155 s | 52.139902 s | 23.305747 s |
| 562 | 40.791813 s | 52.148714 s | 11.356901 s |

Their openings are spread over only 14.348 ms. A subsequent connection, PID
627, authenticates at 52.813879 s and opens at 52.877217 s: **63.338 ms**.
The three earlier connections then log ordinary client-requested disconnects;
there is no Broken pipe equivalent to run 2 boot 25 in this interval.

Upstream systemd 257 orders the user manager after the runtime-directory unit.
Logind defers the session-creation reply until its relevant scope/user-manager
jobs are ready. These dependencies fit the observed sequence: a long upstream
activation, then ordinary user-manager startup, then the waiting sessions
opening together. Distribution units and patches should be verified on the
board before assuming every upstream detail is unchanged.
[User-manager unit](https://raw.githubusercontent.com/systemd/systemd/v257/units/user@.service.in),
[session-creation handling](https://raw.githubusercontent.com/systemd/systemd/v257/src/login/logind-dbus.c).

## What may be inside the runtime-directory interval

The helper's name does not establish that it was blocked in a filesystem
operation. Upstream systemd 257 initializes security labeling, looks up user
credentials, asks logind over the system D-Bus for the runtime-directory size
and inode limit, and creates/checks the directory and its tmpfs mount. It also
fixes labels afterward. The supplied journal has no helper debug messages that
identify which step was slow, or whether some delay occurred before exec.
[Runtime-directory helper source](https://raw.githubusercontent.com/systemd/systemd/v257/src/login/user-runtime-dir.c).

The two D-Bus property lookups have warning/fallback paths, but neither the
size-acquisition nor inode-limit warning appears in this boot. That is no
positive evidence of a D-Bus timeout fallback; it does not prove the calls
completed promptly. Logind announces no additional sessions from 18.204319 s
until 49.835463 s even though further SSH connections authenticate meanwhile.
That makes the helper/logind interaction worth tracing, without establishing
which process or kernel operation is responsible.

Unlike a hypothesis of PID 1 being blocked throughout the interval, there is a
PID 1 dispatcher-deactivation message at 25.945476 s, during the long runtime
activation. Other processes also make progress. A single uninterrupted global
CPU freeze or PID 1 blockage is therefore not established by this trace.

There is no recorded service failure, timeout, soft-lockup, RCU-stall or chronyd
forward-jump report in this boot. The upstream runtime-directory unit is
`Type=oneshot`, for which startup timeouts are disabled by default. A 31.7 s
successful activation consequently need not produce a timeout error. Local
overrides could change that policy; inspect `Type` and `TimeoutStartUSec` on
the installed unit to confirm.
[Runtime-directory unit](https://raw.githubusercontent.com/systemd/systemd/v257/units/user-runtime-dir@.service.in),
[oneshot timeout semantics](https://www.freedesktop.org/software/systemd/man/257/systemd.service.html#TimeoutStartSec=).

## Logind and D-Bus activity around the pause

The bus launcher reports Ready at 11.321649 s. Logind starts at 11.481350 s,
creates seat0 at 12.617962 s, and its service is reported Started at
12.660416 s. It subsequently announces session 1 at 18.204319 s, demonstrating
session-request processing immediately before runtime-directory activation
begins at 18.228413 s.

There are no further logind messages until session 2 is announced at
49.835463 s, followed by session 3 at 49.866476 s. This is a 31.631144-second
gap in logind's output. Both additional SSH connections had authenticated
earlier, at 28.834155 and 40.791813 s. Runtime-directory activation completes
at 49.891436 s, only 55.973 ms after the first resumed logind message.

Logind retains PID 347 throughout these messages, with no recorded crash,
failure or restart. There are no broker-daemon error messages or bus-method
traces that explain the wait. Startup completion proves earlier availability,
not ongoing responsiveness. The recovery ordering is consistent with the
runtime helper waiting for logind/D-Bus, but logind silence alone cannot
distinguish a blocked logind handler, delayed bus delivery, or another shared
dependency. The exact property-request and reply times are not recorded.

## Measurement check and next capture

This is not merely a stale-field artifact: the Starting and Finished journal
messages independently span 31.663023 s. The exported unit duration is
31.662805 s, agreeing within 0.218 ms. The separate exported `activated` endpoint
is stale and predates `activating`; it was not used to infer this delay.

The narrow next capture is the runtime-directory helper's syscall trace and
kernel stack, together with logind and PID 1 state, armed locally before SSH
is attempted. It should distinguish waiting for a D-Bus reply from directory,
mount/security-label work or service-execution setup. The root cause remains
unidentified; the evidence establishes a shared dependency bottleneck rather
than independent SSH and directory-service timeout failures.
