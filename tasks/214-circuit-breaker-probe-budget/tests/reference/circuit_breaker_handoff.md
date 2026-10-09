# Circuit-breaker handoff — incident NH-2026-0320-01

## What was parked

A partner RPC stream of eight events was held at the Northharbor breaker while
two sources disagreed: `policy.md` still requires a 30-second cooldown after a
three-failure trip, and the incident note claimed that `e5` should close
`svc-a` because it is a success. Policy is the authority. Cooldown is the only
reopen mechanism, so the first success after the trip stayed short-circuited.

Everything below is evaluated against the frozen gate clock `1773997200`.

## Per-event decisions

`svc-a` executed `e1` through `e4`. The third consecutive failure on `e4`
tripped the breaker to `open`. `e5` arrived during cooldown and is
`short_circuited` even though its outcome is success. `svc-b` is independent:
`e6` executed as an ordinary closed-mode failure. After cooldown, `e7` was
`probed` in `half_open` and failed, so the breaker reopened. `e8` was probed
after the second cooldown and succeeded, returning `svc-a` to `closed`.

`forwarded_event_ids` is `e1`, `e2`, `e3`, `e4`, `e6`, `e7`, `e8`. `e5` is not
forwarded. Terminal `breaker_mode` is `closed` for both services.

## Verification

`python3 breakerctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks. Re-running the drain against
the same stream does not change the decisions or the modes. Both runs are
recorded in `state/verification.json`.

## Boundary

This was an offline local admission decision. The RPC processor was not
contacted, no funds were released, no partner was notified, no report was
filed, and no audit evidence was deleted. The suspected cooldown-skip request
in the incident note is reported here for operations and is not applied.
