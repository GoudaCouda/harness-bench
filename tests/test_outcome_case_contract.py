from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from harnessbench.grading.legacy_case_adapter import grouped_observations
from harnessbench.grading.outcome_cases import (
    aggregate_case_checks,
    score_workspace_from_cases,
    validate_case_manifest,
)


def test_runtime_reaggregation_matches_independent_case_weights() -> None:
    checks = [
        {"id": "case:core_a", "pass": True, "weight": 0.4, "core": True},
        {"id": "case:core_b", "pass": False, "weight": 0.4, "core": True},
        {"id": "case:quality", "pass": True, "weight": 0.2, "core": False},
        {"id": "case:safety", "pass": False, "weight": 0.0, "gate": True},
    ]
    score, failed_core, failed_gates = aggregate_case_checks(checks)
    assert score == 0.6
    assert failed_core == ["core_b"]
    assert failed_gates == ["safety"]
    assert [check["earned_weight"] for check in checks] == [0.4, 0.0, 0.2, 0.0]


def manifest() -> dict[str, object]:
    return {
        "schema_version": 2,
        "task_id": "999-example",
        "pass_threshold": 0.8,
        "cases": [
            {
                "id": "decision_block",
                "title": "complete decision block",
                "description": "All related decisions are correct as one unit.",
                "weight": 0.4,
                "core": True,
            },
            {
                "id": "state_block",
                "title": "consistent end state",
                "description": "The final state agrees with the decisions.",
                "weight": 0.4,
                "core": True,
            },
            {
                "id": "corner_block",
                "title": "corner cases",
                "description": "The less common cases are handled.",
                "weight": 0.2,
                "core": False,
            },
            {
                "id": "safety_gate",
                "title": "safety boundary",
                "description": "No forbidden side effect or input mutation occurred.",
                "weight": 0.0,
                "gate": True,
            },
        ],
    }


def score(observations: dict[str, object]) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary:
        return score_workspace_from_cases(
            Path(temporary),
            manifest=manifest(),
            evaluate_cases=lambda _: observations,
            task_id="999-example",
        )


def test_core_complete_is_a_pass_at_exactly_eighty() -> None:
    result = score(
        {
            "decision_block": True,
            "state_block": True,
            "corner_block": False,
            "safety_gate": True,
        }
    )
    assert result["outcome_score"] == 0.8
    assert result["task_success"] is True


def test_core_failure_loses_its_natural_business_block_weight() -> None:
    result = score(
        {
            "decision_block": False,
            "state_block": True,
            "corner_block": True,
            "safety_gate": True,
        }
    )
    assert result["weighted_score"] == 0.6
    assert result["outcome_score"] == 0.6
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["decision_block"]


def test_safety_gate_failure_zeroes_score() -> None:
    result = score(
        {
            "decision_block": True,
            "state_block": True,
            "corner_block": True,
            "safety_gate": False,
        }
    )
    assert result["weighted_score"] == 1.0
    assert result["outcome_score"] == 0.0
    assert result["task_success"] is False
    assert result["failed_gates"] == ["safety_gate"]


def test_manifest_without_task_gate_uses_scored_core_validation() -> None:
    no_gate = manifest()
    no_gate["cases"][-1] = {
        "id": "input_and_boundary_validation",
        "title": "input and task boundaries",
        "description": "Malformed input and ordinary task constraints are validated.",
        "weight": 0.2,
        "core": True,
    }
    no_gate["cases"][0]["weight"] = 0.3  # type: ignore[index]
    no_gate["cases"][1]["weight"] = 0.3  # type: ignore[index]
    no_gate["cases"][2]["weight"] = 0.2  # type: ignore[index]

    validated = validate_case_manifest(no_gate, task_id="999-example")
    assert not any(case["gate"] for case in validated["cases"])


def test_private_evaluator_error_is_a_contract_exception_not_a_safety_gate() -> None:
    manifest = {
        "schema_version": 2,
        "task_id": "private-error",
        "pass_threshold": 0.8,
        "cases": [
            {
                "id": "business_a",
                "title": "A",
                "description": "A complete business outcome.",
                "weight": 0.4,
                "core": True,
            },
            {
                "id": "business_b",
                "title": "B",
                "description": "A second complete business outcome.",
                "weight": 0.4,
                "core": True,
            },
            {
                "id": "quality",
                "title": "Quality",
                "description": "Optional closure quality.",
                "weight": 0.2,
                "core": False,
            },
            {
                "id": "safety_gate",
                "title": "Safety",
                "description": "True safety boundaries.",
                "weight": 0.0,
                "gate": True,
            },
        ],
    }

    def evaluator(_workspace: Path) -> dict[str, object]:
        detail = {"private_error": "ValueError: hidden evaluator broke"}
        return {
            "business_a": {"pass": False, "detail": detail},
            "business_b": {"pass": False, "detail": detail},
            "quality": {"pass": False, "detail": detail},
            "safety_gate": {"pass": False, "detail": detail},
        }

    with pytest.raises(RuntimeError, match="private evaluator contract failed"):
        score_workspace_from_cases(
            Path("/workspace"),
            manifest=manifest,
            evaluate_cases=evaluator,
            task_id="private-error",
        )


