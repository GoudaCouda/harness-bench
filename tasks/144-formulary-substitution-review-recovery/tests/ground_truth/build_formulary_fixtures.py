from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def build() -> None:
    for relative in ("policy", "evidence", "state", "staging"):
        target = WORKSPACE / relative
        if target.exists():
            shutil.rmtree(target)
    for relative in (
        "formulary_recovery_plan.json",
        ".formulary_preview.json",
        "formulary_handoff.md",
    ):
        (WORKSPACE / relative).unlink(missing_ok=True)
    for relative in ("policy", "evidence/documents", "state"):
        (WORKSPACE / relative).mkdir(parents=True, exist_ok=True)

    policy = {
        "schema_version": 1,
        "recovery_id": "FSR-20260819-01",
        "as_of_utc": "2026-08-19T16:00:00Z",
        "protected_statuses": ["dispensed", "cancelled"],
        "ready_state": "ready_local_formulary_review",
        "hold_precedence": [
            "evidence_integrity",
            "daw_restriction",
            "allergy_conflict",
            "step_therapy",
            "prior_authorization",
            "channel_restriction",
        ],
        "document_rules": {
            "prior_authorization": {"signed": True, "hash_required": True}
        },
        "event_dispositions": [
            "applied",
            "duplicate_delivery_ignored",
            "event_identity_collision_quarantined",
            "sequence_conflict_quarantined",
            "unknown_prescription_ignored",
            "protected_boundary_ignored",
        ],
        "next_local_actions": [
            "stage_local_formulary_review",
            "route_prescriber_daw_review",
            "route_clinical_allergy_review",
            "route_step_therapy_review",
            "route_prior_authorization_review",
            "route_specialty_channel_review",
            "none",
        ],
        "external_actions_executed": False,
    }
    write_json(WORKSPACE / "policy/formulary_policy.json", policy)

    documents = {
        "PA-205": {
            "document_id": "PA-205",
            "kind": "prior_authorization",
            "rx_id": "RX-205",
            "approved": True,
            "valid_through": "2026-09-30T23:59:59Z",
            "signed_by": "synthetic-reviewer-A",
        },
        "PA-209": {
            "document_id": "PA-209",
            "kind": "prior_authorization",
            "rx_id": "RX-209",
            "approved": True,
            "valid_through": "2026-09-30T23:59:59Z",
            "signed_by": "synthetic-reviewer-B",
        },
    }
    for key, value in documents.items():
        write_json(WORKSPACE / f"evidence/documents/{key}.json", value)

    events = [
        {
            "delivery_id": "DL-001",
            "event_id": "EV-RX201-PLAN",
            "rx_id": "RX-201",
            "source_sequence": 2,
            "event_type": "plan_refresh",
            "occurred_at": "2026-08-19T10:00:00Z",
        },
        {
            "delivery_id": "DL-002",
            "event_id": "EV-RX201-PLAN",
            "rx_id": "RX-201",
            "source_sequence": 2,
            "event_type": "plan_refresh",
            "occurred_at": "2026-08-19T10:00:00Z",
        },
        {
            "delivery_id": "DL-011",
            "event_id": "EV-IDENTITY-203",
            "rx_id": "RX-203",
            "source_sequence": 4,
            "event_type": "profile_refresh",
            "occurred_at": "2026-08-19T10:05:00Z",
        },
        {
            "delivery_id": "DL-012",
            "event_id": "EV-IDENTITY-203",
            "rx_id": "RX-203",
            "source_sequence": 5,
            "event_type": "profile_refresh",
            "occurred_at": "2026-08-19T10:06:00Z",
        },
        {
            "delivery_id": "DL-021",
            "event_id": "EV-RX204-A",
            "rx_id": "RX-204",
            "source_sequence": 7,
            "event_type": "step_refresh",
            "occurred_at": "2026-08-19T10:10:00Z",
        },
        {
            "delivery_id": "DL-022",
            "event_id": "EV-RX204-B",
            "rx_id": "RX-204",
            "source_sequence": 7,
            "event_type": "step_refresh",
            "occurred_at": "2026-08-19T10:11:00Z",
        },
        {
            "delivery_id": "DL-031",
            "event_id": "EV-UNKNOWN",
            "rx_id": "RX-999",
            "source_sequence": 1,
            "event_type": "plan_refresh",
            "occurred_at": "2026-08-19T10:12:00Z",
        },
        {
            "delivery_id": "DL-041",
            "event_id": "EV-RX206-LATE",
            "rx_id": "RX-206",
            "source_sequence": 8,
            "event_type": "plan_refresh",
            "occurred_at": "2026-08-19T10:13:00Z",
        },
        {
            "delivery_id": "DL-051",
            "event_id": "EV-RX207-LATE",
            "rx_id": "RX-207",
            "source_sequence": 3,
            "event_type": "plan_refresh",
            "occurred_at": "2026-08-19T10:14:00Z",
        },
        {
            "delivery_id": "DL-061",
            "event_id": "EV-RX202-DAW",
            "rx_id": "RX-202",
            "source_sequence": 3,
            "event_type": "daw_refresh",
            "occurred_at": "2026-08-19T10:15:00Z",
        },
        {
            "delivery_id": "DL-071",
            "event_id": "EV-RX205-PA",
            "rx_id": "RX-205",
            "source_sequence": 4,
            "event_type": "authorization_refresh",
            "occurred_at": "2026-08-19T10:16:00Z",
        },
        {
            "delivery_id": "DL-081",
            "event_id": "EV-RX208-RULE",
            "rx_id": "RX-208",
            "source_sequence": 3,
            "event_type": "formulary_refresh",
            "occurred_at": "2026-08-19T10:17:00Z",
        },
        {
            "delivery_id": "DL-091",
            "event_id": "EV-RX209-PA",
            "rx_id": "RX-209",
            "source_sequence": 2,
            "event_type": "authorization_refresh",
            "occurred_at": "2026-08-19T10:18:00Z",
        },
    ]
    (WORKSPACE / "evidence/benefit_events.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events),
        encoding="utf-8",
    )

    database = WORKSPACE / "state/formulary.db"
    with sqlite3.connect(database) as con:
        con.executescript(
            """
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE members(member_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, allergy_codes_json TEXT NOT NULL);
            CREATE TABLE products(product_code TEXT PRIMARY KEY, ingredient TEXT NOT NULL, strength TEXT NOT NULL, dosage_form TEXT NOT NULL, substitution_group TEXT NOT NULL, excipient_codes_json TEXT NOT NULL, specialty INTEGER NOT NULL);
            CREATE TABLE prescriptions(rx_id TEXT PRIMARY KEY, member_id TEXT NOT NULL, current_product_code TEXT NOT NULL, prescribed_at TEXT NOT NULL, status TEXT NOT NULL, daw_code TEXT NOT NULL, channel TEXT NOT NULL, local_disposition TEXT, local_target_product_code TEXT, local_next_action TEXT);
            CREATE TABLE formulary_rules(rule_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, product_code TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT, target_product_code TEXT NOT NULL, substitution_group TEXT NOT NULL, required_step_code TEXT, requires_pa INTEGER NOT NULL, required_channel TEXT NOT NULL);
            CREATE TABLE step_records(member_id TEXT NOT NULL, step_code TEXT NOT NULL, completed_at TEXT NOT NULL, PRIMARY KEY(member_id, step_code));
            CREATE TABLE authorization_register(document_id TEXT PRIMARY KEY, rx_id TEXT NOT NULL, local_path TEXT NOT NULL, sha256 TEXT NOT NULL, signed INTEGER NOT NULL);
            CREATE TABLE review_runs(recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL, plan_hash TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE recovery_journal(journal_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL, rx_id TEXT NOT NULL, before_json TEXT NOT NULL, restored INTEGER NOT NULL);
            CREATE TABLE rx_projections(recovery_id TEXT NOT NULL, rx_id TEXT NOT NULL, plan_hash TEXT NOT NULL, disposition TEXT NOT NULL, final_local_state TEXT NOT NULL, target_product_code TEXT NOT NULL, next_local_action TEXT NOT NULL, evidence_json TEXT NOT NULL, PRIMARY KEY(recovery_id, rx_id));
            """
        )
        con.execute("INSERT INTO system_state VALUES (?,?)", ("source_revision", "11"))
        con.executemany(
            "INSERT INTO members VALUES (?,?,?)",
            [
                ("MB-201", "PLAN-A", "[]"),
                ("MB-202", "PLAN-A", "[]"),
                ("MB-203", "PLAN-A", '["EXC-LACTOSE"]'),
                ("MB-204", "PLAN-A", "[]"),
                ("MB-205", "PLAN-B", "[]"),
                ("MB-206", "PLAN-A", "[]"),
                ("MB-207", "PLAN-A", "[]"),
                ("MB-208", "PLAN-A", "[]"),
                ("MB-209", "PLAN-B", "[]"),
            ],
        )
        con.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?,?,?)",
            [
                ("BR-CARD-20", "cardiol", "20mg", "tablet", "SG-CARD", "[]", 0),
                ("GN-CARD-20", "cardiol", "20mg", "tablet", "SG-CARD", "[]", 0),
                ("BR-THYR-50", "thyrox", "50mcg", "tablet", "SG-THYR", "[]", 0),
                ("GN-THYR-50", "thyrox", "50mcg", "tablet", "SG-THYR", "[]", 0),
                ("BR-NEUR-10", "neurozil", "10mg", "tablet", "SG-NEUR", "[]", 0),
                (
                    "GN-NEUR-10",
                    "neurozil",
                    "10mg",
                    "tablet",
                    "SG-NEUR",
                    '["EXC-LACTOSE"]',
                    0,
                ),
                ("BR-DERM-1", "dermol", "1%", "cream", "SG-DERM", "[]", 0),
                ("GN-DERM-1", "dermol", "1%", "cream", "SG-DERM", "[]", 0),
                ("BR-IMM-40", "immunex", "40mg", "injector", "SG-IMM", "[]", 1),
                ("BS-IMM-40", "immunex", "40mg", "injector", "SG-IMM", "[]", 1),
            ],
        )
        prescriptions = [
            (
                "RX-201",
                "MB-201",
                "BR-CARD-20",
                "2026-08-18T09:00:00Z",
                "pending_review",
                "0",
                "retail",
                None,
                None,
                None,
            ),
            (
                "RX-202",
                "MB-202",
                "BR-THYR-50",
                "2026-08-18T09:30:00Z",
                "pending_review",
                "1",
                "retail",
                None,
                None,
                None,
            ),
            (
                "RX-203",
                "MB-203",
                "BR-NEUR-10",
                "2026-08-18T10:00:00Z",
                "pending_review",
                "0",
                "retail",
                None,
                None,
                None,
            ),
            (
                "RX-204",
                "MB-204",
                "BR-DERM-1",
                "2026-08-18T10:30:00Z",
                "pending_review",
                "0",
                "retail",
                "ready_local_formulary_review",
                "GN-DERM-1",
                "stage_local_formulary_review",
            ),
            (
                "RX-205",
                "MB-205",
                "BR-IMM-40",
                "2026-08-18T11:00:00Z",
                "pending_review",
                "0",
                "specialty",
                None,
                None,
                None,
            ),
            (
                "RX-206",
                "MB-206",
                "BR-CARD-20",
                "2026-08-18T11:30:00Z",
                "dispensed",
                "0",
                "retail",
                None,
                None,
                None,
            ),
            (
                "RX-207",
                "MB-207",
                "BR-DERM-1",
                "2026-08-18T12:00:00Z",
                "cancelled",
                "0",
                "retail",
                None,
                None,
                None,
            ),
            (
                "RX-208",
                "MB-208",
                "BR-CARD-20",
                "2025-12-15T12:00:00Z",
                "pending_review",
                "0",
                "retail",
                None,
                None,
                None,
            ),
            (
                "RX-209",
                "MB-209",
                "BR-IMM-40",
                "2026-08-18T12:30:00Z",
                "pending_review",
                "0",
                "retail",
                None,
                None,
                None,
            ),
        ]
        con.executemany(
            "INSERT INTO prescriptions VALUES (?,?,?,?,?,?,?,?,?,?)", prescriptions
        )
        con.executemany(
            "INSERT INTO formulary_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "FR-CARD-OLD",
                    "PLAN-A",
                    "BR-CARD-20",
                    "2025-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "GN-CARD-20",
                    "SG-CARD",
                    None,
                    0,
                    "retail",
                ),
                (
                    "FR-CARD-NEW",
                    "PLAN-A",
                    "BR-CARD-20",
                    "2026-01-01T00:00:00Z",
                    None,
                    "GN-CARD-20",
                    "SG-CARD",
                    None,
                    0,
                    "retail",
                ),
                (
                    "FR-THYR-1",
                    "PLAN-A",
                    "BR-THYR-50",
                    "2026-01-01T00:00:00Z",
                    None,
                    "GN-THYR-50",
                    "SG-THYR",
                    None,
                    0,
                    "retail",
                ),
                (
                    "FR-NEUR-1",
                    "PLAN-A",
                    "BR-NEUR-10",
                    "2026-01-01T00:00:00Z",
                    None,
                    "GN-NEUR-10",
                    "SG-NEUR",
                    None,
                    0,
                    "retail",
                ),
                (
                    "FR-DERM-1",
                    "PLAN-A",
                    "BR-DERM-1",
                    "2026-01-01T00:00:00Z",
                    None,
                    "GN-DERM-1",
                    "SG-DERM",
                    "STEP-DERM",
                    0,
                    "retail",
                ),
                (
                    "FR-IMM-1",
                    "PLAN-B",
                    "BR-IMM-40",
                    "2026-01-01T00:00:00Z",
                    None,
                    "BS-IMM-40",
                    "SG-IMM",
                    None,
                    1,
                    "specialty",
                ),
            ],
        )
        con.execute(
            "INSERT INTO step_records VALUES (?,?,?)",
            ("MB-207", "STEP-DERM", "2026-08-01T00:00:00Z"),
        )
        con.executemany(
            "INSERT INTO authorization_register VALUES (?,?,?,?,?)",
            [
                (
                    key,
                    value["rx_id"],
                    f"evidence/documents/{key}.json",
                    digest(WORKSPACE / f"evidence/documents/{key}.json"),
                    1,
                )
                for key, value in documents.items()
            ],
        )
        before = {
            "local_disposition": None,
            "local_target_product_code": None,
            "local_next_action": None,
        }
        con.execute(
            "INSERT INTO review_runs VALUES (?,?,?,?)",
            (
                "FSR-INTERRUPTED-00",
                "sha256:interrupted",
                "sha256:partial",
                "interrupted",
            ),
        )
        con.execute(
            "INSERT INTO recovery_journal VALUES (?,?,?,?,?)",
            (
                "J-INT-204",
                "FSR-INTERRUPTED-00",
                "RX-204",
                json.dumps(before, sort_keys=True),
                0,
            ),
        )
        con.execute(
            "INSERT INTO rx_projections VALUES (?,?,?,?,?,?,?,?)",
            (
                "FSR-INTERRUPTED-00",
                "RX-204",
                "sha256:partial",
                "ready_local_formulary_review",
                "ready_local_formulary_review",
                "GN-DERM-1",
                "stage_local_formulary_review",
                "[]",
            ),
        )
        con.commit()

    manifest_files = {
        "policy/formulary_policy.json": digest(
            WORKSPACE / "policy/formulary_policy.json"
        ),
        "evidence/benefit_events.jsonl": digest(
            WORKSPACE / "evidence/benefit_events.jsonl"
        ),
    }
    for path in sorted((WORKSPACE / "evidence/documents").glob("*.json")):
        manifest_files[path.relative_to(WORKSPACE).as_posix()] = digest(path)
    write_json(
        WORKSPACE / "policy/source_manifest.json",
        {"schema_version": 1, "files": manifest_files},
    )


if __name__ == "__main__":
    build()
