#!/usr/bin/env python3
"""从不可变合成 fixture 创建 case_17 的独立工作区。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_state(workspace: Path) -> dict[str, Any]:
    database = workspace / "state.sqlite"
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        tables = {}
        for table, order_by in (
            ("contacts", "participant_id"),
            ("existing_transactions", "transaction_id"),
            ("payment_requests", "request_id"),
            ("transfers", "transfer_id"),
            ("status_reports", "report_id"),
            ("audit_log", "audit_id"),
        ):
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
            tables[table] = [dict(row) for row in rows]
    return {
        "expense_ledger": load_json(workspace / "expense_ledger.json"),
        "seed_contacts": load_json(workspace / "contacts.json"),
        "workspace_metadata": load_json(workspace / "workspace_metadata.json"),
        "database": tables,
    }


def state_sha256(workspace: Path) -> str:
    return hashlib.sha256(canonical_bytes(normalized_state(workspace))).hexdigest()


def initialize_database(path: Path, seed: dict[str, Any]) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE contacts (
              participant_id TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              account_id TEXT NOT NULL UNIQUE,
              active INTEGER NOT NULL CHECK(active IN (0, 1))
            );
            CREATE TABLE existing_transactions (
              transaction_id TEXT PRIMARY KEY,
              occurred_at TEXT NOT NULL,
              kind TEXT NOT NULL,
              amount_fen INTEGER NOT NULL,
              memo TEXT NOT NULL
            );
            CREATE TABLE payment_requests (
              request_id TEXT PRIMARY KEY,
              run_tag TEXT NOT NULL,
              expense_id TEXT NOT NULL,
              participant_id TEXT NOT NULL,
              requester_id TEXT NOT NULL,
              recipient_account_id TEXT NOT NULL,
              direction TEXT NOT NULL,
              amount_fen INTEGER NOT NULL CHECK(amount_fen > 0),
              currency TEXT NOT NULL,
              note TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX one_request_per_participant_per_run
              ON payment_requests(run_tag, participant_id);
            CREATE TABLE transfers (
              transfer_id TEXT PRIMARY KEY,
              occurred_at TEXT NOT NULL,
              sender_id TEXT NOT NULL,
              recipient_account_id TEXT NOT NULL,
              amount_fen INTEGER NOT NULL,
              memo TEXT NOT NULL
            );
            CREATE TABLE status_reports (
              report_id TEXT PRIMARY KEY,
              run_tag TEXT NOT NULL UNIQUE,
              content_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE audit_log (
              audit_id TEXT PRIMARY KEY,
              run_tag TEXT NOT NULL,
              action TEXT NOT NULL,
              target_id TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO contacts VALUES (:participant_id, :display_name, :account_id, :active)",
            [{**row, "active": int(row["active"])} for row in seed["contacts"]],
        )
        connection.executemany(
            "INSERT INTO existing_transactions VALUES (:transaction_id, :occurred_at, :kind, :amount_fen, :memo)",
            seed["existing_transactions"],
        )
        connection.executemany(
            """INSERT INTO payment_requests VALUES
            (:request_id, :run_tag, :expense_id, :participant_id, :requester_id,
             :recipient_account_id, :direction, :amount_fen, :currency, :note, :status, :created_at)""",
            seed["payment_requests"],
        )
        connection.executemany(
            "INSERT INTO transfers VALUES (:transfer_id, :occurred_at, :sender_id, :recipient_account_id, :amount_fen, :memo)",
            seed["transfers"],
        )
        connection.execute("PRAGMA user_version = 1")


def reset(fixtures: Path, workspace: Path) -> str:
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError("workspace must be absent or empty")
    workspace.mkdir(parents=True, exist_ok=True)
    expense = fixtures / "expense_ledger.json"
    seed_path = fixtures / "seed_state.json"
    seed = load_json(seed_path)
    shutil.copyfile(expense, workspace / "expense_ledger.json")
    contacts_payload = {
        "schema_version": "case17_contacts_v1",
        "contacts": seed["contacts"],
    }
    (workspace / "contacts.json").write_text(
        json.dumps(contacts_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    initialize_database(workspace / "state.sqlite", seed)
    metadata = {
        "schema_version": "case17_workspace_metadata_v1",
        "fixed_time": seed["fixed_time"],
        "run_tag": seed["run_tag"],
        "source_files": ["expense_ledger.json", "contacts.json"],
    }
    (workspace / "workspace_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return state_sha256(workspace)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    digest = reset(args.fixtures, args.workspace)
    print(json.dumps({"status": "reset", "initial_state_sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
