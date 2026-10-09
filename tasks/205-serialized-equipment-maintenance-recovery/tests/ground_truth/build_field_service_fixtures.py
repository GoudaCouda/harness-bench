#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
sys.dont_write_bytecode = True


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_sources() -> None:
    policy = {
        "schema_version": 1,
        "recovery_id": "FSR-20260819-04",
        "as_of": "2026-08-19T16:00:00Z",
        "duplicate_survivor_rule": "oldest_opened_then_work_order_id",
        "event_identity_rule": "event_id_then_sequence",
        "completed_execution_boundary": "immutable",
        "selection_tie_breaker": "lexicographic_id",
        "symptom_rules": {
            "bearing_temperature_high": {
                "component": "drive_bearing",
                "skill_code": "MECH-ROTATING",
                "measurement_kind": "vibration",
            },
            "bearing_vibration_high": {
                "component": "drive_bearing",
                "skill_code": "MECH-ROTATING",
                "measurement_kind": "vibration",
            },
            "belt_slip": {
                "component": "infeed_belt",
                "skill_code": "MECH-CONVEYOR",
                "measurement_kind": "tachometer",
            },
            "insulation_resistance_low": {
                "component": "control_fuse",
                "skill_code": "ELEC-LV",
                "measurement_kind": "insulation_resistance",
            },
        },
        "dispositions": [
            "ready_local_dispatch", "hold_policy_conflict", "hold_bom_effectivity",
            "hold_technician_qualification", "hold_calibration",
            "hold_part_availability", "merged_into_survivor",
            "completed_execution_preserved",
        ],
        "external_action": "none",
        "stage_boundary": "local_offline_packet_only",
    }
    write_json(WORKSPACE / "policy/maintenance_policy.json", policy)

    deliveries = [
        {
            "delivery_id": "DLV-07", "event_id": "EVT-UNKNOWN-1",
            "work_order_id": "WO-999", "sequence": 1,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T12:01:00Z",
            "payload": {"symptom_code": "bearing_vibration_high", "telemetry_ref": "TLM-999"},
        },
        {
            "delivery_id": "DLV-03", "event_id": "EVT-200-TEMP",
            "work_order_id": "WO-200", "sequence": 20,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T10:07:00Z",
            "payload": {"symptom_code": "bearing_temperature_high", "telemetry_ref": "TLM-200-B"},
        },
        {
            "delivery_id": "DLV-01", "event_id": "EVT-200-VIB",
            "work_order_id": "WO-200", "sequence": 10,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T10:05:00Z",
            "payload": {"symptom_code": "bearing_vibration_high", "telemetry_ref": "TLM-200-A"},
        },
        {
            "delivery_id": "DLV-08", "event_id": "EVT-200-VIB",
            "work_order_id": "WO-200", "sequence": 10,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T10:05:00Z",
            "payload": {"symptom_code": "bearing_vibration_high", "telemetry_ref": "TLM-200-A"},
        },
        {
            "delivery_id": "DLV-05", "event_id": "EVT-201-VIB",
            "work_order_id": "WO-201", "sequence": 30,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T10:09:00Z",
            "payload": {"symptom_code": "bearing_vibration_high", "telemetry_ref": "TLM-201-A"},
        },
        {
            "delivery_id": "DLV-02", "event_id": "EVT-202-MEG",
            "work_order_id": "WO-202", "sequence": 10,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T10:13:00Z",
            "payload": {"symptom_code": "insulation_resistance_low", "telemetry_ref": "TLM-202-A"},
        },
        {
            "delivery_id": "DLV-04", "event_id": "EVT-203-BELT",
            "work_order_id": "WO-203", "sequence": 10,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T10:15:00Z",
            "payload": {"symptom_code": "belt_slip", "telemetry_ref": "TLM-203-A"},
        },
        {
            "delivery_id": "DLV-06", "event_id": "EVT-190-LATE",
            "work_order_id": "WO-190", "sequence": 90,
            "event_type": "condition_observation",
            "occurred_at": "2026-08-19T11:00:00Z",
            "payload": {"symptom_code": "bearing_temperature_high", "telemetry_ref": "TLM-190-LATE"},
        },
    ]
    event_path = WORKSPACE / "evidence/work_order_events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in deliveries), encoding="utf-8")
    telemetry = [
        {"reading_id": "TLM-200-A", "asset_serial": "PKG-PX8-00041", "kind": "vibration", "value": 12.7, "unit": "mm/s", "observed_at": "2026-08-19T10:05:00Z"},
        {"reading_id": "TLM-200-B", "asset_serial": "PKG-PX8-00041", "kind": "bearing_temperature", "value": 91.4, "unit": "C", "observed_at": "2026-08-19T10:07:00Z"},
        {"reading_id": "TLM-201-A", "asset_serial": "PKG-PX8-00041", "kind": "vibration", "value": 12.8, "unit": "mm/s", "observed_at": "2026-08-19T10:09:00Z"},
        {"reading_id": "TLM-202-A", "asset_serial": "PKG-PX9-00007", "kind": "insulation_resistance", "value": 0.4, "unit": "Mohm", "observed_at": "2026-08-19T10:13:00Z"},
        {"reading_id": "TLM-203-A", "asset_serial": "PKG-PX8-00055", "kind": "belt_speed_delta", "value": 18.0, "unit": "percent", "observed_at": "2026-08-19T10:15:00Z"},
    ]
    telemetry_path = WORKSPACE / "evidence/telemetry_readings.jsonl"
    telemetry_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in telemetry), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "files": {
            "policy/maintenance_policy.json": digest((WORKSPACE / "policy/maintenance_policy.json").read_bytes()),
            "evidence/work_order_events.jsonl": digest(event_path.read_bytes()),
            "evidence/telemetry_readings.jsonl": digest(telemetry_path.read_bytes()),
        },
        "synthetic_fixture": True,
    }
    write_json(WORKSPACE / "policy/source_manifest.json", manifest)


