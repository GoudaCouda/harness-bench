import unittest

from src.watch_reconciler import reconcile_batch


POLICY = {"roots": ["config"], "extensions": [".json"], "temporary_prefixes": ["."], "temporary_suffixes": [".tmp"]}
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class WatchReconcilerTests(unittest.TestCase):
    def test_atomic_save_coalesces_to_reload(self):
        checkpoint = {"seq": 1, "watched": {"config/app.json": {"inode": 10, "digest": DIGEST_A}}}
        batch = {"seq": 2, "events": [{"kind": "rename", "path": "config/app.json"}, {"kind": "change", "path": "config/app.json"}], "snapshot": {"config/app.json": {"type": "file", "inode": 11, "digest": DIGEST_B}}}
        result = reconcile_batch(checkpoint, batch, POLICY)
        self.assertEqual(result["actions"], [{"path": "config/app.json", "action": "reload", "reason": "content_changed"}])

    def test_same_content_new_inode_rebinds(self):
        checkpoint = {"seq": 1, "watched": {"config/app.json": {"inode": 10, "digest": DIGEST_A}}}
        batch = {"seq": 2, "events": [{"kind": "rename", "path": None}], "snapshot": {"config/app.json": {"type": "file", "inode": 12, "digest": DIGEST_A}}}
        self.assertEqual(reconcile_batch(checkpoint, batch, POLICY)["actions"][0]["action"], "rebind")


if __name__ == "__main__":
    unittest.main()
