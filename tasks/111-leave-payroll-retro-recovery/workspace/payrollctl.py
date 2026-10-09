#!/usr/bin/env python3
"""Offline controller for a synthetic HRIS/payroll retro recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
POLICY = ROOT / "policy/retro_policy.json"
SOURCE_MANIFEST = ROOT / "policy/source_manifest.json"
EMPLOYEES = ROOT / "evidence/employees.json"
KEYS = ROOT / "evidence/approval_keys.json"
APPROVALS = ROOT / "evidence/late_approvals.json"
CALENDAR = ROOT / "evidence/payroll_calendar.json"
DATABASE = ROOT / "state/hris_payroll.db"
BATCH = ROOT / "state/batch.json"
APPLY_STATE = ROOT / ".retro_apply_state.json"
RECEIPT = ROOT / "state/stage_receipt.json"


def fail(message: str) -> None:
    raise ValueError(message)


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def key_records() -> dict[str, dict[str, Any]]:
    value = load(KEYS)
    rows = value.get("keys") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        fail("approval key registry is malformed")
    return {str(row["key_id"]): row for row in rows if isinstance(row, dict)}


def employee_records() -> dict[str, dict[str, Any]]:
    value = load(EMPLOYEES)
    rows = value.get("employees") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        fail("employee snapshot is malformed")
    return {str(row["employee_id"]): row for row in rows if isinstance(row, dict)}


def signature_valid(row: dict[str, Any], key: dict[str, Any] | None) -> bool:
    if not isinstance(key, dict):
        return False
    payload = {name: value for name, value in row.items() if name != "signature"}
    signed = canonical(payload).rstrip(b"\n") + b":" + str(
        key.get("verification_material", "")
    ).encode()
    return str(row.get("signature")) == digest_bytes(signed)


def current_approvals() -> dict[str, dict[str, Any]]:
    value = load(APPROVALS)
    rows = value.get("approvals") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        fail("approval records are malformed")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            fail("approval record must be an object")
        grouped.setdefault(str(row.get("request_id")), []).append(row)
    return {
        request_id: max(records, key=lambda item: int(item.get("revision", -1)))
        for request_id, records in grouped.items()
    }


def connection() -> sqlite3.Connection:
    result = sqlite3.connect(DATABASE)
    result.row_factory = sqlite3.Row
    result.execute("PRAGMA foreign_keys=ON")
    return result


def query_rows(db: sqlite3.Connection, query: str, values: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(query, values).fetchall()]


def hours_between(row: dict[str, Any]) -> float:
    try:
        start = datetime.fromisoformat(str(row["start_local"]))
        end = datetime.fromisoformat(str(row["end_local"]))
    except (KeyError, ValueError) as exc:
        fail(f"invalid signed interval for {row.get('approval_id')}: {exc}")
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        fail(f"signed interval for {row.get('approval_id')} must be offset-aware and positive")
    hours = (end - start).total_seconds() / 3600
    if hours <= 0 or hours * 4 != round(hours * 4):
        fail(f"signed interval for {row.get('approval_id')} is not a positive quarter-hour")
    return hours


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(plan)
    dispositions = normalized.get("dispositions")
    adjustments = normalized.get("adjustments")
    if not isinstance(dispositions, list) or not isinstance(adjustments, list):
        fail("dispositions and adjustments must be arrays")
    normalized_dispositions = []
    for row in dispositions:
        if not isinstance(row, dict):
            fail("each disposition must be an object")
        copied = dict(row)
        evidence = copied.get("evidence")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            fail("disposition evidence must be a string array")
        copied["evidence"] = sorted(evidence)
        normalized_dispositions.append(copied)
    normalized["dispositions"] = sorted(
        normalized_dispositions, key=lambda row: str(row.get("request_id"))
    )
    normalized["adjustments"] = sorted(
        (dict(row) for row in adjustments if isinstance(row, dict)),
        key=lambda row: str(row.get("adjustment_id")),
    )
    if len(normalized["adjustments"]) != len(adjustments):
        fail("each adjustment must be an object")
    return normalized


def semantic_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Return the business decision identity, excluding evidence-set wording."""
    normalized = normalize_plan(plan)
    normalized["dispositions"] = [
        {key: value for key, value in row.items() if key != "evidence"}
        for row in normalized["dispositions"]
    ]
    return normalized


