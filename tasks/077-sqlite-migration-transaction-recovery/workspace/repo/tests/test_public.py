import unittest
from src.migration_recovery import plan_migration_recovery


def migration():
    return {"id":"m2","from_version":1,"to_version":2,"checksum":"a" * 64,"statements":["CREATE TABLE x(id INTEGER)"]}


class MigrationRecoveryTests(unittest.TestCase):
    def test_clean_plan_is_one_immediate_transaction(self):
        result = plan_migration_recovery(migration(), {"user_version":1,"ledger":[{"id":"m1","from_version":0,"to_version":1,"checksum":"b" * 64}]}, {"phase":"clean","transaction_active":False})
        self.assertEqual(result["actions"][0], "begin_immediate")
        self.assertEqual(result["actions"][-1], "commit")
        self.assertEqual(result["retry_scope"], "none")

    def test_busy_commit_retries_commit_without_rollback(self):
        result = plan_migration_recovery(migration(), {"user_version":1,"ledger":[{"id":"m1","from_version":0,"to_version":1,"checksum":"b" * 64}]}, {"phase":"busy_commit","transaction_active":True})
        self.assertEqual(result["actions"], ["wait_backoff", "commit"])


if __name__ == "__main__":
    unittest.main()
