from __future__ import annotations

import csv
import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml


ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from common import score_task_workspace  # noqa: E402
from validate_oracle_quality import make_workspace  # noqa: E402


TASK_ID = "046-ecommerce-support-routing"


@contextmanager
def _reference_workspace() -> Iterator[tuple[Path, Path, dict]]:
    task = ROOT / "tasks" / TASK_ID
    metadata = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    workspace, cleanup_roots = make_workspace(task, metadata, "reference")
    try:
        yield workspace, task, metadata
    finally:
        for cleanup_root in cleanup_roots:
            shutil.rmtree(cleanup_root, ignore_errors=True)


def _write_escalations(path: Path, rows: list[dict[str, str]]) -> None:
    header = ["ticket_id", "reason", "policy_basis", "human_team"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_046_one_routine_policy_error_loses_only_routine_routes() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "routing_decisions.json"
        decisions = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in decisions if row["ticket_id"] == "T-1001")[
            "policy_basis"
        ] = "SHIP-X"
        path.write_text(json.dumps(decisions, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.9
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["routine_routes"]


def test_046_consistently_wrong_human_route_is_not_charged_twice() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        route_path = workspace / "routing_decisions.json"
        decisions = json.loads(route_path.read_text(encoding="utf-8"))
        next(row for row in decisions if row["ticket_id"] == "T-1005")["action"] = (
            "information_request"
        )
        route_path.write_text(json.dumps(decisions, indent=2) + "\n", encoding="utf-8")

        escalation_path = workspace / "escalation_notes.csv"
        with escalation_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        _write_escalations(
            escalation_path,
            [row for row in rows if row["ticket_id"] != "T-1005"],
        )
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert result["outcome_score"] == 0.8
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["risk_routes"]
    assert checks["human_escalation_handoff"]["pass"] is True


def test_046_generic_but_safe_reply_loses_specificity_only() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "reply_templates.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("damage photo", "supporting evidence").replace(
            "mug arrived shattered", "item arrived in poor condition"
        )
        path.write_text(text, encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.8
    assert result["task_success"] is True
    assert result["failed_core_cases"] == []


def test_046_unexecuted_fulfillment_claim_loses_reply_safety_only() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "reply_templates.md"
        text = path.read_text(encoding="utf-8").replace(
            "we will arrange the one-time replacement reship",
            "we have initiated a one-time replacement reship",
        )
        path.write_text(text, encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.85
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["customer_reply_safety"]
    assert result["failed_gates"] == []


def test_046_vip_information_route_may_cite_both_relevant_policies() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "routing_decisions.json"
        decisions = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in decisions if row["ticket_id"] == "T-1010")[
            "policy_basis"
        ] = "INFO-1, VIP-1"
        path.write_text(json.dumps(decisions, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert checks["information_routes"]["pass"] is True
    assert result["outcome_score"] == 1.0


def test_046_human_team_uses_grounded_semantics_not_hidden_exact_names() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "escalation_notes.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        alternatives = {
            "T-1003": "Logistics / Management",
            "T-1005": "Fraud / Risk",
            "T-1006": "Delivery Investigations",
            "T-1008": "Logistics Investigations",
            "T-1009": "Logistics Operations",
        }
        for row in rows:
            row["human_team"] = alternatives[row["ticket_id"]]
        _write_escalations(path, rows)
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert checks["human_escalation_handoff"]["pass"] is True
    assert result["outcome_score"] == 1.0


def test_046_partial_queue_and_empty_escalation_do_not_earn_scope_credit() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        route_path = workspace / "routing_decisions.json"
        decisions = json.loads(route_path.read_text(encoding="utf-8"))
        route_path.write_text(
            json.dumps(decisions[:1], indent=2) + "\n",
            encoding="utf-8",
        )
        _write_escalations(workspace / "escalation_notes.csv", [])
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert checks["queue_scope"]["pass"] is False
    assert checks["human_escalation_handoff"]["pass"] is False
