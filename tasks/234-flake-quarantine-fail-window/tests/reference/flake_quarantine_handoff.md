# Harborwatch CI handoff — incident HW-2026-234

## What was parked

A batch of 7 items was held while two sources disagreed.
A dashboard treats runner timeouts as failures that should quarantine immediately. Policy is the authority and is evaluated against frozen
gate clock `1776209600`.

## Per-item decisions

`test_login` at index 0 is `recorded`.
`test_search` at index 1 is `conflict`.
`test_pay` at index 2 is `conflict`.
`test_login` at index 3 is `malformed`.
`test_empty` at index 4 is `malformed`.
`test_cart` at index 5 is `recorded`.
`test_broken` at index 6 is `malformed`.

A later item that repeats an `test_id` is malformed as a duplicate.
Three or more assertion failures record the test. Infrastructure errors are not failures. One or two failures remain a conflict, not a quarantine.
A dashboard treats runner timeouts as failures that should quarantine immediately.

## Verification

`python3 flakectl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
