import sqlite3
import unittest

from src.outbox_recovery import recover_outbox


class SQLiteCaptureIntegrationTests(unittest.TestCase):
    def test_rows_loaded_from_transactional_tables_keep_unknown_delivery_as_probe(self):
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        database.execute("create table outbox(event_id, aggregate_id, sequence, payload_hash, status, attempts, lease_owner, lease_until, last_error)")
        database.execute("create table receipts(event_id, attempt, outcome, payload_hash, observed_at)")
        digest = "a" * 64
        database.execute("insert into outbox values(?,?,?,?,?,?,?,?,?)", ("event-1", "order-1", 1, digest, "leased", 1, "relay-old", 80, None))
        database.execute("insert into receipts values(?,?,?,?,?)", ("event-1", 1, "unknown", digest, 90))
        events = [dict(row) for row in database.execute("select * from outbox")]
        receipts = [dict(row) for row in database.execute("select * from receipts")]
        result = recover_outbox(events, receipts, {"now": 100, "worker": "relay-a", "lease_seconds": 30, "max_attempts": 3})
        self.assertEqual(result["actions"][0]["type"], "probe")
        self.assertEqual(result["state"][0], events[0])


if __name__ == "__main__":
    unittest.main()
