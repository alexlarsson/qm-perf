# Run 2 boot 25: delayed SSH session scope

Times use the report's reconstructed kernel-start origin. The boot offset is
4.064548 seconds. This is the second root SSH connection, after the first
session and the user manager already started successfully.

| Time | Observation |
| ---: | --- |
| 13.647877 s | `sshd.service` started, after approximately 0.132 s activation. |
| 17.525539 s | Root's `user@0.service` started. |
| 17.692994 s | QM started successfully. |
| 17.882256 s | PID 1 logged overall boot completion. |
| 19.940214 s | SSH PID 624 accepted the public key. |
| 19.979392 s | logind announced new session 3. |
| 20.066985 s | chronyd selected an NTP source. |
| 41.337323 s | A further SSH connection, PID 628, authenticated. |
| 50.661541 s | PID 1 reported `session-3.scope` started. |
| 50.669609 s | hostnamed deactivated successfully. |
| 50.669782 s | SSH PID 624 opened its PAM session. |
| 50.683536 s | NetworkManager dispatcher deactivated successfully. |
| 50.692618 s | SSH session child PID 634 reported `Broken pipe` sending a reply. |
| 50.748224 s | PID 1 reported session 4's scope started. |
| 50.764060 s | SSH PID 628 opened its PAM session. |

The accepted-key-to-session interval is 30.729568 seconds. More specifically,
30.682149 seconds separates logind's new-session message from the scope's
Started message. PAM opens only 0.008241 seconds after that scope message.
The previous PID 1 message was at 17.882256 seconds, a 32.779285-second gap in
its journal output. Silence alone does not prove PID 1 was blocked or when a
stall began, but the session scope and several unit-state notifications all
appear together afterward.

Upstream systemd 257 starts/queues the session scope before logging the new
session. It defers the session-creation reply until the relevant scope/user
manager jobs are ready. This explains why a new-session announcement is not a
completed login. Here the root user manager was already active, and the scope
completion is followed almost immediately by the PAM session-open message.
[Session startup source](https://raw.githubusercontent.com/systemd/systemd/v257/src/login/logind-session.c),
[session-creation reply handling](https://raw.githubusercontent.com/systemd/systemd/v257/src/login/logind-dbus.c).

The corresponding upstream `pam_systemd` session-creation bus call has a
120-second timeout. A roughly 31-second wait can therefore complete without a
PAM timeout error. The installed distribution may contain patches, and this
does not exclude a separate timeout inside another operation.
[PAM session code](https://raw.githubusercontent.com/systemd/systemd/v257/src/login/pam_systemd.c).

The Broken pipe is consistent with a client that stopped waiting before the
server resumed; the server-side journal cannot establish when the peer closed
or why. Another connection authenticates during the interval, so complete
network loss is not established either. There is no soft-lockup, RCU-stall, or
chronyd forward-jump report in this boot.

The strongest supported localization is the local session-scope activation/
completion path involving PID 1 and logind. A hidden timeout is possible, but
the observed duration does not identify a 30-second timer. PID 1's kernel
stack, wait channel and current syscall, captured locally during the delay,
would help distinguish a kernel wait from a userspace/event-loop delay. A
sleeping kernel wait can delay this path without tripping a CPU soft-lockup
watchdog.
