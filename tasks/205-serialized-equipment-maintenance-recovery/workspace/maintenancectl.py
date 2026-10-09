#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/maintenance.db"
POLICY = ROOT / "policy/maintenance_policy.json"
MANIFEST = ROOT / "policy/source_manifest.json"
EVENTS = ROOT / "evidence/work_order_events.jsonl"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "assignments",
    "event_dispositions", "totals", "external_actions_executed",
}
ASSIGNMENT_FIELDS = {
    "work_order_id", "asset_serial", "survivor_work_order_id", "disposition",
    "final_state", "symptom_codes", "selected_bom_revision",
    "required_part_number", "allocated_part_lot", "technician_id",
    "qualification_code", "instrument_id", "next_local_action", "evidence_refs",
}
EVENT_FIELDS = {
    "delivery_id", "event_id", "source_work_order_id", "effective_work_order_id",
    "sequence", "disposition",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def normalized(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    assignments = []
    if isinstance(plan.get("assignments"), list):
        for raw in plan["assignments"]:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            for field in ("symptom_codes", "evidence_refs"):
                if isinstance(row.get(field), list):
                    row[field] = sorted(row[field])
            assignments.append(row)
    events = [dict(row) for row in plan.get("event_dispositions", []) if isinstance(row, dict)]
    result["assignments"] = sorted(assignments, key=lambda row: str(row.get("work_order_id")))
    result["event_dispositions"] = sorted(events, key=lambda row: str(row.get("delivery_id")))
    return result


def source_files_valid() -> tuple[bool, list[str]]:
    manifest = load_json(MANIFEST)
    failures = []
    for locator, expected in manifest.get("files", {}).items():
        path = ROOT / locator
        try:
            if digest(path.read_bytes()) != expected:
                failures.append(locator)
        except OSError:
            failures.append(locator)
    return not failures, failures


def database_snapshot() -> dict[str, list[dict[str, Any]]]:
    with sqlite3.connect(DB) as connection:
        return {
            "assets": rows(connection, "assets", "asset_serial"),
            "work_orders": rows(connection, "work_orders", "work_order_id"),
            "bom_effectivity": rows(connection, "bom_effectivity", "model, component, effective_from"),
            "technician_qualifications": rows(connection, "technician_qualifications", "technician_id, model, skill_code"),
            "instruments": rows(connection, "instruments", "instrument_id"),
            "part_lots": rows(connection, "part_lots", "lot_id"),
            "recovery_journal": rows(connection, "recovery_journal", "journal_id"),
            "system_state": rows(connection, "system_state", "key"),
        }


def restored_baseline(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    baseline = {key: [dict(row) for row in value] for key, value in snapshot.items()}
    for journal in baseline["recovery_journal"]:
        before = json.loads(journal["before_image_json"])
        for table, keyed in before.items():
            key_name = "work_order_id" if table == "work_orders" else "lot_id"
            by_key = {row[key_name]: row for row in baseline[table]}
            for key, fields in keyed.items():
                by_key[key].update(fields)
    return baseline


def read_deliveries() -> list[dict[str, Any]]:
    deliveries = []
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("event delivery must be an object")
        deliveries.append(value)
    return deliveries


def validation_report(candidate: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Validate candidate fields while keeping the completed answer non-exportable."""
    valid, failures = source_files_valid()
    if not valid:
        raise ValueError(f"protected source hash mismatch: {failures}")
    policy = load_json(POLICY)
    snapshot = database_snapshot()
    baseline = restored_baseline(snapshot)
    assets = {row["asset_serial"]: row for row in baseline["assets"]}
    orders = {row["work_order_id"]: row for row in baseline["work_orders"]}
    lots = {row["lot_id"]: dict(row) for row in baseline["part_lots"]}

    survivor: dict[str, str] = {}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for order in orders.values():
        if order["status"] == "completed":
            survivor[order["work_order_id"]] = order["work_order_id"]
            continue
        groups.setdefault((order["asset_serial"], order["alarm_group"]), []).append(order)
    for group in groups.values():
        chosen = min(group, key=lambda row: (row["opened_at"], row["work_order_id"]))["work_order_id"]
        for order in group:
            survivor[order["work_order_id"]] = chosen

    deliveries = read_deliveries()
    seen: dict[str, bytes] = {}
    accepted: dict[str, list[dict[str, Any]]] = {}
    dispositions = []
    for delivery in deliveries:
        source_id = str(delivery["work_order_id"])
        event_id = str(delivery["event_id"])
        event_body = {key: value for key, value in delivery.items() if key != "delivery_id"}
        fingerprint = canonical(event_body)
        effective = survivor.get(source_id)
        if event_id in seen:
            if seen[event_id] != fingerprint:
                raise ValueError(f"conflicting duplicate event: {event_id}")
            disposition = "ignored_duplicate_event"
        elif source_id not in orders:
            seen[event_id] = fingerprint
            disposition = "ignored_unknown_work_order"
            effective = None
        elif orders[source_id]["status"] == "completed":
            seen[event_id] = fingerprint
            disposition = "ignored_completed_boundary"
        else:
            seen[event_id] = fingerprint
            disposition = "accepted_routed_to_survivor" if effective != source_id else "accepted"
            accepted.setdefault(str(effective), []).append(delivery)
        dispositions.append({
            "delivery_id": delivery["delivery_id"],
            "event_id": event_id,
            "source_work_order_id": source_id,
            "effective_work_order_id": effective,
            "sequence": delivery["sequence"],
            "disposition": disposition,
        })
    for group in accepted.values():
        group.sort(key=lambda row: (int(row["sequence"]), str(row["event_id"])))

    source_payload = {
        "manifest": load_json(MANIFEST)["files"],
        "assets": baseline["assets"],
        "work_orders": baseline["work_orders"],
        "bom_effectivity": baseline["bom_effectivity"],
        "technician_qualifications": baseline["technician_qualifications"],
        "instruments": baseline["instruments"],
        "part_lots": baseline["part_lots"],
        "source_revision": next(row["value"] for row in baseline["system_state"] if row["key"] == "source_revision"),
    }
    checkpoint = digest(canonical(source_payload))
    final_orders = {key: dict(value) for key, value in orders.items()}
    final_lots = {key: dict(value) for key, value in lots.items()}
    assignments = []
    totals = {
        "ready_dispatch_count": 0,
        "held_count": 0,
        "merged_count": 0,
        "preserved_completed_count": 0,
        "allocated_part_count": 0,
    }
    as_of = policy["as_of"]

    for order_id in sorted(orders):
        order = orders[order_id]
        chosen = survivor[order_id]
        refs = {f"state/maintenance.db#work_orders:{order_id}"}
        if order["status"] == "completed":
            totals["preserved_completed_count"] += 1
            assignments.append({
                "work_order_id": order_id, "asset_serial": order["asset_serial"],
                "survivor_work_order_id": order_id,
                "disposition": "completed_execution_preserved", "final_state": "completed",
                "symptom_codes": [], "selected_bom_revision": order["selected_bom_revision"],
                "required_part_number": order["required_part_number"],
                "allocated_part_lot": order["allocated_part_lot"],
                "technician_id": order["technician_id"],
                "qualification_code": order["qualification_code"],
                "instrument_id": order["instrument_id"], "next_local_action": "none",
                "evidence_refs": sorted(refs | {"policy/maintenance_policy.json#completed_execution_boundary"}),
            })
            continue
        if chosen != order_id:
            totals["merged_count"] += 1
            assignments.append({
                "work_order_id": order_id, "asset_serial": order["asset_serial"],
                "survivor_work_order_id": chosen, "disposition": "merged_into_survivor",
                "final_state": "merged", "symptom_codes": [],
                "selected_bom_revision": None, "required_part_number": None,
                "allocated_part_lot": None, "technician_id": None,
                "qualification_code": None, "instrument_id": None,
                "next_local_action": "none",
                "evidence_refs": sorted(refs | {f"state/maintenance.db#work_orders:{chosen}", "policy/maintenance_policy.json#duplicate_survivor_rule"}),
            })
            final_orders[order_id].update(
                status="merged", survivor_work_order_id=chosen, selected_bom_revision=None,
                required_part_number=None, allocated_part_lot=None, technician_id=None,
                qualification_code=None, instrument_id=None, version=int(order["version"]) + 1,
            )
            continue

        event_rows = accepted.get(order_id, [])
        symptoms = sorted({str(row["payload"]["symptom_code"]) for row in event_rows if row["event_type"] == "condition_observation"})
        refs.update(f"evidence/work_order_events.jsonl#{row['event_id']}" for row in event_rows)
        rules = [policy["symptom_rules"].get(code) for code in symptoms]
        rules = [rule for rule in rules if isinstance(rule, dict)]
        component = rules[0]["component"] if rules and all(rule["component"] == rules[0]["component"] for rule in rules) else None
        skill = rules[0]["skill_code"] if rules and all(rule["skill_code"] == rules[0]["skill_code"] for rule in rules) else None
        measurement = rules[0]["measurement_kind"] if rules and all(rule["measurement_kind"] == rules[0]["measurement_kind"] for rule in rules) else None
        model = assets[order["asset_serial"]]["model"]
        boms = [row for row in baseline["bom_effectivity"] if row["model"] == model and row["component"] == component and row["effective_from"] <= order["opened_at"] and (row["effective_to"] is None or order["opened_at"] < row["effective_to"])]
        bom = min(boms, key=lambda row: (row["effective_from"], row["bom_revision"]), default=None)
        techs = [row for row in baseline["technician_qualifications"] if row["model"] == model and row["skill_code"] == skill and row["valid_from"] <= as_of <= row["valid_until"]]
        tech = min(techs, key=lambda row: row["technician_id"], default=None)
        instruments = [row for row in baseline["instruments"] if row["measurement_kind"] == measurement and row["status"] == "active" and row["calibration_valid_until"] >= as_of]
        instrument = min(instruments, key=lambda row: row["instrument_id"], default=None)
        eligible_lots = [row for row in final_lots.values() if bom and row["part_number"] == bom["part_number"] and row["status"] == "released" and int(row["quantity"]) > 0]
        lot = min(eligible_lots, key=lambda row: row["lot_id"], default=None)
        if not symptoms or len(rules) != len(symptoms) or component is None:
            disposition, state, action = "hold_policy_conflict", "held", "resolve_symptom_policy"
        elif bom is None:
            disposition, state, action = "hold_bom_effectivity", "held", "resolve_bom_effectivity"
        elif tech is None:
            disposition, state, action = "hold_technician_qualification", "held", "obtain_qualified_technician"
        elif instrument is None:
            disposition, state, action = "hold_calibration", "held", "obtain_calibrated_instrument"
        elif lot is None:
            disposition, state, action = "hold_part_availability", "held", "release_or_replenish_effective_part"
        else:
            disposition, state, action = "ready_local_dispatch", "ready_local_dispatch", "stage_offline_dispatch_packet"
        allocated = lot["lot_id"] if disposition == "ready_local_dispatch" else None
        if allocated:
            final_lots[allocated]["quantity"] = int(final_lots[allocated]["quantity"]) - 1
            totals["ready_dispatch_count"] += 1
            totals["allocated_part_count"] += 1
        else:
            totals["held_count"] += 1
        if bom:
            refs.add(f"state/maintenance.db#bom_effectivity:{model}:{component}:{bom['bom_revision']}")
        if tech:
            refs.add(f"state/maintenance.db#technician_qualifications:{tech['technician_id']}:{model}:{skill}")
        if instrument:
            refs.add(f"state/maintenance.db#instruments:{instrument['instrument_id']}")
        if allocated:
            refs.add(f"state/maintenance.db#part_lots:{allocated}")
        assignments.append({
            "work_order_id": order_id, "asset_serial": order["asset_serial"],
            "survivor_work_order_id": order_id, "disposition": disposition,
            "final_state": state, "symptom_codes": symptoms,
            "selected_bom_revision": bom["bom_revision"] if bom else None,
            "required_part_number": bom["part_number"] if bom else None,
            "allocated_part_lot": allocated,
            "technician_id": tech["technician_id"] if tech else None,
            "qualification_code": skill if tech else None,
            "instrument_id": instrument["instrument_id"] if instrument else None,
            "next_local_action": action, "evidence_refs": sorted(refs),
        })
        final_orders[order_id].update(
            status=state, survivor_work_order_id=order_id,
            selected_bom_revision=bom["bom_revision"] if bom else None,
            required_part_number=bom["part_number"] if bom else None,
            allocated_part_lot=allocated, technician_id=tech["technician_id"] if tech else None,
            qualification_code=skill if tech else None,
            instrument_id=instrument["instrument_id"] if instrument else None,
            version=int(order["version"]) + 1,
        )

    target = normalized({
        "schema_version": 1, "recovery_id": policy["recovery_id"],
        "source_checkpoint": checkpoint, "assignments": assignments,
        "event_dispositions": dispositions, "totals": totals,
        "external_actions_executed": False,
    })
    candidate = normalized(candidate)
    problems: list[dict[str, str]] = []
    schema_ok = (
        set(candidate) == PLAN_FIELDS
        and isinstance(candidate.get("assignments"), list)
        and all(isinstance(row, dict) and set(row) == ASSIGNMENT_FIELDS for row in candidate.get("assignments", []))
        and isinstance(candidate.get("event_dispositions"), list)
        and all(isinstance(row, dict) and set(row) == EVENT_FIELDS for row in candidate.get("event_dispositions", []))
    )
    if not schema_ok:
        problems.append({"scope": "plan", "id": "schema", "field": "fields", "evidence": "published maintenance plan schema"})
    submitted_assignments = {
        str(row.get("work_order_id")): row
        for row in candidate.get("assignments", [])
        if isinstance(row, dict)
    }
    required_assignments = {row["work_order_id"]: row for row in target["assignments"]}
    if set(submitted_assignments) != set(required_assignments):
        problems.append({"scope": "assignments", "id": "set", "field": "work_order_ids", "evidence": "restored work-order baseline"})
    for work_order_id, required in required_assignments.items():
        submitted = submitted_assignments.get(work_order_id)
        for field in ASSIGNMENT_FIELDS:
            if not isinstance(submitted, dict) or submitted.get(field) != required[field]:
                problems.append({"scope": "work_order", "id": work_order_id, "field": field, "evidence": "events, incident-time BOM, qualification, calibration, and released stock"})
    submitted_events = {
        str(row.get("delivery_id")): row
        for row in candidate.get("event_dispositions", [])
        if isinstance(row, dict)
    }
    required_events = {row["delivery_id"]: row for row in target["event_dispositions"]}
    if set(submitted_events) != set(required_events):
        problems.append({"scope": "events", "id": "set", "field": "delivery_ids", "evidence": "work-order event deliveries"})
    for delivery_id, required in required_events.items():
        submitted = submitted_events.get(delivery_id)
        for field in EVENT_FIELDS:
            if not isinstance(submitted, dict) or submitted.get(field) != required[field]:
                problems.append({"scope": "event", "id": delivery_id, "field": field, "evidence": "event identity, duplicate, sequence, and survivor routing"})
    for field in ("schema_version", "recovery_id", "source_checkpoint", "external_actions_executed", "totals"):
        if candidate.get(field) != target[field]:
            category = "protected sources and restored baseline" if field == "source_checkpoint" else "published policy and independently recomputed totals"
            problems.append({"scope": "plan", "id": str(policy["recovery_id"]), "field": field, "evidence": category})
    return problems, {"baseline": baseline, "checkpoint": checkpoint}


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    raw = load_json(path)
    candidate = normalized(raw)
    problems, facts = validation_report(candidate)
    if problems:
        raise ValueError(json.dumps({"status": "invalid", "discrepancies": problems}, sort_keys=True))
    semantic = digest(canonical(candidate))
    return candidate, facts, semantic


def logical_database_digest(connection: sqlite3.Connection) -> str:
    payload = {
        "work_orders": rows(connection, "work_orders", "work_order_id"),
        "part_lots": rows(connection, "part_lots", "lot_id"),
        "event_receipts": rows(connection, "event_receipts", "delivery_id"),
        "recovery_runs": rows(connection, "recovery_runs", "recovery_id"),
        "recovery_journal": rows(connection, "recovery_journal", "journal_id"),
        "system_state": rows(connection, "system_state", "key"),
    }
    return digest(canonical(payload))


def command_inspect() -> None:
    valid, failures = source_files_valid()
    with sqlite3.connect(DB) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables if table != "sqlite_sequence"}
        journal = rows(connection, "recovery_journal", "journal_id")
    print(json.dumps({"source_hashes_valid": valid, "source_hash_failures": failures, "tables": counts, "journal": journal}, indent=2, sort_keys=True))


def command_preview(path: Path) -> None:
    plan = normalized(load_json(path))
    problems, _ = validation_report(plan)
    semantic = digest(canonical(plan))
    report = {
        "status": "valid" if not problems else "invalid",
        "recovery_id": plan.get("recovery_id"),
        "source_checkpoint": plan.get("source_checkpoint"),
        "semantic_plan_digest": semantic,
        "assignment_count": len(plan.get("assignments", [])),
        "event_delivery_count": len(plan.get("event_dispositions", [])),
        "database_mutation": "pending", "external_actions_executed": False,
        "discrepancies": problems,
    }
    write_json(ROOT / ".maintenance_preview.json", report)
    print(json.dumps(report, sort_keys=True))
    if problems:
        raise ValueError("preview rejected")


def command_apply(path: Path) -> None:
    plan, facts, semantic = validate_plan(path)
    with sqlite3.connect(DB) as connection:
        existing = connection.execute("SELECT semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if existing:
            if existing[0] != semantic:
                raise ValueError("conflict: recovery identity already committed with different semantics")
            print(json.dumps({"status": "idempotent"}))
            return
        connection.execute("BEGIN IMMEDIATE")
        try:
            baseline = facts["baseline"]
            for journal in baseline["recovery_journal"]:
                before = json.loads(journal["before_image_json"])
                for work_order_id, fields in before.get("work_orders", {}).items():
                    for field, value in fields.items():
                        connection.execute(f"UPDATE work_orders SET {field}=? WHERE work_order_id=?", (value, work_order_id))
                for lot_id, fields in before.get("part_lots", {}).items():
                    for field, value in fields.items():
                        connection.execute(f"UPDATE part_lots SET {field}=? WHERE lot_id=?", (value, lot_id))
                connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal["journal_id"],))
            original_orders = {row["work_order_id"]: row for row in baseline["work_orders"]}
            for assignment in plan["assignments"]:
                work_order_id = assignment["work_order_id"]
                original = original_orders[work_order_id]
                final = dict(original)
                if original["status"] != "completed":
                    final.update(
                        status=assignment["final_state"],
                        survivor_work_order_id=assignment["survivor_work_order_id"],
                        selected_bom_revision=assignment["selected_bom_revision"],
                        required_part_number=assignment["required_part_number"],
                        allocated_part_lot=assignment["allocated_part_lot"],
                        technician_id=assignment["technician_id"],
                        qualification_code=assignment["qualification_code"],
                        instrument_id=assignment["instrument_id"],
                        version=int(original["version"]) + 1,
                    )
                columns = ["status", "survivor_work_order_id", "selected_bom_revision", "required_part_number", "allocated_part_lot", "technician_id", "qualification_code", "instrument_id", "version"]
                connection.execute(
                    "UPDATE work_orders SET " + ",".join(f"{field}=?" for field in columns) + " WHERE work_order_id=?",
                    tuple(final[field] for field in columns) + (work_order_id,),
                )
            lot_quantities = {row["lot_id"]: int(row["quantity"]) for row in baseline["part_lots"]}
            for assignment in plan["assignments"]:
                lot_id = assignment.get("allocated_part_lot")
                if assignment.get("disposition") == "ready_local_dispatch" and lot_id:
                    lot_quantities[str(lot_id)] -= 1
            for lot_id, quantity in lot_quantities.items():
                connection.execute("UPDATE part_lots SET quantity=? WHERE lot_id=?", (quantity, lot_id))
            connection.execute("DELETE FROM event_receipts")
            for row in plan["event_dispositions"]:
                connection.execute(
                    "INSERT INTO event_receipts VALUES (?,?,?,?,?,?)",
                    (row["delivery_id"], row["event_id"], row["source_work_order_id"], row["effective_work_order_id"], row["sequence"], row["disposition"]),
                )
            current_revision = int(connection.execute("SELECT value FROM system_state WHERE key='revision'").fetchone()[0])
            connection.execute("UPDATE system_state SET value=? WHERE key='revision'", (str(current_revision + 1),))
            connection.execute(
                "INSERT INTO recovery_runs(recovery_id, source_checkpoint, semantic_plan_digest, committed_revision, external_actions_executed) VALUES (?,?,?,?,0)",
                (plan["recovery_id"], plan["source_checkpoint"], semantic, current_revision + 1),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    print(json.dumps({"status": "applied", "recovery_id": plan["recovery_id"]}, sort_keys=True))


def committed_closure(plan: dict[str, Any], semantic: str) -> dict[str, Any]:
    with sqlite3.connect(DB) as connection:
        run = connection.execute("SELECT source_checkpoint, semantic_plan_digest, external_actions_executed FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if run != (plan["source_checkpoint"], semantic, 0):
            raise ValueError("matching committed recovery run not found")
        logical = logical_database_digest(connection)
        journal_ok = all(row[0] == 1 for row in connection.execute("SELECT restored FROM recovery_journal"))
    return {"logical_database_digest": logical, "journal_restored": journal_ok}


def command_verify(path: Path) -> None:
    plan, _, semantic = validate_plan(path)
    closure = committed_closure(plan, semantic)
    result = {
        "status": "verified", "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": semantic,
        **closure, "allocated_part_count": plan["totals"]["allocated_part_count"],
        "executed_boundaries_preserved": True, "external_actions_executed": False,
    }
    write_json(ROOT / "state/verification.json", result)
    print(json.dumps({"status": "verified"}))


def stage_payloads(plan: dict[str, Any], semantic: str, logical: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ready = [row for row in plan["assignments"] if row["disposition"] == "ready_local_dispatch"]
    held = [row for row in plan["assignments"] if row["final_state"] == "held"]
    bundle = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "dispatch_items": ready, "hold_items": held,
        "external_actions_executed": False,
    }
    bundle_hash = digest(canonical(bundle))
    manifest = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "semantic_plan_digest": semantic, "logical_database_digest": logical,
        "bundle_sha256": bundle_hash, "dispatch_item_count": len(ready),
        "hold_item_count": len(held), "external_actions_executed": False,
    }
    receipt = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_digest": semantic, "logical_database_digest": logical,
        "bundle_sha256": bundle_hash,
        "receipt_token": digest(canonical({"recovery_id": plan["recovery_id"], "bundle_sha256": bundle_hash, "logical_database_digest": logical})),
        "receipt_type": "local_staging_only", "external_actions_executed": False,
    }
    return bundle, manifest, receipt


def command_stage(path: Path) -> None:
    plan, _, semantic = validate_plan(path)
    closure = committed_closure(plan, semantic)
    bundle, manifest, receipt = stage_payloads(plan, semantic, closure["logical_database_digest"])
    write_json(ROOT / "staging/service_dispatch_bundle.json", bundle)
    write_json(ROOT / "staging/dispatch_manifest.json", manifest)
    write_json(ROOT / "state/recovery_receipt.json", receipt)
    print(json.dumps({"status": "staged", "receipt_type": "local_staging_only"}))


def command_replay(path: Path) -> None:
    plan, _, semantic = validate_plan(path)
    closure = committed_closure(plan, semantic)
    bundle, manifest, receipt = stage_payloads(plan, semantic, closure["logical_database_digest"])
    expected = {
        ROOT / "staging/service_dispatch_bundle.json": bundle,
        ROOT / "staging/dispatch_manifest.json": manifest,
        ROOT / "state/recovery_receipt.json": receipt,
    }
    if any(load_json(path_) != value for path_, value in expected.items()):
        raise ValueError("staged artifacts do not close under committed semantics")
    write_json(ROOT / "state/replay_report.json", {
        "status": "idempotent", "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_digest": semantic, "authoritative_bytes_unchanged": True,
        "transaction_count": 1, "external_actions_executed": False,
    })
    print(json.dumps({"status": "idempotent", "authoritative_bytes_unchanged": True}))


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded local maintenance recovery controller")
    parser.add_argument("command", choices=("inspect", "preview", "apply", "verify", "stage", "replay"))
    parser.add_argument("plan", nargs="?", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            command_inspect()
        else:
            if args.plan is None:
                raise ValueError("plan path required")
            path = args.plan if args.plan.is_absolute() else ROOT / args.plan
            {"preview": command_preview, "apply": command_apply, "verify": command_verify, "stage": command_stage, "replay": command_replay}[args.command](path)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
