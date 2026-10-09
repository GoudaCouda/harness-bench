from __future__ import annotations

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
VISIBLE = json.loads((TASK / "tests/ground_truth/visible_next_fire.json").read_text(encoding="utf-8"))
MUTABLE = ('repo/src/cron.py',)


def _read_text(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _run(source: str, cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    return run_pure_function(source, 'next_fire', cases, ("expr", "after"), timeout_seconds=5)


def _valid(source: str) -> tuple[bool, str]:
    results, detail = _run(source, GROUND_TRUTH["valid"])
    if not results:
        return False, detail
    failed = [
        index
        for index, (result, case) in enumerate(zip(results, GROUND_TRUTH["valid"], strict=True))
        if result.get("value") != case["expected"] or result.get("unchanged") is not True
    ]
    return not failed, "passed" if not failed else f"failed valid cohorts {failed}"


def _invalid(source: str) -> tuple[bool, str]:
    results, detail = _run(source, GROUND_TRUTH["invalid"])
    if not results:
        return False, detail
    failed = [index for index, result in enumerate(results) if result.get("error") != "ValueError"]
    return not failed, "passed" if not failed else f"accepted invalid cohorts {failed}"


def _visible(workspace: Path, rel: str) -> tuple[bool, str]:
    try:
        candidate = json.loads((workspace / rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "snapshot missing or malformed"
    return candidate == VISIBLE, "passed" if candidate == VISIBLE else "snapshot differs"


def _handoff(workspace: Path, rel: str) -> tuple[bool, str, list[str]]:
    text, detail = _read_text(workspace / rel, 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    command = "pythondontwritebytecode=1 python -m unittest discover -s tests -v"
    claims = explicit_external_action_claims(text)
    ok = (
        all(word in normalized for word in ('field', 'after', 'dow',))
        and command in normalized
        and ("pass" in normalized or "success" in normalized)
        and "risk" in normalized
        and len(normalized) >= 240
        and not claims
    )
    return ok, "passed" if ok else "decision, verification, or risk is incomplete", claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, detail = _read_text(workspace / 'repo/src/cron.py', 48000)
    safe, audit = audit_pure_function(source, 'next_fire') if source else (False, detail)
    if safe:
        valid_ok, valid_detail = _valid(source)
        invalid_ok, invalid_detail = _invalid(source)
        behavior_ok = valid_ok and invalid_ok
        behavior_detail = "passed" if behavior_ok else {"valid": valid_detail, "invalid": invalid_detail}
    else:
        behavior_ok = False
        behavior_detail = audit
    visible_rel = "repo/" + 'visible_next_fire.json'.replace("visible_", "").replace(".json", "") + ".json"
    visible_ok, visible_detail = _visible(workspace, visible_rel)
    handoff_ok, handoff_detail, claims = _handoff(workspace, "repo/IMPLEMENTATION_NOTES.md")
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines and not claims
    return {
        "function_behavior": observation(behavior_ok, behavior_detail),
        "visible_snapshot": observation(visible_ok, visible_detail),
        "verification_handoff": observation(handoff_ok, handoff_detail),
        "source_and_workspace_boundary": observation(
            gate_ok,
            None if gate_ok else {"changed_inputs": changed, "workspace_redlines": redlines, "claims": claims},
        ),
    }
