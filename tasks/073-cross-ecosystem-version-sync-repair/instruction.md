# Repair cross-ecosystem release version synchronization

A release tag is authoritative, but a Python distribution, npm package, and
Cargo crate currently translate and compare it inconsistently. Repair the
offline planner before anyone edits manifests or publishes artifacts.

Work only in `repo/`. Preserve
`plan_version_sync(release_tag, previous_tag, manifests)`. Read the contract,
broken source, visible incidents, and public tests.

Deliver repaired `repo/src/version_sync.py`, ordered `repo/version_plan.json`
with every visible `case_id` and exact result, and `repo/REPAIR_NOTES.md`.
Explain tag authority, strict monotonic precedence, Python versus SemVer
pre-release spelling, atomic manifest coverage, malformed-input blocking,
verification, and residual publisher/lockfile risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not edit captured evidence, manifests, lockfiles, tags, registries,
or publish anything.
