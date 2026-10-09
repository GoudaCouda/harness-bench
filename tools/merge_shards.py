#!/usr/bin/env python3
"""Merge disjoint benchmark shard runs into one dashboard-ready run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from harnessbench.task_sets import (  # noqa: E402
    TaskSetError,
    load_task_set,
    task_ids_sha256,
    validate_task_selection_identity,
)


TASK_IDS = {path.parent.name for path in (ROOT / "tasks").glob("*/task.yaml")}
TERMINAL = {
    "completed",
    "protocol_error",
    "model_error",
    "timeout",
    "infrastructure_error",
}
SCOREABLE = TERMINAL - {"infrastructure_error"}
MERGED_SEMANTIC_FIELDS = (
    "schema_version",
    "benchmark",
    "suite",
    "suite_size",
    "task_set",
    "selection",
    "suite_definition_sha256",
    "suite_snapshot_sha256",
    "controller_definition_sha256",
    "controller_runtime",
    "controller_runtime_id",
    "grading",
    "model",
    "model_service_id",
    "harness",
    "harness_version",
    "harness_protocol",
    "harness_profile",
    "provider_timeout_policy",
    "harness_image",
    "openclaw_image",
    "trace_complete",
    "runtime_images",
    "isolation",
    "experimental_task_environments",
    "task_environment_set_sha256",
    "environment_builder_id",
    "context_window",
    "max_agent_turns",
    "max_tokens",
    "temperature",
    "thinking",
    "timeout_override",
)
CONSISTENCY_FIELDS = (
    *MERGED_SEMANTIC_FIELDS,
    "shard_count",
)
RUN_PLAN_FIELDS = (
    "base_url",
    "data_parallel_rank",
    "workers",
    "model_service_id",
)
RUN_PLAN_IDENTITY_FIELDS = (
    "suite_definition_sha256",
    "suite_snapshot_sha256",
    "controller_definition_sha256",
    "controller_runtime_id",
    "model_service_id",
    "task_environment_set_sha256",
    "environment_builder_id",
)
INVALIDATION_MARKER = "RUN_INVALIDATED.json"
INVALIDATION_MARKERS = (INVALIDATION_MARKER, "INVALIDATED.json")


def load_summary(root: Path) -> dict[str, Any]:
    path = root / "summary.json"
    if not path.is_file():
        raise ValueError(f"missing shard summary: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def reject_invalidated_run(root: Path) -> None:
    """Refuse a shard beneath any explicitly retired run ancestor."""
    candidate = root.expanduser().resolve()
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


def load_run_plan(path: Path) -> dict[str, Any]:
    """Load one explicit shard routing plan from a JSON file."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"missing run plan: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid run plan JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("run plan must contain one JSON object")
    return payload


def semantic_value(summary: dict[str, Any], key: str) -> Any:
    """Return a merge identity, preserving strictness for legacy summaries."""
    if key == "model_service_id":
        return summary.get(key) or summary.get("base_url")
    return summary.get(key)


def compatibility_value(summary: dict[str, Any], key: str) -> Any:
    """Return the execution identity used to decide whether shards may merge.

    Docker's server patch version describes the worker host rather than the
    task container contract.  CPU workers may therefore differ only in that
    field while still providing the same isolation guarantees.  The complete
    per-shard identities remain in the merged evidence for auditability.
    """
    value = semantic_value(summary, key)
    if key == "isolation" and isinstance(value, dict):
        return {
            isolation_key: isolation_value
            for isolation_key, isolation_value in value.items()
            if isolation_key != "server_version"
        }
    return value


def summary_selection_identity(
    summary: dict[str, Any],
    *,
    source: Path,
) -> dict[str, Any] | None:
    """Validate one shard's global selection identity, preserving legacy main."""
    raw_identity = summary.get("selection")
    task_set_name = summary.get("task_set")
    if raw_identity is None:
        if task_set_name is not None:
            raise ValueError(
                f"named task-set shard has no selection identity: {source}"
            )
        return None
    try:
        identity = validate_task_selection_identity(raw_identity)
    except TaskSetError as exc:
        raise ValueError(f"invalid task selection in shard {source}: {exc}") from exc
    if identity["task_set"] != task_set_name:
        raise ValueError(
            f"task_set disagrees with selection identity in shard {source}"
        )
    return identity


