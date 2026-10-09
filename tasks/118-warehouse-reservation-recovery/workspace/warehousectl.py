#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "warehouse.db"
CHECKPOINT = ROOT / "recovery_checkpoint.json"
SEED = ROOT / "warehouse_seed.sql"
STATE_TABLES = ("inventory", "orders", "reservations")
ALL_TABLES = (*STATE_TABLES, "recovery_transactions")
ALLOWED_EVIDENCE_FILES = {
    "warehouse.db",
    "recovery_policy.md",
    "shipment_receipts.json",
    "recovery_checkpoint.json",
}


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_checkpoint() -> dict[str, Any]:
    value = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("recovery checkpoint must be an object")
    return value


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def baseline_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SEED.read_text(encoding="utf-8"))
    return connection


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in ALL_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return [
        dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")
    ]


def operational_snapshot(
    connection: sqlite3.Connection,
) -> dict[str, list[dict[str, Any]]]:
    return {table: rows(connection, table) for table in STATE_TABLES}


def snapshot(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    return {table: rows(connection, table) for table in ALL_TABLES}


def status() -> int:
    checkpoint = load_checkpoint()
    with connect() as connection:
        state = operational_snapshot(connection)
        value = {
            "checkpoint": checkpoint,
            "current_state_sha256": canonical_digest(state),
            "state": snapshot(connection),
        }
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def query(sql: str) -> int:
    if not sql.lstrip().casefold().startswith("select"):
        print("query accepts SELECT only")
        return 2
    with connect() as connection:
        print(json.dumps([dict(row) for row in connection.execute(sql)], indent=2))
    return 0


def load_plan(name: str) -> dict[str, Any]:
    path = (ROOT / name).resolve()
    if path.parent != ROOT or not path.is_file():
        raise ValueError("plan must be a file in the workspace root")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    return value


def action_map(plan: dict[str, Any]) -> dict[str, str]:
    actions = plan.get("actions")
    if not isinstance(actions, list):
        return {}
    return {
        str(row.get("reservation_id")): str(row.get("action"))
        for row in actions
        if isinstance(row, dict)
    }


def semantic_plan(plan: dict[str, Any]) -> dict[str, Any]:
    actions = action_map(plan)
    return {
        "recovery_id": plan.get("recovery_id"),
        "source_state_sha256": plan.get("source_state_sha256"),
        "actions": [
            {"reservation_id": reservation_id, "action": actions[reservation_id]}
            for reservation_id in sorted(actions)
        ],
    }


def semantic_plan_digest(plan: dict[str, Any]) -> str:
    return canonical_digest(semantic_plan(plan))


def expected_actions(connection: sqlite3.Connection) -> dict[str, str]:
    checkpoint = load_checkpoint()
    receipts = json.loads((ROOT / "shipment_receipts.json").read_text())["receipts"]
    shipped = {
        row["reservation_id"] for row in receipts if row.get("verified") is True
    }
    reservations = rows(connection, "reservations")
    lowest: dict[str, tuple[int, str]] = {}
    for row in reservations:
        current = lowest.get(row["idempotency_key"])
        candidate = (row["sequence"], row["reservation_id"])
        if current is None or candidate < current:
            lowest[row["idempotency_key"]] = candidate
    expected = {}
    for row in reservations:
        key = row["reservation_id"]
        if key in shipped:
            expected[key] = "commit_shipped"
        elif lowest[row["idempotency_key"]][1] != key:
            expected[key] = "cancel_duplicate"
        elif row["expires_at"] < checkpoint["as_of"] and not row["pick_confirmed"]:
            expected[key] = "release_expired"
        else:
            expected[key] = "keep"
    return expected


def evidence_requirements(
    reservation_id: str, action: str
) -> list[set[str]]:
    database_refs = {
        f"warehouse.db#{reservation_id}",
        f"warehouse.db#reservation/{reservation_id}",
        f"warehouse.db#reservations/{reservation_id}",
    }
    if action == "commit_shipped":
        receipts = json.loads(
            (ROOT / "shipment_receipts.json").read_text(encoding="utf-8")
        ).get("receipts", [])
        authority_refs = {
            f"shipment_receipts.json#{row.get('receipt_id')}"
            for row in receipts
            if isinstance(row, dict)
            and str(row.get("reservation_id")) == reservation_id
            and row.get("verified") is True
        }
    elif action == "cancel_duplicate":
        authority_refs = {
            "recovery_policy.md#policy",
            "recovery_policy.md#duplicate-holds",
        }
    elif action == "keep":
        authority_refs = {
            "recovery_policy.md#policy",
            "recovery_policy.md#duplicate-holds",
            "recovery_policy.md#expired-holds",
        }
    else:
        authority_refs = {
            "recovery_policy.md#policy",
            "recovery_policy.md#expired-holds",
        }
    return [database_refs, authority_refs]


def missing_local_evidence(actions: object) -> dict[str, list[list[str]]]:
    if not isinstance(actions, list):
        return {"<plan>": [["actions must be a list"]]}
    missing: dict[str, list[list[str]]] = {}
    for index, row in enumerate(actions):
        key = f"<action:{index}>"
        if not isinstance(row, dict):
            missing[key] = [["action must be an object"]]
            continue
        reservation_id = str(row.get("reservation_id"))
        key = reservation_id or key
        evidence = row.get("evidence_ids")
        if not isinstance(evidence, list) or not evidence:
            missing[key] = [["evidence_ids must be a non-empty list"]]
            continue
        refs = {str(item) for item in evidence}
        invalid = sorted(
            ref
            for ref in refs
            if "#" not in ref
            or ref.startswith(("/", "../", "http://", "https://"))
            or ref.split("#", 1)[0] not in ALLOWED_EVIDENCE_FILES
        )
        groups = [
            sorted(group)
            for group in evidence_requirements(reservation_id, str(row.get("action")))
            if refs.isdisjoint(group)
        ]
        if invalid:
            groups.append([f"remove invalid locator: {ref}" for ref in invalid])
        if groups:
            missing[key] = groups
    return missing


def validate_plan(
    connection: sqlite3.Connection, plan: dict[str, Any]
) -> tuple[bool, dict[str, bool], dict[str, list[list[str]]]]:
    checkpoint = load_checkpoint()
    actions = plan.get("actions")
    actual = action_map(plan)
    expected = expected_actions(connection)
    missing_evidence = missing_local_evidence(actions)
    checks = {
        "schema": plan.get("schema_version") == 1 and isinstance(actions, list),
        "recovery_identity": plan.get("recovery_id") == checkpoint.get("recovery_id"),
        "source_checkpoint": plan.get("source_state_sha256")
        == checkpoint.get("source_state_sha256"),
        "one_action_per_reservation": isinstance(actions, list)
        and len(actual) == len(actions) == len(expected),
        "reservation_coverage": set(actual) == set(expected),
        "policy_actions": actual == expected,
        "local_evidence": not missing_evidence,
        "offline_boundary": plan.get("external_actions_executed") is False,
    }
    return all(checks.values()), checks, missing_evidence


def apply_actions(connection: sqlite3.Connection, plan: dict[str, Any]) -> None:
    for action in plan["actions"]:
        reservation = connection.execute(
            "SELECT * FROM reservations WHERE reservation_id=?",
            (action["reservation_id"],),
        ).fetchone()
        kind = action["action"]
        if kind == "keep":
            continue
        if kind in {"cancel_duplicate", "release_expired"}:
            status_value = (
                "cancelled_duplicate"
                if kind == "cancel_duplicate"
                else "released_expired"
            )
            connection.execute(
                "UPDATE reservations SET status=? WHERE reservation_id=?",
                (status_value, reservation["reservation_id"]),
            )
            connection.execute(
                "UPDATE inventory SET reserved=reserved-?, available=available+? WHERE sku=?",
                (reservation["quantity"], reservation["quantity"], reservation["sku"]),
            )
            if kind == "release_expired":
                connection.execute(
                    "UPDATE orders SET status='released' WHERE order_id=?",
                    (reservation["order_id"],),
                )
        elif kind == "commit_shipped":
            connection.execute(
                "UPDATE reservations SET status='shipped' WHERE reservation_id=?",
                (reservation["reservation_id"],),
            )
            connection.execute(
                "UPDATE inventory SET reserved=reserved-?, shipped=shipped+? WHERE sku=?",
                (reservation["quantity"], reservation["quantity"], reservation["sku"]),
            )
            connection.execute(
                "UPDATE orders SET status='shipped' WHERE order_id=?",
                (reservation["order_id"],),
            )


def inventory_is_safe(connection: sqlite3.Connection) -> bool:
    return all(
        min(row["available"], row["reserved"], row["shipped"]) >= 0
        and row["available"] + row["reserved"] + row["shipped"] == row["on_hand"]
        for row in rows(connection, "inventory")
    )


def prior_transaction(
    connection: sqlite3.Connection, recovery_id: object
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM recovery_transactions WHERE recovery_id=?", (recovery_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def replay_result(
    connection: sqlite3.Connection, plan: dict[str, Any], checks: dict[str, bool]
) -> tuple[str, dict[str, Any]] | None:
    checkpoint = load_checkpoint()
    prior = prior_transaction(connection, checkpoint.get("recovery_id"))
    if prior is None:
        return None
    structural = all(
        checks[name]
        for name in (
            "schema",
            "recovery_identity",
            "source_checkpoint",
            "one_action_per_reservation",
            "reservation_coverage",
            "local_evidence",
            "offline_boundary",
        )
    )
    semantic_sha = semantic_plan_digest(plan)
    if structural and semantic_sha == prior["semantic_plan_sha256"]:
        return "idempotent", {
            "status": "idempotent",
            "recovery_id": prior["recovery_id"],
            "semantic_plan_sha256": semantic_sha,
        }
    return "conflict", {
        "status": "rejected",
        "reason": "semantic_plan_conflict",
        "recovery_id": checkpoint.get("recovery_id"),
        "committed_semantic_plan_sha256": prior["semantic_plan_sha256"],
        "submitted_semantic_plan_sha256": semantic_sha,
        "checks": checks,
    }


def preview(name: str) -> int:
    plan = load_plan(name)
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        valid, checks, missing_evidence = validate_plan(connection, plan)
        replay = replay_result(connection, plan, checks)
        if replay is not None:
            kind, result = replay
            result["projected"] = snapshot(connection) if kind == "idempotent" else None
            connection.rollback()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if kind == "idempotent" else 2
        checkpoint = load_checkpoint()
        current_sha = canonical_digest(operational_snapshot(connection))
        with baseline_connection() as baseline:
            baseline_sha = canonical_digest(operational_snapshot(baseline))
        checks["initial_state_matches_checkpoint"] = (
            current_sha == checkpoint.get("source_state_sha256")
        )
        checks["protected_baseline_matches_checkpoint"] = (
            baseline_sha == checkpoint.get("source_state_sha256")
        )
        if valid and all(
            checks[name]
            for name in (
                "initial_state_matches_checkpoint",
                "protected_baseline_matches_checkpoint",
            )
        ):
            apply_actions(connection, plan)
            checks["projected_inventory_safe"] = inventory_is_safe(connection)
        result = {
            "status": "pass" if all(checks.values()) else "fail",
            "recovery_id": plan.get("recovery_id"),
            "semantic_plan_sha256": semantic_plan_digest(plan),
            "checks": checks,
            "projected": snapshot(connection) if all(checks.values()) else None,
        }
        if missing_evidence:
            result["missing_evidence_by_reservation"] = missing_evidence
        connection.rollback()
    finally:
        connection.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def apply(name: str) -> int:
    plan = load_plan(name)
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        valid, checks, missing_evidence = validate_plan(connection, plan)
        replay = replay_result(connection, plan, checks)
        if replay is not None:
            kind, result = replay
            connection.rollback()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if kind == "idempotent" else 2
        checkpoint = load_checkpoint()
        current_sha = canonical_digest(operational_snapshot(connection))
        with baseline_connection() as baseline:
            baseline_sha = canonical_digest(operational_snapshot(baseline))
        checks["initial_state_matches_checkpoint"] = (
            current_sha == checkpoint.get("source_state_sha256")
        )
        checks["protected_baseline_matches_checkpoint"] = (
            baseline_sha == checkpoint.get("source_state_sha256")
        )
        if not valid or not all(
            checks[name]
            for name in (
                "initial_state_matches_checkpoint",
                "protected_baseline_matches_checkpoint",
            )
        ):
            connection.rollback()
            result: dict[str, Any] = {"status": "rejected", "checks": checks}
            if missing_evidence:
                result["missing_evidence_by_reservation"] = missing_evidence
            print(json.dumps(result, indent=2, sort_keys=True))
            return 2
        apply_actions(connection, plan)
        checks["inventory_safe"] = inventory_is_safe(connection)
        if not checks["inventory_safe"]:
            connection.rollback()
            print(json.dumps({"status": "rejected", "checks": checks}, indent=2))
            return 2
        semantic_sha = semantic_plan_digest(plan)
        connection.execute(
            "INSERT INTO recovery_transactions VALUES (?, ?, ?, ?, ?)",
            (
                checkpoint["recovery_id"],
                checkpoint["source_state_sha256"],
                semantic_sha,
                checkpoint["as_of"],
                len(plan["actions"]),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    print(
        json.dumps(
            {
                "status": "applied",
                "recovery_id": checkpoint["recovery_id"],
                "semantic_plan_sha256": semantic_sha,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def verify() -> int:
    checkpoint = load_checkpoint()
    with connect() as connection:
        snap = snapshot(connection)
        inventory = rows(connection, "inventory")
        current_operational_state = operational_snapshot(connection)
        transactions = rows(connection, "recovery_transactions")
        transaction = transactions[0] if len(transactions) == 1 else {}
        try:
            plan = load_plan("recovery_plan.json")
            plan_binding = semantic_plan_digest(plan) == transaction.get(
                "semantic_plan_sha256"
            )
            with baseline_connection() as baseline:
                baseline_sha = canonical_digest(operational_snapshot(baseline))
                baseline_plan_valid, _, _ = validate_plan(baseline, plan)
                if baseline_plan_valid:
                    apply_actions(baseline, plan)
                    projected_state = operational_snapshot(baseline)
                else:
                    projected_state = {}
        except (OSError, ValueError, json.JSONDecodeError):
            plan_binding = False
            baseline_plan_valid = False
            baseline_sha = ""
            projected_state = {}
        checks = {
            "baseline_plan_valid": baseline_plan_valid,
            "terminal_state_matches_projection": current_operational_state
            == projected_state,
            "protected_baseline_matches_checkpoint": baseline_sha
            == checkpoint.get("source_state_sha256"),
            "inventory_closes": all(
                row["available"] + row["reserved"] + row["shipped"]
                == row["on_hand"]
                for row in inventory
            ),
            "inventory_nonnegative": all(
                min(row["available"], row["reserved"], row["shipped"]) >= 0
                for row in inventory
            ),
            "single_recovery_transaction": len(transactions) == 1,
            "recovery_identity": transaction.get("recovery_id")
            == checkpoint.get("recovery_id"),
            "source_checkpoint_bound": transaction.get("source_state_sha256")
            == checkpoint.get("source_state_sha256"),
            "semantic_plan_bound": plan_binding,
        }
        receipt = {
            "tool": "warehousectl/2",
            "status": "pass" if all(checks.values()) else "fail",
            "recovery_id": checkpoint.get("recovery_id"),
            "source_state_sha256": checkpoint.get("source_state_sha256"),
            "semantic_plan_sha256": transaction.get("semantic_plan_sha256"),
            "logical_state_sha256": canonical_digest(snap),
            "checks": checks,
        }
    (ROOT / "recovery_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("sql")
    for name in ("preview", "apply"):
        child = sub.add_parser(name)
        child.add_argument("plan")
    sub.add_parser("verify")
    args = parser.parse_args()
    commands = {
        "status": status,
        "query": lambda: query(args.sql),
        "preview": lambda: preview(args.plan),
        "apply": lambda: apply(args.plan),
        "verify": verify,
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
