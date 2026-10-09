#!/usr/bin/env python3
"""Guarded offline mailbox-recovery controller.

It validates submitted decisions at object/field granularity.  No callable
constructs or returns the complete recovery plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/mailops.db"
MAILDIR = ROOT / "maildir/cur"
POLICY = ROOT / "policy/recovery_policy.json"
APPROVALS = ROOT / "evidence/approvals.json"
TRUST = ROOT / "evidence/approval_trust.json"
CHECKPOINT = ROOT / "evidence/mailbox_checkpoint.json"
PLAN_FIELDS = {"schema_version", "recovery_id", "mailbox_checkpoint", "decisions", "quarantined_dsn_ids", "ignored_approval_ids", "external_messages_sent"}
DECISION_FIELDS = {"message_id", "thread_id", "delivery_state", "dsn_ids", "action", "target_recipient", "approval_id", "draft_id", "evidence_refs"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in {"message_state", "drafts", "recovery_runs", "recovery_journal", "system_state"}:
        raise ValueError(f"unsupported table: {table}")
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {', '.join(columns[:2])}")]


def _dsn_fields(message: Any) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in message.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        payload = part.get_payload()
        for block in payload if isinstance(payload, list) else []:
            for key in ("Original-Message-ID", "Final-Recipient", "Action", "Status"):
                if block.get(key) and key not in fields:
                    fields[key] = str(block.get(key)).strip()
    original = message.get("X-Original-Message-ID")
    if original and "Original-Message-ID" not in fields:
        fields["Original-Message-ID"] = str(original).strip()
    return fields


def _mail_graph() -> dict[str, Any]:
    """Return parsed source observations, never candidate decisions."""
    originals: dict[str, dict[str, Any]] = {}
    original_hashes: dict[str, str] = {}
    dsns: dict[str, dict[str, Any]] = {}
    dsn_hashes: dict[str, str] = {}
    counts: Counter[str] = Counter()
    quarantine: set[str] = set()
    for path in sorted(MAILDIR.glob("*.eml")):
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        message_id = str(message.get("Message-ID", "")).strip()
        if not message_id:
            raise ValueError(f"missing Message-ID in {path.name}")
        relative = f"maildir/cur/{path.name}"
        if message.get_content_type() == "multipart/report" or message.get("X-DSN-ID"):
            dsn_id = str(message.get("X-DSN-ID") or message_id).strip()
            fields = _dsn_fields(message)
            row = {
                "dsn_id": dsn_id,
                "message_id": message_id,
                "original_message_id": fields.get("Original-Message-ID", ""),
                "final_recipient": fields.get("Final-Recipient", "").split(";", 1)[-1].strip().lower(),
                "action": fields.get("Action", "").lower(),
                "status": fields.get("Status", ""),
                "sources": [relative],
            }
            semantic = _digest({key: value for key, value in row.items() if key != "sources"})
            counts[dsn_id] += 1
            if dsn_id in dsn_hashes and dsn_hashes[dsn_id] != semantic:
                quarantine.add(dsn_id)
            dsn_hashes[dsn_id] = semantic
            if dsn_id in dsns:
                dsns[dsn_id]["sources"].append(relative)
            else:
                dsns[dsn_id] = row
            continue
        row = {
            "message_id": message_id,
            "thread_id": str(message.get("X-Thread-ID", "")).strip(),
            "recipient": str(message.get("To", "")).strip().lower(),
            "subject": str(message.get("Subject", "")).strip(),
            "sources": [relative],
        }
        semantic = _digest({key: value for key, value in row.items() if key != "sources"})
        if message_id in original_hashes and original_hashes[message_id] != semantic:
            raise ValueError(f"conflicting original copies for {message_id}")
        original_hashes[message_id] = semantic
        if message_id in originals:
            originals[message_id]["sources"].append(relative)
        else:
            originals[message_id] = row
    linked: dict[str, list[dict[str, Any]]] = {key: [] for key in originals}
    for dsn_id, row in dsns.items():
        original = originals.get(row["original_message_id"])
        if dsn_id in quarantine or original is None or not row["final_recipient"] or row["final_recipient"] != original["recipient"] or row["action"] not in {"delivered", "failed", "delayed"}:
            quarantine.add(dsn_id)
            continue
        linked[row["original_message_id"]].append(row)
    for message_id, rows in linked.items():
        if len({row["action"] for row in rows}) > 1:
            quarantine.update(row["dsn_id"] for row in rows)
            linked[message_id] = []
    return {"originals": originals, "dsns": dsns, "linked": linked, "quarantine_dsn_ids": sorted(quarantine), "duplicate_dsn_ids": sorted(key for key, count in counts.items() if count > 1)}


def _approval_observations() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return approval evidence, not actions or final decisions."""
    feed, trust = _load(APPROVALS), _load(TRUST)
    materials = {str(row.get("key_id")): str(row.get("verification_material")) for row in trust.get("keys", []) if isinstance(row, dict) and row.get("status") == "active"}
    valid: dict[str, dict[str, Any]] = {}
    ignored: list[str] = []
    for raw in feed.get("approvals", []):
        if not isinstance(raw, dict):
            continue
        unsigned = dict(raw)
        signature = str(unsigned.pop("signature", ""))
        approval_id = str(unsigned.get("approval_id", ""))
        material = materials.get(str(unsigned.get("key_id", "")))
        correct = bool(material and signature == _digest(_canonical(unsigned) + material.encode()) and unsigned.get("decision") == "approve_redraft")
        if correct:
            valid[str(unsigned.get("original_message_id", ""))] = unsigned
        else:
            ignored.append(approval_id)
    return valid, sorted(ignored)


