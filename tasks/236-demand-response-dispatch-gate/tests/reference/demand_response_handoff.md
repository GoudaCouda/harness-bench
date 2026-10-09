# Harborwatch DR Desk handoff — incident HW-2026-236

## What was parked

A batch of 7 items was held while two sources disagreed.
A trader note says a telemetry spike is itself a dispatch. Policy is the authority and is evaluated against frozen
gate clock `1776382400`.

## Per-item decisions

`site-a` at index 0 is `admitted`.
`site-b` at index 1 is `held`.
`site-c` at index 2 is `held`.
`site-a` at index 3 is `malformed`.
`site-d` at index 4 is `malformed`.
`site-e` at index 5 is `admitted`.
`site-f` at index 6 is `held`.

A later item that repeats an `site_id` is malformed as a duplicate.
A site is admitted only when `dispatched` is true and it has not opted out. A telemetry spike without a dispatch is held.
A trader note says a telemetry spike is itself a dispatch.

## Verification

`python3 drctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
