# GOAWAY retry contract

`plan_goaway_retries(requests, goaway, policy)` is pure and returns exactly
`{"decisions": [...], "summary": {...}}` without mutating arguments.

GOAWAY has exactly `connection_id`, `last_stream_id`, and `error_code`. Client
request stream IDs are unique positive odd integers at most 2^31-1; ledgers are
sorted by request ID. A completed response cannot have a stream ID above the
GOAWAY last-stream ID. `reset_code` is present only for `response_state=reset`.
Requests use exact fields documented in the sample ledger.

Completed responses settle. An unfinished stream above `last_stream_id` was
not processed by the peer and is safe to retry on a fresh connection regardless
of HTTP method, provided its body is replayable. `REFUSED_STREAM` is likewise
definitive non-processing evidence. For streams at or below the boundary, an
unfinished request is ambiguous: configured idempotent methods may retry;
unsafe methods require an idempotency key when policy says so.

Before any retry, the GOAWAY error must be in sorted `retryable_errors`, the
body must be replayable, and `attempt < max_retries`. Completed responses have
precedence over these retry controls. Policies have exactly `max_retries`,
`idempotent_methods`, `require_idempotency_key_for_unsafe`, and
`retryable_errors`.

Each decision has exactly `request_id`, `status`, `action`, `reason`, and
`target`. Settled uses `keep_response/response_complete/none`. Retry uses target
`fresh_connection`: definitive non-processing uses `retry_fresh_connection`
with `goaway_unprocessed` or `refused_stream`; ambiguous idempotent work uses
`retry_fresh_connection/idempotent_ambiguous`; keyed unsafe work uses
`retry_with_idempotency_key/keyed_ambiguous`; policy-permitted unsafe work uses
`retry_fresh_connection/unsafe_policy_allowed`. Blocked uses `do_not_retry`,
target `none`, and the first applicable reason: `goaway_error`, `retry_budget`,
`body_not_replayable`, or `ambiguous_non_idempotent`.

Summary has exactly `request_count`, `settled`, `retry`, `blocked`, and
`highest_retry_stream`; the latter is the highest retried stream ID or null.
