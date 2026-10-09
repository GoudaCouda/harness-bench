import unittest

from src.bundle_policy import verify_bundles


POLICY = {
    "require_tlog": True,
    "require_timestamp": False,
    "min_tlog_operators": 1,
    "accepted_payload_types": ["application/test"],
}
ARTIFACT = {
    "artifact_id": "public",
    "digest": "sha256:abc123",
    "identity": "workflow:test",
    "issuer": "issuer:test",
    "payload_type": "application/test",
}
ROOT = {
    "root_id": "root",
    "valid_from": 100,
    "valid_until": 300,
    "ca_operator": "ca",
    "tlog_operators": ["log"],
    "timestamp_operators": [],
}
BUNDLE = {
    "artifact_id": "public",
    "digest": "sha256:abc123",
    "payload_type": "application/test",
    "signature_verified": True,
    "chain_verified": True,
    "identity": "workflow:test",
    "issuer": "issuer:test",
    "root_id": "root",
    "cert_not_before": 150,
    "cert_not_after": 200,
    "tlog_entries": [{"operator": "log", "verified": True, "time": 175}],
    "timestamps": [],
}


class BundleTests(unittest.TestCase):
    def test_trusted_signing_time_verifies(self):
        row = verify_bundles([ARTIFACT], [BUNDLE], [ROOT], POLICY)["decisions"][0]
        self.assertEqual((row["status"], row["signing_time"]), ("verified", 175))

    def test_wrong_identity_blocks(self):
        bundle = dict(BUNDLE)
        bundle["identity"] = "workflow:other"
        row = verify_bundles([ARTIFACT], [bundle], [ROOT], POLICY)["decisions"][0]
        self.assertEqual(row["reason"], "identity")


if __name__ == "__main__":
    unittest.main()
