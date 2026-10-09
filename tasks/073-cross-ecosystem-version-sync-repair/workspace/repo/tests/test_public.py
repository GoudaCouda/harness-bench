import unittest
from src.version_sync import plan_version_sync


class VersionSyncTests(unittest.TestCase):
    def test_final_release_is_sorted_and_noop_is_preserved(self):
        result = plan_version_sync("v1.2.0", "1.1.9", [
            {"path":"z/package.json","ecosystem":"npm","current":"1.1.9","publish":True},
            {"path":"a/pyproject.toml","ecosystem":"python","current":"1.2.0","publish":False},
        ])
        self.assertEqual([row["path"] for row in result["changes"]], ["a/pyproject.toml", "z/package.json"])
        self.assertEqual(result["changes"][0]["action"], "noop")

    def test_rc_spelling_is_ecosystem_specific(self):
        result = plan_version_sync("2.0.0-rc.3", "2.0.0-rc.2", [
            {"path":"pyproject.toml","ecosystem":"python","current":"2.0.0rc2","publish":True},
            {"path":"package.json","ecosystem":"npm","current":"2.0.0-rc.2","publish":True},
        ])
        self.assertEqual([row["to"] for row in result["changes"]], ["2.0.0-rc.3", "2.0.0rc3"])


if __name__ == "__main__":
    unittest.main()
