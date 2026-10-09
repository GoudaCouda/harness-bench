from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]


def _load_outcome():
    path = TASK / "tests" / "test_outcome.py"
    spec = importlib.util.spec_from_file_location("task_216_outcome", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verification_idempotence_does_not_repeat_decision_penalty(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
    path = workspace / "state" / "audit_log.json"
    log = json.loads(path.read_text(encoding="utf-8"))
    log["decisions"][0]["decision"] = "malformed"
    path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")

    checks = _load_outcome()._executable_checks(workspace)
    assert checks["executable_decision_cohort"]["pass"] is False
    assert checks["executable_idempotence"]["pass"] is True
