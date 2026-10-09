from __future__ import annotations

import gc
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harnessbench.grading.oracle_contract import (  # noqa: E402
    STRUCTURAL_POLICY_CASE_OWNED,
    STRUCTURAL_POLICY_LEGACY,
    safe_score_workspace,
)
from harnessbench.grading.outcome_cases import (  # noqa: E402
    score_workspace_from_cases,
    validate_case_manifest,
)
from harnessbench.grading.deterministic_oracle import (  # noqa: E402
    score_workspace_from_spec,
)

TASK_ROOTS = {
    "main": ROOT / "tasks",
}
LOCAL_RUNTIME_DIRECTORY_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}


def is_local_runtime_artifact(path: Path) -> bool:
    """Identify cache/editor files that are never part of a task package."""
    return (
        any(part in LOCAL_RUNTIME_DIRECTORY_NAMES for part in path.parts)
        or path.suffix == ".pyc"
        or path.name == ".DS_Store"
    )


def _task_root_filename(value: str, field: str) -> str:
    candidate = Path(value)
    if (
        not value
        or candidate.is_absolute()
        or ".." in candidate.parts
        or len(candidate.parts) != 1
    ):
        raise RuntimeError(f"{field} must be one safe task-root filename")
    return value


def _task_relative_file(value: str, field: str) -> Path:
    candidate = Path(value.replace("\\", "/"))
    if (
        not value
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "." in candidate.parts
    ):
        raise RuntimeError(f"{field} must be one safe task-relative path")
    return candidate


def outcome_case_definition(
    task_dir: Path,
    metadata: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Resolve and validate the hidden case manifest for a formal task."""
    raw_name = str(metadata.get("cases_file") or "tests/cases.yaml").strip()
    path = task_dir / _task_relative_file(raw_name, "cases_file")
    if not path.is_file():
        raise RuntimeError(f"missing cases_file: {raw_name}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return path, validate_case_manifest(raw, task_id=str(metadata.get("task_id") or ""))


def oracle_definition(
    task_dir: Path,
    metadata: dict[str, Any],
) -> tuple[str, Path]:
    """Resolve exactly one outcome test or legacy oracle definition."""
    outcome_name = str(metadata.get("outcome_test") or "").strip()
    module_name = str(metadata.get("oracle_module") or "").strip()
    spec_name = str(metadata.get("oracle_spec") or "").strip()
    if sum(bool(value) for value in (outcome_name, module_name, spec_name)) > 1:
        raise RuntimeError(
            "task declares more than one of outcome_test, oracle_module, oracle_spec"
        )
    if outcome_name:
        return "outcome", task_dir / _task_relative_file(
            outcome_name,
            "outcome_test",
        )
    if module_name:
        return "module", task_dir / _task_root_filename(
            module_name,
            "oracle_module",
        )
    if spec_name:
        return "spec", task_dir / _task_root_filename(
            spec_name,
            "oracle_spec",
        )
    legacy = task_dir / "oracle_grade.py"
    declarative = task_dir / "oracle_spec.json"
    if legacy.is_file() and declarative.is_file():
        raise RuntimeError(
            "task has both default oracle_grade.py and oracle_spec.json; "
            "declare exactly one in task.yaml"
        )
    if legacy.is_file():
        return "module", legacy
    return "spec", declarative


def iter_task_yamls() -> Iterable[Path]:
    for task_root in TASK_ROOTS.values():
        yield from sorted(task_root.glob("*/task.yaml"))


def find_task_dir(task_id: str) -> Path:
    matches = [
        task_root / task_id
        for task_root in TASK_ROOTS.values()
        if (task_root / task_id).is_dir()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one directory for {task_id}, found {matches}")
    return matches[0]


def load_oracle(module_path: Path, task_id: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"audit_{task_id.replace('-', '_')}", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_task_workspace(
    task_dir: Path,
    metadata: dict[str, Any],
    workspace: Path,
    *,
    workspace_mutation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind, path = oracle_definition(task_dir, metadata)
    if kind == "outcome":
        module = load_oracle(path, metadata["task_id"])
        evaluate_cases = getattr(module, "evaluate_cases", None)
        if not callable(evaluate_cases):
            raise RuntimeError(
                f"{metadata['task_id']}: outcome test lacks evaluate_cases"
            )
        _, manifest = outcome_case_definition(task_dir, metadata)

        def score_workspace(candidate: Path) -> dict[str, object]:
            return score_workspace_from_cases(
                candidate,
                manifest=manifest,
                evaluate_cases=evaluate_cases,
                task_id=metadata["task_id"],
            )

    elif kind == "module":
        module = load_oracle(path, metadata["task_id"])
        score_workspace = module.score_workspace
    else:

        def score_workspace(candidate: Path) -> dict[str, object]:
            return score_workspace_from_spec(candidate, spec_path=path)

    return safe_score_workspace(
        score_workspace,
        workspace=workspace,
        required_artifacts=metadata.get("required_artifacts", []),
        task_id=metadata["task_id"],
        workspace_mutation=workspace_mutation,
        require_task_success=kind == "outcome",
        structural_policy=(
            STRUCTURAL_POLICY_CASE_OWNED
            if kind == "outcome"
            else STRUCTURAL_POLICY_LEGACY
        ),
    )


def pre_agent_score(
    task_dir: Path, metadata: dict[str, Any]
) -> tuple[float | None, int, int, str]:
    temporary_root = ""
    try:
        with tempfile.TemporaryDirectory(prefix="harnessbench-audit-") as tmp:
            temporary_root = tmp
            workspace = Path(tmp)
            seed = task_dir / str(metadata.get("workspace_dir") or "workspace")
            if seed.exists():
                for child in seed.iterdir():
                    dest = workspace / child.name
                    if child.is_dir():
                        shutil.copytree(
                            child,
                            dest,
                            dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(
                                *LOCAL_RUNTIME_DIRECTORY_NAMES,
                                "*.pyc",
                                ".DS_Store",
                            ),
                        )
                    elif is_local_runtime_artifact(child.relative_to(seed)):
                        continue
                    else:
                        shutil.copy2(child, dest)
            result = score_task_workspace(task_dir, metadata, workspace)
            if os.name == "nt":
                # Some legacy SQLite Oracles rely on connection finalizers.
                # Run them before TemporaryDirectory cleanup so catalog output
                # is deterministic on Windows rather than timing-dependent.
                gc.collect()
        checks = [c for c in result.get("checks", []) if isinstance(c, dict)]
        passed = sum(bool(c.get("pass")) for c in checks)
        raw_score = result.get("outcome_score")
        score = float(raw_score) if isinstance(raw_score, (int, float)) else None
        return score, passed, len(checks), ""
    except Exception as exc:
        detail = str(exc)
        if temporary_root:
            for rendered_root in {
                temporary_root,
                temporary_root.replace("\\", "\\\\"),
                temporary_root.replace("\\", "/"),
            }:
                detail = detail.replace(rendered_root, "<temporary-workspace>")
        return None, 0, 0, f"{type(exc).__name__}: {detail[:160]}"


def load_task_metadata(task_yaml: Path) -> dict[str, Any]:
    return yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
