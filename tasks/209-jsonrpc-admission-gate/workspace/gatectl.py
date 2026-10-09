#!/usr/bin/env python3
"""Local JSON-RPC admission-gate controller.

Read-only operational feedback for the gate in this workspace. The controller
reports structure, vocabulary, and self-consistency failures it can observe.
It does not decide batch items, does not name which item belongs in which
outcome, and never writes to the workspace.

Commands:

    clock                       print the frozen gate clock
    inspect catalog [METHOD]    show catalogued methods
    inspect tenants [TENANT]    show tenant capability grants
    inspect freeze              show the freeze overlay
    inspect batch [INDEX]       show inbound batch items
    schemacheck METHOD          list required params for a catalogued method
    validate                    check the artifacts on disk for self-consistency
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
CATALOG_PATH = WORKSPACE / "catalogs" / "method_catalog.json"
TENANT_PATH = WORKSPACE / "catalogs" / "tenant_capabilities.json"
FREEZE_PATH = WORKSPACE / "overlays" / "freeze.json"
BATCH_PATH = WORKSPACE / "staging" / "inbound_batch.json"
LOG_PATH = WORKSPACE / "state" / "admission_log.json"
RECEIPT_PATH = WORKSPACE / "state" / "gate_receipt.json"

GATE_CLOCK_EPOCH = 1773565200
VALID_DECISIONS = {
    "admitted",
    "frozen",
    "method_not_found",
    "tenant_denied",
    "invalid_params",
    "malformed",
}


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
    if args.target == "catalog":
        catalog = _load(CATALOG_PATH)
        methods = catalog.get("methods") if isinstance(catalog, dict) else {}
        if args.selector:
            _emit(
                {
                    "method": args.selector,
                    "present": args.selector in methods,
                    "spec": methods.get(args.selector),
                }
            )
            return 0
        _emit({"count": len(methods), "methods": sorted(methods)})
        return 0
    if args.target == "tenants":
        document = _load(TENANT_PATH)
        tenants = document.get("tenants") if isinstance(document, dict) else {}
        if args.selector:
            _emit(
                {
                    "tenant_id": args.selector,
                    "present": args.selector in tenants,
                    "capabilities": tenants.get(args.selector),
                }
            )
            return 0
        _emit({"count": len(tenants), "tenant_ids": sorted(tenants)})
        return 0
    if args.target == "freeze":
        _emit(_load(FREEZE_PATH))
        return 0
    batch = _load(BATCH_PATH)
    items = batch.get("items") if isinstance(batch, dict) else []
    if args.selector is not None:
        try:
            index = int(args.selector)
        except ValueError:
            raise SystemExit("batch selector must be an integer index")
        if index < 0 or index >= len(items):
            _emit({"index": index, "present": False})
            return 0
        item = items[index]
        _emit(
            {
                "index": index,
                "item": item,
                "has_id": isinstance(item, dict) and "id" in item,
                "jsonrpc": item.get("jsonrpc") if isinstance(item, dict) else None,
            }
        )
        return 0
    _emit(
        {
            "batch_id": batch.get("batch_id"),
            "count": len(items),
            "ids": [item.get("id") if isinstance(item, dict) else None for item in items],
        }
    )
    return 0


def cmd_schemacheck(args: argparse.Namespace) -> int:
    catalog = _load(CATALOG_PATH)
    spec = (catalog.get("methods") or {}).get(args.method)
    _emit(
        {
            "method": args.method,
            "catalogued": spec is not None,
            "required_params": (spec or {}).get("required_params"),
            "capability": (spec or {}).get("capability"),
        }
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    batch = _load(BATCH_PATH)
    items = [item for item in batch.get("items", [])]
    freeze = _load(FREEZE_PATH)
    frozen = set(freeze.get("frozen_methods") or []) - set(freeze.get("lifted_methods") or [])

    log = None
    if LOG_PATH.is_file():
        try:
            log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append({"check": "log_schema", "detail": f"invalid JSON: {exc}"})
    else:
        failures.append({"check": "log_schema", "detail": "state/admission_log.json is missing"})

    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as extra:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {extra}"})
    else:
        failures.append({"check": "receipt_schema", "detail": "state/gate_receipt.json is missing"})

    if isinstance(log, dict):
        decisions = log.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(items):
            failures.append(
                {
                    "check": "log_coverage",
                    "detail": "admission_log must record one decision per batch item",
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
            counts = log.get("counts")
            recomputed = {name: 0 for name in sorted(VALID_DECISIONS)}
            for decision in seen.values():
                recomputed[decision] += 1
            if counts != recomputed:
                failures.append(
                    {
                        "check": "log_internal_totals",
                        "detail": "counts disagree with the decisions actually recorded",
                    }
                )
            forwarded = log.get("forwarded_methods") or []
            leaked_frozen = [name for name in forwarded if name in frozen]
            if leaked_frozen:
                failures.append(
                    {
                        "check": "freeze_integrity",
                        "detail": f"frozen methods were forwarded: {leaked_frozen}",
                    }
                )

    if isinstance(receipt, dict) and isinstance(log, dict):
        responses = receipt.get("response_batch")
        if not isinstance(responses, list):
            failures.append({"check": "receipt_schema", "detail": "response_batch must be an array"})
        else:
            notifications = [
                entry
                for entry in log.get("decisions") or []
                if isinstance(entry, dict) and entry.get("notification") is True
            ]
            if receipt.get("response_count") != len(responses):
                failures.append(
                    {
                        "check": "receipt_internal_totals",
                        "detail": "response_count disagrees with response_batch length",
                    }
                )
            if len(responses) != len(items) - len(notifications):
                failures.append(
                    {
                        "check": "notification_silence",
                        "detail": "notifications must not produce a JSON-RPC response",
                    }
                )
            if receipt.get("counts") != log.get("counts"):
                failures.append(
                    {
                        "check": "receipt_internal_totals",
                        "detail": "receipt counts disagree with the admission log",
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
                "freeze_integrity",
                "receipt_schema",
                "receipt_internal_totals",
                "notification_silence",
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
    inspect.add_argument("target", choices=["catalog", "tenants", "freeze", "batch"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    schema = sub.add_parser("schemacheck")
    schema.add_argument("method")
    schema.set_defaults(func=cmd_schemacheck)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
