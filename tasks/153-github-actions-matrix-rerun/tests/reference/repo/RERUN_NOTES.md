# CI rerun handoff

Jobs are processed in deterministic DAG topological order, with every matrix shard kept distinct. A direct failure or policy-enabled cancelled instance is selected directly; job-level needs then create matrix fan-in impact. Skipped downstream work is restored, but unrelated successful shards remain kept.

A successful producer with stale output reruns. A successful downstream job reruns only when it consumes a selected producer, because its artifact is then stale; a control-only dependency does not force replay. Selected deployment or other side-effect work becomes manual approval unless policy explicitly permits it. Manual work remains an impact source for later jobs.

Verification ran `python -m unittest discover -s tests -p 'test_*.py'`, `python bin/plan_rerun.py`, and JSON parsing of plan and summary; all passed. This was offline analysis only: no GitHub API was called, no workflow was dispatched or rerun, no deployment approved, and no CI state changed.
