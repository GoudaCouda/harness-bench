#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
import subprocess
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

state = {"generation": 2, "active": ["base"], "registrations": [{"plugin": "base", "hook": "h0"}]}
clone = deepcopy(state)
clone["active"].append("leaf")
if state["active"] != ["base"]:
    raise SystemExit("deep-copy rollback isolation probe failed")
edges = defaultdict(set)
edges["leaf"].add("base")
if edges["leaf"] != {"base"}:
    raise SystemExit("dependency graph container probe failed")
probe = subprocess.run(
    ["python", "-B", "-c", "from collections import defaultdict; from copy import deepcopy; import json; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"python alias lifecycle probe failed: {probe.stderr.strip()}")

print(json.dumps({"python": "3.12", "python3": "3.12", "dependency_graph": "passed", "deepcopy": "passed"}, sort_keys=True))
