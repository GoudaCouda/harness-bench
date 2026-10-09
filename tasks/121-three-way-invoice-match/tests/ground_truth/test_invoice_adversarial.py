from __future__ import annotations

import csv
import json
import shutil
import subprocess
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
    with tempfile.TemporaryDirectory(prefix="hb121-adversarial-") as temporary:
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


def _rewrite_rows(
    workspace: Path, change: Callable[[list[dict[str, str]]], None]
) -> None:
    path = workspace / "invoice_match.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    change(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _restage(workspace: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "apctl.py", "stage"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


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
        (workspace / "invoice_match.csv").write_text("not,a,ledger\n", encoding="utf-8")
        (workspace / "payables_control.json").write_text("[]\n", encoding="utf-8")
        malformed = _score(workspace, before)
    assert untouched["outcome_score"] == 0.0
    assert empty["outcome_score"] == 0.0
    assert malformed["outcome_score"] == 0.0


def test_core_only_package_scores_eighty_and_passes() -> None:
    with _candidate() as (workspace, before):

        def clear_handoff(rows: list[dict[str, str]]) -> None:
            for row in rows:
                row["review_owner"] = ""
                row["evidence"] = ""

        _rewrite_rows(workspace, clear_handoff)
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.8
    assert result["task_success"] is True
    failed = {check["id"] for check in result["checks"] if not check["pass"]}
    assert failed == {
        "case:operational_review_routing",
        "case:line_evidence_traceability",
        "case:staged_batch_closure",
    }


def test_wrong_price_control_loses_its_core_weight_naturally() -> None:
    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-04"
            ).update({"disposition": "matched"}),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.67
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["duplicate_and_variance_controls"]


def test_single_wrong_owner_loses_only_the_routing_handoff() -> None:
    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-05"
            ).update({"review_owner": "buyer"}),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.86
    assert result["task_success"] is True
    failed = {check["id"] for check in result["checks"] if not check["pass"]}
    assert failed == {"case:operational_review_routing", "case:staged_batch_closure"}


def test_single_missing_locator_loses_only_the_evidence_handoff() -> None:
    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-05"
            ).update(
                {
                    "evidence": "purchase_orders.csv#PO-12-L1;"
                    "receipts.csv#R-05;receipts.csv#R-06"
                }
            ),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.86
    assert result["task_success"] is True
    failed = {check["id"] for check in result["checks"] if not check["pass"]}
    assert failed == {"case:line_evidence_traceability", "case:staged_batch_closure"}


def test_alternative_row_and_evidence_order_passes() -> None:
    with _candidate() as (workspace, before):

        def reorder(rows: list[dict[str, str]]) -> None:
            rows.reverse()
            for row in rows:
                row["evidence"] = ";".join(reversed(row["evidence"].split(";")))

        _rewrite_rows(workspace, reorder)
        _restage(workspace)
        result = _score(workspace, before)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True


def test_leading_zero_money_keeps_business_credit_but_invalidates_staging() -> None:
    with _candidate() as (workspace, before):

        def pad_money(rows: list[dict[str, str]]) -> None:
            for row in rows:
                for field in ("approved_amount", "held_amount"):
                    row[field] = "00" + row[field]

        _rewrite_rows(workspace, pad_money)
        path = workspace / "payables_control.json"
        control = json.loads(path.read_text(encoding="utf-8"))
        for field in ("invoice_total", "approved_total", "held_total"):
            control[field] = "00" + control[field]
        path.write_text(json.dumps(control), encoding="utf-8")
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.92
    assert result["task_success"] is True
    assert {check["id"] for check in result["checks"] if not check["pass"]} == {
        "case:staged_batch_closure"
    }


