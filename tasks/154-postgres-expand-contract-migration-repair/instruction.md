# Repair an online expand-contract migration planner

A schema rollout may validate or drop columns while old application versions
still read or write them, and it ignores replica lag before lock-taking steps.
Work only in `/workspace/repo`.

Read `docs/migration_contract.md`, inspect the ordered rollout snapshots,
policy, runner, and public tests, then repair `src/migration_planner.py` as a
general pure implementation. Run public tests and `python bin/plan_migration.py`;
re-parse `out/decisions.json` and `out/summary.json`. Write
`MIGRATION_NOTES.md` covering expand/dual-write/backfill, mismatch repair,
`NOT VALID` and validation, read cutover, old-write removal, non-null proof,
contract observation, load blockers, validation, commands/results, and the
offline/no-database boundary.

Do not connect to PostgreSQL, execute DDL, deploy an application, drop a column,
edit evidence, or claim production migration.
