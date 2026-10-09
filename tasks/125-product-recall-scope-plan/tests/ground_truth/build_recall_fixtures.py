#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests" / "reference"
TRUTH = TASK / "tests" / "ground_truth" / "ground_truth.json"
STATE_TABLES = (
    "lots",
    "component_batches",
    "lot_components",
    "inventory",
    "channels",
    "shipments",
)
ALL_TABLES = (
    *STATE_TABLES,
    "event_ledger",
    "event_quarantine",
    "recall_transactions",
    "recall_journal",
)


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def snapshot(connection: sqlite3.Connection, tables: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    connection.row_factory = sqlite3.Row
    result = {}
    for table in tables:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        order = ", ".join(columns[:2])
        result[table] = [
            dict(row)
            for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
        ]
    return result


def build_database() -> str:
    database = WORKSPACE / "recall.db"
    database.unlink(missing_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript((WORKSPACE / "recall_seed.sql").read_text(encoding="utf-8"))
        source_sha = canonical_digest(snapshot(connection, STATE_TABLES))
        connection.execute(
            "UPDATE recall_journal SET source_state_sha256=? WHERE recall_id='RC-2026-0417'",
            (source_sha,),
        )
        connection.commit()
    checkpoint = {
        "recall_id": "RC-2026-0417",
        "source_state_sha256": source_sha,
        "interrupted_phase": "prepared",
        "prepared_action_key": "EV-504",
        "created_at": "2026-08-19T08:20:00Z",
    }
    (WORKSPACE / "recall_checkpoint.json").write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return source_sha


def plan(source_sha: str) -> dict[str, Any]:
    lot_actions = {
        "LOT-A": "affected",
        "LOT-B": "affected",
        "LOT-C": "unaffected",
        "LOT-D": "pending_trace",
        "LOT-E": "affected",
        "LOT-F": "unaffected",
    }
    event_actions = {
        "EV-500": "ignore_stale",
        "EV-501": "apply_current",
        "EV-502": "apply_current",
        "EV-503": "ignore_stale",
        "EV-504": "apply_current",
        "EV-505": "quarantine_unknown_shipment",
        "EV-506": "apply_current",
    }
    event_shipments = {
        "EV-500": "SH-A",
        "EV-501": "SH-A",
        "EV-502": "SH-B",
        "EV-503": "SH-B",
        "EV-504": "SH-E",
        "EV-505": "SH-UNKNOWN",
        "EV-506": "SH-D",
    }
    return {
        "schema_version": 1,
        "recall_id": "RC-2026-0417",
        "source_state_sha256": source_sha,
        "scope_revision_id": "SCOPE-02",
        "lot_actions": [
            {
                "lot_id": lot_id,
                "disposition": disposition,
                "evidence_refs": [
                    f"recall.db#lots/{lot_id}",
                    "signed_scope_revisions.json#revisions",
                    "recall_policy.md#genealogy-decisions",
                ],
            }
            for lot_id, disposition in lot_actions.items()
        ],
        "event_actions": [
            {
                "event_id": event_id,
                "disposition": disposition,
                "evidence_refs": [
                    f"recall.db#shipments/{event_shipments[event_id]}",
                    f"shipment_events.jsonl#{event_id}",
                    "recall_policy.md#feed-adjudication",
                ],
            }
            for event_id, disposition in event_actions.items()
        ],
        "external_actions_executed": False,
    }


HANDOFF = """# RC-2026-0417 local recall recovery handoff

The controlling signed scope is SCOPE-02: it supersedes SCOPE-01, while the later
SCOPE-03-DRAFT has no authority. LOT-A and mixed LOT-B directly contain CB-77;
LOT-E contains verified descendant CB-77-D. All three are affected and their
available inventory is quarantined. LOT-F contains CB-77 but falls outside the
controlling manufacture window, and LOT-C contains only CB-SAFE, so both remain
unaffected. LOT-D uses ADH-RED through CB-UNK with an unresolved parent and is
therefore held as pending trace rather than guessed affected or cleared.

The out-of-order feed was reduced by stable event identity and sequence. EV-501,
EV-502, EV-504, and EV-506 are the current shipment events. EV-500 and EV-503
are stale. The exact duplicate EV-502 delivery is represented only once, and
EV-505 is quarantined because SH-UNKNOWN is absent. The interrupted prepared
EV-504 journal was completed in the same RC-2026-0417 transaction.

SH-A is already delivered, so CH-RETAIL receives only a local recall draft;
SH-E is in transit and has a staged stop request. SH-B is in transit but CH-DIST
still lacks approved authority, so its channel work remains pending approval.
SH-D stays under a pending-trace hold and CH-MKT remains a trace hold. Inventory
for affected and unresolved lots is nonnegative and conserved: units were moved
from available to quarantine without changing on-hand totals.

Preview, apply, independent verification, equivalent idempotent replay, and local
stage binding completed. This package executed no external stop-sale, notice,
refund, repair, shipment change, or channel action; every draft and receipt is
an offline handoff pending human authority.
"""


def write_reference(source_sha: str) -> None:
    REFERENCE.mkdir(parents=True, exist_ok=True)
    for path in REFERENCE.iterdir():
        if path.is_file():
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="recall-125-build-") as directory:
        workspace = Path(directory) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        (workspace / "recall_plan.json").write_text(
            json.dumps(plan(source_sha), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (workspace / "recall_handoff.md").write_text(HANDOFF, encoding="utf-8")
        for arguments in (
            ("preview", "recall_plan.json"),
            ("apply", "recall_plan.json"),
            ("apply", "recall_plan.json"),
            ("verify", "recall_plan.json"),
            ("stage", "recall_plan.json"),
            ("stage", "recall_plan.json"),
        ):
            subprocess.run(
                ["python3", "recallctl.py", *arguments],
                cwd=workspace,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
        for name in (
            "recall.db",
            "recall_plan.json",
            "recall_verification.json",
            "recall_stage_receipt.json",
            "recall_handoff.md",
        ):
            shutil.copy2(workspace / name, REFERENCE / name)
        with sqlite3.connect(workspace / "recall.db") as connection:
            final = snapshot(connection, ALL_TABLES)
    TRUTH.write_text(
        json.dumps(
            {
                "source_state_sha256": source_sha,
                "lot_dispositions": {
                    row["lot_id"]: row["disposition"] for row in plan(source_sha)["lot_actions"]
                },
                "event_dispositions": {
                    row["event_id"]: row["disposition"] for row in plan(source_sha)["event_actions"]
                },
                "final_state": final,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_hashes() -> None:
    protected = (
        "recall_seed.sql",
        "signed_scope_revisions.json",
        "shipment_events.jsonl",
        "recall_policy.md",
        "recall_checkpoint.json",
        "recallctl.py",
    )
    hashes = {
        name: hashlib.sha256((WORKSPACE / name).read_bytes()).hexdigest()
        for name in protected
    }
    (WORKSPACE / "SOURCE_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    source_sha = build_database()
    write_reference(source_sha)
    write_hashes()


if __name__ == "__main__":
    main()
