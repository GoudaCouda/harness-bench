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


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> None:
    for name in ("policy", "evidence", "state", "staging"):
        shutil.rmtree(WORKSPACE / name, ignore_errors=True)
    for name in (
        "recovery_plan.json", ".escrow_preview.json", "escrow_handoff.md"
    ):
        (WORKSPACE / name).unlink(missing_ok=True)

    policy = {
        "schema_version": 1,
        "recovery_id": "EDR-20260819-01",
        "event_identity_rule": "first_delivery_per_event_id",
        "event_order_rule": "source_sequence_then_event_id",
        "hold_priority": [
            "hold_wire_missing",
            "hold_wire_amount_mismatch",
            "hold_missing_closing_authorization",
            "hold_payee_unverified",
            "hold_instruction_mismatch",
            "hold_funds_not_conserved",
            "hold_recording_pending",
        ],
        "stage_actions": {
            "ready_local_disbursement_packet": "stage_local_disbursement_packet",
            "holdback_release_ready": "stage_local_holdback_release_packet",
        },
        "local_only": True,
        "evidence_rules": {
            "closing_authorization": "signed document plus accepted closing_authorized event",
            "instruction": "signed document hash, payee, account suffix, and amount must match",
            "recording": "existing protected timestamp or accepted recording_confirmed event",
            "holdback_release": "signed matching document plus accepted holdback_release_authorized event",
        },
    }
    write_json(WORKSPACE / "policy/escrow_policy.json", policy)

    closings = [
        ("ESC-101", "PROP-ALDER-17", 10_000_000, "review_pending", None, None, 0, 100_000, 0, "reconcile", 1),
        ("ESC-102", "PROP-BAY-42", 8_000_000, "review_pending", None, None, 0, 0, 0, "reconcile", 1),
        ("ESC-103", "PROP-CEDAR-08", 6_500_000, "disbursed", "2026-08-17T16:05:00Z", "2026-08-17T16:40:00Z", 6_500_000, 0, 6_500_000, "none", 7),
        ("ESC-104", "PROP-DUNE-31", 7_200_000, "recorded_pending_disbursement", "2026-08-18T21:15:00Z", None, 0, 0, 0, "reconcile", 3),
        ("ESC-105", "PROP-ELM-55", 5_000_000, "disbursed_holdback", "2026-08-10T14:00:00Z", "2026-08-10T15:30:00Z", 4_920_000, 80_000, 5_000_000, "holdback_review", 6),
        ("ESC-106", "PROP-FIR-19", 9_000_000, "review_pending", None, None, 0, 0, 0, "reconcile", 1),
        ("ESC-107", "PROP-GROVE-73", 4_400_000, "review_pending", None, None, 0, 0, 0, "reconcile", 1),
    ]
    payees = [
        ("P-PAYOFF", "Northstar Servicing", "1122", "verified"),
        ("P-SELLER", "Synthetic Seller Trust", "3344", "verified"),
        ("P-TAX", "County Tax Office", "5566", "verified"),
        ("P-BROKER", "Example Realty", "7788", "verified"),
        ("P-ESCROW", "Offline Escrow Co", "9900", "verified"),
        ("P-HOLD", "Repair Holdback Ledger", "2468", "verified"),
    ]
    allocation_templates = {
        "ESC-101": [("PAYOFF", "P-PAYOFF", 6_000_000), ("SELLER", "P-SELLER", 3_000_000), ("TAX", "P-TAX", 500_000), ("BROKER", "P-BROKER", 300_000), ("ESCROW", "P-ESCROW", 100_000), ("HOLDBACK", "P-HOLD", 100_000)],
        "ESC-102": [("PAYOFF", "P-PAYOFF", 5_000_000), ("SELLER", "P-SELLER", 2_700_000), ("ESCROW", "P-ESCROW", 300_000)],
        "ESC-103": [("PAYOFF", "P-PAYOFF", 4_000_000), ("SELLER", "P-SELLER", 2_400_000), ("ESCROW", "P-ESCROW", 100_000)],
        "ESC-104": [("PAYOFF", "P-PAYOFF", 4_500_000), ("SELLER", "P-SELLER", 2_500_000), ("ESCROW", "P-ESCROW", 200_000)],
        "ESC-105": [("PAYOFF", "P-PAYOFF", 3_000_000), ("SELLER", "P-SELLER", 1_820_000), ("ESCROW", "P-ESCROW", 100_000), ("HOLDBACK", "P-HOLD", 80_000)],
        "ESC-106": [("PAYOFF", "P-PAYOFF", 5_500_000), ("SELLER", "P-SELLER", 3_300_000), ("ESCROW", "P-ESCROW", 150_000)],
        "ESC-107": [("PAYOFF", "P-PAYOFF", 2_500_000), ("SELLER", "P-SELLER", 1_700_000), ("ESCROW", "P-ESCROW", 200_000)],
    }
    instructions: list[tuple[object, ...]] = []
    documents: list[tuple[object, ...]] = []
    for closing_id, rows in allocation_templates.items():
        for suffix, payee_id, amount in rows:
            instruction_id = f"INS-{closing_id[4:]}-{suffix}"
            instructions.append((instruction_id, closing_id, payee_id, amount, "active"))
            account = next(row[2] for row in payees if row[0] == payee_id)
            document_account = "9999" if closing_id == "ESC-102" and suffix == "PAYOFF" else account
            body = {
                "schema_version": 1, "document_id": f"DOC-{instruction_id}",
                "closing_id": closing_id, "instruction_id": instruction_id,
                "payee_id": payee_id, "account_last4": document_account,
                "amount_cents": amount, "signed": True,
            }
            rel = f"evidence/documents/{body['document_id']}.json"
            write_json(WORKSPACE / rel, body)
            documents.append((body["document_id"], closing_id, "instruction_authorization", rel,
                              digest((WORKSPACE / rel).read_bytes()), instruction_id, payee_id,
                              document_account, amount, 1))

    for closing_id, *_ in closings:
        if closing_id == "ESC-107":
            continue
        body = {
            "schema_version": 1, "document_id": f"DOC-{closing_id}-CLOSE",
            "closing_id": closing_id, "document_type": "closing_authorization", "signed": True,
        }
        rel = f"evidence/documents/{body['document_id']}.json"
        write_json(WORKSPACE / rel, body)
        documents.append((body["document_id"], closing_id, "closing_authorization", rel,
                          digest((WORKSPACE / rel).read_bytes()), None, None, None, None, 1))
    release = {
        "schema_version": 1, "document_id": "DOC-ESC-105-HOLDBACK-RELEASE",
        "closing_id": "ESC-105", "document_type": "holdback_release_authorization",
        "payee_id": "P-HOLD", "account_last4": "2468", "amount_cents": 80_000,
        "signed": True,
    }
    release_rel = "evidence/documents/DOC-ESC-105-HOLDBACK-RELEASE.json"
    write_json(WORKSPACE / release_rel, release)
    documents.append((release["document_id"], "ESC-105", "holdback_release_authorization",
                      release_rel, digest((WORKSPACE / release_rel).read_bytes()),
                      "INS-105-HOLDBACK", "P-HOLD", "2468", 80_000, 1))

    def ev(delivery: str, event: str, closing: str, seq: int, kind: str, payload: dict[str, object]) -> dict[str, object]:
        return {"delivery_id": delivery, "event_id": event, "closing_id": closing,
                "source_sequence": seq, "event_type": kind, "payload": payload}

    events = [
        ev("DL-001", "EV-101-REC", "ESC-101", 30, "recording_confirmed", {"recorded_at": "2026-08-19T15:05:00Z"}),
        ev("DL-002", "EV-101-WIRE", "ESC-101", 10, "wire_received", {"amount_cents": 10_000_000, "bank_trace": "TR-101-A"}),
        ev("DL-003", "EV-101-AUTH", "ESC-101", 20, "closing_authorized", {"document_id": "DOC-ESC-101-CLOSE"}),
        ev("DL-004", "EV-101-WIRE", "ESC-101", 10, "wire_received", {"amount_cents": 10_000_000, "bank_trace": "TR-101-A"}),
        ev("DL-005", "EV-102-WIRE", "ESC-102", 10, "wire_received", {"amount_cents": 8_000_000, "bank_trace": "TR-102-A"}),
        ev("DL-006", "EV-102-AUTH", "ESC-102", 20, "closing_authorized", {"document_id": "DOC-ESC-102-CLOSE"}),
        ev("DL-007", "EV-102-REC", "ESC-102", 30, "recording_confirmed", {"recorded_at": "2026-08-19T15:12:00Z"}),
        ev("DL-008", "EV-103-LATE", "ESC-103", 90, "wire_received", {"amount_cents": 6_500_000, "bank_trace": "TR-LATE"}),
        ev("DL-009", "EV-104-AUTH", "ESC-104", 20, "closing_authorized", {"document_id": "DOC-ESC-104-CLOSE"}),
        ev("DL-010", "EV-104-WIRE", "ESC-104", 10, "wire_received", {"amount_cents": 7_200_000, "bank_trace": "TR-104-A"}),
        ev("DL-011", "EV-105-REL", "ESC-105", 80, "holdback_release_authorized", {"document_id": "DOC-ESC-105-HOLDBACK-RELEASE", "amount_cents": 80_000}),
        ev("DL-012", "EV-106-REC", "ESC-106", 30, "recording_confirmed", {"recorded_at": "2026-08-19T15:20:00Z"}),
        ev("DL-013", "EV-106-WIRE", "ESC-106", 10, "wire_received", {"amount_cents": 9_000_000, "bank_trace": "TR-106-A"}),
        ev("DL-014", "EV-106-AUTH", "ESC-106", 20, "closing_authorized", {"document_id": "DOC-ESC-106-CLOSE"}),
        ev("DL-015", "EV-107-WIRE", "ESC-107", 10, "wire_received", {"amount_cents": 4_400_000, "bank_trace": "TR-107-A"}),
        ev("DL-016", "EV-107-REC", "ESC-107", 30, "recording_confirmed", {"recorded_at": "2026-08-19T15:30:00Z"}),
        ev("DL-017", "EV-107-AUTH", "ESC-107", 20, "closing_authorized", {"document_id": "DOC-ESC-107-CLOSE"}),
        ev("DL-018", "EV-999-WIRE", "ESC-999", 10, "wire_received", {"amount_cents": 1_000_000, "bank_trace": "TR-UNKNOWN"}),
    ]
    events_path = WORKSPACE / "evidence/settlement_events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")

    db = WORKSPACE / "state/escrow.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE closings(closing_id TEXT PRIMARY KEY, property_id TEXT NOT NULL,
              expected_wire_cents INTEGER NOT NULL, state TEXT NOT NULL, recorded_at TEXT,
              disbursed_at TEXT, disbursed_cents INTEGER NOT NULL,
              retained_holdback_cents INTEGER NOT NULL, verified_allocations_cents INTEGER NOT NULL,
              next_action TEXT NOT NULL, version INTEGER NOT NULL);
            CREATE TABLE payees(payee_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
              account_last4 TEXT NOT NULL, verification_status TEXT NOT NULL);
            CREATE TABLE instructions(instruction_id TEXT PRIMARY KEY, closing_id TEXT NOT NULL,
              payee_id TEXT NOT NULL, amount_cents INTEGER NOT NULL, status TEXT NOT NULL);
            CREATE TABLE documents(document_id TEXT PRIMARY KEY, closing_id TEXT NOT NULL,
              document_type TEXT NOT NULL, local_path TEXT NOT NULL, sha256 TEXT NOT NULL,
              instruction_id TEXT, payee_id TEXT, account_last4 TEXT, amount_cents INTEGER,
              signed INTEGER NOT NULL);
            CREATE TABLE event_receipts(delivery_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
              closing_id TEXT NOT NULL, source_sequence INTEGER NOT NULL, disposition TEXT NOT NULL,
              recovery_id TEXT NOT NULL);
            CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY, status TEXT NOT NULL,
              source_checkpoint TEXT NOT NULL, semantic_plan_digest TEXT NOT NULL,
              final_revision INTEGER NOT NULL, external_actions_executed INTEGER NOT NULL);
            CREATE TABLE recovery_journal(journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
              recovery_id TEXT NOT NULL, closing_id TEXT NOT NULL, before_json TEXT NOT NULL,
              restored INTEGER NOT NULL);
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO closings VALUES(?,?,?,?,?,?,?,?,?,?,?)", closings)
        connection.executemany("INSERT INTO payees VALUES(?,?,?,?)", payees)
        connection.executemany("INSERT INTO instructions VALUES(?,?,?,?,?)", instructions)
        connection.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)", documents)
        baseline_101 = dict(zip(
            ("closing_id", "property_id", "expected_wire_cents", "state", "recorded_at",
             "disbursed_at", "disbursed_cents", "retained_holdback_cents",
             "verified_allocations_cents", "next_action", "version"), closings[0], strict=True
        ))
        connection.execute(
            "INSERT INTO recovery_runs VALUES(?,?,?,?,?,?)",
            ("EDR-INTERRUPTED-20260818", "interrupted", "prior-checkpoint", "prior-plan", 12, 0),
        )
        connection.execute(
            "INSERT INTO recovery_journal(recovery_id,closing_id,before_json,restored) VALUES(?,?,?,0)",
            ("EDR-INTERRUPTED-20260818", "ESC-101", json.dumps(baseline_101, sort_keys=True)),
        )
        connection.execute(
            "UPDATE closings SET state='ready_local_disbursement_packet', "
            "verified_allocations_cents=999999, next_action='stage_local_disbursement_packet', "
            "version=2 WHERE closing_id='ESC-101'"
        )
        connection.executemany(
            "INSERT INTO system_state VALUES(?,?)",
            [("source_revision", "12"), ("portfolio_revision", "12"), ("stage_state", "interrupted")],
        )
        connection.commit()
        connection.execute("VACUUM")

    protected_files = ["policy/escrow_policy.json", "evidence/settlement_events.jsonl"]
    protected_files += sorted(
        path.relative_to(WORKSPACE).as_posix()
        for path in (WORKSPACE / "evidence/documents").glob("*.json")
    )
    manifest = {path: digest((WORKSPACE / path).read_bytes()) for path in protected_files}
    write_json(WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": manifest})


if __name__ == "__main__":
    build()
