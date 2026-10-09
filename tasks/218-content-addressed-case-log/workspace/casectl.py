#!/usr/bin/env python3
"""Local Aerowake content-addressed case-log controller.

Read-only operational feedback. The controller reports structure, vocabulary,
and self-consistency failures it can observe. It does not decide cases, does
not name which case belongs in which outcome, and never writes to the workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
BATCH_PATH = WORKSPACE / "staging" / "case_batch.json"
LOG_PATH = WORKSPACE / "state" / "caselog.json"
RECEIPT_PATH = WORKSPACE / "state" / "case_receipt.json"
CLOCK = 1774342800
VALID = {"recorded", "already_recorded", "conflict", "malformed"}


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
    document = _load(BATCH_PATH)
    cases = document.get("cases") if isinstance(document, dict) else []
    if args.selector is not None:
        try:
            index = int(args.selector)
        except ValueError:
            raise SystemExit("batch selector must be an integer index")
        if index < 0 or index >= len(cases):
            _emit({"index": index, "present": False})
            return 0
        item = cases[index]
        payload = item.get("payload") if isinstance(item, dict) else None
        digest = None
        if isinstance(payload, dict):
            blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha256(blob).hexdigest()
        _emit({"index": index, "item": item, "canonical_digest": digest})
        return 0
    _emit(
        {
            "batch_id": document.get("batch_id"),
            "count": len(cases),
            "case_ids": [item.get("case_id") if isinstance(item, dict) else None for item in cases],
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    cases = (_load(BATCH_PATH) or {}).get("cases") or []
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.is_file() else None
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) if RECEIPT_PATH.is_file() else None
    if log is None:
        failures.append({"check": "log_schema", "detail": "state/caselog.json is missing"})
    if receipt is None:
        failures.append({"check": "receipt_schema", "detail": "state/case_receipt.json is missing"})
    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(cases):
            failures.append({"check": "log_coverage", "detail": "caselog must record one decision per batch item"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "log_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if log.get("counts") != recomputed:
                failures.append({"check": "log_internal_totals", "detail": "counts disagree with decisions"})
            names = log.get("recorded_names") or []
            if names != sorted(names):
                failures.append({"check": "log_internal_totals", "detail": "recorded_names must be sorted"})
    if isinstance(receipt, dict) and isinstance(log, dict):
        if receipt.get("counts") != log.get("counts") or receipt.get("recorded_names") != log.get("recorded_names"):
            failures.append({"check": "receipt_internal_totals", "detail": "receipt disagrees with the case log"})
        recorded = receipt.get("cases") or []
        if isinstance(recorded, list) and [row.get("name") for row in recorded if isinstance(row, dict)] != (log.get("recorded_names") or []):
            failures.append({"check": "receipt_internal_totals", "detail": "cases names disagree with recorded_names"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["batch"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
