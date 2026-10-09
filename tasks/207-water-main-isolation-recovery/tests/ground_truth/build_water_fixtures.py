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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    for relative in ("policy", "evidence", "state", "staging"):
        target = WORKSPACE / relative
        if target.exists():
            shutil.rmtree(target)
    (WORKSPACE / "policy").mkdir(parents=True)
    (WORKSPACE / "evidence").mkdir(parents=True)
    (WORKSPACE / "state").mkdir(parents=True)

    policy = {
        "schema_version": 1,
        "as_of_utc": "2026-08-19T17:00:00Z",
        "recovery_id": "WIR-20260819-01",
        "work_order_id": "WO-4471",
        "target_pipe_id": "P-4471",
        "selection_rule": "admissible lowest affected_connections then boundary_id",
        "admissibility": {
            "require_all_valves_closable": True,
            "allow_maintenance_lock_crossing": False,
            "maximum_critical_service_outages": 0,
        },
        "reason_precedence": ["maintenance_lock", "unavailable", "critical_feed", "selected_boundary", "outside_boundary"],
        "accepted_event_types": ["operability_observation"],
        "external_actions_allowed": False,
    }
    write_json(WORKSPACE / "policy/isolation_policy.json", policy)

    events = [
        {"delivery_id": "D-001", "event_id": "EV-V02-3", "valve_id": "V-02", "source_sequence": 3, "event_type": "operability_observation", "payload": {"operability": "stuck_open"}},
        {"delivery_id": "D-003", "event_id": "EV-V03-4", "valve_id": "V-03", "source_sequence": 4, "event_type": "operability_observation", "payload": {"operability": "operable"}},
        {"delivery_id": "D-002", "event_id": "EV-V02-3", "valve_id": "V-02", "source_sequence": 3, "event_type": "operability_observation", "payload": {"operability": "stuck_open"}},
        {"delivery_id": "D-004", "event_id": "EV-V03-4", "valve_id": "V-03", "source_sequence": 4, "event_type": "operability_observation", "payload": {"operability": "operable"}},
        {"delivery_id": "D-051", "event_id": "EV-COLLIDE-04", "valve_id": "V-04", "source_sequence": 5, "event_type": "operability_observation", "payload": {"operability": "operable"}},
        {"delivery_id": "D-052", "event_id": "EV-COLLIDE-04", "valve_id": "V-04", "source_sequence": 5, "event_type": "operability_observation", "payload": {"operability": "stuck_open"}},
        {"delivery_id": "D-061", "event_id": "EV-V06-A", "valve_id": "V-06", "source_sequence": 8, "event_type": "operability_observation", "payload": {"operability": "operable"}},
        {"delivery_id": "D-062", "event_id": "EV-V06-B", "valve_id": "V-06", "source_sequence": 8, "event_type": "operability_observation", "payload": {"operability": "stuck_open"}},
        {"delivery_id": "D-091", "event_id": "EV-UNKNOWN", "valve_id": "V-99", "source_sequence": 1, "event_type": "operability_observation", "payload": {"operability": "operable"}},
        {"delivery_id": "D-011", "event_id": "EV-V01-OLD", "valve_id": "V-01", "source_sequence": 1, "event_type": "operability_observation", "payload": {"operability": "stuck_open"}},
        {"delivery_id": "D-071", "event_id": "EV-V05-LOCKED", "valve_id": "V-05", "source_sequence": 7, "event_type": "operability_observation", "payload": {"operability": "operable"}},
    ]
    event_path = WORKSPACE / "evidence/telemetry_events.jsonl"
    event_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")

    database = WORKSPACE / "state/network.db"
    with sqlite3.connect(database) as con:
        con.executescript(
            """
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE work_orders(work_order_id TEXT PRIMARY KEY, target_pipe_id TEXT NOT NULL, status TEXT NOT NULL, requested_at TEXT NOT NULL);
            CREATE TABLE valves(valve_id TEXT PRIMARY KEY, physical_position TEXT NOT NULL, base_operability TEXT NOT NULL, maintenance_locked INTEGER NOT NULL, critical_feed INTEGER NOT NULL, high_water_sequence INTEGER NOT NULL, local_desired_position TEXT, local_disposition TEXT);
            CREATE TABLE boundaries(boundary_id TEXT PRIMARY KEY, target_pipe_id TEXT NOT NULL, affected_connections INTEGER NOT NULL, critical_service_outages INTEGER NOT NULL, impacted_zone_ids_json TEXT NOT NULL);
            CREATE TABLE boundary_valves(boundary_id TEXT NOT NULL, valve_id TEXT NOT NULL, PRIMARY KEY(boundary_id,valve_id));
            CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL, plan_hash TEXT NOT NULL, status TEXT NOT NULL, selected_boundary_id TEXT NOT NULL);
            CREATE TABLE recovery_journal(journal_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL, valve_id TEXT NOT NULL, before_json TEXT NOT NULL, restored INTEGER NOT NULL);
            CREATE TABLE valve_projections(recovery_id TEXT NOT NULL, valve_id TEXT NOT NULL, plan_hash TEXT NOT NULL, desired_position TEXT NOT NULL, disposition TEXT NOT NULL, operability TEXT NOT NULL, PRIMARY KEY(recovery_id,valve_id));
            """
        )
        con.execute("INSERT INTO system_state VALUES (?,?)", ("source_revision", "23"))
        con.execute("INSERT INTO work_orders VALUES (?,?,?,?)", ("WO-4471", "P-4471", "authorized_for_offline_planning", "2026-08-19T15:00:00Z"))
        con.executemany("INSERT INTO valves VALUES (?,?,?,?,?,?,?,?)", [
            ("V-01", "open", "operable", 0, 0, 2, None, None),
            ("V-02", "open", "operable", 0, 0, 2, None, None),
            ("V-03", "open", "unknown", 0, 0, 3, None, None),
            ("V-04", "open", "operable", 0, 0, 4, "closed", "stage_close"),
            ("V-05", "open", "operable", 1, 0, 6, None, None),
            ("V-06", "open", "operable", 0, 0, 7, None, None),
            ("V-07", "open", "operable", 0, 1, 2, None, None),
        ])
        con.executemany("INSERT INTO boundaries VALUES (?,?,?,?,?)", [
            ("B-A", "P-4471", 120, 0, json.dumps(["Z-NORTH"])),
            ("B-B", "P-4471", 145, 0, json.dumps(["Z-EAST", "Z-NORTH"])),
            ("B-C", "P-4471", 80, 0, json.dumps(["Z-WEST"])),
            ("B-D", "P-4471", 60, 1, json.dumps(["Z-HOSPITAL"])),
        ])
        con.executemany("INSERT INTO boundary_valves VALUES (?,?)", [
            ("B-A", "V-01"), ("B-A", "V-02"),
            ("B-B", "V-03"), ("B-B", "V-04"),
            ("B-C", "V-05"), ("B-C", "V-06"),
            ("B-D", "V-03"), ("B-D", "V-07"),
        ])
        before = {"local_desired_position": None, "local_disposition": None}
        con.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?)", ("WIR-INTERRUPTED-00", "sha256:interrupted", "sha256:partial", "interrupted", "B-B"))
        con.execute("INSERT INTO recovery_journal VALUES (?,?,?,?,?)", ("J-INT-V04", "WIR-INTERRUPTED-00", "V-04", json.dumps(before, sort_keys=True), 0))
        con.execute("INSERT INTO valve_projections VALUES (?,?,?,?,?,?)", ("WIR-INTERRUPTED-00", "V-04", "sha256:partial", "closed", "stage_close", "operable"))
        con.commit()

    write_json(WORKSPACE / "policy/source_manifest.json", {
        "schema_version": 1,
        "files": {
            "policy/isolation_policy.json": sha256(WORKSPACE / "policy/isolation_policy.json"),
            "evidence/telemetry_events.jsonl": sha256(event_path),
        },
    })
    for relative in (
        "isolation_recovery_plan.json", ".isolation_preview.json", "isolation_handoff.md",
        "state/recovery_receipt.json", "state/verification.json", "state/replay_report.json",
    ):
        (WORKSPACE / relative).unlink(missing_ok=True)


if __name__ == "__main__":
    build()
