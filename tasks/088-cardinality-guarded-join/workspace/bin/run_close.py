#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


LEDGER_HEADER = ["order_id", "join_status", "segment", "usd_amount", "reason"]
REASONS = {
    "null_customer_key",
    "unmatched_customer",
    "ambiguous_customer",
    "unmatched_rate",
    "ambiguous_rate",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_db(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE orders(order_id TEXT, customer_id TEXT, currency TEXT, date TEXT, amount REAL)")
    db.execute("CREATE TABLE customers(customer_id TEXT, segment TEXT, version INTEGER, current INTEGER)")
    db.execute("CREATE TABLE rates(currency TEXT, date TEXT, usd_rate REAL, version INTEGER, current INTEGER)")
    for row in read_csv(root / "orders.csv"):
        db.execute("INSERT INTO orders VALUES(?,?,?,?,?)", (
            row["order_id"], row["customer_id"], row["currency"], row["date"], float(row["amount"]),
        ))
    for row in read_csv(root / "customers.csv"):
        db.execute("INSERT INTO customers VALUES(?,?,?,?)", (
            row["customer_id"], row["segment"], int(row["version"]), int(row["current"].casefold() == "true"),
        ))
    for row in read_csv(root / "rates.csv"):
        db.execute("INSERT INTO rates VALUES(?,?,?,?,?)", (
            row["currency"], row["date"], float(row["usd_rate"]), int(row["version"]), int(row["current"].casefold() == "true"),
        ))
    return db


def write_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in LEDGER_HEADER})


def validate(rows: list[dict[str, Any]], input_orders: list[dict[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    input_ids = [row["order_id"] for row in input_orders]
    output_ids = [str(row.get("order_id") or "") for row in rows]
    if len(rows) != len(input_ids) or Counter(output_ids) != Counter(input_ids):
        errors.append("output must contain exactly one row per input order")
    statuses = [str(row.get("join_status") or "").casefold() for row in rows]
    if any(value not in {"matched", "rejected"} for value in statuses):
        errors.append("join_status must be matched or rejected")
    rejection_counts = Counter()
    revenue = 0.0
    for row, status in zip(rows, statuses):
        reason = str(row.get("reason") or "")
        amount = row.get("usd_amount")
        if status == "matched":
            if reason:
                errors.append(f"matched order {row.get('order_id')} has a rejection reason")
            try:
                revenue += float(amount)
            except (TypeError, ValueError):
                errors.append(f"matched order {row.get('order_id')} has no numeric usd_amount")
        elif status == "rejected":
            if reason not in REASONS:
                errors.append(f"rejected order {row.get('order_id')} has invalid reason {reason!r}")
            else:
                rejection_counts[reason] += 1
            if amount not in (None, "", 0, 0.0):
                errors.append(f"rejected order {row.get('order_id')} contributes revenue")
    return {
        "status": "pass" if not errors else "fail",
        "input_orders": len(input_ids),
        "output_rows": len(rows),
        "output_unique_orders": len(set(output_ids)),
        "matched_orders": statuses.count("matched"),
        "rejected_orders": statuses.count("rejected"),
        "matched_revenue_usd": round(revenue, 2),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "cardinality": {
            "orders_to_customers": "many_to_one",
            "orders_to_rates": "many_to_one",
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    sql_path = root / "pipeline/revenue_join.sql"
    db = build_db(root)
    try:
        db.executescript(sql_path.read_text(encoding="utf-8"))
        cursor = db.execute("SELECT * FROM order_join ORDER BY order_id")
        header = [column[0] for column in cursor.description or []]
        raw_rows = cursor.fetchall()
        if header != LEDGER_HEADER:
            raise ValueError(f"order_join columns must be {LEDGER_HEADER}, got {header}")
        rows = [dict(zip(header, row)) for row in raw_rows]
        audit = validate(rows, read_csv(root / "orders.csv"))
    except Exception as exc:
        rows = []
        audit = {
            "status": "fail",
            "input_orders": len(read_csv(root / "orders.csv")),
            "output_rows": 0,
            "output_unique_orders": 0,
            "matched_orders": 0,
            "rejected_orders": 0,
            "matched_revenue_usd": 0.0,
            "rejection_counts": {},
            "cardinality": {
                "orders_to_customers": "many_to_one",
                "orders_to_rates": "many_to_one",
            },
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    write_ledger(root / "close/order_join.csv", rows)
    audit_path = root / "close/join_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
