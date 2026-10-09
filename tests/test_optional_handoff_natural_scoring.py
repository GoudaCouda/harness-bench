from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from common import score_task_workspace  # noqa: E402


OPTIONAL_HANDOFFS = (
    ("025-dependency-upgrade-compat", "repo/UPGRADE_NOTES.md", 0.80),
    ("030-sql-query-report", "quarterly_revenue_brief.md", 0.88),
    ("055-financial-close-reconciliation", "close/close_memo.md", 0.90),
    ("062-privacy-dsar-intake-review", "privacy_operations_handoff.md", 0.92),
)


@pytest.mark.parametrize(("task_id", "optional_path", "expected"), OPTIONAL_HANDOFFS)
def test_missing_optional_handoff_keeps_its_natural_business_score(
    task_id: str,
    optional_path: str,
    expected: float,
) -> None:
    task = ROOT / "tasks" / task_id
    metadata = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    assert optional_path not in metadata["required_artifacts"]
    assert any(
        optional_path == rule.rstrip("/")
        or optional_path.startswith(rule.rstrip("/") + "/")
        for rule in metadata["mutation_contract"]["allowed_created"]
    )

    with tempfile.TemporaryDirectory(prefix=f"hb-optional-{task_id[:3]}-") as tmp:
        workspace = Path(tmp) / "workspace"
        shutil.copytree(task / "workspace", workspace)
        shutil.copytree(task / "tests" / "reference", workspace, dirs_exist_ok=True)
        (workspace / optional_path).unlink()
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == expected
    assert result["task_success"] is True
    assert result["failed_gates"] == []
    assert result["required_artifact_contract"]["complete"] is True
