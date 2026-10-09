#!/usr/bin/env python3
"""Local settlement-ledger controller.

Read-only operational feedback for the recovery in this workspace. The
controller reports structure, vocabulary, fingerprints, and rule violations it
can observe. It does not decide requests for you, does not reveal which queued
request belongs in which outcome, and never writes to the workspace.

Commands:

    clock                       print the frozen recovery clock and retention window
    inspect ledger [KEY]        show recovered-ledger records currently on disk
    inspect queue [REQUEST_ID]  show queued requests
    fingerprint REQUEST_ID      compute the published fingerprint for a request
    keycheck VALUE              report whether a raw key is usable, and its canonical form
    validate                    check the artifacts on disk for self-consistency
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
LEDGER_PATH = WORKSPACE / "state" / "ledger.json"
QUEUE_PATH = WORKSPACE / "staging" / "replay_queue.json"
RECEIPT_PATH = WORKSPACE / "state" / "recovery_receipt.json"

RECOVERY_CLOCK_EPOCH = 1773478800
RECORD_TTL_SECONDS = 86400

KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
VALID_DECISIONS = {"replayed", "conflict", "executed", "deferred", "rejected"}
VALID_STATUSES = {"completed", "in_flight"}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path.relative_to(WORKSPACE)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.relative_to(WORKSPACE)} is not valid JSON: {exc}")


def _canonical_body(body: Any) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(method: str, path: str, body: Any) -> str:
    payload = f"{method}\n{path}\n{_canonical_body(body)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_key(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    candidate = raw.strip(" \t")
    return candidate if KEY_PATTERN.match(candidate) else None


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def cmd_clock(_: argparse.Namespace) -> int:
    _emit(
        {
            "recovery_clock_epoch": RECOVERY_CLOCK_EPOCH,
            "record_ttl_seconds": RECORD_TTL_SECONDS,
            "retention_cutoff_epoch": RECOVERY_CLOCK_EPOCH - RECORD_TTL_SECONDS,
        }
    )
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "ledger":
        ledger = _load(LEDGER_PATH)
        if not isinstance(ledger, dict):
            raise SystemExit("state/ledger.json must be a JSON object keyed by idempotency key")
        if args.selector:
            if args.selector not in ledger:
                _emit({"key": args.selector, "present": False})
                return 0
            _emit({"key": args.selector, "present": True, "record": ledger[args.selector]})
            return 0
        summary = []
        for key in sorted(ledger):
            record = ledger[key] if isinstance(ledger[key], dict) else {}
            created_at = record.get("created_at")
            age = (
                RECOVERY_CLOCK_EPOCH - int(created_at)
                if isinstance(created_at, int)
                else None
            )
            summary.append(
                {
                    "key": key,
                    "status": record.get("status"),
                    "created_at": created_at,
                    "age_seconds": age,
                    "past_retention": bool(age is not None and age >= RECORD_TTL_SECONDS),
                    "lease_expires_at": record.get("lease_expires_at"),
                    "lease_live": (
                        RECOVERY_CLOCK_EPOCH < int(record["lease_expires_at"])
                        if isinstance(record.get("lease_expires_at"), int)
                        else None
                    ),
                }
            )
        _emit({"count": len(summary), "records": summary})
        return 0

    queue = _load(QUEUE_PATH)
    requests = queue.get("requests") if isinstance(queue, dict) else None
    if not isinstance(requests, list):
        raise SystemExit("staging/replay_queue.json must contain a 'requests' array")
    if args.selector:
        for request in requests:
            if str(request.get("request_id")) == args.selector:
                _emit(request)
                return 0
        _emit({"request_id": args.selector, "present": False})
        return 0
    _emit(
        {
            "queue_id": queue.get("queue_id"),
            "count": len(requests),
            "request_ids": [request.get("request_id") for request in requests],
        }
    )
    return 0


def cmd_fingerprint(args: argparse.Namespace) -> int:
    queue = _load(QUEUE_PATH)
    for request in queue.get("requests", []):
        if str(request.get("request_id")) == args.request_id:
            _emit(
                {
                    "request_id": args.request_id,
                    "canonical_body": _canonical_body(request.get("body")),
                    "fingerprint": _fingerprint(
                        str(request.get("method") or ""),
                        str(request.get("path") or ""),
                        request.get("body"),
                    ),
                }
            )
            return 0
    raise SystemExit(f"unknown request_id: {args.request_id}")


def cmd_keycheck(args: argparse.Namespace) -> int:
    canonical = _canonical_key(args.value)
    _emit(
        {
            "raw": args.value,
            "usable": canonical is not None,
            "canonical_key": canonical,
            "rule": "^[A-Za-z0-9._:-]{1,64}$ after trimming spaces and tabs",
        }
    )
    return 0


def _validate_ledger(ledger: Any, failures: list[dict[str, Any]]) -> None:
    if not isinstance(ledger, dict):
        failures.append({"check": "ledger_schema", "detail": "ledger is not a JSON object"})
        return
    schema_problems: list[str] = []
    retention_problems: list[str] = []
    lease_problems: list[str] = []
    for key, record in sorted(ledger.items()):
        if not isinstance(record, dict):
            schema_problems.append(f"{key}: record is not an object")
            continue
        status = record.get("status")
        if status not in VALID_STATUSES:
            schema_problems.append(f"{key}: status {status!r} is not a known status")
        if not isinstance(record.get("created_at"), int):
            schema_problems.append(f"{key}: created_at must be an integer epoch")
        if status == "completed":
            if not isinstance(record.get("fingerprint"), str):
                schema_problems.append(f"{key}: completed record needs a fingerprint")
            if not isinstance(record.get("response"), dict):
                schema_problems.append(f"{key}: completed record needs a stored response")
        if status == "in_flight" and not isinstance(record.get("lease_expires_at"), int):
            schema_problems.append(f"{key}: in_flight record needs lease_expires_at")
        created_at = record.get("created_at")
        if isinstance(created_at, int) and RECOVERY_CLOCK_EPOCH - created_at >= RECORD_TTL_SECONDS:
            retention_problems.append(key)
        lease = record.get("lease_expires_at")
        if (
            status == "in_flight"
            and isinstance(lease, int)
            and RECOVERY_CLOCK_EPOCH >= lease
        ):
            lease_problems.append(key)
    if schema_problems:
        failures.append({"check": "ledger_schema", "detail": schema_problems})
    if retention_problems:
        failures.append(
            {
                "check": "ledger_retention",
                "detail": f"records past the retention window remain: {retention_problems}",
            }
        )
    if lease_problems:
        failures.append(
            {
                "check": "ledger_leases",
                "detail": f"records with a dead lease remain: {lease_problems}",
            }
        )


def _validate_receipt(
    receipt: Any,
    ledger: Any,
    requests: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    if not isinstance(receipt, dict):
        failures.append({"check": "receipt_schema", "detail": "receipt is not a JSON object"})
        return
    decisions = receipt.get("decisions")
    if not isinstance(decisions, list):
        failures.append({"check": "receipt_schema", "detail": "decisions must be an array"})
        return

    schema_problems: list[str] = []
    seen: dict[str, str] = {}
    for entry in decisions:
        if not isinstance(entry, dict):
            schema_problems.append("decision entry is not an object")
            continue
        request_id = entry.get("request_id")
        decision = entry.get("decision")
        if not isinstance(request_id, str):
            schema_problems.append("decision entry needs a string request_id")
            continue
        if decision not in VALID_DECISIONS:
            schema_problems.append(f"{request_id}: decision {decision!r} is not a known outcome")
            continue
        if request_id in seen:
            schema_problems.append(f"{request_id}: duplicate decision")
            continue
        seen[request_id] = decision
    if schema_problems:
        failures.append({"check": "receipt_schema", "detail": schema_problems})

    expected_ids = {str(request.get("request_id")) for request in requests}
    missing = sorted(expected_ids - set(seen))
    extra = sorted(set(seen) - expected_ids)
    if missing or extra:
        failures.append(
            {
                "check": "receipt_queue_coverage",
                "detail": {"missing": missing, "unknown": extra},
            }
        )

    counts = receipt.get("counts")
    recomputed = {name: 0 for name in sorted(VALID_DECISIONS)}
    for decision in seen.values():
        recomputed[decision] += 1
    if counts != recomputed:
        failures.append(
            {
                "check": "receipt_internal_totals",
                "detail": "counts disagree with the decisions actually recorded",
            }
        )

    body_by_id = {str(r.get("request_id")): r for r in requests}
    executed_sum = 0
    for entry in decisions:
        if not isinstance(entry, dict) or entry.get("decision") != "executed":
            continue
        request = body_by_id.get(str(entry.get("request_id")), {})
        body = request.get("body") if isinstance(request, dict) else {}
        amount = body.get("amount_cents") if isinstance(body, dict) else None
        if isinstance(amount, int):
            executed_sum += amount
    if receipt.get("settled_total_cents") != executed_sum:
        failures.append(
            {
                "check": "receipt_internal_totals",
                "detail": "settled_total_cents disagrees with the executed decisions recorded",
            }
        )

    if not isinstance(ledger, dict):
        return
    replay_problems: list[str] = []
    executed_problems: list[str] = []
    for entry in decisions:
        if not isinstance(entry, dict):
            continue
        decision = entry.get("decision")
        key = _canonical_key(entry.get("idempotency_key"))
        record = ledger.get(key) if key else None
        if decision == "replayed":
            stored = record.get("response") if isinstance(record, dict) else None
            if stored is None or stored != entry.get("response"):
                replay_problems.append(str(entry.get("request_id")))
        elif decision == "executed":
            request = body_by_id.get(str(entry.get("request_id")), {})
            expected = _fingerprint(
                str(request.get("method") or ""),
                str(request.get("path") or ""),
                request.get("body"),
            )
            if not isinstance(record, dict):
                executed_problems.append(f"{entry.get('request_id')}: no ledger record for key")
            elif record.get("status") != "completed":
                executed_problems.append(f"{entry.get('request_id')}: ledger record is not completed")
            elif record.get("fingerprint") != expected:
                executed_problems.append(f"{entry.get('request_id')}: ledger fingerprint mismatch")
            elif record.get("created_at") != RECOVERY_CLOCK_EPOCH:
                executed_problems.append(
                    f"{entry.get('request_id')}: settled record must start a fresh retention window"
                )
    if replay_problems:
        failures.append(
            {
                "check": "replay_response_binding",
                "detail": f"replayed responses do not match the stored record: {replay_problems}",
            }
        )
    if executed_problems:
        failures.append({"check": "executed_record_binding", "detail": executed_problems})


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    ledger = None
    try:
        ledger = _load(LEDGER_PATH)
    except SystemExit as exc:
        failures.append({"check": "ledger_schema", "detail": str(exc)})
    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {exc}"})
    else:
        failures.append(
            {"check": "receipt_schema", "detail": "state/recovery_receipt.json is missing"}
        )

    queue = _load(QUEUE_PATH)
    requests = [r for r in queue.get("requests", []) if isinstance(r, dict)]

    if ledger is not None:
        _validate_ledger(ledger, failures)
    if receipt is not None:
        _validate_receipt(receipt, ledger, requests, failures)

    checks = [
        "ledger_schema",
        "ledger_retention",
        "ledger_leases",
        "receipt_schema",
        "receipt_queue_coverage",
        "receipt_internal_totals",
        "replay_response_binding",
        "executed_record_binding",
    ]
    failed = sorted({str(item["check"]) for item in failures})
    _emit(
        {
            "status": "pass" if not failed else "fail",
            "checks": checks,
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
    inspect.add_argument("target", choices=["ledger", "queue"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)

    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("request_id")
    fingerprint.set_defaults(func=cmd_fingerprint)

    keycheck = sub.add_parser("keycheck")
    keycheck.add_argument("value")
    keycheck.set_defaults(func=cmd_keycheck)

    sub.add_parser("validate").set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
