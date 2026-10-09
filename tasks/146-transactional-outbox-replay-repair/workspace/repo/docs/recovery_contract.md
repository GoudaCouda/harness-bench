# Transactional outbox recovery contract

Implement `recover_outbox(events, receipts, policy)` without mutating inputs.
Exact structural violations raise `ValueError` before producing partial output.

Policy has exact keys `now` (nonnegative integer seconds), `worker` (nonempty
lowercase token), `lease_seconds` (1..86400), and `max_attempts` (1..20).
Each event has exact keys `event_id`, `aggregate_id`, `sequence`, `payload_hash`,
`status`, `attempts`, `lease_owner`, `lease_until`, and `last_error`. IDs are
nonempty lowercase tokens, sequence is positive, and payload hashes are 64
lowercase hexadecimal characters. `(aggregate_id, sequence)` and `event_id`
are unique. Status is `pending`, `leased`, `sent`, or `dead`.

Pending rows have attempts below the maximum and null lease fields. Leased rows
have attempts 1..maximum, a token owner, and a nonnegative integer deadline.
Sent rows have at least one attempt and null lease fields. Dead rows have exactly
the maximum attempts and null lease fields. `last_error` is null or a nonempty
string of at most 200 characters.

Each receipt has exact keys `event_id`, `attempt`, `outcome`, `payload_hash`, and
`observed_at`. Outcome is `acked`, `rejected`, or `unknown`; observed time is a
nonnegative integer no later than policy `now`. A receipt must reference the
same payload and an existing attempt. Exact duplicates are deduplicated, but
different receipts for one `(event_id, attempt)` are contradictory and make the
whole batch invalid.

Any acknowledgement, including a late acknowledgement for an older attempt,
makes an event `sent`, clears lease fields and error, and may expose its next
aggregate sequence. Otherwise only a receipt for the current attempt controls
recovery. An `unknown` current outcome emits `probe` and never republishes. An
active lease (`lease_until > now`) remains leased. A current rejection or an
expired lease without a receipt becomes retryable unless attempts are exhausted;
exhaustion changes it to `dead` and emits `dead_letter`.

Within each aggregate, only its earliest event not already `sent` or `dead` may
receive an action. Later events are blocked even when otherwise ready. A pending
head is claimed for `publish`: increment attempts, set status `leased`, assign
the policy worker, set deadline to `now + lease_seconds`, and clear error.
Rejection records `last_error` as `rejected` before retry/dead-letter handling.
At most one action is emitted per aggregate.

Actions are sorted by `(aggregate_id, sequence, type)` and contain exact keys
`type`, `event_id`, `attempt`, `idempotency_key`, and `payload_hash`.
`idempotency_key` is always the event ID. `probe` uses the current attempt and
does not mutate event state. `dead_letter` uses the exhausted current attempt.

Return `{"state": [...], "actions": [...]}`. State preserves input event order.
No clock read, network, broker, database, filesystem, process, or random access
is allowed.
