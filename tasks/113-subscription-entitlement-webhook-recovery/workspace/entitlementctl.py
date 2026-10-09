#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/billing.db"
DECISION_FIELDS = {
    "subscription_id", "invoice_id", "source_high_watermark",
    "subscription_status", "invoice_status", "paid_cents", "refunded_cents",
    "dispute_status", "entitlement_state", "plan_code", "seats", "event_ids",
    "bridged_event_ids", "duplicate_event_ids", "next_local_action", "external_action",
}
PLAN_FIELDS = {
    "schema_version", "run_id", "snapshot_id", "decisions",
    "quarantined_event_ids", "external_actions_executed",
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain one JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_bundle() -> tuple[dict[str, Any], str]:
    manifest = read_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source manifest is malformed")
    changed = []
    for name, expected_hash in files.items():
        path = ROOT / str(name)
        try:
            actual = digest(path.read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected_hash:
            changed.append(str(name))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def verified_snapshot() -> dict[str, Any]:
    trust = read_json(ROOT / "evidence/provider_trust.json")
    snapshot = read_json(ROOT / "evidence/provider_snapshot.json")
    signature = str(snapshot.pop("signature", ""))
    key_id = str(snapshot.pop("key_id", ""))
    if key_id != trust.get("key_id"):
        raise ValueError("provider snapshot key_id is not trusted")
    actual = digest(canonical(snapshot) + str(trust.get("verification_material", "")).encode())
    if signature != actual:
        raise ValueError("provider snapshot signature verification failed")
    snapshot["signature"] = signature
    snapshot["key_id"] = key_id
    return snapshot


def spool() -> list[dict[str, Any]]:
    rows = []
    try:
        lines = (ROOT / "evidence/webhook_spool.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read webhook spool: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed webhook line {line_number}: {exc}") from exc
        required = {"event_id", "subscription_id", "invoice_id", "provider_sequence", "type", "occurred_at", "data"}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"webhook line {line_number} has the wrong schema")
        rows.append(row)
    return rows


def row_dict(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {description[0]: value for description, value in zip(cursor.description, row, strict=True)}


def table_rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    return [row_dict(cursor, row) for row in cursor.fetchall()]


def baseline_rows(connection: sqlite3.Connection) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    tables = {}
    for table, key in (("subscriptions", "subscription_id"), ("invoices", "invoice_id"), ("entitlements", "subscription_id")):
        values = {row[key]: row for row in table_rows(connection, table, key)}
        for rollback in table_rows(connection, "rollback_rows", "run_id, table_name, record_key"):
            if rollback["table_name"] == table and not rollback["restored"]:
                values[rollback["record_key"]] = json.loads(rollback["before_json"])
        tables[table] = values
    return tables["subscriptions"], tables["invoices"], tables["entitlements"]


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def recovery_inputs() -> dict[str, Any]:
    """Load verified source material, never a candidate answer or final state."""
    policy = read_json(ROOT / "policy/recovery_policy.json")
    snapshot = verified_snapshot()
    deliveries = spool()
    with sqlite3.connect(DB) as connection:
        subscriptions, invoices, entitlements = baseline_rows(connection)
    known = set(subscriptions)
    counts = Counter(str(row["event_id"]) for row in deliveries)
    distinct: dict[str, dict[str, Any]] = {}
    for row in deliveries:
        event_id = str(row["event_id"])
        if event_id in distinct and canonical(distinct[event_id]) != canonical(row):
            raise ValueError(f"duplicate event {event_id} has conflicting payloads")
        distinct[event_id] = row
    quarantine = sorted(event_id for event_id, row in distinct.items() if row["subscription_id"] not in known)
    histories: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for event_id, row in distinct.items():
        if row["subscription_id"] in known:
            histories[str(row["subscription_id"])].append((row, "webhook_spool"))
    bridges = {str(row["event_id"]): row for row in snapshot.get("bridge_events", []) if isinstance(row, dict)}
    return {
        "policy": policy,
        "snapshot": snapshot,
        "subscriptions": subscriptions,
        "invoices": invoices,
        "entitlements": entitlements,
        "counts": counts,
        "distinct": distinct,
        "histories": histories,
        "bridges": bridges,
        "quarantined_event_ids": quarantine,
    }


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    decisions = []
    for raw in plan.get("decisions", []):
        row = dict(raw)
        for key in ("event_ids", "bridged_event_ids", "duplicate_event_ids"):
            if isinstance(row.get(key), list):
                row[key] = sorted(row[key])
        decisions.append(row)
    result["decisions"] = sorted(decisions, key=lambda row: str(row.get("subscription_id")))
    if isinstance(result.get("quarantined_event_ids"), list):
        result["quarantined_event_ids"] = sorted(result["quarantined_event_ids"])
    return result


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = normalized_plan(read_json(path))
    inputs = recovery_inputs()
    policy = inputs["policy"]
    snapshot = inputs["snapshot"]
    subscriptions = inputs["subscriptions"]
    invoices = inputs["invoices"]
    entitlements = inputs["entitlements"]
    counts = inputs["counts"]
    histories = inputs["histories"]
    bridges = inputs["bridges"]
    problems: list[str] = []
    if set(candidate) != PLAN_FIELDS:
        problems.append(f"top-level fields must be exactly {sorted(PLAN_FIELDS)}")
    if candidate.get("schema_version") != 1 or candidate.get("run_id") != policy["run_id"]:
        problems.append("schema_version or run_id does not match policy")
    if candidate.get("snapshot_id") != snapshot["snapshot_id"]:
        problems.append("snapshot_id does not match the verified provider snapshot")
    if candidate.get("external_actions_executed") is not False:
        problems.append("external_actions_executed must be false")
    rows = candidate.get("decisions")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != DECISION_FIELDS for row in rows):
        problems.append(f"every decision must have exactly {sorted(DECISION_FIELDS)}")
        rows = []
    by_id = {str(row.get("subscription_id")): row for row in rows if isinstance(row, dict)}
    if set(by_id) != set(subscriptions):
        problems.append("decisions must cover every known subscription exactly once")
    if candidate.get("quarantined_event_ids") != inputs["quarantined_event_ids"]:
        problems.append("quarantined_event_ids differs at the unknown-subscription evidence dimension")
    event_records = []
    for subscription_id in sorted(subscriptions):
        high = int(snapshot["known_subscription_high_watermarks"][subscription_id])
        by_sequence = {int(row["provider_sequence"]): (row, source) for row, source in histories[subscription_id]}
        bridged = []
        for sequence in range(1, high + 1):
            if sequence in by_sequence:
                continue
            matches = [row for row in bridges.values() if row.get("subscription_id") == subscription_id and row.get("provider_sequence") == sequence]
            if len(matches) != 1:
                raise ValueError(f"subscription {subscription_id} sequence {sequence} lacks one signed snapshot bridge")
            by_sequence[sequence] = (matches[0], "provider_snapshot")
            bridged.append(str(matches[0]["event_id"]))
        if set(by_sequence) != set(range(1, high + 1)):
            raise ValueError(f"subscription {subscription_id} has event(s) beyond the signed high-watermark")
        sub = dict(subscriptions[subscription_id])
        invoice = dict(invoices[next(key for key, row in invoices.items() if row["subscription_id"] == subscription_id)])
        entitlement = dict(entitlements[subscription_id])
        grace_until = None
        types = []
        event_ids = []
        for sequence in range(1, high + 1):
            row, source = by_sequence[sequence]
            event_id = str(row["event_id"])
            kind = str(row["type"])
            data = row["data"]
            event_ids.append(event_id)
            types.append(kind)
            event_records.append({
                "event_id": event_id, "subscription_id": subscription_id,
                "provider_sequence": sequence, "source": source,
                "payload_hash": digest(canonical(row)), "run_id": policy["run_id"],
            })
            if kind == "invoice_finalized":
                invoice["total_cents"] = int(data["total_cents"])
            elif kind == "invoice_paid":
                invoice["paid_cents"] = int(data["amount_cents"])
                invoice["status"] = "paid"
                sub["status"] = "active"
                entitlement["state"] = "active"
                entitlement["seats"] = sub["seats"]
                entitlement["plan_code"] = sub["plan_code"]
            elif kind == "refund_partially_completed":
                invoice["refunded_cents"] = int(data["amount_cents"])
                invoice["status"] = "partially_refunded"
            elif kind == "subscription_updated":
                sub["plan_code"] = str(data["plan_code"])
                sub["seats"] = int(data["seats"])
                entitlement["plan_code"] = sub["plan_code"]
                entitlement["seats"] = sub["seats"]
            elif kind == "invoice_payment_failed":
                sub["status"] = "past_due"
                invoice["status"] = "payment_failed"
                grace_until = str(data["grace_until"])
            elif kind == "payment_retry_scheduled":
                pass
            elif kind == "chargeback_opened":
                grace_until = str(data["grace_until"])
            elif kind == "chargeback_lost":
                invoice["status"] = "charged_back"
                invoice["dispute_status"] = "lost"
                if grace_until is None or iso(str(policy["as_of"])) <= iso(grace_until):
                    raise ValueError(f"lost chargeback for {subscription_id} is not beyond a proven grace deadline")
                sub["status"] = "delinquent"
                entitlement["state"] = "suspended"
                entitlement["seats"] = 0
            elif kind == "cancellation_scheduled":
                if iso(str(data["effective_at"])) <= iso(str(policy["as_of"])):
                    raise ValueError("period-end cancellation boundary has already elapsed")
                sub["status"] = "cancel_at_period_end"
                entitlement["state"] = "active"
            else:
                raise ValueError(f"unsupported event type: {kind}")
        next_action = (
            "support_review_partial_refund" if "refund_partially_completed" in types else
            "manual_billing_review" if "chargeback_lost" in types else
            "close_recovered_payment_incident" if "invoice_payment_failed" in types and "invoice_paid" in types else
            "review_at_period_end"
        )
        version = int(subscriptions[subscription_id]["version"]) + high
        sub["version"] = invoice["version"] = entitlement["version"] = version
        entitlement["valid_until"] = sub["current_period_end"]
        required = {
            "subscription_id": subscription_id, "invoice_id": invoice["invoice_id"],
            "source_high_watermark": high, "subscription_status": sub["status"],
            "invoice_status": invoice["status"], "paid_cents": invoice["paid_cents"],
            "refunded_cents": invoice["refunded_cents"], "dispute_status": invoice["dispute_status"],
            "entitlement_state": entitlement["state"], "plan_code": sub["plan_code"],
            "seats": entitlement["seats"], "event_ids": sorted(event_ids),
            "bridged_event_ids": sorted(bridged),
            "duplicate_event_ids": sorted(event_id for event_id in event_ids if counts[event_id] > 1),
            "next_local_action": next_action, "external_action": "none",
        }
        got = by_id.get(subscription_id)
        differing = sorted(
            field for field in DECISION_FIELDS
            if not isinstance(got, dict) or got.get(field) != required[field]
        )
        if differing:
            problems.append(f"{subscription_id} differs in: {', '.join(differing)}")
    if problems:
        raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
    distinct = inputs["distinct"]
    quarantine = inputs["quarantined_event_ids"]
    operational = {
        "policy": policy,
        "snapshot": snapshot,
        "events": event_records,
        "quarantined_event_ids": quarantine,
        "quarantine_rows": [
            {
                "event_id": event_id, "reason": "unknown_subscription",
                "payload_hash": digest(canonical(distinct[event_id])), "run_id": policy["run_id"],
            }
            for event_id in quarantine
        ],
    }
    return candidate, operational


def projection_digest(connection: sqlite3.Connection) -> str:
    bundle = {
        "customers": table_rows(connection, "customers", "customer_id"),
        "subscriptions": table_rows(connection, "subscriptions", "subscription_id"),
        "invoices": table_rows(connection, "invoices", "invoice_id"),
        "entitlements": table_rows(connection, "entitlements", "subscription_id"),
        "processed_events": table_rows(connection, "processed_events", "event_id"),
        "quarantined_events": table_rows(connection, "quarantined_events", "event_id"),
        "rollback_rows": table_rows(connection, "rollback_rows", "run_id, table_name, record_key"),
    }
    return digest(canonical(bundle))


def preview(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    _, source_hash = source_bundle()
    value = {
        "schema_version": 1, "run_id": plan["run_id"], "status": "valid",
        "snapshot_id": plan["snapshot_id"], "snapshot_signature_verified": True,
        "decision_count": len(plan["decisions"]),
        "unique_event_count": len(facts["events"]),
        "bridged_event_ids": sorted(event_id for row in plan["decisions"] for event_id in row["bridged_event_ids"]),
        "duplicate_event_ids": sorted(event_id for row in plan["decisions"] for event_id in row["duplicate_event_ids"]),
        "quarantined_event_ids": plan["quarantined_event_ids"],
        "plan_hash": digest(canonical(plan)), "source_bundle_hash": source_hash,
        "external_actions_executed": False,
    }
    write_json(ROOT / ".entitlement_preview.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))


def restore_interrupted(connection: sqlite3.Connection) -> list[str]:
    restored = []
    runs = connection.execute("SELECT run_id FROM recovery_runs WHERE status = 'applying' ORDER BY run_id").fetchall()
    for (run_id,) in runs:
        cursor = connection.execute(
            "SELECT table_name, record_key, before_json FROM rollback_rows WHERE run_id=? AND restored=0 ORDER BY table_name, record_key",
            (run_id,),
        )
        for table, key, before_json in cursor.fetchall():
            if table not in {"subscriptions", "invoices", "entitlements"}:
                raise ValueError(f"unsafe rollback table {table}")
            row = json.loads(before_json)
            columns = list(row)
            key_column = "invoice_id" if table == "invoices" else "subscription_id"
            assignments = ", ".join(f"{column}=?" for column in columns if column != key_column)
            values = [row[column] for column in columns if column != key_column] + [key]
            connection.execute(f"UPDATE {table} SET {assignments} WHERE {key_column}=?", values)
        connection.execute("DELETE FROM processed_events WHERE run_id=?", (run_id,))
        connection.execute("DELETE FROM quarantined_events WHERE run_id=?", (run_id,))
        connection.execute("UPDATE rollback_rows SET restored=1 WHERE run_id=?", (run_id,))
        connection.execute("UPDATE recovery_runs SET status='rolled_back_recovered' WHERE run_id=?", (run_id,))
        restored.append(run_id)
    return restored


def apply(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    preview_value = read_json(ROOT / ".entitlement_preview.json")
    _, source_hash = source_bundle()
    plan_hash = digest(canonical(plan))
    if preview_value.get("status") != "valid" or preview_value.get("plan_hash") != plan_hash or preview_value.get("source_bundle_hash") != source_hash:
        raise ValueError("run preview for the current plan and source bundle before apply")
    connection = sqlite3.connect(DB)
    try:
        connection.execute("BEGIN IMMEDIATE")
        restored = restore_interrupted(connection)
        for row in plan["decisions"]:
            sub_id, invoice_id = row["subscription_id"], row["invoice_id"]
            base_sub = connection.execute("SELECT customer_id, current_period_end FROM subscriptions WHERE subscription_id=?", (sub_id,)).fetchone()
            version = connection.execute("SELECT version FROM subscriptions WHERE subscription_id=?", (sub_id,)).fetchone()[0]
            high = int(row["source_high_watermark"])
            if restored or plan["run_id"] not in {item[0] for item in connection.execute("SELECT run_id FROM recovery_runs")}:
                version = version + high
            connection.execute(
                "UPDATE subscriptions SET plan_code=?, status=?, seats=?, version=? WHERE subscription_id=?",
                (row["plan_code"], row["subscription_status"], row["seats"] if row["entitlement_state"] == "active" else connection.execute("SELECT seats FROM subscriptions WHERE subscription_id=?", (sub_id,)).fetchone()[0], version, sub_id),
            )
            connection.execute(
                "UPDATE invoices SET paid_cents=?, refunded_cents=?, dispute_status=?, status=?, version=? WHERE invoice_id=?",
                (row["paid_cents"], row["refunded_cents"], row["dispute_status"], row["invoice_status"], version, invoice_id),
            )
            connection.execute(
                "UPDATE entitlements SET plan_code=?, state=?, seats=?, valid_until=?, version=? WHERE subscription_id=?",
                (row["plan_code"], row["entitlement_state"], row["seats"], base_sub[1], version, sub_id),
            )
        connection.execute("DELETE FROM processed_events WHERE run_id=?", (plan["run_id"],))
        connection.execute("DELETE FROM quarantined_events WHERE run_id=?", (plan["run_id"],))
        connection.executemany(
            "INSERT INTO processed_events VALUES (:event_id,:subscription_id,:provider_sequence,:source,:payload_hash,:run_id)", facts["events"],
        )
        connection.executemany(
            "INSERT INTO quarantined_events VALUES (:event_id,:reason,:payload_hash,:run_id)", facts["quarantine_rows"],
        )
        connection.execute(
            "INSERT INTO recovery_runs VALUES (?,?,?,?,?,?,0) ON CONFLICT(run_id) DO UPDATE SET status=excluded.status, plan_hash=excluded.plan_hash, source_bundle_hash=excluded.source_bundle_hash, semantic_db_hash=excluded.semantic_db_hash, revision=excluded.revision, external_actions_executed=0",
            (plan["run_id"], "applied_local", plan_hash, source_hash, "", 18),
        )
        connection.execute("UPDATE system_state SET value='18' WHERE key='projection_revision'")
        connection.execute("UPDATE system_state SET value='applied_not_staged' WHERE key='stage_state'")
        connection.commit()
        semantic_hash = projection_digest(connection)
        connection.execute("UPDATE recovery_runs SET semantic_db_hash=? WHERE run_id=?", (semantic_hash, plan["run_id"]))
        connection.commit()
    finally:
        connection.close()
    print(json.dumps({"status": "applied_local", "run_id": plan["run_id"], "restored_runs": restored}, sort_keys=True))


def verify(plan_path: Path) -> dict[str, Any]:
    plan, facts = validate_plan(plan_path)
    _, source_hash = source_bundle()
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        run = connection.execute("SELECT status,plan_hash,source_bundle_hash,semantic_db_hash,revision,external_actions_executed FROM recovery_runs WHERE run_id=?", (plan["run_id"],)).fetchone()
        processed = table_rows(connection, "processed_events", "event_id")
        quarantined = table_rows(connection, "quarantined_events", "event_id")
        prior = connection.execute("SELECT status FROM recovery_runs WHERE run_id='ER-INTERRUPTED-20260817'").fetchone()
        restored_count = connection.execute("SELECT COUNT(*) FROM rollback_rows WHERE run_id='ER-INTERRUPTED-20260817' AND restored=1").fetchone()[0]
        semantic_hash = projection_digest(connection)
    event_ok = {(row["event_id"], row["source"], row["payload_hash"]) for row in processed} == {(row["event_id"], row["source"], row["payload_hash"]) for row in facts["events"]}
    quarantine_ok = {row["event_id"] for row in quarantined} == set(facts["quarantined_event_ids"])
    checks = {
        "plan_hash_matches": bool(run and run[1] == plan_hash),
        "source_bundle_matches": bool(run and run[2] == source_hash),
        "semantic_db_matches": bool(run and run[3] == semantic_hash),
        "event_journal_exact": event_ok,
        "quarantine_exact": quarantine_ok,
        "interrupted_run_recovered": prior == ("rolled_back_recovered",) and restored_count == 3,
        "local_only": bool(run and run[5] == 0),
    }
    value = {
        "schema_version": 1, "run_id": plan["run_id"],
        "status": "pass" if all(checks.values()) else "fail", "checks": checks,
        "plan_hash": plan_hash, "source_bundle_hash": source_hash,
        "semantic_db_hash": semantic_hash, "projection_revision": 18,
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/verification.json", value)
    if value["status"] != "pass":
        raise ValueError("verification failed")
    print(json.dumps(value, indent=2, sort_keys=True))
    return value


def stage(plan_path: Path) -> dict[str, Any]:
    plan, _ = validate_plan(plan_path)
    verification = read_json(ROOT / "state/verification.json")
    if verification.get("status") != "pass" or verification.get("run_id") != plan["run_id"]:
        raise ValueError("run verify for the current plan before stage")
    verification_hash = digest(canonical(verification))
    token_input = {
        "run_id": plan["run_id"], "plan_hash": verification["plan_hash"],
        "source_bundle_hash": verification["source_bundle_hash"],
        "semantic_db_hash": verification["semantic_db_hash"],
        "verification_hash": verification_hash, "stage_boundary": "local_only_pending_support_approval",
    }
    receipt = {
        "schema_version": 1, **token_input,
        "status": "staged_pending_support_approval",
        "stage_token": digest(canonical(token_input)),
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/recovery_receipt.json", receipt)
    with sqlite3.connect(DB) as connection:
        connection.execute("UPDATE recovery_runs SET status='staged_pending_support_approval' WHERE run_id=?", (plan["run_id"],))
        connection.execute("UPDATE system_state SET value='staged_pending_support_approval' WHERE key='stage_state'")
        connection.commit()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def replay(plan_path: Path) -> None:
    before_receipt = (ROOT / "state/recovery_receipt.json").read_bytes()
    with sqlite3.connect(DB) as connection:
        before_semantic = projection_digest(connection)
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    after_receipt = (ROOT / "state/recovery_receipt.json").read_bytes()
    with sqlite3.connect(DB) as connection:
        after_semantic = projection_digest(connection)
    value = {
        "schema_version": 1, "run_id": read_json(plan_path)["run_id"],
        "status": "pass" if before_receipt == after_receipt and before_semantic == after_semantic else "fail",
        "receipt_byte_stable": before_receipt == after_receipt,
        "semantic_db_stable": before_semantic == after_semantic,
        "semantic_db_hash": after_semantic, "external_actions_executed": False,
    }
    write_json(ROOT / "state/replay_report.json", value)
    if value["status"] != "pass":
        raise ValueError("replay was not idempotent")
    print(json.dumps(value, indent=2, sort_keys=True))


def inspect() -> None:
    _, source_hash = source_bundle()
    snapshot = verified_snapshot()
    deliveries = spool()
    with sqlite3.connect(DB) as connection:
        result = {
            "source_bundle_hash": source_hash,
            "snapshot_id": snapshot["snapshot_id"],
            "snapshot_signature_verified": True,
            "snapshot_high_watermarks": snapshot["known_subscription_high_watermarks"],
            "delivery_count": len(deliveries),
            "duplicate_event_ids": sorted(event_id for event_id, count in Counter(row["event_id"] for row in deliveries).items() if count > 1),
            "subscriptions": table_rows(connection, "subscriptions", "subscription_id"),
            "invoices": table_rows(connection, "invoices", "invoice_id"),
            "entitlements": table_rows(connection, "entitlements", "subscription_id"),
            "recovery_runs": table_rows(connection, "recovery_runs", "run_id"),
            "rollback_rows": table_rows(connection, "rollback_rows", "run_id, table_name, record_key"),
        }
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline subscription-entitlement recovery controller")
    parser.add_argument("command", choices=("inspect", "preview", "apply", "verify", "stage", "replay"))
    parser.add_argument("plan", nargs="?", default="recovery_plan.json")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            inspect()
        elif args.command == "preview":
            preview(ROOT / args.plan)
        elif args.command == "apply":
            apply(ROOT / args.plan)
        elif args.command == "verify":
            verify(ROOT / args.plan)
        elif args.command == "stage":
            stage(ROOT / args.plan)
        else:
            replay(ROOT / args.plan)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
