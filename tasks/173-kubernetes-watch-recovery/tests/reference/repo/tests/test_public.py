import unittest

from src.watch_recovery import recover_watches


def policy():
    return {"max_attempts": 3, "require_initial_bookmark": True}


def watch(**updates):
    value = {
        "watch_id":"public","mode":"watch","requested_rv":"start","rv_match":"Exact",
        "send_initial_events":False,"allow_bookmarks":True,
        "last_applied_rv":"z-cursor","initial_complete":True,"outcome":"EVENT",
        "event_type":"MODIFIED","event_rv":"a-cursor","attempt":1,
    }
    value.update(updates)
    return value


class WatchTests(unittest.TestCase):
    def test_different_opaque_event_cursor_applies(self):
        row = recover_watches([watch()], policy())["decisions"][0]
        self.assertEqual((row["action"], row["next_rv"]), ("apply_event", "a-cursor"))

    def test_equal_event_cursor_is_duplicate(self):
        row = recover_watches(
            [watch(last_applied_rv="same", event_rv="same")], policy()
        )["decisions"][0]
        self.assertEqual(row["reason"], "duplicate_event")

    def test_gone_relists_and_resets(self):
        row = recover_watches(
            [watch(outcome="GONE", event_type=None, event_rv=None)], policy()
        )["decisions"][0]
        self.assertEqual(row["action"], "relist")
        self.assertTrue(row["reset_state"])


if __name__ == "__main__":
    unittest.main()
