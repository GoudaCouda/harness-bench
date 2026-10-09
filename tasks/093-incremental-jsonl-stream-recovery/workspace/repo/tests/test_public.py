import unittest
from src.stream_consumer import consume_segments


class StreamTests(unittest.TestCase):
    def test_partial_line_is_completed(self):
        checkpoint = {"file_id": "f", "offset": 7, "pending": "{\"id\":1", "last_record_id": 0}
        segment = {"file_id": "f", "start": 7, "data": ",\"payload\":true}\n", "eof": False}
        result = consume_segments(checkpoint, [segment], {"max_pending_chars": 80})
        self.assertEqual(result["records"], [{"id": 1, "payload": True}])
        self.assertEqual(result["checkpoint"]["pending"], "")

    def test_rotation_quarantines_old_fragment_without_content(self):
        checkpoint = {"file_id": "old", "offset": 4, "pending": "bad", "last_record_id": 0}
        segment = {"file_id": "new", "start": 0, "data": "", "eof": True}
        result = consume_segments(checkpoint, [segment], {"max_pending_chars": 20})
        self.assertEqual(result["quarantine"][0]["reason"], "truncated_on_rotation")
        self.assertNotIn("content", result["quarantine"][0])


if __name__ == "__main__":
    unittest.main()
