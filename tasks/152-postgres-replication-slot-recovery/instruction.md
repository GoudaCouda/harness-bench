# Repair logical replication-slot recovery planning

A database runbook drops invalid or oversized logical slots too aggressively,
risking silent consumer data loss and unsafe failover. Work only in
`/workspace/repo`.

Read `docs/slot_contract.md`, inspect the synthetic slot/consumer observations,
policy, runner, and public tests, then repair `src/slot_recovery.py` as a general
pure implementation. Run the public tests and `python bin/plan_recovery.py`;
re-parse `out/plans.json` and `out/summary.json`. Write `RECOVERY_NOTES.md`
covering WAL retention, invalidation, consumer checkpoints, failover sync,
active-slot safety, rebuild prerequisites/order, resume behavior, validation,
commands/results, and the offline/no-database boundary.

Do not connect to PostgreSQL, execute SQL, drop/create a slot, advance an LSN,
restart a consumer, edit evidence, or claim production recovery.
