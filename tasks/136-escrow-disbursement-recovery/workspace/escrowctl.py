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
DB = ROOT / "state/escrow.db"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "closing_decisions",
    "event_dispositions", "totals", "external_actions_executed",
}
DECISION_FIELDS = {
    "closing_id", "property_id", "disposition", "final_state", "wire_amount_cents",
    "authorized_allocations_cents", "holdback_cents", "next_local_action",
    "instruction_ids", "evidence_refs",
}
EVENT_FIELDS = {"delivery_id", "event_id", "closing_id", "source_sequence", "disposition"}
TOTAL_FIELDS = {
    "received_wire_cents", "locally_stageable_cents", "preserved_disbursed_cents",
    "retained_holdback_cents",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain one JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def source_manifest() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source_manifest.json is malformed")
    changed = []
    for locator, expected in files.items():
        try:
            actual = digest((ROOT / str(locator)).read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def load_events() -> list[dict[str, Any]]:
    result = []
    try:
        lines = (ROOT / "evidence/settlement_events.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read settlement events: {exc}") from exc
    for number, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed settlement event line {number}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"settlement event line {number} is not an object")
        result.append(item)
    return result


def baseline_state(connection: sqlite3.Connection, recovery_id: str) -> dict[str, Any]:
    closings = {row["closing_id"]: row for row in rows(connection, "closings", "closing_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
    journal = rows(connection, "recovery_journal", "journal_id")
    current = runs.get(recovery_id)
    if current and current["status"] in {"committed", "staged_local_bundle"}:
        for row in journal:
            if row["recovery_id"] == recovery_id:
                closings[row["closing_id"]] = json.loads(row["before_json"])
    for row in journal:
        run = runs.get(row["recovery_id"])
        if run and run["status"] == "interrupted" and not row["restored"]:
            closings[row["closing_id"]] = json.loads(row["before_json"])
    system = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
    return {
        "closings": [closings[key] for key in sorted(closings)],
        "payees": rows(connection, "payees", "payee_id"),
        "instructions": rows(connection, "instructions", "instruction_id"),
        "documents": rows(connection, "documents", "document_id"),
        "source_revision": int(system["source_revision"]),
    }


def event_facts(
    deliveries: list[dict[str, Any]], closings: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    seen: set[str] = set()
    dispositions = []
    accepted: dict[str, list[dict[str, Any]]] = {}
    for delivery in deliveries:
        event_id = str(delivery.get("event_id", ""))
        closing_id = str(delivery.get("closing_id", ""))
        event_type = str(delivery.get("event_type", ""))
        if event_id in seen:
            status = "duplicate_delivery_ignored"
        else:
            seen.add(event_id)
            if closing_id not in closings:
                status = "unknown_closing_ignored"
            elif closings[closing_id]["disbursed_at"] and event_type != "holdback_release_authorized":
                status = "irreversible_disbursement_ignored"
            else:
                status = "applied"
                accepted.setdefault(closing_id, []).append(delivery)
        dispositions.append({
            "delivery_id": str(delivery.get("delivery_id", "")),
            "event_id": event_id,
            "closing_id": closing_id,
            "source_sequence": int(delivery.get("source_sequence", -1)),
            "disposition": status,
        })
    for values in accepted.values():
        values.sort(key=lambda row: (int(row["source_sequence"]), str(row["event_id"])))
    return dispositions, accepted


def document_valid(document: dict[str, Any]) -> bool:
    try:
        return bool(document["signed"]) and digest((ROOT / document["local_path"]).read_bytes()) == document["sha256"]
    except OSError:
        return False


def validation_report(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate a submitted plan without exporting the completed answer."""
    policy = load_json(ROOT / "policy/escrow_policy.json")
    manifest, source_bundle_hash = source_manifest()
    deliveries = load_events()
    with sqlite3.connect(DB) as connection:
        baseline = baseline_state(connection, str(policy["recovery_id"]))
    closings = {row["closing_id"]: row for row in baseline["closings"]}
    payees = {row["payee_id"]: row for row in baseline["payees"]}
    instructions: dict[str, list[dict[str, Any]]] = {}
    for row in baseline["instructions"]:
        instructions.setdefault(row["closing_id"], []).append(row)
    documents: dict[str, list[dict[str, Any]]] = {}
    for row in baseline["documents"]:
        documents.setdefault(row["closing_id"], []).append(row)
    event_rows, accepted = event_facts(deliveries, closings)

    decisions = []
    final_closings: dict[str, dict[str, Any]] = {}
    received_wire = stageable = preserved = retained = 0
    for closing_id in sorted(closings):
        original = closings[closing_id]
        closing_events = accepted.get(closing_id, [])
        by_type: dict[str, list[dict[str, Any]]] = {}
        refs = {f"state/escrow.db#closings:{closing_id}", "policy/escrow_policy.json#evidence_rules"}
        for event in closing_events:
            by_type.setdefault(str(event["event_type"]), []).append(event)
            refs.add(f"evidence/settlement_events.jsonl#{event['event_id']}")
        closing_instructions = sorted(instructions.get(closing_id, []), key=lambda row: row["instruction_id"])
        instruction_ids = [row["instruction_id"] for row in closing_instructions]
        allocation_total = sum(int(row["amount_cents"]) for row in closing_instructions if row["status"] == "active")
        holdback = int(original["retained_holdback_cents"])
        retained += holdback

        wire_events = by_type.get("wire_received", [])
        wire_amount = int(wire_events[-1]["payload"]["amount_cents"]) if wire_events else 0
        received_wire += wire_amount
        auth_events = by_type.get("closing_authorized", [])
        recording_events = by_type.get("recording_confirmed", [])
        closing_docs = [row for row in documents.get(closing_id, []) if row["document_type"] == "closing_authorization"]
        auth_doc_ids = {str(row["payload"].get("document_id")) for row in auth_events}
        closing_auth_ok = any(row["document_id"] in auth_doc_ids and document_valid(row) for row in closing_docs)
        for row in closing_docs:
            if row["document_id"] in auth_doc_ids:
                refs.add(f"{row['local_path']}#{row['document_id']}")

        payees_ok = True
        instruction_docs_ok = True
        for instruction in closing_instructions:
            payee = payees.get(instruction["payee_id"], {})
            payees_ok &= payee.get("verification_status") == "verified"
            candidates = [
                row for row in documents.get(closing_id, [])
                if row["document_type"] == "instruction_authorization"
                and row["instruction_id"] == instruction["instruction_id"]
            ]
            valid = [
                row for row in candidates
                if document_valid(row)
                and row["payee_id"] == instruction["payee_id"]
                and row["account_last4"] == payee.get("account_last4")
                and row["amount_cents"] == instruction["amount_cents"]
            ]
            instruction_docs_ok &= bool(valid)
            for row in valid or candidates[:1]:
                refs.add(f"{row['local_path']}#{row['document_id']}")
            refs.add(f"state/escrow.db#instructions:{instruction['instruction_id']}")

        recorded_at = original["recorded_at"]
        if recorded_at is None and recording_events:
            recorded_at = str(recording_events[-1]["payload"]["recorded_at"])

        if original["disbursed_at"]:
            preserved += int(original["disbursed_cents"])
            release_events = by_type.get("holdback_release_authorized", [])
            release_docs = [row for row in documents.get(closing_id, []) if row["document_type"] == "holdback_release_authorization"]
            release_doc_ids = {str(row["payload"].get("document_id")) for row in release_events}
            release_ok = any(
                row["document_id"] in release_doc_ids and document_valid(row)
                and int(row["amount_cents"] or 0) == holdback for row in release_docs
            )
            if release_ok and holdback:
                disposition = final_state = "holdback_release_ready"
                action = "stage_local_holdback_release_packet"
                stageable += holdback
                for row in release_docs:
                    if row["document_id"] in release_doc_ids:
                        refs.add(f"{row['local_path']}#{row['document_id']}")
            else:
                disposition = "already_disbursed_preserved"
                final_state = original["state"]
                action = "none"
            verified = int(original["verified_allocations_cents"])
        elif not wire_events:
            disposition, final_state, action, verified = "hold_wire_missing", "held", "resolve_wire_hold", 0
        elif wire_amount != int(original["expected_wire_cents"]):
            disposition, final_state, action, verified = "hold_wire_amount_mismatch", "held", "resolve_wire_hold", 0
        elif not closing_auth_ok:
            disposition, final_state, action, verified = "hold_missing_closing_authorization", "held", "resolve_authorization_hold", 0
        elif not payees_ok:
            disposition, final_state, action, verified = "hold_payee_unverified", "held", "resolve_payee_hold", 0
        elif not instruction_docs_ok:
            disposition, final_state, action, verified = "hold_instruction_mismatch", "held", "resolve_instruction_hold", 0
        elif allocation_total != wire_amount:
            disposition, final_state, action, verified = "hold_funds_not_conserved", "held", "resolve_conservation_hold", 0
        elif not recorded_at:
            disposition, final_state, action, verified = "hold_recording_pending", "held", "await_recording_confirmation", 0
        else:
            disposition = final_state = "ready_local_disbursement_packet"
            action = "stage_local_disbursement_packet"
            verified = allocation_total
            stageable += allocation_total

        decision = {
            "closing_id": closing_id,
            "property_id": original["property_id"],
            "disposition": disposition,
            "final_state": final_state,
            "wire_amount_cents": wire_amount,
            "authorized_allocations_cents": verified,
            "holdback_cents": holdback,
            "next_local_action": action,
            "instruction_ids": instruction_ids,
            "evidence_refs": sorted(refs),
        }
        final = dict(original)
        final.update(
            state=final_state, recorded_at=recorded_at,
            verified_allocations_cents=verified, next_action=action,
            version=int(original["version"]) + 1,
        )
        decisions.append(decision)
        final_closings[closing_id] = final

    checkpoint_payload = {
        "immutable_source_hashes": manifest["files"],
        "source_bundle_hash": source_bundle_hash,
        "source_revision": baseline["source_revision"],
        "baseline_closings": baseline["closings"],
        "payees": baseline["payees"],
        "instructions": baseline["instructions"],
        "documents": baseline["documents"],
    }
    plan = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": digest(canonical(checkpoint_payload)),
        "closing_decisions": decisions,
        "event_dispositions": event_rows,
        "totals": {
            "received_wire_cents": received_wire,
            "locally_stageable_cents": stageable,
            "preserved_disbursed_cents": preserved,
            "retained_holdback_cents": retained,
        },
        "external_actions_executed": False,
    }
    target = normalize_plan(plan)
    return plan_errors(raw, target), {"baseline": baseline}


def normalize_locator(value: str) -> str:
    return value.replace("#closing:", "#closings:").replace("#instruction:", "#instructions:")


def normalize_plan(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    decisions = []
    for raw in value.get("closing_decisions", []) if isinstance(value.get("closing_decisions"), list) else []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        if isinstance(row.get("instruction_ids"), list):
            row["instruction_ids"] = sorted(row["instruction_ids"])
        if isinstance(row.get("evidence_refs"), list):
            row["evidence_refs"] = sorted(normalize_locator(str(item)) for item in row["evidence_refs"])
        decisions.append(row)
    result["closing_decisions"] = sorted(decisions, key=lambda row: str(row.get("closing_id")))
    events = value.get("event_dispositions")
    result["event_dispositions"] = sorted(
        [dict(row) for row in events if isinstance(row, dict)] if isinstance(events, list) else [],
        key=lambda row: str(row.get("delivery_id")),
    )
    return result


def plan_errors(raw: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if set(raw) != PLAN_FIELDS:
        errors.append({"scope": "plan", "id": "schema", "field": "top_level_fields", "evidence": "published recovery-plan schema"})
        return errors
    if not isinstance(raw.get("closing_decisions"), list) or any(not isinstance(row, dict) or set(row) != DECISION_FIELDS for row in raw["closing_decisions"]):
        errors.append({"scope": "plan", "id": "schema", "field": "closing_decisions", "evidence": "published closing-decision schema"})
        return errors
    if not isinstance(raw.get("event_dispositions"), list) or any(not isinstance(row, dict) or set(row) != EVENT_FIELDS for row in raw["event_dispositions"]):
        errors.append({"scope": "plan", "id": "schema", "field": "event_dispositions", "evidence": "published event-disposition schema"})
        return errors
    if not isinstance(raw.get("totals"), dict) or set(raw["totals"]) != TOTAL_FIELDS:
        errors.append({"scope": "plan", "id": "schema", "field": "totals", "evidence": "published funds-total schema"})
        return errors
    candidate = normalize_plan(raw)
    for field in ("schema_version", "recovery_id", "source_checkpoint", "totals", "external_actions_executed"):
        if candidate.get(field) != target.get(field):
            errors.append({"scope": "plan", "id": "global", "field": field, "evidence": "policy, protected sources, and independently recomputed funds"})
    for key, identity in (("closing_decisions", "closing_id"), ("event_dispositions", "delivery_id")):
        got = {str(row.get(identity)): row for row in candidate.get(key, [])}
        expected = {str(row.get(identity)): row for row in target.get(key, [])}
        for item_id in sorted(set(got) | set(expected)):
            if item_id not in got or item_id not in expected:
                errors.append({"scope": key, "id": item_id, "field": "presence", "evidence": "restored closing baseline or event delivery set"})
                continue
            for field in sorted(set(got[item_id]) | set(expected[item_id])):
                if got[item_id].get(field) != expected[item_id].get(field):
                    evidence = "event order and duplicate boundary" if key == "event_dispositions" else "wire, authority, payee, instruction, recording, and conservation facts"
                    errors.append({"scope": key, "id": item_id, "field": field, "evidence": evidence})
    return errors


def closure_targets(plan: dict[str, Any], baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build closure only after a candidate plan has passed validation."""
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        final_rows = rows(connection, "closings", "closing_id")
    receipts = [{**row, "recovery_id": plan["recovery_id"]} for row in plan["event_dispositions"]]
    state_hash = digest(canonical({"closings": final_rows, "event_receipts": receipts}))
    preview = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "valid",
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "decision_count": len(plan["closing_decisions"]), "delivery_count": len(plan["event_dispositions"]),
        "totals": plan["totals"], "discrepancies": [], "external_actions_executed": False,
    }
    verification = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass",
        "checks": {"source_checkpoint_matches": True, "semantic_plan_matches": True,
                   "closing_projection_exact": True, "event_receipts_exact": True,
                   "interrupted_journal_recovered": True, "funds_conserve": True,
                   "irreversible_boundaries_preserved": True, "local_only": True},
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "semantic_state_digest": state_hash,
        "final_revision": baseline["source_revision"] + 1,
        "external_actions_executed": False,
    }
    items = []
    for decision in plan["closing_decisions"]:
        if decision["disposition"] not in {"ready_local_disbursement_packet", "holdback_release_ready"}:
            continue
        items.append({
            "position": len(items) + 1, "closing_id": decision["closing_id"],
            "packet_type": "holdback_release" if decision["disposition"] == "holdback_release_ready" else "disbursement_review",
            "amount_cents": decision["holdback_cents"] if decision["disposition"] == "holdback_release_ready" else decision["authorized_allocations_cents"],
            "instruction_ids": decision["instruction_ids"], "evidence_refs": decision["evidence_refs"],
        })
    packet = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "packet_items": items, "stage_boundary": "local_review_only_not_disbursed",
        "external_actions_executed": False,
    }
    packet_hash = digest(canonical(packet))
    manifest = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "packet_path": "staging/disbursement_packet.json", "packet_sha256": packet_hash,
        "packet_count": len(items), "packet_order": [row["closing_id"] for row in items],
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "external_actions_executed": False,
    }
    payload = {
        "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_digest": plan_hash, "packet_sha256": packet_hash,
        "manifest_sha256": digest(canonical(manifest)), "stage_boundary": "local_review_only_not_disbursed",
    }
    receipt = {"schema_version": 1, **payload, "status": "staged_local_bundle",
               "stage_token": digest(canonical(payload)), "external_actions_executed": False}
    replay = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass",
        "database_byte_stable": True, "packet_byte_stable": True,
        "manifest_byte_stable": True, "receipt_byte_stable": True,
        "semantic_plan_digest": plan_hash, "external_actions_executed": False,
    }
    return {"preview": preview, "verification": verification, "packet": packet,
            "manifest": manifest, "receipt": receipt, "replay": replay}


