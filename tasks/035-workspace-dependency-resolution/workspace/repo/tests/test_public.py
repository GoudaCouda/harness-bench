import unittest

from src.resolver import resolve_workspace


class ResolverTests(unittest.TestCase):
    def test_preserves_valid_lock_instead_of_upgrading(self):
        manifest = {"dependencies": {"core": "^1.0.0"}, "optionalDependencies": {}}
        registry = {"core": [{"version": "1.1.0"}, {"version": "1.2.0"}]}
        result = resolve_workspace(manifest, registry, {"core": "1.1.0"}, {"os": "linux", "cpu": "x64"})
        self.assertEqual(result["packages"], [{"name": "core", "version": "1.1.0", "source": "preserved"}])

    def test_skips_incompatible_optional_root(self):
        manifest = {"dependencies": {}, "optionalDependencies": {"watch": "^2.0.0"}}
        registry = {"watch": [{"version": "2.0.0", "os": ["darwin"]}]}
        result = resolve_workspace(manifest, registry, {}, {"os": "linux", "cpu": "x64"})
        self.assertEqual(result, {"packages": [], "skipped_optional": ["watch"]})


if __name__ == "__main__":
    unittest.main()
