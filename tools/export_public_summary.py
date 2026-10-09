#!/usr/bin/env python3
"""Export the minimal, shareable subset of a HarnessBench run summary."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


INVALIDATION_MARKER = "RUN_INVALIDATED.json"
INVALIDATION_MARKERS = (INVALIDATION_MARKER, "INVALIDATED.json")
TOP_LEVEL_FIELDS = (
    "benchmark",
    "suite",
    "suite_size",
    "run_id",
    "model",
    "harness",
    "grading",
    "selected_count",
    "completed_count",
    "progress",
    "mean_oracle_completed",
    "pass_rate_completed",
    "strict_pass_evaluated_count",
    "strict_passed_count",
    "safety_gate_evaluated_count",
    "safety_gate_failed_count",
    "safety_gate_failure_rate",
    "failed_gate_total",
    "failed_core_total",
    "headline_task_success_rate",
    "headline_oracle_score",
    "eta_sec",
    "updated_epoch",
)
COUNT_FIELDS = (
    "not_selected",
    "queued",
    "running",
    "completed",
    "protocol_error",
    "model_error",
    "timeout",
    "infrastructure_error",
)
TASK_FIELDS = (
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
    "required_artifacts",
    "tool_calls",
    "tool_failures",
    "elapsed_sec",
    "review_flag",
)
REQUIRED_ARTIFACT_LIST_FIELDS = (
    "declared",
    "present",
    "missing",
)
ISOLATION_FIELDS = (
    "level",
    "engine",
    "server_version",
    "rootless",
    "default_runtime",
    "network_policy",
)
SCOREABLE_STATUSES = {
    "completed",
    "protocol_error",
    "model_error",
    "timeout",
}
SENSITIVE_VALUE_PATTERNS = {
    "url": re.compile(r"(?i)(?:\b[a-z][a-z0-9+.-]{1,31}://|\bwww\.)"),
    "private_ipv4": re.compile(
        r"\b(?:0\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|169\.254\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}"
        r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
    ),
    "private_ipv6": re.compile(
        r"(?i)(?<![0-9a-f:])(?:::1|f[cd][0-9a-f]{0,2}:|fe[89ab][0-9a-f]?:)"
    ),
    "absolute_posix_path": re.compile(
        r"""(?:^|[\s"'`=:(])/(?!/)[a-z0-9._~-]+"""
        r"""(?:/[a-z0-9._~+@%=-]+)*""",
        re.IGNORECASE,
    ),
    "absolute_windows_path": re.compile(
        r"""(?i)(?:^|[\s"'`=(])(?:[a-z]:[\\/]|\\\\[^\\/\s]+[\\/])"""
    ),
    "credential": re.compile(
        r"(?i)(?:github_pat_|ghp_|gho_|ghu_|ghs_|ghr_|bearer\s+"
        r"|api[_-]?key\s*[:=]|access[_-]?token\s*[:=])"
    ),
    "local_host": re.compile(r"(?i)\blocalhost\b"),
    "internal_host": re.compile(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:internal|local|lan|corp|intranet)\b"),
}


def reject_invalidated_summary(summary: Path) -> None:
    """Do not publish a snapshot from an explicitly retired run."""
    candidate = summary.expanduser().resolve().parent
    while True:
        for marker_name in INVALIDATION_MARKERS:
            try:
                (candidate / marker_name).lstat()
            except FileNotFoundError:
                continue
            except OSError:
                raise ValueError("run invalidation state cannot be verified") from None
            raise ValueError("run is explicitly invalidated")
        if candidate == candidate.parent:
            break
        candidate = candidate.parent


def copy_scalar_fields(
    source: dict[str, Any],
    fields: tuple[str, ...],
    *,
    context: str,
) -> dict[str, Any]:
    """Copy only JSON scalar values, preventing containers from hiding fields."""
    copied: dict[str, Any] = {}
    for field in fields:
        if field not in source:
            continue
        value = source[field]
        if isinstance(value, (dict, list)):
            raise ValueError(f"{context}.{field} must be a scalar")
        copied[field] = value
    return copied


