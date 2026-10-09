#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
schema_fields = ['heads', 'merge', 'uses_historical_model', 'idempotent', 'reverse', 'fresh_replay', 'upgrade_replay']
checked_fields = ['fresh_replay', 'heads', 'idempotent', 'merge', 'reverse', 'upgrade_replay', 'uses_historical_model']
for key in schema_fields:
    if key not in data:
        raise SystemExit(f"missing key: {key}")
if set(data) != set(schema_fields):
    raise SystemExit("top-level schema differs from the public contract")

fixture_root = Path(__file__).resolve().parents[1]


def load_json(relative):
    return json.loads((fixture_root / relative).read_text(encoding="utf-8"))


def version_tuple(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(value))
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


from simulate import evaluate
results = evaluate(data, fixture_root)

failed = [name for name in checked_fields if not bool(results.get(name))]
if failed:
    raise SystemExit("semantic invariants failed: " + ", ".join(failed))
print(json.dumps({"status": "pass", "checked": checked_fields}))
