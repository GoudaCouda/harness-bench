# Prepare an anomaly and incident-attribution brief

You are the service reliability analyst. An operations review needs a defensible list of anomalous service-hours and a cautious attribution to deployments or known events.

Your job is to apply the approved detection rules, suppress low-volume noise, and reconcile anomaly-level evidence with an executive incident brief.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs include:
- `deployments.csv`
- `detection_rules.md`
- `hourly_metrics.csv`
- `incident_calendar.csv`

## Deliverables

- `anomalies.csv`: Use columns anomaly_id, timestamp, service, region, metric, observed, expected, z_score, severity, attributed_cause.
- `attribution_summary.json`: Summarize anomaly_ids, cause_counts, high_severity_count, total_revenue_impact_usd, and unattributed_anomaly_ids.
- `reconciliation_notes.md`: Explain suppression, overlapping evidence, unresolved anomalies, and the correlation-versus-causation limitation.

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Use the supplied expected values and z-scores. Apply request-volume thresholds before declaring an anomaly.
2. Use the metric order and deterministic anomaly IDs stated in detection_rules.md; severity is high at absolute z-score 6 or above.
3. Attribute overlapping events in this order: deployment, third-party incident, marketing/calendar, otherwise unattributed; retain overlap uncertainty in the brief.
4. Compute the revenue-impact total according to the service-hour deduplication
   rule in `detection_rules.md` and round currency to two decimals.

Keep all source evidence byte-for-byte unchanged except for a path explicitly named as an in-place deliverable. Work offline. Do not execute or claim an external, production, payment, filing, deletion, message-send, booking, or account action. Before finishing, re-open the final CSV/JSON files and reconcile their keys and totals across the handoff.
