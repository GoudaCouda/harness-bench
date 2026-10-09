#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
BATCH_ID = "CDC-2026-08-19-42"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def build_database(path: Path) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        CREATE TABLE dimension_current (
          customer_id TEXT PRIMARY KEY, current_version INTEGER NOT NULL,
          name TEXT NOT NULL, segment TEXT NOT NULL, region TEXT NOT NULL,
          consent_state TEXT NOT NULL, is_deleted INTEGER NOT NULL CHECK(is_deleted IN (0,1))
        );
        CREATE TABLE dimension_history (
          customer_id TEXT NOT NULL, version INTEGER NOT NULL,
          name TEXT NOT NULL, segment TEXT NOT NULL, region TEXT NOT NULL,
          consent_state TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT,
          is_deleted INTEGER NOT NULL CHECK(is_deleted IN (0,1)), source_event_id TEXT NOT NULL,
          PRIMARY KEY(customer_id, version)
        );
        CREATE TABLE event_ledger (
          event_id TEXT PRIMARY KEY, disposition TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL, applied_at TEXT NOT NULL
        );
        CREATE TABLE event_quarantine (
          event_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
          reason TEXT NOT NULL, payload_sha256 TEXT NOT NULL
        );
        CREATE TABLE recovery_transactions (
          batch_id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL,
          source_sha256 TEXT NOT NULL, action_count INTEGER NOT NULL, committed_at TEXT NOT NULL
        );
        CREATE TABLE recovery_journal (
          batch_id TEXT PRIMARY KEY, phase TEXT NOT NULL, prepared_event_id TEXT NOT NULL,
          prepared_payload_sha256 TEXT NOT NULL, source_sha256 TEXT NOT NULL,
          plan_sha256 TEXT, started_at TEXT NOT NULL, committed_at TEXT
        );
        """
    )
    current = [
        ("C001", 3, "Alpha Goods", "standard", "west", "granted", 0),
        ("C002", 1, "Beacon Retail", "basic", "north", "granted", 0),
        ("C003", 2, "Cedar Clinic", "pro", "south", "denied", 0),
    ]
    history = [
        ("C001", 1, "Alpha Goods", "basic", "west", "granted", "2026-01-01T00:00:00Z", "2026-05-01T00:00:00Z", 0, "INIT-C001-1"),
        ("C001", 2, "Alpha Goods", "standard", "west", "granted", "2026-05-01T00:00:00Z", "2026-08-18T08:00:00Z", 0, "INIT-C001-2"),
        ("C001", 3, "Alpha Goods", "standard", "west", "granted", "2026-08-18T08:00:00Z", None, 0, "INIT-C001-3"),
        ("C002", 1, "Beacon Retail", "basic", "north", "granted", "2026-06-01T00:00:00Z", None, 0, "INIT-C002-1"),
        ("C003", 1, "Cedar Clinic", "basic", "south", "denied", "2026-02-01T00:00:00Z", "2026-07-01T00:00:00Z", 0, "INIT-C003-1"),
        ("C003", 2, "Cedar Clinic", "pro", "south", "denied", "2026-07-01T00:00:00Z", None, 0, "INIT-C003-2"),
    ]
    connection.executemany("INSERT INTO dimension_current VALUES (?, ?, ?, ?, ?, ?, ?)", current)
    connection.executemany("INSERT INTO dimension_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", history)
    events = {}
    for line in (WORKSPACE / "cdc_batch.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        events[row["event_id"]] = row
    connection.execute(
        "INSERT INTO recovery_journal VALUES (?, 'prepared', ?, ?, ?, NULL, ?, NULL)",
        (
            BATCH_ID,
            "EV-406",
            digest_bytes(canonical(events["EV-406"])),
            digest_bytes((WORKSPACE / "cdc_batch.jsonl").read_bytes()),
            "2026-08-19T10:42:00Z",
        ),
    )
    connection.commit()
    connection.row_factory = sqlite3.Row
    initial = {
        "dimension_current": [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM dimension_current ORDER BY customer_id"
            )
        ],
        "dimension_history": [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM dimension_history ORDER BY customer_id, version"
            )
        ],
    }
    (WORKSPACE / "initial_warehouse.json").write_text(
        json.dumps(initial, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    connection.execute("VACUUM")
    connection.close()


def write_manifest() -> None:
    names = [
        "initial_warehouse.json", "cdc_batch.jsonl", "recovery_policy.md", "schema_registry.json",
        "retention_holds.csv", "signed_corrections.json", "cdcctl.py",
    ]
    value = {name: digest_bytes((WORKSPACE / name).read_bytes()) for name in names}
    (WORKSPACE / "SOURCE_HASHES.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def plan() -> dict[str, object]:
    dispositions = {
        "EV-401": "apply_upsert", "EV-402": "apply_upsert", "EV-403": "apply_upsert",
        "EV-404": "quarantine_retention_hold", "EV-405": "quarantine_missing_consent",
        "EV-406": "apply_upsert", "EV-407": "ignore_stale",
        "EV-408": "apply_signed_correction", "EV-409": "quarantine_unsupported_schema",
    }
    extra = {
        "EV-404": ["retention_holds.csv#C003"],
        "EV-405": ["recovery_policy.md#missing-consent"],
        "EV-406": ["warehouse.db#recovery_journal"],
        "EV-408": ["signed_corrections.json#CORR-88"],
        "EV-409": ["schema_registry.json#supported"],
    }
    return {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "source_sha256": digest_bytes((WORKSPACE / "cdc_batch.jsonl").read_bytes()),
        "actions": [
            {
                "event_id": event_id,
                "disposition": disposition,
                "evidence_refs": [f"cdc_batch.jsonl#{event_id}", *extra.get(event_id, [])],
            }
            for event_id, disposition in dispositions.items()
        ],
        "external_publish_executed": False,
    }


def handoff() -> str:
    return """# CDC-42 recovery handoff

