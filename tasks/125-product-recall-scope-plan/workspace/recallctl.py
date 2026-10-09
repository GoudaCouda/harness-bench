#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "recall.db"
SEED = ROOT / "recall_seed.sql"
CHECKPOINT = ROOT / "recall_checkpoint.json"
REVISIONS = ROOT / "signed_scope_revisions.json"
EVENTS = ROOT / "shipment_events.jsonl"
NOW = "2026-08-19T12:00:00Z"
STATE_TABLES = (
    "lots",
    "component_batches",
    "lot_components",
    "inventory",
    "channels",
    "shipments",
)
ALL_TABLES = (
    *STATE_TABLES,
    "event_ledger",
    "event_quarantine",
    "recall_transactions",
    "recall_journal",
)
ALLOWED_EVIDENCE = {
    "recall.db",
    "recall_checkpoint.json",
    "recall_policy.md",
    "signed_scope_revisions.json",
    "shipment_events.jsonl",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _connect(path: Path = DB) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _baseline() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SEED.read_text(encoding="utf-8"))
    checkpoint = _checkpoint()
    connection.execute(
        "UPDATE recall_journal SET source_state_sha256=? WHERE recall_id=?",
        (checkpoint["source_state_sha256"], checkpoint["recall_id"]),
    )
    return connection


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in ALL_TABLES:
        raise ValueError(f"unsupported table: {table}")
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    if not columns:
        raise ValueError(f"missing table: {table}")
    order = ", ".join(columns[:2])
    return [
        dict(row)
        for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    ]


def _snapshot(
    connection: sqlite3.Connection, tables: tuple[str, ...] = ALL_TABLES
) -> dict[str, list[dict[str, Any]]]:
    return {table: _rows(connection, table) for table in tables}


def _checkpoint() -> dict[str, Any]:
    value = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("checkpoint must be an object")
    return value


def _scope_revision() -> dict[str, Any]:
    source = json.loads(REVISIONS.read_text(encoding="utf-8"))
    trusted = set(source.get("trusted_key_ids", []))
    revisions = [
        row
        for row in source.get("revisions", [])
        if isinstance(row, dict)
        and row.get("signature_status") == "verified"
        and row.get("key_id") in trusted
    ]
    if not revisions:
        raise ValueError("no trusted signed scope revision")
    superseded = {row.get("supersedes") for row in revisions if row.get("supersedes")}
    controlling = [row for row in revisions if row.get("revision_id") not in superseded]
    if len(controlling) != 1:
        raise ValueError("signed scope chain does not have one controlling revision")
    return controlling[0]


