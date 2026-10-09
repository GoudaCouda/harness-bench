#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict, deque

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
needs = {
    "test[py311]": ["build"],
    "test[py312]": ["build"],
    "package": ["test[py311]", "test[py312]"],
    "build": [],
}
dependants: dict[str, list[str]] = defaultdict(list)
degree = {job: len(required) for job, required in needs.items()}
for job, required in needs.items():
    for dependency in required:
        dependants[dependency].append(job)
ready = deque(sorted(job for job, count in degree.items() if count == 0))
order: list[str] = []
while ready:
    job = ready.popleft()
    order.append(job)
    for dependant in sorted(dependants[job]):
        degree[dependant] -= 1
        if degree[dependant] == 0:
            ready.append(dependant)
if order[0] != "build" or order[-1] != "package" or len(order) != 4:
    raise SystemExit("GitHub matrix DAG fan-in probe failed")
payload = json.dumps({"order": order, "manual": ["deploy"]}, sort_keys=True).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("rerun plan hash probe failed")
print(json.dumps({"python3": "3.12", "matrix_dag": "passed", "json": "passed", "sha256": "passed"}, sort_keys=True))
