# Repair a multi-file JSON Schema bundle after an identifier migration

Work only in '/workspace/repo'. The catalog schema was moved under a new URI prefix, but the order resource still carries a stale identifier. The final files look plausible while reference resolution and instance classification are broken.

Read README.md and registry.json, inspect all schemas and examples, and run:

  python3 tools/check_bundle.py
  python3 tools/check_bundle.py --write

Repair the schema package without changing the protected registry, checker, examples, or unrelated schema resources. Leave:

- a corrected 'schemas/orders/order.json';
- 'out/bundle_audit.json' generated from the corrected package;
- 'SCHEMA_HANDOFF.md' explaining the retrieval URI versus effective base distinction, the repaired reference chain, example results, commands run, and offline scope.

Do not replace the checker, weaken required fields, hard-code example filenames into schema logic, contact external services, or claim deployment.
