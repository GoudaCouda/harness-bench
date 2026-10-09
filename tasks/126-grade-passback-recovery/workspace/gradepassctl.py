#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/gradepass.db"
PLAN_FIELDS = {
    "schema_version", "passback_id", "source_checkpoint", "assignment_bindings",
    "result_actions", "duplicate_event_ids", "external_actions_executed",
}
BINDING_FIELDS = {
    "lms_line_item_id", "sis_assignment_id", "sis_section_id",
    "assignment_version", "score_maximum", "line_item_event_id",
}
ACTION_FIELDS = {
    "event_id", "source_sequence", "attempt_id", "lms_user_id",
    "sis_student_id", "sis_section_id", "sis_assignment_id",
    "assignment_version", "score_given", "score_maximum", "submitted_at",
    "disposition", "reason_code", "gradebook_action", "evidence_event_ids",
    "external_action",
}

SOURCE_LOCATORS = {
    "feed_event": "evidence/grade_feed.jsonl#event_id=<event_id>",
    "identity_rekey": "evidence/identity_rekeys.json#<section_rekeys|student_rekeys|student_merges>/<external_id>",
    "enrollment": "state/gradepass.db#enrollments/<student_id>|<section_id>",
    "assignment": "state/gradepass.db#assignments/<assignment_id>",
    "attempt": "state/gradepass.db#lms_attempts/<attempt_id>",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
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


def row_dict(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {description[0]: value for description, value in zip(cursor.description, row, strict=True)}


def table_rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    return [row_dict(cursor, row) for row in cursor.fetchall()]


def table_digest(connection: sqlite3.Connection, table: str, order: str) -> str:
    return digest(canonical(table_rows(connection, table, order)))


def source_bundle() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("source manifest is malformed")
    changed = []
    for relative, expected in manifest["files"].items():
        path = ROOT / str(relative)
        try:
            actual = digest(path.read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(relative))
    orders = {
        "students": "student_id", "sections": "section_id",
        "enrollments": "student_id, section_id", "identity_aliases": "alias_type, external_id",
        "assignments": "assignment_id", "lms_attempts": "attempt_id",
    }
    protected = manifest.get("protected_tables")
    if not isinstance(protected, dict):
        raise ValueError("source manifest lacks protected table digests")
    with sqlite3.connect(DB) as connection:
        for table, order in orders.items():
            if protected.get(table) != table_digest(connection, table, order):
                changed.append(f"state/gradepass.db#{table}")
        manual = connection.execute(
            "SELECT * FROM gradebook_results WHERE manual_override = 1 ORDER BY student_id, assignment_id"
        )
        manual_rows = [row_dict(manual, row) for row in manual.fetchall()]
        if protected.get("manual_overrides") != digest(canonical(manual_rows)):
            changed.append("state/gradepass.db#manual_overrides")
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    bundle = {
        "checkpoint_id": manifest.get("checkpoint_id"),
        "files": manifest["files"],
        "protected_tables": protected,
    }
    return manifest, digest(canonical(bundle))


def feed_events() -> tuple[list[dict[str, Any]], list[str]]:
    try:
        lines = (ROOT / "evidence/grade_feed.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read grade feed: {exc}") from exc
    deliveries: list[dict[str, Any]] = []
    line_item_fields = {
        "event_id", "event_type", "source_sequence", "lms_section_id",
        "lms_line_item_id", "assignment_version", "score_maximum",
    }
    result_fields = line_item_fields | {
        "attempt_id", "lms_user_id", "score_given", "submitted_at",
    }
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed grade feed line {number}: {exc}") from exc
        expected = line_item_fields if isinstance(row, dict) and row.get("event_type") == "line_item" else result_fields
        if not isinstance(row, dict) or set(row) != expected or row.get("event_type") not in {"line_item", "result"}:
            raise ValueError(f"grade feed line {number} has the wrong schema")
        deliveries.append(row)
    counts = Counter(str(row["event_id"]) for row in deliveries)
    unique: dict[str, dict[str, Any]] = {}
    for row in deliveries:
        event_id = str(row["event_id"])
        if event_id in unique and canonical(unique[event_id]) != canonical(row):
            raise ValueError(f"duplicate event {event_id} has conflicting payloads")
        unique[event_id] = row
    events = sorted(unique.values(), key=lambda row: (int(row["source_sequence"]), str(row["event_id"])))
    sequences = [int(row["source_sequence"]) for row in events]
    if sequences != list(range(1, len(events) + 1)):
        raise ValueError("unique feed source_sequence must form one contiguous checkpoint")
    return events, sorted(event_id for event_id, count in counts.items() if count > 1)


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def identity_maps(connection: sqlite3.Connection) -> tuple[dict[str, str], dict[str, str]]:
    evidence = load_json(ROOT / "evidence/identity_rekeys.json")
    sections = {
        str(row["external_id"]): str(row["canonical_id"])
        for row in evidence.get("section_rekeys", [])
        if isinstance(row, dict)
    }
    students: dict[str, str] = {}
    for key in ("student_rekeys", "student_merges"):
        for row in evidence.get(key, []):
            if isinstance(row, dict):
                students[str(row["external_id"])] = str(row["canonical_id"])
    database_rows = table_rows(connection, "identity_aliases", "alias_type, external_id")
    db_sections = {row["external_id"]: row["canonical_id"] for row in database_rows if row["alias_type"] == "section"}
    db_students = {row["external_id"]: row["canonical_id"] for row in database_rows if row["alias_type"] == "student"}
    if sections != db_sections or students != db_students:
        raise ValueError("identity rekey evidence disagrees with the protected SIS identity index")
    return sections, students


def recovery_inputs() -> dict[str, Any]:
    """Load verified source facts without constructing a candidate answer."""
    policy = load_json(ROOT / "policy/passback_policy.json")
    manifest, source_hash = source_bundle()
    events, duplicates = feed_events()
    with sqlite3.connect(DB) as connection:
        section_aliases, student_aliases = identity_maps(connection)
        students = {row["student_id"]: row for row in table_rows(connection, "students", "student_id")}
        enrollments = {
            (row["student_id"], row["section_id"]): row
            for row in table_rows(connection, "enrollments", "student_id, section_id")
        }
        assignments = table_rows(connection, "assignments", "assignment_id")
        attempts = {row["attempt_id"]: row for row in table_rows(connection, "lms_attempts", "attempt_id")}
    return {
        "policy": policy, "manifest": manifest, "source_hash": source_hash,
        "events": events, "duplicates": duplicates,
        "section_aliases": section_aliases, "student_aliases": student_aliases,
        "students": students, "enrollments": enrollments,
        "assignments": assignments, "attempts": attempts,
    }


def contract() -> None:
    """Publish the candidate schema and controlled vocabulary, never decisions."""
    policy = load_json(ROOT / "policy/passback_policy.json")
    value = {
        "schema_version": 1,
        "plan_top_level_fields": sorted(PLAN_FIELDS),
        "assignment_binding_fields": sorted(BINDING_FIELDS),
        "result_action_fields": sorted(ACTION_FIELDS),
        "set_fields": [
            "assignment_bindings",
            "duplicate_event_ids",
            "result_actions",
            "result_actions[].evidence_event_ids",
        ],
        "controlled_vocabularies": {
            "disposition": policy.get("disposition_vocabulary", []),
            "reason_code": policy.get("reason_code_vocabulary", []),
            "gradebook_action": policy.get("gradebook_action_vocabulary", []),
            "external_action": policy.get("external_action_vocabulary", []),
        },
        "source_locators": SOURCE_LOCATORS,
        "evidence_event_ids_rule": [
            "include the result event_id",
            "include the active line-item event_id when an assignment is resolvable",
        ],
    }
    print(json.dumps(value, indent=2, sort_keys=True))


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    result["assignment_bindings"] = sorted(
        [dict(row) for row in plan.get("assignment_bindings", []) if isinstance(row, dict)],
        key=lambda row: (str(row.get("sis_assignment_id")), str(row.get("lms_line_item_id"))),
    )
    actions = []
    for raw in plan.get("result_actions", []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        if isinstance(row.get("evidence_event_ids"), list):
            row["evidence_event_ids"] = sorted(row["evidence_event_ids"])
        actions.append(row)
    result["result_actions"] = sorted(actions, key=lambda row: str(row.get("event_id")))
    if isinstance(result.get("duplicate_event_ids"), list):
        result["duplicate_event_ids"] = sorted(result["duplicate_event_ids"])
    return result


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_candidate = load_json(path)
    candidate = normalized_plan(raw_candidate)
    facts = recovery_inputs()
    problems: list[str] = []
    if set(candidate) != PLAN_FIELDS:
        problems.append(f"top-level fields must be exactly {sorted(PLAN_FIELDS)}")
    if candidate.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if candidate.get("passback_id") != facts["policy"].get("passback_id"):
        problems.append("passback_id does not match policy")
    if candidate.get("source_checkpoint") != facts["manifest"].get("checkpoint_id"):
        problems.append("source_checkpoint does not match the immutable feed checkpoint")
    if candidate.get("external_actions_executed") is not False:
        problems.append("external_actions_executed must be false")
    raw_bindings = raw_candidate.get("assignment_bindings")
    bindings = candidate.get("assignment_bindings")
    if not isinstance(raw_bindings, list):
        problems.append("assignment_bindings must be an array of JSON objects")
    else:
        malformed = [
            index for index, row in enumerate(raw_bindings)
            if not isinstance(row, dict) or set(row) != BINDING_FIELDS
        ]
        if malformed:
            problems.append(
                f"assignment_bindings entries {malformed} must be objects with exactly "
                f"{sorted(BINDING_FIELDS)}"
            )
    raw_actions = raw_candidate.get("result_actions")
    actions = candidate.get("result_actions")
    if not isinstance(raw_actions, list):
        problems.append("result_actions must be an array of JSON objects")
    else:
        malformed = [
            index for index, row in enumerate(raw_actions)
            if not isinstance(row, dict) or set(row) != ACTION_FIELDS
        ]
        if malformed:
            problems.append(
                f"result_actions entries {malformed} must be objects with exactly "
                f"{sorted(ACTION_FIELDS)}"
            )
    if not isinstance(candidate.get("duplicate_event_ids"), list):
        problems.append("duplicate_event_ids must be an array")
    if problems:
        raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
    active = {
        row["lms_line_item_id"]: row
        for row in facts["assignments"]
        if row["status"] == "active"
    }
    line_items = [row for row in facts["events"] if row["event_type"] == "line_item"]
    by_assignment = {
        str(row.get("sis_assignment_id")): row for row in bindings
        if isinstance(row, dict)
    }
    binding_events: dict[str, str] = {}
    if len(by_assignment) != len(bindings):
        problems.append("assignment_bindings contains duplicate assignment identifiers")
    for assignment in sorted(active.values(), key=lambda row: row["assignment_id"]):
        matches = [
            row for row in line_items
            if row["lms_line_item_id"] == assignment["lms_line_item_id"]
            and int(row["assignment_version"]) == int(assignment["version"])
            and facts["section_aliases"].get(str(row["lms_section_id"])) == assignment["section_id"]
            and int(row["score_maximum"]) == int(assignment["points_possible"])
        ]
        if len(matches) != 1:
            raise ValueError(f"active assignment {assignment['assignment_id']} lacks one valid line-item event")
        item = matches[0]
        binding_events[assignment["lms_line_item_id"]] = str(item["event_id"])
        required = {
            "lms_line_item_id": assignment["lms_line_item_id"],
            "sis_assignment_id": assignment["assignment_id"],
            "sis_section_id": assignment["section_id"],
            "assignment_version": int(assignment["version"]),
            "score_maximum": int(assignment["points_possible"]),
            "line_item_event_id": item["event_id"],
        }
        got = by_assignment.get(str(assignment["assignment_id"]))
        if got is None:
            problems.append(
                f"line item {assignment['lms_line_item_id']} is missing its active assignment binding"
            )
            continue
        differing = sorted(field for field in BINDING_FIELDS if got.get(field) != required[field])
        if differing:
            problems.append(
                f"line item {assignment['lms_line_item_id']} / assignment "
                f"{assignment['assignment_id']} differs in fields: {', '.join(differing)}"
            )
    expected_assignment_ids = {str(row["assignment_id"]) for row in active.values()}
    extra_assignment_ids = sorted(set(by_assignment) - expected_assignment_ids)
    if extra_assignment_ids:
        problems.append(f"unexpected assignment binding identifiers: {extra_assignment_ids}")

    by_event = {str(row.get("event_id")): row for row in actions if isinstance(row, dict)}
    result_events = [row for row in facts["events"] if row["event_type"] == "result"]
    if len(by_event) != len(actions):
        problems.append("result_actions contains duplicate event identifiers")
    accepted = set(facts["policy"].get("accepted_dispositions", []))
    for event in result_events:
        section_id = facts["section_aliases"].get(str(event["lms_section_id"]))
        student_id = facts["student_aliases"].get(str(event["lms_user_id"]))
        assignment = active.get(str(event["lms_line_item_id"]))
        attempt = facts["attempts"].get(str(event["attempt_id"]))
        reason = "accepted_on_time"
        if section_id is None or student_id is None or student_id not in facts["students"]:
            reason = "unknown_identity"
        elif (student_id, section_id) not in facts["enrollments"] or facts["enrollments"][(student_id, section_id)]["status"] != "active":
            reason = "inactive_enrollment"
        elif assignment is None or assignment["section_id"] != section_id:
            reason = "unknown_assignment"
        elif int(event["assignment_version"]) != int(assignment["version"]):
            reason = "stale_assignment_version"
        elif int(event["score_maximum"]) != int(assignment["points_possible"]) or float(event["score_given"]) < 0 or float(event["score_given"]) > float(event["score_maximum"]):
            reason = "invalid_score_scale"
        elif attempt is None or any(attempt[field] != event[field] for field in ("lms_user_id", "lms_section_id", "lms_line_item_id", "assignment_version", "score_given", "score_maximum", "submitted_at")):
            reason = "attempt_mismatch"
        elif iso(str(event["submitted_at"])) > iso(str(assignment["late_accept_until"])):
            reason = "late_window_closed"
        elif iso(str(event["submitted_at"])) > iso(str(assignment["due_at"])):
            reason = "accepted_late"
        disposition = "accept" if reason in accepted else "quarantine"
        assignment_id = assignment["assignment_id"] if assignment and assignment["section_id"] == section_id else None
        evidence_ids = [str(event["event_id"])]
        if assignment is not None and assignment["lms_line_item_id"] in binding_events:
            evidence_ids.append(binding_events[assignment["lms_line_item_id"]])
        required = {
            "event_id": event["event_id"], "source_sequence": int(event["source_sequence"]),
            "attempt_id": event["attempt_id"], "lms_user_id": event["lms_user_id"],
            "sis_student_id": student_id, "sis_section_id": section_id,
            "sis_assignment_id": assignment_id, "assignment_version": int(event["assignment_version"]),
            "score_given": event["score_given"], "score_maximum": event["score_maximum"],
            "submitted_at": event["submitted_at"], "disposition": disposition,
            "reason_code": reason, "gradebook_action": "upsert_local" if disposition == "accept" else "quarantine_local",
            "evidence_event_ids": sorted(evidence_ids), "external_action": "none",
        }
        got = by_event.get(str(event["event_id"]))
        if got is None:
            problems.append(
                f"result event {event['event_id']} (student {event['lms_user_id']}, "
                f"line item {event['lms_line_item_id']}) is missing"
            )
            continue
        differing = sorted(field for field in ACTION_FIELDS if got.get(field) != required[field])
        if differing:
            problems.append(
                f"result event {event['event_id']} (student {event['lms_user_id']}, "
                f"line item {event['lms_line_item_id']}) differs in fields: {', '.join(differing)}"
            )
    expected_event_ids = {str(row["event_id"]) for row in result_events}
    extra_event_ids = sorted(set(by_event) - expected_event_ids)
    if extra_event_ids:
        problems.append(f"unexpected result event identifiers: {extra_event_ids}")
    if candidate.get("duplicate_event_ids") != facts["duplicates"]:
        problems.append("duplicate_event_ids does not match duplicate delivery evidence")
    if problems:
        raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
    return candidate, facts


def record_key(row: dict[str, Any]) -> str:
    return f"{row['sis_student_id']}|{row['sis_assignment_id']}"


def gradebook_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return table_rows(connection, "gradebook_results", "student_id, assignment_id")


def restore_row(connection: sqlite3.Connection, key: str, before_json: str) -> None:
    student_id, assignment_id = key.split("|", 1)
    if before_json == "null":
        connection.execute(
            "DELETE FROM gradebook_results WHERE student_id = ? AND assignment_id = ?",
            (student_id, assignment_id),
        )
        return
    row = json.loads(before_json)
    columns = (
        "student_id", "assignment_id", "score_given", "score_maximum", "submitted_at",
        "source_event_id", "passback_id", "status", "version", "manual_override",
    )
    connection.execute(
        f"INSERT OR REPLACE INTO gradebook_results ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        tuple(row[column] for column in columns),
    )


def baseline_gradebook(connection: sqlite3.Connection, facts: dict[str, Any]) -> list[dict[str, Any]]:
    rows = {(row["student_id"], row["assignment_id"]): row for row in gradebook_rows(connection)}
    ids = {facts["policy"].get("interrupted_passback_id"), facts["policy"].get("passback_id")}
    rollback = table_rows(connection, "rollback_rows", "passback_id, table_name, record_key")
    for item in rollback:
        if item["passback_id"] not in ids or item["table_name"] != "gradebook_results":
            continue
        student_id, assignment_id = item["record_key"].split("|", 1)
        key = (student_id, assignment_id)
        before = json.loads(item["before_json"])
        if before is None:
            rows.pop(key, None)
        else:
            rows[key] = before
    return sorted(rows.values(), key=lambda row: (row["student_id"], row["assignment_id"]))


def projected_gradebook(connection: sqlite3.Connection, plan: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    values = {(row["student_id"], row["assignment_id"]): dict(row) for row in baseline_gradebook(connection, facts)}
    for action in sorted(plan["result_actions"], key=lambda row: int(row["source_sequence"])):
        if action["disposition"] != "accept":
            continue
        key = (action["sis_student_id"], action["sis_assignment_id"])
        previous = values.get(key)
        version = int(previous["version"]) + 1 if previous else 1
        values[key] = {
            "student_id": key[0], "assignment_id": key[1],
            "score_given": action["score_given"], "score_maximum": action["score_maximum"],
            "submitted_at": action["submitted_at"], "source_event_id": action["event_id"],
            "passback_id": plan["passback_id"],
            "status": "late" if action["reason_code"] == "accepted_late" else "posted_local",
            "version": version, "manual_override": 0,
        }
    return sorted(values.values(), key=lambda row: (row["student_id"], row["assignment_id"]))


def event_rows(plan: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    actions = {row["event_id"]: row for row in plan["result_actions"]}
    rows = []
    for event in facts["events"]:
        action = actions.get(event["event_id"])
        rows.append({
            "event_id": event["event_id"], "event_type": event["event_type"],
            "source_sequence": int(event["source_sequence"]),
            "disposition": action["disposition"] if action else "line_item_observed",
            "payload_hash": digest(canonical(event)), "passback_id": plan["passback_id"],
        })
    return sorted(rows, key=lambda row: row["event_id"])


def quarantine_rows(plan: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {row["event_id"]: row for row in facts["events"]}
    return sorted([
        {
            "event_id": row["event_id"], "reason_code": row["reason_code"],
            "payload_hash": digest(canonical(by_id[row["event_id"]])),
            "passback_id": plan["passback_id"],
        }
        for row in plan["result_actions"] if row["disposition"] == "quarantine"
    ], key=lambda row: row["event_id"])


def projection_hash(connection: sqlite3.Connection) -> str:
    bundle = {
        "gradebook_results": gradebook_rows(connection),
        "processed_events": table_rows(connection, "processed_events", "event_id"),
        "quarantined_events": table_rows(connection, "quarantined_events", "event_id"),
        "rollback_rows": table_rows(connection, "rollback_rows", "passback_id, table_name, record_key"),
    }
    return digest(canonical(bundle))


def preview(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    accepted = [row for row in plan["result_actions"] if row["disposition"] == "accept"]
    quarantined = [row for row in plan["result_actions"] if row["disposition"] == "quarantine"]
    value = {
        "schema_version": 1, "passback_id": plan["passback_id"], "status": "valid",
        "source_checkpoint": plan["source_checkpoint"],
        "assignment_binding_count": len(plan["assignment_bindings"]),
        "unique_event_count": len(facts["events"]), "result_action_count": len(plan["result_actions"]),
        "accepted_event_ids": sorted(row["event_id"] for row in accepted),
        "quarantined_event_ids": sorted(row["event_id"] for row in quarantined),
        "duplicate_event_ids": plan["duplicate_event_ids"],
        "plan_hash": digest(canonical(plan)), "source_bundle_hash": facts["source_hash"],
        "external_actions_executed": False,
    }
    write_json(ROOT / ".gradepass_preview.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))


def recover_interrupted(connection: sqlite3.Connection, facts: dict[str, Any]) -> list[str]:
    interrupted_id = str(facts["policy"].get("interrupted_passback_id"))
    rows = connection.execute(
        "SELECT table_name, record_key, before_json FROM rollback_rows WHERE passback_id = ? AND restored = 0 ORDER BY table_name, record_key",
        (interrupted_id,),
    ).fetchall()
    restored = []
    for table_name, key, before_json in rows:
        if table_name != "gradebook_results":
            raise ValueError(f"unsupported interrupted rollback table: {table_name}")
        restore_row(connection, key, before_json)
        restored.append(key)
    if rows:
        connection.execute("UPDATE rollback_rows SET restored = 1 WHERE passback_id = ?", (interrupted_id,))
        connection.execute(
            "UPDATE recovery_runs SET status = 'rolled_back_recovered' WHERE passback_id = ? AND status = 'applying'",
            (interrupted_id,),
        )
    return restored


def apply(plan_path: Path) -> None:
    raw = load_json(plan_path)
    normalized = normalized_plan(raw)
    candidate_hash = digest(canonical(normalized))
    passback_id = raw.get("passback_id")
    if isinstance(passback_id, str) and DB.is_file():
        with sqlite3.connect(DB) as connection:
            prior = connection.execute(
                "SELECT status, plan_hash FROM recovery_runs WHERE passback_id = ?", (passback_id,)
            ).fetchone()
        if prior and prior[1] != candidate_hash:
            raise ValueError(f"conflicting replay for stable passback_id {passback_id}")
        if prior and prior[0] in {"applied_pending_verification", "staged_pending_registrar_review"}:
            validate_plan(plan_path)
            print(json.dumps({"passback_id": passback_id, "status": "idempotent_noop"}, sort_keys=True))
            return
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        connection.execute("BEGIN IMMEDIATE")
        recover_interrupted(connection, facts)
        accepted = [row for row in plan["result_actions"] if row["disposition"] == "accept"]
        seen_keys = set()
        for action in sorted(accepted, key=lambda row: int(row["source_sequence"])):
            key = record_key(action)
            if key not in seen_keys:
                existing = connection.execute(
                    "SELECT * FROM gradebook_results WHERE student_id = ? AND assignment_id = ?",
                    (action["sis_student_id"], action["sis_assignment_id"]),
                )
                row = existing.fetchone()
                before = row_dict(existing, row) if row else None
                connection.execute(
                    "INSERT INTO rollback_rows VALUES (?, 'gradebook_results', ?, ?, 0)",
                    (plan["passback_id"], key, json.dumps(before, sort_keys=True, separators=(",", ":"))),
                )
                seen_keys.add(key)
            prior = connection.execute(
                "SELECT version, manual_override FROM gradebook_results WHERE student_id = ? AND assignment_id = ?",
                (action["sis_student_id"], action["sis_assignment_id"]),
            ).fetchone()
            if prior and int(prior[1]) == 1:
                raise ValueError(f"accepted action would overwrite manual override {key}")
            version = int(prior[0]) + 1 if prior else 1
            values = (
                action["sis_student_id"], action["sis_assignment_id"], action["score_given"],
                action["score_maximum"], action["submitted_at"], action["event_id"],
                plan["passback_id"], "late" if action["reason_code"] == "accepted_late" else "posted_local",
                version, 0,
            )
            connection.execute("INSERT OR REPLACE INTO gradebook_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
        for row in event_rows(plan, facts):
            connection.execute(
                "INSERT INTO processed_events VALUES (?, ?, ?, ?, ?, ?)",
                tuple(row[key] for key in ("event_id", "event_type", "source_sequence", "disposition", "payload_hash", "passback_id")),
            )
        for row in quarantine_rows(plan, facts):
            connection.execute(
                "INSERT INTO quarantined_events VALUES (?, ?, ?, ?)",
                tuple(row[key] for key in ("event_id", "reason_code", "payload_hash", "passback_id")),
            )
        revision = int(facts["policy"]["target_revision"])
        connection.execute(
            "INSERT INTO recovery_runs VALUES (?, 'applied_pending_verification', ?, ?, '', ?, 0)",
            (plan["passback_id"], plan_hash, facts["source_hash"], revision),
        )
        connection.execute("UPDATE system_state SET value = ? WHERE key = 'projection_revision'", (str(revision),))
        connection.execute("UPDATE system_state SET value = 'local_applied_pending_verification' WHERE key = 'stage_state'")
        semantic_hash = projection_hash(connection)
        connection.execute(
            "UPDATE recovery_runs SET semantic_db_hash = ? WHERE passback_id = ?",
            (semantic_hash, plan["passback_id"]),
        )
        connection.commit()
    print(json.dumps({"passback_id": plan["passback_id"], "status": "applied", "restored_interrupted": True}, sort_keys=True))


def database_matches(connection: sqlite3.Connection, plan: dict[str, Any], facts: dict[str, Any]) -> bool:
    return (
        gradebook_rows(connection) == projected_gradebook(connection, plan, facts)
        and table_rows(connection, "processed_events", "event_id") == event_rows(plan, facts)
        and table_rows(connection, "quarantined_events", "event_id") == quarantine_rows(plan, facts)
    )


def verification_value(plan: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    with sqlite3.connect(DB) as connection:
        run = connection.execute(
            "SELECT status, plan_hash, source_bundle_hash, semantic_db_hash, revision, external_actions_executed FROM recovery_runs WHERE passback_id = ?",
            (plan["passback_id"],),
        ).fetchone()
        interrupted = connection.execute(
            "SELECT status FROM recovery_runs WHERE passback_id = ?",
            (facts["policy"]["interrupted_passback_id"],),
        ).fetchone()
        semantic_hash = projection_hash(connection)
        db_exact = database_matches(connection, plan, facts)
    plan_hash = digest(canonical(plan))
    checks = {
        "plan_hash_matches": bool(run and run[1] == plan_hash),
        "source_bundle_matches": bool(run and run[2] == facts["source_hash"]),
        "semantic_db_matches": bool(run and run[3] == semantic_hash and db_exact),
        "event_journal_exact": db_exact,
        "quarantine_exact": db_exact,
        "interrupted_run_recovered": bool(interrupted and interrupted[0] == "rolled_back_recovered"),
        "local_only": bool(run and run[5] == 0),
    }
    return {
        "schema_version": 1, "passback_id": plan["passback_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "status": "pass" if all(checks.values()) else "fail", "checks": checks,
        "plan_hash": plan_hash, "source_bundle_hash": facts["source_hash"],
        "semantic_db_hash": semantic_hash,
        "projection_revision": int(run[4]) if run else None,
        "external_actions_executed": False,
    }


def verify(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    value = verification_value(plan, facts)
    write_json(ROOT / "state/verification.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))
    if value["status"] != "pass":
        raise ValueError("verification failed")


def receipt_value(plan: dict[str, Any], facts: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    token_input = {
        "passback_id": plan["passback_id"], "source_checkpoint": plan["source_checkpoint"],
        "plan_hash": verification["plan_hash"], "source_bundle_hash": facts["source_hash"],
        "semantic_db_hash": verification["semantic_db_hash"],
        "verification_hash": digest(canonical(verification)),
        "stage_boundary": "local_only_pending_registrar_review",
    }
    return {
        "schema_version": 1, **token_input,
        "status": "staged_pending_registrar_review",
        "stage_token": digest(canonical(token_input)), "external_actions_executed": False,
    }


def stage(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    verification = verification_value(plan, facts)
    if verification.get("status") != "pass":
        raise ValueError("cannot stage before exact verification")
    receipt = receipt_value(plan, facts, verification)
    with sqlite3.connect(DB) as connection:
        run = connection.execute(
            "SELECT plan_hash FROM recovery_runs WHERE passback_id = ?", (plan["passback_id"],)
        ).fetchone()
        if not run or run[0] != verification["plan_hash"]:
            raise ValueError("recovery run identity does not match plan")
        connection.execute(
            "UPDATE recovery_runs SET status = 'staged_pending_registrar_review' WHERE passback_id = ?",
            (plan["passback_id"],),
        )
        connection.execute("UPDATE system_state SET value = 'staged_pending_registrar_review' WHERE key = 'stage_state'")
        connection.commit()
    write_json(ROOT / "state/verification.json", verification)
    write_json(ROOT / "state/stage_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    before_db = DB.read_bytes()
    receipt_path = ROOT / "state/stage_receipt.json"
    before_receipt = receipt_path.read_bytes() if receipt_path.is_file() else b""
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    plan, facts = validate_plan(plan_path)
    after_receipt = receipt_path.read_bytes() if receipt_path.is_file() else b""
    value = {
        "schema_version": 1, "passback_id": plan["passback_id"], "status": "pass",
        "database_byte_stable": before_db == DB.read_bytes(),
        "receipt_byte_stable": before_receipt == after_receipt,
        "semantic_db_hash": verification_value(plan, facts)["semantic_db_hash"],
        "external_actions_executed": False,
    }
    if not value["database_byte_stable"] or not value["receipt_byte_stable"]:
        value["status"] = "fail"
    write_json(ROOT / "state/replay_report.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))
    if value["status"] != "pass":
        raise ValueError("replay was not byte-stable")


def inspect() -> None:
    manifest, source_hash = source_bundle()
    events, duplicates = feed_events()
    with sqlite3.connect(DB) as connection:
        runs = table_rows(connection, "recovery_runs", "passback_id")
        summary = {
            "source_checkpoint": manifest.get("checkpoint_id"), "source_bundle_hash": source_hash,
            "delivery_count": len((ROOT / "evidence/grade_feed.jsonl").read_text().splitlines()),
            "unique_event_count": len(events), "duplicate_event_ids": duplicates,
            "students": len(table_rows(connection, "students", "student_id")),
            "active_enrollments": sum(row["status"] == "active" for row in table_rows(connection, "enrollments", "student_id, section_id")),
            "assignments": len(table_rows(connection, "assignments", "assignment_id")),
            "attempts": len(table_rows(connection, "lms_attempts", "attempt_id")),
            "gradebook_rows": len(gradebook_rows(connection)), "recovery_runs": runs,
            "external_actions_available": False,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


def query(kind: str) -> None:
    choices = {
        "roster": ("students", "student_id"),
        "enrollments": ("enrollments", "student_id, section_id"),
        "aliases": ("identity_aliases", "alias_type, external_id"),
        "assignments": ("assignments", "assignment_id"),
        "attempts": ("lms_attempts", "attempt_id"),
        "gradebook": ("gradebook_results", "student_id, assignment_id"),
        "recovery-runs": ("recovery_runs", "passback_id"),
        "rollback": ("rollback_rows", "passback_id, table_name, record_key"),
    }
    table, order = choices[kind]
    with sqlite3.connect(DB) as connection:
        print(json.dumps(table_rows(connection, table, order), indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded offline LMS-to-SIS grade-passback recovery")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    commands.add_parser("contract")
    query_parser = commands.add_parser("query")
    query_parser.add_argument("kind", choices=["roster", "enrollments", "aliases", "assignments", "attempts", "gradebook", "recovery-runs", "rollback"])
    for name in ("preview", "apply", "verify", "stage", "replay"):
        child = commands.add_parser(name)
        child.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            inspect()
        elif args.command == "contract":
            contract()
        elif args.command == "query":
            query(args.kind)
        elif args.command == "preview":
            preview(args.plan)
        elif args.command == "apply":
            apply(args.plan)
        elif args.command == "verify":
            verify(args.plan)
        elif args.command == "stage":
            stage(args.plan)
        elif args.command == "replay":
            replay(args.plan)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"gradepassctl: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
