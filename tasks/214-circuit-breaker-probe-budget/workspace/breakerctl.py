#!/usr/bin/env python3
"""Local Northharbor RPC circuit-breaker controller.

Read-only operational feedback for the breaker in this workspace. The
controller reports structure, vocabulary, and self-consistency failures it can
observe. It does not decide events, does not name which event belongs in which
outcome, and never writes to the workspace.

Commands:

    clock                       print the frozen gate clock
    inspect events [INDEX]      show parked RPC events
    inspect policy              show published threshold, cooldown, and probe budget
    validate                    check the artifacts on disk for self-consistency
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
EVENTS_PATH = WORKSPACE / "staging" / "rpc_events.json"
LOG_PATH = WORKSPACE / "state" / "breaker_log.json"
RECEIPT_PATH = WORKSPACE / "state" / "breaker_receipt.json"

GATE_CLOCK_EPOCH = 1773997200
THRESHOLD = 3
COOLDOWN_SEC = 30
PROBE_BUDGET = 1
VALID_DECISIONS = {"executed", "short_circuited", "probed"}
VALID_MODES = {"closed", "open", "half_open"}


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
    _emit({"gate_clock_epoch": GATE_CLOCK_EPOCH})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "policy":
        _emit(
            {
                "threshold": THRESHOLD,
                "cooldown_sec": COOLDOWN_SEC,
                "probe_budget": PROBE_BUDGET,
            }
        )
        return 0
    document = _load(EVENTS_PATH)
    events = document.get("events") if isinstance(document, dict) else []
    if args.selector is not None:
        try:
            index = int(args.selector)
        except ValueError:
            raise SystemExit("events selector must be an integer index")
        if index < 0 or index >= len(events):
            _emit({"index": index, "present": False})
            return 0
        _emit({"index": index, "event": events[index]})
        return 0
    _emit(
        {
            "stream_id": document.get("stream_id"),
            "count": len(events),
            "event_ids": [
                item.get("event_id") if isinstance(item, dict) else None for item in events
            ],
            "services": sorted(
                {
                    str(item.get("service"))
                    for item in events
                    if isinstance(item, dict) and item.get("service")
                }
            ),
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    document = _load(EVENTS_PATH)
    events = [item for item in document.get("events", [])]
    log = None
    if LOG_PATH.is_file():
        try:
            log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append({"check": "log_schema", "detail": f"invalid JSON: {exc}"})
    else:
        failures.append({"check": "log_schema", "detail": "state/breaker_log.json is missing"})

    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as extra:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {extra}"})
    else:
        failures.append({"check": "receipt_schema", "detail": "state/breaker_receipt.json is missing"})

    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(events):
            failures.append(
                {
                    "check": "log_coverage",
                    "detail": "breaker_log must record one decision per event",
                }
            )
        else:
            seen: dict[int, str] = {}
            schema_problems: list[str] = []
            for entry in decisions:
                if not isinstance(entry, dict):
                    schema_problems.append("decision entry is not an object")
                    continue
                index = entry.get("index")
                decision = entry.get("decision")
                if not isinstance(index, int):
                    schema_problems.append("decision entry needs an integer index")
                    continue
                if decision not in VALID_DECISIONS:
                    schema_problems.append(f"index {index}: unknown decision {decision!r}")
                    continue
                if index in seen:
                    schema_problems.append(f"index {index}: duplicate decision")
                    continue
                seen[index] = str(decision)
            if schema_problems:
                failures.append({"check": "log_schema", "detail": schema_problems})
            recomputed = {name: 0 for name in sorted(VALID_DECISIONS)}
            for decision in seen.values():
                recomputed[decision] += 1
            if log.get("counts") != recomputed:
                failures.append(
                    {
                        "check": "log_internal_totals",
                        "detail": "counts disagree with the decisions actually recorded",
                    }
                )
            forwarded = log.get("forwarded_event_ids") or []
            allowed = {
                entry.get("event_id")
                for entry in decisions
                if isinstance(entry, dict) and entry.get("decision") in {"executed", "probed"}
            }
            extra = [event_id for event_id in forwarded if event_id not in allowed]
            if extra:
                failures.append(
                    {
                        "check": "forward_integrity",
                        "detail": "short-circuited events must not be forwarded",
                    }
                )

    if isinstance(receipt, dict) and isinstance(log, dict):
        if receipt.get("counts") != log.get("counts"):
            failures.append(
                {
                    "check": "receipt_internal_totals",
                    "detail": "receipt counts disagree with the breaker log",
                }
            )
        if receipt.get("forwarded_event_ids") != log.get("forwarded_event_ids"):
            failures.append(
                {
                    "check": "receipt_internal_totals",
                    "detail": "receipt forwarded_event_ids disagree with the breaker log",
                }
            )
        modes = receipt.get("breaker_mode")
        if not isinstance(modes, dict) or any(mode not in VALID_MODES for mode in modes.values()):
            failures.append(
                {
                    "check": "receipt_schema",
                    "detail": "breaker_mode must map services to closed, open, or half_open",
                }
            )

    failed = sorted({str(item["check"]) for item in failures})
    _emit(
        {
            "status": "pass" if not failed else "fail",
            "checks": [
                "log_schema",
                "log_coverage",
                "log_internal_totals",
                "forward_integrity",
                "receipt_schema",
                "receipt_internal_totals",
            ],
            "checks_failed": failed,
            "failures": failures,
        }
    )
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["events", "policy"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
