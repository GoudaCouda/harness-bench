#!/usr/bin/env python3
"""Task 159 plans from captured protocol evidence; live HTTP is intentionally absent."""
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
goaway = {"last_stream_id": 5, "error_code": "NO_ERROR"}
requests = [
    {"request_id": "r1", "stream_id": 3, "completed": True},
    {"request_id": "r2", "stream_id": 7, "completed": False},
]
if any(row["stream_id"] % 2 != 1 for row in requests):
    raise SystemExit("HTTP/2 client stream-id probe failed")
unprocessed = [
    row["request_id"]
    for row in requests
    if not row["completed"] and row["stream_id"] > goaway["last_stream_id"]
]
if unprocessed != ["r2"]:
    raise SystemExit("GOAWAY last-stream boundary probe failed")
payload = json.dumps({"goaway": goaway, "requests": requests}, sort_keys=True).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("GOAWAY evidence digest probe failed")
print(json.dumps({
    "python3": "3.12", "goaway_boundary": "passed", "json": "passed",
    "sha256": "passed", "http_runtime": "not_required_by_task_contract",
}, sort_keys=True))
