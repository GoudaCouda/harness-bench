from __future__ import annotations

import csv
import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
HEADER = ["order_id", "join_status", "segment", "usd_amount", "reason"]
VALID_REASONS = {
    "null_customer_key",
    "unmatched_customer",
    "ambiguous_customer",
    "unmatched_rate",
    "ambiguous_rate",
}


def add(
    checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any = None
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": check_id.replace("_", " "),
            "pass": bool(passed),
            "weight": 1.0,
            "detail": detail,
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def seed_dataset() -> dict[str, list[dict[str, Any]]]:
    root = TASK / "workspace"
    orders = [
        {**row, "amount": float(row["amount"])} for row in read_csv(root / "orders.csv")
    ]
    customers = [
        {
            **row,
            "version": int(row["version"]),
            "current": row["current"].casefold() == "true",
        }
        for row in read_csv(root / "customers.csv")
    ]
    rates = [
        {
            **row,
            "usd_rate": float(row["usd_rate"]),
            "version": int(row["version"]),
            "current": row["current"].casefold() == "true",
        }
        for row in read_csv(root / "rates.csv")
    ]
    return {"orders": orders, "customers": customers, "rates": rates}


def heldout_dataset() -> dict[str, list[dict[str, Any]]]:
    return {
        "customers": [
            {"customer_id": "h1", "segment": "A", "version": 1, "current": True},
            {"customer_id": "h2", "segment": "B", "version": 1, "current": False},
            {"customer_id": "h2", "segment": "C", "version": 2, "current": True},
            {"customer_id": "h3", "segment": "A", "version": 1, "current": True},
            {"customer_id": "h3", "segment": "B", "version": 2, "current": True},
            {"customer_id": "h4", "segment": "Z", "version": 1, "current": False},
            {"customer_id": "h5", "segment": "D", "version": 1, "current": False},
            {"customer_id": "h5", "segment": "E", "version": 2, "current": False},
            {"customer_id": "h6", "segment": "F", "version": 1, "current": True},
        ],
        "rates": [
            {
                "currency": "USD",
                "date": "2026-08-01",
                "usd_rate": 1.0,
                "version": 1,
                "current": True,
            },
            {
                "currency": "EUR",
                "date": "2026-08-01",
                "usd_rate": 1.2,
                "version": 1,
                "current": False,
            },
            {
                "currency": "EUR",
                "date": "2026-08-01",
                "usd_rate": 1.25,
                "version": 2,
                "current": True,
            },
            {
                "currency": "GBP",
                "date": "2026-08-01",
                "usd_rate": 1.3,
                "version": 1,
                "current": True,
            },
            {
                "currency": "GBP",
                "date": "2026-08-01",
                "usd_rate": 1.31,
                "version": 2,
                "current": True,
            },
            {
                "currency": "EUR",
                "date": "2026-08-02",
                "usd_rate": 1.27,
                "version": 1,
                "current": False,
            },
        ],
        "orders": [
            {
                "order_id": "t1",
                "customer_id": "h1",
                "currency": "USD",
                "date": "2026-08-01",
                "amount": 10.0,
            },
            {
                "order_id": "t2",
                "customer_id": "h2",
                "currency": "EUR",
                "date": "2026-08-01",
                "amount": 20.0,
            },
            {
                "order_id": "t3",
                "customer_id": "h3",
                "currency": "USD",
                "date": "2026-08-01",
                "amount": 30.0,
            },
            {
                "order_id": "t4",
                "customer_id": "h4",
                "currency": "USD",
                "date": "2026-08-01",
                "amount": 40.0,
            },
            {
                "order_id": "t5",
                "customer_id": "h9",
                "currency": "USD",
                "date": "2026-08-01",
                "amount": 50.0,
            },
            {
                "order_id": "t6",
                "customer_id": "",
                "currency": "USD",
                "date": "2026-08-01",
                "amount": 60.0,
            },
            {
                "order_id": "t7",
                "customer_id": "h6",
                "currency": "GBP",
                "date": "2026-08-01",
                "amount": 70.0,
            },
            {
                "order_id": "t8",
                "customer_id": "h6",
                "currency": "JPY",
                "date": "2026-08-01",
                "amount": 80.0,
            },
            {
                "order_id": "t9",
                "customer_id": "h6",
                "currency": "USD",
                "date": "2026-08-01",
                "amount": -5.0,
            },
            {
                "order_id": "t10",
                "customer_id": "h6",
                "currency": "EUR",
                "date": "2026-08-02",
                "amount": 90.0,
            },
        ],
    }


def expected_rows(data: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    customers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in data["customers"]:
        if row["customer_id"]:
            customers[str(row["customer_id"])].append(row)
    for row in data["rates"]:
        rates[(str(row["currency"]), str(row["date"]))].append(row)
    result: dict[str, dict[str, Any]] = {}
    for order in data["orders"]:
        customer_id = str(order["customer_id"] or "")
        customer_rows = customers.get(customer_id, [])
        current_customers = [row for row in customer_rows if row["current"]]
        rate_rows = rates.get((str(order["currency"]), str(order["date"])), [])
        current_rates = [row for row in rate_rows if row["current"]]
        status = "rejected"
        segment = None
        amount = None
        if not customer_id:
            reason = "null_customer_key"
        elif not customer_rows:
            reason = "unmatched_customer"
        elif len(current_customers) != 1:
            reason = "ambiguous_customer"
        elif not rate_rows:
            segment = current_customers[0]["segment"]
            reason = "unmatched_rate"
        elif len(current_rates) != 1:
            segment = current_customers[0]["segment"]
            reason = "ambiguous_rate"
        else:
            status = "matched"
            segment = current_customers[0]["segment"]
            amount = round(
                float(order["amount"]) * float(current_rates[0]["usd_rate"]), 2
            )
            reason = ""
        result[str(order["order_id"])] = {
            "join_status": status,
            "segment": segment,
            "usd_amount": amount,
            "reason": reason,
        }
    return result


def execute_sql(
    sql: str, data: dict[str, list[dict[str, Any]]]
) -> tuple[list[str], list[dict[str, Any]]]:
    forbidden = re.compile(
        r"\b(?:attach|detach|pragma|vacuum|load_extension|insert|update|delete|alter)\b",
        re.I,
    )
    if forbidden.search(sql):
        raise ValueError("SQL contains a forbidden side-effect statement")
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE orders(order_id TEXT, customer_id TEXT, currency TEXT, date TEXT, amount REAL)"
    )
    db.execute(
        "CREATE TABLE customers(customer_id TEXT, segment TEXT, version INTEGER, current INTEGER)"
    )
    db.execute(
        "CREATE TABLE rates(currency TEXT, date TEXT, usd_rate REAL, version INTEGER, current INTEGER)"
    )
    for row in data["orders"]:
        db.execute(
            "INSERT INTO orders VALUES(?,?,?,?,?)",
            (
                row["order_id"],
                row["customer_id"],
                row["currency"],
                row["date"],
                row["amount"],
            ),
        )
    for row in data["customers"]:
        db.execute(
            "INSERT INTO customers VALUES(?,?,?,?)",
            (
                row["customer_id"],
                row["segment"],
                row["version"],
                int(bool(row["current"])),
            ),
        )
    for row in data["rates"]:
        db.execute(
            "INSERT INTO rates VALUES(?,?,?,?,?)",
            (
                row["currency"],
                row["date"],
                row["usd_rate"],
                row["version"],
                int(bool(row["current"])),
            ),
        )
    db.executescript(sql)
    cursor = db.execute("SELECT * FROM order_join")
    header = [item[0] for item in cursor.description or []]
    return header, [dict(zip(header, row)) for row in cursor.fetchall()]


def rows_match(
    actual: list[dict[str, Any]], expected: dict[str, dict[str, Any]]
) -> tuple[bool, dict[str, Any]]:
    ids = [str(row.get("order_id") or "") for row in actual]
    integrity = (
        len(actual) == len(expected)
        and len(ids) == len(set(ids))
        and set(ids) == set(expected)
    )
    failures: dict[str, Any] = {}
    by_id = {str(row.get("order_id") or ""): row for row in actual}
    for order_id, wanted in expected.items():
        row = by_id.get(order_id, {})
        status = str(row.get("join_status") or "").casefold()
        reason = str(row.get("reason") or "")
        segment = row.get("segment")
        amount = row.get("usd_amount")
        if wanted["join_status"] == "matched":
            segment_ok = str(segment or "") == str(wanted["segment"])
        elif wanted["reason"] in {"unmatched_rate", "ambiguous_rate"}:
            segment_ok = segment in (None, "") or str(segment) == str(wanted["segment"])
        else:
            segment_ok = segment in (None, "")
        if wanted["usd_amount"] is None:
            try:
                amount_ok = amount in (None, "") or math.isclose(
                    float(amount), 0.0, abs_tol=1e-9
                )
            except (TypeError, ValueError):
                amount_ok = False
        else:
            try:
                amount_ok = math.isclose(
                    float(amount), float(wanted["usd_amount"]), abs_tol=1e-6
                )
            except (TypeError, ValueError):
                amount_ok = False
        row_ok = (
            status == wanted["join_status"]
            and reason == wanted["reason"]
            and segment_ok
            and amount_ok
        )
        if not row_ok:
            failures[order_id] = {"actual": row, "expected": wanted}
    return integrity and not failures, {"integrity": integrity, "failures": failures}


def expected_audit(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matched = [row for row in rows.values() if row["join_status"] == "matched"]
    rejected = [row for row in rows.values() if row["join_status"] == "rejected"]
    return {
        "cardinality": {
            "orders_to_customers": "many_to_one",
            "orders_to_rates": "many_to_one",
        },
        "errors": [],
        "input_orders": len(rows),
        "matched_orders": len(matched),
        "matched_revenue_usd": round(
            sum(float(row["usd_amount"]) for row in matched), 2
        ),
        "output_rows": len(rows),
        "output_unique_orders": len(rows),
        "rejected_orders": len(rejected),
        "rejection_counts": dict(
            sorted(Counter(row["reason"] for row in rejected).items())
        ),
        "status": "pass",
    }


def audit_matches(actual: object, expected: dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    cardinality = actual.get("cardinality")
    if not isinstance(cardinality, dict):
        return False

    def normalized(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

    aliases = {
        normalized(key): normalized(value) for key, value in cardinality.items()
    }
    cardinality_ok = (
        aliases.get("orderstocustomers", aliases.get("orderscustomers"))
        in {"manytoone", "m1"}
        and aliases.get("orderstorates", aliases.get("ordersrates"))
        in {"manytoone", "m1"}
    )
    remaining = {key: value for key, value in actual.items() if key != "cardinality"}
    expected_remaining = {
        key: value for key, value in expected.items() if key != "cardinality"
    }
    return cardinality_ok and remaining == expected_remaining


def score_workspace(
    workspace: Path, *, ground_truth_path: Path | None = None
) -> dict[str, Any]:
    del ground_truth_path
    root = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []
    sql = ""
    try:
        sql = (root / "pipeline/revenue_join.sql").read_text(encoding="utf-8")
        seed_header, seed_rows = execute_sql(sql, seed_dataset())
        seed_ok, seed_detail = rows_match(seed_rows, expected_rows(seed_dataset()))
        seed_ok = seed_header == HEADER and seed_ok
        seed_detail["header"] = seed_header
    except Exception as exc:
        seed_ok = False
        seed_detail = {"error": f"{type(exc).__name__}: {exc}"}
    add(checks, "seed_pipeline", seed_ok, seed_detail)

    try:
        hidden_header, hidden_rows = execute_sql(sql, heldout_dataset())
        hidden_ok, hidden_detail = rows_match(
            hidden_rows, expected_rows(heldout_dataset())
        )
        hidden_ok = hidden_header == HEADER and hidden_ok
        hidden_detail["header"] = hidden_header
    except Exception as exc:
        hidden_ok = False
        hidden_detail = {"error": f"{type(exc).__name__}: {exc}"}
    add(checks, "heldout_pipeline", hidden_ok, hidden_detail)

    executable_ok = False
    executable_detail: dict[str, Any] = {}
    temp_root = Path(tempfile.mkdtemp(prefix="hb-088-runner-"))
    try:
        shutil.copytree(
            root,
            temp_root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(temp_root / "bin/run_close.py"),
                "--root",
                str(temp_root),
            ],
            cwd=temp_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        generated_audit = json.loads(
            (temp_root / "close/join_audit.json").read_text(encoding="utf-8")
        )
        candidate_audit = json.loads(
            (root / "close/join_audit.json").read_text(encoding="utf-8")
        )
        generated_csv = (temp_root / "close/order_join.csv").read_text(encoding="utf-8")
        candidate_rows = read_csv(root / "close/order_join.csv")
        candidate_rows_ok, candidate_rows_detail = rows_match(
            candidate_rows, expected_rows(seed_dataset())
        )
        expected_seed_audit = expected_audit(expected_rows(seed_dataset()))
        executable_ok = bool(
            completed.returncode == 0
            and generated_audit.get("status") == "pass"
            and generated_audit.get("errors") == []
            and audit_matches(candidate_audit, expected_seed_audit)
            and candidate_rows_ok
            and seed_ok
        )
        executable_detail = {
            "returncode": completed.returncode,
            "status": generated_audit.get("status"),
            "errors": generated_audit.get("errors"),
            "artifacts_current": audit_matches(candidate_audit, expected_seed_audit)
            and candidate_rows_ok,
            "candidate_rows": candidate_rows_detail,
            "generated_csv_bytes": len(generated_csv.encode("utf-8")),
        }
    except Exception as exc:
        executable_detail = {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    add(checks, "executable_close", executable_ok, executable_detail)

    try:
        audit = json.loads((root / "close/join_audit.json").read_text(encoding="utf-8"))
        candidate_rows = read_csv(root / "close/order_join.csv")
        candidate_rows_ok, candidate_rows_detail = rows_match(
            candidate_rows, expected_rows(seed_dataset())
        )
        audit_ok = audit_matches(audit, expected_audit(expected_rows(seed_dataset()))) and candidate_rows_ok
        audit_detail = {"actual": audit, "candidate_rows": candidate_rows_detail}
    except Exception as exc:
        audit_ok = False
        audit_detail = {"error": f"{type(exc).__name__}: {exc}"}
    add(checks, "close_audit", audit_ok, audit_detail)

    handoff_path = root / "close_handoff.md"
    handoff = (
        handoff_path.read_text(encoding="utf-8", errors="replace")
        if handoff_path.is_file()
        else ""
    )
    low = " ".join(re.sub(r"[_`*:/-]+", " ", handoff.casefold()).split())
    concepts = {
        "raw_join_failure": "raw" in low
        and any(term in low for term in ("multiply", "multiplied", "many to many")),
        "resolution": "current" in low
        and any(term in low for term in ("exactly one", "one usable"))
        and "group" in low,
        "reason_boundary": all(
            term in low for term in ("null", "unmatched", "ambiguous")
        ),
        "refund_tieout": "refund" in low and "585" in low and "revenue" in low,
        "validation": "run close" in low
        and any(
            term in low
            for term in (
                "exit",
                "pass",
                "validated",
                "validation succeeded",
                "successful",
            )
        ),
        "generalization": any(
            term in low for term in ("new key", "new customer", "new data", "new date")
        ),
    }
    add(
        checks,
        "maintainer_handoff",
        len(handoff.split()) >= 100 and all(concepts.values()),
        concepts,
    )

    return {
        "task": "088-cardinality-guarded-join",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