def _normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    if isinstance(plan.get("decisions"), list):
        for raw in plan["decisions"]:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            if isinstance(row.get("dsn_ids"), list):
                row["dsn_ids"] = sorted({str(value) for value in row["dsn_ids"]})
            if isinstance(row.get("evidence_refs"), list):
                refs = []
                for value in row["evidence_refs"]:
                    ref = str(value)
                    path, separator, fragment = ref.partition("#")
                    if path.startswith("maildir/cur/") and separator:
                        ref = path
                    elif path == "evidence/approvals.json" and separator:
                        cleaned = fragment.strip()
                        for prefix in ("approval-id=", "approval_id="):
                            if cleaned.casefold().startswith(prefix):
                                cleaned = cleaned[len(prefix):]
                        if cleaned.startswith("approvals/"):
                            cleaned = cleaned.split("/", 1)[1]
                        ref = f"{path}#{cleaned}"
                    refs.append(ref)
                row["evidence_refs"] = sorted(set(refs))
            if isinstance(row.get("target_recipient"), str):
                row["target_recipient"] = row["target_recipient"].strip().lower()
            rows.append(row)
    rows.sort(key=lambda row: str(row.get("message_id", "")))
    return {
        "schema_version": plan.get("schema_version"),
        "recovery_id": plan.get("recovery_id"),
        "mailbox_checkpoint": plan.get("mailbox_checkpoint"),
        "decisions": rows,
        "quarantined_dsn_ids": sorted({str(value) for value in plan.get("quarantined_dsn_ids", [])}) if isinstance(plan.get("quarantined_dsn_ids"), list) else [],
        "ignored_approval_ids": sorted({str(value) for value in plan.get("ignored_approval_ids", [])}) if isinstance(plan.get("ignored_approval_ids"), list) else [],
        "external_messages_sent": plan.get("external_messages_sent"),
    }


def _locator(ref: str, allowed_paths: dict[str, set[str]]) -> tuple[str | None, str]:
    path, separator, fragment = str(ref).partition("#")
    accepted = allowed_paths.get(path)
    if accepted is None:
        return None, "unrecognized_path"
    if not separator:
        return path, "ok"
    cleaned = fragment.strip()
    variants = {cleaned}
    for prefix in ("message-id=", "message_id=", "dsn-id=", "dsn_id=", "approval-id=", "approval_id="):
        if cleaned.casefold().startswith(prefix):
            variants.add(cleaned[len(prefix):])
    if cleaned.startswith("approvals/"):
        variants.add(cleaned.split("/", 1)[1])
    return (path, "ok") if variants & accepted else (None, "invalid_fragment")


