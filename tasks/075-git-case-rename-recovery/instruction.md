# Repair collision-safe Git case renames

A rename batch works on Linux but collapses case-only paths and cyclic swaps on
a case-insensitive checkout. Repair the offline index-preserving planner before
anyone runs Git commands.

Work only in `repo/`. Preserve
`plan_case_renames(entries, requests, ignore_case)`. Read the contract, broken
source, visible incidents, and public tests.

Deliver repaired `repo/src/case_rename.py`, ordered `repo/rename_plan.json`
with every visible `case_id` and exact result, and `repo/REPAIR_NOTES.md`.
Explain `core.ignoreCase`, temporary hops, cycles, object-ID preservation,
collision blocking, verification, and residual filesystem/index risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. The visible suite creates a disposable Git repository under `/tmp`,
applies the returned `git mv` operations, and verifies the real index and blob
OID. You may create your own disposable local repositories under `/tmp`; do not
modify the captured evidence, contact a remote, force an overwrite, reset,
clean, commit outside a disposable fixture, or push.
