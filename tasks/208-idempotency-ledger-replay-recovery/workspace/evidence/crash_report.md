# Incident NC-2026-0314-02: settlement replay worker lost mid-batch

## What happened

`settle-worker-7` was draining the overnight settlement replay queue when the
host was fenced. The process died without unwinding its own leases, so the
ledger it left behind mixes three eras: records it finished, records it had
claimed but never completed, and records that were already stale before the
batch started.

A second worker, `settle-worker-4`, is still running and holds at least one
lease of its own. Nothing in this incident authorizes taking work away from it.

## What we know

- The ledger snapshot in `state/ledger.json` is the last durable state.
- The queue in `staging/replay_queue.json` was never acknowledged, so every
  request in it still needs a decision.
- At least one queued request reuses a key that was already settled with a
  different amount. Finance flagged it as a suspected duplicate-submission bug
  upstream; it must not become a second settlement.
- Retention was last swept before the batch, so expired records are still
  physically present in the snapshot.

## What we do not know

The processor-side state is not observable from this host. Treat the ledger and
the policy as the only authority, and do not attempt to reach the processor.

## Requested outcome

Finance needs a reconciliation they can hand to the auditor: a recovered
ledger, a per-request decision record, evidence that the recovery was verified
rather than asserted, and a written explanation of why no invoice was settled
twice.
