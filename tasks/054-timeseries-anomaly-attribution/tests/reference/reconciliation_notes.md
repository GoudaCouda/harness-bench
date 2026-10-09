# Reconciliation notes

The recommendations row is a low-volume signal and was suppressed even though two z-scores cross their statistical cutoffs.

At 2026-04-20T11:30:00Z, checkout overlaps both deployment D-443 and third-party incident I-20. The priority rule selects deployment:D-443; the competing incident makes that attribution uncertain. More generally, temporal correlation is not proof of causation, so each cause remains a likely attribution rather than a demonstrated mechanism.

The two profile metrics remain unattributed because no listed event overlaps
their service, region, and time. Revenue impact is counted once for every
flagged anomaly row, including both profile metrics.
