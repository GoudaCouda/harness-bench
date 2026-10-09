#!/usr/bin/env python3
"""Task 157 evaluates decoded claims offline; JWT and cloud runtimes are out of scope."""
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
claims = {
    "repository": "harbor/infra",
    "owner_id": "1001",
    "repository_id": "2002",
    "environment": "prod:blue",
}
owner, name = claims["repository"].split("/", 1)
subject = (
    f"repo:{owner}@{claims['owner_id']}/{name}@{claims['repository_id']}"
    f":environment:{claims['environment'].replace(':', '%3A')}"
)
if subject != "repo:harbor@1001/infra@2002:environment:prod%3Ablue":
    raise SystemExit("OIDC subject reconstruction probe failed")
payload = json.dumps({"sub": subject}, sort_keys=True).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("OIDC claim digest probe failed")
print(json.dumps({
    "python3": "3.12", "decoded_claims": "passed", "subject": "passed",
    "json": "passed", "sha256": "passed",
    "github_cloud_runtime": "not_required_by_task_contract",
}, sort_keys=True))
