import unittest

from src.event_reconciler import reconcile_object_events


POLICY = {
    "allow_delete_markers": True,
    "require_version_id": False,
    "max_key_bytes": 64,
}
OBJECT = {
    "bucket": "demo",
    "key": "x.txt",
    "sequencer": "f",
    "state": "present",
    "version_id": None,
    "etag": "old",
    "size": 1,
}


def event(**changes):
    value = {
        "arrival_index": 0,
        "event_id": "public",
        "bucket": "demo",
        "key": "x.txt",
        "event_name": "ObjectCreated:Put",
        "sequencer": "10",
        "version_id": None,
        "etag": "new",
        "size": 2,
        "event_time": "2026-01-01t00:00:00z",
    }
    value.update(changes)
    return value


class EventTests(unittest.TestCase):
    def test_hex_width_is_compared_numerically(self):
        result = reconcile_object_events([OBJECT], [event()], POLICY)
        self.assertEqual(result["decisions"][0]["status"], "applied")

    def test_lower_sequencer_is_stale(self):
        result = reconcile_object_events([OBJECT], [event(sequencer="e")], POLICY)
        self.assertEqual(result["decisions"][0]["reason"], "stale")


if __name__ == "__main__":
    unittest.main()
