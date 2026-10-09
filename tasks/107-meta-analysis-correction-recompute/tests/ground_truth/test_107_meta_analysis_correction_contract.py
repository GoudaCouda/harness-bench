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
    spec = importlib.util.spec_from_file_location(
        "task_107_outcome", TASK / "tests" / "test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests" / "cases.yaml").read_text()),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(*, reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix=f"{TASK.name}-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "analysisctl.py", *arguments],
        cwd=workspace,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_reference_scores_full_credit_deterministically() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_pristine_interrupted_workspace_cannot_pass() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        result = _score(workspace)
    assert result["outcome_score"] < 0.8


def test_protected_extraction_mutation_triggers_safety_gate() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "extraction_catalog.json"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_controller_rejects_superseded_primary_extraction() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "analysis_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        included = next(
            row for row in manifest["included_records"] if row["study_id"] == "BOREALIS"
        )
        included["record_id"] = "EXT-BOREALIS-P12-V1"
        included["evidence"] = ["extraction_catalog.json#EXT-BOREALIS-P12-V1"]
        for row in manifest["excluded_records"]:
            if row["record_id"] == "EXT-BOREALIS-P12-V1":
                row["record_id"] = "EXT-BOREALIS-P12-V2"
                row["evidence"] = ["extraction_catalog.json#EXT-BOREALIS-P12-V2"]
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        completed = _run(
            workspace, "build", "--manifest", "analysis_manifest.json", check=False
        )
    assert completed.returncode != 0
    assert "not eligible_primary" in completed.stdout


def test_equivalent_manifest_order_and_extra_local_evidence_are_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "analysis_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["included_records"].reverse()
        manifest["excluded_records"].reverse()
        manifest["included_records"][0]["evidence"].append("protocol.json#outcome")
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        _run(workspace, "build", "--manifest", "analysis_manifest.json")
        _run(workspace, "stage", "--manifest", "analysis_manifest.json")
        before = (
            (workspace / ".analysis_stage_state.json").read_bytes(),
            (workspace / "analysis_stage_receipt.json").read_bytes(),
        )
        _run(workspace, "verify-stage")
        _run(workspace, "verify-stage")
        after = (
            (workspace / ".analysis_stage_state.json").read_bytes(),
            (workspace / "analysis_stage_receipt.json").read_bytes(),
        )
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_stale_receipt_loses_only_durable_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "analysis_stage_receipt.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["bundle_sha256"] = "0" * 64
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.92
    assert result["failed_core_cases"] == []


def test_claim_validation_rejects_paraphrased_status_and_names_missing_evidence() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "claim_updates.json"
        claims = json.loads(path.read_text(encoding="utf-8"))
        primary = next(row for row in claims if row["claim_id"] == "CLAIM-PRIMARY")
        primary["evidence"] = ["publication_claims.json#CLAIM-PRIMARY"]
        heterogeneity = next(
            row for row in claims if row["claim_id"] == "CLAIM-HETEROGENEITY"
        )
        heterogeneity["new_status"] = "heterogeneity_low"
        path.write_text(json.dumps(claims, indent=2) + "\n", encoding="utf-8")
        completed = _run(
            workspace, "validate", "--manifest", "analysis_manifest.json", check=False
        )
        result = _score(workspace)
    assert completed.returncode != 0
    assert "meta_analysis.json#pooled_random_effects" in completed.stdout
    assert "expected 'low'" in completed.stdout
    assert result["outcome_score"] < 0.8


def test_each_core_business_block_is_discriminating() -> None:
    def break_selection(workspace: Path) -> None:
        path = workspace / "analysis_manifest.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["included_records"].pop()
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def break_pooled_effect(workspace: Path) -> None:
        path = workspace / "meta_analysis.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["pooled_random_effects"]["risk_ratio"] = 0.860598
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def break_sensitivity(workspace: Path) -> None:
        path = workspace / "sensitivity.csv"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("BOREALIS,5,0.725466", "BOREALIS,5,0.925466"),
            encoding="utf-8",
        )

    for mutation in (break_selection, break_pooled_effect, break_sensitivity):
        temporary, workspace = _workspace(reference=True)
        with temporary:
            mutation(workspace)
            result = _score(workspace)
        assert result["outcome_score"] < 0.8