def _decision_diagnostics(row: dict[str, Any], original: dict[str, Any], linked: list[dict[str, Any]], approval: dict[str, Any] | None) -> dict[str, Any]:
    """Return mismatching field names and evidence categories, never values."""
    fields: list[str] = []
    categories: list[str] = []
    actions = {item["action"] for item in linked}
    if actions == {"delivered"}:
        state, action = "delivered", "close_delivery"
    elif actions == {"failed"}:
        state, action = "hard_bounced", "stage_approved_redraft" if approval else "hold_bounce_without_approval"
    elif actions == {"delayed"}:
        state, action = "delayed", "monitor_delivery"
    else:
        state, action = "pending", "preserve_pending"
    approval_id = str(approval["approval_id"]) if approval and actions == {"failed"} else None
    recipient = str(approval["corrected_recipient"]).strip().lower() if approval_id else str(original["recipient"]).strip().lower()
    draft_id = "draft-" + _digest({"message_id": original["message_id"], "approval_id": approval_id})[:12] if approval_id else None
    scalars = {"message_id": original["message_id"], "thread_id": original["thread_id"], "delivery_state": state, "action": action, "target_recipient": recipient, "approval_id": approval_id, "draft_id": draft_id}
    for key, value in scalars.items():
        actual = row.get(key)
        if key == "target_recipient" and isinstance(actual, str):
            actual = actual.strip().lower()
        if actual != value:
            fields.append(key)
    required_dsns = sorted(item["dsn_id"] for item in linked)
    if not isinstance(row.get("dsn_ids"), list) or sorted({str(value) for value in row.get("dsn_ids", [])}) != required_dsns:
        fields.append("dsn_ids")
    allowed_paths: dict[str, set[str]] = {}
    required_paths = set(original["sources"])
    for path in original["sources"]:
        allowed_paths[path] = {original["message_id"]}
    for item in linked:
        required_paths.update(item["sources"])
        for path in item["sources"]:
            allowed_paths[path] = {item["dsn_id"]}
    if approval_id:
        required_paths.add("evidence/approvals.json")
        allowed_paths["evidence/approvals.json"] = {approval_id, f"approvals/{approval_id}"}
    actual_paths: set[str] = set()
    refs = row.get("evidence_refs")
    invalid = not isinstance(refs, list)
    for ref in refs if isinstance(refs, list) else []:
        normalized, status = _locator(str(ref), allowed_paths)
        if normalized is None:
            invalid = True
            categories.append(status)
        else:
            actual_paths.add(normalized)
    missing = required_paths - actual_paths
    if set(original["sources"]) & missing:
        categories.append("missing_original_mail")
    if {path for item in linked for path in item["sources"]} & missing:
        categories.append("missing_dsn_mail")
    if approval_id and "evidence/approvals.json" in missing:
        categories.append("missing_approval_record")
    if invalid or missing or actual_paths != required_paths:
        fields.append("evidence_refs")
    return {"status": "ok" if not fields else "mismatch", "fields": sorted(set(fields)), "evidence_categories": sorted(set(categories))}


