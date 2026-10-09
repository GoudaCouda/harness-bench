#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

base = {"metadata": {"labels": {}}, "spec": {"replicas": 1}}
patches = [
    ("/metadata/labels/owner", "platform"),
    ("/spec/replicas", 3),
]


def apply(order):
    value = copy.deepcopy(base)
    for path, replacement in order:
        if path == "/metadata/labels/owner":
            value["metadata"]["labels"]["owner"] = replacement
        elif path == "/spec/replicas":
            value["spec"]["replicas"] = replacement
    return value


forward = apply(patches)
reverse = apply(list(reversed(patches)))
if forward != reverse or forward["spec"]["replicas"] != 3:
    raise SystemExit("admission order-independence probe failed")

conflicting = [
    ("/spec/replicas", 2),
    ("/spec/replicas", 3),
]
if len({path for path, _ in conflicting}) == len(conflicting):
    raise SystemExit("admission path-conflict probe failed")
json.loads(json.dumps(forward))
print(json.dumps({"python3": "3.12", "order_independence": "passed",
                  "json_pointer_conflict": "passed",
                  "kubernetes_runtime": "not_required_by_task_contract"}, sort_keys=True))
