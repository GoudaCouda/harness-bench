from __future__ import annotations

import unittest


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover("tests", pattern="test_public_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
