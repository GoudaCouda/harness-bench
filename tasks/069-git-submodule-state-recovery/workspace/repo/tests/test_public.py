import unittest

from src.submodule_recovery import plan_submodule_recovery


def state(**changes):
    base = {"path": "vendor/a", "depth": 0, "recorded_sha": "a" * 40, "checked_out_sha": "b" * 40, "remote_sha": "c" * 40, "initialized": True, "commit_present": True, "dirty": False, "untracked": False, "conflict": False}
    base.update(changes)
    return base


class SubmoduleRecoveryTests(unittest.TestCase):
    def test_targets_recorded_gitlink(self):
        result = plan_submodule_recovery([state()], False)[0]
        self.assertEqual((result["action"], result["target_sha"]), ("checkout_recorded", "a" * 40))

    def test_dirty_worktree_blocks(self):
        result = plan_submodule_recovery([state(dirty=True)], False)[0]
        self.assertEqual((result["status"], result["action"]), ("blocked", "preserve_local_changes"))


if __name__ == "__main__":
    unittest.main()
