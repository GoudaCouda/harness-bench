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
ARGS = ("checkpoint", "segments", "policy")
IMPORTS = ("copy", "json", "math")
MUTABLE = ("repo/src/stream_consumer.py",)


def _oracle():
    spec = importlib.util.spec_from_file_location(
        "task093_oracle", TASK / "tests/ground_truth/oracle_impl.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.consume_segments


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
        source, "consume_segments", cases, ARGS, allowed_imports=IMPORTS
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
    try:

        def load(root, name):
            return json.loads((root / f"repo/{name}.json").read_text())

        checkpoint, segments, policy = (
            load(SEED, name) for name in ("checkpoint", "segments", "policy")
        )
        actual = {
            name: load(workspace, f"out/{name}")
            for name in ("records", "quarantine", "checkpoint")
        }
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible outputs are missing or malformed"
    results, detail = run_pure_function(
        source,
        "consume_segments",
        [{"checkpoint": checkpoint, "segments": segments, "policy": policy}],
        ARGS,
        allowed_imports=IMPORTS,
    )
    if not results or "value" not in results[0]:
        return False, detail
    ok = actual == results[0]["value"]
    return ok, "passed" if ok else "outputs differ from the submitted consumer"


def _handoff(workspace):
    text, detail = _read(workspace / "repo/STREAM_NOTES.md", 24000)
    if not text:
        return False, detail, [], []
    normalized = " ".join(text.casefold().split())
    concepts = all(
        term in normalized
        for term in (
            "offset",
            "pending",
            "newline",
            "duplicate",
            "malformed",
            "quarantine",
            "rotation",
            "eof",
            "validation",
            "immutable",
            "replay_stream.py",
        )
    )
    test_evidence = any(
        term in normalized for term in ("unittest", "unit test", "test_public.py")
    )
    raw_markers = [
        value for value in ("not-json", '"payload":"duplicate"') if value in normalized
    ]
    claims = explicit_external_action_claims(text)
    ok = (
        concepts
        and test_evidence
        and ("pass" in normalized or "success" in normalized)
        and len(normalized) >= 430
        and not raw_markers
        and not claims
    )
    return (
        ok,
        "passed"
        if ok
        else "stream semantics, verification, or ingestion boundary is incomplete",
        raw_markers,
        claims,
    )


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/stream_consumer.py", 128000)
    safe, audit = (
        audit_pure_function(
            source,
            "consume_segments",
            allowed_imports=IMPORTS,
            allowed_methods=(
                "append",
                "deepcopy",
                "endswith",
                "find",
                "get",
                "isfinite",
                "items",
                "loads",
                "pop",
                "split",
                "splitlines",
                "values",
            ),
            max_nodes=18000,
        )
        if source
        else (False, detail)
    )
    continuation_ok, continuation_detail = (
        _cohort(source, "continuation") if safe else (False, audit)
    )
    rotation_ok, rotation_detail = (
        _cohort(source, "rotation") if safe else (False, audit)
    )
    invalid_ok, invalid_detail = _cohort(source, "invalid") if safe else (False, audit)
    visible_ok, visible_detail = _visible(workspace, source) if safe else (False, audit)
    notes_ok, notes_detail, raw_markers, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    validation_ok = safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "partial_resume_and_deduplication": observation(
            continuation_ok, continuation_detail
        ),
        "rotation_eof_and_quarantine": observation(rotation_ok, rotation_detail),
        "visible_stream_replay": observation(visible_ok, visible_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_ingestion_boundary": observation(
            validation_ok,
            None
            if validation_ok
            else {
                "source_audit": audit,
                "invalid": invalid_detail,
                "changed_inputs": changed,
                "workspace_redlines": redlines,
                "external_action_claims": claims,
            },
        ),
    }
