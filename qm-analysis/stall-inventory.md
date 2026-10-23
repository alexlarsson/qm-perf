# Complete observation inventory

Times are reconstructed seconds since kernel start. Intervals are operation bounds, not exact stall onset. Points are report times. See stall-report.md for interpretation and stall-timeline.html for expandable service context.

| Run/index | Observation | Interval/report (s) | Context anchor (s) | Services starting at anchor |
| --- | --- | --- | --- | --- |
| 1/1 | NetworkManager.service | 11.196–45.750 | 11.196 | NetworkManager.service |
| 1/1 | NIC PTP registration to fixed-link configuration | 13.274–45.731 | 13.274 | NetworkManager.service |
| 1/6 | systemd-journal-flush.service | 7.070–10.695 | 7.070 | systemd-journal-flush.service; systemd-udevd.service |
| 1/11 | systemd-journal-flush.service | 7.078–11.016 | 7.078 | systemd-journal-flush.service; systemd-udevd.service |
| 1/15 | qm.service initial attempt | 13.504–46.183 | 13.504 | NetworkManager-dispatcher.service; qm.service; sshd.service; systemd-user-sessions.service |
| 1/15 | SSH PID 453: accepted key to PAM session | 28.622–48.531 | 28.622 | qm.service |
| 1/15 | chronyd forward time-jump report | 46.125 (report) | 46.125 | qm.service |
| 1/20 | SSH PID 624: accepted key to PAM session | 21.446–52.819 | 21.446 | None observed |
| 1/20 | chronyd forward time-jump report | 52.774 (report) | 52.774 | None observed |
| 1/33 | SSH PID 620: accepted key to PAM session | 20.738–50.360 | 20.738 | None observed |
| 1/33 | chronyd forward time-jump report | 50.312 (report) | 50.312 | None observed |
| 1/42 | qm.service initial attempt | 13.422–46.136 | 13.422 | NetworkManager-dispatcher.service; qm.service; sshd.service; systemd-user-sessions.service |
| 1/48 | systemd-journal-flush.service | 7.062–11.015 | 7.062 | systemd-journal-flush.service; systemd-udevd.service |
| 1/63 | NetworkManager.service | 11.255–45.422 | 11.255 | NetworkManager.service |
| 1/63 | systemd-hostnamed.service | 11.765–45.101 | 11.765 | NetworkManager.service; systemd-hostnamed.service; systemd-logind.service |
| 1/81 | CPU 0 watchdog report, age 30s | 56.170 (report) | 26.170 | None observed |
| 1/93 | systemd-journal-flush.service | 7.058–10.256 | 7.058 | systemd-journal-flush.service; systemd-udevd.service |
| 1/95 | chronyd forward time-jump report | 51.472 (report) | 51.472 | None observed |
| 1/97 | chronyd forward time-jump report | 52.263 (report) | 52.263 | None observed |
| 2/16 | chronyd forward time-jump report | 56.017 (report) | 56.017 | None observed |
| 2/20 | sshd-keygen@rsa.service | 11.354–20.964 | 11.354 | NetworkManager.service; chronyd.service; dracut-shutdown.service; podman-clean-transient-at-shutdown.service; rcu-normal.service; sshd-keygen@ecdsa.service; sshd-keygen@ed25519.service; sshd-keygen@rsa.service |
| 2/20 | SSH PID 649: accepted key to PAM session | 28.110–60.627 | 28.110 | None observed |
| 2/20 | SSH PID 653: accepted key to PAM session | 50.028–60.635 | 50.028 | None observed |
| 2/25 | SSH PID 624: accepted key to PAM session | 19.940–50.670 | 19.940 | None observed |
| 2/31 | SSH PID 525: accepted key to PAM session | 18.068–52.134 | 18.068 | None observed |
| 2/31 | user-runtime-dir@0.service | 18.228–49.891 | 18.228 | user-runtime-dir@0.service |
| 2/31 | SSH PID 558: accepted key to PAM session | 28.834–52.140 | 28.834 | user-runtime-dir@0.service |
| 2/31 | SSH PID 562: accepted key to PAM session | 40.792–52.149 | 40.792 | user-runtime-dir@0.service |
| 2/35 | mount-sysroot.service | 1.128–33.495 | 1.128 | mount-sysroot.service |
| 2/36 | sshd.service | 15.863–17.073 | 15.863 | qm.service; sshd.service |
| 2/39 | systemd-journal-flush.service | 7.060–10.480 | 7.060 | systemd-journal-flush.service; systemd-udevd.service |
| 2/60 | sshd-keygen@rsa.service | 11.449–22.450 | 11.449 | NetworkManager.service; chronyd.service; dracut-shutdown.service; podman-clean-transient-at-shutdown.service; rcu-normal.service; sshd-keygen@ecdsa.service; sshd-keygen@ed25519.service; sshd-keygen@rsa.service |
| 2/66 | qm.service initial attempt | 13.477–48.255 | 13.477 | NetworkManager-dispatcher.service; qm.service; sshd.service; systemd-user-sessions.service |
| 2/66 | SSH PID 467: accepted key to PAM session | 15.541–50.447 | 15.541 | qm.service |
| 2/66 | user-runtime-dir@0.service | 15.715–48.294 | 15.715 | qm.service; user-runtime-dir@0.service |
| 2/83 | qm.service initial attempt | 13.537–46.399 | 13.537 | NetworkManager-dispatcher.service; qm.service; sshd.service; systemd-user-sessions.service |
| 2/83 | chronyd forward time-jump report | 46.299 (report) | 46.299 | qm.service |
| 2/84 | systemd-journal-flush.service | 7.078–10.272 | 7.078 | systemd-journal-flush.service; systemd-udevd.service |
| 2/90 | SSH PID 638: accepted key to PAM session | 21.167–52.703 | 21.167 | None observed |
| 2/94 | SSH PID 617: accepted key to PAM session | 22.281–55.443 | 22.281 | None observed |
| 2/94 | SSH PID 621: accepted key to PAM session | 43.174–55.450 | 43.174 | None observed |
| 2/94 | CPU 7 watchdog report, age 32s | 53.260 (report) | 21.260 | None observed |
| 3/2 | systemd-udevd.service | 6.998–9.240 | 6.998 | systemd-udevd.service |
| 3/4 | systemd-udevd.service | 6.902–9.054 | 6.902 | systemd-udevd.service |
| 3/8 | chronyd forward time-jump report | 52.012 (report) | 52.012 | None observed |
| 3/10 | SSH PID 596: accepted key to PAM session | 20.836–51.661 | 20.836 | None observed |
| 3/10 | chronyd forward time-jump report | 51.611 (report) | 51.611 | None observed |
| 3/26 | qm.service initial attempt | 13.614–45.785 | 13.614 | NetworkManager-dispatcher.service; qm.service; sshd.service; systemd-user-sessions.service |
| 3/26 | SSH PID 458: accepted key to PAM session | 15.137–48.053 | 15.137 | qm.service |
| 3/26 | user-runtime-dir@0.service | 15.259–45.916 | 15.259 | qm.service; user-runtime-dir@0.service |
| 3/26 | SSH PID 465: accepted key to PAM session | 26.478–48.059 | 26.478 | qm.service; user-runtime-dir@0.service |
| 3/34 | hrtimer: interrupt took 7799 ns | 32.525 (report) | 32.525 | None observed |
| 3/35 | SSH PID 625: accepted key to PAM session | 39.654–52.705 | 39.654 | None observed |
| 3/35 | chronyd forward time-jump report | 50.542 (report) | 50.542 | None observed |
| 3/42 | SSH PID 608: accepted key to PAM session | 20.777–52.390 | 20.777 | None observed |
| 3/42 | SSH PID 615: accepted key to PAM session | 42.415–52.488 | 42.415 | None observed |
| 3/42 | chronyd forward time-jump report | 52.343 (report) | 52.343 | None observed |
| 3/62 | qm.service initial attempt | 13.542–43.579 | 13.542 | NetworkManager-dispatcher.service; qm.service; sshd.service; systemd-user-sessions.service |
| 3/66 | systemd-vconsole-setup.service | 9.566–11.316 | 9.566 | systemd-journal-flush.service; systemd-vconsole-setup.service |
