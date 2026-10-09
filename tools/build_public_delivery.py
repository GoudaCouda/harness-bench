#!/usr/bin/env python3
"""Build a deterministic, self-contained public result delivery.

The input must be the allowlisted ``summary.json`` produced by
``export_public_summary.py``.  This tool never reads private task results or a
run directory: every derivative is computed from that one public snapshot.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

from export_public_summary import (
    ISOLATION_FIELDS,
    TASK_FIELDS,
    TOP_LEVEL_FIELDS,
    reject_invalidated_summary,
    sensitive_locations,
)


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_BUILDER = ROOT / "tools" / "build_standalone_dashboard.py"
CANONICAL_SUITE_MANIFEST = ROOT / "catalog" / "suite.yaml"
CURRENT_MAIN_SUITE_SIZE = 274
TERMINAL_STATUSES = {
    "completed",
    "protocol_error",
    "model_error",
    "timeout",
    "infrastructure_error",
}
SCOREABLE_STATUSES = TERMINAL_STATUSES - {"infrastructure_error"}
ALL_STATUSES = (
    "not_selected",
    "queued",
    "running",
    "completed",
    "protocol_error",
    "model_error",
    "timeout",
    "infrastructure_error",
)
ARTIFACT_FIELDS = {
    "declared",
    "present",
    "missing",
    "completion_ratio",
}
DELIVERY_FILES = (
    "SYNC_REPORT.md",
    "dashboard.html",
    "statistics.json",
    "summary.json",
    "task_scores.csv",
)
SCORE_BANDS = (
    ("below_0_15", 0.0, 0.15, False),
    ("0_15_to_below_0_40", 0.15, 0.40, False),
    ("0_40_to_below_0_75", 0.40, 0.75, False),
    ("0_75_to_1_00", 0.75, 1.00, True),
)
PUBLIC_TOP_LEVEL_FIELDS = {
    *TOP_LEVEL_FIELDS,
    "counts",
    "isolation",
    "tasks",
    "public_snapshot",
}
PUBLIC_VALUE_PATTERNS = {
    "network_url": re.compile(r"(?i)\b(?:https?|ssh)://"),
    "ip_address": re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    "host_port": re.compile(
        r"(?i)\b(?:localhost|[a-z0-9][a-z0-9.-]*\.[a-z]{2,}):\d{2,5}\b"
    ),
    "absolute_unix_path": re.compile(
        r"(?<![a-z0-9._~+@%/-])/(?!/)(?:[^/\s\"'`<>{}\[\],;:]+/)*"
        r"[^/\s\"'`<>{}\[\],;:]*",
        re.IGNORECASE,
    ),
    "absolute_windows_path": re.compile(
        r"(?i)(?<![a-z0-9._~+@%/\\-])(?:[a-z]:[\\/]|\\\\[^\\/\s]+[\\/])"
    ),
    "dns_name": re.compile(
        r"(?i)(?<![a-z0-9._/-])(?:[a-z0-9-]+\.)+"
        r"(?:internal|local|lan|svc|cluster\.local)(?![a-z0-9.-])"
    ),
    "credential": re.compile(
        r"(?i)(?:github_pat_|gh[pousr]_|bearer\s+|"
        r"(?:api[_ -]?key|access[_ -]?token|password|credential)"
        r"\s*[:=])"
    ),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "internal_host": re.compile(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:internal|local|lan|corp|intranet)\b"),
}


def _number(value: Any, *, label: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must be a finite number")
    return numeric


def _nonnegative_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _public_string(value: Any, *, label: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ValueError(f"{label} must be {qualifier}")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} contains control characters")
    return value


def _unsafe_value_locations(value: Any, path: str = "$") -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for index, child in enumerate(value.values()):
            findings.extend(_unsafe_value_locations(child, f"{path}.<value:{index}>"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_unsafe_value_locations(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for label, pattern in PUBLIC_VALUE_PATTERNS.items():
            if pattern.search(value):
                findings.append((path, label))
    return sorted(set(findings))


def _safe_artifact_path(value: Any, *, label: str) -> str:
    path = _public_string(value, label=label)
    pure = PurePosixPath(path)
    if pure.is_absolute() or "\\" in path or ".." in pure.parts or path in {".", ""}:
        raise ValueError(f"{label} must be a relative workspace artifact path")
    return path


def _validate_artifacts(value: Any, *, task_path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{task_path}.required_artifacts must be an object or null")
    extras = sorted(set(value) - ARTIFACT_FIELDS)
    if extras:
        raise ValueError(f"{task_path}.required_artifacts contains non-public fields")

    normalized: dict[str, Any] = {}
    for field in ("declared", "present", "missing"):
        raw = value.get(field, [])
        if not isinstance(raw, list):
            raise ValueError(f"{task_path}.required_artifacts.{field} must be a list")
        paths = [
            _safe_artifact_path(
                item,
                label=f"{task_path}.required_artifacts.{field}[{index}]",
            )
            for index, item in enumerate(raw)
        ]
        if len(paths) != len(set(paths)):
            raise ValueError(
                f"{task_path}.required_artifacts.{field} contains duplicates"
            )
        normalized[field] = paths

    declared = set(normalized["declared"])
    present = set(normalized["present"])
    missing = set(normalized["missing"])
    if not present <= declared or not missing <= declared:
        raise ValueError(
            f"{task_path}.required_artifacts references an undeclared artifact"
        )
    if present & missing:
        raise ValueError(
            f"{task_path}.required_artifacts marks an artifact present and missing"
        )
    if present | missing != declared:
        raise ValueError(
            f"{task_path}.required_artifacts does not account for every "
            "declared artifact"
        )

    completion_ratio = value.get("completion_ratio")
    if completion_ratio is None:
        if declared:
            raise ValueError(
                f"{task_path}.required_artifacts.completion_ratio is required"
            )
        normalized["completion_ratio"] = None
    else:
        ratio = _number(
            completion_ratio,
            label=f"{task_path}.required_artifacts.completion_ratio",
        )
        assert ratio is not None
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(
                f"{task_path}.required_artifacts.completion_ratio must be in [0, 1]"
            )
        expected_ratio = len(present) / len(declared) if declared else None
        if expected_ratio is None or not math.isclose(
            ratio, expected_ratio, abs_tol=0.0001
        ):
            raise ValueError(
                f"{task_path}.required_artifacts.completion_ratio is inconsistent"
            )
        normalized["completion_ratio"] = ratio
    return normalized


def _rounded(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def _mean(values: list[float]) -> float | None:
    return _rounded(statistics.mean(values)) if values else None


def _median(values: list[float]) -> float | None:
    return _rounded(statistics.median(values)) if values else None


def _close_to_summary(actual: float | None, declared: Any, *, label: str) -> None:
    if actual is None:
        if declared is not None:
            raise ValueError(f"{label} must be null for an unscored snapshot")
        return
    numeric = _number(declared, label=label)
    assert numeric is not None
    if not math.isclose(round(actual, 4), numeric, abs_tol=0.0001):
        raise ValueError(f"{label} is inconsistent with task rows")


def validate_public_summary(raw: Any) -> dict[str, Any]:
    """Validate and normalize one already-redacted public summary."""
    if not isinstance(raw, dict):
        raise ValueError("summary must contain one JSON object")
    extras = sorted(set(raw) - PUBLIC_TOP_LEVEL_FIELDS)
    if extras:
        raise ValueError("summary contains non-public fields")
    if raw.get("public_snapshot") is not True:
        raise ValueError("summary.public_snapshot must be true")

    findings = sorted(set(sensitive_locations(raw)) | set(_unsafe_value_locations(raw)))
    if findings:
        locations = ", ".join(f"{path} ({kind})" for path, kind in findings)
        raise ValueError(f"summary contains unsafe public values at: {locations}")

    for field in ("benchmark", "suite", "run_id", "model", "harness", "grading"):
        _public_string(raw.get(field), label=f"summary.{field}")
    if raw["benchmark"] != "HarnessBench":
        raise ValueError("summary.benchmark must be HarnessBench")
    if raw["grading"] not in {
        "oracle_only",
        "deterministic_oracle_with_bounded_semantic_fallback",
    }:
        raise ValueError("summary.grading uses an unsupported scoring protocol")

    suite_size = _nonnegative_integer(raw.get("suite_size"), label="summary.suite_size")
    selected_count = _nonnegative_integer(
        raw.get("selected_count"), label="summary.selected_count"
    )
    completed_count = _nonnegative_integer(
        raw.get("completed_count"), label="summary.completed_count"
    )
    progress = _number(raw.get("progress"), label="summary.progress")
    assert progress is not None
    if not 0.0 <= progress <= 1.0:
        raise ValueError("summary.progress must be in [0, 1]")
    for field in ("eta_sec", "updated_epoch"):
        if field not in raw:
            continue
        value = _number(
            raw[field],
            label=f"summary.{field}",
            allow_none=field == "eta_sec",
        )
        if value is not None and value < 0:
            raise ValueError(f"summary.{field} must be non-negative")

    tasks = raw.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("summary.tasks must be a list")
    if len(tasks) != suite_size:
        raise ValueError("summary.suite_size does not match task row count")

    normalized_tasks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, task in enumerate(tasks):
        task_path = f"summary.tasks[{index}]"
        if not isinstance(task, dict):
            raise ValueError(f"{task_path} must be an object")
        extras = sorted(set(task) - set(TASK_FIELDS))
        if extras:
            raise ValueError(f"{task_path} contains non-public fields")
        normalized = dict(task)
        task_id = _public_string(task.get("task_id"), label=f"{task_path}.task_id")
        if task_id in seen_ids:
            raise ValueError("summary.tasks contains a duplicate task_id")
        seen_ids.add(task_id)
        for field in ("title", "domain", "difficulty", "status"):
            _public_string(task.get(field), label=f"{task_path}.{field}")
        status = task["status"]
        if status not in ALL_STATUSES:
            raise ValueError(f"{task_path}.status is unsupported")

        score = _number(
            task.get("outcome_score"),
            label=f"{task_path}.outcome_score",
            allow_none=True,
        )
        if score is not None and not 0.0 <= score <= 1.0:
            raise ValueError(f"{task_path}.outcome_score must be in [0, 1]")
        if status in {"not_selected", "queued", "running"} and score is not None:
            raise ValueError(f"{task_path} has a score before terminal completion")
        normalized["outcome_score"] = score
        task_success = task.get("task_success")
        if task_success is not None and not isinstance(task_success, bool):
            raise ValueError(f"{task_path}.task_success must be boolean or null")
        if status in {"not_selected", "queued", "running"} and task_success is not None:
            raise ValueError(f"{task_path} has task_success before terminal completion")
        normalized["task_success"] = task_success
        safety_gate_failed = task.get("safety_gate_failed", False)
        if not isinstance(safety_gate_failed, bool):
            raise ValueError(f"{task_path}.safety_gate_failed must be boolean")
        failed_gate_count = _nonnegative_integer(
            task.get("failed_gate_count", 0),
            label=f"{task_path}.failed_gate_count",
        )
        failed_core_count = _nonnegative_integer(
            task.get("failed_core_count", 0),
            label=f"{task_path}.failed_core_count",
        )
        if safety_gate_failed != (failed_gate_count > 0):
            raise ValueError(
                f"{task_path}.safety_gate_failed disagrees with failed_gate_count"
            )
        normalized["safety_gate_failed"] = safety_gate_failed
        normalized["failed_gate_count"] = failed_gate_count
        normalized["failed_core_count"] = failed_core_count
        normalized["required_artifacts"] = _validate_artifacts(
            task.get("required_artifacts"),
            task_path=task_path,
        )

        review_flag = task.get("review_flag")
        if review_flag is None:
            normalized["review_flag"] = ""
        else:
            normalized["review_flag"] = _public_string(
                review_flag,
                label=f"{task_path}.review_flag",
                allow_empty=True,
            )
        for field in ("tool_calls", "tool_failures"):
            value = task.get(field)
            if value is not None:
                normalized[field] = _nonnegative_integer(
                    value, label=f"{task_path}.{field}"
                )
        elapsed = _number(
            task.get("elapsed_sec"),
            label=f"{task_path}.elapsed_sec",
            allow_none=True,
        )
        if elapsed is not None and elapsed < 0:
            raise ValueError(f"{task_path}.elapsed_sec must be non-negative")
        normalized["elapsed_sec"] = elapsed
        normalized_tasks.append(normalized)

    isolation = raw.get("isolation")
    if isolation is not None:
        if not isinstance(isolation, dict):
            raise ValueError("summary.isolation must be an object")
        extras = sorted(set(isolation) - set(ISOLATION_FIELDS))
        if extras:
            raise ValueError("summary.isolation contains non-public fields")
        for field in (
            "level",
            "engine",
            "server_version",
            "default_runtime",
            "network_policy",
        ):
            if field in isolation:
                _public_string(
                    isolation[field],
                    label=f"summary.isolation.{field}",
                )
        if "rootless" in isolation and not isinstance(isolation["rootless"], bool):
            raise ValueError("summary.isolation.rootless must be boolean")

    derived_status = Counter(task["status"] for task in normalized_tasks)
    declared_counts = raw.get("counts")
    if not isinstance(declared_counts, dict):
        raise ValueError("summary.counts must be an object")
    if set(declared_counts) != set(ALL_STATUSES):
        raise ValueError("summary.counts must contain exactly the supported statuses")
    for status in ALL_STATUSES:
        declared = _nonnegative_integer(
            declared_counts[status], label=f"summary.counts.{status}"
        )
        if declared != derived_status[status]:
            raise ValueError(f"summary.counts.{status} is inconsistent with task rows")

    selected = [task for task in normalized_tasks if task["status"] != "not_selected"]
    terminal = [task for task in selected if task["status"] in TERMINAL_STATUSES]
    scores = [
        float(task["outcome_score"])
        for task in selected
        if task["status"] in SCOREABLE_STATUSES
        if task["outcome_score"] is not None
    ]
    if selected_count != len(selected):
        raise ValueError("summary.selected_count is inconsistent with task rows")
    if completed_count != len(terminal):
        raise ValueError("summary.completed_count is inconsistent with task rows")
    expected_progress = len(terminal) / len(selected) if selected else 1.0
    if not math.isclose(round(expected_progress, 4), progress, abs_tol=0.0001):
        raise ValueError("summary.progress is inconsistent with task rows")
    _close_to_summary(
        statistics.mean(scores) if scores else None,
        raw.get("mean_oracle_completed"),
        label="summary.mean_oracle_completed",
    )
    strict_results = [
        bool(task["task_success"])
        for task in selected
        if task["status"] in SCOREABLE_STATUSES
        if isinstance(task.get("task_success"), bool)
    ]
    if "strict_pass_evaluated_count" in raw:
        if _nonnegative_integer(
            raw["strict_pass_evaluated_count"],
            label="summary.strict_pass_evaluated_count",
        ) != len(strict_results):
            raise ValueError(
                "summary.strict_pass_evaluated_count is inconsistent with task rows"
            )
    if "strict_passed_count" in raw:
        if _nonnegative_integer(
            raw["strict_passed_count"],
            label="summary.strict_passed_count",
        ) != sum(strict_results):
            raise ValueError(
                "summary.strict_passed_count is inconsistent with task rows"
            )
    if "pass_rate_completed" in raw:
        _close_to_summary(
            sum(strict_results) / len(strict_results) if strict_results else None,
            raw.get("pass_rate_completed"),
            label="summary.pass_rate_completed",
        )
    safety_rows = [task for task in selected if task["status"] in SCOREABLE_STATUSES]
    safety_gate_failed_count = sum(task["safety_gate_failed"] for task in safety_rows)
    failed_gate_total = sum(task["failed_gate_count"] for task in safety_rows)
    failed_core_total = sum(task["failed_core_count"] for task in safety_rows)
    expected_safety_rate = (
        safety_gate_failed_count / len(safety_rows) if safety_rows else None
    )
    integer_safety_metrics = {
        "safety_gate_evaluated_count": len(safety_rows),
        "safety_gate_failed_count": safety_gate_failed_count,
        "failed_gate_total": failed_gate_total,
        "failed_core_total": failed_core_total,
    }
    for field, expected in integer_safety_metrics.items():
        if (
            field in raw
            and _nonnegative_integer(raw[field], label=f"summary.{field}") != expected
        ):
            raise ValueError(f"summary.{field} is inconsistent with task rows")
    if "safety_gate_failure_rate" in raw:
        _close_to_summary(
            expected_safety_rate,
            raw.get("safety_gate_failure_rate"),
            label="summary.safety_gate_failure_rate",
        )

    complete_without_infra = (
        len(terminal) == len(selected)
        and derived_status["infrastructure_error"] == 0
        and bool(selected)
    )
    expected_headline = sum(scores) / len(selected) if complete_without_infra else None
    _close_to_summary(
        expected_headline,
        raw.get("headline_oracle_score"),
        label="summary.headline_oracle_score",
    )
    if "headline_task_success_rate" in raw:
        expected_task_success_headline = (
            sum(strict_results) / len(selected)
            if complete_without_infra and len(strict_results) == len(selected)
            else None
        )
        _close_to_summary(
            expected_task_success_headline,
            raw.get("headline_task_success_rate"),
            label="summary.headline_task_success_rate",
        )

    normalized = dict(raw)
    normalized["tasks"] = sorted(normalized_tasks, key=lambda task: task["task_id"])
    normalized.update(integer_safety_metrics)
    normalized["safety_gate_failure_rate"] = _rounded(
        expected_safety_rate,
        digits=4,
    )
    return normalized


def canonical_suite_identity() -> dict[str, Any]:
    """Load the public canonical task-ID manifest and content-address it."""
    try:
        manifest = yaml.safe_load(CANONICAL_SUITE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("canonical suite manifest is unavailable or invalid") from exc
    if not isinstance(manifest, dict):
        raise ValueError("canonical suite manifest must be an object")
    task_ids = manifest.get("task_ids")
    if (
        manifest.get("suite") != "main"
        or manifest.get("suite_size") != CURRENT_MAIN_SUITE_SIZE
        or not isinstance(task_ids, list)
        or len(task_ids) != CURRENT_MAIN_SUITE_SIZE
        or not all(isinstance(task_id, str) and task_id for task_id in task_ids)
        or len(set(task_ids)) != len(task_ids)
    ):
        raise ValueError("canonical suite manifest identity is inconsistent")
    serialized_ids = ("\n".join(task_ids) + "\n").encode("utf-8")
    return {
        "suite": "main",
        "suite_size": CURRENT_MAIN_SUITE_SIZE,
        "task_ids": list(task_ids),
        "task_ids_sha256": hashlib.sha256(serialized_ids).hexdigest(),
        "hash_contract": "sha256(newline_delimited_ordered_task_ids_utf8)",
    }


def delivery_mode(
    summary: dict[str, Any],
    *,
    allow_diagnostic: bool,
) -> str:
    """Fail closed unless this is a complete current main-suite snapshot."""
    if allow_diagnostic:
        return "diagnostic"
    identity = canonical_suite_identity()
    counts = summary["counts"]
    eligible = (
        summary["suite"] == "main"
        and summary["suite_size"] == CURRENT_MAIN_SUITE_SIZE
        and [task["task_id"] for task in summary["tasks"]] == identity["task_ids"]
        and summary["selected_count"] == CURRENT_MAIN_SUITE_SIZE
        and summary["completed_count"] == CURRENT_MAIN_SUITE_SIZE
        and summary["progress"] == 1.0
        and counts["not_selected"] == 0
        and counts["queued"] == 0
        and counts["running"] == 0
        and counts["infrastructure_error"] == 0
        and summary["headline_oracle_score"] is not None
    )
    if not eligible:
        raise ValueError(
            "snapshot does not match the canonical complete main task set; "
            "use explicit diagnostic mode for a non-leaderboard bundle"
        )
    return "main_taskset_verified"


def public_delivery_summary(
    summary: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    """Attach portable publication scope before building detached artifacts."""
    identity = canonical_suite_identity()
    task_ids_match = [task["task_id"] for task in summary["tasks"]] == identity[
        "task_ids"
    ]
    publication_scope = (
        "diagnostic_non_leaderboard"
        if mode == "diagnostic"
        else "canonical_task_ids_structurally_complete_unattested"
    )
    payload = dict(summary)
    payload.update(
        {
            "source_suite": summary["suite"],
            "delivery_mode": mode,
            "publication_scope": publication_scope,
            "publication_attested": False,
            "canonical_suite_identity": {
                "suite": identity["suite"],
                "suite_size": identity["suite_size"],
                "task_ids_sha256": identity["task_ids_sha256"],
                "hash_contract": identity["hash_contract"],
                "task_ids_match": task_ids_match,
                "suite_package_hash_attested": False,
            },
        }
    )
    if mode == "diagnostic":
        payload["suite"] = "diagnostic-non-leaderboard"
        payload["headline_oracle_score"] = None
        payload["headline_task_success_rate"] = None
    return payload


def _group_statistics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    selected = [row for row in materialized if row["status"] != "not_selected"]
    terminal = [row for row in selected if row["status"] in TERMINAL_STATUSES]
    scores = [
        float(row["outcome_score"])
        for row in selected
        if row["status"] in SCOREABLE_STATUSES
        if row["outcome_score"] is not None
    ]
    strict_results = [
        bool(row["task_success"])
        for row in selected
        if row["status"] in SCOREABLE_STATUSES
        if isinstance(row.get("task_success"), bool)
    ]
    safety_rows = [row for row in selected if row["status"] in SCOREABLE_STATUSES]
    safety_failures = sum(row["safety_gate_failed"] for row in safety_rows)
    return {
        "task_count": len(materialized),
        "selected_task_count": len(selected),
        "terminal_task_count": len(terminal),
        "scored_task_count": len(scores),
        "score_sum": _rounded(sum(scores)),
        "mean_score_of_scored": _mean(scores),
        "median_score_of_scored": _median(scores),
        "strict_pass_evaluated_count": len(strict_results),
        "strict_passed_count": sum(strict_results),
        "strict_pass_rate": _mean([float(value) for value in strict_results]),
        "safety_gate_evaluated_count": len(safety_rows),
        "safety_gate_failed_count": safety_failures,
        "safety_gate_failure_rate": _mean(
            [float(row["safety_gate_failed"]) for row in safety_rows]
        ),
        "failed_gate_total": sum(row["failed_gate_count"] for row in safety_rows),
        "failed_core_total": sum(row["failed_core_count"] for row in safety_rows),
    }


def _groups(
    tasks: list[dict[str, Any]],
    field: str,
    *,
    values: Iterable[str] | None = None,
) -> dict[str, Any]:
    labels = (
        list(values)
        if values is not None
        else sorted({str(row[field]) for row in tasks})
    )
    return {
        label: _group_statistics(row for row in tasks if row[field] == label)
        for label in labels
    }


def score_band(score: float | None) -> str:
    if score is None:
        return "unscored"
    for band_id, lower, upper, upper_inclusive in SCORE_BANDS:
        if score >= lower and (score <= upper if upper_inclusive else score < upper):
            return band_id
    raise ValueError("score is outside the supported range")


def _score_for_statistics(task: dict[str, Any]) -> float | None:
    value = task["outcome_score"]
    if task["status"] not in SCOREABLE_STATUSES or value is None:
        return None
    return float(value)


def build_statistics(
    summary: dict[str, Any],
    *,
    mode: str = "diagnostic",
) -> dict[str, Any]:
    tasks = list(summary["tasks"])
    identity = canonical_suite_identity()
    task_ids_match = [task["task_id"] for task in tasks] == identity["task_ids"]
    publication_scope = (
        "diagnostic_non_leaderboard"
        if mode == "diagnostic"
        else "canonical_task_ids_structurally_complete_unattested"
    )
    selected = [row for row in tasks if row["status"] != "not_selected"]
    terminal = [row for row in selected if row["status"] in TERMINAL_STATUSES]
    scores = [
        score for row in selected if (score := _score_for_statistics(row)) is not None
    ]
    strict_results = [
        bool(row["task_success"])
        for row in selected
        if row["status"] in SCOREABLE_STATUSES
        if isinstance(row.get("task_success"), bool)
    ]
    safety_rows = [row for row in selected if row["status"] in SCOREABLE_STATUSES]
    safety_failures = sum(row["safety_gate_failed"] for row in safety_rows)
    band_counts = Counter(score_band(_score_for_statistics(row)) for row in selected)
    band_definitions = {
        band_id: {
            "lower": lower,
            "upper": upper,
            "upper_inclusive": upper_inclusive,
        }
        for band_id, lower, upper, upper_inclusive in SCORE_BANDS
    }
    band_definitions["unscored"] = {
        "lower": None,
        "upper": None,
        "upper_inclusive": None,
    }

    review_counts = Counter(str(row.get("review_flag") or "none") for row in selected)
    artifact_rows = [
        row for row in selected if isinstance(row.get("required_artifacts"), dict)
    ]
    missing_rows = [
        row for row in artifact_rows if row["required_artifacts"]["missing"]
    ]
    missing_entries = sum(
        len(row["required_artifacts"]["missing"]) for row in missing_rows
    )

    return {
        "schema_version": 1,
        "benchmark": summary["benchmark"],
        "suite": summary["suite"],
        "run_id": summary["run_id"],
        "delivery_mode": mode,
        "publication_scope": publication_scope,
        "publication_attested": False,
        "canonical_suite_identity": {
            "suite": identity["suite"],
            "suite_size": identity["suite_size"],
            "task_ids_sha256": identity["task_ids_sha256"],
            "hash_contract": identity["hash_contract"],
            "task_ids_match": task_ids_match,
            "suite_package_hash_attested": False,
        },
        "evaluation": {
            "model": summary["model"],
            "harness": summary["harness"],
            "grading": summary["grading"],
            "score_semantics": "end_to_end_model_harness_oracle_outcome",
            "human_review": "not_performed_by_delivery_generator",
        },
        "overall": {
            "suite_size": summary["suite_size"],
            "task_rows": len(tasks),
            "selected_tasks": len(selected),
            "terminal_tasks": len(terminal),
            "scored_tasks": len(scores),
            "unscored_selected_tasks": len(selected) - len(scores),
            "score_sum": _rounded(sum(scores)),
            "mean_score_of_scored": _mean(scores),
            "median_score_of_scored": _median(scores),
            "minimum_score": _rounded(min(scores)) if scores else None,
            "maximum_score": _rounded(max(scores)) if scores else None,
            "headline_oracle_score": (
                None if mode == "diagnostic" else summary.get("headline_oracle_score")
            ),
            "headline_task_success_rate": (
                None
                if mode == "diagnostic"
                else summary.get("headline_task_success_rate")
            ),
            "strict_pass_evaluated_count": len(strict_results),
            "strict_passed_count": sum(strict_results),
            "strict_pass_rate": _mean([float(value) for value in strict_results]),
            "safety_gate_evaluated_count": len(safety_rows),
            "safety_gate_failed_count": safety_failures,
            "safety_gate_failure_rate": _mean(
                [float(row["safety_gate_failed"]) for row in safety_rows]
            ),
            "failed_gate_total": sum(row["failed_gate_count"] for row in safety_rows),
            "failed_core_total": sum(row["failed_core_count"] for row in safety_rows),
            "progress": summary["progress"],
        },
        "domain": _groups(tasks, "domain"),
        "difficulty": _groups(tasks, "difficulty"),
        "status": _groups(tasks, "status", values=ALL_STATUSES),
        "score_bands": {
            "scope": "selected_tasks",
            "selected_denominator": len(selected),
            "scored_denominator": len(scores),
            "definitions": band_definitions,
            "counts": {
                band_id: band_counts[band_id]
                for band_id in (*[row[0] for row in SCORE_BANDS], "unscored")
            },
        },
        "review_flags": {
            "scope": "selected_tasks",
            "flagged_task_count": sum(
                count for flag, count in review_counts.items() if flag != "none"
            ),
            "counts": dict(sorted(review_counts.items())),
        },
        "missing_artifacts": {
            "scope": "selected_tasks",
            "tasks_with_artifact_report": len(artifact_rows),
            "tasks_without_artifact_report": len(selected) - len(artifact_rows),
            "tasks_with_missing_artifacts": len(missing_rows),
            "missing_artifact_entries": missing_entries,
            "task_ids_with_missing_artifacts": sorted(
                row["task_id"] for row in missing_rows
            ),
        },
    }


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def render_task_scores(
    summary: dict[str, Any],
    *,
    mode: str,
) -> str:
    publication_scope = (
        "diagnostic_non_leaderboard"
        if mode == "diagnostic"
        else "canonical_task_ids_structurally_complete_unattested"
    )
    fields = (
        "delivery_mode",
        "publication_scope",
        "task_id",
        "title",
        "domain",
        "difficulty",
        "status",
        "outcome_score",
        "task_success",
        "safety_gate_failed",
        "failed_gate_count",
        "failed_core_count",
        "score_band",
        "artifact_declared_count",
        "artifact_present_count",
        "artifact_missing_count",
        "artifact_completion_ratio",
        "tool_calls",
        "tool_failures",
        "elapsed_sec",
        "review_flag",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for task in summary["tasks"]:
        artifacts = task.get("required_artifacts")
        writer.writerow(
            {
                "delivery_mode": mode,
                "publication_scope": publication_scope,
                "task_id": _csv_value(task["task_id"]),
                "title": _csv_value(task["title"]),
                "domain": _csv_value(task["domain"]),
                "difficulty": _csv_value(task["difficulty"]),
                "status": task["status"],
                "outcome_score": (
                    "" if task["outcome_score"] is None else task["outcome_score"]
                ),
                "task_success": (
                    "" if task.get("task_success") is None else task["task_success"]
                ),
                "safety_gate_failed": task["safety_gate_failed"],
                "failed_gate_count": task["failed_gate_count"],
                "failed_core_count": task["failed_core_count"],
                "score_band": score_band(_score_for_statistics(task)),
                "artifact_declared_count": (
                    "" if artifacts is None else len(artifacts["declared"])
                ),
                "artifact_present_count": (
                    "" if artifacts is None else len(artifacts["present"])
                ),
                "artifact_missing_count": (
                    "" if artifacts is None else len(artifacts["missing"])
                ),
                "artifact_completion_ratio": (
                    "" if artifacts is None else artifacts["completion_ratio"]
                ),
                "tool_calls": task.get("tool_calls"),
                "tool_failures": task.get("tool_failures"),
                "elapsed_sec": task.get("elapsed_sec"),
                "review_flag": _csv_value(task.get("review_flag") or ""),
            }
        )
    return output.getvalue()


def _markdown_table(rows: Iterable[tuple[str, Any]]) -> str:
    lines = ["| Metric | Value |", "|---|---:|"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(lines)


def _markdown_inline(value: str) -> str:
    """Render one untrusted scalar as inert Markdown/HTML inline text."""
    escaped = html.escape(value, quote=True)
    return re.sub(r"([\\`*_[\]{}()#+.!|<>-])", r"\\\1", escaped)


def render_sync_report(
    summary: dict[str, Any],
    statistics_payload: dict[str, Any],
    *,
    mode: str,
) -> str:
    overall = statistics_payload["overall"]
    missing = statistics_payload["missing_artifacts"]
    review = statistics_payload["review_flags"]
    identity = statistics_payload["canonical_suite_identity"]
    normalized_model = re.sub(r"[^a-z0-9]", "", summary["model"].lower())
    family_note = (
        "- Friendly family label: **Gemma4-31B + OpenClaw**.\n"
        if "gemma4" in normalized_model
        and "31b" in normalized_model
        and "openclaw" in summary["harness"].lower()
        else ""
    )
    scope_notice = (
        "> **DIAGNOSTIC SNAPSHOT — NOT LEADERBOARD ELIGIBLE.** "
        "This bundle was generated with the explicit diagnostic override.\n\n"
        if mode == "diagnostic"
        else "> **CANONICAL MAIN TASK-SET MATCH.** The ordered 177 task IDs and "
        "structural completeness checks passed. This artifact does not attest "
        "the suite package hash, so it is not by itself proof of official "
        "leaderboard publication eligibility.\n\n"
    )
    scoring_note = (
        "task-specific deterministic Oracle; no LLM rubric contributes"
        if summary["grading"] == "oracle_only"
        else "deterministic Oracle plus an explicitly bounded semantic case fallback"
    )
    return f"""# HarnessBench public delivery sync report

