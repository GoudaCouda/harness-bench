"""Adapt trusted legacy facts into all-or-nothing business acceptance cases.

This module is deliberately small.  A migrated task may reuse its old private
oracle as a fact library, but the old field weights never reach the formal
score.  ``tests/test_outcome.py`` declares coherent groups of fact checks and
each group either passes in full or earns no case weight.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from harnessbench.grading.deterministic_oracle import score_workspace_from_spec


def load_private_score(
    workspace: Path,
    *,
    task_id: str,
    hidden_root: Path,
) -> dict[str, Any]:
    """Run one relocated module or declarative oracle from the hidden package."""
    module_path = hidden_root / "oracle_impl.py"
    spec_path = hidden_root / "oracle_spec.json"
    if module_path.is_file() == spec_path.is_file():
        raise RuntimeError(
            "hidden grading package must contain exactly one of oracle_impl.py "
            "and oracle_spec.json"
        )
    if spec_path.is_file():
        return score_workspace_from_spec(Path(workspace), spec_path=spec_path)

    spec = importlib.util.spec_from_file_location(
        f"private_{task_id.replace('-', '_')}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load private outcome assertions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    score_workspace = getattr(module, "score_workspace", None)
    if not callable(score_workspace):
        raise RuntimeError("private outcome assertions lack score_workspace")
    signature = inspect.signature(score_workspace)
    if "ground_truth_path" in signature.parameters:
        return score_workspace(
            Path(workspace),
            ground_truth_path=hidden_root / "ground_truth.json",
        )
    return score_workspace(Path(workspace))


def checks_by_id(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Index well-formed legacy checks without trusting their weights."""
    return {
        str(check["id"]): dict(check)
        for check in result.get("checks", [])
        if isinstance(check, Mapping) and str(check.get("id") or "").strip()
    }


def select_checks(
    checks: Mapping[str, dict[str, Any]], selector: str
) -> list[dict[str, Any]]:
    """Select one exact check or a prefix ending in ``*``."""
    if selector.endswith("*"):
        prefix = selector[:-1]
        return [
            check for check_id, check in checks.items() if check_id.startswith(prefix)
        ]
    return [checks[selector]] if selector in checks else []


def group_observation(
    checks: Mapping[str, dict[str, Any]],
    selectors: Sequence[str],
) -> dict[str, Any]:
    """Require every named private fact; fail closed on a stale selector."""
    failed: set[str] = set()
    missing: list[str] = []
    selected: set[str] = set()
    for selector in selectors:
        matched = select_checks(checks, selector)
        if not matched:
            missing.append(selector)
            continue
        for check in matched:
            check_id = str(check["id"])
            selected.add(check_id)
            if not bool(check.get("pass")):
                failed.add(check_id)
    passed = bool(selected) and not failed and not missing
    return {
        "pass": passed,
        "detail": None if passed else {"failed": sorted(failed), "missing": missing},
    }


def grouped_observations(
    result: Mapping[str, Any],
    groups: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    """Convert private fact checks to declared business-level observations."""
    checks = checks_by_id(result)
    # A legacy oracle may use ``error`` for an ordinary invalid candidate
    # (for example, a missing Git worktree).  That is a business-case failure,
    # not evidence that the evaluator itself crashed.  Keep it visible for
    # diagnostics without using the reserved ``private_error`` contract marker
    # emitted by task adapters when loading/executing the evaluator raises.
    candidate_error = str(result.get("error") or "").strip()
    observations: dict[str, object] = {}
    for case_id, selectors in groups.items():
        observation = group_observation(checks, selectors)
        if candidate_error:
            observation = {
                "pass": False,
                "detail": {"candidate_error": candidate_error},
            }
        observations[case_id] = observation
    return observations


def source_files_unchanged(
    workspace: Path,
    *,
    seed: Path,
    mutable_inputs: Iterable[str] = (),
) -> tuple[bool, list[str]]:
    """Compare durable agent-visible sources, excluding declared mutable inputs.

    Interpreter and test-runner caches are reproducible execution residue, not
    source evidence.  Their presence, absence, or Python-version-specific name
    must therefore never trip a zero-score integrity gate.
    """
    mutable = {Path(value).as_posix() for value in mutable_inputs}
    changed: list[str] = []
    for original in seed.rglob("*"):
        if not original.is_file():
            continue
        relative = original.relative_to(seed).as_posix()
        parts = Path(relative).parts
        if "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        if relative in mutable:
            continue
        candidate = Path(workspace) / relative
        try:
            if (
                not candidate.is_file()
                or candidate.read_bytes() != original.read_bytes()
            ):
                changed.append(relative)
        except OSError:
            changed.append(relative)
    return not changed, changed
