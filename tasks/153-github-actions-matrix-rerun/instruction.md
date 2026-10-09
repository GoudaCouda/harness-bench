# Repair matrix workflow rerun planning

A CI recovery helper either reruns an entire workflow or only the visibly failed
matrix cell, leaving skipped dependents and stale artifacts behind. Work only in
`/workspace/repo`.

Read `docs/rerun_contract.md`, inspect workflow/run evidence, policy, runner,
and public tests, then repair `src/rerun_planner.py` as a general pure
implementation. Run public tests and `python bin/plan_rerun.py`; re-parse
`out/plan.json` and `out/summary.json`. Write `RERUN_NOTES.md` covering DAG
order, matrix fan-in, direct failure/cancellation, skipped propagation, stale
artifacts, side-effect/manual boundaries, validation, commands/results, and the
offline/no-GitHub boundary.

Do not call GitHub, dispatch or rerun a workflow, approve a deployment, edit
evidence, or claim any CI state changed.
