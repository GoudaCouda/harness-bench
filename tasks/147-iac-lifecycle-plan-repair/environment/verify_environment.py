#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict, deque

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
dependencies = {
    "network.frontend": ["network.core"],
    "service.api": ["network.frontend", "database.primary"],
    "network.core": [],
    "database.primary": [],
}
dependants: dict[str, list[str]] = defaultdict(list)
degree = {name: len(required) for name, required in dependencies.items()}
for name, required in dependencies.items():
    for dependency in required:
        dependants[dependency].append(name)
ready = deque(sorted(name for name, value in degree.items() if value == 0))
ordered: list[str] = []
while ready:
    name = ready.popleft()
    ordered.append(name)
    for dependant in sorted(dependants[name]):
        degree[dependant] -= 1
        if degree[dependant] == 0:
            ready.append(dependant)
if ordered[-1] != "service.api" or len(ordered) != len(dependencies):
    raise SystemExit("IaC dependency ordering probe failed")
payload = json.dumps(
    {"order": ordered, "redacted": {"password": "<sensitive>"}},
    sort_keys=True,
).encode()
if json.loads(payload)["redacted"]["password"] != "<sensitive>":
    raise SystemExit("IaC redaction JSON probe failed")
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("IaC plan hash probe failed")
print(json.dumps({"python3": "3.12", "graph_order": "passed", "json": "passed", "sha256": "passed"}, sort_keys=True))
