#!/usr/bin/env python3
"""Hidden deterministic final-state verifier for case_15."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_ROOT / "environment"))
from state_model import (  # noqa: E402
    canonical_state,
    connect,
    derive_eligible_products,
    load_json,
    populate_database,
    state_hash,
    unique_lowest_product,
)


def baseline_state(catalog: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    populate_database(connection, catalog, seed)
    result = canonical_state(connection)
    connection.close()
    return result


def check(check_id: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": bool(passed),
        "required": True,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--constraints", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        catalog = load_json(args.catalog)
        seed = load_json(args.seed)
        constraints = load_json(args.constraints)
        eligible = derive_eligible_products(catalog, constraints)
        target = unique_lowest_product(catalog, constraints)
        baseline = baseline_state(catalog, seed)
        with connect(args.db) as connection:
            actual = canonical_state(connection)
            final_hash = state_hash(connection)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        payload = {
            "schema_version": "nami_work_case15_verifier_result_v1",
            "verdict": "invalid",
            "score": 0,
            "checks": [check("state_readable", False, type(exc).__name__)],
            "final_state_sha256": "0" * 64,
        }
        if args.output:
            args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    target_user = constraints["target_user_id"]
    required_quantity = constraints["required_quantity"]
    target_items = [row for row in actual["cart_items"] if row["user_id"] == target_user]
    other_items = [row for row in actual["cart_items"] if row["user_id"] != target_user]
    baseline_other = [row for row in baseline["cart_items"] if row["user_id"] != target_user]
    expected_audit = [
        {
            "event_id": 1,
            "event_type": "cart_add",
            "user_id": target_user,
            "product_id": target["product_id"],
            "quantity": required_quantity,
            "event_time": "2026-07-20T08:00:00Z",
        }
    ]
    checks = [
        check("eligible_set_nonempty", bool(eligible), f"eligible_count={len(eligible)}"),
        check(
            "unique_lowest_target",
            sum(item["price_cents"] == target["price_cents"] for item in eligible) == 1,
            "lowest_price_is_unique",
        ),
        check(
            "target_cart_exact",
            target_items
            == [
                {
                    "user_id": target_user,
                    "product_id": target["product_id"],
                    "quantity": required_quantity,
                }
            ],
            f"target_item_count={len(target_items)}",
        ),
        check("products_unchanged", actual["products"] == baseline["products"], "table=products"),
        check("variants_unchanged", actual["variants"] == baseline["variants"], "table=variants"),
        check("users_unchanged", actual["users"] == baseline["users"], "table=users"),
        check("other_carts_unchanged", other_items == baseline_other, "scope=non_target_users"),
        check("orders_unchanged", actual["orders"] == baseline["orders"], "table=orders"),
        check("settings_unchanged", actual["settings"] == baseline["settings"], "table=settings"),
        check("audit_exact", actual["audit_log"] == expected_audit, f"audit_count={len(actual['audit_log'])}"),
    ]
    passed = all(item["passed"] for item in checks if item["required"])
    payload = {
        "schema_version": "nami_work_case15_verifier_result_v1",
        "verdict": "accept" if passed else "reject",
        "score": sum(item["passed"] for item in checks) / len(checks),
        "checks": checks,
        "final_state_sha256": final_hash,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
