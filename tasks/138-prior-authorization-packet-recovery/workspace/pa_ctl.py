#!/usr/bin/env python3
"""Guarded, synthetic, offline prior-authorization recovery controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/portal.db"
PLAN_KEYS = {"schema_version", "recovery_id", "source_checkpoint", "case_id", "event_dispositions", "packet", "attempt_actions", "external_actions_executed"}
EVENT_KEYS = {"delivery_id", "event_id", "event_type", "sequence", "disposition"}
PACKET_KEYS = {"patient_id", "member_id", "payer_id", "service_code", "diagnosis_code", "service_window", "authorization_window", "documents", "evidence_refs"}
ACTION_KEYS = {"attempt_id", "action", "protected_boundary"}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return value


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def table_rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def baseline() -> dict[str, Any]:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        cases = table_rows(connection, "cases", "case_id")
        attempts = {row["attempt_id"]: row for row in table_rows(connection, "attempts", "attempt_id")}
        queue = {row["queue_id"]: row for row in table_rows(connection, "local_queue", "queue_id")}
        runs = {row["recovery_id"]: row for row in table_rows(connection, "recovery_runs", "recovery_id")}
        journal = table_rows(connection, "recovery_journal", "journal_id")
        for entry in journal:
            run = runs.get(entry["recovery_id"])
            # Journal before-images remain the immutable source baseline after
            # rollback; ``restored`` records execution, not source revision.
            if run and run["status"] in {"interrupted", "rolled_back"}:
                before = json.loads(entry["before_json"])
                if entry["table_name"] == "attempts":
                    attempts[entry["record_id"]] = before
                elif entry["table_name"] == "local_queue":
                    queue[entry["record_id"]] = before
        journal_queue_ids = {
            entry["record_id"] for entry in journal if entry["table_name"] == "local_queue"
        }
        queue = {key: value for key, value in queue.items() if key in journal_queue_ids}
        system = dict(connection.execute("SELECT key,value FROM system_state"))
    return {"cases": cases, "attempts": [attempts[key] for key in sorted(attempts)], "queue": [queue[key] for key in sorted(queue)], "documents": load(ROOT / "evidence/documents.json")["documents"], "source_revision": int(system["source_revision"])}


def deliveries() -> list[dict[str, Any]]:
    result = []
    for line in (ROOT / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("event rows must be objects")
        result.append(value)
    return result


def checkpoint(base: dict[str, Any]) -> str:
    files = load(ROOT / "policy/source_manifest.json").get("files", {})
    actual = {str(name): sha((ROOT / str(name)).read_bytes()) for name in files}
    if actual != files:
        return "invalid-source-bundle"
    protected = [row for row in base["attempts"] if row["status"] in {"submitted", "denied", "partial_local"}]
    return sha(canonical({"source_hashes": actual, "source_revision": base["source_revision"], "cases": base["cases"], "protected_attempts": protected}))


def normalize(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    packet = dict(plan.get("packet", {})) if isinstance(plan.get("packet"), dict) else {}
    for key in ("documents", "evidence_refs"):
        if isinstance(packet.get(key), list):
            packet[key] = sorted(packet[key])
    result["packet"] = packet
    result["event_dispositions"] = sorted([dict(row) for row in plan.get("event_dispositions", []) if isinstance(row, dict)], key=lambda row: str(row.get("delivery_id")))
    result["attempt_actions"] = sorted([dict(row) for row in plan.get("attempt_actions", []) if isinstance(row, dict)], key=lambda row: str(row.get("attempt_id")))
    return result


def validate(plan: dict[str, Any]) -> tuple[dict[str, bool], dict[str, Any]]:
    """Validate a submitted candidate without constructing or returning a gold plan."""
    base = baseline()
    policy = load(ROOT / "policy/prior_auth_policy.json")
    case = next(
        row for row in base["cases"] if row["case_id"] == policy["target_case_id"]
    )
    events = deliveries()
    candidate = normalize(plan)
    exact_shape = set(plan) == PLAN_KEYS and isinstance(plan.get("packet"), dict) and set(plan["packet"]) == PACKET_KEYS and isinstance(plan.get("event_dispositions"), list) and all(isinstance(row, dict) and set(row) == EVENT_KEYS for row in plan["event_dispositions"]) and isinstance(plan.get("attempt_actions"), list) and all(isinstance(row, dict) and set(row) == ACTION_KEYS for row in plan["attempt_actions"])
    packet = candidate.get("packet", {})
    lists_valid = all(isinstance(packet.get(key), list) and len(packet[key]) == len(set(packet[key])) and all(isinstance(item, str) for item in packet[key]) for key in ("documents", "evidence_refs"))
    seen: set[str] = set()
    matching: list[dict[str, Any]] = []
    fixed: dict[str, str] = {}
    for event in events:
        event_id = str(event["event_id"])
        delivery_id = str(event["delivery_id"])
        if event_id in seen:
            fixed[delivery_id] = "duplicate_delivery_ignored"
            continue
        seen.add(event_id)
        if all(
            event.get(key) == case[key]
            for key in ("case_id", "patient_id", "member_id", "payer_id")
        ):
            matching.append(event)
        else:
            fixed[delivery_id] = "identity_mismatch_ignored"
    latest: dict[str, int] = {}
    for event in matching:
        kind = str(event["event_type"])
        latest[kind] = max(latest.get(kind, -1), int(event["sequence"]))
    supplied_events = {
        str(row.get("delivery_id")): row
        for row in candidate.get("event_dispositions", [])
        if isinstance(row, dict)
    }
    event_fields_ok = len(supplied_events) == len(events)
    for event in events:
        delivery_id = str(event["delivery_id"])
        disposition = fixed.get(delivery_id)
        if disposition is None:
            disposition = (
                "applied_current"
                if int(event["sequence"]) == latest[str(event["event_type"])]
                else "superseded_by_newer_sequence"
            )
        supplied = supplied_events.get(delivery_id, {})
        event_fields_ok &= all(
            supplied.get(key) == value
            for key, value in (
                ("delivery_id", event["delivery_id"]),
                ("event_id", event["event_id"]),
                ("event_type", event["event_type"]),
                ("sequence", int(event["sequence"])),
                ("disposition", disposition),
            )
        )
    current = {
        kind: next(
            event
            for event in matching
            if event["event_type"] == kind and int(event["sequence"]) == sequence
        )
        for kind, sequence in latest.items()
    }
    chosen_ids: list[str] = []
    for kind in policy["required_document_types"]:
        eligible = [
            row
            for row in base["documents"]
            if row.get("document_type") == kind
            and row.get("current") is True
            and row.get("signed") is True
            and row.get("patient_id") == case["patient_id"]
            and row.get("member_id") == case["member_id"]
            and row.get("service_code") == case["service_code"]
            and row.get("sensitive_category") is None
            and row.get("valid_through", "") >= policy["as_of"]
        ]
        eligible.sort(key=lambda row: (row["effective_at"], row["document_id"]))
        if eligible:
            chosen_ids.append(str(eligible[-1]["document_id"]))
    eligibility, order = current["eligibility"], current["order"]
    packet_fields_ok = all(
        packet.get(key) == value
        for key, value in (
            ("patient_id", case["patient_id"]),
            ("member_id", case["member_id"]),
            ("payer_id", case["payer_id"]),
            ("service_code", order["payload"]["service_code"]),
            ("diagnosis_code", case["diagnosis_code"]),
            ("service_window", {"from": case["service_from"], "to": case["service_to"]}),
            (
                "authorization_window",
                {
                    "from": max(case["service_from"], eligibility["payload"]["effective_from"]),
                    "to": min(policy["authorization_window_to"], eligibility["payload"]["effective_to"]),
                },
            ),
        )
    )
    evidence_refs = [f"evidence/documents.json#{item}" for item in chosen_ids]
    evidence_refs.extend(
        (
            f"evidence/events.jsonl#{eligibility['event_id']}",
            f"evidence/events.jsonl#{order['event_id']}",
            f"state/portal.db#cases:{case['case_id']}",
            "policy/prior_auth_policy.json#minimum_necessary",
        )
    )
    evidence_ok = packet.get("documents") == sorted(chosen_ids) and packet.get(
        "evidence_refs"
    ) == sorted(evidence_refs)
    boundary_by_status = {
        "partial_local": ("recover_partial_and_replace", "local_partial"),
        "submitted": ("preserve_submitted", "payer_submission_irreversible"),
        "denied": ("preserve_denied", "denial_record_irreversible"),
    }
    supplied_actions = {
        str(row.get("attempt_id")): row
        for row in candidate.get("attempt_actions", [])
        if isinstance(row, dict)
    }
    relevant_attempts = [
        row for row in base["attempts"] if row["status"] in boundary_by_status
    ]
    actions_ok = len(supplied_actions) == len(relevant_attempts)
    for attempt in relevant_attempts:
        action, boundary = boundary_by_status[attempt["status"]]
        supplied = supplied_actions.get(str(attempt["attempt_id"]), {})
        actions_ok &= all(
            supplied.get(key) == value
            for key, value in (
                ("attempt_id", attempt["attempt_id"]),
                ("action", action),
                ("protected_boundary", boundary),
            )
        )
    checks = {
        "schema_exact": exact_shape and lists_valid,
        "stable_identity": candidate.get("schema_version") == 1
        and candidate.get("recovery_id") == policy["recovery_id"]
        and candidate.get("case_id") == case["case_id"],
        "source_checkpoint_current": candidate.get("source_checkpoint") == checkpoint(base),
        "event_dispositions_exact": event_fields_ok,
        "identity_service_windows_exact": packet_fields_ok,
        "minimum_necessary_evidence": evidence_ok,
        "attempt_boundaries_exact": actions_ok,
        "local_only": candidate.get("external_actions_executed") is False,
    }
    return checks, base


def closure(plan: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    plan_hash, packet_hash = sha(canonical(plan)), sha(canonical(plan["packet"]))
    attempts = []
    for original in base["attempts"]:
        row = dict(original)
        if row["attempt_id"] == "ATT-PART-502":
            row.update(status="recovered_local_replacement", queue_id="Q-PA-502", packet_digest=packet_hash, version=int(row["version"]) + 1)
        attempts.append(row)
    queue = []
    for original in base["queue"]:
        row = dict(original)
        if row["queue_id"] == "Q-PART-502":
            row.update(status="recovered_abandoned", packet_digest=None)
        queue.append(row)
    queue.append({"queue_id": "Q-PA-502", "attempt_id": "ATT-PART-502", "status": "staged_offline", "packet_digest": packet_hash, "packet_json": canonical(plan["packet"]).decode().strip(), "transmitted": 0})
    queue.sort(key=lambda row: row["queue_id"])
    receipts = [{**row, "recovery_id": plan["recovery_id"], "external_action": 0} for row in plan["event_dispositions"]]
    state_hash = sha(canonical({"attempts": attempts, "queue": queue, "event_receipts": receipts}))
    return {"plan_hash": plan_hash, "packet_hash": packet_hash, "state_hash": state_hash, "attempts": attempts, "queue": queue, "receipts": receipts}


def inspect_state() -> int:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        value = {name: table_rows(connection, name, order) for name, order in (("cases", "case_id"), ("attempts", "attempt_id"), ("local_queue", "queue_id"), ("recovery_runs", "recovery_id"), ("recovery_journal", "journal_id"))}
        value["system_state"] = dict(connection.execute("SELECT key,value FROM system_state"))
        value["note"] = "Unrestored journal before-images are authoritative after an interrupted write."
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


def query(sql: str) -> int:
    statement = sql.strip()
    if not statement or ";" in statement.rstrip(";") or not statement.casefold().startswith(("select ", "pragma ")):
        print(json.dumps({"status": "rejected", "reason": "one read-only SELECT or PRAGMA is required"})); return 2
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            values = [dict(row) for row in connection.execute(statement).fetchmany(200)]
    except sqlite3.Error as exc:
        print(json.dumps({"status": "error", "reason": str(exc)})); return 2
    print(json.dumps({"status": "pass", "rows": values}, indent=2, sort_keys=True)); return 0


def requirements(case_id: str) -> int:
    base = baseline()
    policy = load(ROOT / "policy/prior_auth_policy.json")
    case = next(
        row for row in base["cases"] if row["case_id"] == policy["target_case_id"]
    )
    if case_id != case["case_id"]:
        print(json.dumps({"status": "not_found", "case_id": case_id})); return 2
    value = {"status": "pass", "case_id": case_id, "recovery_id": policy["recovery_id"], "source_checkpoint": checkpoint(base), "required_document_types": policy["required_document_types"], "selection_rules": ["match patient/member/payer/service identity", "current, signed, unexpired, least necessary", "exclude sensitive and superseded evidence"], "event_rule": "first delivery per event_id; highest sequence per event type", "attempts": [{"attempt_id": row["attempt_id"], "observed_status": row["status"]} for row in base["attempts"]], "journal_rule": "restore every unrestored interrupted before-image before projection", "external_boundary": "offline local queue only"}
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


def preview(name: str) -> int:
    try:
        plan = load(ROOT / name); checks, base = validate(plan); candidate = normalize(plan)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"status": "rejected", "errors": [str(exc)]})); return 2
    value = {"schema_version": 1, "recovery_id": candidate.get("recovery_id"), "status": "valid" if all(checks.values()) else "rejected", "checks": checks, "failed_checks": [key for key, passed in checks.items() if not passed], "source_checkpoint_match": candidate.get("source_checkpoint") == checkpoint(base), "semantic_plan_digest": sha(canonical(candidate)), "event_count": len(candidate.get("event_dispositions", [])), "document_count": len(candidate.get("packet", {}).get("documents", [])), "external_actions_executed": False}
    write(ROOT / ".pa_preview.json", value); print(json.dumps(value, indent=2, sort_keys=True)); return 0 if all(checks.values()) else 2


def apply(name: str) -> int:
    try:
        plan = normalize(load(ROOT / name)); checks, base = validate(plan)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)})); return 2
    if not all(checks.values()):
        print(json.dumps({"status": "rejected", "checks": checks}, indent=2)); return 2
    target = closure(plan, base)
    with sqlite3.connect(DB, timeout=5) as connection:
        connection.execute("PRAGMA foreign_keys=ON"); connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute("SELECT source_checkpoint,semantic_plan_digest,status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if existing:
            connection.rollback()
            if existing == (plan["source_checkpoint"], target["plan_hash"], "committed"):
                print(json.dumps({"status": "idempotent", "recovery_id": plan["recovery_id"]})); return 0
            print(json.dumps({"status": "conflict", "reason": "recovery identity already bound"})); return 3
        revision = int(connection.execute("SELECT value FROM system_state WHERE key='source_revision'").fetchone()[0])
        if revision != base["source_revision"]:
            connection.rollback(); print(json.dumps({"status": "stale", "reason": "source revision changed"})); return 4
        for recovery_id, in connection.execute("SELECT recovery_id FROM recovery_runs WHERE status='interrupted'"):
            for journal_id, table, record, before_text in connection.execute("SELECT journal_id,table_name,record_id,before_json FROM recovery_journal WHERE recovery_id=? AND restored=0 ORDER BY journal_id", (recovery_id,)).fetchall():
                before = json.loads(before_text)
                if table == "attempts":
                    connection.execute("UPDATE attempts SET case_id=?,status=?,transmitted_at=?,denial_at=?,payer_reference=?,queue_id=?,packet_digest=?,version=? WHERE attempt_id=?", tuple(before[key] for key in ("case_id", "status", "transmitted_at", "denial_at", "payer_reference", "queue_id", "packet_digest", "version")) + (record,))
                else:
                    connection.execute("UPDATE local_queue SET attempt_id=?,status=?,packet_digest=?,packet_json=?,transmitted=? WHERE queue_id=?", tuple(before[key] for key in ("attempt_id", "status", "packet_digest", "packet_json", "transmitted")) + (record,))
                connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
            connection.execute("UPDATE recovery_runs SET status='rolled_back' WHERE recovery_id=?", (recovery_id,))
        attempt = next(row for row in target["attempts"] if row["attempt_id"] == "ATT-PART-502")
        connection.execute("UPDATE attempts SET status=?,queue_id=?,packet_digest=?,version=? WHERE attempt_id=?", (attempt["status"], attempt["queue_id"], attempt["packet_digest"], attempt["version"], attempt["attempt_id"]))
        connection.execute("UPDATE local_queue SET status='recovered_abandoned',packet_digest=NULL WHERE queue_id='Q-PART-502'")
        queue = next(row for row in target["queue"] if row["queue_id"] == "Q-PA-502")
        connection.execute("INSERT INTO local_queue VALUES(?,?,?,?,?,?)", tuple(queue[key] for key in ("queue_id", "attempt_id", "status", "packet_digest", "packet_json", "transmitted")))
        for event in target["receipts"]:
            connection.execute("INSERT INTO event_receipts VALUES(?,?,?,?,?,?,?)", tuple(event[key] for key in ("delivery_id", "event_id", "event_type", "sequence", "disposition", "recovery_id", "external_action")))
        final_revision = revision + 1
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?,?,?)", (plan["recovery_id"], "committed", plan["source_checkpoint"], target["plan_hash"], target["state_hash"], final_revision, 0))
        connection.execute("UPDATE system_state SET value=? WHERE key='projection_revision'", (str(final_revision),)); connection.execute("UPDATE system_state SET value='applied' WHERE key='stage_state'"); connection.commit()
    print(json.dumps({"status": "applied", "recovery_id": plan["recovery_id"]}, indent=2)); return 0


def state_check(plan: dict[str, Any], base: dict[str, Any]) -> tuple[dict[str, bool], dict[str, Any]]:
    target = closure(plan, base)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        attempts = table_rows(connection, "attempts", "attempt_id"); queue = table_rows(connection, "local_queue", "queue_id"); receipts = table_rows(connection, "event_receipts", "delivery_id"); runs = {row["recovery_id"]: row for row in table_rows(connection, "recovery_runs", "recovery_id")}; journal = table_rows(connection, "recovery_journal", "journal_id"); system = dict(connection.execute("SELECT key,value FROM system_state"))
    run = runs.get(plan["recovery_id"], {}); actual = {row["attempt_id"]: row for row in attempts}; protected = {row["attempt_id"]: row for row in base["attempts"] if row["status"] in {"submitted", "denied"}}
    checks = {"attempt_projection_exact": attempts == target["attempts"], "local_queue_exact": queue == target["queue"], "event_receipts_exact": receipts == target["receipts"], "journal_restored": all(row["restored"] == 1 and runs[row["recovery_id"]]["status"] == "rolled_back" for row in journal), "semantic_identity_bound": run.get("status") == "committed" and run.get("source_checkpoint") == plan["source_checkpoint"] and run.get("semantic_plan_digest") == target["plan_hash"] and run.get("semantic_state_digest") == target["state_hash"], "irreversible_attempts_preserved": all(actual.get(key) == value for key, value in protected.items()), "source_revision_preserved": system.get("source_revision") == str(base["source_revision"]), "local_only": all(row["transmitted"] == 0 for row in queue) and run.get("external_actions_executed") == 0}
    return checks, target


def stage(name: str) -> int:
    try:
        plan = normalize(load(ROOT / name)); plan_checks, truth = validate(plan); checks, target = state_check(plan, truth)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)})); return 2
    if not all({**plan_checks, **checks}.values()):
        print(json.dumps({"status": "rejected", "checks": {**plan_checks, **checks}}, indent=2)); return 2
    packet = {"schema_version": 1, "queue_id": "Q-PA-502", "recovery_id": plan["recovery_id"], "case_id": plan["case_id"], "packet": plan["packet"], "status": "staged_offline", "transmitted": False, "clinical_decision_made": False}
    manifest = {"schema_version": 1, "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": target["plan_hash"], "semantic_state_digest": target["state_hash"], "packet_sha256": sha(canonical(packet)), "external_actions_executed": False}
    receipt = {"schema_version": 1, "recovery_id": plan["recovery_id"], "status": "staged_offline", "queue_id": "Q-PA-502", "packet_sha256": manifest["packet_sha256"], "manifest_sha256": sha(canonical(manifest)), "external_actions_executed": False}
    outputs = {ROOT / "staging/prior_auth_packet.json": packet, ROOT / "staging/packet_manifest.json": manifest, ROOT / "state/recovery_receipt.json": receipt}
    for path, value in outputs.items():
        if path.exists() and path.read_bytes() != json.dumps(value, indent=2, sort_keys=True).encode() + b"\n":
            print(json.dumps({"status": "conflict", "reason": f"{path.name} already has different content"})); return 3
    for path, value in outputs.items(): write(path, value)
    print(json.dumps({"status": "staged", "queue_id": "Q-PA-502", "transmitted": False}, indent=2)); return 0


def verify(name: str) -> int:
    try:
        plan = normalize(load(ROOT / name)); plan_checks, truth = validate(plan); checks, target = state_check(plan, truth); packet = load(ROOT / "staging/prior_auth_packet.json"); manifest = load(ROOT / "staging/packet_manifest.json"); receipt = load(ROOT / "state/recovery_receipt.json")
        packet_hash = sha(canonical(packet)); artifacts = {"packet_matches_plan": packet.get("packet") == plan["packet"], "packet_local_only": packet.get("transmitted") is False and packet.get("clinical_decision_made") is False, "packet_hash_closes": manifest.get("packet_sha256") == packet_hash, "manifest_identity_closes": manifest.get("source_checkpoint") == plan["source_checkpoint"] and manifest.get("semantic_plan_digest") == target["plan_hash"] and manifest.get("semantic_state_digest") == target["state_hash"], "receipt_closes": receipt.get("packet_sha256") == packet_hash and receipt.get("manifest_sha256") == sha(canonical(manifest)) and receipt.get("external_actions_executed") is False}
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"status": "fail", "reason": str(exc)})); return 2
    combined = {**plan_checks, **checks, **artifacts}; value = {"schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass" if all(combined.values()) else "fail", "checks": combined, "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": target["plan_hash"], "semantic_state_digest": target["state_hash"], "external_actions_executed": False}
    write(ROOT / "state/verification.json", value); print(json.dumps(value, indent=2, sort_keys=True)); return 0 if value["status"] == "pass" else 2


def replay(name: str) -> int:
    try:
        plan = normalize(load(ROOT / name)); plan_checks, truth = validate(plan); checks, target = state_check(plan, truth)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)})); return 2
    if not all({**plan_checks, **checks}.values()):
        print(json.dumps({"status": "conflict", "checks": {**plan_checks, **checks}}, indent=2)); return 3
    value = {"schema_version": 1, "recovery_id": plan["recovery_id"], "status": "idempotent_noop", "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": target["plan_hash"], "semantic_state_digest": target["state_hash"], "mutation_count": 0, "external_actions_executed": False}
    write(ROOT / "state/replay_report.json", value); print(json.dumps(value, indent=2, sort_keys=True)); return 0


def main() -> int:
    parser = argparse.ArgumentParser(); subs = parser.add_subparsers(dest="command", required=True); subs.add_parser("inspect"); q = subs.add_parser("query"); q.add_argument("sql"); req = subs.add_parser("requirements"); req.add_argument("case_id")
    for command in ("preview", "apply", "stage", "verify", "replay"):
        child = subs.add_parser(command); child.add_argument("plan")
    args = parser.parse_args(); commands = {"inspect": inspect_state, "query": lambda: query(args.sql), "requirements": lambda: requirements(args.case_id), "preview": lambda: preview(args.plan), "apply": lambda: apply(args.plan), "stage": lambda: stage(args.plan), "verify": lambda: verify(args.plan), "replay": lambda: replay(args.plan)}
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
