# Repair the versioned settings importer

An application upgrade must import settings exported by three historical
versions. The current migrator collapses missing and explicit-null values,
mutates caller data, and silently accepts malformed documents.

Work only in `/workspace/repo`. Read `docs/import_contract.md`, inspect the
fixture, runner, and public tests, then repair `src/import_migrator.py` as a
general pure implementation. Do not hard-code visible source IDs or values.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python bin/run_import.py
```

The final runner invocation must create `out/migrated.json` and
`out/rejected.json`; re-parse both. Create `MIGRATION_NOTES.md` explaining
schema dispatch, missing versus explicit null, v2 feature conversion,
extension preservation, canonical v3 output, per-document rejection,
batch-level validation, immutability, exact verification commands, and their
result.

Do not edit the contract, fixture, defaults, runner, or tests. Do not use the
network or filesystem from `src/import_migrator.py`, and do not claim that the
migrated settings were applied to a live service.
