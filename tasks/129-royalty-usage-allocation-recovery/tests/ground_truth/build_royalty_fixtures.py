#!/usr/bin/env python3
"""Build deterministic synthetic source and interrupted-ledger fixtures for task 129."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"


def encoded(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_sources() -> None:
    policy = {
        "schema_version": 1,
        "statement_id": "RST-2026Q2-NORTH-01",
        "recovery_id": "ROYREC-20260819-01",
        "statement_period": {"from": "2026-04-01", "through": "2026-06-30"},
        "generated_at": "2026-08-19T17:30:00Z",
        "money_currency": "USD",
        "mapping_rule": "highest uniquely effective recording-to-work mapping version",
        "split_rule": "highest uniquely effective ownership version in territory on usage date",
        "adjustment_rule": "negative adjustments may offset only an event in this statement and inherit its mapping, rights, and split",
        "quarantine_states": [
            "unknown_recording",
            "ambiguous_mapping",
            "outside_rights_window",
            "cross_statement_adjustment",
        ],
        "external_actions_permitted": False,
    }
    write_json(WORKSPACE / "policy/royalty_policy.json", policy)

    events = [
        {
            "event_id": "USE-100",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZAAA2600001",
            "usage_date": "2026-05-10",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": 1000,
            "royalty_cents": 100000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-101",
            "event_version": 2,
            "event_type": "usage",
            "isrc": "QZAAA2600001",
            "usage_date": "2026-06-20",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": 550,
            "royalty_cents": 55000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-103",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZUNKNOWN00001",
            "usage_date": "2026-05-02",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": 200,
            "royalty_cents": 20000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-102",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZBBB2600002",
            "usage_date": "2026-04-15",
            "territory": "GB",
            "usage_type": "download",
            "units": 80,
            "royalty_cents": 40000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-104",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZAMBIG260004",
            "usage_date": "2026-05-25",
            "territory": "CA",
            "usage_type": "on_demand_stream",
            "units": 300,
            "royalty_cents": 30000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-101",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZAAA2600001",
            "usage_date": "2026-06-20",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": 600,
            "royalty_cents": 60000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-106",
            "event_version": 1,
            "event_type": "adjustment",
            "isrc": "QZAAA2600001",
            "usage_date": "2026-06-25",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": -100,
            "royalty_cents": -10000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": "USE-100",
        },
        {
            "event_id": "USE-105",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZCCC2600003",
            "usage_date": "2026-05-20",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": 500,
            "royalty_cents": 50000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-100",
            "event_version": 1,
            "event_type": "usage",
            "isrc": "QZAAA2600001",
            "usage_date": "2026-05-10",
            "territory": "US",
            "usage_type": "on_demand_stream",
            "units": 1000,
            "royalty_cents": 100000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": None,
        },
        {
            "event_id": "USE-107",
            "event_version": 1,
            "event_type": "adjustment",
            "isrc": "QZBBB2600002",
            "usage_date": "2026-06-28",
            "territory": "GB",
            "usage_type": "download",
            "units": -50,
            "royalty_cents": -5000,
            "statement_id": "RST-2026Q2-NORTH-01",
            "adjusts_event_id": "USE-099",
        },
    ]
    usage = WORKSPACE / "sources/usage_events.jsonl"
    usage.parent.mkdir(parents=True, exist_ok=True)
    usage.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events),
        encoding="utf-8",
    )

    mappings = {
        "schema_version": 1,
        "records": [
            {"mapping_id": "MAP-A1", "isrc": "QZAAA2600001", "recording_id": "REC-A", "iswc": "T-100.000.001-0", "version": 1, "effective_from": "2025-01-01", "effective_through": "2026-04-30"},
            {"mapping_id": "MAP-A2", "isrc": "QZAAA2600001", "recording_id": "REC-A", "iswc": "T-100.000.002-0", "version": 2, "effective_from": "2026-05-01", "effective_through": None},
            {"mapping_id": "MAP-B1", "isrc": "QZBBB2600002", "recording_id": "REC-B", "iswc": "T-200.000.001-0", "version": 1, "effective_from": "2025-01-01", "effective_through": None},
            {"mapping_id": "MAP-C1", "isrc": "QZCCC2600003", "recording_id": "REC-C", "iswc": "T-300.000.001-0", "version": 1, "effective_from": "2025-01-01", "effective_through": None},
            {"mapping_id": "MAP-X1", "isrc": "QZAMBIG260004", "recording_id": "REC-X", "iswc": "T-400.000.001-0", "version": 3, "effective_from": "2026-01-01", "effective_through": None},
            {"mapping_id": "MAP-X2", "isrc": "QZAMBIG260004", "recording_id": "REC-X", "iswc": "T-400.000.099-0", "version": 3, "effective_from": "2026-01-01", "effective_through": None},
        ],
    }
    write_json(WORKSPACE / "sources/recording_work_mappings.json", mappings)

    rights = {
        "schema_version": 1,
        "rights": [
            {"right_id": "RIGHT-A-US", "iswc": "T-100.000.002-0", "territory": "US", "usage_types": ["on_demand_stream"], "effective_from": "2026-01-01", "effective_through": "2026-12-31"},
            {"right_id": "RIGHT-A-CA", "iswc": "T-100.000.002-0", "territory": "CA", "usage_types": ["on_demand_stream"], "effective_from": "2026-01-01", "effective_through": "2026-12-31"},
            {"right_id": "RIGHT-B-GB", "iswc": "T-200.000.001-0", "territory": "GB", "usage_types": ["download"], "effective_from": "2026-01-01", "effective_through": "2026-12-31"},
            {"right_id": "RIGHT-C-US", "iswc": "T-300.000.001-0", "territory": "US", "usage_types": ["on_demand_stream"], "effective_from": "2025-01-01", "effective_through": "2026-04-30"},
        ],
        "ownership_splits": [
            {"split_id": "SPLIT-A1", "iswc": "T-100.000.002-0", "territory": "US", "version": 1, "effective_from": "2026-01-01", "effective_through": "2026-05-31", "shares_bps": {"RIGHTHOLDER-A": 6000, "RIGHTHOLDER-B": 4000}},
            {"split_id": "SPLIT-A2", "iswc": "T-100.000.002-0", "territory": "US", "version": 2, "effective_from": "2026-06-01", "effective_through": "2026-12-31", "shares_bps": {"RIGHTHOLDER-A": 5000, "RIGHTHOLDER-B": 5000}},
            {"split_id": "SPLIT-B1", "iswc": "T-200.000.001-0", "territory": "GB", "version": 1, "effective_from": "2026-01-01", "effective_through": "2026-12-31", "shares_bps": {"RIGHTHOLDER-C": 7000, "RIGHTHOLDER-D": 3000}},
        ],
    }
    write_json(WORKSPACE / "sources/rights_catalog.json", rights)


def build_ledger() -> None:
    path = WORKSPACE / "state/royalty_ledger.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA foreign_keys=ON;
        CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE recovery_journal (
            recovery_id TEXT PRIMARY KEY,
            statement_id TEXT NOT NULL,
            source_checkpoint TEXT NOT NULL,
            phase TEXT NOT NULL,
            partial_event_id TEXT,
            partial_allocation_count INTEGER NOT NULL,
            semantic_plan_sha256 TEXT,
            committed_at TEXT
        );
        CREATE TABLE statement_runs (
            statement_id TEXT PRIMARY KEY,
            recovery_id TEXT NOT NULL,
            source_checkpoint TEXT NOT NULL,
            semantic_plan_sha256 TEXT NOT NULL,
            event_count INTEGER NOT NULL,
            allocated_units INTEGER NOT NULL,
            allocated_cents INTEGER NOT NULL,
            quarantined_units INTEGER NOT NULL,
            quarantined_cents INTEGER NOT NULL,
            committed_at TEXT NOT NULL
        );
        CREATE TABLE event_dispositions (
            statement_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_version INTEGER NOT NULL,
            disposition TEXT NOT NULL,
            recording_id TEXT,
            iswc TEXT,
            mapping_version INTEGER,
            split_version INTEGER,
            units INTEGER NOT NULL,
            royalty_cents INTEGER NOT NULL,
            evidence_json TEXT NOT NULL,
            PRIMARY KEY (statement_id, event_id)
        );
        CREATE TABLE allocations (
            statement_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            rightsholder_id TEXT NOT NULL,
            units INTEGER NOT NULL,
            royalty_cents INTEGER NOT NULL,
            recovery_id TEXT NOT NULL,
            PRIMARY KEY (statement_id, event_id, rightsholder_id)
        );
        CREATE TABLE quarantines (
            statement_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            units INTEGER NOT NULL,
            royalty_cents INTEGER NOT NULL,
            evidence_json TEXT NOT NULL,
            PRIMARY KEY (statement_id, event_id)
        );
        """
    )
    source_paths = [
        WORKSPACE / "policy/royalty_policy.json",
        WORKSPACE / "sources/usage_events.jsonl",
        WORKSPACE / "sources/recording_work_mappings.json",
        WORKSPACE / "sources/rights_catalog.json",
    ]
    checkpoint = hashlib.sha256(
        (json.dumps(
            {p.relative_to(WORKSPACE).as_posix(): sha(p) for p in source_paths},
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n").encode()
    ).hexdigest()
    connection.execute("INSERT INTO system_state VALUES ('source_revision','17')")
    connection.execute(
        "INSERT INTO recovery_journal VALUES (?,?,?,?,?,?,?,?)",
        (
            "ROYREC-20260819-01",
            "RST-2026Q2-NORTH-01",
            checkpoint,
            "interrupted_partial_allocation",
            "USE-100",
            1,
            None,
            None,
        ),
    )
    connection.execute(
        "INSERT INTO allocations VALUES (?,?,?,?,?,?)",
        (
            "RST-2026Q2-NORTH-01",
            "USE-100",
            "RIGHTHOLDER-A",
            600,
            60000,
            "ROYREC-20260819-01",
        ),
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


if __name__ == "__main__":
    build_sources()
    build_ledger()
