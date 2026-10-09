from __future__ import annotations

import importlib.util
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "task_052_outcome", TASK / "tests" / "test_outcome.py"
)
assert SPEC and SPEC.loader
OUTCOME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OUTCOME)


def test_bad_ics_does_not_erase_verified_live_workflow(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "appointment_summary.md").write_text(
        "run-specific receipt summary", encoding="utf-8"
    )
    (workspace / "appointment.ics").write_text(
        "BEGIN:VCALENDAR\nCLASS:TENTATIVE\nEND:VCALENDAR\n", encoding="utf-8"
    )
    hold = {
        "slot_id": "PAS-204",
        "hold_id": "HLD-0123456789",
        "status": "held",
    }
    events = [
        {
            "sequence": 1,
            "action": "search",
            "outcome": "ok",
            "result_slot_ids": ["PAS-204"],
            "session_fingerprint": "abc123def456",
        },
        {
            "sequence": 2,
            "action": "view_slot_detail",
            "outcome": "ok",
            "slot_id": "PAS-204",
            "session_fingerprint": "abc123def456",
        },
        {
            "sequence": 3,
            "action": "place_hold",
            "outcome": "held",
            "slot_id": "PAS-204",
            "hold_id": "HLD-0123456789",
            "session_fingerprint": "abc123def456",
        },
    ]
    state = {"holds": [hold], "events": events}

    monkeypatch.setattr(OUTCOME, "_trusted_state", lambda _workspace: (state, ""))
    monkeypatch.setattr(OUTCOME, "_hold_record_valid", lambda *_args: True)
    monkeypatch.setattr(OUTCOME, "_active_hold", lambda *_args: True)
    monkeypatch.setattr(OUTCOME, "_choice_complete", lambda *_args: True)
    monkeypatch.setattr(OUTCOME, "_summary_matches_hold", lambda *_args: True)
    monkeypatch.setattr(OUTCOME, "_ics_matches", lambda *_args: False)
    monkeypatch.setattr(OUTCOME, "_preparation_complete", lambda *_args: True)

    checks = OUTCOME.evaluate_cases(workspace)

    assert checks["verified_handoff"]["pass"] is False
    assert checks["real_workflow_evidence"]["pass"] is True
