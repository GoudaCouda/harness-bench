# Online migration handoff

The planner preserves expand-contract order: create a nullable target, deploy all-version dual write, repair mismatches, finish bounded backfill, add the check constraint as `NOT VALID`, validate it, cut reads over, disable old writes, prove and set non-null, then consider contraction. A count alone is insufficient if the cursor or mismatch ledger disagrees.

Replica lag and lock waiters block database actions but do not block application rollout steps. Old-column removal additionally requires contract policy, zero old-read QPS, enough stable observation windows, every reader on the target, and no old writers. Snapshot counts and schema state are monotonic, so stale or impossible evidence fails closed.

Verification ran `python -m unittest discover -s tests -p 'test_*.py'`, `python bin/plan_migration.py`, and JSON parsing of decisions and summary; all passed. This is an offline plan: no PostgreSQL connection or DDL ran, no application was deployed, and no production column was changed or dropped.