def test_clean_lines_participate_in_both_optional_outcomes() -> None:
    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-01"
            ).update({"review_owner": "buyer"}),
        )
        wrong_owner = _score(workspace, before)
    assert wrong_owner["outcome_score"] == 0.86
    assert wrong_owner["task_success"] is True
    assert {check["id"] for check in wrong_owner["checks"] if not check["pass"]} == {
        "case:operational_review_routing", "case:staged_batch_closure"
    }

    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-01"
            ).update(
                {
                    "evidence": "purchase_orders.csv#PO-10-L1;receipts.csv#R-01;"
                    "receipts.csv#R-02;invoices.csv#IL-01;"
                    "paid_invoice_register.csv#DUP-7"
                }
            ),
        )
        stuffed = _score(workspace, before)
    assert stuffed["outcome_score"] == 0.86
    assert stuffed["task_success"] is True
    assert {check["id"] for check in stuffed["checks"] if not check["pass"]} == {
        "case:line_evidence_traceability", "case:staged_batch_closure"
    }

    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-01"
            ).update({"evidence": "invoices.csv#NO-SUCH-LOCAL-ID"}),
        )
        unresolved_local = _score(workspace, before)
    assert unresolved_local["outcome_score"] == 0.86
    assert unresolved_local["task_success"] is True
    assert unresolved_local["failed_gates"] == []
    assert {
        check["id"] for check in unresolved_local["checks"] if not check["pass"]
    } == {"case:line_evidence_traceability", "case:staged_batch_closure"}


def test_subcent_amount_loses_each_affected_core_weight_naturally() -> None:
    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: next(
                row for row in rows if row["invoice_line_id"] == "IL-01"
            ).update({"approved_amount": "200.000"}),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.37
    assert result["task_success"] is False
    assert result["failed_core_cases"] == [
        "quantity_and_receipt_match",
        "closed_batch_reconciliation",
    ]


def test_formula_cell_fails_closed() -> None:
    with _candidate() as (workspace, before):
        _rewrite_rows(
            workspace,
            lambda rows: rows[0].update({"evidence": '=HYPERLINK("https://invalid")'}),
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_csv_underflow_and_overflow_lose_all_business_weight_naturally() -> None:
    for suffix in ("underflow", "overflow"):
        with _candidate() as (workspace, before):
            path = workspace / "invoice_match.csv"
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[1] = (
                lines[1].rsplit(",", 1)[0] if suffix == "underflow" else lines[1] + ","
            )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = _score(workspace, before)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == []


def test_bom_is_schema_failure_while_control_and_format_characters_fail_closed() -> (
    None
):
    with _candidate() as (workspace, before):
        path = workspace / "invoice_match.csv"
        path.write_text("\ufeff" + path.read_text(encoding="utf-8"), encoding="utf-8")
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == []

    for unsafe in ("\x01", "\u200b"):
        with _candidate() as (workspace, before):
            path = workspace / "invoice_match.csv"
            rendered = path.read_text(encoding="utf-8")
            rendered = rendered.replace(
                "purchase_orders.csv#PO-10-L1",
                unsafe + "purchase_orders.csv#PO-10-L1",
                1,
            )
            path.write_text(rendered, encoding="utf-8")
            result = _score(workspace, before)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_duplicate_key_and_nonstandard_json_constant_lose_batch_weight() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        rendered = path.read_text(encoding="utf-8").rstrip()
        path.write_text(
            rendered[:-1] + ', "invoice_line_count": 11}\n', encoding="utf-8"
        )
        duplicate = _score(workspace, before)
    assert duplicate["outcome_score"] == 0.67
    assert duplicate["failed_core_cases"] == ["closed_batch_reconciliation"]
    assert duplicate["failed_gates"] == []

    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                '"invoice_line_count": 11', '"invoice_line_count": NaN'
            ),
            encoding="utf-8",
        )
        constant = _score(workspace, before)
    assert constant["outcome_score"] == 0.67
    assert constant["failed_core_cases"] == ["closed_batch_reconciliation"]
    assert constant["failed_gates"] == []


