#!/usr/bin/env python3
"""Local review-queue controller; never approves or pays an invoice."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".ap_review_state.json"
RECEIPT = ROOT / "ap_review_receipt.json"
HEADER = [
    "invoice_line_id",
    "disposition",
    "approved_amount",
    "held_amount",
    "exception_code",
    "review_owner",
    "evidence",
]
CONTROL_FIELDS = {
    "batch_id",
    "policy_id",
    "cutoff_date",
    "currency",
    "execution_state",
    "invoice_line_count",
    "exception_line_count",
    "invoice_total",
    "approved_total",
    "held_total",
}
SOURCE_FILES = [
    "ap_review_template.csv",
    "invoices.csv",
    "match_policy.md",
    "paid_invoice_register.csv",
    "purchase_orders.csv",
    "receipts.csv",
]
CENT = re.compile(r"[0-9]+\.[0-9]{2}\Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: sha256(ROOT / name) for name in SOURCE_FILES}


def bundle_sha256(hashes: dict[str, str]) -> str:
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path.name}: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name} must contain one JSON object")
    return value


def read_rows(path: Path, header: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            raw = list(csv.reader(handle, strict=True))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"cannot parse {path.name}: {type(exc).__name__}") from exc
    if not raw or raw[0] != header:
        raise ValueError(f"{path.name}: exact header required")
    if any(len(row) != len(header) for row in raw[1:]):
        raise ValueError(f"{path.name}: every row must have {len(header)} cells")
    return [dict(zip(header, row)) for row in raw[1:]]


def invoice_rows() -> list[dict[str, str]]:
    return read_rows(
        ROOT / "invoices.csv",
        ["invoice_line_id", "invoice_no", "po_line", "qty", "unit_price"],
    )


def command_status(_: argparse.Namespace) -> int:
    state = read_object(STATE)
    state["sources_intact"] = bundle_sha256(source_hashes()) == state.get(
        "input_bundle_sha256"
    )
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    invoices = invoice_rows()
    matches = [row for row in invoices if row["invoice_line_id"] == args.invoice_line]
    if len(matches) != 1:
        raise SystemExit(f"unknown invoice line: {args.invoice_line}")
    invoice = matches[0]
    po_rows = read_rows(
        ROOT / "purchase_orders.csv",
        ["po_line", "sku", "ordered_qty", "unit_price"],
    )
    receipts = read_rows(
        ROOT / "receipts.csv",
        ["receipt_id", "po_line", "received_at", "quantity", "status"],
    )
    register = read_rows(
        ROOT / "paid_invoice_register.csv",
        ["invoice_no", "status", "status_date", "amount", "reference"],
    )
    result = {
        "invoice": invoice,
        "purchase_order": [row for row in po_rows if row["po_line"] == invoice["po_line"]],
        "receipts": [row for row in receipts if row["po_line"] == invoice["po_line"]],
        "register_events": [row for row in register if row["invoice_no"] == invoice["invoice_no"]],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def money(value: object) -> Decimal | None:
    text = str(value or "")
    if not CENT.fullmatch(text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def validate_package() -> dict:
    errors: list[str] = []
    try:
        rows = read_rows(ROOT / "invoice_match.csv", HEADER)
    except ValueError as exc:
        rows = []
        errors.append(str(exc))
    try:
        control = read_object(ROOT / "payables_control.json")
    except SystemExit as exc:
        control = {}
        errors.append(str(exc))
    invoice_map = {row["invoice_line_id"]: row for row in invoice_rows()}
    ids = [row["invoice_line_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(invoice_map):
        errors.append("review rows must cover each source invoice_line_id exactly once")
    approved = Decimal("0.00")
    held = Decimal("0.00")
    exceptions = 0
    for number, row in enumerate(rows, start=2):
        a, h = money(row["approved_amount"]), money(row["held_amount"])
        source = invoice_map.get(row["invoice_line_id"])
        try:
            invoice_amount = (
                Decimal(source["qty"]) * Decimal(source["unit_price"])
                if source
                else None
            )
        except (InvalidOperation, KeyError):
            invoice_amount = None
        if a is None or h is None or invoice_amount is None or a + h != invoice_amount:
            errors.append(f"review row {number}: approved plus held does not equal invoice amount")
            continue
        approved += a
        held += h
        exceptions += int(h != 0)
    if set(control) != CONTROL_FIELDS:
        errors.append("payables_control.json must use the exact published fields")
    expected_control = {
        "batch_id": "2026-07-ap-review",
        "policy_id": "AP-POL-7.2",
        "cutoff_date": "2026-07-31",
        "currency": "USD",
        "execution_state": "review_only",
        "invoice_line_count": len(rows),
        "exception_line_count": exceptions,
        "invoice_total": f"{approved + held:.2f}",
        "approved_total": f"{approved:.2f}",
        "held_total": f"{held:.2f}",
    }
    if control != expected_control:
        errors.append("payables control does not reconcile with the exact review bytes")
    return {"status": "pass" if not errors else "fail", "errors": errors, "review_rows": len(rows)}


def stage_token(bundle: str, review: str, control: str) -> str:
    raw = f"2026-07-ap-review\n{bundle}\n{review}\n{control}\nreview_only\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def receipt_for(state: dict) -> dict:
    return {
        "receipt_type": "local_ap_review_stage",
        "batch_id": "2026-07-ap-review",
        "state_revision": state["revision"],
        "phase": "staged_for_controller_review",
        "input_bundle_sha256": state["input_bundle_sha256"],
        "review_sha256": state["review_sha256"],
        "control_sha256": state["control_sha256"],
        "stage_token": state["stage_token"],
        "execution_state": "review_only",
        "external_payments_executed": False,
    }


def command_validate(_: argparse.Namespace) -> int:
    result = validate_package()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def command_stage(_: argparse.Namespace) -> int:
    result = validate_package()
    if result["status"] != "pass":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    state = read_object(STATE)
    bundle = bundle_sha256(source_hashes())
    if bundle != state.get("input_bundle_sha256"):
        raise SystemExit("immutable source bundle no longer matches controller state")
    review, control = sha256(ROOT / "invoice_match.csv"), sha256(ROOT / "payables_control.json")
    token = stage_token(bundle, review, control)
    same = state.get("phase") == "staged_for_controller_review" and state.get("stage_token") == token
    if not same:
        state = {
            "schema_version": 1,
            "batch_id": "2026-07-ap-review",
            "phase": "staged_for_controller_review",
            "revision": int(state.get("revision", 0)) + 1,
            "input_bundle_sha256": bundle,
            "review_sha256": review,
            "control_sha256": control,
            "stage_token": token,
            "execution_state": "review_only",
            "external_payments_executed": False,
        }
        STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        RECEIPT.write_text(json.dumps(receipt_for(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "staged", "idempotent_replay": same, "stage_token": token}, indent=2, sort_keys=True))
    return 0


def command_replay(_: argparse.Namespace) -> int:
    state = read_object(STATE)
    errors: list[str] = []
    if state.get("phase") != "staged_for_controller_review" or not RECEIPT.is_file():
        errors.append("batch has not been staged")
    else:
        bundle = bundle_sha256(source_hashes())
        review, control = sha256(ROOT / "invoice_match.csv"), sha256(ROOT / "payables_control.json")
        if (bundle, review, control, stage_token(bundle, review, control)) != (
            state.get("input_bundle_sha256"), state.get("review_sha256"), state.get("control_sha256"), state.get("stage_token")
        ):
            errors.append("staged batch hashes are stale")
        if read_object(RECEIPT) != receipt_for(state):
            errors.append("stage receipt mismatch")
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "stage_token": state.get("stage_token")}, indent=2, sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Local AP review queue controller")
    sub = parser.add_subparsers(required=True)
    status = sub.add_parser("status")
    status.set_defaults(func=command_status)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--invoice-line", required=True)
    inspect.set_defaults(func=command_inspect)
    validate = sub.add_parser("validate")
    validate.set_defaults(func=command_validate)
    stage = sub.add_parser("stage")
    stage.set_defaults(func=command_stage)
    replay = sub.add_parser("replay")
    replay.set_defaults(func=command_replay)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
