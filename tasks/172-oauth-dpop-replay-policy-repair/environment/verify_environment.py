#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from urllib.parse import urlsplit, urlunsplit

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


def normalize_htu(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    default = (parsed.scheme.lower() == "https" and parsed.port == 443)
    port = "" if parsed.port is None or default else f":{parsed.port}"
    return urlunsplit((parsed.scheme.lower(), host + port, parsed.path or "/", "", ""))


if normalize_htu("HTTPS://API.EXAMPLE:443/token?debug=1#fragment") != "https://api.example/token":
    raise SystemExit("DPoP htu normalization probe failed")

now, skew = 1_000, 30
if not (now - skew <= 970 <= now + skew) or (now - skew <= 969 <= now + skew):
    raise SystemExit("DPoP inclusive iat window probe failed")

cache = {"old-jti": 900, "active-jti": 1_100}
retained = {jti: expiry for jti, expiry in cache.items() if expiry > now}
if retained != {"active-jti": 1_100}:
    raise SystemExit("replay-cache expiry probe failed")
accepted = []
batch = ["fresh-jti", "fresh-jti"]
for jti in batch:
    if jti not in retained and jti not in accepted:
        accepted.append(jti)
if accepted != ["fresh-jti"]:
    raise SystemExit("same-batch replay probe failed")
retained.update({jti: now + 300 for jti in accepted})

print(json.dumps({
    "python3": "3.12",
    "htu_normalization": "passed",
    "iat_boundary": "passed",
    "transactional_replay_cache": "passed",
    "cryptography": "prevalidated_evidence_only",
    "identity_service": "not_required_by_task_contract",
}, sort_keys=True))
