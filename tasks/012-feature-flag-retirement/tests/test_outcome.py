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
GROUND_TRUTH = json.loads((TASK / "tests/ground_truth/behavior_cases.json").read_text(encoding="utf-8"))
MUTABLE = ("repo/src/checkout_policy.py", "repo/config/flags.json")

_FORBIDDEN = (
    ast.AsyncFor, ast.AsyncFunctionDef, ast.AsyncWith, ast.Await, ast.ClassDef,
    ast.Delete, ast.Global, ast.Lambda, ast.Match,
    ast.Nonlocal, ast.While, ast.With, ast.Yield, ast.YieldFrom,
)
_CALLS = {
    "ValueError", "all", "any", "bool", "dict", "enumerate", "int",
    "isinstance", "len", "list", "max", "min", "range", "set", "sorted",
    "str", "tuple",
}
_METHODS = {"add", "append", "casefold", "endswith", "get", "isdigit", "items", "keys", "startswith", "strptime", "values"}


def _read_text(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _audit(source: str) -> tuple[bool, str]:
    return audit_pure_function(source, "select_checkout_engine", max_nodes=1800, allowed_imports=('datetime',))







def _run(source: str, cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    return run_pure_function(
        source, "select_checkout_engine", cases, ("event", "policy"),
        timeout_seconds=5, allowed_imports=("datetime",),
    )



def _valid(source: str) -> tuple[bool, str]:
    cases = GROUND_TRUTH["valid"]
    results, detail = _run(source, cases)
    if not results:
        return False, detail
    failed = [index for index, (result, case) in enumerate(zip(results, cases, strict=True)) if result.get("value") != case["expected"] or result.get("unchanged") is not True]
    return not failed, "passed" if not failed else f"failed valid cohorts {failed}"


def _invalid(source: str) -> tuple[bool, str]:
    results, detail = _run(source, GROUND_TRUTH["invalid"])
    if not results:
        return False, detail
    failed = [index for index, result in enumerate(results) if result.get("error") != "ValueError"]
    return not failed, "passed" if not failed else f"accepted invalid cohorts {failed}"


def _registry(workspace: Path) -> tuple[bool, str]:
    try:
        actual = json.loads((workspace / "repo/config/flags.json").read_text(encoding="utf-8"))
        expected = json.loads((TASK / "tests/reference/repo/config/flags.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "registry is missing or malformed"
    return actual == expected, "passed" if actual == expected else "registry differs from the required minimal retirement"


def _handoff(workspace: Path) -> tuple[bool, str, list[str]]:
    text, detail = _read_text(workspace / "repo/MIGRATION_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    decision = all(word in normalized for word in ("historical", "cutoff", "snapshot", "received_at", "registry"))
    verification = command in normalized and ("pass" in normalized or "success" in normalized)
    claims = explicit_external_action_claims(text)
    ok = decision and verification and "risk" in normalized and len(normalized) >= 260 and not claims
    return ok, "passed" if ok else "decision, verification, or risk is incomplete", claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, detail = _read_text(workspace / "repo/src/checkout_policy.py", 48000)
    safe, audit = _audit(source) if source else (False, detail)
    if safe:
        valid_ok, valid_detail = _valid(source)
        invalid_ok, invalid_detail = _invalid(source)
    else:
        valid_ok = invalid_ok = False
        valid_detail = invalid_detail = audit
    registry_ok, registry_detail = _registry(workspace)
    handoff_ok, handoff_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines
    return {
        "historical_and_retired_behavior": observation(valid_ok, valid_detail),
        "fail_closed_replay_edges": observation(invalid_ok, invalid_detail),
        "registry_retirement": observation(registry_ok, registry_detail),
        "migration_handoff": observation(handoff_ok, handoff_detail),
        "source_and_workspace_boundary": observation(gate_ok, None if gate_ok else {"changed_inputs": changed, "workspace_redlines": redlines, "source_audit": audit}),
    }
