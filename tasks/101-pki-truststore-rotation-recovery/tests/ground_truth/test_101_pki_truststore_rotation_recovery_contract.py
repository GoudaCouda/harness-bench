from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_controller_rejects_initial_state_and_accepts_reference(tmp_path: Path) -> None:
    task = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    subprocess.run(["cp", "-a", str(task / "workspace"), str(workspace)], check=True)
    initial = subprocess.run(
        [sys.executable, "pki_ctl.py", "verify"],
        cwd=workspace,
        text=True,
        capture_output=True,
    )
    assert initial.returncode == 2
    plan = {
        "actions": [
            {
                "service_id": "billing-api",
                "presented_chain": ["leaf-api-v2", "int-b"],
                "truststore_add": ["root-2026"],
                "truststore_remove": [],
            }
        ]
    }
    (workspace / "rotation_plan.json").write_text(json.dumps(plan) + "\n")
    first = subprocess.run(
        [sys.executable, "pki_ctl.py", "apply", "rotation_plan.json"],
        cwd=workspace,
        check=True,
        text=True,
        capture_output=True,
    )
    retry = subprocess.run(
        [sys.executable, "pki_ctl.py", "apply", "rotation_plan.json"],
        cwd=workspace,
        check=True,
        text=True,
        capture_output=True,
    )
    final = subprocess.run(
        [sys.executable, "pki_ctl.py", "verify"],
        cwd=workspace,
        check=True,
        text=True,
        capture_output=True,
    )
    assert '"status": "applied"' in first.stdout
    assert '"status": "idempotent"' in retry.stdout
    assert '"status": "pass"' in final.stdout
    assert len((workspace / "pki_audit.jsonl").read_text().splitlines()) == 1


def _evaluate(task: Path, workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task101_outcome", task / "tests/test_outcome.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.evaluate_cases(workspace)


def _reference_workspace(task: Path, workspace: Path) -> None:
    shutil.copytree(task / "workspace", workspace)
    shutil.copytree(task / "tests/reference", workspace, dirs_exist_ok=True)


def test_reporting_fault_is_attributed_only_to_preservation(tmp_path: Path) -> None:
    task = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    _reference_workspace(task, workspace)
    state_path = workspace / "pki_state.json"
    state = json.loads(state_path.read_text())
    state["services"]["reporting"]["presented_chain"] = ["leaf-worker-v1", "int-a"]
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    subprocess.run(
        [sys.executable, "pki_ctl.py", "verify"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    result = _evaluate(task, workspace)
    assert result["billing_chain_and_trust_rotation"]["pass"]
    assert not result["overlap_and_unrelated_service_preservation"]["pass"]


def test_billing_fault_is_attributed_only_to_billing(tmp_path: Path) -> None:
    task = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    _reference_workspace(task, workspace)
    state_path = workspace / "pki_state.json"
    state = json.loads(state_path.read_text())
    state["services"]["billing-api"]["presented_chain"] = ["leaf-api-v1", "int-a"]
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    subprocess.run(
        [sys.executable, "pki_ctl.py", "verify"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    result = _evaluate(task, workspace)
    assert not result["billing_chain_and_trust_rotation"]["pass"]
    assert result["overlap_and_unrelated_service_preservation"]["pass"]
