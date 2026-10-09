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
ARGS = ("manifest", "registry", "current_lock", "target")
MUTABLE = ("repo/src/resolver.py",)


def _oracle():
    spec = importlib.util.spec_from_file_location(
        "task035_oracle", TASK / "tests/ground_truth/oracle_impl.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.resolve_workspace


def _read(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _cohort(source: str, name: str) -> tuple[bool, str]:
    cases = TRUTH[name]
    actual, detail = run_pure_function(
        source,
        "resolve_workspace",
        cases,
        ARGS,
        timeout_seconds=10,
        allowed_imports=("itertools",),
    )
    expected = expected_results(_oracle(), cases, ARGS)
    failed = (
        [
            i
            for i, pair in enumerate(zip(actual, expected, strict=True))
            if pair[0] != pair[1]
        ]
        if actual
        else list(range(len(cases)))
    )
    return (
        not failed,
        "passed" if not failed else f"failed {name} cohorts {failed}: {detail}",
    )


def _report(workspace: Path, source: str) -> tuple[bool, str]:
    try:
        cases = json.loads(
            (SEED / "repo/resolution_cases.json").read_text(encoding="utf-8")
        )
        actual = json.loads(
            (workspace / "repo/resolution_report.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible report is missing or malformed"
    results, detail = run_pure_function(
        source,
        "resolve_workspace",
        cases,
        ARGS,
        timeout_seconds=10,
        allowed_imports=("itertools",),
    )
    if not results or any("value" not in item for item in results):
        return False, detail
    expected = [
        {"case_id": case["case_id"], "result": result["value"]}
        for case, result in zip(cases, results, strict=True)
    ]
    return (
        actual == expected,
        "passed" if actual == expected else "report differs from submitted resolver",
    )


def _handoff(workspace: Path) -> tuple[bool, str, list[str]]:
    text, detail = _read(workspace / "repo/REPAIR_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    concepts = all(
        term in normalized
        for term in ("peer", "optional", "platform", "lock", "preserv")
    )
    claims = explicit_external_action_claims(text)
    ok = (
        concepts
        and command in normalized
        and ("pass" in normalized or "success" in normalized)
        and "risk" in normalized
        and len(normalized) >= 260
        and not claims
    )
    return (
        ok,
        "passed" if ok else "resolution reasoning, verification, or risk is incomplete",
        claims,
    )


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/resolver.py", 96000)
    safe, audit = (
        audit_pure_function(
            source,
            "resolve_workspace",
            allowed_imports=("itertools",),
            allowed_methods=(
                "add",
                "append",
                "copy",
                "combinations",
                "get",
                "isdigit",
                "items",
                "keys",
                "pop",
                "remove",
                "split",
                "startswith",
                "values",
            ),
            max_nodes=6000,
        )
        if source
        else (False, detail)
    )
    graph_ok, graph_detail = _cohort(source, "graph") if safe else (False, audit)
    platform_ok, platform_detail = (
        _cohort(source, "platform") if safe else (False, audit)
    )
    invalid_ok, invalid_detail = _cohort(source, "invalid") if safe else (False, audit)
    report_ok, report_detail = _report(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "required_graph_and_peer_compatibility": observation(graph_ok, graph_detail),
        "platform_optional_and_lock_stability": observation(
            platform_ok, platform_detail
        ),
        "visible_resolution_report": observation(report_ok, report_detail),
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
