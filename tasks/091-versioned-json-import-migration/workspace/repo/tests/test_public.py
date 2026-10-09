import unittest

from src.import_migrator import migrate_batch


DEFAULTS = {"retry_limit": 3, "region": "us-central"}


class ImportMigratorTests(unittest.TestCase):
    def test_v1_missing_and_null_are_distinct(self):
        records = [
            {"source_id": "missing", "document": {"schema_version": 1, "name": "a", "endpoint": "https://a"}},
            {"source_id": "null", "document": {"schema_version": 1, "name": "b", "endpoint": "https://b", "retries": None, "region": None}},
        ]
        result = migrate_batch(records, DEFAULTS)
        self.assertEqual(result["migrated"][0]["document"]["connection"], {"endpoint": "https://a", "retry_limit": 3, "region": "us-central"})
        self.assertEqual(result["migrated"][1]["document"]["connection"], {"endpoint": "https://b", "retry_limit": 0, "region": None})

    def test_v2_features_become_sorted_enabled_names(self):
        records = [{"source_id": "v2", "document": {"schema_version": 2, "identity": {"name": "svc"}, "connection": {"endpoint": "https://svc", "retry_limit": 2}, "features": {"z": True, "a": True, "off": False}, "extensions": {}}}]
        result = migrate_batch(records, DEFAULTS)
        self.assertEqual(result["migrated"][0]["document"]["enabled_features"], ["a", "z"])


if __name__ == "__main__":
    unittest.main()