def read_plan(path: str) -> dict[str, Any]:
    return load_json((ROOT / path).resolve())


def preview(path: str) -> None:
    raw = read_plan(path)
    errors, facts = validation_report(raw)
    if errors:
        write_json(ROOT / ".escrow_preview.json", {"schema_version": 1, "status": "invalid", "discrepancies": errors, "external_actions_executed": False})
        raise ValueError(f"preview rejected {len(errors)} discrepancy(s); inspect .escrow_preview.json")
    plan = normalize_plan(raw)
    write_json(ROOT / ".escrow_preview.json", closure_targets(plan, facts["baseline"])["preview"])
    print("preview valid")


def apply(path: str) -> None:
    raw = read_plan(path)
    errors, facts = validation_report(raw)
    if errors:
        raise ValueError(f"apply rejected {len(errors)} plan discrepancy(s); run preview")
    plan = normalize_plan(raw)
    baseline = facts["baseline"]
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        connection.row_factory = sqlite3.Row
        current = connection.execute("SELECT * FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if current:
            if current["source_checkpoint"] == plan["source_checkpoint"] and current["semantic_plan_digest"] == plan_hash:
                print("equivalent recovery already committed; no mutation")
                return
            raise ValueError("conflicting plan under existing recovery identity")
        connection.execute("BEGIN IMMEDIATE")
        pending = connection.execute(
            "SELECT journal_id,closing_id,before_json FROM recovery_journal j JOIN recovery_runs r USING(recovery_id) WHERE r.status='interrupted' AND j.restored=0 ORDER BY journal_id"
        ).fetchall()
        for item in pending:
            before = json.loads(item["before_json"])
            connection.execute(
                "UPDATE closings SET property_id=?,expected_wire_cents=?,state=?,recorded_at=?,disbursed_at=?,disbursed_cents=?,retained_holdback_cents=?,verified_allocations_cents=?,next_action=?,version=? WHERE closing_id=?",
                (before["property_id"], before["expected_wire_cents"], before["state"], before["recorded_at"], before["disbursed_at"], before["disbursed_cents"], before["retained_holdback_cents"], before["verified_allocations_cents"], before["next_action"], before["version"], before["closing_id"]),
            )
            connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (item["journal_id"],))
        connection.execute("UPDATE recovery_runs SET status='rolled_back_recovered' WHERE status='interrupted'")
        closing_by_id = {row["closing_id"]: row for row in baseline["closings"]}
        _, accepted = event_facts(load_events(), closing_by_id)
        decisions = {row["closing_id"]: row for row in plan["closing_decisions"]}
        for before in baseline["closings"]:
            connection.execute(
                "INSERT INTO recovery_journal(recovery_id,closing_id,before_json,restored) VALUES(?,?,?,0)",
                (plan["recovery_id"], before["closing_id"], json.dumps(before, sort_keys=True)),
            )
            decision = decisions[before["closing_id"]]
            recorded_at = before["recorded_at"]
            recording_events = [
                row for row in accepted.get(before["closing_id"], [])
                if row.get("event_type") == "recording_confirmed"
            ]
            if recorded_at is None and recording_events:
                recorded_at = str(recording_events[-1]["payload"]["recorded_at"])
            connection.execute(
                "UPDATE closings SET state=?,recorded_at=?,verified_allocations_cents=?,next_action=?,version=? WHERE closing_id=?",
                (decision["final_state"], recorded_at, decision["authorized_allocations_cents"], decision["next_local_action"], int(before["version"]) + 1, before["closing_id"]),
            )
        for row in plan["event_dispositions"]:
            connection.execute(
                "INSERT INTO event_receipts VALUES(?,?,?,?,?,?)",
                (row["delivery_id"], row["event_id"], row["closing_id"], row["source_sequence"], row["disposition"], plan["recovery_id"]),
            )
        revision = baseline["source_revision"] + 1
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?,0)", (plan["recovery_id"], "committed", plan["source_checkpoint"], plan_hash, revision))
        connection.execute("UPDATE system_state SET value=? WHERE key='portfolio_revision'", (str(revision),))
        connection.execute("UPDATE system_state SET value='committed' WHERE key='stage_state'")
        connection.commit()
    print("atomic local projection committed")