The local batch was recovered and staged pending publish approval. No external publish, notification, deployment, or remote warehouse action occurred.

## Adjudication

EV-401 advances C001 from version 3 to version 4 and changes only the segment to enterprise. Its second delivery is byte-equivalent, so it is deduplicated by event ID and applied once. EV-402 arrived before EV-403, but sorting by entity version shows that EV-403 supplies C002 version 2 and EV-402 supplies version 3; together they close the complete 1→2→3 chain. EV-407 is an ordinary C001 version-2 event below the existing version 3 and is recorded as stale without rewinding history.

EV-408 is the verified CORR-88 steward correction for C001 version 3. It changes region to central. EV-401 does not explicitly change region, so version 4 inherits central; the correction does not disturb its enterprise segment. EV-404 is quarantined because C003 has active HOLD-77, and C003 remains at version 2 without a tombstone. EV-405 is quarantined because a new customer lacks consent provenance. EV-409 is quarantined because source schema 3 is unsupported. EV-406 is a valid schema-2 insert for C005 and consumes the durable prepared journal record without a duplicate application.

## Transaction and verification

The recovery committed one nine-action batch transaction. The event ledger has one final disposition per unique event, the prepare journal is committed, history intervals close at the next effective timestamp, and current projections match the final history rows. The controller verification passed for projections, history, ledger, quarantines, transaction count, and journal state. Re-running apply returned idempotent; re-running stage preserved the same digest-bound receipt. The package remains an offline local stage pending an independent publish approval.
"""


def build_reference() -> None:
    REFERENCE.mkdir(parents=True, exist_ok=True)
    for child in REFERENCE.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
    with tempfile.TemporaryDirectory(prefix="cdc-reference-") as temporary:
        target = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, target)
        (target / "recovery_plan.json").write_text(json.dumps(plan(), indent=2) + "\n", encoding="utf-8")
        (target / "recovery_handoff.md").write_text(handoff(), encoding="utf-8")
        for arguments in (
            ("preview", "recovery_plan.json"),
            ("apply", "recovery_plan.json"),
            ("apply", "recovery_plan.json"),
            ("verify",),
            ("stage", "recovery_plan.json"),
            ("stage", "recovery_plan.json"),
        ):
            subprocess.run(["python3", "cdcctl.py", *arguments], cwd=target, check=True, stdout=subprocess.PIPE, text=True)
        for name in ("warehouse.db", "recovery_plan.json", "recovery_handoff.md", "cdc_verification.json", "cdc_stage_receipt.json"):
            shutil.copy2(target / name, REFERENCE / name)


def main() -> None:
    build_database(WORKSPACE / "warehouse.db")
    write_manifest()
    build_reference()
    truth = {
        "batch_id": BATCH_ID,
        "source_sha256": digest_bytes((WORKSPACE / "cdc_batch.jsonl").read_bytes()),
        "unique_event_count": 9,
        "quarantine_event_ids": ["EV-404", "EV-405", "EV-409"],
        "current_versions": {"C001": 4, "C002": 3, "C003": 2, "C005": 1},
    }
    (TASK / "tests/ground_truth/ground_truth.json").write_text(
        json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
