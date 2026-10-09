from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "task_021_outcome", TASK / "tests/test_outcome.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


@pytest.fixture()
def reference(tmp_path: Path) -> Path:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(TASK / "tests/reference", tmp_path, dirs_exist_ok=True)
    return tmp_path


def checks(path: Path) -> dict[str, object]:
    return MODULE.evaluate_cases(path)


def test_reference_passes(reference: Path) -> None:
    assert all(row["pass"] for row in checks(reference).values())


def test_reference_semantic_input_builder_uses_runner_contract(reference: Path) -> None:
    candidate = MODULE.build_semantic_judge_input(reference)
    assert candidate["artifact"] == "work/compliance_handoff.md"
    assert candidate["judge_eligible"] is True
    assert len(str(candidate["text"]).strip()) >= 1000


def test_untouched_has_no_reward(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    result = checks(tmp_path)
    assert not any(
        row["pass"]
        for name, row in result.items()
        if name != "safety_and_input_integrity"
    )


def test_latest_version_cannot_rewrite_prespecification(reference: Path) -> None:
    path = reference / "work/corrected_results.json"
    value = json.loads(path.read_text())
    value["outcomes"][0]["classification"] = "secondary"
    value["outcomes"][1]["classification"] = "primary_prespecified"
    path.write_text(json.dumps(value))
    assert not checks(reference)["outcome_and_arm_corrections"]["pass"]


def test_submitted_is_not_posted(reference: Path) -> None:
    path = reference / "work/corrected_results.json"
    value = json.loads(path.read_text())
    value["registry_status"].update(
        results_first_posted_date="2026-08-10", state="posted"
    )
    path.write_text(json.dumps(value))
    assert not checks(reference)["outcome_and_arm_corrections"]["pass"]


def test_arm_swap_fails(reference: Path) -> None:
    path = reference / "work/corrected_results.json"
    value = json.loads(path.read_text())
    value["arms"] = [
        {"arm_id": "A", "label": "Placebo"},
        {"arm_id": "B", "label": "LX-21"},
    ]
    path.write_text(json.dumps(value))
    assert not checks(reference)["outcome_and_arm_corrections"]["pass"]


def test_completed_count_cannot_replace_primary_population(reference: Path) -> None:
    path = reference / "work/corrected_results.json"
    value = json.loads(path.read_text())
    value["outcomes"][0]["groups"][0]["n"] = 56
    path.write_text(json.dumps(value))
    assert not checks(reference)["outcome_and_arm_corrections"]["pass"]


def test_randomized_count_cannot_replace_safety_population(reference: Path) -> None:
    path = reference / "work/corrected_results.json"
    value = json.loads(path.read_text())
    value["serious_adverse_events"]["denominator"] = {"A": 60, "B": 60}
    path.write_text(json.dumps(value))
    assert not checks(reference)["populations_and_events"]["pass"]


def test_missing_manuscript_correction_fails(reference: Path) -> None:
    path = reference / "work/discrepancy_ledger.json"
    value = json.loads(path.read_text())
    value["findings"] = [
        row for row in value["findings"] if row["finding_id"] != "F-07"
    ]
    path.write_text(json.dumps(value))
    assert not checks(reference)["populations_and_events"]["pass"]


def test_receipt_tamper_fails(reference: Path) -> None:
    path = reference / "work/correction_receipt.json"
    value = json.loads(path.read_text())
    value["receipt_sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    assert not checks(reference)["staged_receipt_replay"]["pass"]


def test_graph_and_ledger_order_irrelevant(reference: Path) -> None:
    for rel, field in (
        ("work/source_graph.json", "nodes"),
        ("work/discrepancy_ledger.json", "findings"),
        ("work/corrected_results.json", "outcomes"),
    ):
        path = reference / rel
        value = json.loads(path.read_text())
        value[field].reverse()
        path.write_text(json.dumps(value))
    assert all(row["pass"] for row in checks(reference).values())


def test_equivalent_relationship_actions_and_finding_ids_are_accepted(
    reference: Path,
) -> None:
    graph_path = reference / "work/source_graph.json"
    graph = json.loads(graph_path.read_text())
    for row in graph["nodes"]:
        row["relationship"] = f"dated role for {row['source_id']} is documented"
    graph_path.write_text(json.dumps(graph))

    ledger_path = reference / "work/discrepancy_ledger.json"
    ledger = json.loads(ledger_path.read_text())
    for index, row in enumerate(ledger["findings"], start=1):
        row["finding_id"] = f"ALT-{index:02d}"
        row["action"] = f"Apply the documented correction for {row['field']}"
        row["authority_ids"].reverse()
        if row["field"] == "prespecified_primary_claim":
            row["observed"] = "The proof describes Day 56 as prespecified"
            row["corrected"] = "Day 28 was prespecified; Day 56 remains post-hoc"
        elif row["field"] == "registry_posting_claim":
            row["observed"] = "The proof says results were posted on 2026-08-10"
            row["corrected"] = (
                "Submitted on 2026-08-10, still under QC, and not publicly posted"
            )
    ledger_path.write_text(json.dumps(ledger))

    results_path = reference / "work/corrected_results.json"
    results = json.loads(results_path.read_text())
    results["arms"].reverse()
    results["outcomes"].reverse()
    for outcome in results["outcomes"]:
        outcome["groups"].reverse()
    results_path.write_text(json.dumps(results, separators=(",", ":")))

    state_before = (reference / "state/correction_case.json").read_bytes()
    receipt_before = (reference / "work/correction_receipt.json").read_bytes()

    args = [
        "--graph",
        "work/source_graph.json",
        "--ledger",
        "work/discrepancy_ledger.json",
        "--results",
        "work/corrected_results.json",
    ]
    for command in ("stage", "replay"):
        subprocess.run(
            ["python3", "trialctl.py", command, *args],
            cwd=reference,
            check=True,
            capture_output=True,
            text=True,
        )
    assert (reference / "state/correction_case.json").read_bytes() == state_before
    assert (reference / "work/correction_receipt.json").read_bytes() == receipt_before
    assert all(row["pass"] for row in checks(reference).values())


def test_controller_validates_mutated_visible_seed_without_answer_export(
    tmp_path: Path,
) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(TASK / "tests/reference/work", tmp_path / "work", dirs_exist_ok=True)

    def rewrite(relative: str, transform) -> None:
        path = tmp_path / relative
        value = json.loads(path.read_text())
        transform(value)
        path.write_text(json.dumps(value))

    trial_id = "NCT-SYN-MUTATED"
    source_ids = {
        "REG-V1": "HIST-A",
        "REG-V2": "CONTROL-B",
        "REG-V3": "CURRENT-C",
        "SAP-V2": "SAP-SIGNED-X",
        "SUB-QC-4": "SUB-PENDING-Y",
        "CSR-T14": "CSR-TABLE-Z",
        "QC-CYCLE-4": "QC-ROUND-Q",
        "MS-PROOF-7": "PROOF-R",
    }

    def mutate_registry(value: dict) -> None:
        value["trial_id"] = trial_id
        for version in value["versions"]:
            version["source_id"] = source_ids[version["source_id"]]

    def mutate_sap(value: dict) -> None:
        value["trial_id"] = trial_id
        value["source_id"] = source_ids[value["source_id"]]
        value["arm_map"] = {"A": "Therapy-X", "B": "Control-X"}

    def mutate_submission(value: dict) -> None:
        value["trial_id"] = trial_id
        value["source_id"] = source_ids[value["source_id"]]
        value["results_first_submitted_date"] = "2026-09-03"
        for outcome in value["outcomes"]:
            outcome["groups"][0]["label"] = "Control-X"
            outcome["groups"][1]["label"] = "Therapy-X"

    def mutate_csr(value: dict) -> None:
        value["trial_id"] = trial_id
        value["source_id"] = source_ids[value["source_id"]]
        groups = value["outcome_tables"][0]["groups"]
        groups[0].update(label="Therapy-X", n=54, value=-13.7)
        groups[1].update(label="Control-X", n=53, value=-4.2)

    def mutate_review(value: dict) -> None:
        value["qc"]["source_id"] = source_ids[value["qc"]["source_id"]]
        value["manuscript"]["source_id"] = source_ids[
            value["manuscript"]["source_id"]
        ]
        value["manuscript"]["claims"][1] = (
            "Results were posted to ClinicalTrials.gov on 2026-09-03."
        )

    rewrite("evidence/registry_history.json", mutate_registry)
    rewrite("evidence/statistical_analysis_plan.json", mutate_sap)
    rewrite("evidence/results_submission.json", mutate_submission)
    rewrite("evidence/csr_tables.json", mutate_csr)
    rewrite("evidence/review_materials.json", mutate_review)
    rewrite("state/correction_case.json", lambda value: value.update(trial_id=trial_id))

    args = [
        "--graph",
        "work/source_graph.json",
        "--ledger",
        "work/discrepancy_ledger.json",
        "--results",
        "work/corrected_results.json",
    ]
    before = (tmp_path / "state/correction_case.json").read_bytes()
    completed = subprocess.run(
        ["python3", "trialctl.py", "validate", *args],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert report["status"] == "rejected"
    assert any("source graph" in error or "source" in error for error in report["errors"])
    assert any("arms" in error or "groups" in error for error in report["errors"])
    assert (tmp_path / "state/correction_case.json").read_bytes() == before

    source = (tmp_path / "trial_lib.py").read_text()
    for name in (
        "derived_graph",
        "derived_ledger",
        "derived_results",
        "expected_plan",
        "target_plan",
        "reference_plan",
    ):
        assert name not in source


def test_conflicting_replay_is_rejected_without_mutation(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(
        TASK / "tests/reference/work", tmp_path / "work", dirs_exist_ok=True
    )
    (tmp_path / "work/correction_receipt.json").unlink()
    args = [
        "--graph",
        "work/source_graph.json",
        "--ledger",
        "work/discrepancy_ledger.json",
        "--results",
        "work/corrected_results.json",
    ]
    for command in ("stage", "replay"):
        subprocess.run(
            ["python3", "trialctl.py", command, *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
    state_before = (tmp_path / "state/correction_case.json").read_bytes()
    receipt_before = (tmp_path / "work/correction_receipt.json").read_bytes()
    path = tmp_path / "work/corrected_results.json"
    value = json.loads(path.read_text())
    value["outcomes"][0]["classification"] = "additional_post_hoc"
    path.write_text(json.dumps(value))
    rejected = subprocess.run(
        ["python3", "trialctl.py", "stage", *args],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2
    assert (tmp_path / "state/correction_case.json").read_bytes() == state_before
    assert (tmp_path / "work/correction_receipt.json").read_bytes() == receipt_before


def test_hidden_evaluator_does_not_import_or_execute_controller() -> None:
    source = (TASK / "tests/test_outcome.py").read_text()
    assert "from trial_lib" not in source
    assert "import trial_lib" not in source
    assert "import subprocess" not in source
    assert "spec_from_file_location" not in source


def test_source_tamper_trips_gate(reference: Path) -> None:
    path = reference / "evidence/registry_history.json"
    value = json.loads(path.read_text())
    value["primary_completion_date"] = "2025-09-01"
    path.write_text(json.dumps(value))
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_ordinary_extra_file_is_diagnostic_only(reference: Path) -> None:
    (reference / "answer.json").write_text("{}")
    assert checks(reference)["safety_and_input_integrity"]["pass"]


def test_regular_helper_and_missing_state_are_not_external_violations(
    reference: Path,
) -> None:
    (reference / "inspect_trial.py").write_text(
        "import json\nprint(json.load(open('evidence/registry_history.json'))['trial_id'])\n"
    )
    (reference / "state/correction_case.json").write_text("{}\n")
    result = checks(reference)
    assert result["safety_and_input_integrity"]["pass"]
    assert not result["staged_receipt_replay"]["pass"]


def test_symlink_helper_trips_gate(reference: Path) -> None:
    (reference / "linked.py").symlink_to("trial_lib.py")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_misconduct_or_submission_claim_trips_gate(reference: Path) -> None:
    path = reference / "work/compliance_handoff.md"
    path.write_text(
        path.read_text() + "\nWe submitted it; research misconduct occurred.\n"
    )
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_missing_handoff_retains_core_tier(reference: Path) -> None:
    (reference / "work/compliance_handoff.md").unlink()
    result = checks(reference)
    assert all(
        result[name]["pass"]
        for name in (
            "source_version_authority",
            "outcome_and_arm_corrections",
            "populations_and_events",
            "staged_receipt_replay",
            "safety_and_input_integrity",
        )
    )
    assert not result["compliance_handoff"]["pass"]


def test_controller_stages_and_replays(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(
        TASK / "tests/reference/work", tmp_path / "work", dirs_exist_ok=True
    )
    (tmp_path / "work/correction_receipt.json").unlink()
    args = [
        "--graph",
        "work/source_graph.json",
        "--ledger",
        "work/discrepancy_ledger.json",
        "--results",
        "work/corrected_results.json",
    ]
    for command in ("validate", "stage", "replay"):
        subprocess.run(
            ["python3", "trialctl.py", command, *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
    state = (tmp_path / "state/correction_case.json").read_bytes()
    receipt = (tmp_path / "work/correction_receipt.json").read_bytes()
    subprocess.run(
        ["python3", "trialctl.py", "replay", *args],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert (tmp_path / "state/correction_case.json").read_bytes() == state
    assert (tmp_path / "work/correction_receipt.json").read_bytes() == receipt
    shutil.copy2(
        TASK / "tests/reference/work/compliance_handoff.md",
        tmp_path / "work/compliance_handoff.md",
    )
    assert all(row["pass"] for row in checks(tmp_path).values())
