import unittest
from cron import next_fire


class CronTests(unittest.TestCase):
    def test_star_is_the_next_minute(self):
        self.assertEqual(
            next_fire("* * * * *", {"month": 1, "day": 1, "hour": 0, "minute": 0}),
            {"month": 1, "day": 1, "hour": 0, "minute": 1},
        )

    def test_bad_expr_raises(self):
        with self.assertRaises(ValueError):
            next_fire("0 0", {"month": 1, "day": 1, "hour": 0, "minute": 0})


if __name__ == "__main__":
    unittest.main()
