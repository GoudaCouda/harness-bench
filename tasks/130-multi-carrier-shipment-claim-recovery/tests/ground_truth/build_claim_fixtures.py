from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


CASES = [
    ("CL-A1", "RoadStar", "RS-9001", "2026-06-02", "draft", None, None, 0, 0, None, None, 1),
    ("CL-A2", "RoadStar", "RS-9001", "2026-06-08", "draft", None, None, 0, 0, None, None, 1),
    ("CL-B1", "ParcelNorth", "PN-7712", "2026-07-01", "draft", None, None, 0, 0, None, None, 1),
    ("CL-C1", "FreightWest", "FW-3210", "2026-07-03", "draft", None, None, 0, 0, None, None, 1),
    ("CL-D1", "ParcelNorth", "PN-8890", "2026-07-04", "draft", None, None, 0, 0, None, None, 1),
    ("CL-E1", "RoadStar", "RS-4410", "2026-06-22", "submitted", "2026-08-10T15:20:00Z", None, 0, 40000, None, None, 3),
    ("CL-F1", "FreightWest", "FW-8808", "2026-06-28", "awaiting_carrier", "2026-08-01T12:00:00Z", None, 0, 60000, None, None, 4),
    ("CL-G1", "ParcelNorth", "PN-0044", "2026-05-02", "closed_paid", "2026-05-12T10:00:00Z", "2026-06-01T18:00:00Z", 25000, 25000, None, None, 7),
]

LINES = [
    ("LN-A1-S", "CL-A1", "shortage", 20000, "SHIP-A", "two cartons short"),
    ("LN-A2-D", "CL-A2", "damage", 10000, "SHIP-A", "housing cracked"),
    ("LN-B1-D", "CL-B1", "damage", 50000, "SHIP-B", "instrument damage"),
    ("LN-C1-S", "CL-C1", "shortage", 80000, "SHIP-C", "one pallet short"),
    ("LN-D1-S", "CL-D1", "shortage", 70000, "SHIP-D", "shipment identity disputed"),
    ("LN-E1-D", "CL-E1", "damage", 40000, "SHIP-E", "submitted damage line"),
    ("LN-F1-S", "CL-F1", "shortage", 60000, "SHIP-F", "denied shortage line"),
    ("LN-G1-D", "CL-G1", "damage", 25000, "SHIP-G", "paid damage line"),
]

EVIDENCE = [
    ("BL-A1-I", "CL-A1", "LN-A1-S", "invoice", "SHIP-A", 0, None),
    ("BL-A1-B", "CL-A1", "LN-A1-S", "signed_bol", "SHIP-A", 1, None),
    ("BL-A2-I", "CL-A2", "LN-A2-D", "invoice", "SHIP-A", 0, "EV-A2-SUP"),
    ("BL-A2-P", "CL-A2", "LN-A2-D", "damage_photos", "SHIP-A", 0, "EV-A2-SUP"),
    ("BL-B1-I", "CL-B1", "LN-B1-D", "invoice", "SHIP-B", 0, None),
    ("BL-B1-P", "CL-B1", "LN-B1-D", "damage_photos", "SHIP-B", 0, "EV-B-SUP"),
    ("BL-C1-I", "CL-C1", "LN-C1-S", "invoice", "SHIP-C", 0, None),
    ("BL-C1-B", "CL-C1", "LN-C1-S", "signed_bol", "SHIP-C", 1, None),
    ("BL-D1-I", "CL-D1", "LN-D1-S", "invoice", "SHIP-WRONG", 0, None),
    ("BL-D1-B", "CL-D1", "LN-D1-S", "signed_bol", "SHIP-D", 1, None),
    ("BL-F1-N", "CL-F1", "LN-F1-S", "carrier_notice", "SHIP-F", 0, "EV-F-SUP"),
]

