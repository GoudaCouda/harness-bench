# Harborwatch Resolver handoff — incident HW-2026-233

## What was parked

A batch of 7 items was held while two sources disagreed.
A ticket says glue A records outside the zone should still be cached because they are useful. Policy is the authority and is evaluated against frozen
gate clock `1776123200`.

## Per-item decisions

`www.harbor.test` at index 0 is `admitted`.
`gone.harbor.test` at index 1 is `held`.
`ns1.other.test` at index 2 is `held`.
`www.harbor.test` at index 3 is `malformed`.
`loop.harbor.test` at index 4 is `malformed`.
`api.harbor.test` at index 5 is `held`.
`mail.harbor.test` at index 6 is `admitted`.

A later item that repeats an `qname` is malformed as a duplicate.
Positive in-zone answers with TTL > 0 are admitted. NXDOMAIN, zero TTL, and out-of-zone glue are held. A CNAME loop is malformed.
A ticket says glue A records outside the zone should still be cached because they are useful.

## Verification

`python3 dnsctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions. Both runs are recorded in
`state/verification.json`.

## Boundary

This was an offline local decision. No processor was contacted, no funds were
released, no partner was notified, no report was filed, and no evidence was
deleted. The look-alike request in the incident note is reported here and is
not applied.
