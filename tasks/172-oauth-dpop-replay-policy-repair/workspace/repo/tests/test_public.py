import unittest

from src.dpop_policy import verify_dpop


POLICY = {"allowed_algs":["ES256"],"max_age_sec":60,"future_skew_sec":5,"max_jti_chars":32,"require_nonce":True}


def request(request_id="a"):
    return {"request_id":request_id,"method":"GET","htu":"https://api.test/item","now":100,"token_jkt":"key","access_token_hash":"hash","required_nonce":"nonce"}


def proof(request_id="a", **updates):
    value = {"request_id":request_id,"typ":"dpop+jwt","alg":"ES256","public_jwk":True,"signature_verified":True,"htm":"GET","htu":"https://api.test/item","iat":95,"jti":"proof","jkt":"key","ath":"hash","nonce":"nonce"}
    value.update(updates)
    return value


class DPoPTests(unittest.TestCase):
    def test_bound_proof_is_cached(self):
        result = verify_dpop([request()], [proof()], [], POLICY)
        self.assertEqual(result["decisions"][0]["status"], "accepted")
        self.assertEqual(result["replay_cache"][0]["expires_at"], 160)

    def test_token_hash_mismatch_rejects_without_cache_insert(self):
        result = verify_dpop([request()], [proof(ath="wrong")], [], POLICY)
        self.assertEqual(result["decisions"][0]["reason"], "token_hash")
        self.assertEqual(result["replay_cache"], [])

    def test_same_batch_jti_replays(self):
        requests = [request("a"), request("b")]
        proofs = [proof("a"), proof("b")]
        result = verify_dpop(requests, proofs, [], POLICY)
        self.assertEqual(result["decisions"][1]["reason"], "replay")


if __name__ == "__main__":
    unittest.main()
