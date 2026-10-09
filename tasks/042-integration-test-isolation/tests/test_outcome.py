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
TRUTH = json.loads((TASK / "tests/ground_truth/behavior_cases.json").read_text())
ARGS = ("fixture", "tests", "seed", "quarantines", "day")
MUTABLE = ("repo/src/isolation_runner.py",)


def _oracle():
    spec = importlib.util.spec_from_file_location(
        "task042_oracle", TASK / "tests/ground_truth/oracle_impl.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.run_isolated_suite


def _read(path, limit):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _cohort(source, name):
    cases = TRUTH[name]
    actual, detail = run_pure_function(
        source,
        "run_isolated_suite",
        cases,
        ARGS,
        allowed_imports=("copy",),
    )
    expected = expected_results(_oracle(), cases, ARGS)
    failed = (
        [i for i, p in enumerate(zip(actual, expected, strict=True)) if p[0] != p[1]]
        if actual
        else list(range(len(cases)))
    )
    return (
        not failed,
        "passed" if not failed else f"failed {name} cohorts {failed}: {detail}",
    )


def _report(workspace, source):
    try:
        cases = json.loads((SEED / "repo/isolation_cases.json").read_text())
        actual = json.loads((workspace / "repo/isolation_report.json").read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible report is missing or malformed"
    results, detail = run_pure_function(
        source,
        "run_isolated_suite",
        cases,
        ARGS,
        allowed_imports=("copy",),
    )
    if not results or any("value" not in x for x in results):
        return False, detail
    expected = [
        {"case_id": case["case_id"], "result": result["value"]}
        for case, result in zip(cases, results, strict=True)
    ]
    return (
        actual == expected,
        "passed" if actual == expected else "report differs from submitted runner",
    )


def _handoff(workspace):
    text, detail = _read(workspace / "repo/REPAIR_NOTES.md", 24000)
    if not text:
        return False, detail, []
    low = " ".join(text.casefold().split())
    claims = explicit_external_action_claims(text)
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    ok = (
        all(x in low for x in ("isolat", "seed", "quarantin", "expir", "regression"))
        and command in low
        and ("pass" in low or "success" in low)
        and "risk" in low
        and len(low) >= 260
        and not claims
    )
    return (
        ok,
        "passed" if ok else "isolation reasoning, verification, or risk is incomplete",
        claims,
    )


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/isolation_runner.py", 96000)
    safe, audit = (
        audit_pure_function(
            source,
            "run_isolated_suite",
            allowed_imports=("copy",),
            allowed_methods=(
                "add",
                "append",
                "deepcopy",
                "encode",
                "get",
                "items",
                "keys",
                "values",
            ),
            max_nodes=6000,
        )
        if source
        else (False, detail)
    )
    isolation_ok, isolation_detail = (
        _cohort(source, "isolation") if safe else (False, audit)
    )
    random_ok, random_detail = (
        _cohort(source, "random_quarantine") if safe else (False, audit)
    )
    invalid_ok, invalid_detail = _cohort(source, "invalid") if safe else (False, audit)
    report_ok, report_detail = _report(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "fixture_isolation_and_true_outcomes": observation(
            isolation_ok, isolation_detail
        ),
        "stable_seed_and_quarantine_boundary": observation(random_ok, random_detail),
        "visible_isolation_report": observation(report_ok, report_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_workspace_boundary": observation(
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