def validate_frozen_task_set(
    root: Path,
    identity: dict[str, Any],
) -> Path:
    """Verify a named shard carries the exact manifest behind its identity."""
    name = str(identity["task_set"])
    catalog_dir = root / "selection" / "catalog"
    try:
        task_set = load_task_set(
            catalog_dir,
            name,
            known_task_ids=TASK_IDS,
        )
    except TaskSetError as exc:
        raise ValueError(
            f"invalid frozen task-set manifest in shard {root}: {exc}"
        ) from exc
    if task_set.manifest_sha256 != identity["manifest_sha256"]:
        raise ValueError(f"frozen task-set manifest hash mismatch in shard {root}")
    if task_set.task_count != identity["declared_count"]:
        raise ValueError(f"frozen task-set task_count mismatch in shard {root}")
    if task_ids_sha256(task_set.task_ids) != identity["task_ids_sha256"]:
        raise ValueError(f"frozen task-set membership mismatch in shard {root}")
    return task_set.source_path


def validate_controller_runtime(summary: dict[str, Any], *, source: Path) -> None:
    """Require a self-consistent, content-addressed controller runtime."""
    payload = summary.get("controller_runtime")
    runtime_id = summary.get("controller_runtime_id")
    if not isinstance(payload, dict):
        raise ValueError(f"missing controller_runtime in shard {source}")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected_id = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    if runtime_id != expected_id:
        raise ValueError(
            f"invalid controller_runtime_id in shard {source}: "
            f"expected={expected_id}, actual={runtime_id!r}"
        )


