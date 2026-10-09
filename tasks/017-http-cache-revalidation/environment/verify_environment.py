#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
alias = subprocess.run(
    ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    capture_output=True, text=True, check=False, timeout=10,
)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")

fmt = "%a, %d %b %Y %H:%M:%S GMT"
left = datetime.strptime("Wed, 21 Oct 2015 07:28:00 GMT", fmt).replace(tzinfo=timezone.utc)
right = datetime.strptime("Wed, 21 Oct 2015 07:28:01 GMT", fmt).replace(tzinfo=timezone.utc)
if not left < right or left.strftime(fmt) != "Wed, 21 Oct 2015 07:28:00 GMT":
    raise SystemExit("HTTP-date boundary probe failed")
weak = 'W/"rev-7"'
strong = '"rev-7"'
if weak.removeprefix("W/") != strong:
    raise SystemExit("weak ETag normalization probe failed")
print(json.dumps({"python": "3.12", "http_date_and_weak_etag": "passed"}, sort_keys=True))
