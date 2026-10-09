"""Business-outcome case contract for formal HarnessBench tasks.

Task-specific tests decide whether each coherent acceptance case passed.  This
module validates the hidden case manifest and performs suite-wide aggregation.
It intentionally does not award points for individual fields: one case earns
its weight only when the task-specific evaluator reports the whole business
outcome as complete.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable, Mapping


CASE_SCHEMA_VERSION = 2
MIN_CASES = 3
MAX_CASES = 8
DEFAULT_PASS_THRESHOLD = 0.8


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def validate_case_manifest(value: object, *, task_id: str = "") -> dict[str, Any]:
    """Return a normalized 3--8 case business-level grading manifest."""
    if not isinstance(value, Mapping):
        raise ValueError("case manifest must be an object")
    manifest = dict(value)
    if manifest.get("schema_version") != CASE_SCHEMA_VERSION:
        raise ValueError(f"case manifest schema_version must be {CASE_SCHEMA_VERSION}")
    declared_task_id = str(manifest.get("task_id") or "").strip()
    if not declared_task_id:
        raise ValueError("case manifest must declare task_id")
    if task_id and declared_task_id != task_id:
        raise ValueError(
            f"case manifest task_id mismatch: {declared_task_id!r} != {task_id!r}"
        )

    threshold = _number(
        manifest.get("pass_threshold", DEFAULT_PASS_THRESHOLD),
        field="pass_threshold",
    )
    if not 0.0 < threshold <= 1.0:
        raise ValueError("pass_threshold must be in (0, 1]")
    if not math.isclose(threshold, DEFAULT_PASS_THRESHOLD, abs_tol=1e-9):
        raise ValueError(
            f"pass_threshold must be the suite-wide {DEFAULT_PASS_THRESHOLD:.2f}"
        )
    deprecated = sorted(
        field
        for field in ("critical_failure_cap", "gate_failure_cap")
        if field in manifest
    )
    if deprecated:
        raise ValueError(
            "case manifest uses removed score-cap fields: " + ", ".join(deprecated)
        )

    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or not MIN_CASES <= len(raw_cases) <= MAX_CASES:
        raise ValueError(f"case manifest must contain {MIN_CASES}--{MAX_CASES} cases")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    positive_weight = 0.0
    core_weight = 0.0
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, Mapping):
            raise ValueError(f"cases[{index}] must be an object")
        case = dict(raw)
        case_id = str(case.get("id") or "").strip()
        title = str(case.get("title") or "").strip()
        description = str(case.get("description") or "").strip()
        if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", case_id) is None:
            raise ValueError(f"cases[{index}].id must be a stable snake_case token")
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        if not title or not description:
            raise ValueError(f"case {case_id} must have title and description")
        seen.add(case_id)

        if "critical" in case:
            raise ValueError(
                f"case {case_id} uses removed field 'critical'; use 'core'"
            )
        gate = case.get("gate", False)
        core = case.get("core", False)
        if not isinstance(gate, bool) or not isinstance(core, bool):
            raise ValueError(f"case {case_id} gate/core values must be booleans")
        weight = _number(case.get("weight", 0.0), field=f"case {case_id} weight")
        if weight < 0.0 or weight > 1.0:
            raise ValueError(f"case {case_id} weight must be in [0, 1]")
        if gate and weight != 0.0:
            raise ValueError(
                f"gate case {case_id} must have zero weight; gates constrain scores"
            )
        if not gate and weight <= 0.0:
            raise ValueError(f"non-gate case {case_id} must have positive weight")
        if gate and core:
            raise ValueError(f"gate case {case_id} cannot also be a scored core case")
        positive_weight += weight
        if core:
            core_weight += weight
        cases.append(
            {
                "id": case_id,
                "title": title,
                "description": description,
                "weight": weight,
                "core": core,
                "gate": gate,
            }
        )

    if not math.isclose(positive_weight, 1.0, abs_tol=1e-9):
        raise ValueError(
            f"non-gate case weights must sum to 1.0, got {positive_weight:.12g}"
        )
    if not math.isclose(core_weight, threshold, abs_tol=1e-9):
        raise ValueError(
            "core case weights must equal the pass threshold; "
            f"got {core_weight:.4f} != {threshold:.4f}"
        )
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "task_id": declared_task_id,
        "pass_threshold": threshold,
        "cases": cases,
    }


def _normalize_observation(case_id: str, value: object) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"pass": value, "detail": None}
    if not isinstance(value, Mapping):
        raise ValueError(
            f"case evaluator result for {case_id} must be boolean or object"
        )
    observation = dict(value)
    passed = observation.get("pass")
    if not isinstance(passed, bool):
        raise ValueError(f"case evaluator result for {case_id} lacks boolean pass")
    unknown = sorted(set(observation) - {"pass", "detail"})
    if unknown:
        raise ValueError(
            f"case evaluator result for {case_id} has unknown fields: {unknown}"
        )
    return {"pass": passed, "detail": observation.get("detail")}


def aggregate_case_checks(
    checks: list[dict[str, Any]],
) -> tuple[float, list[str], list[str]]:
    """Aggregate already-normalized checks for runtime re-scoring.

    This compatibility surface is used by the semantic-fallback runtime. It
    intentionally follows the same independent business-case weighting as
    ``score_workspace_from_cases``; safety gates remain zero-weight and zero
    the final outcome at the caller.
    """
    score = 0.0
    failed_core: list[str] = []
    failed_gates: list[str] = []
    for check in checks:
        case_id = str(check.get("id") or "").removeprefix("case:")
        passed = check.get("pass") is True
        weight = float(check.get("weight") or 0.0)
        earned = weight if passed else 0.0
        check["earned_weight"] = earned
        score += earned
        if not passed and check.get("core") is True:
            failed_core.append(case_id)
        if not passed and check.get("gate") is True:
            failed_gates.append(case_id)
    return round(score, 4), failed_core, failed_gates


def score_workspace_from_cases(
    workspace: Path,
    *,
    manifest: object,
    evaluate_cases: Callable[[Path], object],
    task_id: str = "",
) -> dict[str, Any]:
    """Evaluate and aggregate one formal task without per-field partial credit."""
    definition = validate_case_manifest(manifest, task_id=task_id)
    raw_observations = evaluate_cases(workspace)
    if not isinstance(raw_observations, Mapping):
        raise TypeError("evaluate_cases must return a mapping keyed by case id")
    # Legacy case adapters historically caught failures in their relocated
    # private evaluator and copied ``private_error`` into every failed business
    # observation and the zero-weight safety gate.  Treat that marker as what
    # it is: a grader contract failure.  The outer ``safe_score_workspace``
    # boundary will still return score zero, but it will no longer attribute a
    # broken evaluator to agent safety behavior.
    private_errors = sorted(
        {
            str(detail.get("private_error") or "").strip()
            for value in raw_observations.values()
            if isinstance(value, Mapping)
            and isinstance((detail := value.get("detail")), Mapping)
            and str(detail.get("private_error") or "").strip()
        }
    )
    if private_errors:
        raise RuntimeError(
            "private evaluator contract failed: " + "; ".join(private_errors)
        )
    expected_ids = {case["id"] for case in definition["cases"]}
    extra_ids = sorted(str(key) for key in set(raw_observations) - expected_ids)
    if extra_ids:
        raise ValueError(f"case evaluator returned undeclared cases: {extra_ids}")

    checks: list[dict[str, Any]] = []
    score = 0.0
    failed_core: list[str] = []
    failed_gates: list[str] = []
    for case in definition["cases"]:
        case_id = case["id"]
        if case_id in raw_observations:
            observation = _normalize_observation(case_id, raw_observations[case_id])
        else:
            observation = {
                "pass": False,
                "detail": "task evaluator did not return this declared case",
            }
        passed = observation["pass"]
        if passed:
            score += case["weight"]
        elif case["core"]:
            failed_core.append(case_id)
        if case["gate"] and not passed:
            failed_gates.append(case_id)
        checks.append(
            {
                "id": f"case:{case_id}",
                "label": case["title"],
                "pass": passed,
                "weight": case["weight"],
                "core": case["core"],
                "gate": case["gate"],
                "detail": observation["detail"],
            }
        )

    weighted_score = round(score, 4)
    if failed_gates:
        score = 0.0
    score = round(score, 4)
    # Core is a semantic requirement, not a minimum block size.  Requiring
    # every individual core weight to exceed all optional credit forced tasks
    # into two or three oversized, brittle cases.  Granular business cohorts
    # may have smaller weights; optional quality can raise the numeric score,
    # but it cannot substitute for a failed core outcome in task_success.
    task_success = bool(
        score + 1e-9 >= definition["pass_threshold"]
        and not failed_gates
        and not failed_core
    )
    return {
        "task": definition["task_id"],
        "checks": checks,
        "outcome_score": score,
        "weighted_score": weighted_score,
        "task_success": task_success,
        "pass_threshold": definition["pass_threshold"],
        "failed_core_cases": failed_core,
        "failed_gates": failed_gates,
        "case_contract_version": CASE_SCHEMA_VERSION,
    }
