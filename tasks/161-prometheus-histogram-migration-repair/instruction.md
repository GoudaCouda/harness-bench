# Repair a Prometheus histogram migration planner

A telemetry team is migrating classic bucket series to native histograms. Its
planner switches queries during partial rollout, ignores counter resets and
parity drift, and may retire classic emission before consumers are stable.
Work only in `/workspace/repo`.

Read `docs/histogram_contract.md`, inspect metric observations, policy, runner,
and public tests, then repair `src/histogram_migration.py` as a general pure
implementation. Run public tests and `python bin/plan_migration.py`; re-parse
`out/decisions.json` and `out/summary.json`. Write `MIGRATION_NOTES.md` covering
classic and native query shapes, mixed rollout, schema compatibility, counter
resets, parity, consumer readiness, stable windows, query cutover, classic
emission retirement, fraction limitations, validation, commands/results, and
the offline/no-Prometheus boundary.

Do not query Prometheus, reload rules, change scrape configuration, deploy
instrumentation, disable live series, or claim production migration.
