import unittest
from src.recurrence_engine import expand_schedules


class RecurrenceTests(unittest.TestCase):
    def test_gap_shift_and_stable_id(self):
        schedule={"schedule_id":"job","start_local":"2026-03-08T02:30","frequency":"daily","interval":1,"count":1,"duration_minutes":30,"timezone_history":[{"effective_date":"2026-01-01","timezone":"America/New_York"}],"gap_policy":"shift_forward","fold_policy":"earlier"}
        result=expand_schedules([schedule],{"start":"2026-03-01T00:00:00Z","end":"2026-04-01T00:00:00Z"},[])
        self.assertEqual(result["occurrences"][0]["occurrence_id"],"job#0001")
        self.assertEqual(result["occurrences"][0]["scheduled_local"],"2026-03-08T03:00")
        self.assertEqual(result["occurrences"][0]["resolution"],"gap_shift_forward")

    def test_monthly_clamp_is_not_iterative(self):
        schedule={"schedule_id":"m","start_local":"2024-01-31T10:00","frequency":"monthly","interval":1,"count":3,"duration_minutes":1,"timezone_history":[{"effective_date":"2024-01-01","timezone":"UTC"}],"gap_policy":"skip","fold_policy":"earlier"}
        result=expand_schedules([schedule],{"start":"2024-01-01T00:00:00Z","end":"2024-04-01T00:00:00Z"},[])
        self.assertEqual([row["nominal_local"] for row in result["occurrences"]],["2024-01-31T10:00","2024-02-29T10:00","2024-03-31T10:00"])


if __name__=="__main__": unittest.main()