def has_local_locator(refs: list[str], filename: str, object_id: str) -> bool:
    """Accept stable section/key spellings for one visible local object."""
    return any(
        ref.startswith(filename)
        and (ref.endswith(f"#{object_id}") or ref.endswith(f"/{object_id}"))
        for ref in refs
    )


def validate_plan(plan: dict[str, Any], db: sqlite3.Connection) -> dict[str, Any]:
    actual = normalize_plan(plan)
    required_top = {
        "schema_version", "batch_id", "source_period_id", "target_period_id",
        "strategy", "frozen_source_action", "approval_boundary", "dispositions",
        "adjustments", "external_actions_executed",
    }
    if set(actual) != required_top:
        fail(f"plan keys must be exactly {sorted(required_top)}")
    policy = load(POLICY)
    errors: list[str] = []
    for name in (
        "schema_version",
        "batch_id",
        "source_period_id",
        "target_period_id",
        "strategy",
        "frozen_source_action",
        "approval_boundary",
        "external_actions_executed",
    ):
        required_value = False if name == "external_actions_executed" else (
            1 if name == "schema_version" else policy[name]
        )
        if actual.get(name) != required_value:
            errors.append(f"top-level field {name} violates the published batch contract")
    actual_dispositions = {row.get("request_id"): row for row in actual["dispositions"]}
    approvals = current_approvals()
    if set(actual_dispositions) != set(approvals):
        errors.append("dispositions must cover every current request exactly once")
    keys = key_records()
    employees = employee_records()
    cutoff = datetime.fromisoformat(str(policy["approval_cutoff_utc"]))
    adjustments_by_request: dict[str, list[dict[str, Any]]] = {}
    for adjustment in actual["adjustments"]:
        adjustments_by_request.setdefault(str(adjustment.get("request_id")), []).append(adjustment)
    for request_id, approval in sorted(approvals.items()):
        row = actual_dispositions.get(request_id)
        if not isinstance(row, dict):
            continue
        approval_id = str(approval["approval_id"])
        employee_id = str(approval["employee_id"])
        key_id = str(approval["key_id"])
        employee = employees.get(employee_id)
        key = keys.get(key_id)
        if employee is None:
            fail(f"employee snapshot has no {employee_id}")
        authorized = (
            signature_valid(approval, key) and key is not None
            and key.get("status") == "active"
            and key.get("role") in policy["authority_roles"]
            and set(policy["authority_scopes"]).issubset(set(key.get("scopes", [])))
            and datetime.fromisoformat(str(approval["signed_at_utc"])) <= cutoff
        )
        eligible = date.fromisoformat(str(approval["start_local"])[:10]) >= date.fromisoformat(str(employee["leave_eligible_since"]))
        rule = "authority_failure" if not authorized else ("eligibility_failure" if not eligible else "eligible")
        required_fields = {
            "request_id": request_id,
            "selected_approval_id": approval_id,
            "selected_revision": int(approval["revision"]),
            "disposition": policy["dispositions"][rule],
            "reason_code": policy["reason_codes"][rule],
        }
        differing = sorted(name for name, value in required_fields.items() if row.get(name) != value)
        if differing:
            errors.append(f"disposition {request_id} differs in: {', '.join(differing)}")
        refs = row.get("evidence", [])
        missing_categories = []
        if not has_local_locator(refs, "evidence/late_approvals.json", approval_id):
            missing_categories.append("current signed approval")
        if not has_local_locator(refs, "evidence/approval_keys.json", key_id):
            missing_categories.append("signer key registry")
        if rule != "authority_failure" and not has_local_locator(refs, "evidence/employees.json", employee_id):
            missing_categories.append("employee eligibility record")
        source_rows = query_rows(db, "SELECT line_id, pay_code, hours FROM payroll_lines WHERE request_id=?", (request_id,))
        candidate_adjustments = adjustments_by_request.get(request_id, [])
        if rule == "eligible":
            if len(source_rows) != 1:
                fail(f"eligible request {request_id} must resolve to one paid source line")
            source = source_rows[0]
            if not has_local_locator(refs, "state/hris_payroll.db", str(source["line_id"])):
                missing_categories.append("paid payroll source line")
            revision = int(approval["revision"])
            expected_rows = [
                {"adjustment_id": f"RA-{request_id.removeprefix('LR-')}-REV-{source['pay_code']}-R{revision}", "request_id": request_id, "source_line_id": source["line_id"], "source_revision": revision, "target_period_id": policy["target_period_id"], "pay_code": source["pay_code"], "hours_delta": -float(source["hours"])},
                {"adjustment_id": f"RA-{request_id.removeprefix('LR-')}-ADD-{approval['leave_code']}-R{revision}", "request_id": request_id, "source_line_id": source["line_id"], "source_revision": revision, "target_period_id": policy["target_period_id"], "pay_code": approval["leave_code"], "hours_delta": float(hours_between(approval))},
            ]
            if sorted(candidate_adjustments, key=lambda item: str(item.get("adjustment_id"))) != sorted(expected_rows, key=lambda item: item["adjustment_id"]):
                errors.append(f"adjustments for {request_id} differ in identity, source, revision, period, code, or hours")
        elif candidate_adjustments:
            errors.append(f"held request {request_id} must not have an adjustment")
        if missing_categories:
            errors.append(f"disposition {request_id} is missing evidence categories: {', '.join(missing_categories)}")
    unknown_adjustments = sorted(set(adjustments_by_request) - set(approvals))
    if unknown_adjustments:
        errors.append("adjustments reference unknown requests: " + ", ".join(unknown_adjustments))
    unsafe = [
        ref
        for row in actual["dispositions"]
        for ref in row["evidence"]
        if ref.startswith(("/", "../", "http://", "https://", "file://"))
    ]
    if unsafe:
        errors.append(f"unsafe evidence locators: {unsafe}")
    if errors:
        fail("plan validation failed:\n- " + "\n- ".join(errors))
    return actual


