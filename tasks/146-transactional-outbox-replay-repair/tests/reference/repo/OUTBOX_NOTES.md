# Transactional outbox recovery handoff

The repaired planner validates every event and receipt before projecting any
state. Receipt identity is `(event_id, attempt)`: exact duplicate observations
are harmless, but conflicting observations fail the batch. Acknowledgement has
authority even when it arrives for an older attempt, because republishing an
already accepted event would violate the safety objective. A receipt whose
current outcome is `unknown` remains ambiguous and creates a `probe`; it is
never converted directly into another publish.

Lease expiry is evaluated against the supplied policy time, not the machine
clock. Active leases remain untouched. An expired lease without a receipt, or a
confirmed rejection, becomes retryable while attempts remain. Recovery claims
that retry by incrementing the attempt, assigning the recovery worker, and
setting a new lease deadline. Once the retry limit is exhausted, state becomes
`dead` and a deterministic `dead_letter` action is emitted. Publish, probe, and
dead-letter actions all retain the event ID as their idempotency key and preserve
the payload hash.

Per-aggregate ordering is enforced after receipt reconciliation. Only the
earliest event not already sent or dead can act, and at most one action is
planned for an aggregate. This lets a late acknowledgement expose the next
sequence without allowing a pending tail to bypass an active or ambiguous head.
State remains in captured input order while actions use deterministic aggregate
and sequence ordering.

Verification used `python -m unittest discover -s tests` and
`python bin/recover_outbox.py`, followed by parsing `out/state.json` and
`out/actions.json`. Both commands passed and the two JSON artifacts matched a
fresh call to the repaired pure function. This was offline planning only: no
database row was updated, no broker message was published, and no live relay or
consumer was contacted.
