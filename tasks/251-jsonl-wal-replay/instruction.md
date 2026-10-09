# Replay the mill key-value WAL

`wal.jsonl` is a write-ahead log for a local mill key-value store. The last
line may be torn. Read `docs/replay_contract.md` and replay the log onto an
empty store.

Write `store.json` using the `key` values already present in valid log
records. Write `replay_report.json` using the `op_id` values from those
records. Create `REPLAY_NOTES.md` covering torn tails, duplicate `op_id`s,
deletes, one verification step, and one remaining risk.

Do not modify `wal.jsonl`, contact a remote store, or claim the mill cache
was published.
