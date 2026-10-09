# Quota window handoff — incident WB-2026-0317-03

## What was parked

A partner batch of eight requests arrived against Westbridge's quota ledger.
Burst is 3 debits in 60 seconds. Daily net is 100000 cents in 86400 seconds.
Finance asked to restore quota from `e1`; that debit left the daily window
(`90000` seconds old) so a refund of it is `refund_expired`.

Evaluated at quota clock `1773738000`.

## Decisions

| Request | Tenant | Decision | Why |
|---|---|---|---|
| `q1` | tn-west | `executed` | Burst had room; daily net stayed under cap. |
| `q2` | tn-west | `executed` | Last burst slot for west. |
| `q3` | tn-east | `executed` | East windows had room. |
| `q4` | (none) | `rejected` | Missing `tenant_id`. |
| `q5` | tn-west | `burst_exceeded` | West burst already 3 after `q1` and `q2`. |
| `q6` | tn-west | `refund_expired` | `e1` is outside the daily window, so it restores nothing. |
| `q7` | tn-east | `daily_exceeded` | East daily net plus `70000` exceeds `100000`. |
| `q8` | tn-west | `burst_exceeded` | West burst still full; `q5` did not consume a slot. |

`executed_debit_cents` is `80000` (`40000 + 10000 + 30000`). Refunds and
refusals contributed nothing.

## Verification

`python3 quotactl.py validate` was run twice. Both attempts reported `pass`.
Replaying the same pending list against the final ledger records those
requests as already present and does not append events or add debit cents.
Both runs are in `state/verification.json`.

## Boundary

This was an offline local quota decision. The payment processor was not
contacted, no funds were released, no partner was notified, no report was
filed, and no audit evidence was deleted.
