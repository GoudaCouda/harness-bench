# Job journal handoff — incident RW-2026-0319-01

## What arrived

A completion stream of eight events arrived out of `seq` order after the
Ridgeway dispatcher stalled. `job-b` completed before `job-a`. `job-d` failed
on attempt 1; a later event tries to mark that same attempt succeeded.

Evaluated at journal clock `1773910800`.

## Decisions

| Event | Job | Decision | Why |
|---|---|---|---|
| `c1` | `job-b` | `held` | `job-a` had not succeeded yet. |
| `c2` | `job-a` | `applied` | No dependencies. Drain then applies the held `job-b`. |
| (drain) | `job-b` | `applied` | Dependency now succeeded. |
| `c3` | `job-c` | `applied` | `job-b` had just succeeded. |
| `c4` | `job-d` | `applied` | Independent job failed on attempt 1. |
| `c5` | `job-e` | `blocked` | `job-d` is failed. |
| `c6` | `job-a` | `replayed` | Duplicate ack of the same attempt and status. |
| `c7` | `job-d` | `stale` | Same attempt cannot promote `failed` to `succeeded`. |
| `c8` | `job-x` | `rejected` | Unknown job. |

Succeeded jobs: `job-a`, `job-b`, `job-c`. Failed: `job-d`. `job-e` and
`job-f` remain pending. `job-e` was not marked succeeded.

## Verification

`python3 journalctl.py validate` was run twice. Both attempts reported `pass`.
Replaying the same stream against the final job table does not change terminal
statuses. Both runs are recorded in `state/verification.json`.

## Boundary

This was an offline local journal reconciliation. CI was not contacted, no
requester was notified, no ticket was filed, and no audit evidence was deleted.
