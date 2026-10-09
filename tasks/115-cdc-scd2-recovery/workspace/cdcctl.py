#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "warehouse.db"
BATCH = ROOT / "cdc_batch.jsonl"
BATCH_ID = "CDC-2026-08-19-42"
NOW = "2026-08-19T12:00:00Z"
TABLES = (
    "dimension_current",
    "dimension_history",
    "event_ledger",
    "event_quarantine",
    "recovery_transactions",
    "recovery_journal",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: Any) -> str:
    return _digest_bytes(_canonical(value))


def _sha(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in TABLES:
        raise ValueError(f"unsupported table: {table}")
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    order = ", ".join(columns[:2]) if len(columns) > 1 else columns[0]
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]


def _snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    return {table: _rows(connection, table) for table in TABLES}


def _events() -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    records: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    digests: dict[str, str] = {}
    for number, line in enumerate(BATCH.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        event_id = str(row["event_id"])
        payload_sha = _digest(row)
        counts[event_id] += 1
        if event_id in digests and digests[event_id] != payload_sha:
            raise ValueError(f"conflicting duplicate {event_id} at line {number}")
        digests[event_id] = payload_sha
        records[event_id] = row
    return records, dict(counts)


def _sources() -> tuple[set[int], set[str], dict[str, dict[str, Any]]]:
    registry = json.loads((ROOT / "schema_registry.json").read_text(encoding="utf-8"))
    supported = {int(value) for value in registry["supported"]}
    with (ROOT / "retention_holds.csv").open(newline="", encoding="utf-8") as handle:
        holds = {
            row["customer_id"]
            for row in csv.DictReader(handle)
            if row["status"] == "active"
        }
    signed = json.loads((ROOT / "signed_corrections.json").read_text(encoding="utf-8"))
    trusted_keys = set(signed["trusted_key_ids"])
    corrections = {
        row["correction_id"]: row
        for row in signed["corrections"]
        if row["key_id"] in trusted_keys and row["signature_status"] == "verified"
    }
    return supported, holds, corrections


def _initial() -> dict[str, list[dict[str, Any]]]:
    value = json.loads((ROOT / "initial_warehouse.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("initial warehouse snapshot must be an object")
    return value


def _derive_dispositions(connection: sqlite3.Connection) -> tuple[dict[str, str], dict[str, list[str]]]:
    events, _ = _events()
    supported, holds, corrections = _sources()
    current = {
        row["customer_id"]: int(row["current_version"])
        for row in _initial()["dimension_current"]
    }
    dispositions: dict[str, str] = {}
    candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for event_id, row in events.items():
        customer = str(row["customer_id"])
        version = int(row["entity_version"])
        operation = str(row["operation"])
        if int(row["schema_version"]) not in supported:
            dispositions[event_id] = "quarantine_unsupported_schema"
        elif operation == "correction":
            correction = corrections.get(str(row.get("correction_id")))
            trusted = bool(
                correction
                and correction["customer_id"] == customer
                and int(correction["target_version"]) == version
                and correction["patch"] == row.get("patch")
            )
            dispositions[event_id] = "apply_signed_correction" if trusted else "quarantine_untrusted_correction"
        elif operation == "delete" and customer in holds:
            dispositions[event_id] = "quarantine_retention_hold"
        elif customer not in current and version == 1 and not row.get("consent_ref"):
            dispositions[event_id] = "quarantine_missing_consent"
        elif version <= current.get(customer, 0):
            dispositions[event_id] = "ignore_stale"
        else:
            candidates[customer].append((version, event_id))
    for customer, values in candidates.items():
        values.sort()
        start = current.get(customer, 0) + 1
        versions = [version for version, _ in values]
        complete = versions == list(range(start, max(versions) + 1))
        for _, event_id in values:
            dispositions[event_id] = "apply_upsert" if complete else "defer_version_gap"

    # Each inner set is one requirement group.  A candidate must cite at least
    # one locator from every group; multiple stable identifiers for the same
    # visible row/section are intentionally equivalent.
    evidence = {
        event_id: [{f"cdc_batch.jsonl#{event_id}"}]
        for event_id in events
    }
    evidence["EV-404"].append({
        "retention_holds.csv#C003",
        "retention_holds.csv#HOLD-77",
    })
    evidence["EV-405"].append({
        "recovery_policy.md#5",
        "recovery_policy.md#missing-consent",
    })
    evidence["EV-406"].append({"warehouse.db#recovery_journal"})
    evidence["EV-408"].append({"signed_corrections.json#CORR-88"})
    evidence["EV-409"].append({
        "schema_registry.json",
        "schema_registry.json#supported",
    })
    return dispositions, evidence


def _normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    rows = plan.get("actions")
    actions = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            refs = row.get("evidence_refs")
            actions.append({
                "event_id": str(row.get("event_id", "")),
                "disposition": str(row.get("disposition", "")),
                "evidence_refs": sorted({str(value) for value in refs}) if isinstance(refs, list) else [],
            })
    actions.sort(key=lambda row: row["event_id"])
    return {
        "schema_version": plan.get("schema_version"),
        "batch_id": plan.get("batch_id"),
        "source_sha256": plan.get("source_sha256"),
        "actions": actions,
        "external_publish_executed": plan.get("external_publish_executed"),
    }


def _load_plan(name: str) -> tuple[dict[str, Any], str]:
    plan = json.loads((ROOT / name).read_text(encoding="utf-8"))
    return plan, _digest(_normalized_plan(plan))


def _validate_plan(
    connection: sqlite3.Connection,
    plan: dict[str, Any],
) -> tuple[bool, dict[str, Any], dict[str, list[list[str]]]]:
    policy_map, evidence = _derive_dispositions(connection)
    rows = plan.get("actions")
    actual: dict[str, str] = {}
    refs: dict[str, set[str]] = {}
    unique_rows = isinstance(rows, list)
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("evidence_refs"), list):
                unique_rows = False
                continue
            event_id = str(row.get("event_id"))
            if event_id in actual:
                unique_rows = False
            actual[event_id] = str(row.get("disposition"))
            refs[event_id] = {str(value) for value in row["evidence_refs"]}
    missing_evidence = {
        event_id: [sorted(group) for group in groups if refs.get(event_id, set()).isdisjoint(group)]
        for event_id, groups in evidence.items()
    }
    missing_evidence = {
        event_id: groups for event_id, groups in missing_evidence.items() if groups
    }
    evidence_ok = set(refs) == set(evidence) and not missing_evidence
    checks = {
        "schema_and_batch": plan.get("schema_version") == 1 and plan.get("batch_id") == BATCH_ID,
        "source_binding": plan.get("source_sha256") == _sha(BATCH),
        "one_action_per_unique_event": unique_rows and set(actual) == set(policy_map),
        "policy_dispositions": actual == policy_map,
        "minimum_local_evidence": evidence_ok,
        "offline_boundary": plan.get("external_publish_executed") is False,
    }
    return all(checks.values()), checks, missing_evidence


def _normalize_patch(event: dict[str, Any]) -> dict[str, Any]:
    patch = dict(event.get("patch", {}))
    if int(event["schema_version"]) == 2:
        if "market" in patch:
            patch["region"] = patch.pop("market")
        if "consent_status" in patch:
            patch["consent_state"] = {"yes": "granted", "no": "denied"}[patch.pop("consent_status")]
    return patch


def _simulate_final(connection: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    initial = _initial()
    original_history = [dict(row) for row in initial["dimension_history"]]
    history = [dict(row) for row in original_history]
    current = {row["customer_id"]: dict(row) for row in initial["dimension_current"]}
    events, _ = _events()
    policy_map, _ = _derive_dispositions(connection)

    for event_id, disposition in policy_map.items():
        if disposition != "apply_signed_correction":
            continue
        event = events[event_id]
        customer = str(event["customer_id"])
        target = int(event["entity_version"])
        for field, value in _normalize_patch(event).items():
            customer_original = sorted(
                (row for row in original_history if row["customer_id"] == customer),
                key=lambda row: int(row["version"]),
            )
            customer_rows = {
                int(row["version"]): row
                for row in history
                if row["customer_id"] == customer
            }
            propagate = False
            prior_original: dict[str, Any] | None = None
            for row in customer_original:
                version = int(row["version"])
                if version == target:
                    propagate = True
                elif version > target and prior_original is not None and row[field] != prior_original[field]:
                    propagate = False
                if propagate and version >= target:
                    customer_rows[version][field] = value
                prior_original = row
            latest = max(customer_rows)
            current[customer][field] = customer_rows[latest][field]

    applicable = [
        events[event_id]
        for event_id, disposition in policy_map.items()
        if disposition == "apply_upsert"
    ]
    for event in sorted(
        applicable,
        key=lambda row: (str(row["customer_id"]), int(row["entity_version"]), str(row["event_id"])),
    ):
        customer = str(event["customer_id"])
        version = int(event["entity_version"])
        prior = current.get(customer)
        state = {
            "name": prior["name"] if prior else None,
            "segment": prior["segment"] if prior else None,
            "region": prior["region"] if prior else None,
            "consent_state": prior["consent_state"] if prior else None,
        }
        state.update(_normalize_patch(event))
        if prior:
            for row in history:
                if row["customer_id"] == customer and int(row["version"]) == int(prior["current_version"]):
                    row["valid_to"] = event["effective_at"]
                    break
        history.append({
            "customer_id": customer,
            "version": version,
            **state,
            "valid_from": event["effective_at"],
            "valid_to": None,
            "is_deleted": 0,
            "source_event_id": event["event_id"],
        })
        current[customer] = {
            "customer_id": customer,
            "current_version": version,
            **state,
            "is_deleted": 0,
        }
    return (
        sorted(current.values(), key=lambda row: row["customer_id"]),
        sorted(history, key=lambda row: (row["customer_id"], int(row["version"]))),
    )


def _apply_correction(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    customer = event["customer_id"]
    version = int(event["entity_version"])
    patch = _normalize_patch(event)
    allowed = {"name", "segment", "region", "consent_state"}
    for field, value in patch.items():
        if field not in allowed:
            raise ValueError(f"unsupported correction field: {field}")
        connection.execute(
            f"UPDATE dimension_history SET {field}=? WHERE customer_id=? AND version=?",
            (value, customer, version),
        )
        later_events, _ = _events()
        explicit_override = any(
            row["customer_id"] == customer
            and int(row["entity_version"]) > version
            and row["operation"] == "upsert"
            and field in _normalize_patch(row)
            for row in later_events.values()
        )
        if not explicit_override:
            connection.execute(
                f"UPDATE dimension_current SET {field}=? WHERE customer_id=? AND current_version>=?",
                (value, customer, version),
            )


def _apply_upsert(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    customer = str(event["customer_id"])
    version = int(event["entity_version"])
    patch = _normalize_patch(event)
    prior = connection.execute(
        "SELECT * FROM dimension_current WHERE customer_id=?", (customer,)
    ).fetchone()
    state = {
        "name": prior["name"] if prior else None,
        "segment": prior["segment"] if prior else None,
        "region": prior["region"] if prior else None,
        "consent_state": prior["consent_state"] if prior else None,
    }
    state.update(patch)
    if any(state[field] in (None, "") for field in state):
        raise ValueError(f"incomplete projection for {event['event_id']}")
    if prior:
        connection.execute(
            "UPDATE dimension_history SET valid_to=? WHERE customer_id=? AND version=?",
            (event["effective_at"], customer, int(prior["current_version"])),
        )
    connection.execute(
        "INSERT INTO dimension_history VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?)",
        (customer, version, state["name"], state["segment"], state["region"], state["consent_state"], event["effective_at"], event["event_id"]),
    )
    connection.execute(
        "INSERT INTO dimension_current VALUES (?, ?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(customer_id) DO UPDATE SET current_version=excluded.current_version, name=excluded.name, segment=excluded.segment, region=excluded.region, consent_state=excluded.consent_state, is_deleted=0",
        (customer, version, state["name"], state["segment"], state["region"], state["consent_state"]),
    )


def _commit(connection: sqlite3.Connection, plan: dict[str, Any], plan_sha: str) -> None:
    events, _ = _events()
    actions = {row["event_id"]: row["disposition"] for row in plan["actions"]}
    for event_id, disposition in actions.items():
        if disposition == "apply_signed_correction":
            _apply_correction(connection, events[event_id])
    for event_id, disposition in sorted(
        actions.items(), key=lambda item: (events[item[0]]["customer_id"], int(events[item[0]]["entity_version"]), item[0])
    ):
        event = events[event_id]
        if disposition == "apply_upsert":
            _apply_upsert(connection, event)
        elif disposition.startswith("quarantine_"):
            connection.execute(
                "INSERT INTO event_quarantine VALUES (?, ?, ?, ?)",
                (event_id, event["customer_id"], disposition.removeprefix("quarantine_"), _digest(event)),
            )
        connection.execute(
            "INSERT INTO event_ledger VALUES (?, ?, ?, ?)",
            (event_id, disposition, _digest(event), NOW),
        )
    connection.execute(
        "INSERT INTO recovery_transactions VALUES (?, ?, ?, ?, ?)",
        (BATCH_ID, plan_sha, _sha(BATCH), len(actions), NOW),
    )
    connection.execute(
        "UPDATE recovery_journal SET phase='committed', plan_sha256=?, committed_at=? WHERE batch_id=?",
        (plan_sha, NOW, BATCH_ID),
    )


def inspect() -> int:
    events, counts = _events()
    with _connect() as connection:
        current = {row["customer_id"]: row["current_version"] for row in _rows(connection, "dimension_current")}
        journal = _rows(connection, "recovery_journal")
    by_customer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events.values():
        by_customer[event["customer_id"]].append({
            "event_id": event["event_id"], "version": event["entity_version"],
            "operation": event["operation"], "schema_version": event["schema_version"],
        })
    result = {
        "batch_id": BATCH_ID,
        "source_sha256": _sha(BATCH),
        "delivery_rows": sum(counts.values()),
        "unique_events": len(events),
        "exact_redeliveries": sorted(event_id for event_id, count in counts.items() if count > 1),
        "current_versions": current,
        "events_by_customer": {key: sorted(value, key=lambda row: (row["version"], row["event_id"])) for key, value in sorted(by_customer.items())},
        "recovery_journal": journal,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def query(sql: str) -> int:
    if not sql.lstrip().casefold().startswith(("select", "pragma")):
        print("query accepts SELECT or PRAGMA only")
        return 2
    with _connect() as connection:
        print(json.dumps([dict(row) for row in connection.execute(sql)], indent=2, sort_keys=True))
    return 0


def preview(name: str) -> int:
    try:
        plan, plan_sha = _load_plan(name)
        with _connect() as connection:
            valid, checks, missing_evidence = _validate_plan(connection, plan)
            connection.rollback()
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, KeyError, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2))
        return 2
    result = {
        "status": "pass" if valid else "fail",
        "plan_sha256": plan_sha,
        "checks": checks,
    }
    if missing_evidence:
        result["missing_evidence_by_event"] = missing_evidence
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if valid else 2


def apply(name: str) -> int:
    try:
        plan, plan_sha = _load_plan(name)
        with _connect() as connection:
            prior = connection.execute(
                "SELECT plan_sha256 FROM recovery_transactions WHERE batch_id=?", (BATCH_ID,)
            ).fetchone()
            if prior:
                status = "idempotent" if prior["plan_sha256"] == plan_sha else "conflict"
                print(json.dumps({"status": status, "plan_sha256": plan_sha}, indent=2))
                return 0 if status == "idempotent" else 2
            valid, checks, missing_evidence = _validate_plan(connection, plan)
            if not valid:
                result = {"status": "rejected", "checks": checks}
                if missing_evidence:
                    result["missing_evidence_by_event"] = missing_evidence
                print(json.dumps(result, indent=2, sort_keys=True))
                return 2
            _commit(connection, plan, plan_sha)
            connection.commit()
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, KeyError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"status": "applied", "plan_sha256": plan_sha}, indent=2))
    return 0


def _verification(connection: sqlite3.Connection) -> dict[str, Any]:
    current = _rows(connection, "dimension_current")
    history = _rows(connection, "dimension_history")
    ledger = {row["event_id"]: row["disposition"] for row in connection.execute("SELECT * FROM event_ledger WHERE event_id LIKE 'EV-%'")}
    quarantine = {row["event_id"]: row["reason"] for row in connection.execute("SELECT * FROM event_quarantine")}
    transactions = _rows(connection, "recovery_transactions")
    journal = _rows(connection, "recovery_journal")
    policy_map, _ = _derive_dispositions(connection)
    projected_current, projected_history = _simulate_final(connection)
    projected_quarantine = {
        event_id: disposition.removeprefix("quarantine_")
        for event_id, disposition in policy_map.items()
        if disposition.startswith("quarantine_")
    }
    checks = {
        "current_projection": current == projected_current,
        "history_chain": history == projected_history,
        "event_ledger": ledger == policy_map,
        "quarantine": quarantine == projected_quarantine,
        "single_transaction": len(transactions) == 1 and transactions[0]["action_count"] == len(policy_map),
        "journal_committed": len(journal) == 1 and journal[0]["phase"] == "committed" and bool(journal[0]["plan_sha256"]),
    }
    snapshot = _snapshot(connection)
    return {
        "tool": "cdcctl/1",
        "batch_id": BATCH_ID,
        "status": "pass" if all(checks.values()) else "fail",
        "source_sha256": _sha(BATCH),
        "logical_warehouse_sha256": _digest(snapshot),
        "checks": checks,
        "external_publish_executed": False,
    }


def verify() -> int:
    try:
        with _connect() as connection:
            receipt = _verification(connection)
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        receipt = {"tool": "cdcctl/1", "batch_id": BATCH_ID, "status": "fail", "error": str(exc), "external_publish_executed": False}
    (ROOT / "cdc_verification.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("status") == "pass" else 2


def stage(name: str) -> int:
    try:
        plan, plan_sha = _load_plan(name)
        with _connect() as connection:
            verification = _verification(connection)
        on_disk = json.loads((ROOT / "cdc_verification.json").read_text(encoding="utf-8"))
        handoff = (ROOT / "recovery_handoff.md").read_text(encoding="utf-8")
        low = handoff.casefold()
        handoff_ok = len(handoff) >= 600 and all(
            term in low for term in ("ev-401", "ev-402", "ev-403", "ev-404", "ev-405", "ev-406", "ev-407", "ev-408", "ev-409", "idempotent", "no external")
        )
        if verification["status"] != "pass" or on_disk != verification or not handoff_ok:
            print(json.dumps({"status": "rejected", "verification": verification["status"], "handoff_ok": handoff_ok}, indent=2))
            return 2
        receipt = {
            "receipt_type": "local_cdc_recovery_stage",
            "batch_id": BATCH_ID,
            "phase": "staged_pending_publish_approval",
            "plan_sha256": plan_sha,
            "source_sha256": _sha(BATCH),
            "logical_warehouse_sha256": verification["logical_warehouse_sha256"],
            "verification_sha256": _digest_bytes((ROOT / "cdc_verification.json").read_bytes()),
            "external_publish_executed": False,
        }
        receipt["stage_token"] = _digest(receipt)
        path = ROOT / "cdc_stage_receipt.json"
        rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        status = "idempotent" if path.is_file() and path.read_text(encoding="utf-8") == rendered else "staged"
        path.write_text(rendered, encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"status": status, "stage_token": receipt["stage_token"]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and recover the local CDC/SCD2 batch")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("sql")
    for command in ("preview", "apply", "stage"):
        child = sub.add_parser(command)
        child.add_argument("plan")
    sub.add_parser("verify")
    args = parser.parse_args()
    commands = {
        "inspect": inspect,
        "query": lambda: query(args.sql),
        "preview": lambda: preview(args.plan),
        "apply": lambda: apply(args.plan),
        "verify": verify,
        "stage": lambda: stage(args.plan),
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