def _validate(plan: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    graph = _mail_graph()
    approvals, ignored = _approval_observations()
    published, checkpoint = _load(POLICY), _load(CHECKPOINT)
    top_fields: list[str] = []
    if set(plan) != PLAN_FIELDS:
        top_fields.append("top_level_fields")
    for key, actual, wanted in (
        ("schema_version", plan.get("schema_version"), 1),
        ("recovery_id", plan.get("recovery_id"), published.get("recovery_id")),
        ("mailbox_checkpoint", plan.get("mailbox_checkpoint"), checkpoint.get("checkpoint_id")),
        ("external_messages_sent", plan.get("external_messages_sent"), False),
    ):
        if actual != wanted or (key == "external_messages_sent" and actual is not False):
            top_fields.append(key)
    for key, wanted in (("quarantined_dsn_ids", graph["quarantine_dsn_ids"]), ("ignored_approval_ids", ignored)):
        actual = plan.get(key)
        if not isinstance(actual, list) or sorted({str(value) for value in actual}) != wanted:
            top_fields.append(key)
    diagnostics: dict[str, dict[str, Any]] = {}
    rows: dict[str, dict[str, Any]] = {}
    raw_rows = plan.get("decisions")
    if not isinstance(raw_rows, list):
        top_fields.append("decisions")
        raw_rows = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict):
            diagnostics[f"row:{index}"] = {"status": "mismatch", "fields": ["decision_object"], "evidence_categories": []}
            continue
        message_id = str(raw.get("message_id", "")) or f"row:{index}"
        if message_id in rows:
            diagnostics[message_id] = {"status": "mismatch", "fields": ["duplicate_decision"], "evidence_categories": []}
        rows[message_id] = raw
        if set(raw) != DECISION_FIELDS:
            diagnostics[message_id] = {"status": "mismatch", "fields": ["decision_fields"], "evidence_categories": []}
    for message_id, original in graph["originals"].items():
        if message_id not in rows:
            diagnostics[message_id] = {"status": "missing", "fields": ["decision_missing"], "evidence_categories": []}
        elif set(rows[message_id]) == DECISION_FIELDS and "duplicate_decision" not in diagnostics.get(message_id, {}).get("fields", []):
            result = _decision_diagnostics(rows[message_id], original, graph["linked"].get(message_id, []), approvals.get(message_id))
            if result["status"] != "ok":
                diagnostics[message_id] = result
    for message_id in set(rows) - set(graph["originals"]):
        diagnostics[message_id] = {"status": "unexpected", "fields": ["message_id"], "evidence_categories": []}
    checks = {"top_level": not top_fields, "one_decision_per_original": set(rows) == set(graph["originals"]) and len(raw_rows) == len(rows), "object_fields": not diagnostics, "offline_boundary": plan.get("external_messages_sent") is False}
    report = {"checks": checks, "top_level_mismatches": sorted(set(top_fields)), "decision_diagnostics": diagnostics}
    return all(checks.values()), report


def _restore_prepared(connection: sqlite3.Connection) -> list[str]:
    recovered = []
    for row in connection.execute("SELECT tx_id, before_json FROM recovery_journal WHERE status='prepared' ORDER BY tx_id").fetchall():
        before = json.loads(row["before_json"])
        connection.execute("DELETE FROM message_state")
        connection.executemany("INSERT INTO message_state VALUES (:message_id,:thread_id,:recipient,:delivery_state,:last_dsn_id,:action,:draft_id)", before["message_state"])
        connection.execute("DELETE FROM drafts")
        connection.executemany("INSERT INTO drafts VALUES (:draft_id,:in_reply_to,:recipient,:subject,:body,:status,:approval_id)", before["drafts"])
        connection.execute("UPDATE recovery_journal SET status='rolled_back' WHERE tx_id=?", (row["tx_id"],))
        recovered.append(str(row["tx_id"]))
    return recovered


