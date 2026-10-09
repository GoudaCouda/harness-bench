import unittest

from src.refresh_recovery import reconcile_refresh


class RefreshRecoveryTests(unittest.TestCase):
    def test_first_success_wins_and_later_invalid_grant_is_ignored(self):
        session = {"generation":9,"access_token":"pub-a9","refresh_token":"pub-r9","scope":["profile"],"rotation_required":True,"status":"active"}
        attempts = [
            {"request_id":"pub-1","observed_generation":9,"used_refresh_token":"pub-r9","sequence":40,"response":{"kind":"success","access_token":"pub-a10","refresh_token":"pub-r10","scope":["profile"]}},
            {"request_id":"pub-2","observed_generation":9,"used_refresh_token":"pub-r9","sequence":41,"response":{"kind":"error","error":"invalid_grant"}},
        ]
        result = reconcile_refresh(session, attempts)
        self.assertEqual(result["decision"], "adopt_success")
        self.assertEqual(result["winner_request_id"], "pub-1")
        self.assertEqual(result["ignored_request_ids"], ["pub-2"])

    def test_invalid_grant_before_success_requires_reauthentication(self):
        session = {"generation":12,"access_token":"pub-a12","refresh_token":"pub-r12","scope":["calendar"],"rotation_required":True,"status":"active"}
        attempts = [
            {"request_id":"pub-a","observed_generation":12,"used_refresh_token":"pub-r12","sequence":70,"response":{"kind":"error","error":"invalid_grant"}},
            {"request_id":"pub-b","observed_generation":12,"used_refresh_token":"pub-r12","sequence":71,"response":{"kind":"success","access_token":"pub-a13","refresh_token":"pub-r13","scope":["calendar"]}},
        ]
        result = reconcile_refresh(session, attempts)
        self.assertEqual(result["decision"], "reauth_required")
        self.assertIsNone(result["next_session"]["refresh_token"])


if __name__ == "__main__":
    unittest.main()
