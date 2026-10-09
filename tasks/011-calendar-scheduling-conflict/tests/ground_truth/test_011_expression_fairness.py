from __future__ import annotations

import importlib.util
import json
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "task_011_outcome_fairness", TASK / "tests" / "test_outcome.py"
)
assert SPEC and SPEC.loader
OUTCOME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OUTCOME)


def test_natural_customer_coordination_language_is_accepted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = json.loads(
        (TASK / "tests" / "reference" / "scheduling_plan.json").read_text(
            encoding="utf-8"
        )
    )
    plan["participant_local_times"] = {
        "alex@example.com": "Tuesday, May 12, 11:30 AM - 12:15 PM",
        "priya@example.com": "Tuesday, May 12, 4:30 PM - 5:15 PM",
        "marco@example.com": "Tuesday, May 12, 12:30 PM - 1:15 PM",
        "dana@northwind.example": "Tuesday, May 12, 10:30 AM - 11:15 AM",
    }
    (workspace / "scheduling_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (workspace / "customer_reply.md").write_text(
        """Dear Dana,

We would like to schedule a 45-minute Northwind renewal risk review with our
Incident Lead, Commercial Owner, Product Owner, and you as customer decision
maker. We recommend Tuesday, May 12: 10:30 AM - 11:15 AM CDT
(11:30 AM - 12:15 PM EDT).

If that does not work, alternatives are Wednesday, May 13: 10:45 AM - 11:30 AM
CDT (11:45 AM - 12:30 PM EDT), or Wednesday, May 13: 11:30 AM - 12:15 PM CDT
(12:30 PM - 1:15 PM EDT). Please let us know which option works best, and we
will then send the calendar invitation.
""",
        encoding="utf-8",
    )

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["customer_ready_coordination"]["pass"] is True
    assert checks["auditable_time_zone_handoff"]["pass"] is True
    assert checks["professional_contingency_language"]["pass"] is True


def test_reply_still_rejects_missing_second_fallback(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("scheduling_plan.json", "customer_reply.md"):
        source = TASK / "tests" / "reference" / name
        (workspace / name).write_bytes(source.read_bytes())
    reply = (workspace / "customer_reply.md").read_text(encoding="utf-8")
    reply = "\n".join(line for line in reply.splitlines() if "Fallback 2" not in line)
    (workspace / "customer_reply.md").write_text(reply, encoding="utf-8")

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["customer_ready_coordination"]["pass"] is False
