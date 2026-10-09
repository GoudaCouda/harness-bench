#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

body = '{"id":"probe"}'
digest = hmac.new(b"secret", f"1700.{body}".encode(), hashlib.sha256).hexdigest()
if len(digest) != 64 or not hmac.compare_digest(digest, digest):
    raise SystemExit("HMAC-SHA256/constant-time comparison probe failed")
probe = subprocess.run(
    ["python", "-B", "-c", "import copy,hashlib,hmac,json; print(hmac.compare_digest('x','x'))"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "True":
    raise SystemExit(f"python alias crypto probe failed: {probe.stderr.strip()}")

print(json.dumps({"python": "3.12", "python3": "3.12", "hmac_sha256": "passed"}, sort_keys=True))
