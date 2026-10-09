#!/usr/bin/env python3
"""Local bounded-archive controller. Diagnostic only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
ARCHIVE_PATH = WORKSPACE / "state" / "archive.json"
QUEUE_PATH = WORKSPACE / "staging" / "ingest_queue.json"
RECEIPT_PATH = WORKSPACE / "state" / "ingest_receipt.json"
CLOCK = 1773824400
MAX_BYTES = 10000
MAX_OBJECTS = 4
VALID = {"ingested", "replayed", "conflict", "checksum_mismatch", "capacity_exceeded", "rejected"}


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
    _emit({"archive_clock_epoch": CLOCK, "max_bytes": MAX_BYTES, "max_objects": MAX_OBJECTS})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "archive":
        document = _load(ARCHIVE_PATH)
        objects = document.get("objects") if isinstance(document, dict) else {}
        if args.selector:
            _emit({"object_id": args.selector, "present": args.selector in objects, "record": objects.get(args.selector)})
            return 0
        used = sum(int(item.get("bytes") or 0) for item in objects.values())
        _emit({"count": len(objects), "used_bytes": used, "object_ids": sorted(objects)})
        return 0
    queue = _load(QUEUE_PATH)
    items = queue.get("items") if isinstance(queue, dict) else []
    if args.selector:
        for item in items:
            if item.get("object_id") == args.selector:
                _emit(item)
                return 0
        _emit({"object_id": args.selector, "present": False})
        return 0
    _emit({"count": len(items), "object_ids": [item.get("object_id") for item in items]})
    return 0


def cmd_checksum(args: argparse.Namespace) -> int:
    queue = _load(QUEUE_PATH)
    for item in queue.get("items") or []:
        if item.get("object_id") == args.object_id:
            computed = hashlib.sha256(str(item.get("content") or "").encode("utf-8")).hexdigest()
            _emit({"object_id": args.object_id, "computed": computed, "claimed": item.get("checksum"), "matches": computed == item.get("checksum")})
            return 0
    path = WORKSPACE / "state" / "objects" / f"{args.object_id}.txt"
    if path.is_file():
        computed = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        _emit({"object_id": args.object_id, "computed": computed, "source": "state/objects"})
        return 0
    raise SystemExit(f"unknown object_id: {args.object_id}")


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    archive = _load(ARCHIVE_PATH)
    objects = archive.get("objects") if isinstance(archive, dict) else None
    if not isinstance(objects, dict):
        failures.append({"check": "archive_schema", "detail": "objects must be a JSON object"})
        objects = {}
    used_bytes = sum(int(item.get("bytes") or 0) for item in objects.values() if isinstance(item, dict))
    if archive.get("used_bytes") != used_bytes or archive.get("used_objects") != len(objects):
        failures.append({"check": "archive_internal_totals", "detail": "used_bytes/used_objects disagree with objects"})
    if used_bytes > MAX_BYTES or len(objects) > MAX_OBJECTS:
        failures.append({"check": "archive_capacity", "detail": "archive exceeds published bounds"})
    pinned_missing = [
        object_id
        for object_id, item in objects.items()
        if isinstance(item, dict) and item.get("pinned") and not (WORKSPACE / "state" / "objects" / f"{object_id}.txt").is_file()
    ]
    if pinned_missing:
        failures.append({"check": "pinned_presence", "detail": pinned_missing})
    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as extra:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {extra}"})
    else:
        failures.append({"check": "receipt_schema", "detail": "state/ingest_receipt.json is missing"})
    queue = _load(QUEUE_PATH)
    items = queue.get("items") or []
    if isinstance(receipt, dict):
        decisions = receipt.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(items):
            failures.append({"check": "receipt_coverage", "detail": "one decision per staging item is required"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "receipt_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if receipt.get("counts") != recomputed:
                failures.append({"check": "receipt_internal_totals", "detail": "counts disagree with decisions"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["archive", "queue"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    checksum = sub.add_parser("checksum")
    checksum.add_argument("object_id")
    checksum.set_defaults(func=cmd_checksum)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
