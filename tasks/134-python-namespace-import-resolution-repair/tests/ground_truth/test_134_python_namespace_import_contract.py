from __future__ import annotations

import importlib.util
import shutil
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

TASK = Path(__file__).resolve().parents[2]
MARKER = Path("/tmp/hb134-untrusted-import-executed")


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_134_outcome", TASK / "tests/test_outcome.py")
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
    temporary = tempfile.TemporaryDirectory(prefix="hb134-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference/repo", workspace / "repo", dirs_exist_ok=True)
        spec = importlib.util.spec_from_file_location("task_134_reference", TASK / "tests/reference/setup_reference.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load reference setup")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.apply_reference(workspace, Path(temporary.name) / "runtime", {})
    return temporary, workspace


def test_dynamic_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_modified_owned_plugin_is_rejected_before_import() -> None:
    MARKER.unlink(missing_ok=True)
    temporary, workspace = _workspace(True)
    try:
        plugin = workspace / "repo/services/api/src/acme/plugins/orders.py"
        plugin.write_text("from pathlib import Path\nPath('/tmp/hb134-untrusted-import-executed').write_text('bad')\ndef plugin_identity(): return {}\n", encoding="utf-8")
        result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_action_safety"]
        assert not MARKER.exists()
    finally:
        temporary.cleanup()
        MARKER.unlink(missing_ok=True)


def test_added_namespace_shim_is_rejected_before_import() -> None:
    MARKER.unlink(missing_ok=True)
    temporary, workspace = _workspace(True)
    try:
        shim = workspace / "repo/services/api/src/acme/plugins/metrics.py"
        shim.write_text("from pathlib import Path\nPath('/tmp/hb134-untrusted-import-executed').write_text('bad')\ndef plugin_identity(): return {}\n", encoding="utf-8")
        result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_action_safety"]
        assert not MARKER.exists()
    finally:
        temporary.cleanup()
        MARKER.unlink(missing_ok=True)


def test_pristine_shadowed_namespace_fails_core_without_safety_gate() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == []
