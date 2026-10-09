#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOTS = {
    "api": ROOT / "services/api/src",
    "metrics": ROOT / "vendors/metrics/src",
}
ORDERS = (("api", "metrics"), ("metrics", "api"))
SNIPPET = r"""
import importlib, json, os
def rel(value): return os.path.relpath(value, ROOT).replace(os.sep, "/")
result = {}
for name in ("acme.plugins.orders", "acme.plugins.metrics"):
    try:
        module = importlib.import_module(name)
        result[name] = {
            "ok": True,
            "origin": rel(module.__file__),
            "identity": module.plugin_identity(),
        }
    except Exception as exc:
        result[name] = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)}
import acme
result["namespace_locations"] = sorted(rel(str(x)) for x in acme.__path__)
print(json.dumps(result, sort_keys=True))
"""


def main():
    matrix = {}
    for order in ORDERS:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(str(ROOTS[name]) for name in order)
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; ROOT=" + repr(str(ROOT)) + ";sys.path[:0]=" + repr([str(ROOTS[name]) for name in order]) + ";" + SNIPPET], text=True, capture_output=True, env=env)
        key = "-then-".join(order)
        if completed.returncode:
            matrix[key] = {"process_error": completed.stderr.strip()}
        else:
            matrix[key] = json.loads(completed.stdout)
    valid = True
    for result in matrix.values():
        for module in ("acme.plugins.orders", "acme.plugins.metrics"):
            valid = valid and result.get(module, {}).get("ok") is True
        valid = valid and len(result.get("namespace_locations", [])) == 2
    payload = {"schema_version": 1, "matrix": matrix, "valid": bool(valid)}
    target = ROOT / "out/import_probe.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if valid else 1)

if __name__ == "__main__":
    main()
