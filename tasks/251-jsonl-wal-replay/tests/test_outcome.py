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
STORE = json.loads((TASK / "tests/ground_truth/expected_store.json").read_text(encoding="utf-8"))
REPORT = json.loads((TASK / "tests/ground_truth/expected_report.json").read_text(encoding="utf-8"))


def _load(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _handoff(workspace: Path) -> tuple[bool, str]:
    path = workspace / "REPLAY_NOTES.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False, "notes missing"
    normalized = " ".join(text.casefold().split())
    claims = explicit_external_action_claims(text)
    ok = (
        all(word in normalized for word in ("torn", "op_id", "delete", "risk"))
        and len(normalized) >= 240
        and not claims
    )
    return ok, "passed" if ok else "notes omit WAL evidence or risk"


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    store_ok = _load(workspace / "store.json") == STORE
    report_ok = _load(workspace / "replay_report.json") == REPORT
    notes_ok, notes_detail = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines
    return {
        "store_state": observation(store_ok, "passed" if store_ok else "store differs"),
        "replay_report": observation(report_ok, "passed" if report_ok else "report differs"),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_and_workspace_boundary": observation(
            gate_ok,
            None if gate_ok else {"changed_inputs": changed, "workspace_redlines": redlines},
        ),
    }
