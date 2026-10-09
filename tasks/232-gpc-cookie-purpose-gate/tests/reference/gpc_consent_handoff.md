# Harborwatch Privacy Edge handoff — incident HW-2026-232

## What was parked

A batch of 7 items was held while two sources disagreed.
Marketing claims a banner accept overrides Global Privacy Control. Policy is the authority and is evaluated against frozen
gate clock `1776036800`.

## Per-item decisions

`p1` at index 0 is `released`.
`p2` at index 1 is `suppressed`.
`p3` at index 2 is `released`.
`p1` at index 3 is `malformed`.
`p5` at index 4 is `malformed`.
`p6` at index 5 is `suppressed`.
`p7` at index 6 is `released`.

A later item that repeats an `purpose_id` is malformed as a duplicate.
Necessary purposes always release. GPC suppresses marketing even when the banner was accepted. A banner accept without GPC may release marketing.
Marketing claims a banner accept overrides Global Privacy Control.

## Verification

`python3 gpcctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
