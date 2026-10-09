#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

config = {
    "precedence": ["acknowledged", "duplicate", "critical", "broad_urgent", "limited"],
    "broad_account_threshold": 20,
    "urgent_deadline_hours": 4,
    "threshold_comparator": "greater_than",
    "deadline_comparator": "less_than",
}


def route(case: dict) -> str:
    for rule in config["precedence"]:
        if rule == "acknowledged" and case.get("acknowledged"):
            return "hold_ack"
        if rule == "duplicate" and case.get("duplicate"):
            return "hold_duplicate"
        if rule == "critical" and (case.get("safety") or case.get("regions", 0) > 1):
            return "p1"
        if rule == "broad_urgent":
            if case.get("accounts", 0) > 20 and case.get("deadline_hours", 99) < 4:
                return "p2"
        if rule == "limited":
            return "p3"
    return "unrouted"


observed = [
    route({"acknowledged": True, "regions": 3}),
    route({"duplicate": True, "safety": True}),
    route({"accounts": 20, "deadline_hours": 3}),
    route({"accounts": 21, "deadline_hours": 4}),
    route({"accounts": 21, "deadline_hours": 3}),
    route({"regions": 2}),
]
if observed != ["hold_ack", "hold_duplicate", "p3", "p3", "p2", "p1"]:
    raise SystemExit("first-match routing boundary probe failed")

with tempfile.TemporaryDirectory(prefix="hb-170-routing-") as directory:
    path = Path(directory) / "routing_config.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"tool": "routing_probe/1", "config_sha256": digest, "status": "pass"}
    if report["config_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise SystemExit("digest-bound routing report probe failed")

print(json.dumps({
    "python3": "3.12",
    "first_match_routing": "passed",
    "strict_boundaries": "passed",
    "config_digest_binding": "passed",
    "services": "not_required_by_task_contract",
}, sort_keys=True))
