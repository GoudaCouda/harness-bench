# Settings migration handoff

The importer dispatches explicitly on schema versions 1, 2, and 3. Version 1
keeps missing `retries` distinct from explicit null: missing uses the configured
default while null becomes zero. Missing region uses the default and explicit
null remains null. Version 2 validates nested identity and connection shapes,
then converts only true feature flags into a sorted enabled-feature list.

Every accepted document is rebuilt as canonical v3 rather than edited in
place. This immutable transformation requires extension keys in the `x-`
namespace and deep-copies finite JSON values, so caller-owned nested data is
neither aliased nor mutated.
Canonical v3 input is validated and sorted idempotently. Known malformed
documents enter a value-free `invalid_document` ledger; unknown schema
versions use `unsupported_version`. Invalid defaults, duplicate source IDs, or
invalid batch envelopes raise before processing.

Verification used `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s
tests -v` and `PYTHONDONTWRITEBYTECODE=1 python bin/run_import.py`; both passed.
The generated `out/migrated.json` and `out/rejected.json` were parsed again.
This was an offline rehearsal only; no settings were applied to a service.
