# Incident HW-2026-231: parked batch

## What happened

A batch arrived while two sources disagreed. The items are parked in
`staging/release_queue.json` and have not been handed off.

An author note says a preprint DOI is already the published version. That note is not a policy change.

## What we know

- `staging/release_queue.json` is the parked stream.
- The published rule is in `policy.md`.

## What we do not know

Live production state is not observable. Do not attempt to reach Harborwatch Research Office
production.

## Requested outcome

A practitioner-readable record: one decision per item, evidence that the drain
was verified rather than asserted, and a written explanation of why the
look-alike signal still lost.
