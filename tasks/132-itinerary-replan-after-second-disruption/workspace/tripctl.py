#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/travel.db"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "inventory_snapshot_id",
    "selected_option_id", "option_assessments", "applied_event_ids",
    "ignored_duplicate_delivery_ids", "object_decisions", "external_actions_executed",
}
ASSESSMENT_FIELDS = {
    "option_id", "feasible", "reviewed_air_legs_changed", "incremental_cost_cad",
    "violations", "evidence_refs",
}
DECISION_FIELDS = {
    "object_id", "prior_state", "final_state", "action", "selected_inventory_object",
    "local_stage_kind", "evidence_refs", "external_action",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks UTC offset: {value}")
    return parsed


def source_bundle() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source manifest is malformed")
    changed = []
    for locator, expected in files.items():
        path = ROOT / str(locator)
        try:
            actual = digest(path.read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def verified_inventory() -> dict[str, Any]:
    trust = load_json(ROOT / "evidence/inventory_trust.json")
    raw = load_json(ROOT / "evidence/inventory_snapshot.json")
    payload = {key: value for key, value in raw.items() if key not in {"key_id", "signature"}}
    expected = digest(canonical(payload) + str(trust.get("verification_material", "")).encode())
    if raw.get("key_id") != trust.get("key_id") or raw.get("signature") != expected:
        raise ValueError("inventory signature verification failed")
    if parse_time(str(payload["valid_until"])) <= parse_time(load_json(ROOT / "policy/replan_policy.json")["inventory_as_of"]):
        raise ValueError("inventory snapshot is stale")
    return payload


def events() -> tuple[list[dict[str, Any]], list[str]]:
    deliveries = []
    try:
        lines = (ROOT / "evidence/disruption_events.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read disruption events: {exc}") from exc
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed disruption event line {number}") from exc
        if not isinstance(row, dict) or not {"delivery_id", "event_id", "sequence", "kind", "object_id", "value"} <= set(row):
            raise ValueError(f"malformed disruption event line {number}")
        deliveries.append(row)
    unique: dict[str, dict[str, Any]] = {}
    ignored = []
    for row in sorted(deliveries, key=lambda item: (int(item["sequence"]), str(item["delivery_id"]))):
        event_id = str(row["event_id"])
        if event_id in unique:
            if {key: row[key] for key in ("sequence", "kind", "object_id", "value")} != {key: unique[event_id][key] for key in ("sequence", "kind", "object_id", "value")}:
                raise ValueError(f"conflicting duplicate event {event_id}")
            ignored.append(str(row["delivery_id"]))
        else:
            unique[event_id] = row
    return [unique[key] for key in sorted(unique, key=lambda key: int(unique[key]["sequence"]))], sorted(ignored)


def baseline(connection: sqlite3.Connection) -> tuple[list[dict[str, Any]], int]:
    objects = {row["object_id"]: dict(row) for row in rows(connection, "itinerary_objects", "object_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
    for item in rows(connection, "recovery_journal", "journal_id"):
        run = runs.get(item["recovery_id"])
        if run and (
            (run["status"] == "interrupted" and not item["restored"])
            or run["status"] in {"committed_local_proposal", "staged_local_only"}
        ):
            objects[item["object_id"]] = json.loads(item["before_json"])
    state = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
    return [objects[key] for key in sorted(objects)], int(state["source_revision"])


def assess_option(option: dict[str, Any], policy: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    segments = option["segments"]
    violations = []
    reviewed = {"LEG-1", "LEG-2"}
    preserved = {str(segment["segment_id"]) for segment in segments} & reviewed
    changed = len(reviewed - preserved)
    required_access = policy["traveler_constraints"]["accessibility_code"]
    if required_access not in set(option["accessibility_codes"]):
        violations.append("accessibility_support_missing")
    unauthorized = sorted(set(option["transit_countries"]) - set(policy["traveler_constraints"]["authorized_transit_countries"]))
    if unauthorized:
        violations.append("transit_authorization_missing:" + ",".join(unauthorized))
    if policy["traveler_constraints"]["checked_bags"] and option["checked_bag_mode"] != "through_checked":
        violations.append("checked_bag_recheck_not_permitted")
    for previous, following in zip(segments, segments[1:]):
        if previous["to"] != following["from"]:
            violations.append("broken_segment_continuity")
            continue
        minutes = int((parse_time(following["depart"]) - parse_time(previous["arrive"])).total_seconds() // 60)
        minimum = int(policy["minimum_connection_minutes"]["same_airport"])
        if minutes < minimum:
            violations.append(f"connection_below_{minimum}_minutes")
    arrival = parse_time(segments[-1]["arrive"])
    if arrival > parse_time(policy["arrival_curfew"]):
        violations.append("arrival_after_curfew")
    transfer_minutes = int(inventory["dependent_inventory"]["station_to_hotel_minutes"]) if segments[-1]["mode"] == "rail" else 60
    hotel_arrival = arrival + timedelta(minutes=transfer_minutes)
    if hotel_arrival > parse_time(policy["hotel_checkin_deadline"]):
        violations.append("hotel_checkin_deadline_missed")
    rest = parse_time(policy["event_arrival_deadline"]) - hotel_arrival
    if rest.total_seconds() / 60 < int(policy["required_rest_minutes_before_event"]):
        violations.append("event_rest_window_missed")
    if segments[-1]["mode"] == "air" and segments[-1]["to"] == "YVR":
        eligible = [slot for slot in inventory["dependent_inventory"]["shuttle_slots"] if required_access in slot["accessibility_codes"] and arrival <= parse_time(slot["latest_flight_arrival"])]
        if not eligible:
            violations.append("no_accessible_shuttle_connection")
    return {
        "option_id": option["option_id"],
        "feasible": not violations,
        "reviewed_air_legs_changed": changed,
        "incremental_cost_cad": option["incremental_cost_cad"],
        "violations": sorted(violations),
        "evidence_refs": sorted([f"evidence/inventory_snapshot.json#{option['option_id']}", "policy/replan_policy.json#constraints"]),
    }


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a caller-authored plan without exporting a complete answer builder."""
    candidate = load_json(path)
    policy = load_json(ROOT / "policy/replan_policy.json")
    manifest, source_bundle_hash = source_bundle()
    inventory = verified_inventory()
    applied_events, ignored = events()
    with sqlite3.connect(DB) as connection:
        source_objects, source_revision = baseline(connection)
    computed_assessments = [
        assess_option(option, policy, inventory) for option in inventory["options"]
    ]
    feasible = [row for row in computed_assessments if row["feasible"]]
    if not feasible:
        raise ValueError("no feasible replacement option")
    selected_assessment = min(feasible, key=lambda row: (row["reviewed_air_legs_changed"], row["incremental_cost_cad"], row["option_id"]))
    selected_id = selected_assessment["option_id"]
    selected = next(option for option in inventory["options"] if option["option_id"] == selected_id)
    last_arrival = parse_time(selected["segments"][-1]["arrive"])
    access = policy["traveler_constraints"]["accessibility_code"]
    eligible_slots = [slot for slot in inventory["dependent_inventory"]["shuttle_slots"] if access in slot["accessibility_codes"] and last_arrival <= parse_time(slot["latest_flight_arrival"])]
    shuttle = min(eligible_slots, key=lambda row: parse_time(row["pickup"]))
    original = {row["object_id"]: row for row in source_objects}
    selected_segments = {str(row["segment_id"]): row for row in selected["segments"]}
    event_by_kind = {str(row["kind"]): row for row in applied_events}
    cancelled = str(event_by_kind["segment_cancelled"]["value"])
    withdrawn_shuttle = str(event_by_kind["shuttle_slot_withdrawn"]["value"])
    checkpoint_payload = {
        "source_hashes": manifest["files"], "source_bundle_hash": source_bundle_hash,
        "source_revision": source_revision, "baseline_objects": source_objects,
    }
    got = normalized_plan(candidate)
    problems: list[str] = []
    if set(candidate) != PLAN_FIELDS:
        problems.append("plan schema differs [evidence: output contract]")
    assessments = candidate.get("option_assessments")
    if not isinstance(assessments, list) or any(
        not isinstance(row, dict) or set(row) != ASSESSMENT_FIELDS
        for row in assessments
    ):
        problems.append("option_assessments schema differs [evidence: output contract]")
    candidate_decisions = candidate.get("object_decisions")
    if not isinstance(candidate_decisions, list) or any(
        not isinstance(row, dict) or set(row) != DECISION_FIELDS
        for row in candidate_decisions
    ):
        problems.append("object_decisions schema differs [evidence: output contract]")
    global_expectations = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": digest(canonical(checkpoint_payload)),
        "inventory_snapshot_id": inventory["snapshot_id"],
        "selected_option_id": selected_id,
        "applied_event_ids": sorted(row["event_id"] for row in applied_events),
        "ignored_duplicate_delivery_ids": sorted(ignored),
        "external_actions_executed": False,
    }
    for key, expected in global_expectations.items():
        if got.get(key) != expected:
            problems.append(f"plan/global field {key} differs [evidence: policy, signed inventory, events, SQLite baseline]")

    candidate_assessments = {
        str(row.get("option_id")): row
        for row in got.get("option_assessments", [])
        if isinstance(row, dict)
    }
    option_ids = {str(option["option_id"]) for option in inventory["options"]}
    if set(candidate_assessments) != option_ids:
        problems.append(
            "option_assessments object IDs differ [evidence: signed inventory]"
        )
    for computed in computed_assessments:
        option_id = str(computed["option_id"])
        row = candidate_assessments.get(option_id)
        if row is None:
            continue
        for field in sorted(ASSESSMENT_FIELDS):
            if row.get(field) != computed[field]:
                problems.append(
                    f"option_assessments/{option_id} field {field} differs "
                    "[evidence: signed inventory and travel constraints]"
                )

    candidate_decisions_by_id = {
        str(row.get("object_id")): row
        for row in got.get("object_decisions", [])
        if isinstance(row, dict)
    }
    if set(candidate_decisions_by_id) != set(original):
        problems.append(
            "object_decisions object IDs differ [evidence: SQLite baseline]"
        )
    existing_inventory_objects = {
        str(item["inventory_object"]) for item in original.values()
    }
    for object_id in sorted(original):
        row = candidate_decisions_by_id.get(object_id)
        if row is None:
            continue
        source = original[object_id]
        object_type = str(source["object_type"])
        selected_object = str(source["inventory_object"])
        final_state = str(source["state"])
        action = "preserve"
        stage_kind = "none"
        refs = [f"state/travel.db#{object_id}"]
        if object_type == "air" and selected_object not in selected_segments:
            if selected_object != cancelled:
                raise ValueError(
                    f"selected itinerary unexpectedly drops valid air object {object_id}"
                )
            replacement = next(
                segment
                for segment in selected["segments"]
                if segment["segment_id"] not in existing_inventory_objects
            )
            selected_object = str(replacement["segment_id"])
            final_state = f"local_proposal_hold:{selected_object}"
            action = "replace_disrupted_leg"
            stage_kind = "hold_request"
            refs = [
                f"evidence/disruption_events.jsonl#{event_by_kind['segment_cancelled']['event_id']}",
                f"evidence/inventory_snapshot.json#{selected_id}",
            ]
        elif object_type == "air":
            refs.append(f"evidence/inventory_snapshot.json#{selected_id}")
        elif object_type == "shuttle" and selected_object == withdrawn_shuttle:
            selected_object = str(shuttle["slot_id"])
            final_state = f"local_proposal_hold:{selected_object}"
            action = "replace_with_accessible_slot"
            stage_kind = "hold_request"
            refs = [
                f"evidence/disruption_events.jsonl#{event_by_kind['shuttle_slot_withdrawn']['event_id']}",
                f"evidence/inventory_snapshot.json#{selected_object}",
            ]
        elif object_type == "refund":
            selected_object = cancelled
            final_state = f"local_request_staged:{cancelled}"
            action = "stage_refund_request"
            stage_kind = "request"
            refs = [
                f"evidence/disruption_events.jsonl#{event_by_kind['segment_cancelled']['event_id']}",
                "policy/replan_policy.json#stage_boundary",
            ]
        elif object_type == "hotel":
            refs.append(
                f"evidence/disruption_events.jsonl#{event_by_kind['hotel_late_checkin_confirmed']['event_id']}"
            )
        elif object_type in {"rail", "event"}:
            refs.append(f"evidence/inventory_snapshot.json#{selected_id}")
        else:
            refs.append("policy/replan_policy.json#stage_boundary")
        expected_fields = {
            "object_id": object_id,
            "prior_state": source["state"],
            "final_state": final_state,
            "action": action,
            "selected_inventory_object": selected_object,
            "local_stage_kind": stage_kind,
            "evidence_refs": sorted(refs),
            "external_action": "none",
        }
        for field in sorted(DECISION_FIELDS):
            if row.get(field) != expected_fields[field]:
                problems.append(
                    f"object_decisions/{object_id} field {field} differs "
                    "[evidence: events, selected option, and SQLite baseline]"
                )
    if problems:
        raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
    return got, {
        "policy": policy,
        "inventory": inventory,
        "baseline": source_objects,
        "source_revision": source_revision,
        "duplicates": ignored,
        "selected": selected,
    }


def normalized_plan(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["applied_event_ids"] = sorted(value.get("applied_event_ids", [])) if isinstance(value.get("applied_event_ids"), list) else value.get("applied_event_ids")
    result["ignored_duplicate_delivery_ids"] = sorted(value.get("ignored_duplicate_delivery_ids", [])) if isinstance(value.get("ignored_duplicate_delivery_ids"), list) else value.get("ignored_duplicate_delivery_ids")
    for container, key in (("option_assessments", "option_id"), ("object_decisions", "object_id")):
        normalized = []
        for raw in value.get(container, []) if isinstance(value.get(container), list) else []:
            row = dict(raw) if isinstance(raw, dict) else raw
            if isinstance(row, dict):
                for set_field in ("violations", "evidence_refs"):
                    if isinstance(row.get(set_field), list):
                        row[set_field] = sorted(row[set_field])
            normalized.append(row)
        result[container] = sorted(normalized, key=lambda row: str(row.get(key)) if isinstance(row, dict) else "")
    return result


def recover_interrupted(connection: sqlite3.Connection) -> list[str]:
    recovered = []
    for run in rows(connection, "recovery_runs", "recovery_id"):
        if run["status"] != "interrupted":
            continue
        journal = connection.execute("SELECT journal_id,object_id,before_json FROM recovery_journal WHERE recovery_id=? AND restored=0 ORDER BY journal_id", (run["recovery_id"],)).fetchall()
        for journal_id, object_id, before_json in journal:
            before = json.loads(before_json)
            columns = sorted(before)
            connection.execute(f"UPDATE itinerary_objects SET {', '.join(f'{key}=?' for key in columns)} WHERE object_id=?", [before[key] for key in columns] + [object_id])
            connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
        connection.execute("UPDATE recovery_runs SET status='rolled_back_recovered' WHERE recovery_id=?", (run["recovery_id"],))
        recovered.append(run["recovery_id"])
    return recovered


def preview(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    with sqlite3.connect(DB) as connection:
        pending = [
            row["recovery_id"]
            for row in rows(connection, "recovery_runs", "recovery_id")
            if row["status"] == "interrupted"
        ]
    value = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "valid",
        "inventory_signature_verified": True, "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_digest": digest(canonical(plan)), "selected_option_id": plan["selected_option_id"],
        "feasible_option_ids": sorted(row["option_id"] for row in plan["option_assessments"] if row["feasible"]),
        "changed_object_ids": sorted(row["object_id"] for row in plan["object_decisions"] if row["action"] != "preserve"),
        "interrupted_recoveries_pending": pending,
        "external_actions_executed": False,
    }
    write_json(ROOT / ".trip_preview.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))


def object_digest(connection: sqlite3.Connection) -> str:
    return digest(canonical(rows(connection, "itinerary_objects", "object_id")))


def project_objects(plan: dict[str, Any], baseline_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Project an already validated candidate onto its recovered baseline."""
    projected = {row["object_id"]: dict(row) for row in baseline_rows}
    for decision in plan["object_decisions"]:
        item = projected[decision["object_id"]]
        if decision["final_state"] != item["state"] or decision["selected_inventory_object"] != item["inventory_object"]:
            item.update(
                state=decision["final_state"],
                inventory_object=decision["selected_inventory_object"],
                version=int(item["version"]) + 1,
            )
    return projected


def apply(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    final_objects = project_objects(plan, facts["baseline"])
    with sqlite3.connect(DB) as connection:
        existing = connection.execute("SELECT status,source_checkpoint,semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if existing and existing[0] in {"committed_local_proposal", "staged_local_only"}:
            if existing[1:] == (plan["source_checkpoint"], plan_hash):
                print(json.dumps({"status": "idempotent", "recovery_id": plan["recovery_id"]}))
                return
            raise ValueError("conflict: recovery identity already committed with a different checkpoint or semantic plan")
        connection.execute("BEGIN IMMEDIATE")
        recovered = recover_interrupted(connection)
        for decision in plan["object_decisions"]:
            object_id = decision["object_id"]
            cursor = connection.execute("SELECT * FROM itinerary_objects WHERE object_id=?", (object_id,))
            columns = [item[0] for item in cursor.description]
            before_tuple = cursor.fetchone()
            if before_tuple is None:
                raise ValueError(f"object disappeared during apply: {object_id}")
            before = dict(zip(columns, before_tuple, strict=True))
            connection.execute("INSERT INTO recovery_journal(recovery_id,object_id,before_json,restored) VALUES (?,?,?,0)", (plan["recovery_id"], object_id, canonical(before).decode().strip()))
            final = final_objects[object_id]
            update_columns = sorted(final)
            connection.execute(f"UPDATE itinerary_objects SET {', '.join(f'{key}=?' for key in update_columns)} WHERE object_id=?", [final[key] for key in update_columns] + [object_id])
        final_revision = facts["source_revision"] + 1
        connection.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?,?,0)", (plan["recovery_id"], "committed_local_proposal", plan["source_checkpoint"], plan_hash, "", final_revision))
        connection.execute("UPDATE system_state SET value=? WHERE key='current_revision'", (str(final_revision),))
        connection.execute("UPDATE system_state SET value='committed_local_proposal' WHERE key='stage_state'")
        db_hash = object_digest(connection)
        connection.execute("UPDATE recovery_runs SET semantic_db_digest=? WHERE recovery_id=?", (db_hash, plan["recovery_id"]))
        connection.commit()
    print(json.dumps({"status": "committed_local_proposal", "recovered_runs": recovered, "recovery_id": plan["recovery_id"]}))


def verification_payload(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    plan, facts = validate_plan(plan_path)
    with sqlite3.connect(DB) as connection:
        db_hash = object_digest(connection)
    plan_hash = digest(canonical(plan))
    value = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass",
        "checks": {
            "source_checkpoint_matches": True, "semantic_plan_matches": True,
            "inventory_snapshot_verified": True, "event_delivery_deduplicated": True,
            "minimum_change_then_cost_objective": True, "object_projection_exact": True,
            "interrupted_journal_recovered": True, "single_committed_recovery": True,
            "local_only": True,
        },
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "semantic_db_digest": db_hash, "final_revision": facts["source_revision"] + 1,
        "external_actions_executed": False,
    }
    return value, facts, plan_hash, db_hash


def verify(plan_path: Path) -> None:
    value, facts, plan_hash, db_hash = verification_payload(plan_path)
    plan, _ = validate_plan(plan_path)
    final_objects = project_objects(plan, facts["baseline"])
    with sqlite3.connect(DB) as connection:
        objects = {row["object_id"]: row for row in rows(connection, "itinerary_objects", "object_id")}
        runs_by_id = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
        journal = rows(connection, "recovery_journal", "journal_id")
        system = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
    problems = []
    if objects != final_objects:
        problems.append("itinerary object projection differs")
    run = runs_by_id.get(facts["policy"]["recovery_id"], {})
    if run.get("status") not in {"committed_local_proposal", "staged_local_only"}:
        problems.append("recovery is not committed")
    if run.get("source_checkpoint") != plan["source_checkpoint"] or run.get("semantic_plan_digest") != plan_hash or run.get("semantic_db_digest") != db_hash:
        problems.append("recovery hashes do not close")
    if any(row["status"] == "interrupted" for row in runs_by_id.values()) or any(not row["restored"] for row in journal if row["recovery_id"] != facts["policy"]["recovery_id"]):
        problems.append("interrupted journal was not recovered")
    if system.get("current_revision") != str(facts["source_revision"] + 1):
        problems.append("revision differs")
    if problems:
        raise ValueError("verification failed:\n- " + "\n- ".join(problems))
    write_json(ROOT / "state/verification.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))


def itinerary_ics(plan: dict[str, Any], facts: dict[str, Any]) -> str:
    selected = next(option for option in facts["inventory"]["options"] if option["option_id"] == plan["selected_option_id"])
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HarnessBench//Travel Recovery 132//EN", "CALSCALE:GREGORIAN"]
    for segment in selected["segments"]:
        start = parse_time(segment["depart"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end = parse_time(segment["arrive"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines.extend(["BEGIN:VEVENT", f"UID:{facts['policy']['recovery_id']}-{segment['segment_id']}@local.invalid", f"DTSTART:{start}", f"DTEND:{end}", f"SUMMARY:PROPOSED {segment['mode'].upper()} {segment['from']} to {segment['to']}", "STATUS:TENTATIVE", "END:VEVENT"])
    lines.extend(["END:VCALENDAR", ""])
    # Repository text normalization is LF-based.  Emitting LF here keeps the
    # staged calendar byte-stable after a fresh Linux checkout as well as in
    # the authoring worktree.
    return "\n".join(lines)


def stage(plan_path: Path) -> None:
    verification, facts, plan_hash, db_hash = verification_payload(plan_path)
    if load_json(ROOT / "state/verification.json") != verification:
        raise ValueError("run verify before stage; verification is missing or stale")
    plan, _ = validate_plan(plan_path)
    token_seed = {"recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash, "semantic_db_digest": db_hash, "stage_boundary": facts["policy"]["stage_boundary"]}
    holds = {
        row["object_id"]: digest(canonical({**token_seed, "object_id": row["object_id"]}))
        for row in plan["object_decisions"]
        if row["local_stage_kind"] == "hold_request"
    }
    requests = {
        row["object_id"]: digest(canonical({**token_seed, "object_id": row["object_id"]}))
        for row in plan["object_decisions"]
        if row["local_stage_kind"] == "request"
    }
    receipt = {
        "schema_version": 1, **token_seed, "status": "staged_local_only",
        "local_hold_tokens": holds,
        "local_request_tokens": requests,
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/stage_receipt.json", receipt)
    (ROOT / "itinerary.ics").write_text(itinerary_ics(plan, facts), encoding="utf-8", newline="")
    with sqlite3.connect(DB) as connection:
        current = connection.execute("SELECT status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        stage_state = connection.execute("SELECT value FROM system_state WHERE key='stage_state'").fetchone()
        if current != ("staged_local_only",) or stage_state != ("staged_local_only",):
            connection.execute("UPDATE recovery_runs SET status='staged_local_only' WHERE recovery_id=?", (plan["recovery_id"],))
            connection.execute("UPDATE system_state SET value='staged_local_only' WHERE key='stage_state'")
            connection.commit()
    print(json.dumps(receipt, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    before_db = DB.read_bytes()
    receipt_path = ROOT / "state/stage_receipt.json"
    ics_path = ROOT / "itinerary.ics"
    before_receipt = receipt_path.read_bytes()
    before_ics = ics_path.read_bytes()
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    report = {
        "schema_version": 1, "recovery_id": load_json(plan_path)["recovery_id"], "status": "pass",
        "database_byte_stable": DB.read_bytes() == before_db,
        "receipt_byte_stable": receipt_path.read_bytes() == before_receipt,
        "itinerary_byte_stable": ics_path.read_bytes() == before_ics,
        "single_committed_recovery": True, "external_actions_executed": False,
    }
    if not all(report[key] for key in ("database_byte_stable", "receipt_byte_stable", "itinerary_byte_stable")):
        raise ValueError("semantic replay changed committed local artifacts")
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def inspect(as_json: bool) -> None:
    policy = load_json(ROOT / "policy/replan_policy.json")
    try:
        inventory = verified_inventory()
        verified = True
    except ValueError:
        inventory, verified = {}, False
    delivered, ignored = events()
    with sqlite3.connect(DB) as connection:
        objects = rows(connection, "itinerary_objects", "object_id")
        runs_list = rows(connection, "recovery_runs", "recovery_id")
        system = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
    value = {
        "recovery_id": policy.get("recovery_id"), "trip_id": policy.get("trip_id"),
        "inventory_snapshot_id": inventory.get("snapshot_id"), "inventory_verified": verified,
        "option_count": len(inventory.get("options", [])), "unique_event_ids": [row["event_id"] for row in delivered],
        "ignored_duplicate_delivery_ids": ignored,
        "objects": [{key: row[key] for key in ("object_id", "object_type", "state", "inventory_object", "version")} for row in objects],
        "runs": [{"recovery_id": row["recovery_id"], "status": row["status"]} for row in runs_list], "system_state": system,
    }
    print(json.dumps(value, indent=2, sort_keys=True) if as_json else "\n".join(f"{key}: {item}" for key, item in value.items()))


def query(table: str) -> None:
    allowed = {"itinerary_objects": "object_id", "recovery_runs": "recovery_id", "recovery_journal": "journal_id", "system_state": "key"}
    if table not in allowed:
        raise ValueError("query table must be one of: " + ", ".join(sorted(allowed)))
    with sqlite3.connect(DB) as connection:
        print(json.dumps(rows(connection, table, allowed[table]), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded offline itinerary recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("table")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("plan")
    args = parser.parse_args()
    if args.command == "inspect":
        inspect(args.json)
    elif args.command == "query":
        query(args.table)
    else:
        globals()[args.command]((ROOT / args.plan).resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
