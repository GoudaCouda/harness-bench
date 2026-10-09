import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.migration_recovery import plan_migration_recovery  # noqa: E402


MIGRATION = {
    "id": "m2",
    "from_version": 1,
    "to_version": 2,
    "checksum": "a" * 64,
    "statements": ["CREATE TABLE widgets(id INTEGER PRIMARY KEY)"],
}
STATE = {
    "user_version": 1,
    "ledger": [
        {
            "id": "m1",
            "from_version": 0,
            "to_version": 1,
            "checksum": "b" * 64,
        }
    ],
}


class RealSQLitePlanTests(unittest.TestCase):
    def test_clean_plan_executes_as_one_real_transaction(self):
        plan = plan_migration_recovery(
            MIGRATION,
            STATE,
            {"phase": "clean", "transaction_active": False},
        )
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "fixture.db"
            connection = sqlite3.connect(database, isolation_level=None)
            try:
                connection.execute(
                    "CREATE TABLE migration_ledger("
                    "id TEXT PRIMARY KEY, checksum TEXT NOT NULL, "
                    "from_version INTEGER NOT NULL, to_version INTEGER NOT NULL)"
                )
                connection.execute("PRAGMA user_version = 1")
                for action in plan["actions"]:
                    if action == "begin_immediate":
                        connection.execute("BEGIN IMMEDIATE")
                    elif action.startswith("statement:"):
                        index = int(action.split(":", 1)[1])
                        connection.execute(MIGRATION["statements"][index])
                    elif action.startswith("ledger_insert:"):
                        connection.execute(
                            "INSERT INTO migration_ledger VALUES (?, ?, ?, ?)",
                            (
                                MIGRATION["id"],
                                MIGRATION["checksum"],
                                MIGRATION["from_version"],
                                MIGRATION["to_version"],
                            ),
                        )
                    elif action.startswith("set_user_version:"):
                        version = int(action.split(":", 1)[1])
                        connection.execute(f"PRAGMA user_version = {version}")
                    elif action == "commit":
                        connection.execute("COMMIT")
                    else:
                        self.fail(f"unexpected clean-plan action: {action}")

                version = connection.execute("PRAGMA user_version").fetchone()[0]
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertEqual(version, 2)
                self.assertIn("widgets", tables)
                self.assertEqual(
                    connection.execute(
                        "SELECT id, checksum FROM migration_ledger WHERE id = 'm2'"
                    ).fetchone(),
                    ("m2", "a" * 64),
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
