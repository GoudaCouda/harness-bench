# Cache repair handoff

Expiration uses the inclusive TTL boundary `expires_at <= clock`, including
after an advance. Successful gets and puts consume the monotonic access counter;
misses, unpins, rejected writes, and expiration do not. Capacity victims are
unpinned entries ordered by last access with lexical key tie-breaking.

Each put plans against a copied state. Existing-key size is removed during
overwrite accounting, but the old value remains authoritative until commit.
If pinned capacity prevents a fit, the put is transactionally rejected without
applying any planned eviction; oversize writes are rejected before planning.
Values are deep-copied and arguments remain immutable. Preflight validation
covers the entire operation sequence, JSON values, integer/boolean distinctions, clock
monotonicity, entry totals, TTL, and policy before replay.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed, as
did `PYTHONDONTWRITEBYTECODE=1 python bin/replay_cache.py`. Both generated JSON
files were parsed again. This offline replay did not change a production cache.
