import unittest

from src.migration_planner import plan_online_migration


POLICY = {
    "contract_allowed": True,
    "max_lock_waiters": 2,
    "max_replica_lag_ms": 97,
    "required_stable_windows": 3,
}


def snapshot(**changes):
    value = {
        "snapshot_id": "public",
        "deployed_versions": ["v2"],
        "dual_write_versions": ["v2"],
        "read_target_versions": [],
        "old_write_versions": ["v2"],
        "target_exists": True,
        "target_nullable": True,
        "backfill_cursor": 5,
        "total_rows": 10,
        "target_rows": 5,
        "mismatch_rows": 0,
        "constraint_state": "absent",
        "old_column_exists": True,
        "old_read_qps": 5,
        "stable_windows": 0,
        "replica_lag_ms": 10,
        "lock_waiters": 0,
    }
    value.update(changes)
    return value


class MigrationTests(unittest.TestCase):
    def test_partial_backfill_plans_batch(self):
        row = plan_online_migration([snapshot()], POLICY)["decisions"][0]
        self.assertEqual((row["status"], row["action"]), ("ready", "backfill_batch"))

    def test_high_lag_blocks_backfill(self):
        row = plan_online_migration([snapshot(replica_lag_ms=98)], POLICY)["decisions"][
            0
        ]
        self.assertEqual((row["status"], row["reason"]), ("blocked", "database_load"))


if __name__ == "__main__":
    unittest.main()
