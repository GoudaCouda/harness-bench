#!/usr/bin/env python3
"""Local Pebbleward controller.

Read-only operational feedback. The controller reports structure, vocabulary,
and self-consistency failures it can observe. It does not decide items, does
not name which item belongs in which outcome, and never writes to the workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
STREAM_PATH = WORKSPACE / 'staging/ballots.json'
LOG_PATH = WORKSPACE / 'state/stv_log.json'
RECEIPT_PATH = WORKSPACE / 'state/stv_receipt.json'
CLOCK = 1776468800
VALID = {'recorded', 'conflict', 'malformed'}


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
                'ballot_id': event.get('ballot_id') if isinstance(event, dict) else None,
                'serial': event.get('serial') if isinstance(event, dict) else None,
                "keys": keys,
            }
        )
        return 0
    _emit(
        {
            "stream_id": document.get("stream_id"),
            "count": len(events),
            "item_ids": [
                item.get('ballot_id') if isinstance(item, dict) else None for item in events
            ],
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    events = (_load(STREAM_PATH) or {}).get("events") or []
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.is_file() else None
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) if RECEIPT_PATH.is_file() else None
    if log is None:
        failures.append({"check": "log_schema", "detail": "state/stv_log.json is missing"})
    if receipt is None:
        failures.append({"check": "receipt_schema", "detail": "state/stv_receipt.json is missing"})
    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(events):
            failures.append({"check": "log_coverage", "detail": "log must record one decision per event"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "log_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if log.get("counts") != recomputed:
                failures.append({"check": "log_internal_totals", "detail": "counts disagree with decisions"})
    if isinstance(receipt, dict) and isinstance(log, dict):
        if receipt.get("counts") != log.get("counts"):
            failures.append({"check": "receipt_totals", "detail": "receipt counts disagree with the log"})
    _emit({"ok": not failures, "failures": failures})
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Pebbleward read-only controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock", help="print the frozen gate clock").set_defaults(func=cmd_clock)
    inspect_p = sub.add_parser("inspect", help="inspect parked events without deciding them")
    inspect_p.add_argument("selector", nargs="?")
    inspect_p.set_defaults(func=cmd_inspect)
    sub.add_parser("validate", help="check self-consistency of recorded artifacts").set_defaults(
        func=cmd_validate
    )
    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
