import unittest

from src.window_reconciler import reconcile_event_windows


class WindowTests(unittest.TestCase):
    def test_uses_event_time_not_ingest_time(self):
        events = [{"event_id": "a", "key": "k", "event_ms": 10, "ingest_ms": 90, "value": 2}]
        result = reconcile_event_windows(events, [], 100, 20, 50)
        self.assertEqual(result["windows"][0]["start_ms"], 0)

    def test_exact_lateness_boundary_is_final(self):
        prior = [{"key": "k", "start_ms": 0, "end_ms": 50, "sum": 1, "event_ids": ["a"], "revision": 1, "final": False}]
        result = reconcile_event_windows([], prior, 70, 20, 50)
        self.assertTrue(result["windows"][0]["final"])


if __name__ == "__main__":
    unittest.main()
