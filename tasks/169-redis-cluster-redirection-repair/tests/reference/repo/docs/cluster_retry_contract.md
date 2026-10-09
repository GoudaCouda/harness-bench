# Redis Cluster retry planning contract

Implement `plan_cluster_retries(requests, slots, policy)` without mutation,
I/O, clocks, or environment access. Inputs and outputs use JSON values.

## Exact schemas

`slots` is sorted by unique integer `slot` values from 0 through 16383. Each
record has exactly `slot` and lowercase ASCII token `node`; sparse caches are
valid.

`policy` has exactly positive integer `max_attempts`, `base_backoff_ms`, and
`max_backoff_ms`, plus non-negative integer `reserve_ms`. Booleans are not
integers. Base backoff must not exceed maximum backoff.

`requests` is sorted by unique lowercase ASCII `request_id`. Each record has
exactly `request_id`, uppercase ASCII `command`, sorted unique non-empty
`key_slots`, lowercase token `target_node`, `outcome`, `redirect_slot`,
`redirect_node`, positive integer `attempt`, boolean `idempotent`, boolean
`result_received`, and non-negative integer `deadline_remaining_ms`. Slots are
0 through 16383. Outcome is `OK`, `MOVED`, `ASK`, `TRYAGAIN`, `READONLY`,
`CLUSTERDOWN`, `TIMEOUT`, or `UNASSIGNED`. MOVED and ASK alone require a
redirect slot and node; all other outcomes require both redirect fields null.
OK alone requires `result_received: true`; all errors require false.

## Decision precedence

Return one decision per request, in order, with exactly `request_id`, `action`,
`reason`, `target_node`, `send_asking`, `update_slot`, `next_attempt`, and
`backoff_ms`.

1. More than one distinct key slot is `block` / `cross_slot`, even if an error
   was observed. A valid OK is `complete` / `response`.
2. A MOVED or ASK whose redirect slot differs from the command slot is
   `block` / `redirect_slot_mismatch`. A valid MOVED permanently updates that
   slot in the working cache, even when the retry is later blocked. ASK never
   updates the cache.
3. Any retry at `attempt >= max_attempts` is `block` / `attempt_budget`.
4. MOVED and ASK require `deadline_remaining_ms > reserve_ms`. Otherwise block
   with `deadline_budget`. A valid redirect uses `retry_redirect`; MOVED has
   reason `moved` and no ASKING, while ASK has reason `ask`, targets only the
   redirected request, and sets `send_asking: true`.
5. TRYAGAIN uses exponential backoff
   `min(base_backoff_ms * 2 ** (attempt - 1), max_backoff_ms)` and
   `retry_backoff` / `tryagain`. The deadline must be strictly greater than
   backoff plus reserve.
6. READONLY and UNASSIGNED use `refresh_and_retry` with reasons `readonly` and
   `unassigned`, no backoff, and the same strict reserve check.
7. CLUSTERDOWN and TIMEOUT are ambiguous for this planner. A non-idempotent
   command is `block` / `ambiguous_non_idempotent`; otherwise it uses the same
   exponential backoff and deadline rule, with reasons `clusterdown` and
   `timeout`.

Blocked and complete decisions have null target/attempt, false ASKING, and zero
backoff. `update_slot` is null except for a valid MOVED, where it is exactly
`{"slot": integer, "node": token}` even if action is blocked. Every retry
increments the attempt by one. Refresh retries keep `target_node` null because
the refreshed topology chooses it.

Return final `slots` sorted by slot after sequential MOVED updates. Summary is
exactly `request_count`, `complete`, `retry_redirect`, `retry_backoff`,
`refresh_and_retry`, `block`, and `topology_updates`.
