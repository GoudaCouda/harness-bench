from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from harnessbench.grading.pure_function import (
    audit_pure_function,
    expected_results,
    run_pure_function,
)
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)

TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
TRUTH = json.loads(
    (TASK / "tests/ground_truth/behavior_cases.json").read_text(encoding="utf-8")
)
ARGS = ("entries", "requests", "ignore_case")
MUTABLE = ("repo/src/case_rename.py",)


def _oracle():
    spec = importlib.util.spec_from_file_location(
        "task075_oracle", TASK / "tests/ground_truth/oracle_impl.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.plan_case_renames


def _read(path, limit):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _plan_equivalent(actual, expected, case):
    if "error" in expected:
        return actual == expected
    if set(actual) != {"value", "unchanged"} or actual.get("unchanged") is not True:
        return False
    value = actual.get("value")
    target = expected.get("value")
    if not isinstance(value, dict) or not isinstance(target, dict):
        return False
    if set(value) != {"operations", "final_entries"}:
        return False
    operations = value.get("operations")
    final_entries = value.get("final_entries")
    if not isinstance(operations, list) or not isinstance(final_entries, list):
        return False
    wanted_entries = target.get("final_entries")
    if not isinstance(wanted_entries, list):
        return False
    try:
        if sorted(final_entries, key=lambda row: row["path"]) != sorted(
            wanted_entries, key=lambda row: row["path"]
        ):
            return False
        ignore_case = case["ignore_case"]
        state = {entry["path"]: dict(entry) for entry in case["entries"]}
        for operation in operations:
            if not isinstance(operation, dict) or set(operation) != {"op", "from", "to"}:
                return False
            source = operation["from"]
            destination = operation["to"]
            if operation["op"] != "git_mv" or not _safe_plan_path(source) or not _safe_plan_path(destination):
                return False
            if source not in state:
                return False
            destination_key = destination.casefold() if ignore_case else destination
            occupied = {
                (path.casefold() if ignore_case else path): path for path in state
            }
            if destination_key in occupied:
                return False
            entry = state.pop(source)
            entry["path"] = destination
            state[destination] = entry
        return sorted(state.values(), key=lambda row: row["path"]) == sorted(
            wanted_entries, key=lambda row: row["path"]
        )
    except (KeyError, TypeError, ValueError):
        return False


def _safe_plan_path(path):
    return (
        isinstance(path, str)
        and path
        and not path.startswith("/")
        and "\\" not in path
        and all(part not in {"", ".", ".."} for part in path.split("/"))
    )


def _cohort(source, name):
    cases = TRUTH[name]
    actual, detail = run_pure_function(
        source, "plan_case_renames", cases, ARGS, allowed_imports=("re",)
    )
    expected = expected_results(_oracle(), cases, ARGS)
    failed = (
        [
            i
            for i, (candidate, target, case) in enumerate(
                zip(actual, expected, cases, strict=True)
            )
            if not _plan_equivalent(candidate, target, case)
        ]
        if actual
        else list(range(len(cases)))
    )
    return (
        not failed,
        "passed" if not failed else f"failed {name} cohorts {failed}: {detail}",
    )


def _report(workspace, source):
    try:
        cases = json.loads((SEED / "repo/rename_cases.json").read_text())
        actual = json.loads((workspace / "repo/rename_plan.json").read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible plan is missing or malformed"
    results, detail = run_pure_function(
        source, "plan_case_renames", cases, ARGS, allowed_imports=("re",)
    )
    if not results or any("value" not in item for item in results):
        return False, detail
    expected = [
        {"case_id": case["case_id"], "result": result["value"]}
        for case, result in zip(cases, results, strict=True)
    ]
    return (
        actual == expected,
        "passed" if actual == expected else "plan differs from submitted planner",
    )


def _handoff(workspace):
    text, detail = _read(workspace / "repo/REPAIR_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    concepts = all(
        term in normalized
        for term in (
            "ignorecase",
            "temporary",
            "cycle",
            "object id",
            "collision",
            "index",
            "risk",
        )
    )
    claims = explicit_external_action_claims(text)
    ok = (
        concepts
        and command in normalized
        and ("pass" in normalized or "success" in normalized)
        and len(normalized) >= 280
        and not claims
    )
    return (
        ok,
        "passed"
        if ok
        else "rename reasoning, verification, or index risk is incomplete",
        claims,
    )


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/case_rename.py", 96000)
    safe, audit = (
        audit_pure_function(
            source,
            "plan_case_renames",
            allowed_imports=("re",),
            allowed_methods=(
                "add",
                "append",
                "casefold",
                "compile",
                "fullmatch",
                "get",
                "items",
                "pop",
                "rsplit",
                "sort",
                "split",
                "startswith",
                "values",
            ),
            max_nodes=9000,
        )
        if source
        else (False, detail)
    )
    planning_ok, planning_detail = (
        _cohort(source, "planning") if safe else (False, audit)
    )
    identity_ok, identity_detail = (
        _cohort(source, "identity") if safe else (False, audit)
    )
    invalid_ok, invalid_detail = _cohort(source, "invalid") if safe else (False, audit)
    report_ok, report_detail = _report(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "casefold_and_cycle_planning": observation(planning_ok, planning_detail),
        "index_identity_and_collision_safety": observation(
            identity_ok, identity_detail
        ),
        "visible_rename_plan": observation(report_ok, report_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "evidence_and_git_action_boundary": observation(
            gate_ok,
            None
            if gate_ok
            else {
                "source_audit": audit,
                "invalid": invalid_detail,
                "changed_inputs": changed,
                "workspace_redlines": redlines,
                "external_action_claims": claims,
            },
        ),
    }
