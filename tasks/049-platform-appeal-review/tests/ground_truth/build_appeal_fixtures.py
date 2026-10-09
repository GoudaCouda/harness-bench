#!/usr/bin/env python3
"""Rebuild task049's interrupted seed database and hidden reference closure."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
SEED = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
DB = SEED / "state/appeals.db"


def pending() -> dict[str, object]:
    return {
        "status": "pending_review",
        "decision": None,
        "final_action": None,
        "policy_basis": None,
        "confidence": None,
        "explanation_sha256": None,
        "redaction_count": 0,
    }


def build_database() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.unlink(missing_ok=True)
    with sqlite3.connect(DB) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE appeal_queue(
              case_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              decision TEXT,
              final_action TEXT,
              policy_basis TEXT,
              confidence TEXT,
              explanation_sha256 TEXT,
              redaction_count INTEGER NOT NULL DEFAULT 0,
              production_action_executed INTEGER NOT NULL DEFAULT 0,
              reporter_contacted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY,
              source_checkpoint TEXT NOT NULL,
              semantic_digest TEXT NOT NULL,
              status TEXT NOT NULL,
              staged INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE recovery_journal(
              recovery_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              before_json TEXT NOT NULL,
              restored INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(recovery_id,case_id)
            );
            CREATE TABLE review_receipts(
              recovery_id TEXT PRIMARY KEY,
              queue_id TEXT NOT NULL,
              status TEXT NOT NULL,
              production_action_executed INTEGER NOT NULL DEFAULT 0,
              reporter_contacted INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        connection.executemany(
            "INSERT INTO metadata(key,value) VALUES(?,?)",
            (("queue_id", "APPEALS-20260308-AM"), ("revision", "31")),
        )
        for number in range(1, 8):
            case_id = f"A-{number:02d}"
            row = pending()
            if case_id == "A-01":
                row.update({
                    "status": "partially_applied",
                    "decision": "overturn",
                    "final_action": "restore",
                    "policy_basis": "SAFE-1",
                    "confidence": "low",
                })
            connection.execute(
                "INSERT INTO appeal_queue(case_id,status,decision,final_action,policy_basis,"
                "confidence,explanation_sha256,redaction_count) VALUES(?,?,?,?,?,?,?,?)",
                (case_id, *(row[key] for key in (
                    "status", "decision", "final_action", "policy_basis", "confidence",
                    "explanation_sha256", "redaction_count",
                ))),
            )
        connection.execute(
            "INSERT INTO recovery_journal(recovery_id,case_id,before_json,restored) VALUES(?,?,?,0)",
            ("APPEAL-INTERRUPTED-20260307", "A-01", json.dumps(pending(), sort_keys=True)),
        )
        connection.commit()
        connection.execute("VACUUM")


def build_reference() -> None:
    with tempfile.TemporaryDirectory(prefix="task049-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(SEED, workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("appeal_decisions.csv", "explanations.md", "redaction_audit.csv"):
            shutil.copy2(REFERENCE / name, workspace / name)
        environment = {**os.environ, "HB_WORKSPACE": str(workspace), "PYTHONDONTWRITEBYTECODE": "1"}
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", str(workspace / "appealctl.py"), command],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
        for relative in (
            ".appeal_preview.json", "state/appeals.db", "state/verification.json",
            "state/review_receipt.json", "state/replay_report.json",
        ):
            source = workspace / relative
            target = REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


if __name__ == "__main__":
    build_database()
    build_reference()
