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
DB = ROOT / "state/pv.db"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "case_decisions",
    "delivery_dispositions", "queue_totals", "external_transmissions_executed",
}
DECISION_FIELDS = {
    "case_id", "prior_version", "final_version", "disposition", "final_state",
    "queue", "deadline_class", "selected_message_ids", "next_local_action",
    "evidence_refs",
}
DELIVERY_FIELDS = {
    "delivery_id", "message_id", "case_id", "version", "disposition",
}
TOTAL_FIELDS = {"expedited_review", "routine_review", "held", "preserved"}


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
        raise ValueError(f"{path.relative_to(ROOT)} must be one JSON object")
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
        raise ValueError("source manifest schema is invalid")
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


def jsonl(path: Path) -> list[dict[str, Any]]:
    result = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSONL at {path.name}:{number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL at {path.name}:{number}")
        result.append(value)
    return result


def baseline_state(connection: sqlite3.Connection, recovery_id: str) -> dict[str, Any]:
    cases = {row["case_id"]: row for row in rows(connection, "safety_cases", "case_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
    journal = rows(connection, "recovery_journal", "journal_id")
    current = runs.get(recovery_id)
    if current and current["status"] in {"committed", "staged_local_bundle"}:
        for entry in journal:
            if entry["recovery_id"] == recovery_id:
                cases[entry["case_id"]] = json.loads(entry["before_json"])
    for entry in journal:
        run = runs.get(entry["recovery_id"])
        if run and run["status"] == "interrupted" and not entry["restored"]:
            cases[entry["case_id"]] = json.loads(entry["before_json"])
    system = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
    source_revision = int(system["source_revision"])
    if current and current["status"] in {"committed", "staged_local_bundle"}:
        source_revision = int(current["final_revision"]) - 1
    version_rows = [
        row for row in rows(connection, "report_versions", "case_id,version")
        if row["case_id"] in cases
        and int(row["version"]) <= int(cases[row["case_id"]]["current_version"])
    ]
    return {
        "cases": [cases[key] for key in sorted(cases)],
        "versions": version_rows,
        "submissions": rows(connection, "submissions", "submission_id"),
        "source_revision": source_revision,
    }


def normalize_locator(value: str) -> str:
    return value.replace("#case:", "#safety_cases:").replace("#message:", "#message_id:")


def normalize_plan(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    decisions = []
    raw_decisions = value.get("case_decisions")
    if isinstance(raw_decisions, list):
        for raw in raw_decisions:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            if isinstance(item.get("selected_message_ids"), list):
                item["selected_message_ids"] = sorted(str(part) for part in item["selected_message_ids"])
            if isinstance(item.get("evidence_refs"), list):
                item["evidence_refs"] = sorted(normalize_locator(str(part)) for part in item["evidence_refs"])
            decisions.append(item)
    result["case_decisions"] = sorted(decisions, key=lambda row: str(row.get("case_id")))
    raw_deliveries = value.get("delivery_dispositions")
    result["delivery_dispositions"] = sorted(
        [dict(row) for row in raw_deliveries if isinstance(row, dict)]
        if isinstance(raw_deliveries, list) else [],
        key=lambda row: str(row.get("delivery_id")),
    )
    return result


def validate_candidate(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate caller-authored recovery state; never export the constructed target."""
    policy = load_json(ROOT / "policy/pv_policy.json")
    manifest, source_bundle_hash = source_manifest()
    messages = jsonl(ROOT / "evidence/inbound_messages.jsonl")
    acknowledgements = jsonl(ROOT / "evidence/acknowledgements.jsonl")
    recovery_id = str(policy["recovery_id"])
    with sqlite3.connect(DB) as connection:
        baseline = baseline_state(connection, recovery_id)
    cases = {row["case_id"]: row for row in baseline["cases"]}
    versions = {(row["case_id"], int(row["version"])): row for row in baseline["versions"]}
    accepted = {
        (str(row["case_id"]), int(row["version"]))
        for row in acknowledgements if row.get("status") == "accepted"
    }
    pending = {
        (str(row["case_id"]), int(row["version"]))
        for row in acknowledgements if row.get("status") == "pending"
    }
    permitted = set(policy["permitted_meddra_versions"])
    seen_messages: set[str] = set()
    deliveries = []
    applicable: dict[str, list[dict[str, Any]]] = {}
    held_reason: dict[str, str] = {}
    working_version = {key: int(row["current_version"]) for key, row in cases.items()}
    selected: dict[str, list[str]] = {key: [] for key in cases}
    latest_serious = {key: False for key in cases}

    for message in sorted(messages, key=lambda row: (int(row.get("source_sequence", -1)), str(row.get("message_id", "")))):
        delivery_id = str(message.get("delivery_id", ""))
        message_id = str(message.get("message_id", ""))
        case_id = str(message.get("case_id", ""))
        version = int(message.get("version", -1))
        if message_id in seen_messages:
            status = "duplicate_delivery_ignored"
        else:
            seen_messages.add(message_id)
            case = cases.get(case_id)
            if case is None:
                status = "unknown_case_ignored"
            elif any(key[0] == case_id for key in accepted):
                status = "accepted_boundary_held"
                held_reason.setdefault(case_id, "preserve_submitted_accepted")
            elif any(key[0] == case_id for key in pending):
                status = "pending_ack_boundary_held"
                held_reason.setdefault(case_id, "preserve_pending_ack")
            elif (
                str(message.get("sender_case_id")) != case["sender_case_id"]
                or str(message.get("patient_key")) != case["patient_key"]
                or str(message.get("suspect_product_key")) != case["suspect_product_key"]
            ):
                status = "identity_collision_held"
                held_reason.setdefault(case_id, "hold_identity_collision")
            elif str(message.get("meddra_version")) not in permitted:
                status = "terminology_version_held"
                held_reason.setdefault(case_id, "hold_terminology_version")
            elif message.get("message_type") == "nullification" and not str(message.get("nullification_reason", "")).strip():
                status = "nullification_incomplete_held"
                held_reason.setdefault(case_id, "hold_nullification_incomplete")
            elif version <= working_version[case_id]:
                prior = versions.get((case_id, version))
                if prior and prior["payload_digest"] == str(message.get("payload_digest")):
                    status = "duplicate_content_ignored"
                else:
                    status = "version_collision_held"
                    held_reason.setdefault(case_id, "hold_version_collision")
            elif version != working_version[case_id] + 1:
                status = "version_gap_held"
                held_reason.setdefault(case_id, "hold_version_gap")
            elif not bool(message.get("source_verified")):
                status = "unverified_source_held"
                held_reason.setdefault(case_id, "hold_unverified_source")
            else:
                status = "accepted_local_projection"
                working_version[case_id] = version
                latest_serious[case_id] = bool(message.get("serious"))
                selected[case_id].append(message_id)
                applicable.setdefault(case_id, []).append(message)
        deliveries.append({
            "delivery_id": delivery_id,
            "message_id": message_id,
            "case_id": case_id,
            "version": version,
            "disposition": status,
        })

    decisions = []
    final_cases: dict[str, dict[str, Any]] = {}
    final_versions = list(baseline["versions"])
    totals = {"expedited_review": 0, "routine_review": 0, "held": 0, "preserved": 0}
    for case_id in sorted(cases):
        original = cases[case_id]
        refs = {
            f"state/pv.db#safety_cases:{case_id}",
            "policy/pv_policy.json#rules",
            "evidence/acknowledgements.jsonl",
        }
        for message in messages:
            if str(message.get("case_id")) == case_id:
                refs.add(f"evidence/inbound_messages.jsonl#message_id:{message['message_id']}")
        final = dict(original)
        case_messages = applicable.get(case_id, [])
        reason = held_reason.get(case_id)
        if case_messages:
            queue = "expedited_review" if latest_serious[case_id] else "routine_review"
            disposition = "ready_expedited_review" if latest_serious[case_id] else "ready_routine_review"
            deadline = "seven_calendar_days" if latest_serious[case_id] else "routine_processing"
            state = "local_review_ready"
            next_action = "stage_local_review"
            totals[queue] += 1
            final.update(
                current_version=working_version[case_id], state=state, queue=queue,
                next_action=next_action, row_revision=int(original["row_revision"]) + 1,
            )
            for message in case_messages:
                final_versions.append((
                    case_id, int(message["version"]), str(message["message_type"]),
                    int(bool(message["serious"])), str(message["meddra_version"]),
                    str(message["payload_digest"]),
                ))
        elif reason and reason.startswith("hold_"):
            disposition = reason
            state = "held"
            queue = "none"
            deadline = "none"
            next_action = {
                "hold_identity_collision": "resolve_case_identity",
                "hold_terminology_version": "resolve_terminology_version",
                "hold_nullification_incomplete": "obtain_nullification_reason",
                "hold_version_collision": "resolve_version_collision",
                "hold_version_gap": "obtain_missing_version",
                "hold_unverified_source": "verify_source",
            }[reason]
            totals["held"] += 1
            final.update(
                state=state, queue=queue, next_action=next_action,
                row_revision=int(original["row_revision"]) + 1,
            )
        elif reason == "preserve_submitted_accepted":
            disposition, state, queue = reason, original["state"], original["queue"]
            deadline, next_action = "immutable_accepted_boundary", original["next_action"]
            totals["preserved"] += 1
        elif reason == "preserve_pending_ack":
            disposition, state, queue = reason, original["state"], original["queue"]
            deadline, next_action = "await_ack_boundary", original["next_action"]
            totals["preserved"] += 1
        else:
            disposition, state, queue = "duplicate_preserved", original["state"], original["queue"]
            deadline, next_action = "none", original["next_action"]
            totals["preserved"] += 1
        decisions.append({
            "case_id": case_id,
            "prior_version": int(original["current_version"]),
            "final_version": int(final["current_version"]),
            "disposition": disposition,
            "final_state": state,
            "queue": queue,
            "deadline_class": deadline,
            "selected_message_ids": sorted(selected[case_id]),
            "next_local_action": next_action,
            "evidence_refs": sorted(refs),
        })
        final_cases[case_id] = final

    checkpoint_payload = {
        "immutable_source_hashes": manifest["files"],
        "source_bundle_hash": source_bundle_hash,
        "source_revision": baseline["source_revision"],
        "baseline_cases": baseline["cases"],
        "baseline_versions": baseline["versions"],
        "baseline_submissions": baseline["submissions"],
    }
    plan = normalize_plan({
        "schema_version": 1,
        "recovery_id": recovery_id,
        "source_checkpoint": digest(canonical(checkpoint_payload)),
        "case_decisions": decisions,
        "delivery_dispositions": deliveries,
        "queue_totals": totals,
        "external_transmissions_executed": False,
    })
    errors = plan_errors(raw, plan)
    if errors:
        raise ValueError(json.dumps(errors, sort_keys=True))
    return normalize_plan(raw), {
        "baseline": baseline,
        "messages": messages,
    }


def plan_errors(raw: dict[str, Any], target: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if set(raw) != PLAN_FIELDS:
        return [{"scope": "plan", "id": "schema", "field": "top_level_fields", "code": "schema_mismatch"}]
    if not isinstance(raw.get("case_decisions"), list) or any(
        not isinstance(row, dict) or set(row) != DECISION_FIELDS for row in raw["case_decisions"]
    ):
        return [{"scope": "plan", "id": "schema", "field": "case_decisions", "code": "schema_mismatch"}]
    if not isinstance(raw.get("delivery_dispositions"), list) or any(
        not isinstance(row, dict) or set(row) != DELIVERY_FIELDS for row in raw["delivery_dispositions"]
    ):
        return [{"scope": "plan", "id": "schema", "field": "delivery_dispositions", "code": "schema_mismatch"}]
    if not isinstance(raw.get("queue_totals"), dict) or set(raw["queue_totals"]) != TOTAL_FIELDS:
        return [{"scope": "plan", "id": "schema", "field": "queue_totals", "code": "schema_mismatch"}]
    candidate = normalize_plan(raw)
    for field in ("schema_version", "recovery_id", "source_checkpoint", "queue_totals", "external_transmissions_executed"):
        if candidate.get(field) != target.get(field):
            errors.append({"scope": "plan", "id": "global", "field": field, "code": "value_mismatch"})
    for key, identity in (("case_decisions", "case_id"), ("delivery_dispositions", "delivery_id")):
        got = {str(row.get(identity)): row for row in candidate[key]}
        expected = {str(row.get(identity)): row for row in target[key]}
        for item_id in sorted(set(got) | set(expected)):
            if item_id not in got or item_id not in expected:
                errors.append({"scope": key, "id": item_id, "field": "presence", "code": "missing_or_extra_object"})
                continue
            for field in sorted(set(got[item_id]) | set(expected[item_id])):
                if got[item_id].get(field) != expected[item_id].get(field):
                    errors.append({"scope": key, "id": item_id, "field": field, "code": "value_mismatch"})
    return errors


def read_plan(path: str) -> dict[str, Any]:
    target = (ROOT / path).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("plan must be inside workspace") from exc
    return load_json(target)


def project_state(plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Project a validated candidate onto the recovered before-image."""
    baseline = context["baseline"]
    cases = {row["case_id"]: dict(row) for row in baseline["cases"]}
    messages = {str(row["message_id"]): row for row in context["messages"]}
    versions: list[dict[str, Any] | tuple[object, ...]] = list(baseline["versions"])
    for decision in plan["case_decisions"]:
        case = cases[decision["case_id"]]
        changed = (
            int(case["current_version"]) != int(decision["final_version"])
            or case["state"] != decision["final_state"]
            or case["queue"] != decision["queue"]
            or case["next_action"] != decision["next_local_action"]
        )
        if changed:
            case.update(
                current_version=int(decision["final_version"]),
                state=decision["final_state"],
                queue=decision["queue"],
                next_action=decision["next_local_action"],
                row_revision=int(case["row_revision"]) + 1,
            )
        for message_id in decision["selected_message_ids"]:
            message = messages[message_id]
            versions.append((
                decision["case_id"], int(message["version"]),
                str(message["message_type"]), int(bool(message["serious"])),
                str(message["meddra_version"]), str(message["payload_digest"]),
            ))
    return {"final_cases": cases, "final_versions": versions}


def closure_targets(plan: dict[str, Any], truth: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plan_hash = digest(canonical(plan))
    final_cases = [truth["final_cases"][key] for key in sorted(truth["final_cases"])]
    deliveries = [{**row, "recovery_id": plan["recovery_id"]} for row in plan["delivery_dispositions"]]
    state_hash = digest(canonical({"cases": final_cases, "deliveries": deliveries}))
    preview = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "valid",
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "case_count": len(plan["case_decisions"]), "delivery_count": len(plan["delivery_dispositions"]),
        "queue_totals": plan["queue_totals"], "discrepancies": [],
        "external_transmissions_executed": False,
    }
    verification = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass",
        "checks": {
            "source_checkpoint_matches": True, "semantic_plan_matches": True,
            "case_projection_exact": True, "version_chain_contiguous": True,
            "delivery_receipts_exact": True, "interrupted_journal_recovered": True,
            "accepted_and_pending_boundaries_preserved": True, "local_only": True,
        },
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "semantic_state_digest": state_hash,
        "final_revision": truth["baseline"]["source_revision"] + 1,
        "external_transmissions_executed": False,
    }
    items = []
    for decision in plan["case_decisions"]:
        if decision["disposition"] not in {"ready_expedited_review", "ready_routine_review"}:
            continue
        items.append({
            "position": len(items) + 1, "case_id": decision["case_id"],
            "version": decision["final_version"], "queue": decision["queue"],
            "deadline_class": decision["deadline_class"],
            "selected_message_ids": decision["selected_message_ids"],
            "evidence_refs": decision["evidence_refs"],
        })
    packet = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "review_items": items, "stage_boundary": "local_safety_review_not_transmitted",
        "external_transmissions_executed": False,
    }
    packet_hash = digest(canonical(packet))
    manifest = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "packet_path": "staging/pv_review_queue.json", "packet_sha256": packet_hash,
        "packet_count": len(items), "packet_order": [row["case_id"] for row in items],
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "external_transmissions_executed": False,
    }
    payload = {
        "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_digest": plan_hash, "packet_sha256": packet_hash,
        "manifest_sha256": digest(canonical(manifest)),
        "stage_boundary": "local_safety_review_not_transmitted",
    }
    receipt = {
        "schema_version": 1, **payload, "status": "staged_local_bundle",
        "stage_token": digest(canonical(payload)), "external_transmissions_executed": False,
    }
    replay = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass",
        "database_byte_stable": True, "packet_byte_stable": True,
        "manifest_byte_stable": True, "receipt_byte_stable": True,
        "semantic_plan_digest": plan_hash, "external_transmissions_executed": False,
    }
    return {"preview": preview, "verification": verification, "packet": packet, "manifest": manifest, "receipt": receipt, "replay": replay}


def preview(path: str) -> None:
    try:
        plan, truth = validate_candidate(read_plan(path))
    except ValueError as exc:
        try:
            errors = json.loads(str(exc))
        except json.JSONDecodeError:
            errors = [{"scope": "plan", "id": "global", "field": "source_integrity", "code": "source_error"}]
        write_json(ROOT / ".pv_preview.json", {
            "schema_version": 1, "status": "invalid", "discrepancies": errors,
            "external_transmissions_executed": False,
        })
        raise ValueError(f"preview rejected {len(errors)} discrepancy(s); inspect .pv_preview.json")
    write_json(ROOT / ".pv_preview.json", closure_targets(plan, {**truth, **project_state(plan, truth)})["preview"])
    print("preview valid")


def _restore_interrupted(connection: sqlite3.Connection) -> None:
    pending = connection.execute(
        "SELECT j.journal_id,j.case_id,j.before_json,j.recovery_id FROM recovery_journal j JOIN recovery_runs r USING(recovery_id) WHERE r.status='interrupted' AND j.restored=0 ORDER BY j.journal_id"
    ).fetchall()
    for journal_id, case_id, before_json, recovery_id in pending:
        before = json.loads(before_json)
        connection.execute(
            "UPDATE safety_cases SET sender_case_id=?,patient_key=?,suspect_product_key=?,current_version=?,state=?,queue=?,next_action=?,row_revision=? WHERE case_id=?",
            (before["sender_case_id"], before["patient_key"], before["suspect_product_key"], before["current_version"], before["state"], before["queue"], before["next_action"], before["row_revision"], case_id),
        )
        connection.execute("DELETE FROM delivery_receipts WHERE recovery_id=?", (recovery_id,))
        connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
    connection.execute("UPDATE recovery_runs SET status='rolled_back_recovered' WHERE status='interrupted'")


def apply(path: str) -> None:
    plan, truth = validate_candidate(read_plan(path))
    truth = {**truth, **project_state(plan, truth)}
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        current = connection.execute("SELECT source_checkpoint,semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if current:
            if current == (plan["source_checkpoint"], plan_hash):
                print("equivalent recovery already committed; no mutation")
                return
            raise ValueError("conflicting plan under existing recovery identity")
        connection.execute("BEGIN IMMEDIATE")
        _restore_interrupted(connection)
        for before in truth["baseline"]["cases"]:
            final = truth["final_cases"][before["case_id"]]
            if final == before:
                continue
            connection.execute(
                "INSERT INTO recovery_journal(recovery_id,case_id,before_json,restored) VALUES(?,?,?,0)",
                (plan["recovery_id"], before["case_id"], json.dumps(before, sort_keys=True)),
            )
            connection.execute(
                "UPDATE safety_cases SET current_version=?,state=?,queue=?,next_action=?,row_revision=? WHERE case_id=?",
                (final["current_version"], final["state"], final["queue"], final["next_action"], final["row_revision"], final["case_id"]),
            )
        existing_versions = {(row["case_id"], int(row["version"])) for row in truth["baseline"]["versions"]}
        for version in truth["final_versions"]:
            if isinstance(version, dict):
                values = tuple(version[key] for key in ("case_id", "version", "message_type", "serious", "meddra_version", "payload_digest"))
            else:
                values = tuple(version)
            if (values[0], int(values[1])) not in existing_versions:
                connection.execute("INSERT INTO report_versions VALUES(?,?,?,?,?,?)", values)
        for row in plan["delivery_dispositions"]:
            connection.execute(
                "INSERT INTO delivery_receipts VALUES(?,?,?,?,?,?)",
                (row["delivery_id"], row["message_id"], row["case_id"], row["version"], row["disposition"], plan["recovery_id"]),
            )
        revision = truth["baseline"]["source_revision"] + 1
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?,0)", (plan["recovery_id"], "committed", plan["source_checkpoint"], plan_hash, revision))
        connection.execute("UPDATE system_state SET value=? WHERE key='source_revision'", (str(revision),))
        connection.execute("UPDATE system_state SET value='committed' WHERE key='stage_state'")
        connection.commit()
    print("atomic local pharmacovigilance projection committed")


def database_matches(plan: dict[str, Any], truth: dict[str, Any]) -> bool:
    with sqlite3.connect(DB) as connection:
        actual_cases = rows(connection, "safety_cases", "case_id")
        actual_versions = rows(connection, "report_versions", "case_id,version")
        actual_receipts = rows(connection, "delivery_receipts", "delivery_id")
        old = connection.execute("SELECT status FROM recovery_runs WHERE recovery_id='PV-INTERRUPTED-OLD'").fetchone()
    expected_cases = [truth["final_cases"][key] for key in sorted(truth["final_cases"])]
    expected_versions = [
        dict(zip(("case_id", "version", "message_type", "serious", "meddra_version", "payload_digest"), row, strict=True))
        if not isinstance(row, dict) else row for row in truth["final_versions"]
    ]
    expected_versions.sort(key=lambda row: (row["case_id"], int(row["version"])))
    expected_receipts = [{**row, "recovery_id": plan["recovery_id"]} for row in plan["delivery_dispositions"]]
    return actual_cases == expected_cases and actual_versions == expected_versions and actual_receipts == expected_receipts and old == ("rolled_back_recovered",)


def verify(path: str) -> None:
    plan, truth = validate_candidate(read_plan(path))
    truth = {**truth, **project_state(plan, truth)}
    if not database_matches(plan, truth):
        raise ValueError("database projection or recovery boundary differs")
    write_json(ROOT / "state/verification.json", closure_targets(plan, truth)["verification"])
    print("verification pass")


def stage(path: str) -> None:
    plan, truth = validate_candidate(read_plan(path))
    truth = {**truth, **project_state(plan, truth)}
    if not database_matches(plan, truth):
        raise ValueError("stage requires exact verified local projection")
    targets = closure_targets(plan, truth)
    artifacts = (
        (ROOT / "staging/pv_review_queue.json", targets["packet"]),
        (ROOT / "staging/packet_manifest.json", targets["manifest"]),
        (ROOT / "state/recovery_receipt.json", targets["receipt"]),
    )
    existing = all(path_obj.exists() and load_json(path_obj) == value for path_obj, value in artifacts)
    with sqlite3.connect(DB) as connection:
        status = connection.execute("SELECT status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        stage_state = connection.execute("SELECT value FROM system_state WHERE key='stage_state'").fetchone()
        if existing and status == ("staged_local_bundle",) and stage_state == ("staged_local_bundle",):
            print("equivalent local bundle already staged; no mutation")
            return
        for path_obj, value in artifacts:
            write_json(path_obj, value)
        connection.execute("UPDATE recovery_runs SET status='staged_local_bundle' WHERE recovery_id=?", (plan["recovery_id"],))
        connection.execute("UPDATE system_state SET value='staged_local_bundle' WHERE key='stage_state'")
        connection.commit()
    print("local safety-review bundle staged; no external transmission")


def replay(path: str) -> None:
    tracked = [DB, ROOT / "staging/pv_review_queue.json", ROOT / "staging/packet_manifest.json", ROOT / "state/recovery_receipt.json"]
    if not all(item.exists() for item in tracked):
        raise ValueError("replay requires staged artifacts")
    before = [item.read_bytes() for item in tracked]
    apply(path)
    verify(path)
    stage(path)
    after = [item.read_bytes() for item in tracked]
    if before != after:
        raise ValueError("equivalent replay changed committed or staged bytes")
    plan, truth = validate_candidate(read_plan(path))
    truth = {**truth, **project_state(plan, truth)}
    write_json(ROOT / "state/replay_report.json", closure_targets(plan, truth)["replay"])
    print("semantic replay pass; tracked bytes stable")


def inspect() -> None:
    policy = load_json(ROOT / "policy/pv_policy.json")
    source_manifest()
    messages = jsonl(ROOT / "evidence/inbound_messages.jsonl")
    with sqlite3.connect(DB) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        runs = rows(connection, "recovery_runs", "recovery_id")
        cases = rows(connection, "safety_cases", "case_id")
    print(json.dumps({
        "database": "state/pv.db", "tables": tables,
        "case_ids": [row["case_id"] for row in cases],
        "message_count": len(messages), "permitted_meddra_versions": policy["permitted_meddra_versions"],
        "recovery_runs": runs,
        "next": "inspect every policy rule, JSONL record, acknowledgement, and SQLite table before authoring a plan",
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
