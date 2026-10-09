#!/usr/bin/env python3
"""Local Harborwatch SSO audit-quarantine controller.

Read-only operational feedback. The controller reports structure, vocabulary,
and self-consistency failures it can observe. It does not decide events, does
not name which event belongs in which outcome, and never writes to the workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
STREAM_PATH = WORKSPACE / "staging" / "audit_stream.json"
LOG_PATH = WORKSPACE / "state" / "audit_log.json"
RECEIPT_PATH = WORKSPACE / "state" / "audit_receipt.json"
CLOCK = 1774170000
VALID = {"accepted", "quarantined", "malformed"}
TOKEN_FIELDS = {"access_token", "refresh_token", "password", "secret", "authorization"}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path.relative_to(WORKSPACE)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.relative_to(WORKSPACE)} is not valid JSON: {exc}")


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def cmd_clock(_: argparse.Namespace) -> int:
    _emit({"gate_clock_epoch": CLOCK})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    document = _load(STREAM_PATH)
    events = document.get("events") if isinstance(document, dict) else []
    if args.selector is not None:
        try:
            index = int(args.selector)
        except ValueError:
            raise SystemExit("events selector must be an integer index")
        if index < 0 or index >= len(events):
            _emit({"index": index, "present": False})
            return 0
        event = events[index]
        keys = sorted(event) if isinstance(event, dict) else []
        _emit(
            {
                "index": index,
                "event_id": event.get("event_id") if isinstance(event, dict) else None,
                "correlation_id": event.get("correlation_id") if isinstance(event, dict) else None,
                "kind": event.get("kind") if isinstance(event, dict) else None,
                "keys": keys,
                "token_fields_present": sorted(key for key in keys if key.casefold() in TOKEN_FIELDS),
            }
        )
        return 0
    _emit(
        {
            "stream_id": document.get("stream_id"),
            "count": len(events),
            "event_ids": [item.get("event_id") if isinstance(item, dict) else None for item in events],
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    events = (_load(STREAM_PATH) or {}).get("events") or []
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.is_file() else None
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) if RECEIPT_PATH.is_file() else None
    if log is None:
        failures.append({"check": "log_schema", "detail": "state/audit_log.json is missing"})
    if receipt is None:
        failures.append({"check": "receipt_schema", "detail": "state/audit_receipt.json is missing"})
    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(events):
            failures.append({"check": "log_coverage", "detail": "audit_log must record one decision per event"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "log_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if log.get("counts") != recomputed:
                failures.append({"check": "log_internal_totals", "detail": "counts disagree with decisions"})
        for record in log.get("records") or []:
            if not isinstance(record, dict):
                continue
            payload = record.get("record") if isinstance(record.get("record"), dict) else {}
            for key, value in payload.items():
                if str(key).casefold() in TOKEN_FIELDS and str(value) not in {"", "[REDACTED]"}:
                    failures.append({"check": "redaction_integrity", "detail": "token fields in records must be redacted"})
                    break
    if isinstance(receipt, dict) and isinstance(log, dict):
        if receipt.get("counts") != log.get("counts"):
            failures.append({"check": "receipt_internal_totals", "detail": "receipt counts disagree with the audit log"})
        if receipt.get("quarantined_ids") != log.get("quarantined_ids"):
            failures.append({"check": "receipt_internal_totals", "detail": "quarantined_ids disagree with the audit log"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["events"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
