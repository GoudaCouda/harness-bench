#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests" / "reference"
REVIEW_ID = "CLOSEOUT-2026-08-15-R1"
SOURCE_NAMES = ("contracts.csv", "evidence_events.csv", "closeout_policy.md")
DECISIONS: dict[str, tuple[str, str, str, list[str]]] = {
    "C-401": (
        "ready_for_controller",
        "controller",
        "approve_closeout_package",
        [
            "contracts.csv#C-401",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-401-LEGAL-HOLD",
            "evidence_events.csv#EV-401-ACCEPT",
            "evidence_events.csv#EV-401-INVOICE",
            "evidence_events.csv#EV-401-LEGAL-CLEAR",
            "evidence_events.csv#EV-401-FUNDS",
        ],
    ),
    "C-402": (
        "hold",
        "finance",
        "obtain_final_invoice",
        [
            "contracts.csv#C-402",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-402-ACCEPT",
            "evidence_events.csv#EV-402-LEGAL",
            "evidence_events.csv#EV-402-INVOICE",
            "evidence_events.csv#EV-402-FUNDS",
        ],
    ),
    "C-403": (
        "hold",
        "legal",
        "resolve_legal_hold",
        [
            "contracts.csv#C-403",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-403-ACCEPT",
            "evidence_events.csv#EV-403-LEGAL-HOLD",
            "evidence_events.csv#EV-403-INVOICE",
            "evidence_events.csv#EV-403-FUNDS",
        ],
    ),
    "C-404": (
        "hold",
        "contracts",
        "await_option_expiry",
        [
            "contracts.csv#C-404",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-404-ACCEPT",
            "evidence_events.csv#EV-404-LEGAL",
            "evidence_events.csv#EV-404-INVOICE",
            "evidence_events.csv#EV-404-FUNDS",
        ],
    ),
    "C-405": (
        "hold",
        "program",
        "complete_acceptance",
        [
            "contracts.csv#C-405",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-405-ACCEPT",
            "evidence_events.csv#EV-405-LEGAL",
            "evidence_events.csv#EV-405-INVOICE",
            "evidence_events.csv#EV-405-FUNDS",
        ],
    ),
    "C-406": (
        "ready_for_controller",
        "controller",
        "approve_closeout_package",
        [
            "contracts.csv#C-406",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-406-ACCEPT",
            "evidence_events.csv#EV-406-FUNDS-DRAFT",
            "evidence_events.csv#EV-406-FUNDS-CURE",
            "evidence_events.csv#EV-406-LEGAL",
            "evidence_events.csv#EV-406-INVOICE",
        ],
    ),
    "C-407": (
        "hold",
        "finance",
        "complete_deobligation",
        [
            "contracts.csv#C-407",
            "closeout_policy.md#gate-precedence",
            "evidence_events.csv#EV-407-INVOICE",
            "evidence_events.csv#EV-407-LEGAL",
            "evidence_events.csv#EV-407-FUNDS",
            "evidence_events.csv#EV-407-ACCEPT",
        ],
    ),
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_checkpoint(root: Path) -> str:
    manifest = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in SOURCE_NAMES
    }
    return digest(manifest)


def plan(root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "source_checkpoint_sha256": source_checkpoint(root),
        "decisions": [
            {
                "contract_id": contract_id,
                "disposition": values[0],
                "owner": values[1],
                "next_action": values[2],
                "evidence_refs": sorted(values[3]),
            }
            for contract_id, values in sorted(DECISIONS.items())
        ],
        "external_actions_executed": False,
    }


