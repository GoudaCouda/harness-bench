import unittest

from src.archive_manifest import canonical_archive_manifest


class ArchiveManifestTests(unittest.TestCase):
    def test_strips_build_root_and_sorts(self):
        entries = [
            {"path": "w/dist/z", "kind": "file", "sha256": "a" * 64, "executable": False, "mtime": 9},
            {"path": "w/dist/a", "kind": "file", "sha256": "b" * 64, "executable": True, "mtime": 8},
        ]
        result = canonical_archive_manifest(entries, 1700000001, "w/dist")
        self.assertEqual([row["path"] for row in result], ["a", "z"])

    def test_timestamp_is_canonical(self):
        entries = [{"path": "b/x", "kind": "file", "sha256": "c" * 64, "executable": False, "mtime": 4}]
        self.assertEqual(canonical_archive_manifest(entries, 1700000001, "b")[0]["timestamp"], 1700000000)


if __name__ == "__main__":
    unittest.main()
