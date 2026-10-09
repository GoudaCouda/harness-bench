# Detection rules

Use the provided baseline and z-score columns. A metric is anomalous when its
absolute supplied z-score is at least 3.0, but first suppress any service-hour
with fewer than 100 requests because those rows are known to create false
positives.

Evaluate metrics in this order: `requests`, `error_rate`,
`latency_p95_ms`. Preserve those exact source-column names in the ledger. If a
single service-hour crosses thresholds for more than one metric, report one
anomaly per metric.

Sort detected anomalies by timestamp, service, region, then the metric order
above. Assign IDs sequentially in that order as `A001`, `A002`, and so on.
Severity is `high` when the absolute z-score is at least 6.0 and `medium`
otherwise.

Revenue impact belongs to the affected service-hour, not to each metric.
Therefore sum `revenue_impact_usd` once per distinct flagged
timestamp/service/region even when that row produces multiple anomalies.

Attribution priority:
1. Matching service and region deployment overlap.
2. Matching third-party incident overlap.
3. Matching marketing/calendar overlap.
4. Unattributed.

Overlapping windows are only evidence for likely attribution, not proof of causation.
