import unittest

from src.goaway_recovery import plan_goaway_retries


GOAWAY = {"connection_id": "c1", "last_stream_id": 5, "error_code": "NO_ERROR"}
POLICY = {
    "max_retries": 4,
    "idempotent_methods": ["GET", "HEAD"],
    "require_idempotency_key_for_unsafe": True,
    "retryable_errors": ["NO_ERROR"],
}


def request(**changes):
    value = {
        "request_id": "r1",
        "method": "POST",
        "stream_id": 7,
        "response_state": "none",
        "reset_code": None,
        "body_replayable": True,
        "idempotency_key": None,
        "attempt": 0,
    }
    value.update(changes)
    return value


class GoawayTests(unittest.TestCase):
    def test_stream_above_boundary_retries_even_for_post(self):
        row = plan_goaway_retries([request()], GOAWAY, POLICY)["decisions"][0]
        self.assertEqual(
            (row["status"], row["reason"]), ("retry", "goaway_unprocessed")
        )

    def test_ambiguous_post_without_key_blocks(self):
        row = plan_goaway_retries([request(stream_id=3)], GOAWAY, POLICY)["decisions"][
            0
        ]
        self.assertEqual(
            (row["status"], row["reason"]), ("blocked", "ambiguous_non_idempotent")
        )


if __name__ == "__main__":
    unittest.main()
