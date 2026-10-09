import unittest
from src.cache_engine import replay_cache


class CacheTests(unittest.TestCase):
    def test_ttl_boundary_and_get_recency(self):
        state = {"clock": 5, "next_access": 2, "entries": {"x": {"value": 1, "size": 1, "expires_at": 6, "last_access": 1, "pinned": False}}}
        result = replay_cache(state, [{"op": "advance", "to": 6}, {"op": "get", "key": "x"}], {"capacity": 4, "max_entry_size": 4})
        self.assertEqual(result["events"][0]["expired"], ["x"])
        self.assertEqual(result["events"][1]["status"], "miss")

    def test_failed_put_preserves_pinned_and_old_value(self):
        state = {"clock": 0, "next_access": 2, "entries": {"x": {"value": "old", "size": 4, "expires_at": 9, "last_access": 1, "pinned": True}}}
        operation = {"op": "put", "key": "x", "value": "new", "size": 5, "ttl": 2, "pinned": False}
        result = replay_cache(state, [operation], {"capacity": 4, "max_entry_size": 4})
        self.assertEqual(result["events"][0]["status"], "rejected_size")
        self.assertEqual(result["state"]["entries"]["x"]["value"], "old")


if __name__ == "__main__":
    unittest.main()
