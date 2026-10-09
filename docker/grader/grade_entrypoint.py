from __future__ import annotations

import importlib.util
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

import yaml

from harnessbench.grading.deterministic_oracle import score_workspace_from_spec
from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.oracle_contract import (
    STRUCTURAL_POLICY_CASE_OWNED,
    STRUCTURAL_POLICY_LEGACY,
    WORKSPACE_MUTATION_SCHEMA_VERSION,
    manifest_sha256,
    safe_score_workspace,
    workspace_manifest,
)
from harnessbench.grading.semantic_judge import (
    JUDGE_SCHEMA_VERSION,
    validate_judge_config,
    validate_judge_request,
)


def load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("hidden_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load oracle: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hidden_path(environment_name: str, default: str) -> Path:
    value = os.environ.get(environment_name, default).strip()
    candidate = Path(value.replace("\\", "/"))
    if (
        not value
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "." in candidate.parts
    ):
        raise RuntimeError(f"{environment_name} must be one safe relative path")
    hidden_root = Path("/hidden").resolve()
    resolved = (hidden_root / candidate).resolve()
    if not resolved.is_relative_to(hidden_root):
        raise RuntimeError(f"{environment_name} escapes the hidden task package")
    return resolved


def case_manifest() -> object:
    raw = os.environ.get("HARNESSBENCH_CASES_JSON", "").strip()
    if not raw:
        raise RuntimeError(
            "formal outcome-case task is missing HARNESSBENCH_CASES_JSON"
        )
    return json.loads(raw)


def score_callable() -> Any:
    outcome_name = os.environ.get("HARNESSBENCH_OUTCOME_TEST", "").strip()
    oracle_name = os.environ.get("HARNESSBENCH_ORACLE_MODULE", "").strip()
    spec_name = os.environ.get("HARNESSBENCH_ORACLE_SPEC", "").strip()
    if sum(bool(value) for value in (outcome_name, oracle_name, spec_name)) > 1:
        raise RuntimeError(
            "task declares more than one of outcome_test, oracle_module, oracle_spec"
        )
    if outcome_name:
        outcome_path = hidden_path("HARNESSBENCH_OUTCOME_TEST", outcome_name)
        if not outcome_path.is_file():
            raise RuntimeError(
                f"hidden outcome test does not exist: {outcome_path.relative_to('/hidden')}"
            )
        module = load_module(outcome_path)
        evaluate_cases = getattr(module, "evaluate_cases", None)
        if not callable(evaluate_cases):
            raise RuntimeError("hidden outcome test has no evaluate_cases")
        manifest = case_manifest()
        task_id = os.environ.get("HARNESSBENCH_TASK_ID", "").strip()
        return lambda workspace: score_workspace_from_cases(
            workspace,
            manifest=manifest,
            evaluate_cases=evaluate_cases,
            task_id=task_id,
        )
    if spec_name:
        spec_path = hidden_path("HARNESSBENCH_ORACLE_SPEC", spec_name)
        if not spec_path.is_file():
            raise RuntimeError(f"hidden oracle spec does not exist: {spec_path.name}")
        return lambda workspace: score_workspace_from_spec(
            workspace,
            spec_path=spec_path,
        )
    if oracle_name:
        oracle_path = hidden_path("HARNESSBENCH_ORACLE_MODULE", oracle_name)
    elif Path("/hidden/oracle_grade.py").is_file():
        oracle_path = Path("/hidden/oracle_grade.py")
    elif Path("/hidden/oracle_spec.json").is_file():
        spec_path = Path("/hidden/oracle_spec.json")
        return lambda workspace: score_workspace_from_spec(
            workspace,
            spec_path=spec_path,
        )
    else:
        raise RuntimeError(
            "hidden task has neither outcome test nor legacy oracle definition"
        )
    module = load_module(oracle_path)
    score_workspace = getattr(module, "score_workspace", None)
    if not callable(score_workspace):
        raise RuntimeError("hidden oracle has no score_workspace")
    return score_workspace


def required_artifacts() -> list[object]:
    values = json.loads(os.environ.get("HARNESSBENCH_REQUIRED_ARTIFACTS", "[]"))
    if not isinstance(values, list):
        raise ValueError("HARNESSBENCH_REQUIRED_ARTIFACTS must be a JSON list")
    return values


def semantic_judge_request(workspace: Path, *, task_id: str) -> dict[str, Any] | None:
    raw = os.environ.get("HARNESSBENCH_SEMANTIC_JUDGE_JSON", "").strip()
    if not raw:
        return None
    config = validate_judge_config(json.loads(raw))
    rubric_path = hidden_path("HARNESSBENCH_JUDGE_RUBRIC", config["rubric_file"])
    builder_path = hidden_path("HARNESSBENCH_JUDGE_INPUT", config["input_builder"])
    if not rubric_path.is_file() or not builder_path.is_file():
        raise RuntimeError("semantic judge rubric or input builder is missing")
    rubric = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    builder_module = load_module(builder_path)
    builder = getattr(builder_module, "build_semantic_judge_input", None)
    if not callable(builder):
        raise RuntimeError("semantic judge input module lacks a callable builder")
    candidate = builder(workspace)
    request = {
        "schema_version": JUDGE_SCHEMA_VERSION,
        "task_id": task_id,
        "score_role": config["score_role"],
        "case_map": config["case_map"],
        "rubric": rubric,
        "candidate": candidate,
    }
    validated = validate_judge_request(request)
    validated.pop("criterion_ids", None)
    return validated


def workspace_mutation(
    workspace: Path,
    control_root: Path = Path("/grader-control"),
) -> dict[str, object] | None:
    name = os.environ.get("HARNESSBENCH_MUTATION_REPORT", "").strip()
    if not name:
        return None
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts or len(candidate.parts) != 1:
        raise RuntimeError("HARNESSBENCH_MUTATION_REPORT must be one safe filename")
    path = control_root / candidate
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("workspace mutation report must be a JSON object")
    if (
        value.get("schema_version") != WORKSPACE_MUTATION_SCHEMA_VERSION
        or value.get("enabled") is not True
    ):
        raise RuntimeError("workspace mutation report has an unsupported schema")
    violation_fields = (
        "unexpected_created",
        "unexpected_modified",
        "unexpected_deleted",
        "unsafe_entries",
        "protected_modified",
        "protected_deleted",
    )
    if any(not isinstance(value.get(field), list) for field in violation_fields):
        raise RuntimeError("workspace mutation report has malformed violation fields")
    expected_complete = not any(value[field] for field in violation_fields)
    if value.get("complete") is not expected_complete:
        raise RuntimeError(
            "workspace mutation report has inconsistent completion state"
        )
    expected_safe = not any(
        value[field]
        for field in ("protected_modified", "protected_deleted", "unsafe_entries")
    )
    if value.get("safe") is not expected_safe:
        raise RuntimeError("workspace mutation report has inconsistent safety state")
    expected_safety_violations = {
        "protected_modified": value["protected_modified"],
        "protected_deleted": value["protected_deleted"],
        "unsafe_entries": value["unsafe_entries"],
    }
    if value.get("safety_violations") != expected_safety_violations:
        raise RuntimeError(
            "workspace mutation report has inconsistent safety violations"
        )
    expected_final_sha256 = value.get("final_workspace_sha256")
    if not isinstance(expected_final_sha256, str):
        raise RuntimeError("workspace mutation report lacks a final workspace digest")
    actual_manifest = workspace_manifest(workspace)
    actual_final_sha256 = manifest_sha256(actual_manifest)
    if expected_final_sha256 != actual_final_sha256:
        raise RuntimeError(
            "final workspace digest does not match the trusted mutation report"
        )
    if value.get("final_workspace_entry_count") != len(actual_manifest):
        raise RuntimeError(
            "final workspace entry count does not match the trusted mutation report"
        )
    return dict(value)


def workspace_is_read_only(workspace: Path) -> bool:
    probe = workspace / ".grader-write-probe"
    try:
        probe.write_text("must not succeed", encoding="utf-8")
    except OSError:
        return True
    probe.unlink(missing_ok=True)
    return False


def grader_runtime() -> dict[str, str]:
    """Fail closed when a declared legacy-oracle runtime is unavailable."""
    git = subprocess.run(
        ["git", "--version"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    git_version = git.stdout.strip()
    if git.returncode != 0 or git_version != "git version 2.39.5":
        raise RuntimeError(
            "grader git runtime mismatch: "
            f"returncode={git.returncode} version={git_version!r}"
        )
    return {
        "python": platform.python_version(),
        "git": git_version,
    }


def main() -> None:
    task_id = os.environ.get("HARNESSBENCH_TASK_ID", "").strip()
    workspace = Path("/workspace")
    score_workspace = score_callable()

    read_only = workspace_is_read_only(workspace)
    if not read_only:
        raise RuntimeError("security contract violated: grader workspace is writable")

    outcome_task = bool(os.environ.get("HARNESSBENCH_OUTCOME_TEST", "").strip())
    result = safe_score_workspace(
        score_workspace,
        workspace=workspace,
        required_artifacts=required_artifacts(),
        task_id=task_id,
        workspace_mutation=workspace_mutation(workspace),
        require_task_success=outcome_task,
        structural_policy=(
            STRUCTURAL_POLICY_CASE_OWNED if outcome_task else STRUCTURAL_POLICY_LEGACY
        ),
    )
    result["task_id"] = task_id
    result["grader_runtime"] = grader_runtime()
    result["grader_isolation"] = {
        "network": "none",
        "workspace": "read_only",
        "workspace_write_probe_blocked": read_only,
        "oracle_visible_to_agent": False,
    }
    request = semantic_judge_request(workspace, task_id=task_id)
    if request is not None:
        result["semantic_judge_request"] = request
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
