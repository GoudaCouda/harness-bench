from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


CASES = [
    ("ICSR-2401", "SRC-A-001", "PAT-A7", "PROD-A", 2, "submitted_accepted", "expedited", "none", 4),
    ("ICSR-2402", "SRC-A-002", "PAT-B2", "PROD-B", 1, "draft", "none", "review_inbound", 3),
    ("ICSR-2403", "SRC-A-003", "PAT-C9", "PROD-C", 1, "draft", "none", "review_inbound", 2),
    ("ICSR-2404", "SRC-A-004", "PAT-D4", "PROD-D", 0, "empty", "none", "review_inbound", 0),
    ("ICSR-2405", "SRC-A-005", "PAT-E8", "PROD-E", 1, "draft", "none", "review_inbound", 1),
    ("ICSR-2406", "SRC-A-006", "PAT-F1", "PROD-F", 1, "draft", "none", "review_inbound", 1),
    ("ICSR-2407", "SRC-A-007", "PAT-G6", "PROD-G", 1, "draft", "none", "review_inbound", 1),
    ("ICSR-2408", "SRC-A-008", "PAT-H5", "PROD-H", 1, "submitted_pending_ack", "routine", "await_ack", 2),
]

VERSIONS = [
    ("ICSR-2401", 1, "initial", 1, "27.1", "BASE-2401-V1"),
    ("ICSR-2401", 2, "followup", 1, "27.1", "BASE-2401-V2"),
    ("ICSR-2402", 1, "initial", 1, "27.1", "BASE-2402-V1"),
    ("ICSR-2403", 1, "initial", 0, "27.1", "BASE-2403-V1"),
    ("ICSR-2405", 1, "initial", 0, "27.1", "BASE-2405-V1"),
    ("ICSR-2406", 1, "initial", 0, "27.1", "PAYLOAD-2406-V1"),
    ("ICSR-2407", 1, "initial", 0, "27.1", "BASE-2407-V1"),
    ("ICSR-2408", 1, "initial", 0, "27.1", "BASE-2408-V1"),
]

SUBMISSIONS = [
    ("SUB-2401-V1", "ICSR-2401", 1, "accepted", "ACK-2401-V1"),
    ("SUB-2401-V2", "ICSR-2401", 2, "accepted", "ACK-2401-V2"),
    ("SUB-2408-V1", "ICSR-2408", 1, "pending", "ACK-2408-V1"),
]

