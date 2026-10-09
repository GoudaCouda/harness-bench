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
TRUTH = json.loads((TASK / "tests/ground_truth/behavior_cases.json").read_text(encoding="utf-8"))
MUTABLE = ("repo/src/refresh_recovery.py",)
_FORBIDDEN = (
    ast.AsyncFor, ast.AsyncFunctionDef, ast.AsyncWith, ast.Await, ast.ClassDef,
    ast.Delete, ast.Global, ast.Import, ast.ImportFrom, ast.Match,
    ast.Nonlocal, ast.While, ast.With, ast.Yield, ast.YieldFrom,
)
_CALLS = {
    "ValueError", "all", "any", "dict", "enumerate", "int", "isinstance",
    "len", "list", "range", "set", "sorted", "str", "tuple",
}
_METHODS = {"add", "append", "get", "index", "isalnum", "issubset", "items", "keys", "sort", "split", "startswith"}


def _read(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _audit(source: str) -> tuple[bool, str]:
    return audit_pure_function(source, "reconcile_refresh", max_nodes=2300)



def test_audit_allows_pure_sort_lambda_but_blocks_dynamic_capabilities() -> None:
    pure = """\
def reconcile_refresh(session, attempts):
    return sorted(attempts, key=lambda item: item[\"sequence\"])
"""
    unsafe = """\
import os
def reconcile_refresh(session, attempts):
    return os.listdir(\".\")
"""
    assert _audit(pure) == (True, "audited")
    assert not _audit(unsafe)[0]






def _run(source: str, cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    return run_pure_function(
        source, "reconcile_refresh", cases, ("session", "attempts"), timeout_seconds=5
    )



def _cohort(source: str, name: str) -> tuple[bool, str]:
    cases = TRUTH[name]
    results, detail = _run(source, cases)
    if not results:
        return False, detail
    failed = [
        index for index, (result, case) in enumerate(zip(results, cases, strict=True))
        if result.get("value") != case["expected"] or result.get("unchanged") is not True
    ]
    return not failed, "passed" if not failed else f"failed behavior cohorts {failed}"


def _invalid(source: str) -> tuple[bool, str]:
    results, detail = _run(source, TRUTH["invalid"])
    if not results:
        return False, detail
    failed = [index for index, result in enumerate(results) if result.get("error") != "ValueError"]
    return not failed, "passed" if not failed else f"accepted invalid cohorts {failed}"


def _report(workspace: Path, source: str) -> tuple[bool, str]:
    try:
        cases = json.loads((SEED / "repo/refresh_cases.json").read_text(encoding="utf-8"))
        actual = json.loads((workspace / "repo/reconciliation_report.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible report is missing or malformed"
    results, detail = _run(source, cases)
    if not results or any("value" not in result for result in results):
        return False, detail
    expected = [
        {"case_id": case["case_id"], "reconciliation": result["value"]}
        for case, result in zip(cases, results, strict=True)
    ]
    return actual == expected, "passed" if actual == expected else "report differs from submitted implementation"


def _handoff(workspace: Path) -> tuple[bool, str, list[str]]:
    text, detail = _read(workspace / "repo/RECOVERY_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    explanation = all(word in normalized for word in ("winner", "rotation", "invalid_grant", "stale", "retry"))
    verification = command in normalized and ("pass" in normalized or "success" in normalized)
    claims = explicit_external_action_claims(text)
    ok = explanation and verification and "risk" in normalized and len(normalized) >= 280 and not claims
    return ok, "passed" if ok else "refresh rationale, verification, or risk is incomplete", claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/refresh_recovery.py", 56000)
    safe, audit = _audit(source) if source else (False, detail)
    winner_ok, winner_detail = _cohort(source, "winner") if safe else (False, audit)
    edge_ok, edge_detail = _cohort(source, "edges") if safe else (False, audit)
    invalid_ok, invalid_detail = _invalid(source) if safe else (False, audit)
    edge_ok = edge_ok and invalid_ok
    if not invalid_ok:
        edge_detail = f"{edge_detail}; {invalid_detail}"
    report_ok, report_detail = _report(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines
    return {
        "winner_and_generation_behavior": observation(winner_ok, winner_detail),
        "replay_scope_and_validation_edges": observation(edge_ok, edge_detail),
        "visible_reconciliation_report": observation(report_ok, report_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_workspace_boundary": observation(gate_ok, None if gate_ok else {"changed_inputs": changed, "workspace_redlines": redlines, "source_audit": audit}),
    }
