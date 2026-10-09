# Repair transactional plugin lifecycle reconciliation

A local host retained stale hook registrations after a failed plugin upgrade and
now activates dependencies in the wrong order. Work only in `/workspace/repo`.

Read `docs/lifecycle_contract.md`, inspect the catalog, seed state, request,
fault injection, runner, and public tests, then repair
`src/plugin_lifecycle.py` as a general pure implementation. Do not hard-code
visible plugin names or hooks.

Run the public unittest suite and `python bin/reconcile_plugins.py`. The final
run must create `out/state.json` and `out/journal.json`; parse both again. Write
`LIFECYCLE_NOTES.md` covering dependency and reverse-dependent closure,
deterministic ordering, stale registration cleanup, failure rollback, no-op and
generation behavior, strict validation, exact commands, and results.

Do not edit protected inputs or claim that packages were installed, imported,
or changed in a live host. The lifecycle function must not use filesystem,
network, import, or process capabilities.
