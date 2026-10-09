import unittest

from src.cache_revalidation import evaluate_cache_request


class CacheDecisionTests(unittest.TestCase):
    def test_weak_etag_matches_strong_tag(self):
        request = {"method":"GET","uri":"/x","headers":{"if-none-match":"W/\"a\""}}
        stored = {"uri":"/x","request_headers":{},"response_headers":{"etag":"\"a\"","last-modified":None,"vary":None}}
        self.assertEqual(evaluate_cache_request(request, stored)["status"], 304)

    def test_vary_mismatch_prevents_304(self):
        request = {"method":"GET","uri":"/x","headers":{"accept-language":"fr","if-none-match":"\"a\""}}
        stored = {"uri":"/x","request_headers":{"accept-language":"en"},"response_headers":{"etag":"\"a\"","last-modified":None,"vary":"Accept-Language"}}
        self.assertEqual(evaluate_cache_request(request, stored)["reason"], "vary_miss")


if __name__ == "__main__":
    unittest.main()
