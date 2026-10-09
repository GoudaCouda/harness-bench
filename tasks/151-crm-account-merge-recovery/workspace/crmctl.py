#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "crm.db"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def load_plan(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def merge_context(connection: sqlite3.Connection) -> dict:
    accounts = [dict(row) for row in connection.execute("SELECT * FROM accounts ORDER BY id")]
    groups: dict[str, list[dict]] = {}
    for account in accounts:
        groups.setdefault(str(account.get("domain", "")).casefold(), []).append(account)
    merge_group = next(
        group
        for group in groups.values()
        if {row.get("status") for row in group} >= {"active", "duplicate"}
    )
    survivor = next(row for row in merge_group if row.get("status") == "active")
    duplicate = next(row for row in merge_group if row.get("status") == "duplicate")
    preserve = [row["id"] for row in accounts if row not in merge_group]
    tables = ["contacts", "opportunities", "activities"]
    moves = {
        table: connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE account_id=?", (duplicate["id"],)
        ).fetchone()[0]
        for table in tables
    }
    return {
        "survivor": survivor,
        "duplicate": duplicate,
        "preserve": preserve,
        "tables": tables,
        "moves": moves,
    }


def plan_checks(plan: dict) -> dict[str, bool]:
    with connect() as connection:
        context = merge_context(connection)
    survivor = context["survivor"]
    duplicate = context["duplicate"]
    return {
        "survivor": plan.get("primary_account") == survivor["id"]
        and plan.get("duplicate_account") == duplicate["id"],
        "near_match": plan.get("preserve_accounts") == context["preserve"],
        "fields": plan.get("field_decisions")
        == {"name": survivor["name"], "domain": survivor["domain"]},
        "consent": plan.get("consent_resolution") == "most_restrictive_opt_out",
        "dependencies": plan.get("move") == context["tables"],
    }


def candidates() -> int:
    with connect() as connection:
        context = merge_context(connection)
    print(
        json.dumps(
            {
                "exact_domain_group": [
                    context["survivor"]["id"],
                    context["duplicate"]["id"],
                ],
                "review_only_near_match": context["preserve"],
            },
            indent=2,
        )
    )
    return 0


def query(sql: str) -> int:
    if not sql.lstrip().casefold().startswith("select"):
        return 2
    with connect() as connection:
        print(json.dumps([dict(row) for row in connection.execute(sql)], indent=2))
    return 0


def preview(name: str) -> int:
    result = plan_checks(load_plan(name))
    with connect() as connection:
        projected = merge_context(connection)["moves"]
    print(json.dumps({"status": "pass" if all(result.values()) else "fail", "checks": result, "projected_moves": projected}, indent=2))
    return 0 if all(result.values()) else 2


def merge(name: str) -> int:
    plan = load_plan(name)
    plan_sha = digest(plan)
    with connect() as connection:
        if connection.execute("SELECT 1 FROM merge_log WHERE plan_sha256=?", (plan_sha,)).fetchone():
            print(json.dumps({"status": "idempotent", "plan_sha256": plan_sha}, indent=2))
            return 0
        result = plan_checks(plan)
        if not all(result.values()):
            print(json.dumps({"status": "rejected", "checks": result}, indent=2))
            return 2
        context = merge_context(connection)
        survivor = context["survivor"]["id"]
        duplicate = context["duplicate"]["id"]
        for table in context["tables"]:
            connection.execute(
                f"UPDATE {table} SET account_id=? WHERE account_id=?",
                (survivor, duplicate),
            )
        opted_out = connection.execute(
            "SELECT MAX(email_opt_out) FROM contacts WHERE account_id=?",
            (survivor,),
        ).fetchone()[0]
        connection.execute(
            "UPDATE contacts SET email_opt_out=? WHERE account_id=?",
            (opted_out, survivor),
        )
        connection.execute(
            "UPDATE accounts SET status=? WHERE id=?",
            (f"merged_into:{survivor}", duplicate),
        )
        connection.execute(
            "INSERT INTO merge_log VALUES (?,?,?,?)",
            (plan_sha, survivor, duplicate, sum(context["moves"].values())),
        )
        connection.commit()
    print(json.dumps({"status": "merged", "plan_sha256": plan_sha}, indent=2))
    return 0


def snapshot(connection: sqlite3.Connection) -> dict:
    return {
        table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
        for table in ("accounts", "contacts", "opportunities", "activities", "merge_log")
    }


def verify() -> int:
    with connect() as connection:
        snap = snapshot(connection)
    accounts = {row["id"]: row["status"] for row in snap["accounts"]}
    log = snap["merge_log"]
    survivor = log[0]["primary_id"] if len(log) == 1 else ""
    duplicate = log[0]["duplicate_id"] if len(log) == 1 else ""
    preserved = {
        key for key, status in accounts.items() if key != survivor and status == "active"
    }
    values = {
        "survivor_and_tombstone": bool(survivor)
        and accounts.get(survivor) == "active"
        and accounts.get(duplicate) == f"merged_into:{survivor}",
        "dependencies": all(
            not any(row["account_id"] == duplicate for row in snap[table])
            for table in ("contacts", "opportunities", "activities")
        ),
        "consent": all(
            row["email_opt_out"] == 1
            for row in snap["contacts"]
            if row["account_id"] == survivor
        ),
        "near_match": all(
            all(any(row["account_id"] == account for row in snap[table]) for account in preserved)
            for table in ("contacts", "opportunities", "activities")
        ),
        "single_transaction": len(log) == 1,
    }
    receipt = {"tool": "crmctl/1", "status": "pass" if all(values.values()) else "fail", "checks": values, "logical_state_sha256": digest(snap)}
    (ROOT / "merge_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("candidates")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("sql")
    for command in ("preview", "merge"):
        child = sub.add_parser(command)
        child.add_argument("plan")
    sub.add_parser("verify")
    args = parser.parse_args()
    return {"candidates": candidates, "query": lambda: query(args.sql), "preview": lambda: preview(args.plan), "merge": lambda: merge(args.plan), "verify": verify}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
