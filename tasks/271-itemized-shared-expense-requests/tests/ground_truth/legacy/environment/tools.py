#!/usr/bin/env python3
"""case_17 面向 Agent 的最小权限本地工具。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def metadata(workspace: Path) -> dict[str, Any]:
    return json.loads((workspace / "workspace_metadata.json").read_text(encoding="utf-8"))


def read_expense(workspace: Path) -> dict[str, Any]:
    return json.loads((workspace / "expense_ledger.json").read_text(encoding="utf-8"))


def list_contacts(workspace: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(workspace / "state.sqlite") as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT participant_id, display_name, account_id, active FROM contacts ORDER BY participant_id"
        ).fetchall()
    return [dict(row) for row in rows]


def create_request(args: argparse.Namespace) -> dict[str, Any]:
    meta = metadata(args.workspace)
    expense = read_expense(args.workspace)
    request_id = f"req-{meta['run_tag']}-{args.participant_id}"
    with sqlite3.connect(args.workspace / "state.sqlite") as connection:
        contact = connection.execute(
            "SELECT participant_id, account_id, active FROM contacts WHERE participant_id = ?",
            (args.participant_id,),
        ).fetchone()
        if contact is None or contact[2] != 1:
            raise ValueError("contact_not_found_or_inactive")
        if contact[1] != args.recipient_account_id:
            raise ValueError("contact_account_mismatch")
        if args.participant_id == expense["payer"]["participant_id"]:
            raise ValueError("payer_cannot_receive_request")
        existing = connection.execute(
            "SELECT request_id, amount_fen, recipient_account_id, note FROM payment_requests WHERE run_tag = ? AND participant_id = ?",
            (meta["run_tag"], args.participant_id),
        ).fetchone()
        if existing is not None:
            same = existing[1] == args.amount_fen and existing[2] == args.recipient_account_id and existing[3] == args.note
            if not same:
                raise ValueError("idempotency_conflict")
            return {"status": "already_exists", "request_id": existing[0]}
        connection.execute(
            """INSERT INTO payment_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id,
                meta["run_tag"],
                expense["expense_id"],
                args.participant_id,
                expense["payer"]["participant_id"],
                args.recipient_account_id,
                "collect_from_recipient",
                args.amount_fen,
                expense["currency"],
                args.note,
                "pending",
                meta["fixed_time"],
            ),
        )
        connection.execute(
            "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
            (f"audit-create-{args.participant_id}", meta["run_tag"], "create_payment_request", request_id, meta["fixed_time"]),
        )
    return {"status": "created", "request_id": request_id}


def write_report(args: argparse.Namespace) -> dict[str, Any]:
    meta = metadata(args.workspace)
    content = json.loads(args.content_json)
    required = {"success", "skipped", "missing"}
    if set(content) != required or not all(isinstance(content[key], list) for key in required):
        raise ValueError("invalid_report_shape")
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report_id = f"report-{meta['run_tag']}-v1"
    with sqlite3.connect(args.workspace / "state.sqlite") as connection:
        existing = connection.execute(
            "SELECT content_json FROM status_reports WHERE run_tag = ?", (meta["run_tag"],)
        ).fetchone()
        if existing is not None:
            if existing[0] != canonical:
                raise ValueError("idempotency_conflict")
            return {"status": "already_exists", "report_id": report_id}
        connection.execute(
            "INSERT INTO status_reports VALUES (?, ?, ?, ?)",
            (report_id, meta["run_tag"], canonical, meta["fixed_time"]),
        )
        connection.execute(
            "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
            ("audit-report-case_17", meta["run_tag"], "write_status_report", report_id, meta["fixed_time"]),
        )
    return {"status": "written", "report_id": report_id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("read-expense")
    subparsers.add_parser("list-contacts")
    create = subparsers.add_parser("create-payment-request")
    create.add_argument("--participant-id", required=True)
    create.add_argument("--recipient-account-id", required=True)
    create.add_argument("--amount-fen", type=int, required=True)
    create.add_argument("--note", required=True)
    report = subparsers.add_parser("write-status-report")
    report.add_argument("--content-json", required=True)
    args = parser.parse_args()
    try:
        if args.command == "read-expense":
            emit({"status": "ok", "expense": read_expense(args.workspace)})
        elif args.command == "list-contacts":
            emit({"status": "ok", "contacts": list_contacts(args.workspace)})
        elif args.command == "create-payment-request":
            emit(create_request(args))
        elif args.command == "write-status-report":
            emit(write_report(args))
        else:
            raise AssertionError("unsupported command")
    except (ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        emit({"status": "error", "error": str(exc)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
