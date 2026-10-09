# Repair a Git submodule recovery planner

A release checkout has uninitialized, mismatched, dirty, conflicted, and nested
submodules. Repair the offline planner so it restores only the superproject's
recorded gitlinks and never discards local work or follows a remote branch tip.

Work only in `repo/`. Preserve
`plan_submodule_recovery(submodules, recursive)`. Read the contract, broken
source, captured states, and public tests.

Deliver repaired `repo/src/submodule_recovery.py`, ordered
`repo/recovery_report.json` with every visible `case_id` and exact result, and
`repo/REPAIR_NOTES.md`. Explain gitlink authority, initialized/mismatched state,
dirty and untracked protection, conflicts, missing objects, recursion, why
remote tips are ignored, exact verification, and residual execution risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not edit evidence, fetch, checkout, reset, clean, push, or claim any
repository mutation occurred.
