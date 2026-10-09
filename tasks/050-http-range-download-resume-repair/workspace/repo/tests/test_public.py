import unittest

from src.range_resume import reconcile_resume


class ResumeTests(unittest.TestCase):
    def test_full_response_replaces_partial(self):
        manifest = {"size": 3, "etag": "\"v1\"", "sha256": "a" * 64}
        checkpoint = {"temp_exists": True, "offset": 1, "etag": "\"v1\"", "prefix_sha256": "b" * 64}
        response = {"status": 200, "etag": "\"v1\"", "body_length": 3, "body_sha256": "a" * 64, "content_range": None, "assembled_sha256": None}
        self.assertEqual(reconcile_resume(manifest, checkpoint, response), {"action": "complete", "reason": "full_verified", "offset": 3})

    def test_mismatched_validator_restarts(self):
        manifest = {"size": 3, "etag": "\"v2\"", "sha256": "a" * 64}
        checkpoint = {"temp_exists": True, "offset": 1, "etag": "\"v1\"", "prefix_sha256": "b" * 64}
        response = {"status": 206, "etag": "\"v2\"", "body_length": 2, "body_sha256": "c" * 64, "content_range": "bytes 1-2/3", "assembled_sha256": "a" * 64}
        self.assertEqual(reconcile_resume(manifest, checkpoint, response)["action"], "restart")


if __name__ == "__main__":
    unittest.main()
