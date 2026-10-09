from __future__ import annotations

import ast
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
ARGS = ("state", "operations", "policy")
IMPORTS = ("copy", "math")
MUTABLE = ("repo/src/cache_engine.py",)


def _audit_candidate(source):
    """Permit deletion from in-memory mappings without granting I/O capability."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Delete) and any(
            not isinstance(target, ast.Subscript) for target in node.targets
        ):
            return False, "delete is limited to in-memory mapping entries"

    class _NormalizeMappingDelete(ast.NodeTransformer):
        def visit_Delete(self, node):  # noqa: N802
            return [
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=target.value,
                            attr="pop",
                            ctx=ast.Load(),
                        ),
                        args=[target.slice],
                        keywords=[],
                    )
                )
                for target in node.targets
            ]

    audited_tree = _NormalizeMappingDelete().visit(tree)
    ast.fix_missing_locations(audited_tree)
    return audit_pure_function(
        ast.unparse(audited_tree),
        "replay_cache",
        allowed_imports=IMPORTS,
        allowed_methods=(
            "append",
            "deepcopy",
            "get",
            "isfinite",
            "items",
            "keys",
            "pop",
            "update",
            "values",
        ),
        max_nodes=18000,
    )


def _oracle():
    spec = importlib.util.spec_from_file_location(
        "task092_oracle", TASK / "tests/ground_truth/oracle_impl.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.replay_cache


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
        source, "replay_cache", cases, ARGS, allowed_imports=IMPORTS
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
        "passed" if not failed else f"failed {name} cases {failed}: {detail}",
    )


def _visible(workspace, source):
    def load(root, name):
        return json.loads((root / f"repo/{name}.json").read_text())

    try:
        state, operations, policy = (
            load(SEED, name) for name in ("state", "operations", "policy")
        )
        actual_state, actual_events = (
            load(workspace, f"out/{name}") for name in ("state", "events")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible outputs are missing or malformed"
    results, detail = run_pure_function(
        source,
        "replay_cache",
        [{"state": state, "operations": operations, "policy": policy}],
        ARGS,
        allowed_imports=IMPORTS,
    )
    if not results or "value" not in results[0]:
        return False, detail
    value = results[0]["value"]
    ok = actual_state == value["state"] and actual_events == value["events"]
    return ok, "passed" if ok else "outputs differ from the submitted cache engine"


def _handoff(workspace):
    text, detail = _read(workspace / "repo/CACHE_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    concepts = all(
        term in normalized
        for term in (
            "ttl",
            "boundary",
            "access",
            "lexical",
            "pinned",
            "overwrite",
            "transaction",
            "validation",
            "unittest",
            "replay_cache.py",
        )
    ) and ("immutable" in normalized or "immutability" in normalized)
    claims = explicit_external_action_claims(text)
    ok = (
        concepts
        and ("pass" in normalized or "success" in normalized)
        and len(normalized) >= 430
        and not claims
    )
    return (
        ok,
        "passed"
        if ok
        else "cache invariants, verification, or runtime boundary is incomplete",
        claims,
    )


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/cache_engine.py", 128000)
    safe, audit = _audit_candidate(source) if source else (False, detail)
    eviction_ok, eviction_detail = (
        _cohort(source, "eviction") if safe else (False, audit)
    )
    boundary_ok, boundary_detail = (
        _cohort(source, "boundaries") if safe else (False, audit)
    )
    invalid_ok, invalid_detail = _cohort(source, "invalid") if safe else (False, audit)
    visible_ok, visible_detail = _visible(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "ttl_lru_and_overwrite": observation(eviction_ok, eviction_detail),
        "pinned_transactional_failure": observation(boundary_ok, boundary_detail),
        "visible_cache_replay": observation(visible_ok, visible_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_runtime_boundary": observation(
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