def _apply(plan: dict[str, Any]) -> dict[str, Any]:
    valid, report = _validate(plan)
    if not valid:
        raise ValueError("plan rejected: " + json.dumps(report, sort_keys=True))
    normalized = _normalized_plan(plan)
    semantic_sha = _digest(normalized)
    recovery_id, checkpoint = str(normalized["recovery_id"]), str(normalized["mailbox_checkpoint"])
    originals = _mail_graph()["originals"]
    with _connect() as connection:
        existing = connection.execute("SELECT checkpoint_id, semantic_sha FROM recovery_runs WHERE recovery_id=?", (recovery_id,)).fetchone()
        if existing:
            if existing["checkpoint_id"] != checkpoint or existing["semantic_sha"] != semantic_sha:
                raise ValueError("conflicting replay for stable recovery identity")
            return {"status": "semantic_replay_noop", "recovered_transactions": []}
        recovered = _restore_prepared(connection)
        before = {"message_state": _rows(connection, "message_state"), "drafts": _rows(connection, "drafts")}
        tx_id = f"tx-{recovery_id}"
        connection.execute("INSERT INTO recovery_journal(tx_id,recovery_id,status,before_json) VALUES(?,?,?,?)", (tx_id, recovery_id, "prepared", _canonical(before).decode()))
        for row in normalized["decisions"]:
            message_id = str(row["message_id"])
            connection.execute("UPDATE message_state SET recipient=?,delivery_state=?,last_dsn_id=?,action=?,draft_id=? WHERE message_id=?", (row["target_recipient"], row["delivery_state"], row["dsn_ids"][-1] if row["dsn_ids"] else None, row["action"], row["draft_id"], message_id))
            if row["action"] in {"close_delivery", "stage_approved_redraft"}:
                connection.execute("DELETE FROM drafts WHERE in_reply_to=?", (message_id,))
            if row["draft_id"]:
                connection.execute("INSERT INTO drafts VALUES(?,?,?,?,?,?,?)", (row["draft_id"], message_id, row["target_recipient"], f"REISSUE: {originals[message_id]['subject']}", "Locally staged replacement after verified bounce approval. Review before sending.", "pending_review", row["approval_id"]))
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?)", (recovery_id, checkpoint, semantic_sha, "committed", _load(POLICY)["as_of"]))
        connection.execute("UPDATE recovery_journal SET status='committed' WHERE tx_id=?", (tx_id,))
    return {"status": "committed", "recovered_transactions": recovered}


def _projection_matches(connection: sqlite3.Connection, plan: dict[str, Any]) -> bool:
    """Check submitted validated rows without returning a final projection."""
    decisions = {row["message_id"]: row for row in _normalized_plan(plan)["decisions"]}
    actual_messages = {row["message_id"]: row for row in _rows(connection, "message_state")}
    if set(actual_messages) != set(decisions):
        return False
    for message_id, row in decisions.items():
        if actual_messages[message_id] != {"message_id": message_id, "thread_id": row["thread_id"], "recipient": row["target_recipient"], "delivery_state": row["delivery_state"], "last_dsn_id": row["dsn_ids"][-1] if row["dsn_ids"] else None, "action": row["action"], "draft_id": row["draft_id"]}:
            return False
    originals = _mail_graph()["originals"]
    actual_drafts = {row["in_reply_to"]: row for row in _rows(connection, "drafts")}
    wanted = {row["in_reply_to"]: row for row in _load(ROOT / "evidence/initial_local_state.json").get("drafts", [])}
    for message_id, row in decisions.items():
        if row["action"] in {"close_delivery", "stage_approved_redraft"}:
            wanted.pop(message_id, None)
        if row["draft_id"]:
            wanted[message_id] = {"draft_id": row["draft_id"], "in_reply_to": message_id, "recipient": row["target_recipient"], "subject": f"REISSUE: {originals[message_id]['subject']}", "body": "Locally staged replacement after verified bounce approval. Review before sending.", "status": "pending_review", "approval_id": row["approval_id"]}
    return actual_drafts == wanted


