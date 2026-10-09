#!/usr/bin/env python3
"""case_17 的隐藏参考求解器；仅用于证明环境可解。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def load_tools(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("case17_tools", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tools")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        allocation = split_amount(item["amount_fen"], item["participant_ids"])
        for participant_id, amount_fen in allocation.items():
            shares[participant_id] = shares.get(participant_id, 0) + amount_fen
    return dict(sorted(shares.items()))


def solve(workspace: Path, tools_path: Path) -> dict[str, Any]:
    tools = load_tools(tools_path)
    expense = tools.read_expense(workspace)
    contacts = {row["participant_id"]: row for row in tools.list_contacts(workspace)}
    shares = calculate_shares(expense)
    payer_id = expense["payer"]["participant_id"]
    successes = []
    for participant_id, amount_fen in shares.items():
        if participant_id == payer_id:
            continue
        contact = contacts.get(participant_id)
        if contact is None or not contact["active"]:
            continue
        arguments = argparse.Namespace(
            workspace=workspace,
            participant_id=participant_id,
            recipient_account_id=contact["account_id"],
            amount_fen=amount_fen,
            note=expense["request_note"],
        )
        first = tools.create_request(arguments)
        second = tools.create_request(arguments)
        if second["status"] != "already_exists":
            raise RuntimeError("payment request is not idempotent")
        successes.append(
            {
                "participant_id": participant_id,
                "display_name": contact["display_name"],
                "amount_fen": amount_fen,
                "request_id": first["request_id"],
            }
        )
    missing_ids = sorted(set(shares) - set(contacts) - {payer_id})
    report = {
        "success": successes,
        "skipped": [
            {
                "participant_id": payer_id,
                "display_name": contacts[payer_id]["display_name"],
                "reason": "付款人本人",
            }
        ],
        "missing": [{"participant_id": value, "reason": "联系人缺失"} for value in missing_ids],
    }
    report_args = argparse.Namespace(
        workspace=workspace,
        content_json=json.dumps(report, ensure_ascii=False, sort_keys=True),
    )
    first_report = tools.write_report(report_args)
    second_report = tools.write_report(report_args)
    if second_report["status"] != "already_exists":
        raise RuntimeError("status report is not idempotent")
    return {
        "status": "solved",
        "shares": shares,
        "created_request_ids": [item["request_id"] for item in successes],
        "report_id": first_report["report_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(solve(args.workspace, args.tools), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