def source_errors() -> list[str]:
    manifest = load(SOURCE_MANIFEST)
    errors: list[str] = []
    for relative, expected in manifest.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file() or digest_file(path) != expected:
            errors.append(f"protected source changed: {relative}")
    return errors


def selected_rows(db: sqlite3.Connection, table: str, columns: str, order: str) -> list[dict[str, Any]]:
    return query_rows(db, f"SELECT {columns} FROM {table} ORDER BY {order}")


def frozen_snapshot(db: sqlite3.Connection) -> dict[str, Any]:
    return {
        "periods": selected_rows(
            db,
            "payroll_periods",
            "period_id, state, period_start, period_end, payment_export_id, locked_at_utc",
            "period_id",
        ),
        "payroll_lines": selected_rows(
            db,
            "payroll_lines",
            "line_id, period_id, employee_id, request_id, revision, pay_code, hours, service_start_local, service_end_local, payment_export_id",
            "line_id",
        ),
    }


def adjustment_core(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return selected_rows(
        db,
        "retro_adjustments",
        "adjustment_id, batch_id, request_id, source_line_id, source_revision, target_period_id, pay_code, hours_delta",
        "adjustment_id",
    )


def journal_core(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return selected_rows(
        db,
        "operation_journal",
        "sequence, batch_id, adjustment_id, event, plan_sha256, recorded_at_utc",
        "sequence",
    )


def plan_sha(plan: dict[str, Any]) -> str:
    return digest_bytes(canonical(semantic_plan(plan)))


def verify_database(db: sqlite3.Connection, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    validated = validate_plan(plan, db)
    expected_adjustments = {row["adjustment_id"]: row for row in validated["adjustments"]}
    actual_rows = adjustment_core(db)
    actual = {row["adjustment_id"]: row for row in actual_rows}
    if set(actual) != set(expected_adjustments):
        fail("durable adjustment IDs do not match the validated plan")
    batch_id = validated["batch_id"]
    for adjustment_id, expected_row in expected_adjustments.items():
        row = actual[adjustment_id]
        for field in (
            "request_id",
            "source_line_id",
            "source_revision",
            "target_period_id",
            "pay_code",
            "hours_delta",
        ):
            if row[field] != expected_row[field]:
                fail(f"durable adjustment {adjustment_id} differs at {field}")
        if row["batch_id"] != batch_id:
            fail(f"durable adjustment {adjustment_id} has the wrong batch")
    journal = journal_core(db)
    prefix_ids = [
        row["adjustment_id"]
        for row in journal
        if row["event"] == "committed_before_worker_exit"
    ]
    missing_ids = sorted(set(expected_adjustments) - set(prefix_ids))
    expected_order = prefix_ids + missing_ids
    if (
        not prefix_ids
        or len(prefix_ids) >= len(expected_adjustments)
        or [row["sequence"] for row in journal] != list(range(1, len(journal) + 1))
        or [row["adjustment_id"] for row in journal] != expected_order
    ):
        fail("recovery journal does not preserve the committed prefix and deterministic append order")
    if any(row["plan_sha256"] != plan_sha(plan) for row in journal):
        fail("recovery journal is not bound to this semantic plan")
    batch_rows = query_rows(db, "SELECT * FROM retro_batches WHERE batch_id=?", (batch_id,))
    if len(batch_rows) != 1:
        fail("retro batch row is missing or duplicated")
    return batch_rows[0], {
        "frozen_payroll_sha256": digest_bytes(canonical(frozen_snapshot(db))),
        "adjustment_set_sha256": digest_bytes(canonical(actual_rows)),
        "journal_sha256": digest_bytes(canonical(journal)),
    }


def expected_apply_state(db: sqlite3.Connection, plan: dict[str, Any]) -> dict[str, Any]:
    _, hashes = verify_database(db, plan)
    prefix_count = len(
        query_rows(
            db,
            "SELECT adjustment_id FROM operation_journal WHERE event='committed_before_worker_exit'",
        )
    )
    return {
        "schema_version": 1,
        "batch_id": plan["batch_id"],
        "phase": "applied_verified",
        "recovered_prefix_count": prefix_count,
        "adjustment_count": len(plan["adjustments"]),
        "journal_count": len(plan["adjustments"]),
        "plan_sha256": plan_sha(plan),
        **hashes,
        "recovery_revision": 2,
        "external_payment_executed": False,
        "recovery_phase": "applied_verified",
    }


def command_inspect() -> None:
    with connection() as db:
        approvals = []
        keys = key_records()
        for request_id, row in sorted(current_approvals().items()):
            key = keys.get(str(row.get("key_id")))
            approvals.append(
                {
                    "request_id": request_id,
                    "current_approval_id": row.get("approval_id"),
                    "revision": row.get("revision"),
                    "employee_id": row.get("employee_id"),
                    "signed_interval": [row.get("start_local"), row.get("end_local")],
                    "signature_valid": signature_valid(row, key),
                    "signer_role": key.get("role") if key else None,
                    "signer_status": key.get("status") if key else None,
                }
            )
        result = {
            "approvals": approvals,
            "periods": frozen_snapshot(db)["periods"],
            "payroll_lines": frozen_snapshot(db)["payroll_lines"],
            "retro_batches": query_rows(db, "SELECT * FROM retro_batches ORDER BY batch_id"),
            "retro_adjustments": query_rows(db, "SELECT * FROM retro_adjustments ORDER BY adjustment_id"),
            "operation_journal": journal_core(db),
            "batch_file": load(BATCH),
            "source_errors": source_errors(),
        }
    print(json.dumps(result, indent=2, sort_keys=True))


def load_and_validate(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = load(path)
    if not isinstance(plan, dict):
        fail("plan must be a JSON object")
    with connection() as db:
        normalized = validate_plan(plan, db)
    return plan, normalized


def command_preview(path: Path) -> None:
    _, normalized = load_and_validate(path)
    errors = source_errors()
    if errors:
        fail("; ".join(errors))
    print(
        json.dumps(
            {
                "status": "preview_passed",
                "batch_id": normalized["batch_id"],
                "disposition_count": len(normalized["dispositions"]),
                "adjustment_count": len(normalized["adjustments"]),
                "plan_sha256": plan_sha(normalized),
                "state_changed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def command_apply(path: Path) -> None:
    plan, normalized = load_and_validate(path)
    errors = source_errors()
    if errors:
        fail("; ".join(errors))
    semantic_sha = plan_sha(plan)
    with connection() as db:
        batch = query_rows(db, "SELECT * FROM retro_batches WHERE batch_id=?", (normalized["batch_id"],))
        if len(batch) != 1:
            fail("retro batch row is missing")
        phase = batch[0]["phase"]
        if phase in {"applied_verified", "staged_pending_payroll_approval"}:
            expected_state = expected_apply_state(db, plan)
            if load(APPLY_STATE) != expected_state:
                fail("existing apply state does not verify")
            print(json.dumps({"status": "already_applied", "idempotent": True}, sort_keys=True))
            return
        if phase != "interrupted_after_partial_commit" or batch[0]["revision"] < 1:
            fail("batch is not at the recoverable interrupted checkpoint")
        if batch[0]["plan_sha256"] != semantic_sha:
            fail("interrupted journal belongs to a different semantic plan")
        existing = {row["adjustment_id"]: row for row in adjustment_core(db)}
        prefix = journal_core(db)
        prefix_ids = [
            row["adjustment_id"]
            for row in prefix
            if row["event"] == "committed_before_worker_exit"
        ]
        if (
            not prefix_ids
            or set(existing) != set(prefix_ids)
            or [row["sequence"] for row in prefix] != list(range(1, len(prefix) + 1))
            or [row["adjustment_id"] for row in prefix] != prefix_ids
        ):
            fail("interrupted adjustment prefix is missing or has unexpected rows")
        expected_by_id = {
            row["adjustment_id"]: row for row in normalized["adjustments"]
        }
        if not set(prefix_ids).issubset(expected_by_id):
            fail("interrupted adjustment prefix is not part of the validated plan")
        for adjustment_id in prefix_ids:
            expected_row = expected_by_id[adjustment_id]
            if any(
                existing[adjustment_id][field] != expected_row[field]
                for field in expected_row
            ):
                fail("interrupted adjustment prefix conflicts with the validated plan")
        db.execute("BEGIN IMMEDIATE")
        for row in normalized["adjustments"]:
            if row["adjustment_id"] in existing:
                continue
            db.execute(
                "INSERT INTO retro_adjustments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["adjustment_id"], normalized["batch_id"], row["request_id"],
                    row["source_line_id"], row["source_revision"], row["target_period_id"],
                    row["pay_code"], row["hours_delta"], "prepared", 0,
                ),
            )
        current_journal = {row["adjustment_id"] for row in journal_core(db)}
        append_order = sorted(set(expected_by_id) - set(prefix_ids))
        for adjustment_id in append_order:
            if adjustment_id in current_journal:
                continue
            sequence = int(db.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM operation_journal").fetchone()[0])
            db.execute(
                "INSERT INTO operation_journal VALUES (?, ?, ?, ?, ?, ?)",
                (
                    sequence,
                    normalized["batch_id"],
                    adjustment_id,
                    "recovered_adjustment",
                    semantic_sha,
                    load(POLICY)["recovery_recorded_at_utc"],
                ),
            )
        db.execute(
            "UPDATE retro_batches SET phase=?, revision=?, adjustment_count=?, external_payment_executed=0 WHERE batch_id=?",
            ("applied_verified", 2, len(normalized["adjustments"]), normalized["batch_id"]),
        )
        db.commit()
        apply_state = expected_apply_state(db, plan)
    write_json(APPLY_STATE, apply_state)
    batch_file = load(BATCH)
    batch_file.update(
        {
            "phase": "applied_verified",
            "revision": 2,
            "plan_sha256": semantic_sha,
            "adjustment_count": len(normalized["adjustments"]),
            "external_payment_executed": False,
        }
    )
    write_json(BATCH, batch_file)
    print(
        json.dumps(
            {
                "status": "applied_verified",
                "recovered_rows": len(normalized["adjustments"]) - len(prefix_ids),
            },
            sort_keys=True,
        )
    )


def command_verify(path: Path) -> None:
    plan, _ = load_and_validate(path)
    if source_errors():
        fail("protected source hash verification failed")
    with connection() as db:
        expected = expected_apply_state(db, plan)
    if load(APPLY_STATE) != expected:
        fail("apply-state hashes do not close over the durable database")
    batch_file = load(BATCH)
    if batch_file.get("phase") not in {"applied_verified", "staged_pending_payroll_approval"}:
        fail("batch file is not applied or staged")
    print(json.dumps({"status": "verified", "plan_sha256": expected["plan_sha256"]}, sort_keys=True))


def stage_values(db: sqlite3.Connection, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    batch_row, hashes = verify_database(db, plan)
    source_period = query_rows(
        db,
        "SELECT payment_export_id FROM payroll_periods WHERE period_id=?",
        (plan["source_period_id"],),
    )
    if len(source_period) != 1 or not source_period[0]["payment_export_id"]:
        fail("paid source period has no immutable payment export identity")
    batch_value = {
        "schema_version": 1,
        "batch_id": plan["batch_id"],
        "source_period_id": plan["source_period_id"],
        "target_period_id": plan["target_period_id"],
        "phase": "staged_pending_payroll_approval",
        "revision": 3,
        "plan_sha256": plan_sha(plan),
        "adjustment_count": len(plan["adjustments"]),
        "source_payment_export_id": source_period[0]["payment_export_id"],
        "external_payment_executed": False,
    }
    semantic_state = {
        "batch": batch_value,
        "adjustments": selected_rows(
            db,
            "retro_adjustments",
            "adjustment_id, batch_id, request_id, source_line_id, source_revision, target_period_id, pay_code, hours_delta, status, external_payment_executed",
            "adjustment_id",
        ),
        "journal": journal_core(db),
    }
    state_sha = digest_bytes(canonical(semantic_state))
    token_payload = {
        "batch_id": plan["batch_id"],
        "revision": 3,
        "phase": batch_value["phase"],
        "plan_sha256": plan_sha(plan),
        "semantic_state_sha256": state_sha,
        **hashes,
    }
    receipt = {
        "schema_version": 1,
        **token_payload,
        "stage_token": digest_bytes(canonical(token_payload)),
        "approval_status": "pending",
        "external_payment_executed": False,
    }
    if batch_row["phase"] != "staged_pending_payroll_approval":
        fail("database batch is not staged")
    return batch_value, receipt


def command_stage(path: Path) -> None:
    plan, normalized = load_and_validate(path)
    command_verify(path)
    with connection() as db:
        row = query_rows(db, "SELECT * FROM retro_batches WHERE batch_id=?", (normalized["batch_id"],))[0]
        if row["phase"] == "staged_pending_payroll_approval":
            expected_batch, expected_receipt = stage_values(db, plan)
            if load(BATCH) != expected_batch or load(RECEIPT) != expected_receipt:
                fail("existing staged artifacts do not verify")
            print(json.dumps({"status": "already_staged", "idempotent": True}, sort_keys=True))
            return
        if row["phase"] != "applied_verified" or row["revision"] != 2:
            fail("batch is not ready for local staging")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE retro_adjustments SET status='staged_pending_payroll_approval' WHERE batch_id=?",
            (normalized["batch_id"],),
        )
        db.execute(
            "UPDATE retro_batches SET phase='staged_pending_payroll_approval', revision=3 WHERE batch_id=?",
            (normalized["batch_id"],),
        )
        db.commit()
        batch_value, receipt = stage_values(db, plan)
    write_json(BATCH, batch_value)
    write_json(RECEIPT, receipt)
    print(json.dumps({"status": "staged_pending_payroll_approval", "external_payment_executed": False}, sort_keys=True))


def command_verify_stage(path: Path) -> None:
    plan, _ = load_and_validate(path)
    with connection() as db:
        expected_batch, expected_receipt = stage_values(db, plan)
    if load(BATCH) != expected_batch or load(RECEIPT) != expected_receipt:
        fail("batch JSON or stage receipt does not close over the staged database")
    print(json.dumps({"status": "stage_verified", "stage_token": expected_receipt["stage_token"]}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect")
    for name in ("preview", "apply", "verify", "stage", "verify-stage"):
        command = subparsers.add_parser(name)
        command.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            command_inspect()
        elif args.command == "preview":
            command_preview(args.plan)
        elif args.command == "apply":
            command_apply(args.plan)
        elif args.command == "verify":
            command_verify(args.plan)
        elif args.command == "stage":
            command_stage(args.plan)
        else:
            command_verify_stage(args.plan)
    except (OSError, UnicodeError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"payrollctl: {exc}\n")


if __name__ == "__main__":
    main()
