#!/usr/bin/env python3
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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


policy = {
    "schema_version": 1,
    "recovery_id": "ECNREC-20260819-442",
    "ecn_id": "ECN-442",
    "approval_state_required": "approved",
    "source_revision": 37,
    "component_change": {
        "from_part": "CONN-CU-4P",
        "to_part": "CONN-NI-4P",
        "quantity": 2,
    },
    "revision_map": {
        "ACTUATOR-MODULE": {"from": "C", "to": "D"},
        "PUMP-100": {"from": "12", "to": "13"},
        "SKID-900": {"from": "5", "to": "6"},
        "FIELD-KIT": {"from": "2", "to": "3"},
    },
    "effectivity": {
        "SKID-900": {"basis": "serial", "from": "SN-0500"},
        "FIELD-KIT": {"basis": "lot", "from": "LOT-2026-09"},
    },
    "approved_substitutes": {"CONN-NI-4P": ["CONN-NI-4P-A"]},
    "status_vocabulary": [
        "preserve_as_built",
        "hold_and_rekit",
        "adopt_new_baseline",
        "preserve_pre_effectivity_kit",
        "accept_approved_substitute_new_baseline",
    ],
    "external_boundary": {
        "release_executed": False,
        "shop_floor_change_executed": False,
        "supplier_order_placed": False,
    },
}

change = {
    "schema_version": 1,
    "ecn_id": "ECN-442",
    "approval_state": "approved",
    "approved_at": "2026-08-18T16:00:00Z",
    "approved_by": ["ENG-CFG-12", "QUALITY-07"],
    "reason": "replace copper-contact connector with nickel-contact connector",
    "from_part": "CONN-CU-4P",
    "to_part": "CONN-NI-4P",
    "direct_assembly": "ACTUATOR-MODULE",
    "serial_effectivity": "SN-0500",
    "lot_effectivity": "LOT-2026-09",
    "approval_token": "ECN-442/APPROVED/20260818",
}

work_orders = [
    {
        "work_order_id": "WO-900",
        "end_item": "SKID-900",
        "serial_or_lot": "SN-0498",
        "status": "assembled",
        "baseline_revision": "5",
        "kit_state": "consumed",
        "issued_component": "CONN-CU-4P",
        "version": 4,
    },
    {
        "work_order_id": "WO-901",
        "end_item": "SKID-900",
        "serial_or_lot": "SN-0501",
        "status": "kitted",
        "baseline_revision": "5",
        "kit_state": "issued",
        "issued_component": "CONN-CU-4P",
        "version": 2,
    },
    {
        "work_order_id": "WO-902",
        "end_item": "SKID-900",
        "serial_or_lot": "SN-0502",
        "status": "released",
        "baseline_revision": "5",
        "kit_state": "not_issued",
        "issued_component": None,
        "version": 1,
    },
    {
        "work_order_id": "WO-903",
        "end_item": "FIELD-KIT",
        "serial_or_lot": "LOT-2026-08",
        "status": "kitted",
        "baseline_revision": "2",
        "kit_state": "issued",
        "issued_component": "CONN-CU-4P-A",
        "version": 3,
    },
    {
        "work_order_id": "WO-904",
        "end_item": "FIELD-KIT",
        "serial_or_lot": "LOT-2026-09",
        "status": "kitted",
        "baseline_revision": "2",
        "kit_state": "issued",
        "issued_component": "CONN-NI-4P-A",
        "version": 3,
    },
    {
        "work_order_id": "WO-905",
        "end_item": "FIELD-KIT",
        "serial_or_lot": "LOT-2026-10",
        "status": "released",
        "baseline_revision": "2",
        "kit_state": "not_issued",
        "issued_component": None,
        "version": 1,
    },
]

WORKSPACE.mkdir(parents=True, exist_ok=True)
write_json(WORKSPACE / "policy/ecn_policy.json", policy)
write_json(WORKSPACE / "evidence/engineering_change.json", change)
(WORKSPACE / "evidence/work_orders.jsonl").parent.mkdir(parents=True, exist_ok=True)
(WORKSPACE / "evidence/work_orders.jsonl").write_text(
    "".join(json.dumps(row, sort_keys=True) + "\n" for row in work_orders),
    encoding="utf-8",
)

