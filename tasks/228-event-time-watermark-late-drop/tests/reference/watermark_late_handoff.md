# Harborwatch Telemetry handoff — incident HW-2026-228

## What was parked

A batch of 7 items was held while two sources disagreed.
A dashboard note says processing_time can rescue a late event because it arrived recently. Policy is the authority and is evaluated against frozen
gate clock `1775691200`.

## Per-item decisions

`d1` at index 0 is `applied`.
`d2` at index 1 is `deferred`.
`d3` at index 2 is `applied`.
`d1` at index 3 is `malformed`.
`d5` at index 4 is `malformed`.
`d6` at index 5 is `deferred`.
`d7` at index 6 is `malformed`.

A later item that repeats an `record_id` is malformed as a duplicate.
A record is applied when `event_time + allowed_lateness >= watermark`. Processing time is ignored. Missing stream identity is malformed.
A dashboard note says processing_time can rescue a late event because it arrived recently.

## Verification

`python3 wmctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
