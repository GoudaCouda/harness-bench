from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import yaml


TASK = Path(__file__).resolve().parents[2]
ROOT = TASK.parents[1]
for source in (ROOT / "src", ROOT / "tools" / "task_maintenance"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from common import score_task_workspace  # noqa: E402
from harnessbench.grading.oracle_contract import (  # noqa: E402
    workspace_manifest,
    workspace_mutation_report,
)


METADATA = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))


@contextmanager
def _candidate(*, reference: bool = True) -> Iterator[tuple[Path, dict]]:
    with tempfile.TemporaryDirectory(prefix="hb100-adversarial-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        before = workspace_manifest(workspace)
        if reference:
            shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
        yield workspace, before


def _score(workspace: Path, before: dict) -> dict:
    mutation = workspace_mutation_report(
        before,
        workspace_manifest(workspace),
        contract=METADATA["mutation_contract"],
    )
    return score_task_workspace(
        TASK,
        METADATA,
        workspace,
        workspace_mutation=mutation,
    )


def _case(result: dict, case_id: str) -> dict:
    return next(check for check in result["checks"] if check["id"] == f"case:{case_id}")


def _rewrite_ledger(
    workspace: Path, change: Callable[[list[dict[str, str]]], None]
) -> None:
    path = workspace / "screening_ledger.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    change(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_reference_passes_all_formal_and_shared_gates() -> None:
    with _candidate() as (workspace, before):
        result = _score(workspace, before)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True
    assert result["required_artifact_contract"]["complete"] is True
    assert result["workspace_mutation_contract"]["complete"] is True


def test_untouched_empty_and_malformed_candidates_score_zero() -> None:
    with _candidate(reference=False) as (workspace, before):
        untouched = _score(workspace, before)
        for name in METADATA["required_artifacts"]:
            (workspace / name).write_text("", encoding="utf-8")
        empty = _score(workspace, before)
        (workspace / "screening_ledger.csv").write_text(
            "not,a,ledger\n", encoding="utf-8"
        )
        (workspace / "prisma_flow.json").write_text("[]\n", encoding="utf-8")
        malformed = _score(workspace, before)
    assert untouched["outcome_score"] == 0.0
    assert empty["outcome_score"] == 0.0
    assert malformed["outcome_score"] == 0.0


def test_alternative_ids_row_order_and_canonical_choice_pass() -> None:
    with _candidate() as (workspace, before):

        def change(rows: list[dict[str, str]]) -> None:
            report_ids: dict[str, str] = {}
            study_ids: dict[str, str] = {}
            for row in rows:
                report_ids.setdefault(
                    row["canonical_report_id"],
                    f"R{len(report_ids) + 1:02d}" + "r" * 61,
                )
                study_ids.setdefault(
                    row["study_id"], f"S{len(study_ids) + 1:02d}" + "s" * 61
                )
                row["canonical_report_id"] = report_ids[row["canonical_report_id"]]
                row["study_id"] = study_ids[row["study_id"]]
            p01 = next(row for row in rows if row["source_record_id"] == "P01")
            s01 = next(row for row in rows if row["source_record_id"] == "S01")
            p01["record_status"] = "duplicate"
            p01["eligibility_decision"] = "duplicate_record"
            p01["exclusion_reason"] = "duplicate_source_record"
            s01["record_status"] = "canonical"
            s01["eligibility_decision"] = "include"
            s01["exclusion_reason"] = ""
            rows.reverse()

        _rewrite_ledger(workspace, change)
        result = _score(workspace, before)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True


def test_crosswalk_alias_or_canonical_locator_are_equivalent() -> None:
    with _candidate() as (workspace, before):

        def change(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if row["source_record_id"] == "P02":
                    row["evidence"] = row["evidence"].replace(
                        "registry_crosswalk.csv#BETA-STEP-02",
                        "registry_crosswalk.csv#NCT1002",
                    )
                if row["source_record_id"] == "S02":
                    row["evidence"] = row["evidence"].replace(
                        "registry_crosswalk.csv#NCT1002",
                        "registry_crosswalk.csv#BETA-STEP-02",
                    )

        _rewrite_ledger(workspace, change)
        result = _score(workspace, before)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True


def test_structured_false_merge_naturally_loses_all_core_blocks() -> None:
    with _candidate() as (workspace, before):

        def change(rows: list[dict[str, str]]) -> None:
            p08 = next(row for row in rows if row["source_record_id"] == "P08")
            s08 = next(row for row in rows if row["source_record_id"] == "S08")
            p08["canonical_report_id"] = s08["canonical_report_id"]
            p08["study_id"] = s08["study_id"]

        _rewrite_ledger(workspace, change)
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.2
    assert result["task_success"] is False
    assert result["failed_core_cases"] == [
        "report_entity_resolution",
        "study_linkage_and_disposition",
        "closed_prisma_state",
    ]


def test_wrong_registered_precedence_has_its_natural_weighted_score() -> None:
    with _candidate() as (workspace, before):
        _rewrite_ledger(
            workspace,
            lambda rows: next(
                row for row in rows if row["source_record_id"] == "P05"
            ).update({"exclusion_reason": "wrong_population"}),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.75
    assert result["failed_core_cases"] == ["study_linkage_and_disposition"]
    assert _case(result, "closed_prisma_state")["pass"] is True


def test_core_result_without_either_provenance_handoff_scores_eighty() -> None:
    with _candidate() as (workspace, before):

        def change(rows: list[dict[str, str]]) -> None:
            for row in rows:
                row["evidence"] = ""

        _rewrite_ledger(workspace, change)
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.8
    assert result["task_success"] is True
    failed = {check["id"] for check in result["checks"] if not check["pass"]}
    assert failed == {
        "case:source_report_provenance",
        "case:crosswalk_study_provenance",
    }


def test_complete_source_provenance_without_crosswalk_handoff_scores_ninety() -> None:
    with _candidate() as (workspace, before):

        def change(rows: list[dict[str, str]]) -> None:
            for row in rows:
                row["evidence"] = ";".join(
                    item
                    for item in row["evidence"].split(";")
                    if not item.startswith("registry_crosswalk.csv#")
                )

        _rewrite_ledger(workspace, change)
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.9
    assert result["task_success"] is True
    failed = {check["id"] for check in result["checks"] if not check["pass"]}
    assert failed == {"case:crosswalk_study_provenance"}


def test_single_locator_defects_lose_only_their_business_handoff() -> None:
    scenarios = (
        (
            lambda rows: next(
                row for row in rows if row["source_record_id"] == "S03"
            ).update({"evidence": "registry_crosswalk.csv#NCT1003"}),
            "source_report_provenance",
        ),
        (
            lambda rows: next(
                row for row in rows if row["source_record_id"] == "P02"
            ).update({"evidence": "pubmed_export.csv#P02;scopus_export.ris#S02"}),
            "crosswalk_study_provenance",
        ),
        (
            lambda rows: next(
                row for row in rows if row["source_record_id"] == "P01"
            ).update(
                {
                    "evidence": "pubmed_export.csv#P01;scopus_export.ris#S01;"
                    "registry_crosswalk.csv#NCT1003",
                }
            ),
            "source_report_provenance",
        ),
    )
    for mutation, failed_case in scenarios:
        with _candidate() as (workspace, before):
            _rewrite_ledger(workspace, mutation)
            result = _score(workspace, before)
        assert result["outcome_score"] == 0.9
        assert result["task_success"] is True
        failed = {check["id"] for check in result["checks"] if not check["pass"]}
        assert failed == {f"case:{failed_case}"}


def test_single_missing_duplicate_occurrence_loses_source_provenance_only() -> None:
    with _candidate() as (workspace, before):
        _rewrite_ledger(
            workspace,
            lambda rows: next(
                row for row in rows if row["source_record_id"] == "P01"
            ).update({"evidence": "pubmed_export.csv#P01"}),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.9
    assert result["task_success"] is True
    assert _case(result, "source_report_provenance")["pass"] is False
    assert _case(result, "crosswalk_study_provenance")["pass"] is True


def test_stale_flow_has_its_natural_weighted_score() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "prisma_flow.json"
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["included_reports"] = 9
        path.write_text(json.dumps(flow), encoding="utf-8")
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.75
    assert result["failed_core_cases"] == ["closed_prisma_state"]


def test_benign_extra_artifact_is_diagnostic_but_formula_cell_fails_closed() -> None:
    with _candidate() as (workspace, before):
        (workspace / "protocol_audit.md").write_text("undeclared\n", encoding="utf-8")
        extra = _score(workspace, before)
    assert extra["outcome_score"] == 1.0
    assert extra["failed_gates"] == []
    assert extra["workspace_mutation_contract"]["complete"] is False
    assert extra["workspace_mutation_contract"]["safe"] is True

    with _candidate() as (workspace, before):
        _rewrite_ledger(
            workspace,
            lambda rows: rows[0].update({"evidence": '=HYPERLINK("https://invalid")'}),
        )
        formula = _score(workspace, before)
    assert formula["outcome_score"] == 0.0
    assert formula["failed_gates"] == ["safety_and_integrity"]


def test_malformed_json_naturally_fails_the_closed_state_block() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "prisma_flow.json"
        rendered = path.read_text(encoding="utf-8").rstrip()
        path.write_text(
            rendered[:-1] + ', "records_identified": 19}\n', encoding="utf-8"
        )
        duplicate = _score(workspace, before)
    assert duplicate["outcome_score"] == 0.75
    assert duplicate["failed_core_cases"] == ["closed_prisma_state"]
    assert duplicate["failed_gates"] == []

    with _candidate() as (workspace, before):
        path = workspace / "prisma_flow.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                '"records_identified": 19', '"records_identified": NaN'
            ),
            encoding="utf-8",
        )
        constant = _score(workspace, before)
    assert constant["outcome_score"] == 0.75
    assert constant["failed_core_cases"] == ["closed_prisma_state"]
    assert constant["failed_gates"] == []


def test_deep_json_is_a_candidate_safety_failure_not_an_oracle_failure() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "prisma_flow.json"
        rendered = path.read_text(encoding="utf-8")
        nested = "[" * 500 + "0" + "]" * 500
        path.write_text(
            rendered.replace(
                '"records_identified": 19', f'"records_identified": {nested}'
            ),
            encoding="utf-8",
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.0
    assert result["task_success"] is False
    assert result["failed_gates"] == ["safety_and_integrity"]
    assert result.get("oracle_contract_failure") is not True


def test_csv_underflow_and_overflow_naturally_fail_business_blocks() -> None:
    for suffix in ("underflow", "overflow"):
        with _candidate() as (workspace, before):
            path = workspace / "screening_ledger.csv"
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[1] = (
                lines[1].rsplit(",", 1)[0] if suffix == "underflow" else lines[1] + ","
            )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = _score(workspace, before)
        assert result["outcome_score"] == 0.0
        assert result["failed_core_cases"] == [
            "report_entity_resolution",
            "study_linkage_and_disposition",
            "closed_prisma_state",
        ]
        assert result["failed_gates"] == []
        assert _case(result, "source_report_provenance")["pass"] is False
        assert _case(result, "crosswalk_study_provenance")["pass"] is False


def test_extra_flow_schema_field_naturally_fails_only_closed_state() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "prisma_flow.json"
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["reviewer_note"] = "local schema mistake"
        path.write_text(json.dumps(flow), encoding="utf-8")
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.75
    assert result["failed_core_cases"] == ["closed_prisma_state"]
    assert result["failed_gates"] == []


def test_bom_is_schema_failure_while_control_and_format_characters_fail_closed() -> (
    None
):
    with _candidate() as (workspace, before):
        path = workspace / "screening_ledger.csv"
        path.write_text("\ufeff" + path.read_text(encoding="utf-8"), encoding="utf-8")
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == []

    for unsafe in ("\x01", "\u200b"):
        with _candidate() as (workspace, before):
            path = workspace / "screening_ledger.csv"
            rendered = path.read_text(encoding="utf-8")
            rendered = rendered.replace(
                "pubmed_export.csv#P01", unsafe + "pubmed_export.csv#P01", 1
            )
            path.write_text(rendered, encoding="utf-8")
            result = _score(workspace, before)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["safety_and_integrity"]


def test_input_mutation_fails_oracle_and_shared_mutation_gates() -> None:
    with _candidate() as (workspace, before):
        source = workspace / "review_protocol.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8"
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.0
    assert result["task_success"] is False
    assert result["workspace_mutation_contract"]["complete"] is False