def build_database() -> None:
    path = WORKSPACE / "state/maintenance.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE assets(asset_serial TEXT PRIMARY KEY, model TEXT NOT NULL, commissioned_at TEXT NOT NULL);
            CREATE TABLE work_orders(
              work_order_id TEXT PRIMARY KEY, asset_serial TEXT NOT NULL, alarm_group TEXT NOT NULL,
              opened_at TEXT NOT NULL, status TEXT NOT NULL, survivor_work_order_id TEXT,
              selected_bom_revision TEXT, required_part_number TEXT, allocated_part_lot TEXT,
              technician_id TEXT, qualification_code TEXT, instrument_id TEXT,
              executed_action TEXT, executed_at TEXT, version INTEGER NOT NULL
            );
            CREATE TABLE bom_effectivity(
              model TEXT NOT NULL, component TEXT NOT NULL, bom_revision TEXT NOT NULL,
              part_number TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT,
              PRIMARY KEY(model, component, effective_from)
            );
            CREATE TABLE technician_qualifications(
              technician_id TEXT NOT NULL, model TEXT NOT NULL, skill_code TEXT NOT NULL,
              valid_from TEXT NOT NULL, valid_until TEXT NOT NULL,
              PRIMARY KEY(technician_id, model, skill_code)
            );
            CREATE TABLE instruments(
              instrument_id TEXT PRIMARY KEY, measurement_kind TEXT NOT NULL,
              calibration_valid_until TEXT NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE part_lots(
              lot_id TEXT PRIMARY KEY, part_number TEXT NOT NULL, status TEXT NOT NULL, quantity INTEGER NOT NULL
            );
            CREATE TABLE event_receipts(
              delivery_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, source_work_order_id TEXT NOT NULL,
              effective_work_order_id TEXT, sequence INTEGER NOT NULL, disposition TEXT NOT NULL
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL,
              semantic_plan_digest TEXT NOT NULL, committed_revision INTEGER NOT NULL,
              external_actions_executed INTEGER NOT NULL
            );
            CREATE TABLE recovery_journal(
              journal_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL,
              before_image_json TEXT NOT NULL, restored INTEGER NOT NULL
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO assets VALUES (?,?,?)", [
            ("PKG-PX8-00012", "PX-8", "2024-02-01T00:00:00Z"),
            ("PKG-PX8-00041", "PX-8", "2025-01-10T00:00:00Z"),
            ("PKG-PX8-00055", "PX-8", "2025-06-12T00:00:00Z"),
            ("PKG-PX9-00007", "PX-9", "2025-11-03T00:00:00Z"),
        ])
        work_orders = [
            ("WO-190", "PKG-PX8-00012", "ALM-11", "2026-07-10T08:00:00Z", "completed", "WO-190", "PX8-R1", "BRG-42A", "LOT-B42A-HIST", "TECH-A", "MECH-ROTATING", "VIB-A", "replace_drive_bearing", "2026-07-10T15:30:00Z", 7),
            ("WO-200", "PKG-PX8-00041", "ALM-77", "2026-08-19T10:00:00Z", "open", None, None, None, None, None, None, None, None, None, 1),
            ("WO-201", "PKG-PX8-00041", "ALM-77", "2026-08-19T10:04:00Z", "open", None, None, None, None, None, None, None, None, None, 1),
            ("WO-202", "PKG-PX9-00007", "ALM-81", "2026-08-19T10:12:00Z", "open", None, None, None, None, None, None, None, None, None, 1),
            ("WO-203", "PKG-PX8-00055", "ALM-84", "2026-08-19T10:14:00Z", "open", None, None, None, None, None, None, None, None, None, 1),
        ]
        connection.executemany("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", work_orders)
        connection.executemany("INSERT INTO bom_effectivity VALUES (?,?,?,?,?,?)", [
            ("PX-8", "drive_bearing", "PX8-R1", "BRG-42A", "2024-01-01T00:00:00Z", "2026-08-01T00:00:00Z"),
            ("PX-8", "drive_bearing", "PX8-R2", "BRG-42B", "2026-08-01T00:00:00Z", None),
            ("PX-8", "infeed_belt", "PX8-R3", "BELT-9C", "2026-06-01T00:00:00Z", None),
            ("PX-9", "control_fuse", "PX9-E4", "FUSE-9E", "2026-01-01T00:00:00Z", None),
        ])
        connection.executemany("INSERT INTO technician_qualifications VALUES (?,?,?,?,?)", [
            ("TECH-A", "PX-8", "MECH-ROTATING", "2025-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),
            ("TECH-Z", "PX-8", "MECH-ROTATING", "2025-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),
            ("TECH-C", "PX-8", "MECH-CONVEYOR", "2025-01-01T00:00:00Z", "2026-09-30T23:59:59Z"),
            ("TECH-E", "PX-9", "ELEC-LV", "2025-01-01T00:00:00Z", "2026-10-31T23:59:59Z"),
            ("TECH-X", "PX-9", "ELEC-LV", "2024-01-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        ])
        connection.executemany("INSERT INTO instruments VALUES (?,?,?,?)", [
            ("VIB-A", "vibration", "2026-09-30T23:59:59Z", "active"),
            ("VIB-Z", "vibration", "2026-10-31T23:59:59Z", "active"),
            ("TACH-A", "tachometer", "2026-09-15T23:59:59Z", "active"),
            ("MEG-A", "insulation_resistance", "2026-08-18T23:59:59Z", "active"),
            ("MEG-B", "insulation_resistance", "2026-10-31T23:59:59Z", "inactive"),
        ])
        connection.executemany("INSERT INTO part_lots VALUES (?,?,?,?)", [
            ("LOT-B42-REL", "BRG-42B", "released", 1),
            ("LOT-B42-QUAR", "BRG-42B", "quarantined", 5),
            ("LOT-B42A-OLD", "BRG-42A", "released", 9),
            ("LOT-B42A-HIST", "BRG-42A", "consumed", 0),
            ("LOT-BELT-ZERO", "BELT-9C", "released", 0),
            ("LOT-BELT-QUAR", "BELT-9C", "quarantined", 3),
            ("LOT-FUSE-REL", "FUSE-9E", "released", 4),
        ])
        connection.executemany("INSERT INTO system_state VALUES (?,?)", [("source_revision", "18"), ("revision", "41")])
        mutable_order_fields = (
            "status", "survivor_work_order_id", "selected_bom_revision",
            "required_part_number", "allocated_part_lot", "technician_id",
            "qualification_code", "instrument_id", "version",
        )
        connection.row_factory = sqlite3.Row
        before = {
            "work_orders": {
                row["work_order_id"]: {field: row[field] for field in mutable_order_fields}
                for row in connection.execute("SELECT * FROM work_orders ORDER BY work_order_id")
            },
            "part_lots": {
                row["lot_id"]: {"quantity": row["quantity"]}
                for row in connection.execute("SELECT * FROM part_lots ORDER BY lot_id")
            },
        }
        connection.execute("INSERT INTO recovery_journal VALUES (?,?,?,0)", ("JRN-INT-20260819-04", "FSR-INTERRUPTED-20260819-03", json.dumps(before, sort_keys=True)))
        connection.execute("UPDATE work_orders SET status='ready_local_dispatch', selected_bom_revision='PX8-R1', required_part_number='BRG-42A', allocated_part_lot='LOT-B42-QUAR', technician_id='TECH-X', instrument_id='MEG-A', version=2 WHERE work_order_id='WO-200'")
        connection.execute("UPDATE part_lots SET quantity=0 WHERE lot_id='LOT-B42-REL'")
        connection.commit()


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hb134-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        spec = importlib.util.spec_from_file_location("reference_outcome", TASK / "tests/test_outcome.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load controller")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plan = module._expected()["plan"]
        write_json(workspace / "maintenance_recovery_plan.json", plan)
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run([sys.executable, "maintenancectl.py", command, "maintenance_recovery_plan.json"], cwd=workspace, check=True)
        (workspace / "maintenance_handoff.md").write_text(
            "# Recovered field-service batch\n\n"
            "The event ledger was de-duplicated by event ID before sequence order was applied. DLV-08 is the byte-identical replay of EVT-200-VIB, and WO-201 shares PKG-PX8-00041 and ALM-77 with older WO-200, so its accepted observation routes to survivor WO-200. The unknown WO-999 delivery is ignored, while the late WO-190 observation is rejected at the completed execution boundary.\n\n"
            "WO-200 uses incident-time BOM PX8-R2 and effective part BRG-42B, not superseded BRG-42A. TECH-A is the lexicographically first current MECH-ROTATING qualification, VIB-A is active and calibrated, and released LOT-B42-REL has one unit, so one offline dispatch packet is ready. WO-202 has qualified TECH-E and effective FUSE-9E, but every insulation-resistance instrument is expired or inactive, so it remains on calibration hold. WO-203 has qualified TECH-C and calibrated TACH-A, but BELT-9C has only an exhausted released lot and a quarantined lot, so it remains on part-availability hold. No quarantined, exhausted, superseded, or wrong part was allocated.\n\n"
            "The interrupted journal restored WO-200 and LOT-B42-REL to their before-images before one atomic projection. Exactly one released unit was allocated and the part balance moved from one to zero once. WO-190's completed replace-drive-bearing action, timestamp, serialized identity, and historical lot remain unchanged; it was not reopened. The verification digest closes the logical SQLite state, and the dispatch bundle SHA-256 closes through the manifest and local staging receipt. Equivalent ordering and JSON formatting replay under FSR-20260819-04 is byte-stable and idempotent; conflicting semantics are rejected.\n\n"
            "All artifacts remain an offline local handoff. No technician was dispatched, no part was externally reserved or installed, no permit or lockout was issued or executed, no equipment was energized, and no external maintenance action occurred.\n",
            encoding="utf-8",
        )
        for relative in (
            "maintenance_recovery_plan.json", ".maintenance_preview.json", "state/maintenance.db",
            "state/verification.json", "staging/service_dispatch_bundle.json",
            "staging/dispatch_manifest.json", "state/recovery_receipt.json",
            "state/replay_report.json", "maintenance_handoff.md",
        ):
            destination = REFERENCE / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / relative, destination)


def main() -> None:
    build_sources()
    build_database()
    build_reference()


if __name__ == "__main__":
    main()