def database_matches(plan: dict[str, Any], baseline: dict[str, Any]) -> bool:
    with sqlite3.connect(DB) as connection:
        actual = rows(connection, "closings", "closing_id")
        receipts = rows(connection, "event_receipts", "delivery_id")
        old = connection.execute("SELECT status FROM recovery_runs WHERE recovery_id='EDR-INTERRUPTED-20260818'").fetchone()
    closing_by_id = {row["closing_id"]: row for row in baseline["closings"]}
    _, accepted = event_facts(load_events(), closing_by_id)
    decisions = {row["closing_id"]: row for row in plan["closing_decisions"]}
    expected = []
    for closing_id in sorted(closing_by_id):
        row = dict(closing_by_id[closing_id])
        decision = decisions[closing_id]
        recording_events = [
            item for item in accepted.get(closing_id, [])
            if item.get("event_type") == "recording_confirmed"
        ]
        if row["recorded_at"] is None and recording_events:
            row["recorded_at"] = str(recording_events[-1]["payload"]["recorded_at"])
        row.update(
            state=decision["final_state"],
            verified_allocations_cents=decision["authorized_allocations_cents"],
            next_action=decision["next_local_action"],
            version=int(row["version"]) + 1,
        )
        expected.append(row)
    expected_receipts = [{**row, "recovery_id": plan["recovery_id"]} for row in plan["event_dispositions"]]
    return actual == expected and receipts == expected_receipts and old == ("rolled_back_recovered",)


