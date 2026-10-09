from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nami_service.db import initialize_database
from nami_service.users import authenticate, register_user


class PublicRegistrationContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "service.db"
        initialize_database(self.database)

    def test_existing_authentication_still_works(self) -> None:
        self.assertTrue(authenticate(self.database, "alice", "ExistingPass9"))

    def test_register_returns_public_fields(self) -> None:
        result = register_user(
            self.database,
            "Nova_User",
            "NOVA@Example.Test",
            "StrongPass9",
        )
        self.assertEqual(
            set(result), {"id", "username", "email", "created_at"}
        )
        self.assertEqual(result["username"], "Nova_User")
        self.assertEqual(result["email"], "nova@example.test")


if __name__ == "__main__":
    unittest.main()
