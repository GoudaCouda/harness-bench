import unittest
from config_resolver import resolve_config


class ResolverTests(unittest.TestCase):
    def test_cli_wins_and_sources_are_reported(self):
        schema = {"port": {"type": "int", "min": 1, "max": 9, "nullable": False, "sensitive": False, "env": "EDGE_PORT"}}
        self.assertEqual(resolve_config({"port": 1}, {"port": 2}, {"EDGE_PORT": "3"}, {"port": 4}, schema), {"values": {"port": 4}, "sources": {"port": "cli"}})

    def test_invalid_highest_value_does_not_fall_back(self):
        schema = {"enabled": {"type": "bool", "nullable": False, "sensitive": False, "env": "EDGE_ENABLED"}}
        with self.assertRaises(ValueError):
            resolve_config({"enabled": False}, {}, {"EDGE_ENABLED": "yes"}, {}, schema)


if __name__ == "__main__":
    unittest.main()
