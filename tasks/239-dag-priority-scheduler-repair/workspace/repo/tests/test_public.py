import unittest
from schedule import schedule_jobs


class ScheduleTests(unittest.TestCase):
    def test_priority_beats_input_order(self):
        jobs = [
            {"job_id": "paint", "deps": ["prep"], "priority": 1},
            {"job_id": "prep", "deps": [], "priority": 4},
            {"job_id": "inspect", "deps": [], "priority": 4},
        ]
        self.assertEqual(
            schedule_jobs(jobs)["order"],
            ["inspect", "prep", "paint"],
        )

    def test_cycle_is_rejected(self):
        jobs = [
            {"job_id": "a", "deps": ["b"], "priority": 1},
            {"job_id": "b", "deps": ["a"], "priority": 1},
        ]
        with self.assertRaises(ValueError):
            schedule_jobs(jobs)


if __name__ == "__main__":
    unittest.main()
