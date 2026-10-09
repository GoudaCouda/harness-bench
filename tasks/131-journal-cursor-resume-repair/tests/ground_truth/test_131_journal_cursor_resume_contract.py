from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

TASK = Path(__file__).resolve().parents[2]
HANDOFF = """# Recovery handoff

The applied_events ledger was authoritative while consumer_cursor was stale after the split durable commit. We inspected both immutable JSONL segments and SQLite, acknowledged the stale cursor, and preserved e104 as already applied. Duplicate e103 was ignored by the idempotency ledger; newly applied e105, e106, e107, and e108 exactly once. Before and after account balances and versions were checked, the cursor advanced to segment-00042.jsonl line 6 at e108, and PRAGMA integrity_check returned ok. A copied-state second recovery was a no-op with no new events. All work remained offline; no production deployment or external action occurred. Commands used journal_recovery.py inspect, recover --acknowledge-stale-cursor, and verify. The receipt records the crash boundary, journal end, duplicate delivery, and final account projection for the next operator.
"""


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_131_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb131-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    database = workspace / "repo/state/projection.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.executescript((workspace / "repo/seed/initial_state.sql").read_text(encoding="utf-8"))
    if reference:
        subprocess.run(
            ["python3", "tools/journal_recovery.py", "recover", "--database", "state/projection.db", "--acknowledge-stale-cursor", "--receipt", "out/recovery_receipt.json"],
            cwd=workspace / "repo",
            check=True,
            text=True,
            capture_output=True,
        )
        (workspace / "repo/RECOVERY_HANDOFF.md").write_text(HANDOFF, encoding="utf-8")
    return temporary, workspace


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_pristine_and_malformed_database_fail_closed() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "repo/state/projection.db").write_bytes(b"not sqlite")
        assert _score(workspace)["outcome_score"] == 0.0


def test_modified_recovery_tool_is_rejected_before_oracle_replay() -> None:
    marker = Path("/tmp/hb131-untrusted-tool-executed")
    marker.unlink(missing_ok=True)
    temporary, workspace = _workspace(True)
    try:
        tool = workspace / "repo/tools/journal_recovery.py"
        tool.write_text(
            "from pathlib import Path\nPath('/tmp/hb131-untrusted-tool-executed').write_text('bad')\n",
            encoding="utf-8",
        )
        result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_action_safety"]
        assert not marker.exists()
    finally:
        temporary.cleanup()
        marker.unlink(missing_ok=True)


def test_stale_terminal_cursor_loses_ledger_and_replay_credit_not_safety() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "repo/state/projection.db") as connection:
            connection.execute(
                "UPDATE consumer_cursor SET segment='segment-00041.jsonl', line_no=3, event_id='e102' WHERE consumer='account-projection'"
            )
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.55
    assert result["failed_core_cases"] == ["ledger_and_checkpoint", "no_op_replay_and_receipt"]
    assert result["failed_gates"] == []
