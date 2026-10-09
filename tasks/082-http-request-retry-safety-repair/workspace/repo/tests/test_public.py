import unittest

from src.retry_planner import plan_http_retry


def request(method="POST", key=None, safe=False):
    return {"method":method,"operation_id":"op-1","body_sha256":"a" * 64,"idempotency_key":key,"key_replay_safe":safe,"max_attempts":4,"base_delay_ms":100,"max_delay_ms":10000}


class RetryPlannerTests(unittest.TestCase):
    def test_unsent_post_can_retry(self):
        observation={"outcome":"connect_failure","status":None,"retry_after_ms":None,"application_state":None,"bytes_sent":0}
        result=plan_http_retry(request(),1,observation)
        self.assertEqual((result["decision"],result["safety_basis"]),("retry","not_sent"))

    def test_lost_post_without_contract_requires_probe(self):
        observation={"outcome":"response_lost","status":None,"retry_after_ms":None,"application_state":None,"bytes_sent":120}
        result=plan_http_retry(request(),1,observation)
        self.assertEqual(result["decision"],"probe")


if __name__ == "__main__":
    unittest.main()
