# Cache reconciliation handoff

The reducer keeps canonical base records separate from active optimistic layers. Records are normalized by cache ID, while field patches merge instead of replacing a whole record: a missing field preserves the prior value and explicit `null` overwrites it. Visible state is rebuilt by overlaying non-ignored layers in start order, so a later mutation remains visible when an older mutation resolves.

Success removes only its named layer, rewrites temporary IDs and every matching reference in base and remaining layers, then merges authoritative server writes. Existing target fields beat renamed source fields and server fields beat both. Error removes only its named layer. Ignored optimism stays in lifecycle accounting without becoming an overlay. Every projected reference must resolve, malformed or duplicate lifecycle events fail closed, and caller-owned inputs are cloned.

Verification used `python -m unittest discover -s tests -p 'test_*.py'`, `python bin/reconcile_cache.py`, and a JSON re-parse of `out/base.json`, `out/visible.json`, and `out/audit.json`; all passed. No GraphQL endpoint, browser cache, mutation API, network, or live application was contacted or changed.
