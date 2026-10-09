# Ridgeway job-journal policy (authoritative)

Completions may arrive out of order. Apply them only when dependencies have
already succeeded. This document is authoritative.

## 1. Clock

- `journal_clock_epoch` = `1773910800` (2026-03-19T09:00:00Z)

## 2. Jobs

`state/jobs.json` names each job, its `seq`, `depends_on`, `status`
(`pending`, `succeeded`, `failed`), and `attempt`.

A completion event has `job_id`, `attempt`, and `status` (`succeeded` or
`failed`).

## 3. Precedence for one event

1. `rejected` — unknown `job_id` or unknown status.
2. `replayed` — job already terminal with the same attempt and status.
3. `stale` — job already terminal with a different attempt/status, or the
   event's attempt is lower than the recorded attempt.
4. `blocked` — a dependency is `failed`.
5. `held` — a dependency is not yet `succeeded`. Hold the event and re-try
   it after later events apply.
6. `applied` — otherwise. Write `status`, `attempt`, and `updated_at` = clock.

After every `applied` event, drain held events whose dependencies are now
met, in the order they were held.

A later `succeeded` for the same attempt after `failed` is `stale`. Retries
must use a higher attempt; this stream does not.

## 4. Authorization boundary

This is an offline local journal reconciliation. Contacting CI, notifying a
requester, filing a ticket, or deleting audit evidence is outside
authorization.