db = WORKSPACE / "state/configuration.db"
db.parent.mkdir(parents=True, exist_ok=True)
db.unlink(missing_ok=True)
with sqlite3.connect(db) as connection:
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        CREATE TABLE baselines (
          item_id TEXT NOT NULL, revision TEXT NOT NULL, status TEXT NOT NULL,
          ecn_id TEXT, PRIMARY KEY(item_id, revision)
        );
        CREATE TABLE bom_items (
          item_id TEXT NOT NULL, revision TEXT NOT NULL, line_no INTEGER NOT NULL,
          component_id TEXT NOT NULL, component_revision TEXT NOT NULL,
          quantity INTEGER NOT NULL, substitute_for TEXT,
          PRIMARY KEY(item_id, revision, line_no)
        );
        CREATE TABLE work_orders (
          work_order_id TEXT PRIMARY KEY, end_item TEXT NOT NULL,
          serial_or_lot TEXT NOT NULL, status TEXT NOT NULL,
          baseline_revision TEXT NOT NULL, kit_state TEXT NOT NULL,
          issued_component TEXT, ecn_disposition TEXT, version INTEGER NOT NULL
        );
        CREATE TABLE ecn_runs (
          recovery_id TEXT PRIMARY KEY, ecn_id TEXT NOT NULL,
          source_checkpoint TEXT NOT NULL, semantic_plan_sha256 TEXT NOT NULL,
          state TEXT NOT NULL, logical_db_sha256 TEXT NOT NULL
        );
        CREATE TABLE ecn_journal (
          journal_id INTEGER PRIMARY KEY AUTOINCREMENT, recovery_id TEXT NOT NULL,
          entity_type TEXT NOT NULL, entity_key TEXT NOT NULL,
          before_json TEXT NOT NULL, after_json TEXT NOT NULL, restored INTEGER NOT NULL
        );
        CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    connection.executemany(
        "INSERT INTO baselines VALUES (?, ?, ?, ?)",
        [
            ("ACTUATOR-MODULE", "C", "released", None),
            ("PUMP-100", "12", "released", None),
            ("SKID-900", "5", "released", None),
            ("FIELD-KIT", "2", "released", None),
        ],
    )
    connection.executemany(
        "INSERT INTO bom_items VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("ACTUATOR-MODULE", "C", 10, "FRAME-ACT", "1", 1, None),
            ("ACTUATOR-MODULE", "C", 20, "CONN-CU-4P", "1", 2, None),
            ("ACTUATOR-MODULE", "C", 21, "CONN-CU-4P-A", "1", 2, "CONN-CU-4P"),
            ("PUMP-100", "12", 10, "CASING-P100", "2", 1, None),
            ("PUMP-100", "12", 20, "ACTUATOR-MODULE", "C", 1, None),
            ("SKID-900", "5", 10, "FRAME-S900", "4", 1, None),
            ("SKID-900", "5", 20, "PUMP-100", "12", 2, None),
            ("FIELD-KIT", "2", 10, "CASE-FK", "1", 1, None),
            ("FIELD-KIT", "2", 20, "ACTUATOR-MODULE", "C", 1, None),
        ],
    )
    connection.executemany(
        "INSERT INTO work_orders VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
        [tuple(row[key] for key in (
            "work_order_id", "end_item", "serial_or_lot", "status",
            "baseline_revision", "kit_state", "issued_component", "version",
        )) for row in work_orders],
    )
    connection.executemany(
        "INSERT INTO system_state VALUES (?, ?)",
        [("source_revision", "37"), ("active_ecn", "ECN-442")],
    )
    # Simulate an older crash after changing one work order and inserting one
    # target-revision baseline. Both mutations are recoverable from the journal.
    before_wo = connection.execute(
        "SELECT * FROM work_orders WHERE work_order_id='WO-901'"
    ).fetchone()
    wo_names = [row[1] for row in connection.execute("PRAGMA table_info(work_orders)")]
    before_wo_json = json.dumps(dict(zip(wo_names, before_wo, strict=True)), sort_keys=True)
    connection.execute(
        "UPDATE work_orders SET baseline_revision='6', ecn_disposition='adopt_new_baseline', version=3 WHERE work_order_id='WO-901'"
    )
    after_wo = connection.execute(
        "SELECT * FROM work_orders WHERE work_order_id='WO-901'"
    ).fetchone()
    after_wo_json = json.dumps(dict(zip(wo_names, after_wo, strict=True)), sort_keys=True)
    connection.execute(
        "INSERT INTO baselines VALUES ('ACTUATOR-MODULE', 'D', 'pending_review', 'ECN-442')"
    )
    partial_baseline = {
        "item_id": "ACTUATOR-MODULE", "revision": "D",
        "status": "pending_review", "ecn_id": "ECN-442",
    }
    connection.execute(
        "INSERT INTO ecn_runs VALUES (?, ?, ?, ?, ?, ?)",
        ("ECNREC-20260818-442-PARTIAL", "ECN-442", "stale", "stale", "interrupted", "stale"),
    )
    connection.executemany(
        "INSERT INTO ecn_journal(recovery_id, entity_type, entity_key, before_json, after_json, restored) VALUES (?, ?, ?, ?, ?, 0)",
        [
            ("ECNREC-20260818-442-PARTIAL", "work_order", "WO-901", before_wo_json, after_wo_json),
            ("ECNREC-20260818-442-PARTIAL", "baseline_insert", "ACTUATOR-MODULE@D", "null", json.dumps(partial_baseline, sort_keys=True)),
        ],
    )
    connection.commit()

manifest_files = {}
for locator in (
    "policy/ecn_policy.json",
    "evidence/engineering_change.json",
    "evidence/work_orders.jsonl",
):
    manifest_files[locator] = digest((WORKSPACE / locator).read_bytes())
write_json(
    WORKSPACE / "policy/source_manifest.json",
    {"schema_version": 1, "files": manifest_files},
)
for path in WORKSPACE.rglob("*"):
    if path.is_file():
        path.chmod(0o755 if path.name == "bomctl.py" else 0o644)