def _events() -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    records: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for number, line in enumerate(EVENTS.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        event_id = str(row["event_id"])
        payload_sha = _digest(row)
        if event_id in digests and digests[event_id] != payload_sha:
            raise ValueError(f"conflicting duplicate {event_id} at line {number}")
        digests[event_id] = payload_sha
        records[event_id] = row
        counts[event_id] += 1
    return records, dict(counts)


def _descends_from(
    batch_id: str, targets: set[str], batches: dict[str, dict[str, Any]]
) -> bool:
    seen: set[str] = set()
    current: str | None = batch_id
    while current and current not in seen:
        if current in targets:
            return True
        seen.add(current)
        row = batches.get(current)
        current = (
            str(row.get("parent_batch_id"))
            if row and row.get("parent_batch_id")
            else None
        )
    return False


def _scope_decisions(connection: sqlite3.Connection) -> dict[str, str]:
    revision = _scope_revision()
    targets = {str(value) for value in revision.get("target_batch_ids", [])}
    batches = {row["batch_id"]: row for row in _rows(connection, "component_batches")}
    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relation in _rows(connection, "lot_components"):
        components[relation["lot_id"]].append(batches[relation["batch_id"]])
    decisions: dict[str, str] = {}
    for lot in _rows(connection, "lots"):
        manufactured = str(lot["manufactured_at"])
        in_window = (
            str(revision["manufactured_from"])
            <= manufactured
            <= str(revision["manufactured_through"])
        )
        linked = components.get(lot["lot_id"], [])
        affected = in_window and any(
            batch["batch_id"] in targets
            or (
                bool(revision.get("include_descendants"))
                and batch["trace_status"] == "verified"
                and _descends_from(str(batch["batch_id"]), targets, batches)
            )
            for batch in linked
        )
        unresolved = in_window and any(
            batch["trace_status"] == "unresolved_parent"
            and batch["material_code"] == revision["target_material_code"]
            for batch in linked
        )
        decisions[lot["lot_id"]] = (
            "affected" if affected else "pending_trace" if unresolved else "unaffected"
        )
    return decisions


def _event_dispositions(connection: sqlite3.Connection) -> dict[str, str]:
    events, _ = _events()
    shipments = {row["shipment_id"]: row for row in _rows(connection, "shipments")}
    by_shipment: dict[str, list[tuple[int, str]]] = defaultdict(list)
    result: dict[str, str] = {}
    for event_id, event in events.items():
        shipment_id = str(event["shipment_id"])
        if shipment_id not in shipments:
            result[event_id] = "quarantine_unknown_shipment"
        else:
            by_shipment[shipment_id].append((int(event["sequence"]), event_id))
    for shipment_id, candidates in by_shipment.items():
        stored = int(shipments[shipment_id]["last_sequence"])
        greatest = max(sequence for sequence, _ in candidates)
        for sequence, event_id in candidates:
            result[event_id] = (
                "apply_current"
                if sequence == greatest and sequence > stored
                else "ignore_stale"
            )
    return result


def _actions(
    plan: dict[str, Any], key: str, id_key: str
) -> tuple[dict[str, str], bool]:
    rows = plan.get(key)
    result: dict[str, str] = {}
    unique = isinstance(rows, list)
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                unique = False
                continue
            identifier = str(row.get(id_key, ""))
            if not identifier or identifier in result:
                unique = False
            result[identifier] = str(row.get("disposition", ""))
    return result, unique


def _normalize_policy_fragment(fragment: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fragment.casefold()).strip("-")


def _normalize_evidence_ref(ref: str, scope_revision_id: object) -> str:
    if "#" not in ref:
        return ref
    filename, fragment = ref.split("#", 1)
    if filename == "recall_policy.md":
        return f"{filename}#{_normalize_policy_fragment(fragment)}"
    if filename == "signed_scope_revisions.json":
        revision_id = str(scope_revision_id)
        normalized = fragment.strip("/")
        if normalized in {revision_id, f"revisions/{revision_id}", "revisions"}:
            return f"{filename}#revisions/{revision_id}"
    return ref


def _evidence_diagnostics(
    plan: dict[str, Any], key: str, id_key: str
) -> dict[str, list[str]]:
    rows = plan.get(key)
    if not isinstance(rows, list):
        return {"<collection>": [f"{key} must be a list"]}
    events = _events()[0] if id_key == "event_id" else {}
    known_shipments: set[str] = set()
    if id_key == "event_id":
        with _connect() as connection:
            known_shipments = {
                str(row["shipment_id"]) for row in _rows(connection, "shipments")
            }
    problems: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_refs"), list):
            identifier = (
                str(row.get(id_key, "<missing-id>"))
                if isinstance(row, dict)
                else "<invalid-row>"
            )
            problems[identifier] = ["evidence_refs must be a list"]
            continue
        identifier = str(row.get(id_key, ""))
        raw_refs = {str(value) for value in row["evidence_refs"]}
        refs = {
            _normalize_evidence_ref(ref, plan.get("scope_revision_id"))
            for ref in raw_refs
        }
        if id_key == "lot_id":
            required = {
                f"recall.db#lots/{identifier}",
                f"signed_scope_revisions.json#revisions/{plan.get('scope_revision_id')}",
                "recall_policy.md#genealogy-decisions",
            }
        else:
            event = events.get(identifier, {})
            shipment_id = str(event.get("shipment_id", ""))
            required = {
                f"shipment_events.jsonl#{identifier}",
                "recall_policy.md#feed-adjudication",
            }
            if shipment_id in known_shipments:
                required.add(f"recall.db#shipments/{shipment_id}")
        missing = sorted(required - refs)
        invalid = sorted(
            ref
            for ref in raw_refs
            if not (
                "#" in ref
                and not ref.startswith(("/", "../", "http://", "https://"))
                and ref.split("#", 1)[0] in ALLOWED_EVIDENCE
            )
        )
        messages = [f"missing:{ref}" for ref in missing]
        messages.extend(f"invalid:{ref}" for ref in invalid)
        if messages:
            problems[identifier or "<missing-id>"] = messages
    return problems


def _evidence_ok(plan: dict[str, Any], key: str, id_key: str) -> bool:
    return not _evidence_diagnostics(plan, key, id_key)


def _semantic_plan(plan: dict[str, Any]) -> dict[str, Any]:
    lots, _ = _actions(plan, "lot_actions", "lot_id")
    events, _ = _actions(plan, "event_actions", "event_id")
    return {
        "schema_version": plan.get("schema_version"),
        "recall_id": plan.get("recall_id"),
        "source_state_sha256": plan.get("source_state_sha256"),
        "scope_revision_id": plan.get("scope_revision_id"),
        "lot_actions": [
            {"lot_id": key, "disposition": lots[key]} for key in sorted(lots)
        ],
        "event_actions": [
            {"event_id": key, "disposition": events[key]} for key in sorted(events)
        ],
        "external_actions_executed": plan.get("external_actions_executed"),
    }


def _plan_digest(plan: dict[str, Any]) -> str:
    return _digest(_semantic_plan(plan))


def _load_plan(name: str) -> dict[str, Any]:
    path = (ROOT / name).resolve()
    if path.parent != ROOT or not path.is_file():
        raise ValueError("plan must be a workspace-root JSON file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan must be an object")
    return value


def _structural_checks(plan: dict[str, Any]) -> dict[str, bool]:
    checkpoint = _checkpoint()
    revision = _scope_revision()
    lots, lot_unique = _actions(plan, "lot_actions", "lot_id")
    events, event_unique = _actions(plan, "event_actions", "event_id")
    return {
        "schema": plan.get("schema_version") == 1,
        "recall_identity": plan.get("recall_id") == checkpoint.get("recall_id"),
        "source_checkpoint": plan.get("source_state_sha256")
        == checkpoint.get("source_state_sha256"),
        "scope_revision": plan.get("scope_revision_id") == revision.get("revision_id"),
        "unique_actions": lot_unique and event_unique,
        "lot_evidence": _evidence_ok(plan, "lot_actions", "lot_id"),
        "event_evidence": _evidence_ok(plan, "event_actions", "event_id"),
        "offline_boundary": plan.get("external_actions_executed") is False,
        "nonempty_actions": bool(lots) and bool(events),
    }


def _validate_plan(
    connection: sqlite3.Connection, plan: dict[str, Any]
) -> tuple[bool, dict[str, bool]]:
    checks = _structural_checks(plan)
    actual_lots, _ = _actions(plan, "lot_actions", "lot_id")
    actual_events, _ = _actions(plan, "event_actions", "event_id")
    checks["lot_coverage_and_scope"] = actual_lots == _scope_decisions(connection)
    checks["event_coverage_and_precedence"] = actual_events == _event_dispositions(
        connection
    )
    return all(checks.values()), checks


def _prior(connection: sqlite3.Connection, recall_id: object) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM recall_transactions WHERE recall_id=?", (recall_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def _replay(
    connection: sqlite3.Connection, plan: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    checkpoint = _checkpoint()
    prior = _prior(connection, checkpoint.get("recall_id"))
    if prior is None:
        return None
    checks = _structural_checks(plan)
    semantic_sha = _plan_digest(plan)
    if all(checks.values()) and semantic_sha == prior["semantic_plan_sha256"]:
        return "idempotent", {
            "status": "idempotent",
            "recall_id": prior["recall_id"],
            "semantic_plan_sha256": semantic_sha,
        }
    return "conflict", {
        "status": "rejected",
        "reason": "semantic_plan_conflict",
        "recall_id": checkpoint.get("recall_id"),
        "committed_semantic_plan_sha256": prior["semantic_plan_sha256"],
        "submitted_semantic_plan_sha256": semantic_sha,
        "checks": checks,
    }


def _apply_business_state(connection: sqlite3.Connection, plan: dict[str, Any]) -> None:
    events, _ = _events()
    event_actions, _ = _actions(plan, "event_actions", "event_id")
    for event_id, disposition in event_actions.items():
        event = events[event_id]
        if disposition == "apply_current":
            connection.execute(
                "UPDATE shipments SET status=?, last_sequence=?, last_event_id=? WHERE shipment_id=?",
                (event["status"], event["sequence"], event_id, event["shipment_id"]),
            )
        connection.execute(
            "INSERT INTO event_ledger VALUES (?,?,?)", (event_id, disposition, NOW)
        )
        if disposition == "quarantine_unknown_shipment":
            connection.execute(
                "INSERT INTO event_quarantine VALUES (?,?)",
                (event_id, "unknown_shipment"),
            )

    lot_actions, _ = _actions(plan, "lot_actions", "lot_id")
    for lot_id, disposition in lot_actions.items():
        status = {
            "affected": "affected_quarantined",
            "pending_trace": "pending_trace_quarantined",
            "unaffected": "cleared_unaffected",
        }[disposition]
        connection.execute(
            "UPDATE lots SET recall_status=? WHERE lot_id=?", (status, lot_id)
        )
        if disposition in {"affected", "pending_trace"}:
            hold = "local_hold" if disposition == "affected" else "trace_hold"
            connection.execute(
                "UPDATE inventory SET quarantined=quarantined+available, available=0, stop_sale_status=? WHERE lot_id=?",
                (hold, lot_id),
            )

    for shipment in _rows(connection, "shipments"):
        decision = lot_actions[shipment["lot_id"]]
        if decision == "pending_trace":
            stop = "pending_trace_hold"
        elif decision == "affected" and shipment["status"] == "delivered":
            stop = "local_channel_recall_draft"
        elif decision == "affected":
            stop = "staged_stop_request"
        else:
            stop = "none"
        connection.execute(
            "UPDATE shipments SET stop_sale_status=? WHERE shipment_id=?",
            (stop, shipment["shipment_id"]),
        )

    channel_states: dict[str, list[str]] = defaultdict(list)
    for shipment in _rows(connection, "shipments"):
        channel_states[shipment["channel_id"]].append(lot_actions[shipment["lot_id"]])
    for channel in _rows(connection, "channels"):
        decisions = set(channel_states.get(channel["channel_id"], []))
        if "affected" in decisions:
            draft = (
                "draft_ready"
                if channel["authority_status"] == "verified"
                else "pending_approval"
            )
        elif "pending_trace" in decisions:
            draft = "trace_hold"
        else:
            draft = "none"
        connection.execute(
            "UPDATE channels SET local_draft_status=? WHERE channel_id=?",
            (draft, channel["channel_id"]),
        )


def inspect() -> int:
    with _connect() as connection:
        value = {
            "checkpoint": _checkpoint(),
            "controlling_scope": _scope_revision(),
            "event_delivery_counts": _events()[1],
            "state": _snapshot(connection),
        }
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def query(sql: str) -> int:
    if not sql.lstrip().casefold().startswith("select"):
        print("query accepts SELECT only")
        return 2
    with _connect() as connection:
        print(json.dumps([dict(row) for row in connection.execute(sql)], indent=2))
    return 0


def preview(name: str) -> int:
    plan = _load_plan(name)
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        replay = _replay(connection, plan)
        if replay is not None:
            kind, result = replay
            result["projected"] = (
                _snapshot(connection) if kind == "idempotent" else None
            )
            connection.rollback()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if kind == "idempotent" else 2
        valid, checks = _validate_plan(connection, plan)
        current_sha = _digest(_snapshot(connection, STATE_TABLES))
        checks["initial_state_matches_checkpoint"] = current_sha == _checkpoint().get(
            "source_state_sha256"
        )
        if valid and checks["initial_state_matches_checkpoint"]:
            _apply_business_state(connection, plan)
        result = {
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "missing_evidence_by_lot": _evidence_diagnostics(
                plan, "lot_actions", "lot_id"
            ),
            "missing_evidence_by_event": _evidence_diagnostics(
                plan, "event_actions", "event_id"
            ),
            "semantic_plan_sha256": _plan_digest(plan),
            "projected": _snapshot(connection) if all(checks.values()) else None,
        }
        connection.rollback()
    finally:
        connection.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def apply(name: str) -> int:
    plan = _load_plan(name)
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        replay = _replay(connection, plan)
        if replay is not None:
            kind, result = replay
            connection.rollback()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if kind == "idempotent" else 2
        valid, checks = _validate_plan(connection, plan)
        checkpoint = _checkpoint()
        checks["initial_state_matches_checkpoint"] = _digest(
            _snapshot(connection, STATE_TABLES)
        ) == checkpoint.get("source_state_sha256")
        if not all(checks.values()):
            connection.rollback()
            print(
                json.dumps(
                    {"status": "rejected", "checks": checks}, indent=2, sort_keys=True
                )
            )
            return 2
        _apply_business_state(connection, plan)
        semantic_sha = _plan_digest(plan)
        count = len(plan["lot_actions"]) + len(plan["event_actions"])
        connection.execute(
            "INSERT INTO recall_transactions VALUES (?,?,?,?,?)",
            (
                checkpoint["recall_id"],
                checkpoint["source_state_sha256"],
                semantic_sha,
                count,
                NOW,
            ),
        )
        connection.execute(
            "UPDATE recall_journal SET phase='committed', source_state_sha256=?, semantic_plan_sha256=?, committed_at=? WHERE recall_id=?",
            (
                checkpoint["source_state_sha256"],
                semantic_sha,
                NOW,
                checkpoint["recall_id"],
            ),
        )
        connection.commit()
    finally:
        connection.close()
    print(
        json.dumps(
            {
                "status": "applied",
                "recall_id": checkpoint["recall_id"],
                "semantic_plan_sha256": semantic_sha,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _projected(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    with _baseline() as connection:
        _apply_business_state(connection, plan)
        return _snapshot(
            connection,
            (
                "lots",
                "inventory",
                "channels",
                "shipments",
                "event_ledger",
                "event_quarantine",
            ),
        )


def verify(name: str) -> int:
    plan = _load_plan(name)
    semantic_sha = _plan_digest(plan)
    with _connect() as connection:
        current = _snapshot(connection)
        projected = _projected(plan)
        transactions = current["recall_transactions"]
        journals = current["recall_journal"]
        checkpoint = _checkpoint()
        actual_projection = {table: current[table] for table in projected}
        conservation = all(
            row["available"] >= 0
            and row["quarantined"] >= 0
            and row["available"] + row["quarantined"] == row["on_hand"]
            for row in current["inventory"]
        )
        checks = {
            "terminal_state_matches_projection": actual_projection == projected,
            "inventory_nonnegative_and_conserved": conservation,
            "single_recall_transaction": len(transactions) == 1,
            "committed_journal": len(journals) == 1
            and journals[0]["phase"] == "committed",
            "recovery_identity_bound": bool(transactions)
            and transactions[0]["recall_id"] == checkpoint["recall_id"],
            "source_checkpoint_bound": bool(transactions)
            and transactions[0]["source_state_sha256"]
            == checkpoint["source_state_sha256"],
            "semantic_plan_bound": bool(transactions)
            and transactions[0]["semantic_plan_sha256"] == semantic_sha,
            "prepared_event_preserved": len(journals) == 1
            and journals[0]["prepared_action_key"] == checkpoint["prepared_action_key"],
        }
        receipt = {
            "tool": "recallctl/1",
            "status": "pass" if all(checks.values()) else "fail",
            "recall_id": checkpoint["recall_id"],
            "scope_revision_id": _scope_revision()["revision_id"],
            "source_state_sha256": checkpoint["source_state_sha256"],
            "semantic_plan_sha256": semantic_sha,
            "logical_state_sha256": _digest(current),
            "checks": checks,
            "external_actions_executed": False,
        }
    (ROOT / "recall_verification.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 2


def stage(plan_name: str) -> int:
    plan = _load_plan(plan_name)
    verification_path = ROOT / "recall_verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    with _connect() as connection:
        current = _snapshot(connection)
    unsigned = {
        "receipt_type": "local_recall_recovery_stage",
        "recall_id": _checkpoint()["recall_id"],
        "phase": "staged_pending_external_approval",
        "source_state_sha256": _checkpoint()["source_state_sha256"],
        "semantic_plan_sha256": _plan_digest(plan),
        "logical_state_sha256": _digest(current),
        "verification_sha256": _sha(verification_path),
        "external_actions_executed": False,
    }
    valid = (
        verification.get("status") == "pass"
        and verification.get("semantic_plan_sha256") == unsigned["semantic_plan_sha256"]
        and verification.get("logical_state_sha256") == unsigned["logical_state_sha256"]
    )
    if not valid:
        print(
            json.dumps(
                {"status": "rejected", "reason": "verification_not_bound"}, indent=2
            )
        )
        return 2
    receipt = dict(unsigned)
    receipt["stage_token"] = _digest(unsigned)
    target = ROOT / "recall_stage_receipt.json"
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    if target.exists():
        if target.read_bytes() == payload:
            print(
                json.dumps(
                    {"status": "idempotent", **receipt}, indent=2, sort_keys=True
                )
            )
            return 0
        print(
            json.dumps(
                {"status": "rejected", "reason": "stage_receipt_conflict"}, indent=2
            )
        )
        return 2
    target.write_bytes(payload)
    print(json.dumps({"status": "staged", **receipt}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline product-recall recovery controller"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("sql")
    for command in ("preview", "apply", "verify", "stage"):
        child = sub.add_parser(command)
        child.add_argument("plan", nargs="?", default="recall_plan.json")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect()
        if args.command == "query":
            return query(args.sql)
        if args.command == "preview":
            return preview(args.plan)
        if args.command == "apply":
            return apply(args.plan)
        if args.command == "verify":
            return verify(args.plan)
        return stage(args.plan)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(
            json.dumps(
                {"status": "error", "error": f"{type(exc).__name__}: {exc}"}, indent=2
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
