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


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def reading(
    reading_id: str, device: str, sequence: int, local: str, offset: str, temp: float
) -> dict[str, object]:
    return {
        "reading_id": reading_id,
        "device_id": device,
        "sequence": sequence,
        "observed_local": local,
        "utc_offset": offset,
        "temperature_c": temp,
    }


def main() -> None:
    for name in (
        "excursion_plan.json",
        ".cold_chain_preview.json",
        "cold_chain_handoff.md",
    ):
        (WORKSPACE / name).unlink(missing_ok=True)
    for name in ("verification.json", "qa_packet.json", "replay_report.json"):
        (WORKSPACE / "state" / name).unlink(missing_ok=True)
    policy = {
        "schema_version": 1,
        "recovery_id": "CCR-20261101-01",
        "as_of_utc": "2026-11-01T07:00:00Z",
        "sample_interval_minutes": 10,
        "temperature_band_c": {"lower_inclusive": 2.0, "upper_inclusive": 8.0},
        "excursion_minimum_minutes": 20,
        "dispositions": ["available", "hold_evidence_gap", "quarantine_do_not_use"],
        "next_local_actions": [
            "none",
            "route_to_qa_for_missing_evidence",
            "retain_in_do_not_use_quarantine",
        ],
        "immutable_lot_fields": ["product_code", "quantity", "container_id"],
        "prohibited_actions": ["destroy", "release", "administer", "notify", "ship"],
    }
    trust = {
        "key_id": "DEPOT-LOGGER-QA-2026",
        "verification_material": "synthetic-offline-logger-verification-material-v1",
        "signature_scheme": "synthetic-sha256-fixture-only",
    }
    readings = [
        reading("A-P-001", "P-A1", 1, "2026-11-01T01:00:00", "-04:00", 5.0),
        reading("A-P-002", "P-A1", 2, "2026-11-01T01:10:00", "-04:00", 5.1),
        reading("A-P-003", "P-A1", 3, "2026-11-01T01:20:00", "-04:00", 5.0),
        reading("A-P-007", "P-A1", 7, "2026-11-01T01:10:00", "-05:00", 5.0),
        reading("A-P-008", "P-A1", 8, "2026-11-01T01:20:00", "-05:00", 4.9),
        reading("A-S-053", "S-A1", 53, "2026-11-01T01:00:00", "-05:00", 8.4),
        reading("A-S-050", "S-A1", 50, "2026-11-01T01:30:00", "-04:00", 7.5),
        reading("A-S-052", "S-A1", 52, "2026-11-01T01:50:00", "-04:00", 8.5),
        reading("A-S-051", "S-A1", 51, "2026-11-01T01:40:00", "-04:00", 8.3),
        reading("B-P-001", "P-B1", 1, "2026-11-01T01:00:00", "-04:00", 4.1),
        reading("B-P-002", "P-B1", 2, "2026-11-01T01:10:00", "-04:00", 4.2),
        reading("B-P-003", "P-B1", 3, "2026-11-01T01:20:00", "-04:00", 4.0),
        reading("B-P-006", "P-B1", 6, "2026-11-01T01:00:00", "-05:00", 4.1),
        reading("B-P-007", "P-B1", 7, "2026-11-01T01:10:00", "-05:00", 4.0),
        reading("B-P-008", "P-B1", 8, "2026-11-01T01:20:00", "-05:00", 4.2),
        reading("B-S-050", "S-B1", 50, "2026-11-01T01:30:00", "-04:00", 4.3),
        reading("B-S-051", "S-B1", 51, "2026-11-01T01:40:00", "-04:00", 4.2),
        reading("B-S-052", "S-B1", 52, "2026-11-01T01:50:00", "-04:00", 4.3),
    ]
    cedar_values = [3.0, 3.2, 3.4, 3.6, 4.5, 4.1, 3.9, 3.8, 3.7]
    local_times = [
        ("2026-11-01T01:00:00", "-04:00"),
        ("2026-11-01T01:10:00", "-04:00"),
        ("2026-11-01T01:20:00", "-04:00"),
        ("2026-11-01T01:30:00", "-04:00"),
        ("2026-11-01T01:40:00", "-04:00"),
        ("2026-11-01T01:50:00", "-04:00"),
        ("2026-11-01T01:00:00", "-05:00"),
        ("2026-11-01T01:10:00", "-05:00"),
        ("2026-11-01T01:20:00", "-05:00"),
    ]
    for index, ((local, offset), value) in enumerate(
        zip(local_times, cedar_values, strict=True), 1
    ):
        readings.append(
            reading(f"C-P-{index:03d}", "P-C1", index, local, offset, value)
        )
    readings.append(dict(readings[-6], reading_id="C-P-004-DUP"))
    readings_path = WORKSPACE / "evidence/logger_readings.jsonl"
    readings_path.parent.mkdir(parents=True, exist_ok=True)
    readings_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in readings),
        encoding="utf-8",
    )

    def range_record(
        range_id: str, device: str, container: str, ids: list[str]
    ) -> dict[str, object]:
        selected = [row for row in readings if row["reading_id"] in ids]
        payload = {
            "range_id": range_id,
            "device_id": device,
            "container_id": container,
            "sequence_start": min(int(row["sequence"]) for row in selected),
            "sequence_end": max(int(row["sequence"]) for row in selected),
            "coverage_start_utc": "2026-11-01T05:30:00Z",
            "coverage_end_utc": "2026-11-01T06:00:00Z"
            if device == "S-A1"
            else "2026-11-01T05:50:00Z",
            "readings_sha256": digest(canonical(selected)),
        }
        return {
            **payload,
            "key_id": trust["key_id"],
            "signature": digest(
                canonical(payload) + str(trust["verification_material"]).encode()
            ),
        }

    ranges = {
        "schema_version": 1,
        "ranges": [
            range_record(
                "RANGE-A-50-53",
                "S-A1",
                "CT-01",
                ["A-S-050", "A-S-051", "A-S-052", "A-S-053"],
            ),
            range_record(
                "RANGE-B-50-52", "S-B1", "CT-02", ["B-S-050", "B-S-051", "B-S-052"]
            ),
        ],
    }
    events = {
        "events": [
            {
                "event_id": "DOOR-17",
                "container_id": "CT-01",
                "occurred_at_utc": "2026-11-01T05:37:00Z",
                "kind": "door_open",
                "note": "scheduled transfer inspection",
            },
            {
                "event_id": "MOVE-22",
                "container_id": "CT-02",
                "occurred_at_utc": "2026-11-01T05:25:00Z",
                "kind": "dock_transfer",
                "note": "sealed tote moved to backup power",
            },
        ]
    }
    write_json(WORKSPACE / "policy/cold_chain_policy.json", policy)
    write_json(WORKSPACE / "evidence/logger_trust.json", trust)
    write_json(WORKSPACE / "evidence/secondary_ranges.json", ranges)
    write_json(WORKSPACE / "evidence/transport_events.json", events)

    state = WORKSPACE / "state"
    state.mkdir(exist_ok=True)
    db_path = state / "cold_chain.db"
    db_path.unlink(missing_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript("""
        CREATE TABLE lots(lot_id TEXT PRIMARY KEY, product_code TEXT NOT NULL, quantity INTEGER NOT NULL, container_id TEXT NOT NULL, disposition TEXT NOT NULL, do_not_use INTEGER NOT NULL, version INTEGER NOT NULL);
        CREATE TABLE containers(container_id TEXT PRIMARY KEY, evaluation_start_utc TEXT NOT NULL, evaluation_end_utc TEXT NOT NULL, timezone_name TEXT NOT NULL);
        CREATE TABLE devices(device_id TEXT PRIMARY KEY, serial_number TEXT NOT NULL, device_type TEXT NOT NULL);
        CREATE TABLE device_assignments(assignment_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, container_id TEXT NOT NULL, role TEXT NOT NULL, valid_from_utc TEXT NOT NULL, valid_to_utc TEXT NOT NULL);
        CREATE TABLE calibrations(calibration_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, valid_from_utc TEXT NOT NULL, valid_to_utc TEXT NOT NULL, offset_c REAL NOT NULL, status TEXT NOT NULL);
        CREATE TABLE excursion_assessments(lot_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL, disposition TEXT NOT NULL, min_c REAL, max_c REAL, out_of_range_minutes INTEGER, evidence_sha256 TEXT NOT NULL);
        CREATE TABLE holds(hold_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL, recovery_id TEXT NOT NULL, hold_type TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL, semantic_plan_sha256 TEXT NOT NULL, status TEXT NOT NULL, db_after_sha256 TEXT, stage_token TEXT);
        CREATE TABLE recovery_journal(journal_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL, lot_id TEXT NOT NULL, before_json TEXT NOT NULL, restored INTEGER NOT NULL);
        CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        connection.executemany(
            "INSERT INTO lots VALUES(?,?,?,?,?,?,?)",
            [
                ("LOT-AURORA", "VAC-MRNA-30", 420, "CT-01", "qa_hold", 0, 2),
                ("LOT-BIRCH", "VAC-RSV-10", 160, "CT-02", "available", 0, 1),
                ("LOT-CEDAR", "VAC-FLU-05", 300, "CT-03", "available", 0, 1),
            ],
        )
        connection.executemany(
            "INSERT INTO containers VALUES(?,?,?,?)",
            [
                (
                    container,
                    "2026-11-01T05:00:00Z",
                    "2026-11-01T06:20:00Z",
                    "America/New_York",
                )
                for container in ("CT-01", "CT-02", "CT-03")
            ],
        )
        connection.executemany(
            "INSERT INTO devices VALUES(?,?,?)",
            [
                ("P-A1", "PA-9001", "primary"),
                ("S-A1", "SA-4110", "secondary"),
                ("P-B1", "PB-9002", "primary"),
                ("S-B1", "SB-4111", "secondary"),
                ("P-C1", "PC-9003", "primary"),
            ],
        )
        connection.executemany(
            "INSERT INTO device_assignments VALUES(?,?,?,?,?,?)",
            [
                (
                    "ASN-PA",
                    "P-A1",
                    "CT-01",
                    "primary",
                    "2026-10-01T00:00:00Z",
                    "2026-12-01T00:00:00Z",
                ),
                (
                    "ASN-SA",
                    "S-A1",
                    "CT-01",
                    "secondary",
                    "2026-10-31T20:00:00Z",
                    "2026-11-01T08:00:00Z",
                ),
                (
                    "ASN-PB",
                    "P-B1",
                    "CT-02",
                    "primary",
                    "2026-10-01T00:00:00Z",
                    "2026-12-01T00:00:00Z",
                ),
                (
                    "ASN-SB",
                    "S-B1",
                    "CT-02",
                    "secondary",
                    "2026-10-31T20:00:00Z",
                    "2026-11-01T08:00:00Z",
                ),
                (
                    "ASN-PC",
                    "P-C1",
                    "CT-03",
                    "primary",
                    "2026-10-01T00:00:00Z",
                    "2026-12-01T00:00:00Z",
                ),
            ],
        )
        connection.executemany(
            "INSERT INTO calibrations VALUES(?,?,?,?,?,?)",
            [
                (
                    "CAL-SA-2026",
                    "S-A1",
                    "2026-09-01T00:00:00Z",
                    "2027-09-01T00:00:00Z",
                    -0.1,
                    "valid",
                ),
                (
                    "CAL-SB-OLD",
                    "S-B1",
                    "2025-05-01T00:00:00Z",
                    "2026-11-01T05:20:00Z",
                    0.0,
                    "valid",
                ),
            ],
        )
        before = {
            "lot_id": "LOT-AURORA",
            "product_code": "VAC-MRNA-30",
            "quantity": 420,
            "container_id": "CT-01",
            "disposition": "available",
            "do_not_use": 0,
            "version": 1,
        }
        connection.execute(
            "INSERT INTO recovery_runs VALUES(?,?,?,?,?,?)",
            (
                "CCR-INTERRUPTED-00",
                "old-checkpoint",
                "old-plan",
                "interrupted",
                None,
                None,
            ),
        )
        connection.execute(
            "INSERT INTO recovery_journal VALUES(?,?,?,?,?)",
            (
                "JRN-OLD-A",
                "CCR-INTERRUPTED-00",
                "LOT-AURORA",
                json.dumps(before, sort_keys=True),
                0,
            ),
        )
        connection.execute(
            "INSERT INTO system_state VALUES(?,?)", ("inventory_revision", "12")
        )
        connection.commit()

    protected = [
        "policy/cold_chain_policy.json",
        "evidence/logger_readings.jsonl",
        "evidence/logger_trust.json",
        "evidence/secondary_ranges.json",
        "evidence/transport_events.json",
    ]
    files = {name: digest((WORKSPACE / name).read_bytes()) for name in protected}
    write_json(
        WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": files}
    )


if __name__ == "__main__":
    main()