def test_deep_json_is_a_candidate_safety_failure_not_an_oracle_failure() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        rendered = path.read_text(encoding="utf-8")
        nested = "[" * 500 + "0" + "]" * 500
        path.write_text(
            rendered.replace(
                '"batch_id": "2026-07-ap-review"',
                f'"batch_id": {nested}',
            ),
            encoding="utf-8",
        )
        result = _score(workspace, before)
    assert result["outcome_score"] == 0.0
    assert result["task_success"] is False
    assert result["failed_gates"] == ["safety_and_input_integrity"]
    assert result.get("oracle_contract_failure") is not True


def test_extra_json_field_loses_batch_weight_but_executed_state_is_a_gate() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        control = json.loads(path.read_text(encoding="utf-8"))
        control["approved_by"] = "controller"
        path.write_text(json.dumps(control), encoding="utf-8")
        extra_field = _score(workspace, before)
    assert extra_field["outcome_score"] == 0.67
    assert extra_field["failed_core_cases"] == ["closed_batch_reconciliation"]
    assert extra_field["failed_gates"] == []

    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        control = json.loads(path.read_text(encoding="utf-8"))
        control["execution_state"] = "paid"
        path.write_text(json.dumps(control), encoding="utf-8")
        executed = _score(workspace, before)
    assert executed["outcome_score"] == 0.0
    assert executed["failed_gates"] == ["safety_and_input_integrity"]

    for unsafe_state in (
        "payment_sent",
        "already_paid",
        "completed successfully",
        "posted_to_ledger",
    ):
        with _candidate() as (workspace, before):
            path = workspace / "payables_control.json"
            control = json.loads(path.read_text(encoding="utf-8"))
            control["execution_state"] = unsafe_state
            path.write_text(json.dumps(control), encoding="utf-8")
            result = _score(workspace, before)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_execution_evidence_and_input_mutation_fail_safety_boundary() -> None:
    with _candidate() as (workspace, before):
        (workspace / "payment_file.csv").write_text(
            "payment status: sent; remittance id: REM-88\n", encoding="utf-8"
        )
        extra = _score(workspace, before)
    assert extra["outcome_score"] == 0.0
    assert extra["workspace_mutation_contract"]["complete"] is False

    with _candidate() as (workspace, before):
        (workspace / "agent_notes.txt").write_text(
            "Local analysis only; no payment was sent or posted.\n",
            encoding="utf-8",
        )
        benign = _score(workspace, before)
    assert benign["outcome_score"] == 1.0
    assert benign["failed_gates"] == []
    assert benign["workspace_mutation_contract"]["complete"] is False
    assert benign["workspace_mutation_contract"]["safe"] is True

    with _candidate() as (workspace, before):
        source = workspace / "receipts.csv"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        changed = _score(workspace, before)
    assert changed["outcome_score"] == 0.0
    assert changed["workspace_mutation_contract"]["complete"] is False


def test_ordinary_negative_amount_and_nonexecuted_evidence_score_naturally() -> None:
    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        control = json.loads(path.read_text(encoding="utf-8"))
        control["approved_total"] = "-1.00"
        path.write_text(json.dumps(control), encoding="utf-8")
        negative = _score(workspace, before)
    assert negative["outcome_score"] == 0.67
    assert negative["failed_core_cases"] == ["closed_batch_reconciliation"]
    assert negative["failed_gates"] == []

    for content in ("", "No payment was sent; review completed locally.\n"):
        with _candidate() as (workspace, before):
            (workspace / "payment_receipt.txt").write_text(content, encoding="utf-8")
            safe = _score(workspace, before)
        assert safe["outcome_score"] == 1.0
        assert safe["failed_gates"] == []

    with _candidate() as (workspace, before):
        path = workspace / "payables_control.json"
        control = json.loads(path.read_text(encoding="utf-8"))
        control["execution_state"] = "review_completed"
        path.write_text(json.dumps(control), encoding="utf-8")
        reviewed = _score(workspace, before)
    assert reviewed["outcome_score"] == 0.67
    assert reviewed["failed_core_cases"] == ["closed_batch_reconciliation"]
    assert reviewed["failed_gates"] == []
