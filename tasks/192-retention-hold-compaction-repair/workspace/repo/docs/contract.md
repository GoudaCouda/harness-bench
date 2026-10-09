# Repair retention compaction under legal hold contract

Use event time, not wall-clock receipt. Data expires when event_time+data_ttl <= watermark; tombstones use tombstone_ttl. Legal hold always keeps a record. Sort eligible records by event_time,tenant,id and spend the compaction byte capacity without partial records; overflow is deferred, not deleted. Return id-sorted keep/delete/defer decisions, planned bytes, and remaining capacity. Byte counts and both TTLs must be nonnegative; duplicate ids are prohibited and raise `ValueError`.

The output object has exactly `decisions,planned_bytes,remaining_capacity`. Each id-sorted decision has exactly `id,action,reason,bytes`; action/reason is `keep/legal_hold`, `keep/not_expired`, `delete/expired`, or `defer/capacity`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
