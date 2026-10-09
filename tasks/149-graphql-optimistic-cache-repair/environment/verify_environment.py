#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
base = {
    "Todo:tmp-1": {"id": "tmp-1", "text": "draft"},
    "Query:ROOT": {"todo": {"$ref": "Todo:tmp-1"}},
}
layer = {"Todo:tmp-1": {"text": None, "done": True}}
visible = deepcopy(base)
for entity, patch in layer.items():
    visible.setdefault(entity, {}).update(patch)
if visible["Todo:tmp-1"] != {"id": "tmp-1", "text": None, "done": True}:
    raise SystemExit("GraphQL normalized merge/null probe failed")
alias = {"Todo:tmp-1": "Todo:42"}
rewritten = json.loads(json.dumps(visible).replace("Todo:tmp-1", alias["Todo:tmp-1"]))
if rewritten["Query:ROOT"]["todo"]["$ref"] != "Todo:42":
    raise SystemExit("GraphQL reference rewrite probe failed")
payload = json.dumps(
    {"base": rewritten, "audit": [{"mutation": "m1", "status": "rebased"}]},
    sort_keys=True,
).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("GraphQL cache hash probe failed")
print(json.dumps({"python3": "3.12", "normalized_merge": "passed", "reference_rewrite": "passed", "sha256": "passed"}, sort_keys=True))