{scope_notice}## Evaluation semantics

- Exact model ID: **{_markdown_inline(summary["model"])}**.
- Exact harness ID: **{_markdown_inline(summary["harness"])}**.
{family_note}- Scoring: **{scoring_note}** (`grading={summary["grading"]}`).
- Interpretation: this is an end-to-end model + harness + tool/workspace outcome. It is **not a pure base-model score**.
- Human review: this delivery generator performs **no human review or adjudication**. `review_flag` values are automated triage signals, not human approvals or findings.

## Snapshot consistency

All run-specific data in this delivery were derived only from the redacted public
`summary.json`. The dashboard also uses the repository's checked-in standalone
template, and the other artifacts use this generator. The task ledger, declared
aggregate counts, progress, mean score, and headline score were checked against one
another before generation.

- Canonical ordered task-ID manifest SHA-256: `{identity["task_ids_sha256"]}`
- Task IDs match that manifest: `{str(identity["task_ids_match"]).lower()}`
- Suite package hash attested here: `false`

{
        _markdown_table(
            (
                ("Suite task rows", overall["task_rows"]),
                ("Selected tasks", overall["selected_tasks"]),
                ("Terminal tasks", overall["terminal_tasks"]),
                ("Scored tasks", overall["scored_tasks"]),
                ("Mean of scored tasks", overall["mean_score_of_scored"]),
                ("Headline Oracle score", overall["headline_oracle_score"]),
                ("Safety-gate failures", overall["safety_gate_failed_count"]),
                (
                    "Safety-gate failure rate",
                    overall["safety_gate_failure_rate"],
                ),
                ("Failed core cases", overall["failed_core_total"]),
                ("Automated review flags", review["flagged_task_count"]),
                (
                    "Tasks with missing artifacts",
                    missing["tasks_with_missing_artifacts"],
                ),
                ("Missing artifact entries", missing["missing_artifact_entries"]),
            )
        )
    }

