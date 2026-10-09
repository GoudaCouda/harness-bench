#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
ROOT = TASK / "workspace"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    policy = {
        "schema_version": 1,
        "recovery_id": "CONT-REC-2026-08-14",
        "as_of": "2026-08-14T16:00:00Z",
        "notice_deadline_days": 44,
        "event_replay_order": ["source_sequence", "event_id"],
        "verified_address_states": ["hr_verified"],
        "terminal_delivery_states": ["delivered"],
        "delivery_precedence": ["delivered_receipt", "returned_receipt", "provider_accepted", "callback_timeout", "checkpoint"],
        "decision_precedence": [
            "identity_conflict",
            "delivered_or_post_notice",
            "deadline_expired_unsent",
            "returned_with_new_verified_address",
            "returned_without_new_verified_address",
            "accepted_without_terminal_receipt",
            "beneficiary_snapshot_newer_than_draft",
            "unsent_complete_case"
        ],
        "disposition_vocabulary": [
            "hold_identity_conflict", "preserve_delivered", "preserve_post_notice_state",
            "escalate_deadline_review", "reissue_to_verified_address",
            "hold_address_resolution", "hold_delivery_investigation",
            "rebuild_beneficiary_notice", "prepare_initial_notice"
        ],
        "next_action_vocabulary": [
            "resolve_identity", "none", "stage_compliance_review",
            "stage_reissue_package", "resolve_address", "investigate_provider_receipt",
            "stage_corrected_notice", "stage_initial_notice"
        ],
        "queue_buckets": ["corrected_notice", "reissue", "delivery_investigation", "compliance_review"],
        "evidence_locator_aliases": {
            "state/continuance.db#cases:": "state/continuance.db#case:",
            "evidence/eligibility_events.jsonl#event_id:": "evidence/eligibility_events.jsonl#event:"
        },
        "external_boundary": {
            "notices_sent": False,
            "coverage_changed": False,
            "permitted_output": "local_reviewer_staging_only"
        }
    }
    events = [
        {"event_id": "EV-7205-ELECT", "source_sequence": 18, "case_id": "COV-7205", "event_type": "election_recorded", "employee_id": "EMP-805", "beneficiary_snapshot_version": 2, "beneficiary_keys": ["P-7205-E"], "address_version": 2, "address_state": "hr_verified", "occurred_at": "2026-07-19T12:00:00Z", "source_verified": True},
        {"event_id": "EV-7201-BEN3", "source_sequence": 8, "case_id": "COV-7201", "event_type": "beneficiary_snapshot", "employee_id": "EMP-801", "beneficiary_snapshot_version": 3, "beneficiary_keys": ["P-7201-E", "P-7201-S"], "address_version": 1, "address_state": "hr_verified", "occurred_at": "2026-08-04T09:10:00Z", "source_verified": True},
        {"event_id": "EV-7206-COLLIDE", "source_sequence": 21, "case_id": "COV-7206", "event_type": "address_update", "employee_id": "EMP-999", "beneficiary_snapshot_version": 1, "beneficiary_keys": ["P-7206-E"], "address_version": 2, "address_state": "hr_verified", "occurred_at": "2026-08-11T11:00:00Z", "source_verified": True},
        {"event_id": "EV-7203-ADDR2", "source_sequence": 14, "case_id": "COV-7203", "event_type": "address_update", "employee_id": "EMP-803", "beneficiary_snapshot_version": 2, "beneficiary_keys": ["P-7203-E", "P-7203-C"], "address_version": 2, "address_state": "hr_verified", "occurred_at": "2026-08-09T15:30:00Z", "source_verified": True},
        {"event_id": "EV-7201-QUAL", "source_sequence": 4, "case_id": "COV-7201", "event_type": "qualifying_event", "employee_id": "EMP-801", "beneficiary_snapshot_version": 2, "beneficiary_keys": ["P-7201-E"], "address_version": 1, "address_state": "hr_verified", "occurred_at": "2026-08-03T09:00:00Z", "source_verified": True},
        {"event_id": "EV-7203-REPLAY", "source_sequence": 13, "case_id": "COV-7203", "event_type": "address_update", "employee_id": "EMP-803", "beneficiary_snapshot_version": 2, "beneficiary_keys": ["P-7203-E", "P-7203-C"], "address_version": 1, "address_state": "self_reported", "occurred_at": "2026-08-09T15:20:00Z", "source_verified": False},
        {"event_id": "EV-7207-QUAL", "source_sequence": 1, "case_id": "COV-7207", "event_type": "qualifying_event", "employee_id": "EMP-807", "beneficiary_snapshot_version": 1, "beneficiary_keys": ["P-7207-E"], "address_version": 1, "address_state": "hr_verified", "occurred_at": "2026-06-20T08:00:00Z", "source_verified": True}
    ]
    receipts = [
        {"receipt_id": "RCPT-7204-A", "provider_message_id": "MSG-7204", "notice_id": "NOTICE-7204", "attempt_id": "ATT-7204-1", "status": "accepted", "observed_at": "2026-08-10T14:01:00Z", "address_version": 1, "verified": True},
        {"receipt_id": "RCPT-7203-R", "provider_message_id": "MSG-7203", "notice_id": "NOTICE-7203", "attempt_id": "ATT-7203-1", "status": "returned", "observed_at": "2026-08-09T14:00:00Z", "address_version": 1, "verified": True},
        {"receipt_id": "RCPT-7202-D", "provider_message_id": "MSG-7202", "notice_id": "NOTICE-7202", "attempt_id": "ATT-7202-1", "status": "delivered", "observed_at": "2026-08-07T18:40:00Z", "address_version": 2, "verified": True},
        {"receipt_id": "RCPT-7204-T", "provider_message_id": "MSG-7204", "notice_id": "NOTICE-7204", "attempt_id": "ATT-7204-1", "status": "callback_timeout", "observed_at": "2026-08-10T14:30:00Z", "address_version": 1, "verified": False},
        {"receipt_id": "RCPT-7205-D", "provider_message_id": "MSG-7205", "notice_id": "NOTICE-7205", "attempt_id": "ATT-7205-1", "status": "delivered", "observed_at": "2026-07-10T18:40:00Z", "address_version": 2, "verified": True},
        {"receipt_id": "RCPT-7202-T", "provider_message_id": "MSG-7202", "notice_id": "NOTICE-7202", "attempt_id": "ATT-7202-1", "status": "callback_timeout", "observed_at": "2026-08-07T18:10:00Z", "address_version": 2, "verified": False}
    ]
    checkpoint = {
        "schema_version": 1,
        "written_at": "2026-08-10T14:31:00Z",
        "source_revision": 41,
        "cases": {
            "COV-7201": {"state": "drafted", "notice_version": 1},
            "COV-7202": {"state": "delivery_timeout", "notice_version": 1},
            "COV-7203": {"state": "retry_queued", "notice_version": 1},
            "COV-7204": {"state": "delivery_timeout", "notice_version": 1},
            "COV-7205": {"state": "delivered", "notice_version": 2},
            "COV-7206": {"state": "drafted", "notice_version": 1},
            "COV-7207": {"state": "eligible_unsent", "notice_version": 0}
        }
    }
    write_json(ROOT / "policy/continuance_policy.json", policy)
    write_jsonl(ROOT / "evidence/eligibility_events.jsonl", events)
    write_jsonl(ROOT / "evidence/delivery_receipts.jsonl", receipts)
    write_json(ROOT / "state/stale_checkpoint.json", checkpoint)

    db = ROOT / "state/continuance.db"
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as connection:
        connection.executescript("""
        CREATE TABLE cases(case_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, qualifying_event TEXT NOT NULL, event_date TEXT NOT NULL, case_state TEXT NOT NULL, beneficiary_snapshot_version INTEGER NOT NULL, address_version INTEGER NOT NULL, notice_id TEXT, notice_version INTEGER NOT NULL, row_revision INTEGER NOT NULL);
        CREATE TABLE beneficiaries(case_id TEXT NOT NULL, person_key TEXT NOT NULL, relationship TEXT NOT NULL, eligible INTEGER NOT NULL, snapshot_version INTEGER NOT NULL, PRIMARY KEY(case_id, person_key));
        CREATE TABLE notices(notice_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, notice_version INTEGER NOT NULL, beneficiary_keys_json TEXT NOT NULL, address_version INTEGER NOT NULL, state TEXT NOT NULL, prepared_at TEXT, sent_at TEXT, executed INTEGER NOT NULL);
        CREATE TABLE delivery_attempts(attempt_id TEXT PRIMARY KEY, notice_id TEXT NOT NULL, provider_message_id TEXT NOT NULL, address_version INTEGER NOT NULL, status TEXT NOT NULL, accepted_at TEXT, delivered_at TEXT, returned_at TEXT, executed INTEGER NOT NULL);
        CREATE TABLE recovery_queue(queue_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, executed INTEGER NOT NULL, recovery_id TEXT NOT NULL);
        CREATE TABLE decision_receipts(recovery_id TEXT NOT NULL, case_id TEXT NOT NULL, disposition TEXT NOT NULL, next_local_action TEXT NOT NULL, PRIMARY KEY(recovery_id, case_id));
        CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL, semantic_plan_digest TEXT NOT NULL, semantic_state_digest TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE recovery_journal(journal_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL, table_name TEXT NOT NULL, record_id TEXT NOT NULL, before_json TEXT, restored INTEGER NOT NULL);
        CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        cases = [
            ("COV-7201", "EMP-801", "termination", "2026-08-03", "drafted", 2, 1, "NOTICE-7201", 1, 4),
            ("COV-7202", "EMP-802", "hours_reduction", "2026-08-05", "delivery_timeout", 1, 2, "NOTICE-7202", 1, 5),
            ("COV-7203", "EMP-803", "termination", "2026-08-06", "local_retry_queued", 2, 1, "NOTICE-7203", 1, 7),
            ("COV-7204", "EMP-804", "death", "2026-08-08", "delivery_timeout", 1, 1, "NOTICE-7204", 1, 2),
            ("COV-7205", "EMP-805", "termination", "2026-07-05", "elected", 2, 2, "NOTICE-7205", 2, 8),
            ("COV-7206", "EMP-806", "termination", "2026-08-10", "drafted", 1, 1, "NOTICE-7206", 1, 3),
            ("COV-7207", "EMP-807", "hours_reduction", "2026-06-20", "eligible_unsent", 1, 1, None, 0, 1)
        ]
        connection.executemany("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?)", cases)
        beneficiaries = [
            ("COV-7201", "P-7201-E", "employee", 1, 2),
            ("COV-7202", "P-7202-E", "employee", 1, 1),
            ("COV-7203", "P-7203-E", "employee", 1, 2), ("COV-7203", "P-7203-C", "child", 1, 2),
            ("COV-7204", "P-7204-S", "spouse", 1, 1),
            ("COV-7205", "P-7205-E", "employee", 1, 2),
            ("COV-7206", "P-7206-E", "employee", 1, 1),
            ("COV-7207", "P-7207-E", "employee", 1, 1)
        ]
        connection.executemany("INSERT INTO beneficiaries VALUES (?,?,?,?,?)", beneficiaries)
        notices = [
            ("NOTICE-7201", "COV-7201", 1, '["P-7201-E"]', 1, "drafted", "2026-08-03T12:00:00Z", None, 0),
            ("NOTICE-7202", "COV-7202", 1, '["P-7202-E"]', 2, "sent", "2026-08-06T10:00:00Z", "2026-08-06T12:00:00Z", 1),
            ("NOTICE-7203", "COV-7203", 1, '["P-7203-C", "P-7203-E"]', 1, "sent", "2026-08-07T10:00:00Z", "2026-08-07T12:00:00Z", 1),
            ("NOTICE-7204", "COV-7204", 1, '["P-7204-S"]', 1, "sent", "2026-08-09T10:00:00Z", "2026-08-09T12:00:00Z", 1),
            ("NOTICE-7205", "COV-7205", 2, '["P-7205-E"]', 2, "delivered", "2026-07-08T10:00:00Z", "2026-07-08T12:00:00Z", 1),
            ("NOTICE-7206", "COV-7206", 1, '["P-7206-E"]', 1, "drafted", "2026-08-11T10:00:00Z", None, 0)
        ]
        connection.executemany("INSERT INTO notices VALUES (?,?,?,?,?,?,?,?,?)", notices)
        attempts = [
            ("ATT-7202-1", "NOTICE-7202", "MSG-7202", 2, "callback_timeout", "2026-08-06T12:01:00Z", None, None, 1),
            ("ATT-7203-1", "NOTICE-7203", "MSG-7203", 1, "returned", "2026-08-07T12:01:00Z", None, "2026-08-09T14:00:00Z", 1),
            ("ATT-7204-1", "NOTICE-7204", "MSG-7204", 1, "callback_timeout", "2026-08-10T14:01:00Z", None, None, 1),
            ("ATT-7205-1", "NOTICE-7205", "MSG-7205", 2, "delivered", "2026-07-08T12:01:00Z", "2026-07-10T18:40:00Z", None, 1)
        ]
        connection.executemany("INSERT INTO delivery_attempts VALUES (?,?,?,?,?,?,?,?,?)", attempts)
        before = dict(zip(["case_id", "employee_id", "qualifying_event", "event_date", "case_state", "beneficiary_snapshot_version", "address_version", "notice_id", "notice_version", "row_revision"], cases[2], strict=True))
        before.update(case_state="returned", row_revision=6)
        connection.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?)", ("CONT-CRASH-OLD", "old", "old", "old", "interrupted"))
        connection.execute("INSERT INTO recovery_queue VALUES (?,?,?,?,?,?)", ("Q-PARTIAL-7203", "COV-7203", "resend_notice", "partially_written", 0, "CONT-CRASH-OLD"))
        connection.execute("INSERT INTO recovery_journal VALUES (?,?,?,?,?,?)", ("J-OLD-CASE-7203", "CONT-CRASH-OLD", "cases", "COV-7203", json.dumps(before, sort_keys=True), 0))
        connection.execute("INSERT INTO recovery_journal VALUES (?,?,?,?,?,?)", ("J-OLD-QUEUE-7203", "CONT-CRASH-OLD", "recovery_queue", "Q-PARTIAL-7203", None, 0))
        connection.execute("INSERT INTO system_state VALUES (?,?)", ("source_revision", "42"))
        connection.commit()

    sources = [
        "policy/continuance_policy.json", "evidence/eligibility_events.jsonl",
        "evidence/delivery_receipts.jsonl", "state/stale_checkpoint.json"
    ]
    write_json(ROOT / "policy/source_manifest.json", {
        "schema_version": 1,
        "files": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    })


if __name__ == "__main__":
    main()
