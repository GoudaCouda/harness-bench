# Repair the distributed lease reconciler

A regional API limiter occasionally grants more units than its fixed capacity
after retries and lease expiry. Repair the local reconciler; do not contact or
modify a live limiter.

Work only inside `repo/`. Read `repo/docs/lease_contract.md`, the implementation,
visible batches, and public tests before editing.

Deliver:

1. Repair `repo/src/lease_reconciler.py` while preserving
   `reconcile_leases(state, requests, now_ms)`. It must expire leases at the
   exact boundary, preserve active idempotent replays, reject conflicting reuse
   of a request ID, allocate new requests in deterministic FIFO order, conserve
   capacity, and issue monotonic fencing tokens without mutating inputs.
2. Create `repo/reconciliation_report.json`, an array matching the visible batch
   order. Each item contains `batch_id` and the exact returned result.
3. Create `repo/REPAIR_NOTES.md` explaining expiry, replay, fairness, fencing,
   the verification command/result, and one integration risk.

Run from `repo/`:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not edit contracts, batches, or tests. Do not claim a production rollout or
live quota mutation.
