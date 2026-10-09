# Reconcile a benchmark revision before the monthly labor briefing

You are the economic-data analyst responsible for updating a briefing built
from preliminary monthly values. A benchmark revision changes the latest
direction of two seasonally adjusted series, while a third published claim
still holds. A non-seasonally-adjusted row is present but is not comparable to
the briefing series.

Use only these files in `$WORKSPACE`:

- `series_metadata.json`
- `preliminary.csv`
- `revised.csv`
- `old_claims.json`

Create these deliverables in `$WORKSPACE`:

- `revisions.csv`, with columns
  `series,month,preliminary,revised,delta,adjustment` in that order and one row
  for every comparable series/month;
- `report_state.json`, containing `vintages_retained`, `series_used`,
  `latest_period`, `claim_decisions`, and `nsa_rows_excluded`;
- `revision_brief.md`, explaining which claims change or remain valid and why.

`series_used` is the array of comparable series used for briefing conclusions.
`claim_decisions` is an object keyed by every ID in `old_claims.json`; each value
must clearly say whether the old claim is retained or withdrawn/replaced and,
when replaced, state the corrected direction. Determine latest-month direction
by comparing May with June within the same series. “Above January” compares
the revised June value with revised January.

Retain both vintages side by side and calculate `delta = revised - preliminary`.
Do not mix seasonal-adjustment identities. The unmatched `EMP_NSA` row may be
omitted from the comparison ledger or kept once with explicit unknown
preliminary and delta values, but it must remain outside every briefing
conclusion. Re-parse and reconcile all artifacts before finishing.

Do not modify source evidence, use the network, or claim that a dashboard,
briefing, or production system was actually updated.
