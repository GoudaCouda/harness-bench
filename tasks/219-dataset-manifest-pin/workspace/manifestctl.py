#!/usr/bin/env python3
"""Local Shorefront dataset-manifest pin controller.

Read-only operational feedback. The controller reports structure, vocabulary,
and self-consistency failures it can observe. It does not decide requests, does
not name which request belongs in which outcome, and never writes to the workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
MANIFEST_PATH = WORKSPACE / "catalogs" / "manifest.json"
QUEUE_PATH = WORKSPACE / "staging" / "ingest_queue.json"
LOG_PATH = WORKSPACE / "state" / "ingest_log.json"
RECEIPT_PATH = WORKSPACE / "state" / "manifest_receipt.json"
CLOCK = 1774429200
VALID = {
    "ingested",
    "updated",
    "pin_protected",
    "digest_mismatch",
    "rejected_scheme",
    "malformed",
}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path.relative_to(WORKSPACE)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as extra:
        raise SystemExit(f"{path.relative_to(WORKSPACE)} is not valid JSON: {extra}")


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def cmd_clock(_: argparse.Namespace) -> int:
    _emit({"gate_clock_epoch": CLOCK})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "manifest":
        document = _load(MANIFEST_PATH)
        datasets = document.get("datasets") if isinstance(document, dict) else {}
        if args.selector:
            _emit({"dataset_id": args.selector, "present": args.selector in datasets, "row": datasets.get(args.selector)})
            return 0
        _emit({"count": len(datasets), "dataset_ids": sorted(datasets), "pinned": sorted(key for key, row in datasets.items() if isinstance(row, dict) and row.get("pinned"))})
        return 0
    document = _load(QUEUE_PATH)
    requests = document.get("requests") if isinstance(document, dict) else []
    if args.selector:
        hits = [row for row in requests if isinstance(row, dict) and row.get("request_id") == args.selector]
        _emit({"request_id": args.selector, "rows": hits})
        return 0
    _emit(
        {
            "queue_id": document.get("queue_id"),
            "count": len(requests),
            "request_ids": [row.get("request_id") if isinstance(row, dict) else None for row in requests],
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    requests = (_load(QUEUE_PATH) or {}).get("requests") or []
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.is_file() else None
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) if RECEIPT_PATH.is_file() else None
    if log is None:
        failures.append({"check": "log_schema", "detail": "state/ingest_log.json is missing"})
    if receipt is None:
        failures.append({"check": "receipt_schema", "detail": "state/manifest_receipt.json is missing"})
    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(requests):
            failures.append({"check": "log_coverage", "detail": "ingest_log must record one decision per request"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "log_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if log.get("counts") != recomputed:
                failures.append({"check": "log_internal_totals", "detail": "counts disagree with decisions"})
            ids = log.get("dataset_ids") or []
            if ids != sorted(ids):
                failures.append({"check": "log_internal_totals", "detail": "dataset_ids must be sorted"})
            pinned = set(log.get("pinned_ids") or [])
            if not pinned.issubset(set(ids)):
                failures.append({"check": "pin_integrity", "detail": "pinned_ids must be a subset of dataset_ids"})
    if isinstance(receipt, dict) and isinstance(log, dict):
        if receipt.get("counts") != log.get("counts") or receipt.get("dataset_ids") != log.get("dataset_ids") or receipt.get("pinned_ids") != log.get("pinned_ids"):
            failures.append({"check": "receipt_internal_totals", "detail": "receipt disagrees with the ingest log"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["manifest", "queue"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
