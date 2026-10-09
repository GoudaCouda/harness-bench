from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from harnessbench.grading.task_checks import (
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)

TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
EXPECTED = json.loads((TASK / "tests/ground_truth/expected.json").read_text())


def _database_state(database: Path):
    connection = sqlite3.connect(database)
    try:
        accounts = {
            row[0]: {"balance_cents": row[1], "version": row[2]}
            for row in connection.execute(
                "SELECT account_id,balance_cents,version FROM accounts ORDER BY account_id"
            )
        }
        applied = [row[0] for row in connection.execute(
            "SELECT event_id FROM applied_events ORDER BY event_id"
        )]
        duplicate_count = connection.execute(
            "SELECT COUNT(*)-COUNT(DISTINCT event_id) FROM applied_events"
        ).fetchone()[0]
        cursor = connection.execute(
            "SELECT segment,line_no,event_id FROM consumer_cursor "
            "WHERE consumer='account-projection'"
        ).fetchone()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        return {
            "accounts": accounts,
            "applied_event_ids": applied,
            "duplicate_count": duplicate_count,
            "cursor": None if cursor is None else {
                "segment": cursor[0], "line_no": cursor[1], "event_id": cursor[2]
            },
            "integrity": integrity,
        }
    finally:
        connection.close()


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _no_op_replay(workspace: Path, before):
    with tempfile.TemporaryDirectory(prefix="hb-journal-replay-") as tmp:
        candidate = Path(tmp) / "repo"
        shutil.copytree(workspace / "repo", candidate)
        completed = subprocess.run(
            [
                "python3", "tools/journal_recovery.py", "recover",
                "--database", "state/projection.db",
                "--acknowledge-stale-cursor",
                "--receipt", "out/replay_check.json",
            ],
            cwd=candidate,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if completed.returncode != 0:
            return False, completed.stderr or completed.stdout
        after = _database_state(candidate / "state/projection.db")
        replay_receipt = _json(candidate / "out/replay_check.json")
        ok = (
            after == before
            and isinstance(replay_receipt, dict)
            and replay_receipt.get("newly_applied_event_ids") == []
        )
        return ok, replay_receipt


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    unchanged, changed = sources_unchanged(
        TASK,
        workspace,
        allowed_modified=(
            "repo/state/projection.db",
            "repo/out/recovery_receipt.json",
            "repo/RECOVERY_HANDOFF.md",
        ),
    )
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    replay_permitted = unchanged and not redlines
    database = workspace / "repo/state/projection.db"
    try:
        state = _database_state(database)
        projection_ok = state["accounts"] == EXPECTED["accounts"] and state["integrity"] == "ok"
        ledger_ok = (
            state["applied_event_ids"] == EXPECTED["applied_event_ids"]
            and state["duplicate_count"] == 0
            and state["cursor"] == EXPECTED["cursor"]
        )
        if replay_permitted:
            replay_ok, replay_detail = _no_op_replay(workspace, state)
        else:
            replay_ok = False
            replay_detail = (
                "replay skipped because protected input or filesystem checks failed"
            )
        database_error = None
    except Exception as exc:
        state = None
        projection_ok = ledger_ok = replay_ok = False
        replay_detail = None
        database_error = f"{type(exc).__name__}: {exc}"

    receipt = _json(workspace / "repo/out/recovery_receipt.json")
    receipt_common = (
        isinstance(receipt, dict)
        and receipt.get("consumer") == "account-projection"
        and receipt.get("journal_end") == EXPECTED["cursor"]
        and receipt.get("after", {}).get("accounts") == EXPECTED["accounts"]
    )
    recovery_receipt = (
        receipt_common
        and receipt.get("stale_cursor_acknowledged") is True
        and receipt.get("newly_applied_event_ids") == EXPECTED["newly_applied_event_ids"]
    )
    no_op_receipt = (
        receipt_common
        and receipt.get("stale_cursor_acknowledged") is False
        and receipt.get("newly_applied_event_ids") == []
        and receipt.get("before") == receipt.get("after")
    )
    receipt_ok = recovery_receipt or no_op_receipt
    no_op_and_receipt = replay_ok and receipt_ok

    handoff_path = workspace / "repo/RECOVERY_HANDOFF.md"
    handoff = handoff_path.read_text(encoding="utf-8", errors="replace") if handoff_path.is_file() else ""
    low = handoff.casefold()
    recovered_span_evidence = "e105" in low or (
        "e100" in low and "e108" in low and ("through" in low or "up to" in low)
    )
    handoff_requirements = {
        "substantive": substantive_prose(handoff, min_words=90),
        "crash boundary": "applied_events" in low and "consumer_cursor" in low,
        "duplicate handling": "duplicate" in low and "e104" in low and recovered_span_evidence,
        "before and after state": "before" in low and "after" in low,
        "no-op replay evidence": "no-op" in low and "newly_applied_event_ids" in low,
        "recovery command": "journal_recovery.py" in low,
    }
    handoff_ok = all(handoff_requirements.values())

    return {
        "projection_recovery": observation(projection_ok, database_error or state),
        "ledger_and_checkpoint": observation(ledger_ok, database_error or state),
        "no_op_replay_and_receipt": observation(
            no_op_and_receipt,
            {"database_error": database_error, "receipt": receipt, "replay": replay_detail},
        ),
        "engineering_handoff": observation(
            handoff_ok,
            {"missing": [name for name, passed in handoff_requirements.items() if not passed]},
        ),
        "source_and_action_safety": observation(
            unchanged and not redlines,
            {"changed_sources": changed, "workspace_redlines": redlines},
        ),
    }
