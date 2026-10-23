# Network-focused analysis of QM startup

## Assessment

Networking remains a plausible lead, especially the board's kernel interface
configuration and network-namespace paths. There is a concrete long delay
during physical NIC bring-up in one boot. The records provide substantially
less support for a common DHCP, cable, switch, or DNS-server timeout explaining
the six QM failures. Those possibilities are not excluded: these are boot
journals, not packet captures or hardware-counter samples.

This analysis covers all 299 JSON boot records, preserving zero-based boot
indexes. The September 24–25 debug files are not pooled into these counts.
Event intervals use exported `activating` microseconds; no inference about a
natural stall duration is drawn from QM's configured startup timeout.

## Physical NIC and DHCP across all boots

The controller identifies as `s32-dwmac 4033c000.ethernet`, interface `end0`.
Its full sequence of driver log messages is identical across all 299 boots.
There are no logged physical link-down events, DMA/TX failure messages matching
the analysis patterns, or NetworkManager `<warn>`/`<error>` messages. Messages
about missing optional IRQs occur in every boot and do not distinguish failures.

| Measurement | Successful QM boots: median (range) | Failed QM boots: median (range) |
| --- | --- | --- |
| NetworkManager service start | 2.131 s (1.971–34.554) | 2.114 s (2.068–2.169) |
| NIC PTP registration to fixed-link configuration | 55 ms (2 ms–32.456 s) | 50 ms (45–65 ms) |
| DHCP begin to first lease message, ACD pending | 33 ms (29–170 ms) | 34 ms (33–174 ms) |
| DHCP begin to final lease message | 248 ms (187–437 ms) | 245 ms (196–404 ms) |

Every boot obtains `192.168.100.125` in the matched final DHCP lease message.
In the six failures, physical interface activation completes 0.150–0.537 s
after QM starts. Thus there is no failure-specific slowdown in these recorded
physical interface/DHCP milestones. Early success does not prove the NIC or
external path remains healthy later.

