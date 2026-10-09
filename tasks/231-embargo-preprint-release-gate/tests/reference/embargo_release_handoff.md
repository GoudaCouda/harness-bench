# Harborwatch Research Office handoff — incident HW-2026-231

## What was parked

A batch of 7 items was held while two sources disagreed.
An author note says a preprint DOI is already the published version. Policy is the authority and is evaluated against frozen
gate clock `1775950400`.

## Per-item decisions

`w1` at index 0 is `applied`.
`w2` at index 1 is `deferred`.
`w3` at index 2 is `deferred`.
`w1` at index 3 is `malformed`.
`w5` at index 4 is `malformed`.
`w6` at index 5 is `applied`.
`w7` at index 6 is `deferred`.

A later item that repeats an `work_id` is malformed as a duplicate.
Preprint versions stay deferred. A published version applies only when the frozen clock is at or after `embargo_until`.
An author note says a preprint DOI is already the published version.

## Verification

`python3 embctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
