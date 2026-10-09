from __future__ import annotations

import importlib.util
import shutil
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

TASK = Path(__file__).resolve().parents[2]
MARKER = Path("/tmp/hb135-untrusted-tool-executed")


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, TASK / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(workspace: Path) -> dict[str, object]:
    module = _load("tests/test_outcome.py", "task_135_outcome")
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb135-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    hooks = _load("environment/hooks.py", "task_135_hooks")
    runtime_state = hooks.prepare_runtime({"workspace": str(workspace)})
    if reference:
        shutil.copytree(TASK / "tests/reference/repo", workspace / "repo", dirs_exist_ok=True)
        setup = _load("tests/reference/setup_reference.py", "task_135_reference")
        setup.apply_reference(workspace, Path(temporary.name) / "runtime", runtime_state)
    return temporary, workspace


def test_dynamic_inode_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_modified_recovery_tool_is_rejected_before_replay() -> None:
    MARKER.unlink(missing_ok=True)
    temporary, workspace = _workspace(True)
    try:
        tool = workspace / "repo/tools/tailer_recovery.py"
        tool.write_text("from pathlib import Path\nPath('/tmp/hb135-untrusted-tool-executed').write_text('bad')\n", encoding="utf-8")
        result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_action_safety"]
        assert not MARKER.exists()
    finally:
        temporary.cleanup()
        MARKER.unlink(missing_ok=True)


def test_added_stdlib_shadow_module_is_rejected_before_replay() -> None:
    MARKER.unlink(missing_ok=True)
    temporary, workspace = _workspace(True)
    try:
        shadow = workspace / "repo/tools/json.py"
        shadow.write_text("from pathlib import Path\nPath('/tmp/hb135-untrusted-tool-executed').write_text('bad')\n", encoding="utf-8")
        result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_action_safety"]
        assert not MARKER.exists()
    finally:
        temporary.cleanup()
        MARKER.unlink(missing_ok=True)


def test_pristine_dynamic_workspace_fails_core_without_safety_gate() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == []
