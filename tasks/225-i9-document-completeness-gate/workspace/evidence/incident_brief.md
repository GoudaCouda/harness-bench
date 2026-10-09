# Incident HW-2026-225: parked batch

## What happened

A batch arrived while two sources disagreed. The items are parked in
`staging/i9_queue.json` and have not been handed off.

A recruiter note says the last-four SSN in a comment counts as List C. That note is not a policy change.

## What we know

- `staging/i9_queue.json` is the parked stream.
- The published rule is in `policy.md`.

## What we do not know

Live production state is not observable. Do not attempt to reach Harborwatch People Ops
production.

## Requested outcome

A practitioner-readable record: one decision per item, evidence that the drain
was verified rather than asserted, and a written explanation of why the
look-alike signal still lost.