def verify(path: str) -> None:
    raw = read_plan(path)
    errors, facts = validation_report(raw)
    if errors:
        raise ValueError("verification rejected plan")
    plan = normalize_plan(raw)
    if not database_matches(plan, facts["baseline"]):
        raise ValueError("database projection or recovery boundary differs")
    write_json(ROOT / "state/verification.json", closure_targets(plan, facts["baseline"])["verification"])
    print("verification pass")


def stage(path: str) -> None:
    raw = read_plan(path)
    errors, facts = validation_report(raw)
    plan = normalize_plan(raw)
    if errors or not database_matches(plan, facts["baseline"]):
        raise ValueError("stage requires exact verified local projection")
    targets = closure_targets(plan, facts["baseline"])
    existing = all(
        load_json(path_obj) == targets[key]
        for path_obj, key in (
            (ROOT / "staging/disbursement_packet.json", "packet"),
            (ROOT / "staging/packet_manifest.json", "manifest"),
            (ROOT / "state/recovery_receipt.json", "receipt"),
        ) if path_obj.exists()
    ) and all(path_obj.exists() for path_obj in (
        ROOT / "staging/disbursement_packet.json", ROOT / "staging/packet_manifest.json", ROOT / "state/recovery_receipt.json"
    ))
    with sqlite3.connect(DB) as connection:
        status = connection.execute("SELECT status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        stage_state = connection.execute("SELECT value FROM system_state WHERE key='stage_state'").fetchone()
        if existing and status == ("staged_local_bundle",) and stage_state == ("staged_local_bundle",):
            print("equivalent local bundle already staged; no mutation")
            return
        write_json(ROOT / "staging/disbursement_packet.json", targets["packet"])
        write_json(ROOT / "staging/packet_manifest.json", targets["manifest"])
        write_json(ROOT / "state/recovery_receipt.json", targets["receipt"])
        connection.execute("UPDATE recovery_runs SET status='staged_local_bundle' WHERE recovery_id=?", (plan["recovery_id"],))
        connection.execute("UPDATE system_state SET value='staged_local_bundle' WHERE key='stage_state'")
        connection.commit()
    print("local review bundle staged; no external action")


def replay(path: str) -> None:
    tracked = [DB, ROOT / "staging/disbursement_packet.json", ROOT / "staging/packet_manifest.json", ROOT / "state/recovery_receipt.json"]
    if not all(item.exists() for item in tracked):
        raise ValueError("replay requires staged artifacts")
    before = [item.read_bytes() for item in tracked]
    apply(path)
    verify(path)
    stage(path)
    after = [item.read_bytes() for item in tracked]
    if before != after:
        raise ValueError("equivalent replay changed committed or staged bytes")
    raw = read_plan(path)
    errors, facts = validation_report(raw)
    if errors:
        raise ValueError("replay candidate no longer validates")
    write_json(ROOT / "state/replay_report.json", closure_targets(normalize_plan(raw), facts["baseline"])["replay"])
    print("semantic replay pass; tracked bytes stable")


def inspect() -> None:
    policy = load_json(ROOT / "policy/escrow_policy.json")
    source_manifest()
    with sqlite3.connect(DB) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        runs = rows(connection, "recovery_runs", "recovery_id")
        baseline = baseline_state(connection, str(policy["recovery_id"]))
    print(json.dumps({
        "database": "state/escrow.db", "tables": tables,
        "closing_ids": [row["closing_id"] for row in baseline["closings"]],
        "delivery_count": len(load_events()),
        "recovery_runs": runs,
        "next": "inspect policy, sources, hashes, and all SQLite tables before planning",
    }, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    for name in ("preview", "apply", "verify", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            inspect()
        else:
            globals()[args.command](args.plan)
    except (ValueError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
