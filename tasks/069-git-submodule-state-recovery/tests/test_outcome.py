from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from harnessbench.grading.pure_function import audit_pure_function, expected_results, run_pure_function
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations

TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
TRUTH = json.loads((TASK / "tests/ground_truth/behavior_cases.json").read_text(encoding="utf-8"))
ARGS = ("submodules", "recursive")
MUTABLE = ("repo/src/submodule_recovery.py",)


def _oracle():
    spec = importlib.util.spec_from_file_location("task069_oracle", TASK / "tests/ground_truth/oracle_impl.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.plan_submodule_recovery


def _read(path, limit):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _cohort(source, name):
    cases = TRUTH[name]
    actual, detail = run_pure_function(source, "plan_submodule_recovery", cases, ARGS)
    expected = expected_results(_oracle(), cases, ARGS)
    failed = [i for i, pair in enumerate(zip(actual, expected, strict=True)) if pair[0] != pair[1]] if actual else list(range(len(cases)))
    return not failed, "passed" if not failed else f"failed {name} cohorts {failed}: {detail}"


def _report(workspace, source):
    try:
        cases = json.loads((SEED / "repo/submodule_cases.json").read_text(encoding="utf-8"))
        actual = json.loads((workspace / "repo/recovery_report.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible report is missing or malformed"
    results, detail = run_pure_function(source, "plan_submodule_recovery", cases, ARGS)
    if not results or any("value" not in item for item in results):
        return False, detail
    expected = [{"case_id": case["case_id"], "result": result["value"]} for case, result in zip(cases, results, strict=True)]
    return actual == expected, "passed" if actual == expected else "report differs from submitted planner"


def _handoff(workspace):
    text, detail = _read(workspace / "repo/REPAIR_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    concepts = all(term in normalized for term in ("gitlink", "remote", "dirty", "untracked", "conflict", "missing", "recursive", "risk"))
    claims = explicit_external_action_claims(text)
    ok = concepts and command in normalized and ("pass" in normalized or "success" in normalized) and len(normalized) >= 260 and not claims
    return ok, "passed" if ok else "submodule reasoning, verification, or risk is incomplete", claims


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/submodule_recovery.py", 96000)
    safe, audit = audit_pure_function(source, "plan_submodule_recovery", allowed_methods=("add", "append", "casefold", "get", "items", "sort", "split", "startswith"), max_nodes=7000) if source else (False, detail)
    authority_ok, authority_detail = _cohort(source, "authority") if safe else (False, audit)
    safety_ok, safety_detail = _cohort(source, "safety_and_recursion") if safe else (False, audit)
    invalid_ok, invalid_detail = _cohort(source, "invalid") if safe else (False, audit)
    report_ok, report_detail = _report(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "gitlink_authority_and_checkout_state": observation(authority_ok, authority_detail),
        "local_change_conflict_and_recursion_safety": observation(safety_ok, safety_detail),
        "visible_recovery_report": observation(report_ok, report_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "evidence_and_git_action_boundary": observation(gate_ok, None if gate_ok else {"source_audit": audit, "invalid": invalid_detail, "changed_inputs": changed, "workspace_redlines": redlines, "external_action_claims": claims}),
    }
