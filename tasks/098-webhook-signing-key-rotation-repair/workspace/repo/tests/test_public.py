import hashlib
import hmac
import unittest

from src.webhook_verifier import verify_batch


def signature(secret, timestamp, body):
    return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


class VerifierTests(unittest.TestCase):
    def test_overlap_accepts_old_and_new_signatures(self):
        body = '{"x":1}'
        old = signature("old", 20, body)
        new = signature("new", 20, body)
        deliveries = [{"delivery_id":"d","endpoint":"/e","received_at":20,"raw_body":body,"signature_header":f"t=20,v1={old},v1={new}"}]
        keys = [{"key_id":"old","endpoint":"/e","secret":"old","not_before":0,"not_after":30},{"key_id":"new","endpoint":"/e","secret":"new","not_before":20,"not_after":40}]
        result = verify_batch(deliveries, keys, {"algorithm":"hmac-sha256","signature_version":"v1","tolerance_seconds":5}, {"seen_delivery_ids":[]})
        self.assertEqual(result["decisions"][0]["matched_key_ids"], ["new", "old"])

    def test_authenticated_duplicate_does_not_change_checkpoint(self):
        body = "raw body"
        sig = signature("s", 10, body)
        delivery = {"delivery_id":"seen","endpoint":"/e","received_at":10,"raw_body":body,"signature_header":f"t=10,v1={sig}"}
        key = {"key_id":"k","endpoint":"/e","secret":"s","not_before":0,"not_after":20}
        result = verify_batch([delivery], [key], {"algorithm":"hmac-sha256","signature_version":"v1","tolerance_seconds":0}, {"seen_delivery_ids":["seen"]})
        self.assertEqual(result["decisions"][0]["status"], "duplicate")
        self.assertEqual(result["checkpoint"], {"seen_delivery_ids":["seen"]})


if __name__ == "__main__":
    unittest.main()
