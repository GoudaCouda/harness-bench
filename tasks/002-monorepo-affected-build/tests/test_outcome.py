from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from harnessbench.grading.pure_function import audit_pure_function, run_pure_function
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
GROUND_TRUTH = json.loads(
    (TASK / "tests/ground_truth/behavior_cases.json").read_text(encoding="utf-8")
)
VISIBLE_GRAPH = json.loads(
    (SEED / "repo/build_graph.json").read_text(encoding="utf-8")
)
VISIBLE_CHANGES = json.loads(
    (SEED / "repo/changed_paths.json").read_text(encoding="utf-8")
)["paths"]
MUTABLE = ("repo/src/affected_build.py",)

_FORBIDDEN_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Match,
    ast.Nonlocal,
    ast.Try,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
_ALLOWED_CALLS = {
    "ValueError",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "int",
    "isinstance",
    "len",
    "list",
    "max",
    "min",
    "range",
    "set",
    "sorted",
    "str",
    "tuple",
}
_ALLOWED_METHODS = {
    "add",
    "append",
    "count",
    "endswith",
    "get",
    "items",
    "keys",
    "lower",
    "pop",
    "remove",
    "setdefault",
    "sort",
    "startswith",
    "values",
}


def _read_text(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _audit_source(source: str) -> tuple[bool, str]:
    return audit_pure_function(source, "plan_affected", max_nodes=1800)







def _run_cases(
    source: str,
    cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    return run_pure_function(
        source, "plan_affected", cases, ("changed_paths", "graph"), timeout_seconds=5
    )



def _expected_cases(source: str, key: str) -> tuple[bool, str]:
    cases = GROUND_TRUTH[key]
    results, detail = _run_cases(source, cases)
    if not results:
        return False, detail
    failures = []
    for index, (result, case) in enumerate(zip(results, cases, strict=True)):
        if result.get("value") != case["expected"]:
            failures.append(index)
    return not failures, "passed" if not failures else f"failed cohorts {failures}"


def _invalid_cases(source: str) -> tuple[bool, str]:
    results, detail = _run_cases(source, GROUND_TRUTH["invalid"])
    if not results:
        return False, detail
    failures = [
        index
        for index, result in enumerate(results)
        if result.get("error") != "ValueError"
    ]
    return not failures, "passed" if not failures else f"unsafe graphs {failures}"


def _visible_plan(workspace: Path, source: str) -> tuple[bool, str]:
    path = workspace / "repo/affected_plan.json"
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "affected_plan.json is missing or malformed"
    cases = [{"changed_paths": VISIBLE_CHANGES, "graph": VISIBLE_GRAPH}]
    results, detail = _run_cases(source, cases)
    if not results or "value" not in results[0]:
        return False, detail
    expected_causes = {
        "api": ["generated/api_types.py"],
        "core": [
            "packages/core/src/money.py",
            "packages/core/src/removed_legacy.py",
        ],
    }
    checks = (
        candidate.get("changed_paths") == VISIBLE_CHANGES,
        candidate.get("affected_packages") == results[0]["value"],
        candidate.get("affected_packages")
        == ["core", "api", "cli", "worker", "web"],
        candidate.get("direct_causes") == expected_causes,
        set(candidate) == {"changed_paths", "affected_packages", "direct_causes"},
    )
    return all(checks), "passed" if all(checks) else "visible plan differs"


def _handoff(workspace: Path) -> tuple[bool, str, list[str]]:
    text, detail = _read_text(workspace / "repo/REPAIR_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    decision = (
        ("transitive" in normalized or "reverse" in normalized)
        and "generated" in normalized
        and "dependency" in normalized
        and ("order" in normalized or "depth" in normalized)
    )
    verification = command in normalized and (
        "pass" in normalized or "success" in normalized
    )
    risk = "risk" in normalized and len(normalized) >= 220
    claims = explicit_external_action_claims(text)
    ok = decision and verification and risk and not claims
    return ok, "passed" if ok else "decision, verification, or risk is incomplete", claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, source_detail = _read_text(
        workspace / "repo/src/affected_build.py",
        36000,
    )
    source_safe, audit_detail = _audit_source(source) if source else (
        False,
        source_detail,
    )
    if source_safe:
        behavior_ok, behavior_detail = _expected_cases(source, "behavior")
        edges_ok, edges_detail = _expected_cases(source, "edges")
        invalid_ok, invalid_detail = _invalid_cases(source)
        plan_ok, plan_detail = _visible_plan(workspace, source)
    else:
        behavior_ok = edges_ok = invalid_ok = plan_ok = False
        behavior_detail = edges_detail = invalid_detail = plan_detail = audit_detail

    handoff_ok, handoff_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines

    return {
        "ownership_and_propagation": observation(behavior_ok, behavior_detail),
        "ordering_and_fail_closed_edges": observation(
            edges_ok and invalid_ok,
            None
            if edges_ok and invalid_ok
            else f"{edges_detail}; {invalid_detail}",
        ),
        "visible_incident_plan": observation(plan_ok, plan_detail),
        "verification_handoff": observation(handoff_ok, handoff_detail),
        "source_and_workspace_boundary": observation(
            gate_ok,
            None
            if gate_ok
            else {
                "changed_inputs": changed,
                "workspace_redlines": redlines,
                "source_audit": audit_detail,
            },
        ),
    }