def _verify(plan: dict[str, Any]) -> dict[str, Any]:
    valid, report = _validate(plan)
    with _connect() as connection:
        projection_ok = valid and _projection_matches(connection, plan)
        run = connection.execute("SELECT checkpoint_id, semantic_sha, status FROM recovery_runs WHERE recovery_id=?", (str(plan.get("recovery_id", "")),)).fetchone()
        journal = _rows(connection, "recovery_journal")
    normalized = _normalized_plan(plan)
    result = {
        "schema_version": 1, "recovery_id": plan.get("recovery_id"), "plan_valid": valid,
        "projection_matches": projection_ok,
        "run_binding_valid": bool(run and run["checkpoint_id"] == plan.get("mailbox_checkpoint") and run["semantic_sha"] == _digest(normalized) and run["status"] == "committed"),
        "interrupted_journal_recovered": any(row["status"] == "rolled_back" for row in journal),
        "current_journal_committed": any(row["recovery_id"] == plan.get("recovery_id") and row["status"] == "committed" for row in journal),
        "external_messages_sent": False, "checks": report,
    }
    result["verified"] = all(result[key] for key in ("plan_valid", "projection_matches", "run_binding_valid", "interrupted_journal_recovered", "current_journal_committed"))
    (ROOT / "state/verification.json").write_bytes(_canonical(result) + b"\n")
    return result


def _stage(plan: dict[str, Any]) -> dict[str, Any]:
    verification = _verify(plan)
    if not verification["verified"]:
        raise ValueError("cannot stage an unverified recovery")
    receipt = {"schema_version": 1, "recovery_id": plan["recovery_id"], "mailbox_checkpoint": plan["mailbox_checkpoint"], "semantic_plan_sha256": _digest(_normalized_plan(plan)), "status": "pending_human_review", "draft_ids": sorted(row["draft_id"] for row in plan["decisions"] if row.get("draft_id")), "external_messages_sent": False}
    (ROOT / "state/stage_receipt.json").write_bytes(_canonical(receipt) + b"\n")
    return receipt


def _read_plan(name: str) -> dict[str, Any]:
    path = (ROOT / name).resolve()
    if path.parent != ROOT or path.is_symlink():
        raise ValueError("plan must be a regular file in the workspace root")
    return _load(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline mailbox recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    for name in ("preview", "apply", "verify", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            graph = _mail_graph()
            with _connect() as connection:
                prepared = connection.execute("SELECT COUNT(*) FROM recovery_journal WHERE status='prepared'").fetchone()[0]
            published = _load(POLICY)
            result = {"original_message_count": len(graph["originals"]), "unique_linked_dsn_count": sum(len(rows) for rows in graph["linked"].values()), "duplicate_dsn_ids": graph["duplicate_dsn_ids"], "quarantine_dsn_ids": graph["quarantine_dsn_ids"], "prepared_journal_count": prepared, "delivery_state_vocabulary": published["delivery_state_vocabulary"], "action_vocabulary": published["action_vocabulary"], "external_actions_available": False}
        else:
            plan = _read_plan(args.plan)
            if args.command == "preview":
                valid, report = _validate(plan)
                result = {"valid": valid, **report, "semantic_plan_sha256": _digest(_normalized_plan(plan))}
                (ROOT / ".mail_preview.json").write_bytes(_canonical(result) + b"\n")
                if not valid:
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return 2
            elif args.command == "apply":
                result = _apply(plan)
            elif args.command == "verify":
                result = _verify(plan)
                if not result["verified"]:
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return 2
            elif args.command == "stage":
                result = _stage(plan)
            else:
                before = DB.read_bytes()
                apply_result = _apply(plan)
                verification = _verify(plan)
                receipt_path = ROOT / "state/stage_receipt.json"
                receipt_before = receipt_path.read_bytes()
                _stage(plan)
                result = {"schema_version": 1, "recovery_id": plan["recovery_id"], "apply_status": apply_result["status"], "database_byte_stable": before == DB.read_bytes(), "receipt_byte_stable": receipt_before == receipt_path.read_bytes(), "verified": verification["verified"], "external_messages_sent": False}
                result["replay_safe"] = all((result["apply_status"] == "semantic_replay_noop", result["database_byte_stable"], result["receipt_byte_stable"], result["verified"]))
                (ROOT / "state/replay_report.json").write_bytes(_canonical(result) + b"\n")
                if not result["replay_safe"]:
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, sqlite3.Error) as error:
        print(json.dumps({"error": str(error)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
