#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import hmac
import json
import sys
from urllib.parse import unquote


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

body = json.dumps({"message": "artifact api/v2"}, sort_keys=True, separators=(",", ":")).encode()
signature = hmac.new(b"local-probe-key", body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(signature, hmac.new(b"local-probe-key", body, hashlib.sha256).hexdigest()):
    raise SystemExit("HMAC verification probe failed")
if unquote(unquote("%252E%252E%252Fsecret")) != "../secret":
    raise SystemExit("bounded URL decoding probe failed")
windows: dict[str, deque[int]] = defaultdict(deque)
windows["198.51.100.4"].extend((1, 2, 3))
if list(windows["198.51.100.4"]) != [1, 2, 3]:
    raise SystemExit("sliding-window state probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "hmac_sha256": "passed",
            "url_decode": "passed",
            "deque_window": "passed",
        },
        sort_keys=True,
    )
)