## Delivery files

- `summary.json`: validated and canonically formatted copy of the redacted source snapshot.
- `statistics.json`: deterministic aggregates by overall, domain, difficulty, status, score band, review flag, and artifact health.
- `task_scores.csv`: one public ledger row per task; artifact paths and private evidence are not included.
- `dashboard.html`: self-contained offline dashboard built by the repository's existing dashboard builder.
- `SHA256SUMS`: SHA-256 checksums for the summary, statistics, CSV, dashboard, and this report; the checksum manifest does not checksum itself.
"""


def _json_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_checksums(root: Path) -> str:
    return "".join(f"{_sha256(root / name)}  {name}\n" for name in DELIVERY_FILES)


def _assert_generated_files_safe(root: Path) -> None:
    # HTML necessarily contains relative closing tags and asset paths, so this
    # final defense checks only machine-specific or credential-bearing forms.
    generated_patterns = {
        key: pattern
        for key, pattern in PUBLIC_VALUE_PATTERNS.items()
        if key != "absolute_unix_path"
    }
    generated_patterns["machine_path"] = re.compile(
        r"(?i)(?:/home/|/var/tmp/|/workspace/|/users/|"
        r"[a-z]:\\users\\|/mnt/)"
    )
    for path in sorted(item for item in root.iterdir() if item.is_file()):
        text = path.read_text(encoding="utf-8")
        for label, pattern in generated_patterns.items():
            if pattern.search(text):
                raise ValueError(
                    f"generated public artifact {path.name} contains {label}"
                )


def _annotate_dashboard(path: Path, *, mode: str) -> None:
    if mode == "diagnostic":
        title = "DIAGNOSTIC SNAPSHOT — NOT LEADERBOARD ELIGIBLE"
        detail = (
            "This is an explicitly scoped diagnostic bundle. "
            "Its headline leaderboard score is suppressed."
        )
    else:
        title = "CANONICAL MAIN TASK-SET MATCH"
        detail = (
            "The ordered 177 task IDs match the public manifest. "
            "Suite package hash attestation is outside this artifact."
        )
    banner = (
        '<aside id="publication-scope" role="alert" '
        'style="margin:16px;padding:14px;border:2px solid #b45309;'
        'background:#fff7ed;color:#7c2d12;font:600 14px/1.4 sans-serif">'
        f"<strong>{title}</strong><br>{detail}</aside>"
    )
    document = path.read_text(encoding="utf-8")
    if "<body>" not in document:
        raise ValueError("standalone dashboard template has no body element")
    path.write_text(
        document.replace("<body>", f"<body>\n{banner}", 1),
        encoding="utf-8",
    )


def build_public_delivery(
    summary_path: Path,
    output: Path,
    *,
    allow_diagnostic: bool = False,
) -> dict[str, Any]:
    """Generate a complete delivery directory without reading the run tree."""
    summary_path = summary_path.expanduser().resolve()
    output = output.expanduser().resolve()
    if not summary_path.is_file():
        raise ValueError("public summary input does not exist")
    reject_invalidated_summary(summary_path)
    if output.exists():
        raise ValueError("output directory must not already exist")
    try:
        raw = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("public summary input is not valid UTF-8 JSON") from exc
    summary = validate_public_summary(raw)
    mode = delivery_mode(summary, allow_diagnostic=allow_diagnostic)
    delivery_summary = public_delivery_summary(summary, mode=mode)
    statistics_payload = build_statistics(summary, mode=mode)
    task_scores = render_task_scores(summary, mode=mode)
    sync_report = render_sync_report(summary, statistics_payload, mode=mode)

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        (staging / "summary.json").write_text(
            _json_text(delivery_summary),
            encoding="utf-8",
        )
        (staging / "statistics.json").write_text(
            _json_text(statistics_payload),
            encoding="utf-8",
        )
        (staging / "task_scores.csv").write_text(task_scores, encoding="utf-8")
        (staging / "SYNC_REPORT.md").write_text(sync_report, encoding="utf-8")
        subprocess.run(
            [
                sys.executable,
                str(DASHBOARD_BUILDER),
                str(staging / "summary.json"),
                str(staging / "dashboard.html"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        _annotate_dashboard(staging / "dashboard.html", mode=mode)
        (staging / "SHA256SUMS").write_text(
            _render_checksums(staging),
            encoding="utf-8",
        )
        _assert_generated_files_safe(staging)
        os.replace(staging, output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "task_rows": len(summary["tasks"]),
        "selected_tasks": statistics_payload["overall"]["selected_tasks"],
        "terminal_tasks": statistics_payload["overall"]["terminal_tasks"],
        "delivery_mode": mode,
        "files": [*DELIVERY_FILES, "SHA256SUMS"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build public HarnessBench statistics and delivery artifacts."
    )
    parser.add_argument("public_summary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--allow-diagnostic",
        action="store_true",
        help="explicitly build a visibly non-leaderboard subset/incomplete bundle",
    )
    args = parser.parse_args()
    result = build_public_delivery(
        args.public_summary,
        args.output,
        allow_diagnostic=args.allow_diagnostic,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
