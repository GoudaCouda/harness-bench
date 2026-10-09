# Repair layered configuration resolution

The Edge Relay service started with the wrong port after an emergency CLI
override and also wrote a synthetic API token into a diagnostic snapshot.
Repair the offline repository in `$WORKSPACE/repo`.

Read `docs/config_contract.md`, `schema.json`, and all four configuration layers.
Implement `resolve_config(defaults, file_values, environment, cli_values,
schema)` in `src/config_resolver.py`. Then create `resolved_config.json` for the
supplied inputs. It must contain `values` and `sources`; sensitive values must be
the literal `<redacted>` in this artifact while their source remains visible.

Create `IMPLEMENTATION_NOTES.md` describing precedence, explicit-null and
invalid-highest-layer behavior, typed parsing, redaction, the exact public test
command and observed result, and one remaining integration risk.

Run from `repo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not modify inputs or tests, contact a secret store, start the service, or
claim deployment. The synthetic token in `environment.json` is fixture data.