EVENTS = [
    {"delivery_id": "DL-001", "event_id": "EV-F-DEN", "case_id": "CL-F1", "carrier_sequence": 15, "event_type": "denial", "occurred_at": "2026-08-18T14:00:00Z", "delivered_at": "2026-08-19T08:02:00Z", "payload": {"response_deadline": "2026-08-24"}},
    {"delivery_id": "DL-002", "event_id": "EV-E-ACK", "case_id": "CL-E1", "carrier_sequence": 8, "event_type": "acknowledgment", "occurred_at": "2026-08-18T10:00:00Z", "delivered_at": "2026-08-19T08:03:00Z", "payload": {"carrier_reference": "RS-ACK-812"}},
    {"delivery_id": "DL-003", "event_id": "EV-A2-SUP", "case_id": "CL-A2", "carrier_sequence": 5, "event_type": "supplement", "occurred_at": "2026-08-17T09:00:00Z", "delivered_at": "2026-08-19T08:04:00Z", "payload": {"blob_ids": ["BL-A2-I", "BL-A2-P"]}},
    {"delivery_id": "DL-004", "event_id": "EV-F-SUP", "case_id": "CL-F1", "carrier_sequence": 14, "event_type": "supplement", "occurred_at": "2026-08-18T13:00:00Z", "delivered_at": "2026-08-19T08:05:00Z", "payload": {"blob_ids": ["BL-F1-N"]}},
    {"delivery_id": "DL-005", "event_id": "EV-B-SUP", "case_id": "CL-B1", "carrier_sequence": 2, "event_type": "supplement", "occurred_at": "2026-08-16T11:00:00Z", "delivered_at": "2026-08-19T08:06:00Z", "payload": {"blob_ids": ["BL-B1-P"]}},
    {"delivery_id": "DL-006", "event_id": "EV-UNKNOWN", "case_id": "CL-Z9", "carrier_sequence": 1, "event_type": "supplement", "occurred_at": "2026-08-16T12:00:00Z", "delivered_at": "2026-08-19T08:07:00Z", "payload": {"blob_ids": []}},
    {"delivery_id": "DL-007", "event_id": "EV-G-SUP", "case_id": "CL-G1", "carrier_sequence": 11, "event_type": "supplement", "occurred_at": "2026-08-18T16:00:00Z", "delivered_at": "2026-08-19T08:08:00Z", "payload": {"blob_ids": []}},
    {"delivery_id": "DL-008", "event_id": "EV-B-SUP", "case_id": "CL-B1", "carrier_sequence": 2, "event_type": "supplement", "occurred_at": "2026-08-16T11:00:00Z", "delivered_at": "2026-08-19T08:09:00Z", "payload": {"blob_ids": ["BL-B1-P"]}},
    {"delivery_id": "DL-009", "event_id": "EV-E-ACK", "case_id": "CL-E1", "carrier_sequence": 8, "event_type": "acknowledgment", "occurred_at": "2026-08-18T10:00:00Z", "delivered_at": "2026-08-19T08:10:00Z", "payload": {"carrier_reference": "RS-ACK-812"}},
]


