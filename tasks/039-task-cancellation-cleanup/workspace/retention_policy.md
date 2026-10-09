# Cancellation and evidence retention

- A verified notice governs only its request. When `include_child_attempts` is true, scope includes every descendant in the fanout index even if it is absent from the notice's initial job list. Fence the request generation before draining workers so no further child can be accepted.
- Active worker leases move through `active -> draining -> released`. Cancellation is forbidden until every scoped lease has a checkpoint-confirmed release.
- Withdraw in-scope transfers in `pending` or `preparing`; retain an in-scope `delivered_receipt` record for escalation and never rewrite unrelated transfers.
- Manifest entries classified `row_data` are purged unless `legal_hold` is true. `transient_credential` artifacts are always purged. `audit_receipt` and legal-hold artifacts are retained in place.
- `cleanup_plan.csv` must classify every manifest artifact exactly once. A purge row requires the manifest evidence ID; retain rows must explain audit or hold authority.
- Preserve the source manifest, notice, fanout index, source evidence, and entire audit prefix. Tool-generated events are deterministic and append-only. Every delivered receipt remains non-cancellable and requires a distinct handoff disposition. Local state transitions do not prove an external recipient or customer was contacted.