def create_initial_database(path: Path) -> None:
    path.unlink(missing_ok=True)
    checkpoint = source_checkpoint(WORKSPACE)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            PRAGMA foreign_keys=ON;
            CREATE TABLE review_meta (
                review_id TEXT PRIMARY KEY,
                as_of_date TEXT NOT NULL,
                source_checkpoint_sha256 TEXT NOT NULL,
                external_actions_executed INTEGER NOT NULL CHECK (external_actions_executed IN (0, 1))
            );
            CREATE TABLE contract_state (
                contract_id TEXT PRIMARY KEY,
                disposition TEXT NOT NULL,
                owner TEXT NOT NULL,
                next_action TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                decision_sequence INTEGER NOT NULL
            );
            CREATE TABLE closeout_audit (
                audit_sequence INTEGER PRIMARY KEY,
                review_id TEXT NOT NULL,
                contract_id TEXT NOT NULL UNIQUE,
                disposition TEXT NOT NULL,
                owner TEXT NOT NULL,
                next_action TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES review_meta(review_id)
            );
            CREATE TABLE review_journal (
                review_id TEXT PRIMARY KEY,
                phase TEXT NOT NULL,
                applied_count INTEGER NOT NULL,
                source_checkpoint_sha256 TEXT NOT NULL,
                semantic_plan_sha256 TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES review_meta(review_id)
            );
            CREATE TABLE review_transactions (
                review_id TEXT PRIMARY KEY,
                source_checkpoint_sha256 TEXT NOT NULL,
                semantic_plan_sha256 TEXT NOT NULL,
                action_count INTEGER NOT NULL,
                committed_at TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES review_meta(review_id)
            );
            """
        )
        connection.execute(
            "INSERT INTO review_meta VALUES (?, ?, ?, 0)",
            (REVIEW_ID, "2026-08-15", checkpoint),
        )
        for sequence, (contract_id, values) in enumerate(sorted(DECISIONS.items()), 1):
            if sequence <= 2:
                disposition, owner, action = values[:3]
                refs_json = json.dumps(sorted(values[3]), separators=(",", ":"))
                decision_sequence = sequence
            else:
                disposition, owner, action = "pending", "unassigned", "review"
                refs_json = "[]"
                decision_sequence = 0
            connection.execute(
                "INSERT INTO contract_state VALUES (?, ?, ?, ?, ?, ?)",
                (
                    contract_id,
                    disposition,
                    owner,
                    action,
                    refs_json,
                    decision_sequence,
                ),
            )
        for sequence, contract_id in enumerate(sorted(DECISIONS)[:2], 1):
            disposition, owner, action, refs = DECISIONS[contract_id]
            connection.execute(
                "INSERT INTO closeout_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sequence,
                    REVIEW_ID,
                    contract_id,
                    disposition,
                    owner,
                    action,
                    json.dumps(sorted(refs), separators=(",", ":")),
                    f"2026-08-19T09:0{sequence}:00Z",
                ),
            )
        connection.execute(
            "INSERT INTO review_journal VALUES (?, 'prepared', 2, ?, NULL, ?)",
            (REVIEW_ID, checkpoint, "2026-08-19T09:02:00Z"),
        )
        connection.commit()
        connection.execute("VACUUM")


def run(root: Path, *arguments: str) -> None:
    completed = subprocess.run(
        [sys.executable, "closeoutctl.py", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)


def build_reference() -> None:
    REFERENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="task-124-reference-") as name:
        root = Path(name) / "workspace"
        shutil.copytree(WORKSPACE, root)
        (root / "closeout_plan.json").write_text(
            json.dumps(plan(root), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (root / "closeout_handoff.md").write_text(
            """# Contract closeout recovery handoff

Review CLOSEOUT-2026-08-15-R1 resumed the interrupted two-row audit prefix and committed one local recovery transaction for all seven contracts. C-401 is ready_for_controller because signed event EV-401-LEGAL-CLEAR came after EV-401-LEGAL-HOLD and its acceptance, invoice, funds, and expired option gates are complete. The later legal clearance cures only C-401's earlier hold. C-406 is also ready_for_controller: signed EV-406-FUNDS-CURE controls over the older finance_draft EV-406-FUNDS-DRAFT, and the remaining gates are complete.

C-402 remains on hold with finance; EV-402-INVOICE says the final invoice is missing, so the next action is obtain_final_invoice. C-403 remains on hold with legal for active legal hold LH-88, with resolve_legal_hold as the next action even though finance gates are complete. C-404 remains on hold with contracts because its option ends after the review date; await_option_expiry is controlling. C-405 remains on hold with program because both the contract record and EV-405-ACCEPT show incomplete physical acceptance; complete_acceptance comes before its otherwise complete finance evidence. C-407 remains on hold with finance because EV-407-FUNDS leaves a residual obligation; complete_deobligation is required.

The controller verified the source checkpoint, sequence-ordered audit, one transaction, and an idempotent semantic replay. This handoff and local stage receipt are internal proposals pending controller approval. No contract was closed, no payment or funds release occurred, nobody was contacted or notified, and no external action was executed.
""",
            encoding="utf-8",
        )
        run(root, "preview", "closeout_plan.json")
        run(root, "apply", "closeout_plan.json")
        run(root, "replay", "closeout_plan.json")
        run(root, "verify")
        run(root, "stage", "closeout_plan.json")
        run(root, "stage", "closeout_plan.json")
        for artifact in (
            "closeout.db",
            "closeout_plan.json",
            "closeout_verification.json",
            "closeout_stage_receipt.json",
            "closeout_handoff.md",
        ):
            shutil.copy2(root / artifact, REFERENCE / artifact)


def main() -> None:
    create_initial_database(WORKSPACE / "closeout.db")
    build_reference()


if __name__ == "__main__":
    main()
