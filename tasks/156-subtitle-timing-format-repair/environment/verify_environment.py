#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
sample = "1\n00:00:01,000 --> 00:00:02,500\nWelcome to Harbor Lab.\n"
match = re.fullmatch(
    r"1\n(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})\n(.+)\n",
    sample,
)
if not match or match.group(9) != "Welcome to Harbor Lab.":
    raise SystemExit("SRT parser probe failed")
start = ((int(match.group(1)) * 60 + int(match.group(2))) * 60 + int(match.group(3))) * 1000 + int(match.group(4))
end = ((int(match.group(5)) * 60 + int(match.group(6))) * 60 + int(match.group(7))) * 1000 + int(match.group(8))
if (start, end - start) != (1000, 1500):
    raise SystemExit("subtitle timing arithmetic probe failed")
payload = json.dumps({"start_ms": start, "end_ms": end}, sort_keys=True).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("subtitle digest probe failed")
print(json.dumps({
    "python3": "3.12",
    "srt_parse": "passed",
    "timing": "passed",
    "json": "passed",
    "sha256": "passed",
    "services": "not_required_by_task_contract",
}, sort_keys=True))
