import unittest

from archive_preflight import plan_extraction


POLICY = {
    "case_sensitive": False,
    "max_files": 3,
    "max_file_bytes": 100,
    "max_total_bytes": 200,
    "allowed_types": ["file", "dir"],
}


class ArchivePreflightTests(unittest.TestCase):
    def test_safe_nested_files_preserve_order(self):
        entries = [
            {"path": "pkg", "type": "dir", "size": 0},
            {"path": "pkg/a.txt", "type": "file", "size": 10},
        ]
        self.assertEqual(plan_extraction(entries, POLICY), entries)

    def test_parent_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_extraction(
                [{"path": "../escape", "type": "file", "size": 1}],
                POLICY,
            )


if __name__ == "__main__":
    unittest.main()
