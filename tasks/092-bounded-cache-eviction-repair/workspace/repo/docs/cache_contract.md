# Bounded cache replay contract

Implement pure `replay_cache(state, operations, policy)` without mutating
arguments. Inputs must be fully validated before replay; otherwise raise
`ValueError` and perform no partial work.

`policy` is exactly positive integer `capacity` and `max_entry_size`, with the
latter no greater than capacity. `state` is exactly non-negative integer
`clock`, positive integer `next_access`, and `entries`. Entry keys are non-empty
strings. Each entry has exactly JSON `value`, positive integer `size`,
non-negative integer `expires_at`, non-negative integer `last_access` less than
`next_access`, and boolean `pinned`. Total initial size cannot exceed capacity.
Integers never accept booleans.

Operations are exact objects:

- `advance`: `{"op":"advance","to":N}`, where N is not before current clock;
- `get`: `{"op":"get","key":"..."}`;
- `put`: key, JSON value, positive size, positive integer TTL, and boolean pinned;
- `unpin`: key.

At the start of every operation remove entries with `expires_at <= clock`. An
advance first sets the new clock and then applies the same boundary. Every
event includes sorted `expired`, plus its operation fields and status.

A hit returns a deep-copied value, sets `last_access` to `next_access`, then
increments it. A miss does not. Unpin reports `updated` or `missing` without
changing recency.

A put larger than either size limit is `rejected_size`. Otherwise plan against
a copy with the same key temporarily removed. Evict unpinned entries by
`(last_access, key)` until the candidate fits. If pinned capacity still blocks
it, return `rejected_capacity` and preserve every non-expired entry, including
an older value for the same key; no planned victim is removed. A successful
put commits planned evictions, stores expiry `clock + ttl`, stamps current
`next_access`, increments it, and reports sorted `evicted`.

Return exactly `{"state": canonical_state, "events": events}` with entry keys
in lexical order. Event shapes are demonstrated by the protected runner and
public tests; do not add fields.
