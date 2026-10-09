#!/usr/bin/env python3
"""Local Ridgepeak placement-union controller.

Read-only operational feedback. The controller reports structure, vocabulary,
and self-consistency failures it can observe. It does not decide regions, does
not name which region belongs in which outcome, and never writes to the workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
SNAP_PATH = WORKSPACE / "inventories" / "snapshots.json"
LOG_PATH = WORKSPACE / "state" / "placement_log.json"
RECEIPT_PATH = WORKSPACE / "state" / "placement_receipt.json"
CLOCK = 1774083600
VALID = {"selected", "dropped", "tombstoned"}


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
    document = _load(SNAP_PATH)
    rows = document.get(args.target) or []
    if args.selector:
        hits = [row for row in rows if isinstance(row, dict) and row.get("region_id") == args.selector]
        _emit({"region_id": args.selector, "source": args.target, "rows": hits})
        return 0
    _emit(
        {
            "source": args.target,
            "count": len(rows),
            "region_ids": [row.get("region_id") if isinstance(row, dict) else None for row in rows],
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    snaps = _load(SNAP_PATH)
    merged_ids = sorted(
        {
            str(row.get("region_id"))
            for key in ("started", "waiting", "running")
            for row in (snaps.get(key) or [])
            if isinstance(row, dict) and row.get("region_id")
        }
    )
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.is_file() else None
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) if RECEIPT_PATH.is_file() else None
    if log is None:
        failures.append({"check": "log_schema", "detail": "state/placement_log.json is missing"})
    if receipt is None:
        failures.append({"check": "receipt_schema", "detail": "state/placement_receipt.json is missing"})
    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(merged_ids):
            failures.append({"check": "log_coverage", "detail": "placement_log must record one decision per merged region"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "log_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if log.get("counts") != recomputed:
                failures.append({"check": "log_internal_totals", "detail": "counts disagree with decisions"})
            selected = set(log.get("selected_ids") or [])
            dropped = set(log.get("dropped_ids") or [])
            tomb = set(log.get("tombstoned_ids") or [])
            if selected & dropped or selected & tomb or dropped & tomb:
                failures.append({"check": "set_integrity", "detail": "selected, dropped, and tombstoned must be disjoint"})
            if log.get("item_count") != len(log.get("selected_ids") or []):
                failures.append({"check": "log_internal_totals", "detail": "item_count disagrees with selected_ids"})
    if isinstance(receipt, dict) and isinstance(log, dict):
        for key in ("selected_ids", "dropped_ids", "tombstoned_ids", "item_count", "union_count"):
            if receipt.get(key) != log.get(key):
                failures.append({"check": "receipt_internal_totals", "detail": f"{key} disagrees with the placement log"})
                break
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["started", "waiting", "running"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