def validate_run_plan(
    run_plan: dict[str, Any],
    summaries: list[dict[str, Any]],
    *,
    declared_shards: int,
) -> None:
    """Require every shard summary to match its explicit execution route."""
    if not isinstance(run_plan, dict):
        raise ValueError("run plan must contain one JSON object")
    planned_shard_count = run_plan.get("shard_count")
    if planned_shard_count is not None and (
        type(planned_shard_count) is not int or planned_shard_count != declared_shards
    ):
        raise ValueError(
            "run plan shard_count mismatch: "
            f"expected={declared_shards}, actual={planned_shard_count!r}"
        )
    if "schema_version" in run_plan and run_plan["schema_version"] != 1:
        raise ValueError(
            f"unsupported run plan schema_version: {run_plan['schema_version']!r}"
        )
    baseline = summaries[0]
    identity_mismatches = {
        field: {
            "expected": run_plan[field],
            "actual": semantic_value(baseline, field),
        }
        for field in RUN_PLAN_IDENTITY_FIELDS
        if field in run_plan and run_plan[field] != semantic_value(baseline, field)
    }
    if "workers_total" in run_plan:
        actual_workers = sum(int(summary.get("workers") or 0) for summary in summaries)
        if run_plan["workers_total"] != actual_workers:
            identity_mismatches["workers_total"] = {
                "expected": run_plan["workers_total"],
                "actual": actual_workers,
            }
    if "runtime_images" in run_plan:
        planned_images = run_plan["runtime_images"]
        actual_images = baseline.get("runtime_images")
        if not isinstance(planned_images, dict) or not isinstance(actual_images, dict):
            identity_mismatches["runtime_images"] = {
                "expected": planned_images,
                "actual": actual_images,
            }
        else:
            missing_image_ids = sorted(
                {
                    str(image_id)
                    for image_id in planned_images.values()
                    if image_id not in actual_images.values()
                }
            )
            if missing_image_ids:
                identity_mismatches["runtime_images"] = {
                    "expected_image_ids": sorted(
                        str(image_id) for image_id in planned_images.values()
                    ),
                    "actual_image_ids": sorted(
                        str(image_id) for image_id in actual_images.values()
                    ),
                }
    if identity_mismatches:
        raise ValueError(
            "run plan execution identity mismatch: "
            + json.dumps(
                identity_mismatches,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    rows = run_plan.get("shards")
    if not isinstance(rows, list):
        raise ValueError("run plan requires a shards list")

    planned: dict[int, dict[str, Any]] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"run plan shard entry {position} must be a JSON object")
        missing_fields = [
            field for field in ("shard_index", *RUN_PLAN_FIELDS) if field not in row
        ]
        if missing_fields:
            raise ValueError(
                f"run plan shard entry {position} is missing fields: {missing_fields}"
            )
        shard_index = row["shard_index"]
        if type(shard_index) is not int:
            raise ValueError(
                f"run plan shard_index must be an integer: {shard_index!r}"
            )
        if shard_index in planned:
            raise ValueError(f"run plan contains duplicate shard_index: {shard_index}")
        if not isinstance(row["base_url"], str) or not row["base_url"]:
            raise ValueError(
                f"run plan shard {shard_index} requires a non-empty base_url"
            )
        data_parallel_rank = row["data_parallel_rank"]
        if data_parallel_rank is not None and (
            type(data_parallel_rank) is not int or data_parallel_rank < 0
        ):
            raise ValueError(
                f"run plan shard {shard_index} has an invalid data_parallel_rank"
            )
        workers = row["workers"]
        if type(workers) is not int or workers < 1:
            raise ValueError(f"run plan shard {shard_index} has invalid workers")
        model_service_id = row["model_service_id"]
        if not isinstance(model_service_id, str) or not model_service_id:
            raise ValueError(
                f"run plan shard {shard_index} requires a non-empty model_service_id"
            )
        planned[shard_index] = row

    expected_indices = set(range(declared_shards))
    if len(rows) != declared_shards or set(planned) != expected_indices:
        raise ValueError(
            "run plan shard set is not complete and unique: "
            f"declared={declared_shards}, "
            f"indices={sorted(planned)}"
        )

    summaries_by_index = {int(summary["shard_index"]): summary for summary in summaries}
    for shard_index in range(declared_shards):
        summary = summaries_by_index[shard_index]
        expected = planned[shard_index]
        mismatches = {
            field: {
                "expected": expected[field],
                "actual": summary.get(field),
            }
            for field in RUN_PLAN_FIELDS
            if summary.get(field) != expected[field]
        }
        if mismatches:
            raise ValueError(
                f"run plan mismatch for shard {shard_index}: "
                + json.dumps(
                    mismatches,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )


def validate_terminal_result(
    root: Path,
    *,
    task_id: str,
    status: str,
    summary_row: dict[str, Any],
) -> None:
    """Validate the per-task result evidence referenced by a terminal row."""
    result_path = root / "tasks" / task_id / "result.json"
    if not result_path.is_file():
        raise ValueError(f"missing terminal task result: {result_path}")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"invalid terminal task result JSON {result_path}: {exc}"
        ) from exc
    if not isinstance(result, dict):
        raise ValueError(
            f"terminal task result must contain one JSON object: {result_path}"
        )
    mismatches: dict[str, dict[str, Any]] = {
        field: {
            "expected": expected,
            "actual": result.get(field),
        }
        for field, expected in (("task_id", task_id), ("status", status))
        if result.get(field) != expected
    }
    summary_has_score = "outcome_score" in summary_row
    result_has_score = "outcome_score" in result
    summary_score = summary_row.get("outcome_score")
    result_score = result.get("outcome_score")
    scores_match = False
    if summary_has_score and result_has_score:
        if summary_score is None and result_score is None:
            scores_match = status != "completed"
        elif (
            type(summary_score) in (int, float)
            and type(result_score) in (int, float)
            and math.isfinite(float(summary_score))
            and math.isfinite(float(result_score))
        ):
            scores_match = math.isclose(
                float(summary_score),
                float(result_score),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
    if not scores_match:
        mismatches["outcome_score"] = {
            "expected": summary_score if summary_has_score else "<missing>",
            "actual": result_score if result_has_score else "<missing>",
        }
    if mismatches:
        raise ValueError(
            f"terminal task result disagrees with summary {result_path}: "
            + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
        )
    if result.get("harness") == "openclaw" and status == "completed":
        trace_integrity = result.get("trace_integrity")
        if (
            not isinstance(trace_integrity, dict)
            or trace_integrity.get("status") != "pass"
        ):
            raise ValueError(
                "completed OpenClaw result has no passing trace integrity "
                f"report: {result_path}"
            )


def merge_shard_runs(
    shard_roots: list[Path],
    *,
    output: Path,
    allow_subset: bool = False,
    allow_incomplete: bool = False,
    run_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge a complete shard set, optionally over an explicit task subset."""
    if not shard_roots:
        raise ValueError("at least one shard root is required")
    if allow_subset and allow_incomplete:
        raise ValueError("--allow-subset and --allow-incomplete are exclusive")

    roots = [path.expanduser().resolve() for path in shard_roots]
    for root in roots:
        reject_invalidated_run(root)
    summaries = [load_summary(path) for path in roots]
    for root, summary in zip(roots, summaries):
        validate_controller_runtime(summary, source=root)
    selection_identities = [
        summary_selection_identity(summary, source=root)
        for root, summary in zip(roots, summaries)
    ]
    baseline = summaries[0]
    for root, summary in zip(roots[1:], summaries[1:]):
        mismatches = {
            key: {
                "expected": compatibility_value(baseline, key),
                "actual": compatibility_value(summary, key),
            }
            for key in CONSISTENCY_FIELDS
            if compatibility_value(summary, key)
            != compatibility_value(baseline, key)
        }
        if mismatches:
            raise ValueError(
                f"incompatible shard {root}: "
                + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
            )
    selection_identity = selection_identities[0]
    frozen_task_set_paths: list[Path] = []
    if selection_identity is not None and selection_identity["mode"] == "named":
        frozen_task_set_paths = [
            validate_frozen_task_set(root, identity)
            for root, identity in zip(roots, selection_identities)
            if identity is not None
        ]
    distinct_input_base_urls = {
        str(summary.get("base_url"))
        for summary in summaries
        if summary.get("base_url") is not None
    }
    model_service_id = semantic_value(baseline, "model_service_id")
    if len(distinct_input_base_urls) > 1 and not (
        isinstance(model_service_id, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", model_service_id)
    ):
        raise ValueError(
            "different replica base_url values require a frozen sha256 model_service_id"
        )
    declared_shard_value = baseline.get("shard_count")
    if type(declared_shard_value) is not int or declared_shard_value < 1:
        raise ValueError(f"invalid declared shard_count: {declared_shard_value!r}")
    declared_shards = declared_shard_value
    shard_indices = [summary.get("shard_index") for summary in summaries]
    if (
        any(type(index) is not int for index in shard_indices)
        or declared_shards != len(summaries)
        or set(shard_indices) != set(range(declared_shards))
    ):
        raise ValueError(
            "shard set is not complete and unique: "
            f"declared={declared_shards}, indices={shard_indices}"
        )
    if run_plan is not None:
        validate_run_plan(
            run_plan,
            summaries,
            declared_shards=declared_shards,
        )

    baseline_rows = {
        str(row.get("task_id") or ""): dict(row)
        for row in baseline.get("tasks", [])
        if str(row.get("task_id") or "") in TASK_IDS
    }
    canonical_shards = {
        task_id: index % declared_shards
        for index, task_id in enumerate(sorted(TASK_IDS))
    }
    selected: dict[str, tuple[dict[str, Any], Path]] = {}
    for root, summary in zip(roots, summaries):
        shard_index = int(summary["shard_index"])
        shard_selected_count = 0
        shard_task_ids: set[str] = set()
        for row in summary.get("tasks", []):
            task_id = str(row.get("task_id") or "")
            if task_id in shard_task_ids:
                raise ValueError(f"duplicate task row in shard {root}: {task_id}")
            shard_task_ids.add(task_id)
            if row.get("status") == "not_selected":
                continue
            if task_id not in TASK_IDS:
                raise ValueError(f"shard {root} selected unknown task: {task_id}")
            if not allow_subset and canonical_shards[task_id] != shard_index:
                raise ValueError(
                    "task assigned to non-canonical shard: "
                    f"task_id={task_id}, "
                    f"expected={canonical_shards[task_id]}, "
                    f"actual={shard_index}"
                )
            shard_selected_count += 1
            if task_id in selected:
                raise ValueError(f"task appears in multiple shards: {task_id}")
            selected[task_id] = (dict(row), root)
            status = row.get("status")
            if status in TERMINAL:
                validate_terminal_result(
                    root,
                    task_id=task_id,
                    status=status,
                    summary_row=row,
                )
        declared_selected_count = int(summary.get("selected_count") or 0)
        if declared_selected_count != shard_selected_count:
            raise ValueError(
                f"selected_count mismatch in shard {root}: "
                f"declared={declared_selected_count}, "
                f"rows={shard_selected_count}"
            )

    if selection_identity is not None:
        declared_count = int(selection_identity["declared_count"])
        if len(selected) != declared_count:
            raise ValueError(
                "merged selection count does not match its global identity: "
                f"declared={declared_count}, actual={len(selected)}"
            )
        selected_hash = task_ids_sha256(selected)
        if selected_hash != selection_identity["task_ids_sha256"]:
            raise ValueError(
                "merged task membership does not match its global selection identity"
            )

    missing = sorted(TASK_IDS - set(selected))
    nonterminal = sorted(
        task_id
        for task_id, (row, _) in selected.items()
        if row.get("status") not in TERMINAL
    )
    if missing and not allow_subset:
        raise ValueError(f"incomplete full-suite shards: missing={missing}")
    if not selected:
        raise ValueError("shards selected no benchmark tasks")
    if nonterminal and (allow_subset or not allow_incomplete):
        raise ValueError(f"incomplete shards: nonterminal={nonterminal}")

    output = output.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "dashboard", output / "dashboard")
    if frozen_task_set_paths:
        destination_catalog = output / "selection" / "catalog"
        destination_catalog.mkdir(parents=True)
        shutil.copy2(
            frozen_task_set_paths[0],
            destination_catalog / frozen_task_set_paths[0].name,
        )

    rows: list[dict[str, Any]] = []
    for task_id in sorted(TASK_IDS):
        if task_id not in selected:
            row = baseline_rows.get(task_id, {"task_id": task_id})
            row.update(
                {
                    "status": "not_selected",
                    "outcome_score": None,
                    "task_success": None,
                    "elapsed_sec": None,
                    "required_artifacts": None,
                    "safety_gate_failed": False,
                    "failed_gate_count": 0,
                    "failed_core_count": 0,
                    "review_flag": "",
                    "error": "",
                }
            )
            rows.append(row)
            continue
        row, source_root = selected[task_id]
        source_task = source_root / "tasks" / task_id
        destination_task = output / "tasks" / task_id
        if row.get("status") in TERMINAL:
            shutil.copytree(source_task, destination_task)
            row["result_path"] = str(destination_task / "result.json")
        # Shards produced before the formal case protocol do not have these
        # counters.  Preserve merge compatibility while emitting one stable
        # dashboard schema from the merged run.
        row.setdefault("safety_gate_failed", False)
        row.setdefault("failed_gate_count", 0)
        row.setdefault("failed_core_count", 0)
        rows.append(row)

    selected_count = len(selected)
    terminal_rows = [
        row
        for row in rows
        if row.get("task_id") in selected and row.get("status") in TERMINAL
    ]
    scores = [
        float(row["outcome_score"])
        for row in terminal_rows
        if row.get("status") in SCOREABLE
        if isinstance(row.get("outcome_score"), (int, float))
    ]
    strict_results = [
        bool(row["task_success"])
        for row in terminal_rows
        if row.get("status") in SCOREABLE
        if isinstance(row.get("task_success"), bool)
    ]
    scoreable_rows = [row for row in terminal_rows if row.get("status") in SCOREABLE]
    safety_gate_failed_count = sum(
        row.get("safety_gate_failed") is True for row in scoreable_rows
    )
    failed_gate_total = sum(
        value
        for row in scoreable_rows
        if type(value := row.get("failed_gate_count")) is int and value >= 0
    )
    failed_core_total = sum(
        value
        for row in scoreable_rows
        if type(value := row.get("failed_core_count")) is int and value >= 0
    )
    counts = {
        status: sum(row.get("status") == status for row in rows)
        for status in (
            "not_selected",
            "queued",
            "running",
            "completed",
            "protocol_error",
            "model_error",
            "timeout",
            "infrastructure_error",
        )
    }
    template = baseline
    source_base_urls = {
        str(path): summary.get("base_url") for path, summary in zip(roots, summaries)
    }
    distinct_base_urls = sorted(
        {str(value) for value in source_base_urls.values() if value is not None}
    )
    complete = (
        len(terminal_rows) == selected_count and not counts["infrastructure_error"]
    )
    payload = {
        **{key: semantic_value(template, key) for key in MERGED_SEMANTIC_FIELDS},
        "base_url": (distinct_base_urls[0] if len(distinct_base_urls) == 1 else None),
        "base_urls": distinct_base_urls,
        "run_id": output.name,
        "selected_count": selected_count,
        "shard_index": None,
        "shard_count": len(roots),
        "workers": sum(int(item.get("workers") or 0) for item in summaries),
        "source_shards": [str(path) for path in roots],
        "source_base_urls": source_base_urls,
        "source_runtime_images": {
            str(path): summary.get("runtime_images", {})
            for path, summary in zip(roots, summaries)
        },
        "source_isolation": {
            str(path): summary.get("isolation")
            for path, summary in zip(roots, summaries)
        },
        "docker_server_versions": sorted(
            {
                str(isolation.get("server_version"))
                for summary in summaries
                if isinstance((isolation := summary.get("isolation")), dict)
                and isolation.get("server_version") is not None
            }
        ),
        "source_data_parallel_ranks": {
            str(path): summary.get("data_parallel_rank")
            for path, summary in zip(roots, summaries)
        },
        "updated_epoch": time.time(),
        "counts": counts,
        "completed_count": len(terminal_rows),
        "progress": round(len(terminal_rows) / selected_count, 4),
        "mean_oracle_completed": (
            round(statistics.mean(scores), 4) if scores else None
        ),
        "pass_rate_completed": (
            round(sum(strict_results) / len(strict_results), 4)
            if strict_results
            else None
        ),
        "strict_pass_evaluated_count": len(strict_results),
        "strict_passed_count": sum(strict_results),
        "safety_gate_evaluated_count": len(scoreable_rows),
        "safety_gate_failed_count": safety_gate_failed_count,
        "safety_gate_failure_rate": (
            round(safety_gate_failed_count / len(scoreable_rows), 4)
            if scoreable_rows
            else None
        ),
        "failed_gate_total": failed_gate_total,
        "failed_core_total": failed_core_total,
        "headline_task_success_rate": (
            round(sum(strict_results) / selected_count, 4)
            if complete and len(strict_results) == selected_count
            else None
        ),
        "median_oracle_completed": (
            round(statistics.median(scores), 4) if scores else None
        ),
        "headline_oracle_score": (
            round(sum(scores) / selected_count, 4) if complete else None
        ),
        "tasks": rows,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    (output / "summary.json").write_text(serialized + "\n", encoding="utf-8")
    (output / "summary.js").write_text(
        "window.HARNESSBENCH_SUMMARY = " + serialized + ";\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("shard_roots", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allow-subset",
        action="store_true",
        help=(
            "merge an explicit terminal task subset; omitted formal tasks "
            "remain not_selected"
        ),
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="allow non-terminal rows only in a full-suite interim merge",
    )
    parser.add_argument(
        "--run-plan",
        type=Path,
        metavar="JSON",
        help=(
            "optional JSON shard plan; strictly checks each shard's "
            "base_url, data_parallel_rank, workers and model_service_id"
        ),
    )
    args = parser.parse_args()
    run_plan = load_run_plan(args.run_plan) if args.run_plan else None
    payload = merge_shard_runs(
        args.shard_roots,
        output=args.output,
        allow_subset=args.allow_subset,
        allow_incomplete=args.allow_incomplete,
        run_plan=run_plan,
    )
    output = args.output.expanduser().resolve()
    print(
        json.dumps(
            {
                "output": str(output),
                "dashboard": str(output / "dashboard" / "index.html"),
                "selected": payload["selected_count"],
                "completed": payload["completed_count"],
                "not_selected": payload["counts"]["not_selected"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
