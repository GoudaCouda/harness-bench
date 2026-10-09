# Harborwatch Care handoff — incident HW-2026-224

## What was parked

A batch of 7 items was held while two sources disagreed.
An agent note says the word sorry in the ticket is enough to treat the SLA as missed. Policy is the authority and is evaluated against frozen
gate clock `1775345600`.

## Per-item decisions

`t1` at index 0 is `admitted`.
`t2` at index 1 is `held`.
`t3` at index 2 is `held`.
`t1` at index 3 is `malformed`.
`t5` at index 4 is `malformed`.
`t6` at index 5 is `held`.
`t7` at index 6 is `admitted`.

A later item that repeats an `ticket_id` is malformed as a duplicate.
A refund is admitted only when structured `sla_breach` is true, `amount_cents` is at most `cap_cents`, and no chargeback is open. Apology text is not an SLA miss.
An agent note says the word sorry in the ticket is enough to treat the SLA as missed.

## Verification

`python3 carectl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
