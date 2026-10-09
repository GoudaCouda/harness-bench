# Repair workspace dependency resolution

A lock refresh for a cross-platform monorepo upgrades valid packages, installs
Linux-only optional tooling on Windows, and accepts an incompatible peer set.
Repair the local deterministic resolver.

Work only in `repo/`. Read the contract, implementation, visible incidents, and
public tests. Preserve `resolve_workspace(manifest, registry, current_lock, target)`.

Deliver a repaired `repo/src/resolver.py`, an ordered
`repo/resolution_report.json` containing each visible `case_id` and exact result,
and `repo/REPAIR_NOTES.md`. The notes must explain peer constraints, optional and
platform handling, lock preservation, verification command/result, and risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not edit evidence or claim registry publication/lock deployment.
