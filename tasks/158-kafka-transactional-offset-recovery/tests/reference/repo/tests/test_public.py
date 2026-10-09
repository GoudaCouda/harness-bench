import unittest

from src.transaction_recovery import plan_transaction_recovery


POLICY = {
    "max_retries": 4,
    "require_read_committed": True,
    "require_transactional_offsets": True,
    "transactional_id_prefix": "public-",
}


def batch(**changes):
    value = {
        "batch_id": "b1",
        "transactional_id": "public-worker-1",
        "group_id": "orders-v2",
        "topic": "orders",
        "partition": 0,
        "first_offset": 10,
        "last_offset": 11,
        "committed_offset": 10,
        "expected_output_keys": ["order-10", "order-11"],
        "visible_output_keys": [],
        "transaction_state": "commit_unknown",
        "attempt": 1,
        "producer_epoch": 4,
        "owner_epoch": 4,
        "consumer_isolation": "read_committed",
        "offset_commit_mode": "transactional",
    }
    value.update(changes)
    return value


class RecoveryTests(unittest.TestCase):
    def test_ambiguous_without_evidence_reinitializes(self):
        row = plan_transaction_recovery([batch()], POLICY)["decisions"][0]
        self.assertEqual(
            (row["status"], row["action"]), ("ready", "reinitialize_and_replay")
        )

    def test_atomic_evidence_settles(self):
        row = plan_transaction_recovery(
            [batch(committed_offset=12, visible_output_keys=["order-10", "order-11"])],
            POLICY,
        )["decisions"][0]
        self.assertEqual((row["status"], row["next_offset"]), ("settled", 12))


if __name__ == "__main__":
    unittest.main()
