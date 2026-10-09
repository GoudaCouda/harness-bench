# Harborwatch Workplace Mail handoff — incident HW-2026-226

## What was parked

A batch of 7 items was held while two sources disagreed.
An owner note says a draft with To: filled already counts as Send As. Policy is the authority and is evaluated against frozen
gate clock `1775518400`.

## Per-item decisions

`m1` at index 0 is `applied`.
`m2` at index 1 is `deferred`.
`m3` at index 2 is `deferred`.
`m1` at index 3 is `malformed`.
`m5` at index 4 is `malformed`.
`m6` at index 5 is `applied`.
`m7` at index 6 is `deferred`.

A later item that repeats an `message_id` is malformed as a duplicate.
Only `sent_as` with `sender` equal to the shared mailbox is applied. `sent_on_behalf` and drafts are deferred. A To: header is not a send.
An owner note says a draft with To: filled already counts as Send As.

## Verification

`python3 mailctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