The driver reports **fixed/rgmii-id link mode** and **MDIO bus disabled**.
The reported fixed MAC link should not be treated as a complete check of the
board's external network topology or cable health. The device tree and board
schematic are needed to establish what that link connects to. Linux distinguishes
fixed-link operation from conventional PHY-managed negotiation in its
[phylink documentation](https://cdn.kernel.org/doc/html/latest/networking/sfp-phylink.html).

## A concrete NIC bring-up delay: run 1 boot 1

NetworkManager takes 34.554 s to start in this boot, although QM subsequently
starts successfully in 3.807 s. The delay can be localized much more closely
than the earlier overall-service comparison:

```text
Relative to QM start:
-32.562 s  kernel: s32-dwmac ... end0: registered PTP clock
 -0.106 s  kernel: s32-dwmac ... end0: configuring for fixed/rgmii-id link mode
 -0.103 s  kernel: s32-dwmac ... end0: Link is Up - 1Gbps/Full
 -0.065 s  NetworkManager: dhcp4 (end0): activation: beginning transaction
 +0.154 s  NetworkManager: dhcp4 (end0): state changed new lease ...
```

There is a **32.456 s interval inside the NIC bring-up log sequence**, before
DHCP. All other boots have less than one second between those driver messages.
NetworkManager's embedded realtime timestamps independently show a 32.501 s
gap from `end0` becoming managed/unavailable to its next message. This makes
driver/interface initialization a real investigation target. PTP registration
here is a local hardware-clock registration; the message does not show a wait
for a remote PTP server.

It does **not** establish that the NIC hardware itself spent that interval
initializing: the thread could be descheduled or blocked in another kernel
operation, and the sparse messages do not locate one function. In upstream
Linux 6.12, `stmmac_hw_setup()` registers PTP before finishing other setup,
and `__stmmac_open()` subsequently calls `phylink_start()`. This identifies a
useful span to trace, but the shipped downstream source must be checked.
[Linux 6.12 stmmac source](https://raw.githubusercontent.com/torvalds/linux/v6.12/drivers/net/ethernet/stmicro/stmmac/stmmac_main.c)

Device open runs under RTNL in Linux 6.12. A thread stalled while holding this
network configuration lock could delay other interface configuration operations,
including virtual ones. This is a mechanism to test with stacks and lock-owner
tracing, not an observed lock dependency in these journals.
[Linux 6.12 network-device source](https://raw.githubusercontent.com/torvalds/linux/v6.12/net/core/dev.c)

## The other slow NetworkManager boot is different: run 1 boot 63

NetworkManager explicitly reports:

```text
Error calling StartServiceByName for org.freedesktop.hostname1: Timeout was reached
```

It spends approximately 25.032 s between its firmware-directory monitoring
message and that error. After logging DNS-manager initialization, another
8.295 s passes before its rfkill message. The total NetworkManager start is
34.166 s. Its subsequent PTP-to-fixed-link interval is 73 ms and DHCP takes
262 ms.

The named timeout is a **local D-Bus service activation**, not a DNS query to
the external network. `systemd-hostnamed` manages the local hostname. There is
also a relevant networking connection inside that local service: upstream
systemd 257 configures it with `PrivateNetwork=yes` and `RestrictAddressFamilies=AF_UNIX`.
Network namespace creation during sandbox setup is therefore a candidate worth
checking against the installed unit. This does not mean it is waiting for
internet connectivity, nor prove namespace creation is the stalled step.
[systemd 257 hostnamed unit](https://raw.githubusercontent.com/systemd/systemd/v257/units/systemd-hostnamed.service.in)

The logs identify systemd `257-31.el10-g8a3c29b` and NetworkManager
`1.58.0-1.el10`; installed distribution units and patches may differ from the
upstream examples above. All six QM-failed boots have normal initial hostnamed
startup. Its later `Deactivated successfully` messages should not themselves
be interpreted as network faults or as proof that releasing it ends a stall.

## Where Podman's network setup stops

Times below are relative to the initial QM start. No events from the successful
restart in run 2 boot 83 are assigned to its failed initial attempt.

| Run / boot | Physical interface activated | Podman network progress |
| --- | ---: | --- |
| 1 / 15 | +0.150 s | No bridge/veth messages during the first attempt. |
| 1 / 42 | +0.256 s | No bridge/veth messages during the first attempt. |
| 2 / 66 | +0.283 s | Bridge activation +2.403 s; veth carrier only +35.000 s. |
| 2 / 83 | +0.306 s | No bridge/veth messages during the first attempt. |
| 3 / 26 | +0.229 s | Early storage probing; no bridge/veth messages during the first attempt. |
| 3 / 62 | +0.537 s | Bridge activation +5.167 s, veth carrier +5.344 s, init only +38.576 s. |

Run 2 boot 66 makes virtual interface configuration a strong target: the bridge
exists well before veth setup resumes. Run 3 boot 62 proceeds further: visible
bridge/veth setup is already complete before the long init delay. That does not
prove all network setup is complete; namespace configuration, routes, firewall
work and later runtime setup are not fully logged. The journals do not name
netavark or establish the configured network backend.

NetworkManager assumes an externally created `podman0` connection in healthy
boots too. Its involvement with that bridge is not by itself evidence of a
race or that it is responsible for Podman's delay. A controlled test excluding
the container interfaces from NetworkManager is useful precisely because the
existing logs cannot decide this.

The four pre-event cases do not localize a network operation. They should remain
in the comparison rather than being assumed to be the same veth problem.

## SSH: three demonstrable delays occur after authentication

Pairing `Accepted publickey` and PAM session-open messages by the **same sshd
PID**, rather than combining unrelated connections, gives:

| Run / boot | First accepted key, relative to QM start | Accepted key to PAM session open |
| --- | ---: | ---: |
| 1 / 15 | +15.117 s | 19.909 s |
| 1 / 42 | +33.255 s | 2.473 s |
| 2 / 66 | +2.064 s | 34.906 s |
| 2 / 83 | +33.453 s | 2.462 s |
| 3 / 26 | +1.523 s | 32.916 s |
| 3 / 62 | +3.569 s | 2.746 s |

The first root SSH session normally also starts a user manager, so a few seconds
after authentication is common: the successful-boot median is 2.526 s.
Run 2 boot 66 and run 3 boot 26 explicitly spend long intervals creating the
local user runtime directory. These are observed host-session delays, not
evidence of a slow TCP connection establishment. In runs 1/15 and 3/26, further
connections authenticate while earlier ones are still waiting for sessions.

Runs 1/42 and 2/83 have late first accepted-key messages, but the export does
not show when the client first attempted TCP connection or authentication.
Packet loss, resolver waits, client retries and a stalled local sshd process
cannot be distinguished there. SSH and TCP are not ruled out just because
the daemon logs that it is listening.

There are ten additional boots where QM succeeds but at least one SSH
accepted-key-to-session interval exceeds ten seconds. The problem population
therefore extends beyond the six failed QM starts. Run 3 boot 62 opens multiple
SSH sessions during its Podman delay, which argues against complete loss of
the external network during that particular stall.

DNS remains unmeasured: there are no DNS request/reply traces or effective
resolver/sshd configurations in these files. NetworkManager's hostname-service
timeout is not evidence of broken external DNS. Check the effective SSH
configuration rather than assuming reverse lookups are enabled; upstream
OpenSSH documents `UseDNS` as disabled by default.
[OpenSSH configuration reference](https://man.openbsd.org/sshd_config)

## Additional kernel evidence found in this pass

Run 1 boot 81 logs `BUG: soft lockup - CPU#0 stuck for 30s! [swapper/0:0]`.
Run 2 boot 94 logs the corresponding report for CPU 7. QM succeeds in both.
Both stacks point at `default_idle_call`, `cpuidle_idle_call`, and `do_idle`;
neither shows a NIC driver function. These reports were missed in the original
summary. They strengthen the reason to capture kernel state, but do not prove
that networking or CPU idle is the underlying cause. Driver names in the
loaded-module list are not stack frames implicating those drivers.

## Experiments that would discriminate the network hypotheses

Keep boot count, image, storage, workload, logging and launch method comparable;
record both QM and other service stalls. With six QM failures in 299 boots, a
short clean run would be weak evidence. Count actual boot records and retain
the initial attempt even if a restart recovers.

| Controlled comparison | Main question it addresses |
| --- | --- |
| Same board/image and bridge networking on an isolated, known-good switch/network, initially retaining DHCP | Does the external environment or traffic load change the behavior? Improvement does not alone identify cable versus traffic-triggered driver behavior. |
| DHCP versus a reserved, conflict-free static configuration on the same network | Does DHCP/resolver configuration matter? The existing DHCP timings predict little benefit from changing DHCP alone. |
| Equivalent container test with its network mode changed to `none` | Does removing bridge/veth setup eliminate the pre-workload Podman stall? Check launch milestones; application readiness may legitimately require networking. |
| Original bridge setup, with only the observed container interfaces excluded from NetworkManager | Does NetworkManager's interaction with container interfaces matter? Match names from the trace, not every interface on the host. |
| Local-console test with the physical NIC administratively down, while keeping local container bridge setup | Does the NIC's active driver/traffic path matter independently of virtual networking? Unplugging a cable alone may not disable this fixed-link MAC. |

If offline tests are used, avoid interpreting a wait for `network-online.target`
or a workload's network requirement as a new Podman stall. Record when Podman
actually executes. `Network=none` still involves other namespaces and runtime
work; it does not remove every kernel namespace operation.

Before altering settings, capture one failing boot with:

- Packet timestamps at an external observer or mirrored switch port, plus a
  local capture if possible: DHCP, ARP, DNS and SSH. TCP retries during the stall
  versus successful exchanges followed by host-side delay are discriminating.
- Repeated `ethtool -S end0`, `ip -s -s link show dev end0`, `/proc/interrupts`
  and `/proc/softirqs`, covering per-queue errors and interrupt progress. The
  stmmac documentation identifies ethtool's statistics and register dumps as
  driver debugging interfaces. None of those counters is in the supplied JSON.
  [stmmac debugging documentation](https://docs.kernel.org/networking/device_drivers/ethernet/stmicro/stmmac.html)
- Pre-armed local thread stacks and syscall/latency tracing for NetworkManager,
  Podman and network helpers, service-executor children, and the user-runtime
  helper. Trace NIC open/hardware setup, phylink start, RTNL waits, network
  namespace setup, and kernel synchronization waits. Establish the lock holder
  as well as waiters if RTNL is involved. A blocked `ip` command alone is not
  enough to prove which process owns a lock.
- The generated QM unit, `systemctl cat systemd-hostnamed.service
  user-runtime-dir@0.service`, network backend configuration, actual device
  tree topology, resolver configuration and effective SSH options.

Run independent collectors so that a network-query command blocked inside the
kernel does not prevent collecting stacks or packet evidence. Use local/serial
control because SSH itself is one of the affected paths.

## Reproduction artifacts

Run `python3 analyze_qm_network.py` in the workspace. It generates
`network-boots.csv`, `network-summary.json`, `network-details.json`, and
`network-timelines.txt` in `qm-analysis/`. The details file includes individual
SSH PID pairs and longer gaps between NetworkManager messages, with both export
timestamps and embedded NetworkManager realtime timestamps where available.
