# HTTP retry planning contract

`request` has exactly `method`, `operation_id`, `body_sha256`,
`idempotency_key`, `key_replay_safe`, `max_attempts`, `base_delay_ms`, and
`max_delay_ms`. Supported uppercase methods are GET, HEAD, PUT, DELETE,
OPTIONS, POST, and PATCH. Operation IDs and optional keys are bounded printable
tokens, the body digest is canonical lowercase SHA-256, retry counts are 1..10,
and delays are strict positive integers with base no greater than maximum.
`key_replay_safe` is Boolean and can be true only for a present key whose
server-side contract guarantees same-key/same-body replay safety.

`attempt_number` starts at 1. `observation` has exactly `outcome`, `status`,
`retry_after_ms`, `application_state`, and `bytes_sent`. Outcomes are
`connect_failure`, `write_failure`, `response_lost`, or `http`. A connect
failure has zero bytes and no response fields. Write failure has no response
fields and may have sent bytes. Response loss has positive sent bytes and no
response fields. HTTP has status 100..599, optional non-negative Retry-After
milliseconds, application state `not_applied`, `unknown`, or `applied`, and
non-negative sent bytes. A 2xx response must say applied.

GET, HEAD, PUT, DELETE, and OPTIONS are idempotent for retry policy. A request
known not sent, or an HTTP response saying not applied, can retry regardless of
method. Otherwise unknown outcomes may automatically retry only for an
idempotent method or an enforced idempotency key. Unsafe unknown POST/PATCH
returns `probe`. Successful 2xx returns `success`; applied operations and
non-retryable statuses return `stop`. Retry statuses are 408, 425, 429, 500,
502, 503, and 504. Exhaustion stops before another attempt.

Delay is capped exponential backoff for the current attempt, then raised to a
larger Retry-After. If Retry-After exceeds the automatic wait budget
`max_delay_ms`, return `defer` with the server delay rather than retrying early.
The result schema is exercised by visible incidents and public tests. The
function is pure and may import only `re`; it makes no HTTP request or replay.
