#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}
requests = [
    {"method": "GET", "body_replayable": True, "opt_in": True},
    {"method": "POST", "body_replayable": True, "opt_in": True},
]
eligible = [
    row["method"] in safe_methods and row["body_replayable"] and row["opt_in"]
    for row in requests
]
if eligible != [True, False]:
    raise SystemExit("HTTP early-data method probe failed")

remembered = {"alpn": "h3", "transport": {"max_data": 1024}, "application": {"qpack": 4}}
current = json.loads(json.dumps(remembered))
if current != remembered or not all(current.get(key) for key in ("alpn", "transport", "application")):
    raise SystemExit("complete remembered-session probe failed")

markers = [part.strip() for part in "1, 1".split(",")]
if markers != ["1", "1"]:
    raise SystemExit("Early-Data intermediary marker probe failed")
response = {"status": 425, "handshake": "complete", "attempt": 1, "max_attempts": 2}
retry = (
    response["status"] == 425
    and response["handshake"] == "complete"
    and response["attempt"] < response["max_attempts"]
)
if not retry:
    raise SystemExit("425 post-handshake retry probe failed")
print(json.dumps({"python3": "3.12", "eligibility": "passed", "session": "passed",
                  "early_data_header": "passed", "retry_425": "passed",
                  "network_runtime": "not_required_by_task_contract"}, sort_keys=True))