def public_required_artifacts(value: Any, *, context: str) -> dict[str, Any] | None:
    """Keep only dashboard-safe artifact counts and relative artifact names."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object or null")

    exported: dict[str, Any] = {}
    for field in REQUIRED_ARTIFACT_LIST_FIELDS:
        if field not in value:
            continue
        items = value[field]
        if not isinstance(items, list) or not all(
            isinstance(item, str) for item in items
        ):
            raise ValueError(f"{context}.{field} must be a list of strings")
        exported[field] = list(items)
    if "completion_ratio" in value:
        ratio = value["completion_ratio"]
        if isinstance(ratio, (dict, list)):
            raise ValueError(f"{context}.completion_ratio must be a scalar")
        exported["completion_ratio"] = ratio
    return exported


def public_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a schema-shaped allowlist; private fields never cross this boundary."""
    exported = copy_scalar_fields(raw, TOP_LEVEL_FIELDS, context="summary")

    if "counts" in raw:
        counts = raw["counts"]
        if not isinstance(counts, dict):
            raise ValueError("summary.counts must be an object")
        exported["counts"] = copy_scalar_fields(
            counts,
            COUNT_FIELDS,
            context="summary.counts",
        )

    if "isolation" in raw:
        isolation = raw["isolation"]
        if not isinstance(isolation, dict):
            raise ValueError("summary.isolation must be an object")
        exported["isolation"] = copy_scalar_fields(
            isolation,
            ISOLATION_FIELDS,
            context="summary.isolation",
        )

    tasks = raw.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("summary.tasks must be a list")
    exported["tasks"] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"summary.tasks[{index}] must be an object")
        public_task = copy_scalar_fields(
            task,
            tuple(field for field in TASK_FIELDS if field != "required_artifacts"),
            context=f"summary.tasks[{index}]",
        )
        if "required_artifacts" in task:
            public_task["required_artifacts"] = public_required_artifacts(
                task["required_artifacts"],
                context=f"summary.tasks[{index}].required_artifacts",
            )
        public_task.setdefault("safety_gate_failed", False)
        public_task.setdefault("failed_gate_count", 0)
        public_task.setdefault("failed_core_count", 0)
        exported["tasks"].append(public_task)
    scoreable = [
        task for task in exported["tasks"] if task.get("status") in SCOREABLE_STATUSES
    ]
    safety_failures = sum(task["safety_gate_failed"] is True for task in scoreable)
    exported.setdefault("safety_gate_evaluated_count", len(scoreable))
    exported.setdefault("safety_gate_failed_count", safety_failures)
    exported.setdefault(
        "safety_gate_failure_rate",
        round(safety_failures / len(scoreable), 4) if scoreable else None,
    )
    exported.setdefault(
        "failed_gate_total",
        sum(
            value
            for task in scoreable
            if type(value := task.get("failed_gate_count")) is int and value >= 0
        ),
    )
    exported.setdefault(
        "failed_core_total",
        sum(
            value
            for task in scoreable
            if type(value := task.get("failed_core_count")) is int and value >= 0
        ),
    )
    exported["public_snapshot"] = True
    return exported


def sensitive_locations(value: Any, path: str = "$") -> list[tuple[str, str]]:
    """Find unsafe value classes without returning or logging the values."""
    findings: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for index, (key, child) in enumerate(value.items()):
            if isinstance(key, str):
                for label, pattern in SENSITIVE_VALUE_PATTERNS.items():
                    if pattern.search(key):
                        findings.append((f"{path}.<key:{index}>", f"{label}_key"))
            findings.extend(sensitive_locations(child, f"{path}.<value:{index}>"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(sensitive_locations(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for label, pattern in SENSITIVE_VALUE_PATTERNS.items():
            if pattern.search(value):
                findings.append((path, label))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    reject_invalidated_summary(args.summary)
    raw = json.loads(args.summary.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("summary must contain one JSON object")
    exported = public_summary(raw)
    findings = sensitive_locations(exported)
    if findings:
        locations = ", ".join(f"{path} ({label})" for path, label in findings)
        raise ValueError(f"public summary contains sensitive values at: {locations}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
