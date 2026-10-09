from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_workspace() -> None:
    for path in (
        WORKSPACE / "state",
        WORKSPACE / "staging",
        WORKSPACE / "evidence/documents",
        WORKSPACE / "policy",
    ):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    for name in (".pa_preview.json", "recovery_plan.json", "authorization_handoff.md"):
        path = WORKSPACE / name
        if path.exists():
            path.unlink()
    policy = {
        "schema_version": 1,
        "recovery_id": "PAR-20260819-01",
        "target_case_id": "PA-502",
        "as_of": "2026-08-19",
        "required_document_types": [
            "signed_order",
            "clinical_note",
            "conservative_therapy",
        ],
        "minimum_necessary": "one current signed matching document per required type; never psychotherapy",
        "authorization_window_to": "2026-10-14",
        "external_boundary": "local_stage_only",
    }
    events = [
        {
            "delivery_id": "DEL-001",
            "event_id": "EV-ELIG-12",
            "event_type": "eligibility",
            "sequence": 12,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "payer_id": "SYN-PAYER-A",
            "payload": {
                "status": "active",
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
            },
        },
        {
            "delivery_id": "DEL-002",
            "event_id": "EV-ORD-04",
            "event_type": "order",
            "sequence": 4,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "payer_id": "SYN-PAYER-A",
            "payload": {"order_id": "ORD-OLD", "service_code": "72148"},
        },
        {
            "delivery_id": "DEL-003",
            "event_id": "EV-ORD-05",
            "event_type": "order",
            "sequence": 5,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "payer_id": "SYN-PAYER-A",
            "payload": {"order_id": "ORD-77", "service_code": "72148"},
        },
        {
            "delivery_id": "DEL-004",
            "event_id": "EV-ELIG-11",
            "event_type": "eligibility",
            "sequence": 11,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "payer_id": "SYN-PAYER-A",
            "payload": {
                "status": "terminated",
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
            },
        },
        {
            "delivery_id": "DEL-005",
            "event_id": "EV-ORD-05",
            "event_type": "order",
            "sequence": 5,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "payer_id": "SYN-PAYER-A",
            "payload": {"order_id": "ORD-77", "service_code": "72148"},
        },
        {
            "delivery_id": "DEL-006",
            "event_id": "EV-ELIG-X",
            "event_type": "eligibility",
            "sequence": 99,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-WRONG",
            "payer_id": "SYN-PAYER-A",
            "payload": {
                "status": "active",
                "effective_from": "2026-01-01",
                "effective_to": "2027-12-31",
            },
        },
        {
            "delivery_id": "DEL-007",
            "event_id": "EV-ELIG-12",
            "event_type": "eligibility",
            "sequence": 12,
            "case_id": "PA-502",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "payer_id": "SYN-PAYER-A",
            "payload": {
                "status": "active",
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
            },
        },
    ]
    documents = [
        {
            "document_id": "DOC-ORD-77",
            "document_type": "signed_order",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2026-08-17",
            "valid_through": "2026-11-17",
            "signed": True,
            "current": True,
            "sensitive_category": None,
        },
        {
            "document_id": "DOC-CLN-22",
            "document_type": "clinical_note",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2026-08-16",
            "valid_through": "2026-10-16",
            "signed": True,
            "current": True,
            "sensitive_category": None,
        },
        {
            "document_id": "DOC-PT-09",
            "document_type": "conservative_therapy",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2026-08-12",
            "valid_through": "2026-10-12",
            "signed": True,
            "current": True,
            "sensitive_category": None,
        },
        {
            "document_id": "DOC-CLN-OLD",
            "document_type": "clinical_note",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2025-02-01",
            "valid_through": "2025-04-01",
            "signed": True,
            "current": False,
            "sensitive_category": None,
        },
        {
            "document_id": "DOC-PSYCH-4",
            "document_type": "clinical_note",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2026-08-18",
            "valid_through": "2026-12-01",
            "signed": True,
            "current": True,
            "sensitive_category": "psychotherapy_note",
        },
        {
            "document_id": "DOC-WRONG-MEMBER",
            "document_type": "clinical_note",
            "patient_id": "PAT-4102",
            "member_id": "MEM-0000",
            "service_code": "72148",
            "effective_at": "2026-08-18",
            "valid_through": "2026-12-01",
            "signed": True,
            "current": True,
            "sensitive_category": None,
        },
        {
            "document_id": "DOC-UNSIGNED-PT",
            "document_type": "conservative_therapy",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2026-08-18",
            "valid_through": "2026-12-01",
            "signed": False,
            "current": True,
            "sensitive_category": None,
        },
        {
            "document_id": "DOC-LAB-EXTRA",
            "document_type": "laboratory_result",
            "patient_id": "PAT-4102",
            "member_id": "MEM-8731",
            "service_code": "72148",
            "effective_at": "2026-08-18",
            "valid_through": "2026-12-01",
            "signed": True,
            "current": True,
            "sensitive_category": None,
        },
    ]
    write(WORKSPACE / "policy/prior_auth_policy.json", policy)
    (WORKSPACE / "evidence/events.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events),
        encoding="utf-8",
    )
    write(
        WORKSPACE / "evidence/documents.json",
        {"schema_version": 1, "documents": documents},
    )
    for row in documents:
        write(
            WORKSPACE / f"evidence/documents/{row['document_id']}.json",
            {**row, "synthetic": True},
        )
    files = {}
    for path in sorted((WORKSPACE / "policy").glob("*.json")) + sorted(
        (WORKSPACE / "evidence").rglob("*")
    ):
        if path.is_file() and path.name != "source_manifest.json":
            files[path.relative_to(WORKSPACE).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    write(
        WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": files}
    )
    with sqlite3.connect(WORKSPACE / "state/portal.db") as connection:
        connection.executescript("""
        CREATE TABLE cases(case_id TEXT PRIMARY KEY,patient_id TEXT NOT NULL,member_id TEXT NOT NULL,payer_id TEXT NOT NULL,service_code TEXT NOT NULL,diagnosis_code TEXT NOT NULL,service_from TEXT NOT NULL,service_to TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL);
        CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(case_id),status TEXT NOT NULL,transmitted_at TEXT,denial_at TEXT,payer_reference TEXT,queue_id TEXT,packet_digest TEXT,version INTEGER NOT NULL);
        CREATE TABLE local_queue(queue_id TEXT PRIMARY KEY,attempt_id TEXT NOT NULL,status TEXT NOT NULL,packet_digest TEXT,packet_json TEXT NOT NULL,transmitted INTEGER NOT NULL);
        CREATE TABLE event_receipts(delivery_id TEXT PRIMARY KEY,event_id TEXT NOT NULL,event_type TEXT NOT NULL,sequence INTEGER NOT NULL,disposition TEXT NOT NULL,recovery_id TEXT NOT NULL,external_action INTEGER NOT NULL);
        CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY,status TEXT NOT NULL,source_checkpoint TEXT,semantic_plan_digest TEXT,semantic_state_digest TEXT,final_revision INTEGER,external_actions_executed INTEGER NOT NULL);
        CREATE TABLE recovery_journal(journal_id INTEGER PRIMARY KEY AUTOINCREMENT,recovery_id TEXT NOT NULL,table_name TEXT NOT NULL,record_id TEXT NOT NULL,before_json TEXT NOT NULL,restored INTEGER NOT NULL);
        CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        cases = [
            (
                "PA-401",
                "PAT-3100",
                "MEM-7001",
                "SYN-PAYER-A",
                "70551",
                "G43.909",
                "2026-07-01",
                "2026-07-20",
                "submitted",
                6,
            ),
            (
                "PA-402",
                "PAT-3200",
                "MEM-7002",
                "SYN-PAYER-A",
                "73721",
                "M25.561",
                "2026-07-05",
                "2026-07-25",
                "denied",
                8,
            ),
            (
                "PA-502",
                "PAT-4102",
                "MEM-8731",
                "SYN-PAYER-A",
                "72148",
                "M54.16",
                "2026-09-15",
                "2026-09-30",
                "partial_local",
                2,
            ),
        ]
        connection.executemany("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?)", cases)
        attempts = [
            (
                "ATT-DEN-402",
                "PA-402",
                "denied",
                "2026-07-01T15:00:00Z",
                "2026-07-08T18:00:00Z",
                "DEN-9088",
                None,
                "immutable-denied-digest",
                8,
            ),
            (
                "ATT-PART-502",
                "PA-502",
                "partial_local",
                None,
                None,
                None,
                "Q-PART-502",
                None,
                2,
            ),
            (
                "ATT-SUB-401",
                "PA-401",
                "submitted",
                "2026-06-28T16:40:00Z",
                None,
                "PAY-4410",
                None,
                "immutable-submitted-digest",
                6,
            ),
        ]
        connection.executemany(
            "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?)", attempts
        )
        before_queue = {
            "queue_id": "Q-PART-502",
            "attempt_id": "ATT-PART-502",
            "status": "incomplete",
            "packet_digest": None,
            "packet_json": json.dumps({"documents": ["DOC-ORD-77"]}, sort_keys=True),
            "transmitted": 0,
        }
        connection.execute(
            "INSERT INTO local_queue VALUES(?,?,?,?,?,?)", tuple(before_queue.values())
        )
        connection.executemany(
            "INSERT INTO system_state VALUES(?,?)",
            (
                ("source_revision", "73"),
                ("projection_revision", "73"),
                ("stage_state", "interrupted"),
            ),
        )
        columns = [row[1] for row in connection.execute("PRAGMA table_info(attempts)")]
        before_attempt = dict(
            zip(
                columns,
                connection.execute(
                    "SELECT * FROM attempts WHERE attempt_id='ATT-PART-502'"
                ).fetchone(),
                strict=True,
            )
        )
        connection.execute(
            "INSERT INTO recovery_runs VALUES('PAR-INTERRUPTED-20260818','interrupted',NULL,NULL,NULL,NULL,0)"
        )
        connection.execute(
            "INSERT INTO recovery_journal(recovery_id,table_name,record_id,before_json,restored) VALUES(?,?,?,?,0)",
            (
                "PAR-INTERRUPTED-20260818",
                "attempts",
                "ATT-PART-502",
                json.dumps(before_attempt, sort_keys=True),
            ),
        )
        connection.execute(
            "INSERT INTO recovery_journal(recovery_id,table_name,record_id,before_json,restored) VALUES(?,?,?,?,0)",
            (
                "PAR-INTERRUPTED-20260818",
                "local_queue",
                "Q-PART-502",
                json.dumps(before_queue, sort_keys=True),
            ),
        )
        connection.execute(
            "UPDATE attempts SET status='recovered_local_replacement',packet_digest='partial-bad-digest',version=3 WHERE attempt_id='ATT-PART-502'"
        )
        connection.execute(
            "UPDATE local_queue SET status='staged_offline',packet_digest='partial-bad-digest',packet_json='{}' WHERE queue_id='Q-PART-502'"
        )
        connection.commit()


def module():
    spec = importlib.util.spec_from_file_location(
        "pa_fixture_controller", WORKSPACE / "pa_ctl.py"
    )
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def oracle_module():
    spec = importlib.util.spec_from_file_location(
        "pa_fixture_oracle", TASK / "tests/test_outcome.py"
    )
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    controller = module()
    plan = oracle_module().seed_truth()["plan"]
    write(WORKSPACE / "recovery_plan.json", plan)
    handoff = """# Prior-authorization recovery handoff

For synthetic case PA-502, the recovered packet preserves patient PAT-4102, member MEM-8731, payer SYN-PAYER-A, service code 72148, diagnosis M54.16, service dates 2026-09-15 through 2026-09-30, and authorization window 2026-09-15 through 2026-10-14. Eligibility EV-ELIG-12 and order EV-ORD-05 are current after sequence ordering; older events were superseded, duplicate deliveries were ignored, and the wrong-member eligibility event was rejected.

The minimum-necessary packet contains DOC-ORD-77, DOC-CLN-22, and DOC-PT-09. DOC-CLN-OLD was stale, DOC-PSYCH-4 was a sensitive psychotherapy note, DOC-WRONG-MEMBER had the wrong member, DOC-UNSIGNED-PT was unsigned, and DOC-LAB-EXTRA was unnecessary, so each was excluded.

The interrupted SQLite journal restored the before-images for ATT-PART-502 and Q-PART-502 before one atomic local projection created Q-PA-502. ATT-SUB-401 remains submitted with its payer reference, and ATT-DEN-402 remains denied with its denial timestamp; neither irreversible boundary was reopened. Hash verification closes the source checkpoint, semantic plan, state, packet, manifest, and receipt. Equivalent replay was an idempotent no-op.

Everything remains an offline local staging artifact. No payer transmission, clinical or coverage decision, patient notification, appointment scheduling, or external contact occurred.
"""
    (WORKSPACE / "authorization_handoff.md").write_text(handoff, encoding="utf-8")
    for command in (
        ("preview", "recovery_plan.json"),
        ("apply", "recovery_plan.json"),
        ("stage", "recovery_plan.json"),
        ("verify", "recovery_plan.json"),
        ("replay", "recovery_plan.json"),
    ):
        assert getattr(controller, command[0])(*command[1:]) == 0
    for relative in (
        "recovery_plan.json",
        ".pa_preview.json",
        "authorization_handoff.md",
        "state/portal.db",
        "state/verification.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
        "staging/prior_auth_packet.json",
        "staging/packet_manifest.json",
    ):
        source = WORKSPACE / relative
        target = REFERENCE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    build_workspace()


if __name__ == "__main__":
    build_workspace()
    build_reference()
