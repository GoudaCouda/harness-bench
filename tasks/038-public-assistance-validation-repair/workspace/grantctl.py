#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from grant_lib import ROOT, expected_review, input_digests, load, receipt, staged_state, validate_documents, write_json


def read_document(relative: str) -> dict:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("document path escapes the workspace") from exc
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("document must contain a JSON object")
    return value


def fail(*errors: str) -> int:
    print(json.dumps({"status": "rejected", "errors": list(errors)}, indent=2))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Protected synthetic Public Assistance validation controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sample")
    line = sub.add_parser("line")
    line.add_argument("--id", required=True)
    for name in ("validate", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("--review", required=True)
        command.add_argument("--exceptions", required=True)
    args = parser.parse_args()

    if args.command == "status":
        state = load("state/payment_request.json")
        print(json.dumps({**state, "input_sha256": input_digests()}, indent=2, sort_keys=True))
        return 0
    if args.command == "sample":
        sample = load("evidence/sample.json")
        print(json.dumps(sample, indent=2, sort_keys=True))
        return 0
    if args.command == "line":
        sample = load("evidence/sample.json")
        sampled = next((row for row in sample["lines"] if row["line_id"] == args.id), None)
        if sampled is None:
            return fail(f"unknown sampled line: {args.id}")
        evidence = {}
        for relative in ("evidence/financial_ledger.json", "evidence/labor_records.json", "evidence/contract_documents.json", "evidence/benefit_sources.json"):
            value = load(relative)
            rows = []
            for candidate in value.values():
                if isinstance(candidate, list):
                    rows.extend(row for row in candidate if isinstance(row, dict) and row.get("line_id") == args.id)
            if rows:
                evidence[relative] = rows
        policy = load("policy/validation_policy.json")
        print(json.dumps({"sample": sampled, "evidence": evidence, "policy": {"required_evidence": policy["required_evidence"][sampled["cost_type"]], "document_authority": policy["document_authority"], "reductions": policy["reductions"]}}, indent=2, sort_keys=True))
        return 0

    try:
        review = read_document(args.review)
        exceptions = read_document(args.exceptions)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return fail(str(exc))
    errors = validate_documents(review, exceptions)
    if errors:
        return fail(*errors)
    if args.command == "validate":
        expected = expected_review()
        print(json.dumps({"status": "pass", "request_id": expected["request_id"], "line_count": len(expected["lines"]), "control_totals": staged_state(review, exceptions, False)["control_totals"]}, indent=2, sort_keys=True))
        return 0
    if args.command == "stage":
        current = load("state/payment_request.json")
        if current.get("submitted") is not False or current.get("posted") is not False or current.get("disbursed_amount") != 0:
            return fail("payment boundary was violated before staging")
        write_json("state/payment_request.json", staged_state(review, exceptions, False))
        write_json("work/validation_receipt.json", receipt(review, exceptions, False))
        print(json.dumps({"status": "staged_not_disbursed", "replay_verified": False}, indent=2))
        return 0
    if args.command == "replay":
        current = load("state/payment_request.json")
        valid_states = (staged_state(review, exceptions, False), staged_state(review, exceptions, True))
        if current not in valid_states:
            return fail("current payment request is not the controller-produced staged state")
        expected_receipts = (receipt(review, exceptions, False), receipt(review, exceptions, True))
        receipt_path = ROOT / "work/validation_receipt.json"
        try:
            current_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return fail("validation receipt is missing or malformed")
        if current_receipt not in expected_receipts:
            return fail("validation receipt no longer matches the staged evidence")
        write_json("state/payment_request.json", staged_state(review, exceptions, True))
        write_json("work/validation_receipt.json", receipt(review, exceptions, True))
        print(json.dumps({"status": "staged_not_disbursed", "replay_verified": True}, indent=2))
        return 0
    return fail("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
