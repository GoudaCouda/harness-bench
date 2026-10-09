from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools/task_maintenance"


def _module():
    sys.path.insert(0, str(TOOL_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "validate_public_leakage_tested",
            TOOL_DIR / "validate_public_leakage.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(TOOL_DIR))


def test_complete_plan_constructors_are_public_answer_leakage(tmp_path: Path) -> None:
    task = tmp_path / "127-example"
    workspace = task / "workspace"
    workspace.mkdir(parents=True)
    controller = workspace / "controller.py"
    controller.write_text(
        """
def target_plan(facts):
    return {"decisions": facts["decisions"], "recovery_id": "R-1"}

def _derived():
    return {"plan": target_plan({"decisions": []}), "raw": []}
""".lstrip(),
        encoding="utf-8",
    )

    findings = _module().public_python_findings(task, controller)

    assert any(":target_plan:" in finding for finding in findings)
    assert any(":_derived:" in finding and "['plan']" in finding for finding in findings)


def test_candidate_first_field_validator_is_not_flagged(tmp_path: Path) -> None:
    task = tmp_path / "143-example"
    workspace = task / "workspace"
    workspace.mkdir(parents=True)
    controller = workspace / "controller.py"
    controller.write_text(
        """
def validate_candidate(candidate, policy):
    problems = []
    for row in candidate.get("decisions", []):
        if row.get("action") not in policy["allowed_actions"]:
            problems.append({"object_id": row.get("id"), "fields": ["action"]})
    return problems
""".lstrip(),
        encoding="utf-8",
    )

    assert _module().public_python_findings(task, controller) == []


def test_private_spelling_does_not_hide_public_expected_plan(tmp_path: Path) -> None:
    task = tmp_path / "139-example"
    workspace = task / "workspace"
    workspace.mkdir(parents=True)
    controller = workspace / "controller.py"
    controller.write_text(
        """
def _expected_plan():
    plan = {"decisions": [{"id": "LOT-1", "action": "hold"}]}
    return plan
""".lstrip(),
        encoding="utf-8",
    )

    findings = _module().public_python_findings(task, controller)

    assert any(":_expected_plan:" in finding for finding in findings)


def test_derived_answer_returned_through_local_variable_is_flagged(
    tmp_path: Path,
) -> None:
    task = tmp_path / "199-example"
    workspace = task / "workspace"
    workspace.mkdir(parents=True)
    controller = workspace / "controller.py"
    controller.write_text(
        """
def derive_recovery(facts):
    result = {"decisions": facts["rows"], "final_rows": []}
    return result
""".lstrip(),
        encoding="utf-8",
    )

    findings = _module().public_python_findings(task, controller)

    assert any(":derive_recovery:" in finding for finding in findings)
