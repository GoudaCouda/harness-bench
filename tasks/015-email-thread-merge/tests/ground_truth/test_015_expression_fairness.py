from __future__ import annotations

import importlib.util
from pathlib import Path


OUTCOME_PATH = Path(__file__).resolve().parents[1] / "test_outcome.py"


def _outcome_module():
    spec = importlib.util.spec_from_file_location("task015_outcome", OUTCOME_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_customer_acknowledgment_and_confirmation_request_accept_natural_prose() -> (
    None
):
    module = _outcome_module()
    reply = """
Hi Morgan,

I received your request to send the questionnaire today. The committed
deadline remains Friday, August 7. August 18 is tentative and contingent on
procurement review. Please let me know once procurement review is complete.
"""

    passed, failures = module._reply_result(reply)

    assert passed, failures


def test_named_customer_contact_can_own_procurement_followup() -> None:
    module = _outcome_module()
    milestone = {
        "owner": "Morgan Lee",
        "status": "blocked",
        "target_date": None,
        "blocked_by": ["security_questionnaire"],
        "next_action": "Complete the pending procurement review",
    }

    passed, failures = module._milestone_state(
        milestone,
        "procurement_approval",
    )

    assert passed, failures
