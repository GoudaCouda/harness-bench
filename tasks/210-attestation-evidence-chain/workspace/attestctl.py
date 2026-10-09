#!/usr/bin/env python3
"""Local attestation-chain controller. Diagnostic only; never decides artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
KEY_PATH = WORKSPACE / "keyring" / "keys.json"
ART_PATH = WORKSPACE / "staging" / "artifacts.json"
CACHE_PATH = WORKSPACE / "cache" / "verification_cache.json"
LEDGER_PATH = WORKSPACE / "state" / "attestation_ledger.json"
RECEIPT_PATH = WORKSPACE / "state" / "verification_receipt.json"
CLOCK = 1773651600
VALID = {
    "accepted",
    "digest_mismatch",
    "bad_signature",
    "key_revoked",
    "key_not_valid",
    "unknown_key",
    "stale_cache_reverified",
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


def _digest(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def cmd_clock(_: argparse.Namespace) -> int:
    _emit({"verification_clock_epoch": CLOCK})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "keys":
        keys = _load(KEY_PATH)
        if args.selector:
            key = keys.get(args.selector)
            _emit({"key_id": args.selector, "present": key is not None, "key": key})
            return 0
        summary = []
        for key_id, key in sorted(keys.items()):
            summary.append(
                {
                    "key_id": key_id,
                    "generation": key.get("generation"),
                    "not_before": key.get("not_before"),
                    "not_after": key.get("not_after"),
                    "revoked_at": key.get("revoked_at"),
                    "expired_at_clock": CLOCK > int(key.get("not_after") or CLOCK),
                    "revoked_at_clock": key.get("revoked_at") is not None
                    and CLOCK >= int(key["revoked_at"]),
                }
            )
        _emit({"count": len(summary), "keys": summary})
        return 0
    if args.target == "cache":
        _emit(_load(CACHE_PATH))
        return 0
    bundle = _load(ART_PATH)
    artifacts = bundle.get("artifacts") or []
    if args.selector:
        for item in artifacts:
            if item.get("artifact_id") == args.selector:
                _emit(
                    {
                        "artifact": item,
                        "computed_digest": _digest(item.get("payload")),
                        "digest_matches_claim": _digest(item.get("payload")) == item.get("digest"),
                    }
                )
                return 0
        _emit({"artifact_id": args.selector, "present": False})
        return 0
    _emit(
        {
            "bundle_id": bundle.get("bundle_id"),
            "count": len(artifacts),
            "artifact_ids": [item.get("artifact_id") for item in artifacts],
        }
    )
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    bundle = _load(ART_PATH)
    for item in bundle.get("artifacts") or []:
        if item.get("artifact_id") == args.artifact_id:
            _emit(
                {
                    "artifact_id": args.artifact_id,
                    "computed_digest": _digest(item.get("payload")),
                    "claimed_digest": item.get("digest"),
                }
            )
            return 0
    raise SystemExit(f"unknown artifact_id: {args.artifact_id}")


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    bundle = _load(ART_PATH)
    artifacts = bundle.get("artifacts") or []
    expected_ids = [item.get("artifact_id") for item in artifacts]
    ledger = None
    if LEDGER_PATH.is_file():
        try:
            ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append({"check": "ledger_schema", "detail": f"invalid JSON: {exc}"})
    else:
        failures.append({"check": "ledger_schema", "detail": "state/attestation_ledger.json is missing"})
    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {exc}"})
    else:
        failures.append({"check": "receipt_schema", "detail": "state/verification_receipt.json is missing"})
    if isinstance(ledger, dict):
        decisions = ledger.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(artifacts):
            failures.append({"check": "ledger_coverage", "detail": "one decision per artifact is required"})
        else:
            seen = []
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "ledger_schema", "detail": "unknown decision"})
                    break
                seen.append(entry.get("artifact_id"))
            if seen != expected_ids:
                failures.append({"check": "ledger_coverage", "detail": {"expected": expected_ids, "actual": seen}})
            counts = ledger.get("counts")
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if isinstance(entry, dict) and entry.get("decision") in recomputed:
                    recomputed[entry["decision"]] += 1
            if counts != recomputed:
                failures.append({"check": "ledger_internal_totals", "detail": "counts disagree with decisions"})
            accepted = [
                entry.get("artifact_id")
                for entry in decisions
                if isinstance(entry, dict) and entry.get("decision") == "accepted"
            ]
            if ledger.get("accepted_ids") != accepted:
                failures.append({"check": "ledger_internal_totals", "detail": "accepted_ids disagree with decisions"})
    if isinstance(receipt, dict) and isinstance(ledger, dict) and receipt.get("counts") != ledger.get("counts"):
        failures.append({"check": "receipt_internal_totals", "detail": "receipt counts disagree with the ledger"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["keys", "artifacts", "cache"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    digest = sub.add_parser("digest")
    digest.add_argument("artifact_id")
    digest.set_defaults(func=cmd_digest)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
