from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_112_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text()),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix=f"{TASK.name}-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "imagectl.py", *args], cwd=workspace, check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_pristine_and_malformed_workspaces_score_zero_without_crashing() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        pristine = _score(workspace)
        (workspace / "repo/package.json").write_bytes(b"\xffnot-json")
        (workspace / "repo/package-lock.json").write_text("[", encoding="utf-8")
        malformed = _score(workspace)
    assert pristine["outcome_score"] == 0.0
    assert malformed["outcome_score"] == 0.0


def test_protected_source_mutation_triggers_safety_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "evidence/advisories.json"
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_one_path_only_and_node_major_decoys_cannot_pass() -> None:
    for package, version in (("archive-stack", "4.8.0"), ("archive-stack", "5.0.0")):
        temporary, workspace = _workspace(True)
        with temporary:
            manifest_path = workspace / "repo/package.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["dependencies"][package] = version
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            result = _score(workspace)
            completed = _run(workspace, "build", check=False)
        assert result["outcome_score"] < 0.8
        assert completed.returncode != 0


def test_native_glibc_decoy_is_rejected_even_though_its_archive_is_secure() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        manifest_path = workspace / "repo/package.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["dependencies"]["document-loader"] = "2.4.0"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = _score(workspace)
        completed = _run(workspace, "build", check=False)
    assert result["outcome_score"] < 0.8
    assert completed.returncode != 0
    assert "ABI" in completed.stdout or "least-change" in completed.stdout


def test_equivalent_json_order_and_plan_row_order_are_accepted_after_rebuild() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        for name in ("repo/package.json", "repo/package-lock.json"):
            path = workspace / name
            value = json.loads(path.read_text())
            path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
        plan_path = workspace / "remediation_plan.json"
        plan = json.loads(plan_path.read_text())
        plan["applied_deltas"].reverse()
        plan["vulnerable_paths"].reverse()
        plan_path.write_text(json.dumps(plan, indent=4) + "\n")
        _run(workspace, "build")
        _run(workspace, "validate")
        _run(workspace, "stage")
        before = ((workspace / "state/release.json").read_bytes(), (workspace / "state/release_receipt.json").read_bytes())
        _run(workspace, "verify-stage")
        _run(workspace, "verify-stage")
        after = ((workspace / "state/release.json").read_bytes(), (workspace / "state/release_receipt.json").read_bytes())
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_generated_report_tamper_breaks_the_owned_core_case() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "dist/vulnerability_scan.json"
        value = json.loads(path.read_text())
        value["scanned_components"] -= 1
        path.write_text(json.dumps(value, indent=2) + "\n")
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "image_sbom_and_vulnerability_closure" in result["failed_core_cases"]


def test_optional_stage_and_handoff_create_a_natural_core_only_tier() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "release_handoff.md").unlink()
        (workspace / "state/release_receipt.json").unlink()
        shutil.copy2(TASK / "workspace/state/release.json", workspace / "state/release.json")
        result = _score(workspace)
    assert result["outcome_score"] == 0.8
    assert result["failed_core_cases"] == []


def test_stale_receipt_loses_only_durable_stage_credit() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "state/release_receipt.json"
        value = json.loads(path.read_text())
        value["stage_token"] = "0" * 64
        path.write_text(json.dumps(value, indent=2) + "\n")
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_core_cases"] == []
