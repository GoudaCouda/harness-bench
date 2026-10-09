#!/usr/bin/env python3
"""Local sliding-window quota controller. Diagnostic only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
EVENTS_PATH = WORKSPACE / "state" / "quota_events.json"
PENDING_PATH = WORKSPACE / "staging" / "pending_requests.json"
RECEIPT_PATH = WORKSPACE / "state" / "quota_receipt.json"
CLOCK = 1773738000
BURST_S = 60
DAILY_S = 86400
BURST_MAX = 3
DAILY_MAX = 100000
VALID = {"executed", "burst_exceeded", "daily_exceeded", "refund_expired", "rejected"}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path.relative_to(WORKSPACE)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as extra:
        raise SystemExit(f"{path.relative_to(WORKSPACE)} is not valid JSON: {extra}")


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def in_window(event_at: int, window: int) -> bool:
    return CLOCK - int(event_at) < window and int(event_at) <= CLOCK


def cmd_clock(_: argparse.Namespace) -> int:
    _emit(
        {
            "quota_clock_epoch": CLOCK,
            "burst_window_seconds": BURST_S,
            "daily_window_seconds": DAILY_S,
            "burst_max_debits": BURST_MAX,
            "daily_max_cents": DAILY_MAX,
        }
    )
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "events":
        document = _load(EVENTS_PATH)
        events = document.get("events") if isinstance(document, dict) else []
        if args.selector:
            for event in events:
                if event.get("event_id") == args.selector or event.get("tenant_id") == args.selector:
                    _emit(event)
            return 0
        _emit({"count": len(events), "event_ids": [event.get("event_id") for event in events]})
        return 0
    document = _load(PENDING_PATH)
    requests = document.get("requests") if isinstance(document, dict) else []
    if args.selector:
        for item in requests:
            if item.get("request_id") == args.selector:
                _emit(item)
                return 0
        _emit({"request_id": args.selector, "present": False})
        return 0
    _emit({"count": len(requests), "request_ids": [item.get("request_id") for item in requests]})
    return 0


def cmd_window(args: argparse.Namespace) -> int:
    events = (_load(EVENTS_PATH) or {}).get("events") or []
    tenant = args.tenant_id
    burst = 0
    daily = 0
    by_id = {event.get("event_id"): event for event in events if event.get("tenant_id") == tenant}
    for event in events:
        if event.get("tenant_id") != tenant:
            continue
        when = int(event.get("at") or 0)
        amount = int(event.get("amount_cents") or 0)
        if event.get("kind") == "debit" and in_window(when, BURST_S):
            burst += 1
        if not in_window(when, DAILY_S):
            continue
        if event.get("kind") == "debit":
            daily += amount
        elif event.get("kind") == "refund":
            original = by_id.get(event.get("refund_of"))
            if isinstance(original, dict) and in_window(int(original.get("at") or 0), DAILY_S):
                daily -= amount
    _emit({"tenant_id": tenant, "burst_count": burst, "daily_net_cents": daily})
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    pending = (_load(PENDING_PATH) or {}).get("requests") or []
    expected_ids = [item.get("request_id") for item in pending]
    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as extra:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {extra}"})
    else:
        failures.append({"check": "receipt_schema", "detail": "state/quota_receipt.json is missing"})
    events_doc = _load(EVENTS_PATH)
    if not isinstance(events_doc, dict) or not isinstance(events_doc.get("events"), list):
        failures.append({"check": "ledger_schema", "detail": "quota_events.events must be an array"})
    if isinstance(receipt, dict):
        decisions = receipt.get("decisions")
        if not isinstance(decisions, list) or [entry.get("request_id") for entry in decisions if isinstance(entry, dict)] != expected_ids:
            failures.append({"check": "receipt_coverage", "detail": "one decision per pending request is required"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            executed = 0
            for entry in decisions:
                decision = entry.get("decision")
                if decision not in VALID:
                    failures.append({"check": "receipt_schema", "detail": f"unknown decision {decision!r}"})
                    break
                recomputed[decision] += 1
                if decision == "executed":
                    req = next((item for item in pending if item.get("request_id") == entry.get("request_id")), {})
                    if req.get("kind") == "debit":
                        executed += int(req.get("amount_cents") or 0)
            if receipt.get("counts") != recomputed:
                failures.append({"check": "receipt_internal_totals", "detail": "counts disagree with decisions"})
            if receipt.get("executed_debit_cents") != executed:
                failures.append({"check": "receipt_internal_totals", "detail": "executed_debit_cents disagrees with executed debit requests"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["events", "pending"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    window = sub.add_parser("window")
    window.add_argument("tenant_id")
    window.set_defaults(func=cmd_window)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
