# Replay contract

`wal.jsonl` is one JSON object per line.

1. If the last line is not a JSON object, drop it and set `torn_tail` true.
   Otherwise `torn_tail` is false.
2. Remaining lines must be objects with `op_id`, `op`, and `key`.
3. `op` is `put` (requires `value`) or `delete`.
4. Each `op_id` applies at most once: the first record wins. Later records
   with the same `op_id` are listed in `skipped_duplicate_op_ids` in log
   order and are not applied.
5. `put` writes `store[key] = value`. `delete` removes `key` if present.
6. `applied_op_ids` lists the `op_id`s that mutated the store, in log order.

Start from an empty store. Do not invent keys or op_ids.
