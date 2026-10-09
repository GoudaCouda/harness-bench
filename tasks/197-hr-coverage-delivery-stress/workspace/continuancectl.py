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
DB = ROOT / "state/continuance.db"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "as_of",
    "case_decisions", "journal_actions", "queue_totals",
    "external_notices_sent", "coverage_changed",
}
DECISION_FIELDS = {
    "case_id", "baseline_state", "disposition", "notice_version",
    "address_version", "beneficiary_keys", "delivery_evidence",
    "deadline_state", "next_local_action", "evidence_refs",
}
JOURNAL_FIELDS = {"journal_id", "table_name", "record_id", "action"}
QUEUE_FIELDS = {"corrected_notice", "reissue", "delivery_investigation", "compliance_review"}
TABLES = {
    "cases", "beneficiaries", "notices", "delivery_attempts", "recovery_queue",
    "decision_receipts", "recovery_runs", "recovery_journal", "system_state",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain one JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    values: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSONL at {path.name}:{number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL at {path.name}:{number}")
        values.append(value)
    return values


def write_object(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def source_bundle() -> tuple[dict[str, str], str]:
    manifest = read_object(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source manifest schema is invalid")
    hashes: dict[str, str] = {}
    changed = []
    for relative, wanted in files.items():
        try:
            actual = digest((ROOT / str(relative)).read_bytes())
        except OSError:
            actual = "missing"
        hashes[str(relative)] = actual
        if actual != wanted:
            changed.append(str(relative))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return hashes, digest(canonical(hashes))


def restored_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables != TABLES:
        raise ValueError("database schema mismatch")
    cases = {row["case_id"]: row for row in rows(connection, "cases", "case_id")}
    queue = {row["queue_id"]: row for row in rows(connection, "recovery_queue", "queue_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
    journal = rows(connection, "recovery_journal", "journal_id")
    for entry in journal:
        run = runs.get(str(entry["recovery_id"]))
        if not run or run["status"] != "interrupted" or entry["restored"]:
            continue
        target = cases if entry["table_name"] == "cases" else queue
        before = json.loads(entry["before_json"]) if entry["before_json"] else None
        if before is None:
            target.pop(str(entry["record_id"]), None)
        else:
            target[str(entry["record_id"])] = before
    committed = {key for key, row in runs.items() if row["status"] == "committed"}
    queue = {key: row for key, row in queue.items() if row["recovery_id"] not in committed}
    return {
        "cases": [cases[key] for key in sorted(cases)],
        "beneficiaries": rows(connection, "beneficiaries", "case_id,person_key"),
        "notices": rows(connection, "notices", "notice_id"),
        "attempts": rows(connection, "delivery_attempts", "attempt_id"),
        "queue": [queue[key] for key in sorted(queue)],
        "runs": list(runs.values()),
        "journal": journal,
        "system": dict(connection.execute("SELECT key,value FROM system_state")),
    }


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize_locator(value: str) -> str:
    return value.replace("#cases:", "#case:").replace("#event_id:", "#event:")


def normalize_plan(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    decisions = []
    raw = value.get("case_decisions")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            for field in ("beneficiary_keys", "evidence_refs"):
                if isinstance(row.get(field), list):
                    row[field] = sorted({normalize_locator(str(part)) for part in row[field]})
            decisions.append(row)
    result["case_decisions"] = sorted(decisions, key=lambda row: str(row.get("case_id")))
    raw_journal = value.get("journal_actions")
    result["journal_actions"] = sorted(
        [dict(item) for item in raw_journal if isinstance(item, dict)] if isinstance(raw_journal, list) else [],
        key=lambda row: str(row.get("journal_id")),
    )
    return result


def checkpoint(snapshot: dict[str, Any], hashes: dict[str, str]) -> str:
    return digest(canonical({
        "source_hashes": hashes,
        "source_revision": int(snapshot["system"]["source_revision"]),
        "cases": snapshot["cases"], "beneficiaries": snapshot["beneficiaries"],
        "notices": snapshot["notices"], "attempts": snapshot["attempts"],
        "queue_after_rollback": snapshot["queue"],
    }))


def case_evidence(case_id: str, notice_id: str | None, events: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> list[str]:
    refs = {
        f"state/continuance.db#case:{case_id}",
        f"state/stale_checkpoint.json#cases/{case_id}",
        "policy/continuance_policy.json#decision_precedence",
    }
    if notice_id:
        refs.add(f"state/continuance.db#notices:{notice_id}")
    refs.update(f"evidence/eligibility_events.jsonl#event:{row['event_id']}" for row in events if row.get("case_id") == case_id)
    refs.update(f"evidence/delivery_receipts.jsonl#receipt:{row['receipt_id']}" for row in receipts if row.get("notice_id") == notice_id)
    return sorted(refs)


def assess_candidate(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    """Compare caller-authored fields to evidence-derived controls without exporting corrections."""
    policy = read_object(ROOT / "policy/continuance_policy.json")
    hashes, _ = source_bundle()
    events = read_jsonl(ROOT / "evidence/eligibility_events.jsonl")
    receipts = read_jsonl(ROOT / "evidence/delivery_receipts.jsonl")
    with sqlite3.connect(DB) as connection:
        snapshot = restored_snapshot(connection)
    wanted_checkpoint = checkpoint(snapshot, hashes)
    plan = normalize_plan(raw)
    discrepancies: list[dict[str, str]] = []

    def mismatch(scope: str, identity: str, field: str, code: str = "candidate_mismatch") -> None:
        discrepancies.append({"scope": scope, "id": identity, "field": field, "code": code})

    if set(raw) != PLAN_FIELDS:
        mismatch("plan", "root", "fields", "schema_fields")
    fixed = {
        "schema_version": 1, "recovery_id": policy["recovery_id"],
        "source_checkpoint": wanted_checkpoint, "as_of": policy["as_of"],
        "external_notices_sent": False, "coverage_changed": False,
    }
    for field, expected in fixed.items():
        if plan.get(field) != expected:
            mismatch("plan", "root", field)

    decision_values = plan.get("case_decisions", [])
    by_id = {str(item.get("case_id")): item for item in decision_values if isinstance(item, dict)}
    cases = {row["case_id"]: row for row in snapshot["cases"]}
    notices = {row["notice_id"]: row for row in snapshot["notices"]}
    beneficiaries: dict[str, list[str]] = {}
    for row in snapshot["beneficiaries"]:
        if row["eligible"]:
            beneficiaries.setdefault(str(row["case_id"]), []).append(str(row["person_key"]))
    if len(decision_values) != len(by_id) or set(by_id) != set(cases):
        mismatch("plan", "case_decisions", "case_id", "coverage")
    queue_totals = {key: 0 for key in QUEUE_FIELDS}
    action_bucket = {
        "stage_corrected_notice": "corrected_notice", "stage_reissue_package": "reissue",
        "investigate_provider_receipt": "delivery_investigation",
        "stage_compliance_review": "compliance_review",
    }
    as_of = parse_time(str(policy["as_of"]))
    for case_id, case in cases.items():
        candidate = by_id.get(case_id, {})
        if set(candidate) != DECISION_FIELDS:
            mismatch("case", case_id, "fields", "schema_fields")
        notice_id = case.get("notice_id")
        notice = notices.get(str(notice_id), {}) if notice_id else {}
        case_events = sorted(
            [row for row in events if row.get("case_id") == case_id],
            key=lambda row: (int(row.get("source_sequence", -1)), str(row.get("event_id", ""))),
        )
        verified_events = [row for row in case_events if row.get("source_verified") is True]
        identity_conflict = any(str(row.get("employee_id")) != case["employee_id"] for row in verified_events)
        usable_events = [row for row in verified_events if str(row.get("employee_id")) == case["employee_id"]]
        beneficiary_keys = sorted(beneficiaries.get(case_id, []))
        latest_beneficiary_version = int(case["beneficiary_snapshot_version"])
        for event in usable_events:
            version = int(event.get("beneficiary_snapshot_version", -1))
            if version > latest_beneficiary_version:
                latest_beneficiary_version = version
                beneficiary_keys = sorted(str(item) for item in event.get("beneficiary_keys", []))
        address_version = int(case["address_version"])
        for event in usable_events:
            if event.get("address_state") in policy["verified_address_states"]:
                address_version = max(address_version, int(event.get("address_version", -1)))
        case_receipts = [row for row in receipts if row.get("notice_id") == notice_id and row.get("verified") is True]
        statuses = {str(row.get("status")) for row in case_receipts}
        selected_receipt: dict[str, Any] | None = None
        for status in ("delivered", "returned", "accepted"):
            matches = [row for row in case_receipts if row.get("status") == status]
            if matches:
                selected_receipt = sorted(matches, key=lambda row: str(row.get("observed_at")))[-1]
                break
        delivery_evidence = "none" if selected_receipt is None else f"evidence/delivery_receipts.jsonl#receipt:{selected_receipt['receipt_id']}"
        deadline = parse_time(str(case["event_date"]) + "T00:00:00Z") + timedelta(days=int(policy["notice_deadline_days"]))
        deadline_state = "satisfied" if "delivered" in statuses or case["case_state"] == "elected" else "expired" if as_of > deadline else "open"
        existing_keys = sorted(json.loads(notice.get("beneficiary_keys_json", "[]")))
        if identity_conflict:
            disposition, action = "hold_identity_conflict", "resolve_identity"
            final_notice_version, final_address = int(case["notice_version"]), int(case["address_version"])
            beneficiary_keys = sorted(beneficiaries.get(case_id, []))
        elif case["case_state"] == "elected" and "delivered" in statuses:
            disposition, action = "preserve_post_notice_state", "none"
            final_notice_version, final_address = int(case["notice_version"]), int(case["address_version"])
        elif "delivered" in statuses:
            disposition, action = "preserve_delivered", "none"
            final_notice_version, final_address = int(case["notice_version"]), int(selected_receipt["address_version"])
        elif not notice_id and deadline_state == "expired":
            disposition, action = "escalate_deadline_review", "stage_compliance_review"
            final_notice_version, final_address = 1, address_version
        elif "returned" in statuses and address_version > int(notice.get("address_version", 0)):
            disposition, action = "reissue_to_verified_address", "stage_reissue_package"
            final_notice_version, final_address = int(case["notice_version"]) + 1, address_version
        elif "returned" in statuses:
            disposition, action = "hold_address_resolution", "resolve_address"
            final_notice_version, final_address = int(case["notice_version"]), int(case["address_version"])
        elif "accepted" in statuses:
            disposition, action = "hold_delivery_investigation", "investigate_provider_receipt"
            final_notice_version, final_address = int(case["notice_version"]), int(case["address_version"])
        elif notice_id and (latest_beneficiary_version > int(case["beneficiary_snapshot_version"]) or existing_keys != beneficiary_keys):
            disposition, action = "rebuild_beneficiary_notice", "stage_corrected_notice"
            final_notice_version, final_address = int(case["notice_version"]) + 1, address_version
        else:
            disposition, action = "prepare_initial_notice", "stage_initial_notice"
            final_notice_version, final_address = 1, address_version
        expected = {
            "case_id": case_id, "baseline_state": case["case_state"],
            "disposition": disposition, "notice_version": final_notice_version,
            "address_version": final_address, "beneficiary_keys": beneficiary_keys,
            "delivery_evidence": delivery_evidence, "deadline_state": deadline_state,
            "next_local_action": action,
            "evidence_refs": case_evidence(case_id, notice_id, events, receipts),
        }
        for field, wanted in expected.items():
            actual = candidate.get(field)
            if field in {"beneficiary_keys", "evidence_refs"}:
                actual = sorted({normalize_locator(str(item)) for item in actual}) if isinstance(actual, list) else actual
            if actual != wanted:
                mismatch("case", case_id, field)
        bucket = action_bucket.get(action)
        if bucket:
            queue_totals[bucket] += 1

    journals = [row for row in snapshot["journal"] if any(run["recovery_id"] == row["recovery_id"] and run["status"] in {"interrupted", "rolled_back"} for run in snapshot["runs"])]
    expected_journals = {
        str(row["journal_id"]): {
            "journal_id": row["journal_id"], "table_name": row["table_name"],
            "record_id": row["record_id"],
            "action": "restore_before_image" if row["before_json"] else "remove_partial_insert",
        } for row in journals
    }
    actual_journals = plan.get("journal_actions", [])
    actual_by_id = {str(row.get("journal_id")): row for row in actual_journals if isinstance(row, dict)}
    if len(actual_journals) != len(actual_by_id) or set(actual_by_id) != set(expected_journals):
        mismatch("plan", "journal_actions", "journal_id", "coverage")
    for journal_id, wanted in expected_journals.items():
        candidate = actual_by_id.get(journal_id, {})
        if set(candidate) != JOURNAL_FIELDS:
            mismatch("journal", journal_id, "fields", "schema_fields")
        for field, value in wanted.items():
            if candidate.get(field) != value:
                mismatch("journal", journal_id, field)
    if plan.get("queue_totals") != queue_totals or not isinstance(plan.get("queue_totals"), dict) or set(plan.get("queue_totals", {})) != QUEUE_FIELDS:
        mismatch("plan", "root", "queue_totals")
    context = {"snapshot": snapshot, "checkpoint": wanted_checkpoint, "queue_totals": queue_totals, "policy": policy}
    return plan, context, discrepancies


def state_payload(connection: sqlite3.Connection, recovery_id: str) -> dict[str, Any]:
    return {
        "cases": rows(connection, "cases", "case_id"),
        "beneficiaries": rows(connection, "beneficiaries", "case_id,person_key"),
        "notices": rows(connection, "notices", "notice_id"),
        "attempts": rows(connection, "delivery_attempts", "attempt_id"),
        "queue": rows(connection, "recovery_queue", "queue_id"),
        "receipts": [row for row in rows(connection, "decision_receipts", "recovery_id,case_id") if row["recovery_id"] == recovery_id],
    }


def materialize(plan: dict[str, Any], context: dict[str, Any]) -> None:
    recovery_id = str(plan["recovery_id"])
    semantic_digest = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute("SELECT semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (recovery_id,)).fetchone()
        if current:
            if current[0] == semantic_digest:
                connection.rollback()
                return
            connection.rollback()
            raise ValueError("recovery identity already has different semantic content")
        interrupted = {row[0] for row in connection.execute("SELECT recovery_id FROM recovery_runs WHERE status='interrupted'")}
        for row in connection.execute("SELECT journal_id,recovery_id,table_name,record_id,before_json FROM recovery_journal WHERE restored=0 ORDER BY journal_id").fetchall():
            journal_id, old_run, table, record_id, before_json = row
            if old_run not in interrupted:
                continue
            if table == "cases":
                before = json.loads(before_json)
                connection.execute("DELETE FROM cases WHERE case_id=?", (record_id,))
                connection.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?)", tuple(before[key] for key in ("case_id", "employee_id", "qualifying_event", "event_date", "case_state", "beneficiary_snapshot_version", "address_version", "notice_id", "notice_version", "row_revision")))
            elif table == "recovery_queue":
                connection.execute("DELETE FROM recovery_queue WHERE queue_id=?", (record_id,))
            else:
                connection.rollback()
                raise ValueError("unsupported journal target")
            connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
        for old_run in interrupted:
            connection.execute("UPDATE recovery_runs SET status='rolled_back' WHERE recovery_id=?", (old_run,))
        queued = {"stage_corrected_notice", "stage_reissue_package", "investigate_provider_receipt", "stage_compliance_review"}
        for row in plan["case_decisions"]:
            connection.execute("INSERT INTO decision_receipts VALUES (?,?,?,?)", (recovery_id, row["case_id"], row["disposition"], row["next_local_action"]))
            if row["next_local_action"] in queued:
                connection.execute("INSERT INTO recovery_queue VALUES (?,?,?,?,?,?)", (f"Q-{recovery_id}-{row['case_id']}", row["case_id"], row["next_local_action"], "staged_local", 0, recovery_id))
        interim = state_payload(connection, recovery_id)
        state_digest = digest(canonical(interim))
        connection.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?)", (recovery_id, context["checkpoint"], semantic_digest, state_digest, "committed"))
        connection.commit()


def verify_state(plan: dict[str, Any]) -> dict[str, Any]:
    semantic_digest = digest(canonical(plan))
    errors: list[str] = []
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
            run = connection.execute("SELECT source_checkpoint,semantic_plan_digest,semantic_state_digest,status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
            if run is None or run[0] != plan["source_checkpoint"] or run[1] != semantic_digest or run[3] != "committed":
                errors.append("committed recovery identity mismatch")
            else:
                actual_state = digest(canonical(state_payload(connection, str(plan["recovery_id"]))))
                if actual_state != run[2]:
                    errors.append("semantic state digest mismatch")
            queue = rows(connection, "recovery_queue", "queue_id")
            if any(row["executed"] != 0 for row in queue):
                errors.append("local queue has an executed action")
            if any(row["restored"] != 1 for row in rows(connection, "recovery_journal", "journal_id")):
                errors.append("interrupted journal remains open")
    except sqlite3.Error as exc:
        errors.append(f"database verification failed: {exc}")
    return {"status": "pass" if not errors else "fail", "errors": errors, "semantic_plan_digest": semantic_digest, "external_notices_sent": False, "coverage_changed": False}


def stage_bundle(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    queue_actions = {"stage_corrected_notice", "stage_reissue_package", "investigate_provider_receipt", "stage_compliance_review"}
    items = [{
        "case_id": row["case_id"], "disposition": row["disposition"],
        "next_local_action": row["next_local_action"], "notice_version": row["notice_version"],
        "address_version": row["address_version"], "beneficiary_keys": row["beneficiary_keys"],
        "status": "local_review_only", "executed": False,
    } for row in plan["case_decisions"] if row["next_local_action"] in queue_actions]
    bundle = {"schema_version": 1, "recovery_id": plan["recovery_id"], "items": items, "notices_sent": False, "coverage_changed": False, "external_actions_executed": False}
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        run = connection.execute("SELECT semantic_state_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    if run is None:
        raise ValueError("recovery is not committed")
    manifest = {"bundle_sha256": digest(canonical(bundle)), "semantic_plan_digest": digest(canonical(plan)), "semantic_state_digest": run[0], "source_checkpoint": plan["source_checkpoint"]}
    receipt = {"manifest_sha256": digest(canonical(manifest)), "item_count": len(items), "status": "local_staged", "external_action": False}
    return bundle, manifest, receipt


def resolve_plan(value: str) -> Path:
    path = (ROOT / value).resolve()
    if path.parent != ROOT or path.suffix != ".json":
        raise ValueError("plan path must be a top-level workspace JSON file")
    return path


def inspect_command() -> int:
    hashes, source_hash = source_bundle()
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        snapshot = restored_snapshot(connection)
        payload = {
            "database": "state/continuance.db", "tables": sorted(TABLES),
            "row_counts": {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in sorted(TABLES)},
            "interrupted_runs": [row["recovery_id"] for row in snapshot["runs"] if row["status"] == "interrupted"],
            "open_journals": [row["journal_id"] for row in snapshot["journal"] if not row["restored"]],
            "source_revision": int(snapshot["system"]["source_revision"]),
            "source_bundle_sha256": source_hash,
            "source_checkpoint": checkpoint(snapshot, hashes),
            "note": "query every table and inspect raw evidence; inspect does not provide decisions",
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def query_command(sql: str) -> int:
    statement = sql.strip()
    if not statement.casefold().startswith(("select ", "with ")) or ";" in statement.rstrip(";"):
        raise ValueError("query accepts one read-only SELECT/CTE statement")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        cursor = connection.execute(statement)
        names = [item[0] for item in cursor.description or []]
        print(json.dumps([dict(zip(names, row, strict=True)) for row in cursor.fetchall()], indent=2, sort_keys=True))
    return 0


def plan_command(command: str, plan_name: str) -> int:
    path = resolve_plan(plan_name)
    raw = read_object(path)
    plan, context, discrepancies = assess_candidate(raw)
    preview = {"schema_version": 1, "candidate": path.name, "status": "pass" if not discrepancies else "fail", "candidate_semantic_digest": digest(canonical(plan)), "discrepancies": discrepancies}
    if command == "preview":
        write_object(ROOT / ".continuance_preview.json", preview)
        print(json.dumps(preview, indent=2, sort_keys=True))
        return 0 if not discrepancies else 2
    if discrepancies:
        raise ValueError("candidate failed preview; inspect .continuance_preview.json")
    if command == "apply":
        materialize(plan, context)
        print(json.dumps({"status": "committed", "recovery_id": plan["recovery_id"], "external_actions_executed": False}, indent=2))
        return 0
    if command == "verify":
        report = verify_state(plan)
        write_object(ROOT / "state/verification.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "pass" else 2
    if command == "stage":
        report = verify_state(plan)
        if report["status"] != "pass":
            raise ValueError("verify must pass before staging")
        bundle, manifest, receipt = stage_bundle(plan)
        write_object(ROOT / "staging/notice_review_queue.json", bundle)
        write_object(ROOT / "staging/queue_manifest.json", manifest)
        write_object(ROOT / "state/staging_receipt.json", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    if command == "replay":
        report = verify_state(plan)
        bundle, manifest, receipt = stage_bundle(plan)
        stable = (
            report["status"] == "pass"
            and read_object(ROOT / "staging/notice_review_queue.json") == bundle
            and read_object(ROOT / "staging/queue_manifest.json") == manifest
            and read_object(ROOT / "state/staging_receipt.json") == receipt
        )
        replay = {"status": "idempotent_noop" if stable else "conflict", "mutation_count": 0, "semantic_plan_digest": digest(canonical(plan))}
        write_object(ROOT / "state/replay_report.json", replay)
        print(json.dumps(replay, indent=2, sort_keys=True))
        return 0 if stable else 2
    raise ValueError("unknown command")


def main() -> int:
    parser = argparse.ArgumentParser(description="offline continuation-coverage recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    query = sub.add_parser("query")
    query.add_argument("sql")
    for name in ("preview", "apply", "verify", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect_command()
        if args.command == "query":
            return query_command(args.sql)
        return plan_command(args.command, args.plan)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
