import unittest

from src.lease_reconciler import reconcile_leases


class LeaseTests(unittest.TestCase):
    def test_exact_expiry_releases_capacity(self):
        state = {"capacity": 2, "next_fence": 4, "leases": [{"request_id": "old", "owner": "a", "units": 2, "acquired_ms": 0, "expires_ms": 10, "fence": 3}]}
        requests = [{"request_id": "new", "owner": "b", "units": 2, "requested_ms": 10, "ttl_ms": 5}]
        result = reconcile_leases(state, requests, 10)
        self.assertEqual(result["decisions"][0]["status"], "granted")
        self.assertEqual(result["leases"][0]["request_id"], "new")

    def test_active_replay_keeps_fence(self):
        state = {"capacity": 3, "next_fence": 10, "leases": [{"request_id": "r", "owner": "a", "units": 1, "acquired_ms": 1, "expires_ms": 20, "fence": 9}]}
        request = [{"request_id": "r", "owner": "a", "units": 1, "requested_ms": 2, "ttl_ms": 100}]
        result = reconcile_leases(state, request, 5)
        self.assertTrue(result["decisions"][0]["replayed"])
        self.assertEqual(result["decisions"][0]["fence"], 9)
        self.assertEqual(result["next_fence"], 10)


if __name__ == "__main__":
    unittest.main()
