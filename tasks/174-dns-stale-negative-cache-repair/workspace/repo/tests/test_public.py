import unittest

from src.dns_cache import plan_dns_responses

POLICY = {"serve_stale":True,"allow_stale_negative":True,"refused_preempts_stale":True,"stale_answer_ttl":30,"client_response_ms":1000,"max_negative_ttl":3600}


def query(**updates):
    value = {"query_id":"public","qname":"www.example.","qtype":"A","recursion_desired":True,"cache_kind":"positive","cache_age_sec":61,"cache_ttl_sec":60,"stale_retention_sec":300,"cache_dnssec":"secure","refresh_kind":"failure","refresh_authoritative":False,"refresh_elapsed_ms":1000,"refresh_ttl_sec":None,"soa_ttl_sec":None,"soa_minimum_sec":None,"refresh_rcode":"SERVFAIL"}
    value.update(updates)
    return value


class DNSCacheTests(unittest.TestCase):
    def test_failed_refresh_can_serve_bounded_stale(self):
        row = plan_dns_responses([query()], POLICY)["decisions"][0]
        self.assertEqual((row["action"], row["ttl"], row["ede_code"]), ("serve_stale", 30, 3))

    def test_expiry_boundary_is_not_fresh(self):
        row = plan_dns_responses([query(cache_age_sec=60)], POLICY)["decisions"][0]
        self.assertEqual(row["action"], "serve_stale")

    def test_negative_refresh_uses_soa_minimum(self):
        row = plan_dns_responses([query(cache_kind=None,cache_age_sec=None,cache_ttl_sec=None,stale_retention_sec=None,cache_dnssec=None,refresh_kind="nxdomain",refresh_authoritative=True,refresh_elapsed_ms=100,soa_ttl_sec=7200,soa_minimum_sec=1800,refresh_rcode="NXDOMAIN")], POLICY)["decisions"][0]
        self.assertEqual(row["cache_negative_ttl"], 1800)


if __name__ == "__main__":
    unittest.main()
