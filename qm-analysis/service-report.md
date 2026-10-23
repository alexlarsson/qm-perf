# Startup-duration outliers across services

All 299 boot records contain 15,309 `saplot` service observations across 54
service names. The comparison uses each unit's activation duration, not its
absolute position in the boot or the journal entry's `time` field.

For a reproducible screen, a review candidate must exceed both three times its
own service median and that median plus one second. This selects conspicuous
deviations; it is not a statistical significance test or a proof that smaller
variations are irrelevant. Zero-duration units provide no useful measured
activation interval.

The main additional findings, beyond QM, NetworkManager, hostnamed and sshd:

| Service | Recorded observations | Median | Maximum | Candidate boots, run/index |
| --- | ---: | ---: | ---: | --- |
| `user-runtime-dir@0.service` | 299 | 0.150 s | 32.579 s | 2/31: 31.663 s; 2/66: 32.579 s; 3/26: 30.657 s |
| `mount-sysroot.service` | 299 | 0.200 s | 32.367 s | 2/35 |
| `sshd-keygen@rsa.service` | 99 | 2.129 s | 11.000 s | 2/20: 9.610 s; 2/60: 11.000 s |
| `systemd-journal-flush.service` | 299 | 1.064 s | 3.953 s | 1/6, 1/11, 1/48, 1/93, 2/39, 2/84 |
| `systemd-udevd.service` | 299 | 0.348 s | 2.243 s | 3/2: 2.243 s; 3/4: 2.151 s |
| `systemd-vconsole-setup.service` | 299 | 0.446 s | 1.751 s | 3/66 |

Indexes are zero-based, matching `query.jq`. RSA key-generation service timings
are recorded only in run 2; missing observations in the other runs were not
treated as zero-duration starts. This table shows six additional service names,
with fifteen candidate observations under the screen above.

## The two largest additional delays

`user-runtime-dir@0.service` creates the local runtime directory for root's
session. Its three outliers agree closely with the journal Starting/Finished
message intervals. Two coincide with QM startup failure (run 2 boot 66 and run
3 boot 26). In run 2 boot 31, QM starts successfully in 3.843 s and the runtime
directory delay occurs afterward. The outlier is in the runtime-directory
service, rather than necessarily in `user@0.service` itself.

`mount-sysroot.service` is an initrd service. Run 2 boot 35 records activation
from 5.184249 s to 37.551007 s, a 32.366758 s duration. The independent
`systemd-dbus` phase record reports 33.621237 s spent in InitRD, corroborating a
large initrd delay. The root-system NetworkManager and QM services start later;
QM then completes successfully in 3.727 s. Buffered initrd journal messages do
not locate the time spent inside the mount service, so these records cannot
identify a filesystem operation, device wait, or other blocked function.

## SSH startup versus SSH session opening

The actual `sshd.service` activation median is 0.170 s and maximum 1.210 s
(run 2 boot 36). It has one candidate under this screen. The much larger SSH
delays discussed earlier concern authenticated sessions opening, or, in the
new RSA examples, the separate key-generation service that precedes daemon
startup. A daemon starting late in the boot is distinct from taking a long
time between its own Starting and Started events.

## Timing validation and limitations

Some journal records have `activating` equal to the boot's configured offset
and `time=0`. For example, run 1 boot 6's vconsole Starting message is stamped
4.091893 s, whereas the unit activation begins at 14.035105 s. Naively
subtracting that journal start from its completion yields 11.181 s; the unit
duration is actually recorded as 1.237 s. Similar disagreements occur in
several other boots. These were not counted as 10–11 second console outliers.

Failed/restarted QM unit spans can also be misleading. Six QM-timeout boot
records were retained in `service-starts.csv` but excluded from QM summary
statistics. The six original failures remain established by the journal.
Hostnamed's known failed boot remains labeled as a startup failure, rather
than a slow successful start. Service summaries do not establish what happened
inside an executable, and a short startup duration does not demonstrate that
the service remained responsive later.

For comparison, services without similar large activation deviations include:

| Service | Median | Maximum |
| --- | ---: | ---: |
| `user@0.service` | 2.194 s | 2.845 s |
| `systemd-logind.service` | 1.182 s | 1.381 s |
| `dbus-broker.service` | 0.149 s | 0.164 s |
| `chronyd.service` | 0.387 s | 0.552 s |

Thus the long-delay population includes local runtime-directory setup and an
initrd root mount, in addition to network-related services. That widens the
set of operations to trace; it does not prove a shared cause.

## Reproduction

Run `python3 analyze_qm_services.py` in the workspace to regenerate:

- `qm-analysis/service-summary.csv`: all 54 service summaries.
- `qm-analysis/service-starts.csv`: every recorded unit activation.
- `qm-analysis/service-outliers.csv`: all 19 candidates, including the four
  candidates in the previously discussed NetworkManager, hostnamed and sshd
  services.