MESSAGES = [
    {"delivery_id": "DEL-01", "message_id": "MSG-2401-V3", "source_sequence": 3, "case_id": "ICSR-2401", "sender_case_id": "SRC-A-001", "version": 3, "message_type": "followup", "patient_key": "PAT-A7", "suspect_product_key": "PROD-A", "serious": True, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2401-V3", "nullification_reason": ""},
    {"delivery_id": "DEL-09", "message_id": "MSG-2402-V3", "source_sequence": 9, "case_id": "ICSR-2402", "sender_case_id": "SRC-A-002", "version": 3, "message_type": "followup", "patient_key": "PAT-B2", "suspect_product_key": "PROD-B", "serious": True, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2402-V3", "nullification_reason": ""},
    {"delivery_id": "DEL-02", "message_id": "MSG-2402-V2", "source_sequence": 4, "case_id": "ICSR-2402", "sender_case_id": "SRC-A-002", "version": 2, "message_type": "correction", "patient_key": "PAT-B2", "suspect_product_key": "PROD-B", "serious": True, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2402-V2", "nullification_reason": ""},
    {"delivery_id": "DEL-03", "message_id": "MSG-2403-V2", "source_sequence": 5, "case_id": "ICSR-2403", "sender_case_id": "SRC-A-003", "version": 2, "message_type": "nullification", "patient_key": "PAT-C9", "suspect_product_key": "PROD-C", "serious": False, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2403-V2", "nullification_reason": ""},
    {"delivery_id": "DEL-04", "message_id": "MSG-2404-V1", "source_sequence": 6, "case_id": "ICSR-2404", "sender_case_id": "SRC-A-004", "version": 1, "message_type": "initial", "patient_key": "PAT-D4", "suspect_product_key": "PROD-D", "serious": True, "fatal": True, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2404-V1", "nullification_reason": ""},
    {"delivery_id": "DEL-05", "message_id": "MSG-2405-V2", "source_sequence": 7, "case_id": "ICSR-2405", "sender_case_id": "SRC-A-005", "version": 2, "message_type": "correction", "patient_key": "PAT-OTHER", "suspect_product_key": "PROD-E", "serious": False, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2405-V2", "nullification_reason": ""},
    {"delivery_id": "DEL-06", "message_id": "MSG-2406-V1-DUP", "source_sequence": 8, "case_id": "ICSR-2406", "sender_case_id": "SRC-A-006", "version": 1, "message_type": "initial", "patient_key": "PAT-F1", "suspect_product_key": "PROD-F", "serious": False, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2406-V1", "nullification_reason": ""},
    {"delivery_id": "DEL-07", "message_id": "MSG-2407-V2", "source_sequence": 10, "case_id": "ICSR-2407", "sender_case_id": "SRC-A-007", "version": 2, "message_type": "followup", "patient_key": "PAT-G6", "suspect_product_key": "PROD-G", "serious": False, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2407-V2", "nullification_reason": ""},
    {"delivery_id": "DEL-08", "message_id": "MSG-2408-V2", "source_sequence": 11, "case_id": "ICSR-2408", "sender_case_id": "SRC-A-008", "version": 2, "message_type": "followup", "patient_key": "PAT-H5", "suspect_product_key": "PROD-H", "serious": False, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2408-V2", "nullification_reason": ""},
    {"delivery_id": "DEL-10", "message_id": "MSG-UNKNOWN", "source_sequence": 12, "case_id": "ICSR-9999", "sender_case_id": "SRC-X-999", "version": 2, "message_type": "followup", "patient_key": "PAT-X", "suspect_product_key": "PROD-X", "serious": True, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-X", "nullification_reason": ""},
    {"delivery_id": "DEL-02-RETRY", "message_id": "MSG-2402-V2", "source_sequence": 13, "case_id": "ICSR-2402", "sender_case_id": "SRC-A-002", "version": 2, "message_type": "correction", "patient_key": "PAT-B2", "suspect_product_key": "PROD-B", "serious": True, "fatal": False, "meddra_version": "27.1", "source_verified": True, "payload_digest": "PAYLOAD-2402-V2", "nullification_reason": ""},
    {"delivery_id": "DEL-11", "message_id": "MSG-2403-V2B", "source_sequence": 14, "case_id": "ICSR-2403", "sender_case_id": "SRC-A-003", "version": 2, "message_type": "followup", "patient_key": "PAT-C9", "suspect_product_key": "PROD-C", "serious": False, "fatal": False, "meddra_version": "26.1", "source_verified": True, "payload_digest": "PAYLOAD-2403-V2B", "nullification_reason": ""},
]

ACKS = [
    {"ack_id": "ACK-2401-V2", "case_id": "ICSR-2401", "version": 2, "status": "accepted", "submission_id": "SUB-2401-V2"},
    {"ack_id": "ACK-2408-V1", "case_id": "ICSR-2408", "version": 1, "status": "pending", "submission_id": "SUB-2408-V1"},
]

POLICY = {
    "schema_version": 1,
    "recovery_id": "PV-RECOVERY-140-R1",
    "permitted_meddra_versions": ["27.1"],
    "rules": {
        "delivery_identity": "first occurrence of a message_id wins; later deliveries are duplicates",
        "event_order": "process accepted messages by source_sequence, then message_id",
        "case_identity": "case_id, sender_case_id, patient_key, and suspect_product_key must all match",
        "version_chain": "new versions must be contiguous from the durable current version",
        "accepted_boundary": "an acknowledged accepted version is immutable and later local messages are held",
        "pending_boundary": "do not change a case while its durable submission acknowledgement is pending",
        "nullification": "requires a non-empty nullification_reason and exact identity",
        "terminology": "MedDRA version must be permitted",
        "queue": "accepted serious cases stage to expedited_review; accepted non-serious cases stage to routine_review",
        "execution": "local review staging only; no regulatory transmission or acknowledgement is executed",
    },
}


def build() -> None:
    evidence = WORKSPACE / "evidence"
    policy_dir = WORKSPACE / "policy"
    state = WORKSPACE / "state"
    evidence.mkdir(parents=True, exist_ok=True)
    policy_dir.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    (evidence / "inbound_messages.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in MESSAGES), encoding="utf-8"
    )
    (evidence / "acknowledgements.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in ACKS), encoding="utf-8"
    )
    (policy_dir / "pv_policy.json").write_text(
        json.dumps(POLICY, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    db = state / "pv.db"
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as connection:
        connection.executescript(
            """
            CREATE TABLE safety_cases(case_id TEXT PRIMARY KEY,sender_case_id TEXT NOT NULL,patient_key TEXT NOT NULL,suspect_product_key TEXT NOT NULL,current_version INTEGER NOT NULL,state TEXT NOT NULL,queue TEXT NOT NULL,next_action TEXT NOT NULL,row_revision INTEGER NOT NULL);
            CREATE TABLE report_versions(case_id TEXT NOT NULL,version INTEGER NOT NULL,message_type TEXT NOT NULL,serious INTEGER NOT NULL,meddra_version TEXT NOT NULL,payload_digest TEXT NOT NULL,PRIMARY KEY(case_id,version));
            CREATE TABLE submissions(submission_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,version INTEGER NOT NULL,ack_status TEXT NOT NULL,ack_id TEXT NOT NULL);
            CREATE TABLE delivery_receipts(delivery_id TEXT PRIMARY KEY,message_id TEXT NOT NULL,case_id TEXT NOT NULL,version INTEGER NOT NULL,disposition TEXT NOT NULL,recovery_id TEXT NOT NULL);
            CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY,status TEXT NOT NULL,source_checkpoint TEXT,semantic_plan_digest TEXT,final_revision INTEGER,external_transmissions INTEGER NOT NULL);
            CREATE TABLE recovery_journal(journal_id INTEGER PRIMARY KEY AUTOINCREMENT,recovery_id TEXT NOT NULL,case_id TEXT NOT NULL,before_json TEXT NOT NULL,restored INTEGER NOT NULL);
            CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO safety_cases VALUES(?,?,?,?,?,?,?,?,?)", CASES)
        connection.executemany("INSERT INTO report_versions VALUES(?,?,?,?,?,?)", VERSIONS)
        connection.executemany("INSERT INTO submissions VALUES(?,?,?,?,?)", SUBMISSIONS)
        before = dict(zip(
            ("case_id", "sender_case_id", "patient_key", "suspect_product_key", "current_version", "state", "queue", "next_action", "row_revision"),
            CASES[1], strict=True,
        ))
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?,?)", ("PV-INTERRUPTED-OLD", "interrupted", "old-checkpoint", "old-plan", 40, 0))
        connection.execute("INSERT INTO recovery_journal(recovery_id,case_id,before_json,restored) VALUES(?,?,?,0)", ("PV-INTERRUPTED-OLD", "ICSR-2402", json.dumps(before, sort_keys=True)))
        connection.execute("UPDATE safety_cases SET current_version=2,state='local_review_ready',queue='expedited_review',next_action='stage_local_review',row_revision=4 WHERE case_id='ICSR-2402'")
        connection.execute("INSERT INTO delivery_receipts VALUES(?,?,?,?,?,?)", ("OLD-DEL-02", "MSG-2402-V2", "ICSR-2402", 2, "partially_applied", "PV-INTERRUPTED-OLD"))
        connection.executemany("INSERT INTO system_state VALUES(?,?)", [("source_revision", "41"), ("stage_state", "interrupted")])
        connection.commit()
    immutable = [
        "evidence/inbound_messages.jsonl",
        "evidence/acknowledgements.jsonl",
        "policy/pv_policy.json",
    ]
    manifest = {
        "schema_version": 1,
        "files": {name: digest((WORKSPACE / name).read_bytes()) for name in immutable},
    }
    (policy_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    build()
