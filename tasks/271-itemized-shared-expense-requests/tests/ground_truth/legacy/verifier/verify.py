#!/usr/bin/env python3
"""独立复算并验收 case_17 的终态与副作用。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_amount(amount_fen: int, participant_ids: list[str]) -> dict[str, int]:
    sign = 1 if amount_fen >= 0 else -1
    quotient, remainder = divmod(abs(amount_fen), len(participant_ids))
    result = {participant_id: sign * quotient for participant_id in participant_ids}
    for participant_id in participant_ids[:remainder]:
        result[participant_id] += sign
    return result


def calculate_shares(expense: dict[str, Any]) -> dict[str, int]:
    shares: dict[str, int] = {}
    for item in expense["line_items"]:
        for participant_id, value in split_amount(item["amount_fen"], item["participant_ids"]).items():
            shares[participant_id] = shares.get(participant_id, 0) + value
    return dict(sorted(shares.items()))


def table_rows(connection: sqlite3.Connection, table: str, order_by: str) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]


def verify(workspace: Path, fixtures: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail})

    seed = load_json(fixtures / "seed_state.json")
    expected_entries = {"expense_ledger.json", "contacts.json", "workspace_metadata.json", "state.sqlite"}
    observed_entries = set()
    workspace_shape_ok = workspace.is_dir() and not workspace.is_symlink()
    if workspace_shape_ok:
        for path in workspace.iterdir():
            observed_entries.add(path.name)
            if path.is_symlink() or not path.is_file():
                workspace_shape_ok = False
    workspace_shape_ok = workspace_shape_ok and observed_entries == expected_entries
    check(
        "workspace_inventory_exact",
        workspace_shape_ok,
        "工作区只能含四个规定的普通文件，不得有额外文件、目录或符号链接",
    )
    canonical_contacts = {
        "schema_version": "case17_contacts_v1",
        "contacts": seed["contacts"],
    }
    expected_contacts_bytes = (
        json.dumps(canonical_contacts, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    expense_path = workspace / "expense_ledger.json"
    contacts_path = workspace / "contacts.json"
    check(
        "source_expense_unchanged",
        expense_path.is_file() and file_sha256(expense_path) == file_sha256(fixtures / "expense_ledger.json"),
        "费用源文件必须与不可变 fixture 完全一致",
    )
    check(
        "source_contacts_unchanged",
        contacts_path.is_file() and contacts_path.read_bytes() == expected_contacts_bytes,
        "联系人源文件必须保持 reset 时的规范化内容",
    )
    expected_metadata = {
        "schema_version": "case17_workspace_metadata_v1",
        "fixed_time": seed["fixed_time"],
        "run_tag": seed["run_tag"],
        "source_files": ["expense_ledger.json", "contacts.json"],
    }
    metadata_ok = False
    try:
        metadata_ok = load_json(workspace / "workspace_metadata.json") == expected_metadata
    except (OSError, ValueError, TypeError):
        metadata_ok = False
    check("workspace_metadata_unchanged", metadata_ok, "固定时间、run_tag 和来源声明不得修改")
    try:
        expense = load_json(expense_path)
        shares = calculate_shares(expense)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError):
        expense = load_json(fixtures / "expense_ledger.json")
        shares = calculate_shares(expense)
        check("expense_parseable", False, "费用源不可解析，已使用 fixture 继续诊断")
    else:
        check("expense_parseable", True, "费用源结构可解析")

    database = workspace / "state.sqlite"
    if not database.is_file():
        check("database_exists", False, "状态数据库缺失")
        return finalize(checks)
    with sqlite3.connect(database) as connection:
        contacts = table_rows(connection, "contacts", "participant_id")
        transactions = table_rows(connection, "existing_transactions", "transaction_id")
        requests = table_rows(connection, "payment_requests", "request_id")
        transfers = table_rows(connection, "transfers", "transfer_id")
        reports = table_rows(connection, "status_reports", "report_id")
        audits = table_rows(connection, "audit_log", "audit_id")
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]

    expected_contacts = [{**row, "active": int(row["active"])} for row in seed["contacts"]]
    check("contacts_table_unchanged", contacts == sorted(expected_contacts, key=lambda row: row["participant_id"]), "联系人数据库不得修改")
    check("existing_transactions_unchanged", transactions == seed["existing_transactions"], "既有交易必须逐字段保持不变")
    check("transfers_unchanged", transfers == seed["transfers"], "本任务不得创建、修改或删除转账")
    check(
        "database_schema_not_expanded",
        tables == ["audit_log", "contacts", "existing_transactions", "payment_requests", "status_reports", "transfers"],
        "不得创建绕过工具权限的新业务表",
    )

    prior = [row for row in requests if row["run_tag"] != seed["run_tag"]]
    current = [row for row in requests if row["run_tag"] == seed["run_tag"]]
    check("prior_requests_unchanged", prior == seed["payment_requests"], "既有付款请求必须保持不变")
    contacts_by_id = {row["participant_id"]: row for row in expected_contacts}
    payer_id = expense["payer"]["participant_id"]
    expected_current = []
    for participant_id, amount_fen in sorted(shares.items()):
        if participant_id == payer_id:
            continue
        contact = contacts_by_id[participant_id]
        expected_current.append(
            {
                "request_id": f"req-{seed['run_tag']}-{participant_id}",
                "run_tag": seed["run_tag"],
                "expense_id": expense["expense_id"],
                "participant_id": participant_id,
                "requester_id": payer_id,
                "recipient_account_id": contact["account_id"],
                "direction": "collect_from_recipient",
                "amount_fen": amount_fen,
                "currency": expense["currency"],
                "note": expense["request_note"],
                "status": "pending",
                "created_at": seed["fixed_time"],
            }
        )
    expected_current.sort(key=lambda row: row["request_id"])
    check("requests_exact", current == expected_current, "请求对象、方向、舍入金额、备注和状态必须与独立复算结果完全一致")
    check("request_count", len(current) == len(expected_current), "每名非付款参与人恰有一条本轮请求")
    check("no_payer_or_unrelated_request", all(row["participant_id"] in shares and row["participant_id"] != payer_id for row in current), "不得请求付款人本人或无关联系人")
    check("request_idempotency", len({row["participant_id"] for row in current}) == len(current), "同一参与人不得重复请求")

    expected_success = [
        {
            "participant_id": row["participant_id"],
            "display_name": contacts_by_id[row["participant_id"]]["display_name"],
            "amount_fen": row["amount_fen"],
            "request_id": row["request_id"],
        }
        for row in expected_current
    ]
    expected_report = {
        "success": expected_success,
        "skipped": [{"participant_id": payer_id, "display_name": contacts_by_id[payer_id]["display_name"], "reason": "付款人本人"}],
        "missing": [],
    }
    report_ok = False
    if len(reports) == 1:
        try:
            report_ok = json.loads(reports[0]["content_json"]) == expected_report
        except (json.JSONDecodeError, TypeError):
            report_ok = False
        report_ok = report_ok and reports[0]["run_tag"] == seed["run_tag"] and reports[0]["created_at"] == seed["fixed_time"]
    check("status_report_exact", report_ok, "本轮回报必须准确列出成功、付款人跳过和缺失项")

    expected_audits = [
        {
            "audit_id": f"audit-create-{row['participant_id']}",
            "run_tag": seed["run_tag"],
            "action": "create_payment_request",
            "target_id": row["request_id"],
            "created_at": seed["fixed_time"],
        }
        for row in expected_current
    ] + [
        {
            "audit_id": "audit-report-case_17",
            "run_tag": seed["run_tag"],
            "action": "write_status_report",
            "target_id": "report-case_17-v1",
            "created_at": seed["fixed_time"],
        }
    ]
    expected_audits.sort(key=lambda row: row["audit_id"])
    check("allowed_actions_only", audits == expected_audits, "审计日志只允许三次创建付款请求和一次写回报")
    return finalize(checks)


def finalize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed_count = sum(1 for item in checks if item["passed"])
    return {
        "schema_version": "case17_verifier_result_v1",
        "task_id": "case_17",
        "passed": passed_count == len(checks),
        "checks": checks,
        "summary": {"passed": passed_count, "failed": len(checks) - passed_count, "total": len(checks)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.fixtures)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        result = finalize([{"check_id": "verifier_runtime", "passed": False, "detail": f"验证器运行失败：{type(exc).__name__}"}])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
