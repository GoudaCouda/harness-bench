# Incident AW-2026-0324-01: case batch held at the content-addressed log

## What happened

Overnight aerodynamic cases arrived as a single batch while a wing name was
repeated with two different lift coefficients. The batch was parked in
`staging/case_batch.json` and has not been recorded.

Lab operations wrote that "the same name always overwrites." That note is not
a digest-identity change. A matching digest is already recorded; a different
digest is a conflict.

## What we know

- `staging/case_batch.json` is the parked batch.
- Canonical digests are sorted-key JSON SHA-256 as published in `policy.md`.
- The batch mixes a matching duplicate, a conflicting payload, an empty
  payload, and a repeated case id.

## What we do not know

Live solver state is not observable. Do not attempt to reach Aerowake
production.

## Requested outcome

The lab needs an auditor-readable case log: one decision per item, a recorded
name list that does not silently overwrite, evidence that the log was verified
rather than asserted, and a written explanation of why the second wing payload
was a conflict.
