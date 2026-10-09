#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
live = {"/spec/image": "v1", "/spec/replicas": 2}
ownership = {
    "/spec/image": {"deploy"},
    "/spec/replicas": {"autoscaler"},
}
candidate_live = deepcopy(live)
candidate_ownership = deepcopy(ownership)
requested = {"/spec/image": "v2", "/spec/replicas": 3}
conflicts = [
    path
    for path, value in requested.items()
    if candidate_live.get(path) != value
    and candidate_ownership.get(path, set()) - {"deploy"}
]
if conflicts != ["/spec/replicas"]:
    raise SystemExit("Kubernetes field-conflict probe failed")
if candidate_live != live or candidate_ownership != ownership:
    raise SystemExit("Kubernetes atomicity probe failed")
payload = json.dumps(
    {"object": live, "ownership": {key: sorted(value) for key, value in ownership.items()}},
    sort_keys=True,
).encode()
if json.loads(payload)["object"]["/spec/image"] != "v1":
    raise SystemExit("Kubernetes field JSON probe failed")
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("Kubernetes field hash probe failed")
print(json.dumps({"python3": "3.12", "atomic_conflict": "passed", "json": "passed", "sha256": "passed"}, sort_keys=True))
