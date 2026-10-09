import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "confirm_cli.py"


class RealCliTests(unittest.TestCase):
    def test_no_input_blocks_without_consuming_pipe(self):
        result = subprocess.run(
            [sys.executable, str(CLI), "--target-count", "2", "--no-input"],
            input="yes\n",
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["confirmation"], "no_input")
        self.assertFalse(payload["stdin_consumed"])

    @unittest.skipUnless(os.name == "posix", "PTY behavior is a Linux fixture")
    def test_tty_returns_prompt_without_reading_confirmation(self):
        import pty

        master, slave = pty.openpty()
        try:
            result = subprocess.run(
                [sys.executable, str(CLI), "--target-count", "2"],
                stdin=slave,
                text=True,
                capture_output=True,
                timeout=5,
            )
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "prompt")
        self.assertFalse(payload["stdin_consumed"])


if __name__ == "__main__":
    unittest.main()
