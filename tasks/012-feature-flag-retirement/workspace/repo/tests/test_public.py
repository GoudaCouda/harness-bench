import json
import unittest
from pathlib import Path

from src.checkout_policy import select_checkout_engine


POLICY = json.loads(
    (Path(__file__).resolve().parents[1] / "policy.json").read_text(encoding="utf-8")
)


class CheckoutPolicyTests(unittest.TestCase):
    def test_late_historical_replay_uses_recorded_snapshot(self):
        event = {
            "event_id": "evt-old",
            "event_time": "2026-07-31T23:59:59Z",
            "received_at": "2026-08-03T12:00:00Z",
            "account_id": "acct-a",
            "flag_snapshot": {"checkout_v2": False},
        }
        self.assertEqual(select_checkout_engine(event, POLICY), {
            "event_id": "evt-old", "engine": "v1",
            "decision_source": "historical_snapshot",
        })

    def test_exact_cutoff_ignores_old_snapshot(self):
        event = {
            "event_id": "evt-cutoff",
            "event_time": "2026-08-01T00:00:00Z",
            "received_at": "2026-08-01T00:00:01Z",
            "account_id": "acct-b",
            "flag_snapshot": {"checkout_v2": False},
        }
        self.assertEqual(select_checkout_engine(event, POLICY)["engine"], "v2")


if __name__ == "__main__":
    unittest.main()
