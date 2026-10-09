#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-namespace-probe-") as temporary:
    root = Path(temporary)
    api = root / "api/acme/plugins"
    metrics = root / "metrics/acme/plugins"
    api.mkdir(parents=True)
    metrics.mkdir(parents=True)
    (api / "orders.py").write_text("IDENTITY='orders'\n", encoding="utf-8")
    (metrics / "metrics.py").write_text("IDENTITY='metrics'\n", encoding="utf-8")
    snippet = "import acme.plugins.orders as o, acme.plugins.metrics as m, acme, json; print(json.dumps([o.IDENTITY,m.IDENTITY,len(acme.__path__)]))"
    for roots in ((api.parents[1], metrics.parents[1]), (metrics.parents[1], api.parents[1])):
        command = "import sys;sys.path[:0]=" + repr([str(path) for path in roots]) + ";" + snippet
        completed = subprocess.run([sys.executable, "-I", "-c", command], text=True, capture_output=True, timeout=5)
        if completed.returncode != 0 or json.loads(completed.stdout) != ["orders", "metrics", 2]:
            raise SystemExit("implicit namespace/path-order subprocess probe failed")
print(json.dumps({"python3": "3.12", "pep420": "passed", "isolated_subprocess": "passed", "path_orders": 2}, sort_keys=True))