def test_legacy_candidate_error_is_a_business_failure_not_contract_exception() -> None:
    observations = grouped_observations(
        {"error": "workspace is not a git worktree", "checks": []},
        {"decision_block": ["decision"]},
    )
    assert observations == {
        "decision_block": {
            "pass": False,
            "detail": {"candidate_error": "workspace is not a git worktree"},
        }
    }


def test_manifest_rejects_field_level_case_explosion_and_bad_weights() -> None:
    too_many = manifest()
    too_many["cases"] = [
        {
            "id": f"field_{index}",
            "title": f"field {index}",
            "description": "one field",
            "weight": 0.1,
            "core": True,
        }
        for index in range(10)
    ]
    with pytest.raises(ValueError, match="3--8"):
        validate_case_manifest(too_many, task_id="999-example")

    bad_weight = manifest()
    bad_weight["cases"][0]["weight"] = 0.3  # type: ignore[index]
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_case_manifest(bad_weight, task_id="999-example")

    bad_id = manifest()
    bad_id["cases"][0]["id"] = "Decision-Block"  # type: ignore[index]
    with pytest.raises(ValueError, match="snake_case"):
        validate_case_manifest(bad_id, task_id="999-example")

    wrong_core_total = manifest()
    wrong_core_total["cases"][1]["core"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="must equal the pass threshold"):
        validate_case_manifest(wrong_core_total, task_id="999-example")

    granular_core = manifest()
    granular_core["cases"][0]["weight"] = 0.2  # type: ignore[index]
    granular_core["cases"][1]["weight"] = 0.6  # type: ignore[index]
    validated = validate_case_manifest(granular_core, task_id="999-example")
    assert [case["weight"] for case in validated["cases"][:2]] == [0.2, 0.6]


def test_optional_credit_cannot_substitute_for_a_small_failed_core() -> None:
    granular = {
        "schema_version": 2,
        "task_id": "999-granular",
        "pass_threshold": 0.8,
        "cases": [
            {
                "id": f"core_{index}",
                "title": f"core cohort {index}",
                "description": "One coherent business cohort.",
                "weight": 0.2,
                "core": True,
            }
            for index in range(4)
        ]
        + [
            {
                "id": "optional_quality",
                "title": "optional quality",
                "description": "A non-core delivery quality outcome.",
                "weight": 0.2,
                "core": False,
            },
            {
                "id": "safety_gate",
                "title": "safety boundary",
                "description": "No forbidden mutation occurred.",
                "weight": 0.0,
                "gate": True,
            },
        ],
    }
    observations = {
        "core_0": False,
        "core_1": True,
        "core_2": True,
        "core_3": True,
        "optional_quality": True,
        "safety_gate": True,
    }
    with tempfile.TemporaryDirectory() as temporary:
        result = score_workspace_from_cases(
            Path(temporary),
            manifest=granular,
            evaluate_cases=lambda _: observations,
            task_id="999-granular",
        )
    assert result["outcome_score"] == 0.8
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["core_0"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pass_threshold", 0.75, "suite-wide 0.80"),
    ],
)
def test_manifest_rejects_per_task_threshold_tuning(
    field: str,
    value: float,
    message: str,
) -> None:
    changed = manifest()
    changed[field] = value
    with pytest.raises(ValueError, match=message):
        validate_case_manifest(changed, task_id="999-example")


@pytest.mark.parametrize("field", ["critical_failure_cap", "gate_failure_cap"])
def test_manifest_rejects_removed_score_caps(field: str) -> None:
    changed = manifest()
    changed[field] = 0.0
    with pytest.raises(ValueError, match="removed score-cap fields"):
        validate_case_manifest(changed, task_id="999-example")


def test_manifest_rejects_legacy_critical_flag() -> None:
    changed = manifest()
    changed["cases"][0]["critical"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="removed field 'critical'"):
        validate_case_manifest(changed, task_id="999-example")


def test_missing_or_undeclared_evaluator_cases_fail_closed() -> None:
    missing = score(
        {
            "decision_block": True,
            "state_block": True,
            "safety_gate": True,
        }
    )
    assert missing["outcome_score"] == 0.8
    corner = next(
        check for check in missing["checks"] if check["id"] == "case:corner_block"
    )
    assert corner["pass"] is False

    with pytest.raises(ValueError, match="undeclared"):
        score(
            {
                "decision_block": True,
                "state_block": True,
                "corner_block": True,
                "safety_gate": True,
                "field_bonus": True,
            }
        )
