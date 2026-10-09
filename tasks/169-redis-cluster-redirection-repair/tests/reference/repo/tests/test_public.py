import unittest

from src.cluster_retry import plan_cluster_retries


def policy():
    return {"max_attempts": 3, "base_backoff_ms": 100, "max_backoff_ms": 400, "reserve_ms": 50}


def request(**updates):
    value = {
        "request_id": "public",
        "command": "GET",
        "key_slots": [5],
        "target_node": "node-a",
        "outcome": "MOVED",
        "redirect_slot": 5,
        "redirect_node": "node-b",
        "attempt": 1,
        "idempotent": True,
        "result_received": False,
        "deadline_remaining_ms": 500,
    }
    value.update(updates)
    return value


class ClusterRetryTests(unittest.TestCase):
    def test_moved_updates_cache_and_retries(self):
        result = plan_cluster_retries([request()], [{"slot": 5, "node": "node-a"}], policy())
        self.assertEqual(result["decisions"][0]["reason"], "moved")
        self.assertEqual(result["slots"], [{"slot": 5, "node": "node-b"}])

    def test_ask_is_one_shot_without_cache_update(self):
        result = plan_cluster_retries([request(outcome="ASK")], [{"slot": 5, "node": "node-a"}], policy())
        self.assertTrue(result["decisions"][0]["send_asking"])
        self.assertIsNone(result["decisions"][0]["update_slot"])
        self.assertEqual(result["slots"], [{"slot": 5, "node": "node-a"}])

    def test_timeout_write_is_not_replayed(self):
        row = plan_cluster_retries([request(outcome="TIMEOUT", redirect_slot=None, redirect_node=None, command="INCR", idempotent=False)], [], policy())["decisions"][0]
        self.assertEqual(row["reason"], "ambiguous_non_idempotent")


if __name__ == "__main__":
    unittest.main()
