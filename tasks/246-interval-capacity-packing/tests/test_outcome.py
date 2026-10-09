from __future__ import annotations

import json
from pathlib import Path

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
EXPECTED = json.loads(
    (TASK / "tests/ground_truth/expected_assignment.json").read_text(encoding="utf-8")
)


def _load(workspace: Path) -> dict | None:
    path = workspace / "assignment.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _handoff(workspace: Path) -> tuple[bool, str]:
    path = workspace / "PACKING_NOTES.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False, "notes missing"
    normalized = " ".join(text.casefold().split())
    claims = explicit_external_action_claims(text)
    ok = (
        all(word in normalized for word in ("end", "capacit", "unplaced", "risk"))
        and len(normalized) >= 240
        and not claims
    )
    return ok, "passed" if ok else "notes omit packing evidence or risk"


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    candidate = _load(workspace)
    assigned = candidate.get("assignments") if candidate else None
    unplaced = candidate.get("unplaced") if candidate else None
    assign_ok = assigned == EXPECTED["assignments"]
    unplaced_ok = unplaced == EXPECTED["unplaced"]
    notes_ok, notes_detail = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines
    return {
        "machine_assignment": observation(
            assign_ok, "passed" if assign_ok else "assignment map differs"
        ),
        "unplaced_jobs": observation(
            unplaced_ok, "passed" if unplaced_ok else "unplaced list differs"
        ),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_workspace_boundary": observation(
            gate_ok,
            None if gate_ok else {"changed_inputs": changed, "workspace_redlines": redlines},
        ),
    }
