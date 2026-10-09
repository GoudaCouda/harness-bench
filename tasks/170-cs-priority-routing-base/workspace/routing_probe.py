#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "routing_config.json"


def route(config: dict, case: dict) -> str:
    for rule in config.get("precedence", []):
        if rule == "acknowledged" and case.get("acknowledged"):
            return "hold_ack"
        if rule == "duplicate" and case.get("duplicate"):
            return "hold_duplicate"
        if rule == "critical" and (case.get("safety") or case.get("regions", 0) > 1):
            return "p1"
        if rule == "broad_urgent":
            accounts_ok = case.get("accounts", 0) > config.get(
                "broad_account_threshold", 0
            )
            deadline_ok = case.get("deadline_hours", 99) < config.get(
                "urgent_deadline_hours", 0
            )
            if accounts_ok and deadline_ok:
                return "p2"
        if rule == "limited":
            return "p3"
    return "unrouted"


def main() -> int:
    raw = CONFIG.read_bytes()
    config = json.loads(raw)
    checks = {
        "strict_comparators_declared": config.get("threshold_comparator")
        == "greater_than"
        and config.get("deadline_comparator") == "less_than",
        "acknowledgement_suppresses_critical": route(
            config, {"acknowledged": True, "regions": 3}
        )
        == "hold_ack",
        "duplicate_suppresses_priority": route(
            config, {"duplicate": True, "safety": True}
        )
        == "hold_duplicate",
        "strict_account_boundary": route(config, {"accounts": 20, "deadline_hours": 3})
        == "p3",
        "strict_deadline_boundary": route(config, {"accounts": 21, "deadline_hours": 4})
        == "p3",
        "broad_urgent_route": route(config, {"accounts": 21, "deadline_hours": 3})
        == "p2",
        "multi_region_route": route(config, {"regions": 2}) == "p1",
    }
    report = {
        "tool": "routing_probe/1",
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }
    (ROOT / "routing_probe_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
