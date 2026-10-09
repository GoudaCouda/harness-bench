# Repair SQLite migration transaction recovery

A migration worker retried from the failed statement after `SQLITE_BUSY` and
may duplicate work after an unknown commit result. Repair the offline recovery
planner before another database connection is opened.

Work only in `repo/`. Preserve
`plan_migration_recovery(migration, db_state, observation)`. Read the contract,
broken source, visible incidents, and public tests.

Deliver repaired `repo/src/migration_recovery.py`, ordered
`repo/recovery_plan.json` with every visible `case_id` and exact result, and
`repo/REPAIR_NOTES.md`. Explain `BEGIN IMMEDIATE`, phase-sensitive `BUSY`
handling, rollback versus commit retry, unknown-commit probing, ledger and
`user_version` idempotency, verification, and residual executor risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. The visible suite applies a clean returned plan to a disposable local
SQLite database and verifies the schema, ledger, and `user_version`. You may
create disposable SQLite fixtures under `/tmp`; do not edit captured state,
delete a journal/WAL, migrate a non-fixture database, deploy, or claim a
production action.
