# RPC budget contract

`plan_rpc_budget(calls, policy)` is pure and returns exactly
`{"decisions": [...], "summary": {...}}` without mutating arguments.

Calls have the exact sample-ledger schema and sorted unique lowercase IDs.
Methods are `/Service/Method` ASCII names. Millisecond and count fields are
non-negative integers, incoming timeout is positive, `elapsed_ms` may reach or
exceed it, NOT_STARTED uses attempt 0, and every other status uses attempt at
least 1. Statuses are NOT_STARTED, OK, CANCELLED, DEADLINE_EXCEEDED,
UNAVAILABLE, RESOURCE_EXHAUSTED, ABORTED, FAILED_PRECONDITION, or INTERNAL.
Operation scope is `single_call` or `parent_operation`.

Policy has exactly `max_attempts`, `per_try_timeout_ms`, `reserve_ms`,
`base_backoff_ms`, `max_backoff_ms`, and sorted unique
`retryable_statuses`. Positive limits and `base_backoff_ms <= max_backoff_ms`
are required.

The first applicable rule wins. OK settles and keeps the result. Caller
cancellation stops the call and cancels all active child RPCs. No other action
is possible when `incoming_timeout_ms - elapsed_ms <= reserve_ms`. NOT_STARTED
then starts immediately. Response headers commit a prior attempt and block
retry. ABORTED in a parent operation escalates a parent restart. Remaining
statuses must be retryable, idempotent, and below the attempt limit.

Retry delay is `min(max_backoff_ms, base_backoff_ms * 2 ** (attempt - 1))`.
It is deducted with elapsed time and reserve from the original incoming
timeout. A non-positive remainder blocks. Start/retry timeout is the smaller of
`per_try_timeout_ms` and that remainder; the incoming deadline is never reset.

Each decision has exactly `call_id`, `status`, `action`, `reason`, `delay_ms`,
`timeout_ms`, and `cancel_child_rpcs`. Settled uses `keep_result/rpc_ok`; stopped
uses `cancel_children/caller_cancelled`; ready uses `start_call/not_started` or
`retry_call/retryable_failure`; blocked actions are `do_not_retry` except
ABORTED parent scope uses `restart_parent/restart_parent_operation`. Summary has
exactly `call_count`, `settled`, `ready`, `blocked`, `stopped`, `retry_count`,
and `cancelled_child_rpcs`.
