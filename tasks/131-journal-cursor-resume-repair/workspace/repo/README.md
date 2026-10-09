# Local journal projection recovery

The consumer writes account deltas from ordered JSONL segments into SQLite. Delivery is at least once. `applied_events.event_id` is the durable idempotency boundary; `consumer_cursor` is an optimization that can lag if a crash happens after the projection transaction but before a cursor-only checkpoint.

Use `python3 tools/journal_recovery.py --help` to inspect available operations. Recovery is offline and transactional. Journal segments, policy, seed evidence, and the utility are protected incident evidence.