def make_workspace() -> None:
    cache = WORKSPACE / "__pycache__"
    if cache.exists():
        shutil.rmtree(cache)
    for name in ("policy", "evidence", "state", "staging"):
        path = WORKSPACE / name
        if path.exists():
            shutil.rmtree(path)
    for name in ("recovery_plan.json", ".claims_preview.json", "claims_handoff.md"):
        path = WORKSPACE / name
        if path.exists():
            path.unlink()
    (WORKSPACE / "policy").mkdir(parents=True)
    (WORKSPACE / "evidence/blobs").mkdir(parents=True)
    (WORKSPACE / "state").mkdir(parents=True)
    policy = {
        "schema_version": 1,
        "recovery_id": "CRR-20260819-01",
        "as_of": "2026-08-19",
        "duplicate_survivor_rule": "oldest_opened_at_then_case_id",
        "event_order_rule": "first_delivery_per_event_id_then_carrier_sequence",
        "damage_missing_packaging_percent": 60,
        "settlement_rules": {
            "damage": ["matching_invoice", "damage_photos", "packaging_or_partial_rate"],
            "shortage": ["matching_invoice", "signed_bol"],
            "invoice_identity": "line_shipment_id_must_match",
        },
        "packet_order": "denial_response_deadline_then_ready_case_id",
        "external_boundary": "local_stage_only",
    }
    policy_path = WORKSPACE / "policy/claims_policy.json"
    write_json(policy_path, policy)
    event_path = WORKSPACE / "evidence/carrier_events.jsonl"
    event_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in EVENTS), encoding="utf-8")
    evidence_rows = []
    for blob_id, case_id, line_id, kind, shipment_id, signed, event_id in EVIDENCE:
        relative = f"evidence/blobs/{blob_id}.json"
        content = canonical(
            {
                "blob_id": blob_id,
                "case_id": case_id,
                "line_id": line_id,
                "evidence_type": kind,
                "shipment_id": shipment_id,
                "signed": bool(signed),
                "synthetic": True,
            }
        )
        (WORKSPACE / relative).write_bytes(content)
        evidence_rows.append(
            (blob_id, case_id, line_id, kind, relative, digest(content), shipment_id, signed, event_id)
        )
    manifest_files = {
        "policy/claims_policy.json": digest(policy_path.read_bytes()),
        "evidence/carrier_events.jsonl": digest(event_path.read_bytes()),
    }
    manifest_files.update(
        {
            f"evidence/blobs/{row[0]}.json": digest((WORKSPACE / f"evidence/blobs/{row[0]}.json").read_bytes())
            for row in EVIDENCE
        }
    )
    write_json(
        WORKSPACE / "policy/source_manifest.json",
        {"schema_version": 1, "files": manifest_files},
    )
    db = WORKSPACE / "state/claims.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE cases(
              case_id TEXT PRIMARY KEY, carrier TEXT NOT NULL, tracking_number TEXT NOT NULL,
              opened_at TEXT NOT NULL, state TEXT NOT NULL, submitted_at TEXT, closed_at TEXT,
              paid_amount_cents INTEGER NOT NULL, approved_amount_cents INTEGER NOT NULL,
              survivor_case_id TEXT, response_deadline TEXT, version INTEGER NOT NULL
            );
            CREATE TABLE claim_lines(
              line_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
              loss_type TEXT NOT NULL, requested_amount_cents INTEGER NOT NULL,
              shipment_id TEXT NOT NULL, description TEXT NOT NULL
            );
            CREATE TABLE evidence_blobs(
              blob_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
              line_id TEXT NOT NULL REFERENCES claim_lines(line_id), evidence_type TEXT NOT NULL,
              local_path TEXT NOT NULL, sha256 TEXT NOT NULL, shipment_id TEXT NOT NULL,
              signed INTEGER NOT NULL, received_via_event_id TEXT
            );
            CREATE TABLE event_receipts(
              delivery_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, source_case_id TEXT NOT NULL,
              effective_case_id TEXT NOT NULL, carrier_sequence INTEGER NOT NULL,
              disposition TEXT NOT NULL, recovery_id TEXT NOT NULL
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY, status TEXT NOT NULL, source_checkpoint TEXT,
              semantic_plan_digest TEXT, final_revision INTEGER,
              external_actions_executed INTEGER NOT NULL
            );
            CREATE TABLE recovery_journal(
              journal_id INTEGER PRIMARY KEY AUTOINCREMENT, recovery_id TEXT NOT NULL,
              case_id TEXT NOT NULL, before_json TEXT NOT NULL, restored INTEGER NOT NULL
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", CASES)
        connection.executemany("INSERT INTO claim_lines VALUES(?,?,?,?,?,?)", LINES)
        connection.executemany("INSERT INTO evidence_blobs VALUES(?,?,?,?,?,?,?,?,?)", evidence_rows)
        connection.executemany(
            "INSERT INTO system_state VALUES(?,?)",
            (("source_revision", "41"), ("portfolio_revision", "41"), ("stage_state", "interrupted")),
        )
        columns = [item[1] for item in connection.execute("PRAGMA table_info(cases)")]
        before = dict(zip(columns, connection.execute("SELECT * FROM cases WHERE case_id='CL-B1'").fetchone(), strict=True))
        connection.execute(
            "INSERT INTO recovery_runs VALUES('CRR-INTERRUPTED-20260818','interrupted',NULL,NULL,NULL,0)"
        )
        connection.execute(
            "INSERT INTO recovery_journal(recovery_id,case_id,before_json,restored) VALUES(?,?,?,0)",
            ("CRR-INTERRUPTED-20260818", "CL-B1", json.dumps(before, sort_keys=True)),
        )
        connection.execute(
            "UPDATE cases SET state='ready_local_packet',approved_amount_cents=50000,version=2 WHERE case_id='CL-B1'"
        )
        connection.commit()


def load_controller():
    spec = importlib.util.spec_from_file_location("claims_fixture_controller", WORKSPACE / "claimsctl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_reference() -> None:
    make_workspace()
    spec = importlib.util.spec_from_file_location(
        "claims_fixture_truth", TASK / "tests/test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hidden evaluator truth")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = module._truth()["plan"]
    write_json(WORKSPACE / "recovery_plan.json", plan)
    handoff = """# Shipment claim recovery handoff

CRR-20260819-01 was recovered locally. CL-A2 shares RoadStar tracking RS-9001
with older CL-A1, so CL-A1 is the duplicate survivor; EV-A2-SUP was routed to
that survivor. Events were de-duplicated by event ID and then interpreted by
carrier sequence: the repeated EV-B-SUP and EV-E-ACK deliveries were ignored,
the unknown-case delivery was ignored, and EV-G-SUP could not reopen CL-G1.
Although the denial arrived first in the delivery file, EV-F-SUP sequence 14
precedes EV-F-DEN sequence 15.

Evidence hashes and shipment identity were checked per line. CL-A1's shortage
has a signed BOL and matching invoice; its merged damage line has photos and a
matching invoice but no packaging, so only the 60 percent policy amount applies.
CL-B1 likewise receives the 60 percent damage amount. CL-C1 has a matching
invoice and signed BOL for the full shortage amount. CL-D1 remains held because
BL-D1-I names SHIP-WRONG rather than SHIP-D; its signed BOL cannot cure invoice
identity. Amounts and claim lines reconcile exactly once through the survivor.

CL-F1 is first in packet order because its denial response deadline is
2026-08-24. CL-E1's carrier acknowledgment preserves its existing submission
timestamp and does not resubmit. CL-G1 remains closed and paid with its closed
timestamp and paid amount unchanged.

The interrupted CL-B1 journal entry was restored before the atomic recovery
commit. Verification binds the source checkpoint and normalized semantic plan
to the claim projection and event receipts. The local claim packet bundle and
packet manifest hashes close to the recovery receipt; semantic replay was a
byte-stable no-op.

The packet remains local and not submitted. No claim or denial response was
submitted, no carrier was contacted, and no payment or refund was executed.
"""
    (WORKSPACE / "claims_handoff.md").write_text(handoff, encoding="utf-8")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        subprocess.run(
            ["python3", "claimsctl.py", command, "recovery_plan.json"],
            cwd=WORKSPACE,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    for name in ("recovery_plan.json", ".claims_preview.json", "claims_handoff.md"):
        shutil.copy2(WORKSPACE / name, REFERENCE / name)
    shutil.copytree(WORKSPACE / "state", REFERENCE / "state")
    shutil.copytree(WORKSPACE / "staging", REFERENCE / "staging")
    make_workspace()


if __name__ == "__main__":
    build_reference()
