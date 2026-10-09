#!/usr/bin/env python3
"""Local Westline offline patchset merge-gate controller.

Read-only operational feedback. The controller reports structure, vocabulary,
and self-consistency failures it can observe. It does not decide patches, does
not name which patch belongs in which outcome, and never writes to the workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
POLICY_PATH = WORKSPACE / "policy" / "merge_policy.json"
PATCH_PATH = WORKSPACE / "staging" / "patchset.json"
LOG_PATH = WORKSPACE / "state" / "merge_log.json"
RECEIPT_PATH = WORKSPACE / "state" / "merge_receipt.json"
CLOCK = 1774256400
VALID = {"admitted", "blocked_checks", "blocked_owners", "blocked_rebase", "malformed"}


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
    if args.target == "policy":
        _emit(_load(POLICY_PATH))
        return 0
    document = _load(PATCH_PATH)
    patches = document.get("patches") if isinstance(document, dict) else []
    if args.selector:
        hits = [row for row in patches if isinstance(row, dict) and row.get("patch_id") == args.selector]
        _emit({"patch_id": args.selector, "rows": hits})
        return 0
    _emit(
        {
            "batch_id": document.get("batch_id"),
            "count": len(patches),
            "patch_ids": [row.get("patch_id") if isinstance(row, dict) else None for row in patches],
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    patches = (_load(PATCH_PATH) or {}).get("patches") or []
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.is_file() else None
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) if RECEIPT_PATH.is_file() else None
    if log is None:
        failures.append({"check": "log_schema", "detail": "state/merge_log.json is missing"})
    if receipt is None:
        failures.append({"check": "receipt_schema", "detail": "state/merge_receipt.json is missing"})
    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(patches):
            failures.append({"check": "log_coverage", "detail": "merge_log must record one decision per patch"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "log_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if log.get("counts") != recomputed:
                failures.append({"check": "log_internal_totals", "detail": "counts disagree with decisions"})
            if log.get("admitted_count") != len(log.get("admitted_ids") or []):
                failures.append({"check": "log_internal_totals", "detail": "admitted_count disagrees with admitted_ids"})
    if isinstance(receipt, dict) and isinstance(log, dict):
        if receipt.get("counts") != log.get("counts") or receipt.get("admitted_ids") != log.get("admitted_ids"):
            failures.append({"check": "receipt_internal_totals", "detail": "receipt disagrees with the merge log"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["policy", "patches"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
