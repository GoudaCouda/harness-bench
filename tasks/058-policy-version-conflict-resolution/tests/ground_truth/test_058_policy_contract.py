from __future__ import annotations

import importlib.util
import csv
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


ORACLE = _load("tests/ground_truth/oracle_impl.py", "oracle_058")
OUTCOME = _load("tests/test_outcome.py", "outcome_058")


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    for source in (TASK / "tests" / "reference").iterdir():
        shutil.copy2(source, workspace / source.name)
    return workspace


def test_reference_passes_every_formal_case(tmp_path: Path) -> None:
    assert all(
        value["pass"] for value in OUTCOME.evaluate_cases(_workspace(tmp_path)).values()
    )


def test_enumerated_priority_rules_are_semantically_valid(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "conflict_audit.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    aliases = {
        "version": "version_priority",
        "scope": "scoped_exception",
        "effective_date": "effective_date",
    }
    truth = json.loads(
        (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    for row in rows:
        expected_kind = truth["audit_priority_kinds"][row["case_id"]]
        row["priority_rule"] = aliases[expected_kind]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    result = ORACLE.score_workspace(workspace)
    checks = {check["id"]: check for check in result["checks"]}
    assert checks["conflict_audit"]["pass"]
    assert checks["audit_format"]["pass"]


def test_conflict_trace_may_live_in_dedicated_audit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "policy_rulings.json"
    rulings = json.loads(path.read_text(encoding="utf-8"))
    for case_id in {"C-003", "C-005", "C-010", "C-011"}:
        row = next(item for item in rulings if item["case_id"] == case_id)
        row["conflict_resolution"]["superseded_sources"] = []
    path.write_text(json.dumps(rulings, indent=2), encoding="utf-8")

    observations = OUTCOME.evaluate_cases(workspace)
    assert observations["conflict_handling"]["pass"]
    assert observations["decision_record"]["pass"]

    audit = workspace / "conflict_audit.csv"
    with audit.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row["case_id"] in {"C-003", "C-005", "C-010", "C-011"}:
            row["losing_sources"] = "omitted"
    with audit.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    assert not OUTCOME.evaluate_cases(workspace)["conflict_handling"]["pass"]


def test_malformed_audit_header_fails_record(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "conflict_audit.csv"
    text = path.read_text(encoding="utf-8").replace("claim_axis", "topic", 1)
    path.write_text(text, encoding="utf-8")
    assert not OUTCOME.evaluate_cases(workspace)["decision_record"]["pass"]


def test_fixture_mutation_fails_safety_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "version_rules.json").write_text("{}", encoding="utf-8")
    assert not OUTCOME.evaluate_cases(workspace)["safety_and_input_integrity"]["pass"]
