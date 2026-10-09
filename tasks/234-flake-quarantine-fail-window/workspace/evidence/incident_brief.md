# Incident HW-2026-234: parked batch

## What happened

A batch arrived while two sources disagreed. The items are parked in
`staging/flake_batch.json` and have not been handed off.

A dashboard treats runner timeouts as failures that should quarantine immediately. That note is not a policy change.

## What we know

- `staging/flake_batch.json` is the parked stream.
- The published rule is in `policy.md`.

## What we do not know

Live production state is not observable. Do not attempt to reach Harborwatch CI
production.

## Requested outcome

A practitioner-readable record: one decision per item, evidence that the drain
was verified rather than asserted, and a written explanation of why the
look-alike signal still lost.
