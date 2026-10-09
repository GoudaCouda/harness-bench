import unittest

from src.early_data import plan_early_data


POLICY = {
    "max_ticket_age_sec": 60,
    "max_attempts": 2,
    "require_anti_replay_consistency": True,
    "safe_methods": ["GET", "HEAD"],
}


def session():
    return {
        "ticket_age_sec": 10,
        "remembered_alpn": "h3",
        "current_alpn": "h3",
        "transport_parameters_match": True,
        "application_settings_match": True,
        "anti_replay_consistent": True,
    }


def request(**updates):
    value = {
        "request_id": "public",
        "method": "GET",
        "app_opt_in": True,
        "body_replayable": True,
        "via_intermediary": False,
        "received_in_early_data": False,
        "early_data_header": [],
        "origin_supports_425": False,
        "explicitly_configured_safe": False,
        "early_data_state": "not_sent",
        "response_status": None,
        "attempt": 1,
    }
    value.update(updates)
    return value


class EarlyDataTests(unittest.TestCase):
    def test_safe_direct_read_can_use_early_data(self):
        row = plan_early_data([request()], session(), POLICY)["decisions"][0]
        self.assertEqual((row["action"], row["reason"]), ("send_0rtt", "eligible"))

    def test_425_retries_only_after_handshake(self):
        row = plan_early_data(
            [request(early_data_state="accepted", response_status=425)],
            session(),
            POLICY,
        )["decisions"][0]
        self.assertEqual(row["action"], "retry_after_handshake")
        self.assertTrue(row["reset_application_state"])

    def test_post_waits_for_handshake(self):
        row = plan_early_data([request(method="POST")], session(), POLICY)["decisions"][0]
        self.assertEqual(row["reason"], "method_not_safe")


if __name__ == "__main__":
    unittest.main()
