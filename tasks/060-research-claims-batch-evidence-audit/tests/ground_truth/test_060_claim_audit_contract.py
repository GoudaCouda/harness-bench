from __future__ import annotations

import csv
import importlib.util
import json
import shutil
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]


def _load(relative: str, name: str):
    path = TASK / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load("tests/ground_truth/oracle_impl.py", "oracle_060")
OUTCOME = _load("tests/test_outcome.py", "outcome_060")


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    for source in (TASK / "tests" / "reference").iterdir():
        shutil.copy2(source, workspace / source.name)
    return workspace


def _checks(result: dict) -> dict[str, dict]:
    return {check["id"]: check for check in result["checks"]}


def test_reference_scores_one(tmp_path: Path) -> None:
    result = ORACLE.score_workspace(_workspace(tmp_path))
    assert result["outcome_score"] == 1.0
    assert all(_checks(result)[case_id]["pass"] for case_id in ORACLE._CASE_WEIGHTS)


def test_one_scope_misclassification_loses_its_cohort_once(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    csv_path = workspace / "claim_audit.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    next(row for row in rows if row["claim_id"] == "CL-13")["status"] = "contradicted"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    matrix_path = workspace / "evidence_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    item = next(item for item in matrix["claims"] if item["claim_id"] == "CL-13")
    item["status"] = "contradicted"
    item["evidence"][0]["supports_or_refutes"] = "refutes"
    matrix_path.write_text(json.dumps(matrix, indent=2), encoding="utf-8")

    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert result["outcome_score"] == 0.90
    assert not checks["generalization_scope"]["pass"]
    assert checks["subgroup_results"]["pass"]


def test_missing_secondary_source_loses_traceability_only(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "claim_audit.csv"
    text = path.read_text(encoding="utf-8").replace(
        'sources/peer_review_notes.md,"The partner cohort',
        ',"The partner cohort',
    )
    path.write_text(text, encoding="utf-8")

    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert result["outcome_score"] == 0.90
    assert not checks["cross_source_traceability"]["pass"]
    assert checks["subgroup_results"]["pass"]


def test_valid_source_locator_can_ground_source_text(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert checks["headline_and_methods"]["pass"]
    assert checks["reproducibility_gaps"]["pass"]


def test_logical_csv_row_and_equivalent_scope_source_are_accepted(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    csv_path = workspace / "claim_audit.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for claim_id, locator in {
        "CL-02": "Row retention_lift/partner",
        "CL-06": "Row support_ticket_change/overall",
        "CL-09": "Row retention_lift/mobile",
        "CL-11": "Row activation_lift/south",
    }.items():
        next(row for row in rows if row["claim_id"] == claim_id)[
            "evidence_location"
        ] = locator
    scope = next(row for row in rows if row["claim_id"] == "CL-13")
    scope["primary_source"] = "errata.md"
    scope["evidence_location"] = "ERR-2"
    scope["evidence_signal"] = "Scope is limited to enterprise customers."
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert checks["subgroup_results"]["pass"]
    assert checks["operational_and_safety"]["pass"]
    assert checks["generalization_scope"]["pass"]


def test_direct_regional_result_does_not_require_hidden_corrobation(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "claim_audit.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    next(row for row in rows if row["claim_id"] == "CL-11")["secondary_sources"] = ""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    result = ORACLE.score_workspace(workspace)
    assert _checks(result)["cross_source_traceability"]["pass"]


def test_extra_csv_fields_fail_integrity_not_repro_adjudication(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "claim_audit.csv"
    text = path.read_text(encoding="utf-8").replace(
        '"The raw events, configuration, and driver needed for an end-to-end rerun are missing."',
        "The raw events, configuration, and driver are missing.",
    )
    path.write_text(text, encoding="utf-8")

    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert not checks["audit_integrity"]["pass"]
    assert checks["reproducibility_gaps"]["pass"]


def test_fixture_mutation_fails_safety_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "claims" / "claims.csv").write_text("changed", encoding="utf-8")
    assert not OUTCOME.evaluate_cases(workspace)["safety_and_input_integrity"]["pass"]
