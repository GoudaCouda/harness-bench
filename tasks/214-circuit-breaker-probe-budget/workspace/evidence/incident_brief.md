# Incident NH-2026-0320-01: RPC stream held at the circuit breaker

## What happened

Overnight partner RPC traffic arrived as a single failure stream while
`svc-a` was already accumulating consecutive failures. The stream was parked
in `staging/rpc_events.json` and has not been forwarded.

Partner success management wrote that `e5` "should be treated as a close
because it is a success after the third failure." That note is not a cooldown
expiry. The published cooldown is the only reopen mechanism.

## What we know

- `staging/rpc_events.json` is the parked stream currently loaded by the
  breaker.
- Threshold, cooldown, and probe budget are published in `policy.md`.
- The stream mixes two services, a success that arrives during cooldown, a
  probe that fails, and a later probe that succeeds.

## What we do not know

Live processor state is not observable. Do not attempt to reach Northharbor
production or the partner.

## Requested outcome

Operations needs an auditor-readable breaker record: one decision per event, a
forwarded-id list that never includes a short-circuited call, evidence that the
breaker was verified rather than asserted, and a written explanation of why
the cooldown still held for `e5`.
