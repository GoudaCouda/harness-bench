import unittest

from src.confirm_policy import decide_run


class ConfirmationPolicyTests(unittest.TestCase):
    def test_yes_flag_does_not_require_input(self):
        config = {"mode": "apply", "target_count": 2, "yes": True, "no_input": True, "stdin_is_tty": False}
        self.assertEqual(decide_run(config, "")["confirmation"], "flag")

    def test_tty_is_owned_by_caller(self):
        config = {"mode": "apply", "target_count": 2, "yes": False, "no_input": False, "stdin_is_tty": True}
        result = decide_run(config, "yes")
        self.assertEqual((result["action"], result["stdin_consumed"]), ("prompt", False))


if __name__ == "__main__":
    unittest.main()
