# Split namespace repair handoff

The failure was path-order dependent because `services/api/src/acme/__init__.py` converted the shared top-level namespace into a regular package. When the API root appeared first, Python stopped namespace discovery there and could not find the Metrics-owned module in the second root. Copying that module or mutating `sys.path` would hide the ownership defect rather than repair packaging.

I removed only the obsolete top-level marker. The orders implementation remains under the API-owned source root and metrics remains under the Metrics-owned root. The shared `acme` package now exposes two namespace locations, with each plugin resolving to its original file and returning its expected identity.

I ran `python3 tools/probe_imports.py` and inspected `out/import_probe.json`. Fresh interpreters passed both API-then-Metrics and Metrics-then-API `PYTHONPATH` order cases, including origin and identity checks. Verification was offline; no package was installed or published and no external system was contacted.
