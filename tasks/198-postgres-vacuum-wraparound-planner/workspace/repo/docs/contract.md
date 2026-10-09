# Repair PostgreSQL vacuum wraparound planning contract

Classify table XID age: normal below warn_age, warning at/above warn_age, emergency at/above emergency_age. Locked tables block. Rank eligible unlocked tables emergency first, then descending age, smaller size, database,id. Allocate a worker and full estimated I/O only when both remain; otherwise defer by workers or I/O without partial work. Return id-sorted decisions, remaining resources, and count of emergency tables not vacuumed. Validate thresholds/resources and duplicate ids with `ValueError`.

The output object has exactly `decisions,workers_remaining,io_remaining_mb,emergency_blocked`. Each id-sorted decision has exactly `id,action,priority`; action is `monitor,blocked_lock,vacuum,defer_workers`, or `defer_io`, and priority is `normal,warning`, or `emergency`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
