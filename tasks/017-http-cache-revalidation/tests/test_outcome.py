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
MUTABLE = ("repo/src/cache_revalidation.py",)
_FORBIDDEN = (
    ast.AsyncFor, ast.AsyncFunctionDef, ast.AsyncWith, ast.Await, ast.ClassDef,
    ast.Delete, ast.Global, ast.Lambda, ast.Match,
    ast.Nonlocal, ast.While, ast.With, ast.Yield, ast.YieldFrom,
)
_CALLS = {"ValueError", "all", "any", "dict", "int", "isinstance", "len", "list", "ord", "range", "set", "str", "tuple"}
_METHODS = {"append", "casefold", "endswith", "get", "isalnum", "isdigit", "items", "keys", "lower", "split", "startswith", "strip", "strptime", "values"}


def _read(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _audit(source: str) -> tuple[bool, str]:
    return audit_pure_function(source, "evaluate_cache_request", max_nodes=2400, allowed_imports=('datetime',))







def _run(source: str, cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    return run_pure_function(
        source, "evaluate_cache_request", cases, ("request", "stored"),
        timeout_seconds=5, allowed_imports=("datetime",),
    )



def _valid(source: str) -> tuple[bool, str]:
    cases = TRUTH["valid"]
    results, detail = _run(source, cases)
    if not results:
        return False, detail
    failed = [i for i, (result, case) in enumerate(zip(results, cases, strict=True)) if result.get("value") != case["expected"] or result.get("unchanged") is not True]
    return not failed, "passed" if not failed else f"failed behavior cohorts {failed}"


def _invalid(source: str) -> tuple[bool, str]:
    results, detail = _run(source, TRUTH["invalid"])
    if not results:
        return False, detail
    failed = [i for i, result in enumerate(results) if result.get("error") != "ValueError"]
    return not failed, "passed" if not failed else f"accepted invalid cohorts {failed}"


def _report(workspace: Path, source: str) -> tuple[bool, str]:
    try:
        cases = json.loads((SEED / "repo/revalidation_cases.json").read_text(encoding="utf-8"))
        actual = json.loads((workspace / "repo/revalidation_report.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible report is missing or malformed"
    results, detail = _run(source, cases)
    if not results or any("value" not in result for result in results):
        return False, detail
    expected = [{"case_id": case["case_id"], "decision": result["value"]} for case, result in zip(cases, results, strict=True)]
    return actual == expected, "passed" if actual == expected else "report differs from submitted implementation"


def _handoff(workspace: Path) -> tuple[bool, str, list[str]]:
    text, detail = _read(workspace / "repo/REPAIR_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    decision = all(word in normalized for word in ("vary", "if-none-match", "if-modified-since", "weak", "304"))
    verification = command in normalized and ("pass" in normalized or "success" in normalized)
    claims = explicit_external_action_claims(text)
    ok = decision and verification and "risk" in normalized and len(normalized) >= 260 and not claims
    return ok, "passed" if ok else "decision, verification, or risk is incomplete", claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/cache_revalidation.py", 56000)
    safe, audit = _audit(source) if source else (False, detail)
    valid_ok, valid_detail = _valid(source) if safe else (False, audit)
    invalid_ok, invalid_detail = _invalid(source) if safe else (False, audit)
    report_ok, report_detail = _report(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines
    return {
        "validator_and_variant_behavior": observation(valid_ok, valid_detail),
        "malformed_and_boundary_edges": observation(invalid_ok, invalid_detail),
        "visible_revalidation_report": observation(report_ok, report_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_workspace_boundary": observation(gate_ok, None if gate_ok else {"changed_inputs":changed,"workspace_redlines":redlines,"source_audit":audit}),
    }
