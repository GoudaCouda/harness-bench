#!/usr/bin/env python3
"""Smoke-test task references through the production Docker grader boundary.

This validator is deliberately narrower than a benchmark trial: it does not
run an agent or task lifecycle hooks.  It builds each known-correct reference
workspace with ``validate_oracle_quality.make_workspace`` and submits that
workspace to the same image, entrypoint, mounts, and isolation flags used by
the canonical runner.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

TASK_MAINTENANCE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TASK_MAINTENANCE_DIR.parent
ROOT = TOOLS_DIR.parent
SRC_DIR = ROOT / "src"
for import_root in (TASK_MAINTENANCE_DIR, TOOLS_DIR, SRC_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from common import (  # noqa: E402
    iter_task_yamls,
    load_task_metadata,
    outcome_case_definition,
)
from container_runtime import (  # noqa: E402
    GRADER_IMAGE,
    GRADER_SOURCE_LABEL,
    build_images,
    constrained_run_args,
    docker,
    grader_source_sha256,
    require_docker,
)
from harnessbench.grading.oracle_contract import (  # noqa: E402
    ORACLE_CONTRACT_VERSION,
    WORKSPACE_MUTATION_SCHEMA_VERSION,
    manifest_sha256,
    workspace_manifest,
    workspace_mutation_report,
)
from harnessbench.task_sets import load_task_set, validate_task_set_name  # noqa: E402
from validate_oracle_quality import make_workspace  # noqa: E402


DEFAULT_REPORT = ROOT / "artifacts" / "audits" / "docker-grader-reference.json"
CATALOG_DIR = ROOT / "catalog"
MUTATION_REPORT_NAME = "workspace-mutation.json"


@dataclass(frozen=True)
class TaskReference:
    task_id: str
    task_dir: Path
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PreparedReference:
    workspace: Path
    runtime: Path
    grader_control: Path
    hidden: Path


def numeric_task_id(task_id: str) -> int:
    prefix = task_id.split("-", 1)[0]
    if len(prefix) != 3 or not prefix.isdigit():
        raise ValueError(f"task_id must start with a three-digit number: {task_id!r}")
    return int(prefix)


def discover_tasks() -> list[TaskReference]:
    tasks: list[TaskReference] = []
    seen: set[str] = set()
    for task_yaml in iter_task_yamls():
        metadata = load_task_metadata(task_yaml)
        task_id = str(metadata.get("task_id") or task_yaml.parent.name)
        if task_id in seen:
            raise RuntimeError(f"duplicate task_id: {task_id}")
        if task_id != task_yaml.parent.name:
            raise RuntimeError(
                f"task_id/directory mismatch: {task_id!r} != {task_yaml.parent.name!r}"
            )
        numeric_task_id(task_id)
        seen.add(task_id)
        tasks.append(
            TaskReference(
                task_id=task_id,
                task_dir=task_yaml.parent.resolve(),
                metadata=metadata,
            )
        )
    return sorted(tasks, key=lambda item: item.task_id)


def select_tasks(
    tasks: Sequence[TaskReference],
    *,
    start: int | None,
    end: int | None,
    requested: set[str],
) -> list[TaskReference]:
    if start is not None and end is not None and start > end:
        raise ValueError("--start must be <= --end")
    known = {task.task_id for task in tasks}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError("unknown --tasks value(s): " + ", ".join(unknown))

    selected = []
    for task in tasks:
        number = numeric_task_id(task.task_id)
        if start is not None and number < start:
            continue
        if end is not None and number > end:
            continue
        if requested and task.task_id not in requested:
            continue
        selected.append(task)
    if not selected:
        raise ValueError("no tasks selected")
    return selected


def _replace_mount_roots(path: Path, replacements: Sequence[tuple[str, str]]) -> None:
    """Replace staging-only absolute roots persisted by reference setup.

    Trusted reference helpers run on the maintainer host, while the production
    grader sees the same trees at ``/workspace`` and ``/runtime``.  Persisted
    UTF-8 paths (notably Git worktree metadata) therefore need the same
    container-path rendering used by a real trial.
    """
    if not path.is_file() or path.is_symlink():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return
    rendered = text
    for source, target in replacements:
        rendered = rendered.replace(source, target)
    if rendered != text:
        path.write_text(rendered, encoding="utf-8")


def render_reference_mount_paths(workspace: Path, runtime: Path) -> None:
    replacements = sorted(
        (
            (str(workspace.resolve()), "/workspace"),
            (str(runtime.resolve()), "/runtime"),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for root in (workspace, runtime):
        for path in sorted(root.rglob("*")):
            _replace_mount_roots(path, replacements)


def make_tree_container_readable(root: Path) -> None:
    """Make temporary bind sources traversable/readable by grader UID 1000."""
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError(f"bind source must be a real directory: {root}")
    root.chmod(0o755)
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(0o644)
        else:
            raise RuntimeError(f"unsupported bind-mount entry: {path}")


def trusted_reference_report(
    workspace: Path,
    mutation_contract: Mapping[str, object] | None,
) -> dict[str, Any]:
    """Create a schema-v3 identity report for a trusted final workspace.

    Reference construction is not an agent round, so this report intentionally
    compares the trusted final manifest with itself.  Mutation ownership is
    audited elsewhere; this smoke validates the final identity and grader
    boundary without inventing agent actions.
    """
    manifest = workspace_manifest(workspace)
    report = workspace_mutation_report(
        manifest,
        manifest,
        contract=mutation_contract,
    )
    if report["schema_version"] != WORKSPACE_MUTATION_SCHEMA_VERSION:
        raise RuntimeError("workspace mutation report schema drift")
    if not report["complete"]:
        raise RuntimeError(
            "reference workspace contains entries forbidden by the suite contract"
        )
    report["final_workspace_sha256"] = manifest_sha256(manifest)
    report["final_workspace_entry_count"] = len(manifest)
    return report


@contextmanager
def prepare_reference(task: TaskReference) -> Iterator[PreparedReference]:
    workspace, cleanup_roots = make_workspace(
        task.task_dir,
        task.metadata,
        "reference",
    )
    roots = list(cleanup_roots)
    runtime = next((root for root in roots if root != workspace), None)
    if runtime is None:
        runtime = Path(tempfile.mkdtemp(prefix="hb-docker-grader-runtime-"))
        roots.append(runtime)
    grader_control = Path(tempfile.mkdtemp(prefix="hb-docker-grader-control-"))
    roots.append(grader_control)
    hidden_parent = Path(tempfile.mkdtemp(prefix="hb-docker-grader-hidden-"))
    roots.append(hidden_parent)
    hidden = hidden_parent / task.task_id
    try:
        # The production runner grades an immutable suite snapshot whose files
        # are normalized to 0444/0555.  Copy the task package here as well so
        # this smoke test has the same permission boundary.  Binding the live
        # checkout directly is unreliable under a restrictive host umask:
        # a valid hidden rubric may be 0640 and unreadable to grader UID 1000.
        shutil.copytree(
            task.task_dir,
            hidden,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
        render_reference_mount_paths(workspace, runtime)
        report = trusted_reference_report(
            workspace,
            task.metadata.get("mutation_contract"),
        )
        (grader_control / MUTATION_REPORT_NAME).write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for root in (workspace, runtime, grader_control, hidden):
            make_tree_container_readable(root)
        yield PreparedReference(
            workspace=workspace,
            runtime=runtime,
            grader_control=grader_control,
            hidden=hidden,
        )
    finally:
        for root in reversed(roots):
            shutil.rmtree(root, ignore_errors=True)


def grader_command(
    task: TaskReference,
    prepared: PreparedReference,
    *,
    image: str,
) -> list[str]:
    cases_manifest: dict[str, Any] | None = None
    if str(task.metadata.get("outcome_test") or "").strip():
        _, cases_manifest = outcome_case_definition(task.task_dir, task.metadata)
    mounts = (
        (prepared.workspace.resolve(), "/workspace"),
        (prepared.runtime.resolve(), "/runtime"),
        (prepared.grader_control.resolve(), "/grader-control"),
        (prepared.hidden.resolve(), "/hidden"),
    )
    for source, _ in mounts:
        if "," in str(source):
            raise RuntimeError(f"Docker --mount source contains a comma: {source}")
    return [
        "run",
        "--rm",
        *constrained_run_args(),
        "--user",
        "1000:1000",
        *[
            value
            for source, target in mounts
            for value in (
                "--mount",
                f"type=bind,src={source},dst={target},readonly",
            )
        ],
        "--env",
        f"HARNESSBENCH_TASK_ID={task.task_id}",
        "--env",
        "HARNESSBENCH_REQUIRED_ARTIFACTS="
        + json.dumps(task.metadata.get("required_artifacts", [])),
        "--env",
        f"HARNESSBENCH_MUTATION_REPORT={MUTATION_REPORT_NAME}",
        "--env",
        "HARNESSBENCH_ORACLE_MODULE=" + str(task.metadata.get("oracle_module") or ""),
        "--env",
        "HARNESSBENCH_ORACLE_SPEC=" + str(task.metadata.get("oracle_spec") or ""),
        "--env",
        "HARNESSBENCH_OUTCOME_TEST=" + str(task.metadata.get("outcome_test") or ""),
        "--env",
        "HARNESSBENCH_CASES_JSON="
        + (
            json.dumps(cases_manifest, ensure_ascii=False, separators=(",", ":"))
            if cases_manifest is not None
            else ""
        ),
        "--env",
        "HARNESSBENCH_SEMANTIC_JUDGE_JSON="
        + (
            json.dumps(
                task.metadata.get("semantic_judge"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if task.metadata.get("semantic_judge") is not None
            else ""
        ),
        "--env",
        "GIT_CONFIG_COUNT=1",
        "--env",
        "GIT_CONFIG_KEY_0=safe.directory",
        "--env",
        "GIT_CONFIG_VALUE_0=*",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        image,
    ]


def validate_grader_result(
    value: object,
    *,
    task_id: str,
    minimum_score: float,
    require_task_success: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("grader output must be one JSON object")
    if value.get("task_id") != task_id:
        raise ValueError(
            f"grader task_id mismatch: {value.get('task_id')!r} != {task_id!r}"
        )
    raw_score = value.get("outcome_score")
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        raise ValueError("grader outcome_score must be numeric")
    score = float(raw_score)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(f"grader outcome_score is outside [0, 1]: {raw_score!r}")
    if score + 1e-12 < minimum_score:
        raise ValueError(
            f"reference score {score:.4f} is below required {minimum_score:.4f}"
        )
    if require_task_success and value.get("task_success") is not True:
        raise ValueError("formal reference did not satisfy strict task_success")
    if value.get("oracle_contract_version") != ORACLE_CONTRACT_VERSION:
        raise ValueError("grader output has an unsupported oracle contract version")
    if not isinstance(value.get("checks"), list):
        raise ValueError("grader output checks must be a list")
    artifacts = value.get("required_artifact_contract")
    if not isinstance(artifacts, dict) or artifacts.get("complete") is not True:
        raise ValueError("reference failed the required-artifact contract")
    mutation = value.get("workspace_mutation_contract")
    if (
        not isinstance(mutation, dict)
        or mutation.get("schema_version") != WORKSPACE_MUTATION_SCHEMA_VERSION
        or mutation.get("complete") is not True
        or mutation.get("safe") is not True
    ):
        raise ValueError("reference failed the workspace identity contract")
    if value.get("oracle_contract_failure"):
        raise ValueError("grader reported an oracle contract failure")
    isolation = value.get("grader_isolation")
    expected_isolation = {
        "network": "none",
        "workspace": "read_only",
        "workspace_write_probe_blocked": True,
        "oracle_visible_to_agent": False,
    }
    if isolation != expected_isolation:
        raise ValueError(f"grader isolation evidence is malformed: {isolation!r}")
    runtime = value.get("grader_runtime")
    if not isinstance(runtime, dict) or runtime.get("git") != "git version 2.39.5":
        raise ValueError(f"grader runtime evidence is malformed: {runtime!r}")
    return dict(value)


def run_one(
    task: TaskReference,
    *,
    image: str,
    timeout_sec: int,
    minimum_score: float,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with prepare_reference(task) as prepared:
            completed = docker(
                *grader_command(task, prepared, image=image),
                check=False,
                timeout=timeout_sec,
            )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"grader container exited {completed.returncode}: {detail}"
            )
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"grader stdout is not one JSON object: {exc}") from exc
        result = validate_grader_result(
            raw,
            task_id=task.task_id,
            minimum_score=minimum_score,
            require_task_success=bool(
                str(task.metadata.get("outcome_test") or "").strip()
            ),
        )
        return {
            "task_id": task.task_id,
            "pass": True,
            "outcome_score": float(result["outcome_score"]),
            "elapsed_sec": round(time.monotonic() - started, 3),
            "error": "",
            "grader_result": result,
        }
    except Exception as exc:
        return {
            "task_id": task.task_id,
            "pass": False,
            "outcome_score": None,
            "elapsed_sec": round(time.monotonic() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
            "grader_result": None,
        }


def inspect_grader_image(image: str) -> dict[str, str]:
    completed = docker(
        "image",
        "inspect",
        image,
        "--format",
        "{{json .}}",
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"grader image is unavailable: {image}: {detail}")
    try:
        inspected = json.loads(completed.stdout)
        image_id = str(inspected["Id"])
        labels = inspected.get("Config", {}).get("Labels") or {}
        source_identity = str(labels.get(GRADER_SOURCE_LABEL) or "")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot inspect grader image {image}: {exc}") from exc
    expected_source = grader_source_sha256()
    if source_identity != expected_source:
        raise RuntimeError(
            "grader image does not match current trusted source: "
            f"image={source_identity or '<missing>'} expected={expected_source}"
        )
    return {
        "name": image,
        "id": image_id,
        "source_sha256": source_identity,
    }


def write_report(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="validate known-correct references in the formal Docker grader",
    )
    parser.add_argument("--start", type=int, help="first numeric task ID, inclusive")
    parser.add_argument("--end", type=int, help="last numeric task ID, inclusive")
    selection_group = parser.add_mutually_exclusive_group()
    selection_group.add_argument(
        "--tasks",
        action="append",
        default=[],
        help="comma-separated exact task IDs; may be repeated",
    )
    selection_group.add_argument(
        "--task-set",
        metavar="NAME",
        type=validate_task_set_name,
        help="named subset loaded from catalog/NAME.yaml",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--image", default=GRADER_IMAGE)
    parser.add_argument(
        "--build-image",
        action="store_true",
        help="build the trusted default grader image when its source label is stale",
    )
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument(
        "--minimum-score",
        type=float,
        default=1.0,
        help="minimum accepted reference score (default: 1.0)",
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.task_set is not None and (args.start is not None or args.end is not None):
        parser.error("--task-set cannot be combined with --start or --end")
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.timeout_sec < 1:
        parser.error("--timeout-sec must be >= 1")
    if not math.isfinite(args.minimum_score) or not 0 <= args.minimum_score <= 1:
        parser.error("--minimum-score must be finite and within [0, 1]")
    if args.build_image and args.image != GRADER_IMAGE:
        parser.error("--build-image can only be used with the trusted default image")
    requested = {
        task_id.strip()
        for raw in args.tasks
        for task_id in raw.split(",")
        if task_id.strip()
    }
    try:
        discovered_tasks = discover_tasks()
        if args.task_set is not None:
            task_set = load_task_set(
                CATALOG_DIR,
                args.task_set,
                known_task_ids=(task.task_id for task in discovered_tasks),
            )
            requested = set(task_set.task_ids)
        tasks = select_tasks(
            discovered_tasks,
            start=args.start,
            end=args.end,
            requested=requested,
        )
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    require_docker()
    if args.build_image:
        build_images()
    try:
        image_identity = inspect_grader_image(args.image)
    except RuntimeError as exc:
        parser.error(str(exc))
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(args.workers, len(tasks))
    ) as executor:
        futures = {
            executor.submit(
                run_one,
                task,
                image=args.image,
                timeout_sec=args.timeout_sec,
                minimum_score=args.minimum_score,
            ): task
            for task in tasks
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            state = "PASS" if row["pass"] else "FAIL"
            suffix = (
                f"score={row['outcome_score']}" if row["pass"] else str(row["error"])
            )
            print(
                f"{state} {row['task_id']} {suffix} elapsed={row['elapsed_sec']}s",
                flush=True,
            )

    rows.sort(key=lambda row: str(row["task_id"]))
    failed = sum(not row["pass"] for row in rows)
    payload = {
        "schema_version": 1,
        "kind": "docker_grader_reference_smoke",
        "image": image_identity,
        "selection": {
            "start": args.start,
            "end": args.end,
            "task_set": args.task_set,
            "tasks": sorted(requested),
        },
        "workers": min(args.workers, len(tasks)),
        "timeout_sec": args.timeout_sec,
        "minimum_score": args.minimum_score,
        "task_count": len(rows),
        "passed": len(rows) - failed,
        "failed": failed,
        "elapsed_sec": round(time.monotonic() - started, 3),
        "tasks": rows,
    }
    write_report(args.json_out, payload)
    print(
        f"tasks={len(rows)} passed={payload['passed']} failed={failed} "
        f"report={args.json_out}",
        flush=True,
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
