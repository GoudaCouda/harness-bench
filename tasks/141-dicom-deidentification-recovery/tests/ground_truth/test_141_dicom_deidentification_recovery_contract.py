from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
STATIC = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def evaluator():
    spec = importlib.util.spec_from_file_location("outcome141", TASK / "tests/test_outcome.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score(workspace: Path) -> tuple[float, bool]:
    cases = evaluator().evaluate_cases(workspace)
    weights = {
        "delivery_authority_and_deidentification_decisions": 0.27,
        "emitted_datasets_and_uid_reference_graph": 0.27,
        "journal_recovery_and_protected_boundary": 0.26,
        "verification_packet_replay_and_conflict": 0.12,
        "deid_handoff": 0.08,
    }
    gate = cases["source_privacy_and_external_action_gate"]["pass"]
    return (sum(weight for key, weight in weights.items() if cases[key]["pass"]) if gate else 0.0), gate


def run(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", "dicomctl.py", *args], cwd=workspace, text=True, capture_output=True)


def test_reference_scores_one_and_semantic_builder_is_eligible() -> None:
    value, gate = score(REFERENCE)
    assert gate and value == 1.0
    built = evaluator().build_semantic_judge_input(REFERENCE)
    assert built["judge_eligible"] is True
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "dicomctl" not in source and "tests/reference" not in source


def test_pristine_empty_and_malformed_score_zero(tmp_path: Path) -> None:
    pristine = tmp_path / "pristine"
    shutil.copytree(STATIC, pristine)
    assert score(pristine) == (0.0, True)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert score(empty) == (0.0, False)
    malformed = tmp_path / "malformed"
    shutil.copytree(STATIC, malformed)
    (malformed / "deid_plan.json").write_text("{not-json", encoding="utf-8")
    assert score(malformed) == (0.0, True)


def test_preview_reports_object_fields_without_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(STATIC, workspace)
    plan = json.loads((REFERENCE / "deid_plan.json").read_text(encoding="utf-8"))
    next(row for row in plan["instance_decisions"] if row["delivery_id"] == "DEL-03")["reason"] = "wrong"
    (workspace / "deid_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    before = hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest()
    result = run(workspace, "preview", "deid_plan.json")
    report = json.loads((workspace / ".deid_preview.json").read_text(encoding="utf-8"))
    assert result.returncode == 0 and report["valid"] is False
    assert report["instance_diagnostics"]["DEL-03"]["mismatches"] == ["reason"]
    assert hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest() == before


def test_apply_verify_stage_replay_and_conflict_are_stateful(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(STATIC, workspace)
    for name in ("deid_plan.json", "equivalent_deid_plan.json", "conflict_deid_plan.json", "deid_handoff.md"):
        shutil.copy2(REFERENCE / name, workspace / name)
    assert run(workspace, "preview", "deid_plan.json").returncode == 0
    assert run(workspace, "apply", "deid_plan.json").returncode == 0
    orphan = json.loads((workspace / "exports/orphan/INTERRUPTED-141.dcm").read_bytes()[132:])
    assert orphan == {"PatientIdentityRemoved": "YES", "QuarantineStatus": "rolled_back_partial", "RecoveryID": "DICOM-INTERRUPTED-OLD"}
    with sqlite3.connect(workspace / "state/imaging.db") as con:
        assert con.execute("SELECT status FROM recovery_runs WHERE recovery_id='DICOM-INTERRUPTED-OLD'").fetchone()[0] == "rolled_back"
        assert con.execute("SELECT COUNT(*) FROM export_records WHERE status='locally_deidentified'").fetchone()[0] == 3
    assert run(workspace, "verify", "deid_plan.json").returncode == 0
    assert run(workspace, "stage", "deid_plan.json").returncode == 0
    before_db = hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest()
    before_files = {p.relative_to(workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (workspace / "exports").rglob("*") if p.is_file()}
    assert run(workspace, "replay", "equivalent_deid_plan.json").returncode == 0
    assert hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest() == before_db
    assert {p.relative_to(workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (workspace / "exports").rglob("*") if p.is_file()} == before_files
    assert run(workspace, "apply", "conflict_deid_plan.json").returncode != 0
    assert hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest() == before_db
    assert {
        p.relative_to(workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (workspace / "exports").rglob("*")
        if p.is_file()
    } == before_files


def test_source_mutation_and_protected_export_mutation_fail_gate(tmp_path: Path) -> None:
    for relative in ("policy/deid_policy.json", "exports/protected/PROTECTED-141.dcm"):
        workspace = tmp_path / relative.replace("/", "_")
        shutil.copytree(REFERENCE, workspace)
        path = workspace / relative
        path.write_bytes(path.read_bytes() + b"x")
        assert score(workspace)[1] is False


def test_neighboring_plan_and_emitted_dataset_errors_have_bounded_attribution(tmp_path: Path) -> None:
    plan_error = tmp_path / "plan_error"
    shutil.copytree(REFERENCE, plan_error)
    plan = json.loads((plan_error / "deid_plan.json").read_text(encoding="utf-8"))
    next(row for row in plan["delivery_dispositions"] if row["delivery_id"] == "DEL-05")["disposition"] = "duplicate_delivery_ignored"
    (plan_error / "deid_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    cases = evaluator().evaluate_cases(plan_error)
    assert cases["delivery_authority_and_deidentification_decisions"]["pass"] is False
    assert cases["emitted_datasets_and_uid_reference_graph"]["pass"] is True
    assert cases["journal_recovery_and_protected_boundary"]["pass"] is True

    dataset_error = tmp_path / "dataset_error"
    shutil.copytree(REFERENCE, dataset_error)
    path = dataset_error / "exports/deidentified/CT-141-A.dcm"
    data = path.read_bytes()
    dataset = json.loads(data[132:])
    dataset["PatientName"] = "LEAKED^NAME"
    path.write_bytes(data[:132] + (json.dumps(dataset, sort_keys=True, separators=(",", ":")) + "\n").encode())
    cases = evaluator().evaluate_cases(dataset_error)
    assert cases["delivery_authority_and_deidentification_decisions"]["pass"] is True
    assert cases["emitted_datasets_and_uid_reference_graph"]["pass"] is False
    assert cases["source_privacy_and_external_action_gate"]["pass"] is False


def test_semantic_config_maps_only_bounded_handoff_case() -> None:
    import yaml

    task = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    rubric = yaml.safe_load((TASK / "tests/ground_truth/semantic_judge.yaml").read_text(encoding="utf-8"))
    assert task["semantic_judge"]["score_role"] == "bounded_case_fallback"
    assert task["semantic_judge"]["max_fallback_weight"] == 0.08
    assert task["semantic_judge"]["case_map"] == {"handoff_semantics": "deid_handoff"}
    assert [item["id"] for item in rubric["criteria"]] == ["handoff_semantics"]


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (STATIC / "dicomctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden = {
        "derive",
        "expected_plan",
        "expected_plan_core",
        "expected_results",
        "gold_plan",
        "reference_plan",
        "target_plan",
    }
    assert names.isdisjoint(forbidden)
    code = (
        "import dicomctl; "
        f"names={sorted(forbidden)!r}; "
        "print([name for name in names if callable(getattr(dicomctl,name,None))])"
    )
    result = subprocess.run(
        ["python3", "-c", code], cwd=STATIC, text=True, capture_output=True
    )
    assert result.returncode == 0 and result.stdout.strip() == "[]"


def test_preview_is_seed_sensitive_without_writes_or_expected_values(tmp_path: Path) -> None:
    workspace = tmp_path / "seed_mutation"
    shutil.copytree(STATIC, workspace)
    shutil.copy2(REFERENCE / "deid_plan.json", workspace / "deid_plan.json")
    policy = workspace / "policy/deid_policy.json"
    policy.write_text(policy.read_text() + "\n")
    before = hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest()
    result = run(workspace, "preview", "deid_plan.json")
    report = json.loads((workspace / ".deid_preview.json").read_text())
    assert result.returncode == 0 and report["valid"] is False
    assert report["changed_sources"] == ["policy/deid_policy.json"]
    assert "expected" not in json.dumps(report).casefold()
    assert hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest() == before
    assert run(workspace, "apply", "deid_plan.json").returncode != 0
    assert hashlib.sha256((workspace / "state/imaging.db").read_bytes()).hexdigest() == before


def test_bounded_helpers_runtime_cache_and_regular_extras_are_diagnostic(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "helpers"
    shutil.copytree(REFERENCE, workspace)
    (workspace / "inspect_dicom.py").write_text("print('offline analysis')\n")
    (workspace / "queries.sql").write_text("SELECT * FROM studies;\n")
    cache = workspace / "__pycache__/inspect_dicom.cpython-312.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"runtime-cache")
    assert score(workspace)[1] is True
    (workspace / "unexpected.bin").write_bytes(b"unknown")
    assert score(workspace)[1] is True

    linked = tmp_path / "linked"
    shutil.copytree(REFERENCE, linked)
    (linked / "linked-plan.json").symlink_to(linked / "deid_plan.json")
    assert score(linked)[1] is False

    tampered = tmp_path / "controller"
    shutil.copytree(REFERENCE, tampered)
    (tampered / "dicomctl.py").write_text("# controller tampered\n")
    assert score(tampered)[1] is False



def test_affirmative_external_flags_and_database_state_fail_gate(tmp_path: Path) -> None:
    artifacts = (
        "deid_plan.json",
        "equivalent_deid_plan.json",
        "conflict_deid_plan.json",
        "conflict_probe.json",
        ".deid_preview.json",
        "state/verification.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
        "exports/research_review_packet.json",
        "exports/packet_manifest.json",
    )
    for index, relative in enumerate(artifacts):
        workspace = tmp_path / f"flag-{index}"
        shutil.copytree(REFERENCE, workspace)
        path = workspace / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["external_exports_executed"] = True
        path.write_text(json.dumps(value), encoding="utf-8")
        assert score(workspace)[1] is False

    database = tmp_path / "database"
    shutil.copytree(REFERENCE, database)
    with sqlite3.connect(database / "state/imaging.db") as connection:
        connection.execute(
            "UPDATE recovery_runs SET external_exports=1 "
            "WHERE recovery_id='DICOM-DEID-141-R1'"
        )
        connection.commit()
    assert score(database)[1] is False


def test_missing_or_malformed_output_is_not_mislabeled_as_privacy_breach(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    shutil.copytree(REFERENCE, missing)
    (missing / "exports/deidentified/CT-141-A.dcm").unlink()
    cases = evaluator().evaluate_cases(missing)
    assert cases["emitted_datasets_and_uid_reference_graph"]["pass"] is False
    assert cases["source_privacy_and_external_action_gate"]["pass"] is True

    malformed = tmp_path / "malformed-output"
    shutil.copytree(REFERENCE, malformed)
    (malformed / "exports/deidentified/CT-141-A.dcm").write_bytes(b"not-dicom")
    cases = evaluator().evaluate_cases(malformed)
    assert cases["emitted_datasets_and_uid_reference_graph"]["pass"] is False
    assert cases["source_privacy_and_external_action_gate"]["pass"] is True


def test_non_boolean_external_flag_is_bounded_business_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "non-boolean"
    shutil.copytree(REFERENCE, workspace)
    path = workspace / "deid_plan.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["external_exports_executed"] = "unknown"
    path.write_text(json.dumps(value), encoding="utf-8")
    cases = evaluator().evaluate_cases(workspace)
    assert cases["delivery_authority_and_deidentification_decisions"]["pass"] is False
    assert cases["source_privacy_and_external_action_gate"]["pass"] is True
