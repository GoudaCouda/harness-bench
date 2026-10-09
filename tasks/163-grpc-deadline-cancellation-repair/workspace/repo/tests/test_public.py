import unittest

from src.rpc_budget import plan_rpc_budget


POLICY = {
    "max_attempts": 4,
    "per_try_timeout_ms": 900,
    "reserve_ms": 40,
    "base_backoff_ms": 80,
    "max_backoff_ms": 320,
    "retryable_statuses": ["UNAVAILABLE"],
}


def call(**changes):
    value = {
        "call_id": "public",
        "method": "/Public/Get",
        "status": "UNAVAILABLE",
        "attempt": 1,
        "incoming_timeout_ms": 1500,
        "elapsed_ms": 200,
        "response_headers_received": False,
        "caller_cancelled": False,
        "operation_scope": "single_call",
        "idempotent": True,
        "active_child_rpcs": 0,
    }
    value.update(changes)
    return value


class RpcBudgetTests(unittest.TestCase):
    def test_retry_deducts_backoff_and_caps_timeout(self):
        row = plan_rpc_budget([call()], POLICY)["decisions"][0]
        self.assertEqual((row["delay_ms"], row["timeout_ms"]), (80, 900))

    def test_cancellation_cleans_children(self):
        row = plan_rpc_budget(
            [call(caller_cancelled=True, active_child_rpcs=3)], POLICY
        )["decisions"][0]
        self.assertEqual((row["status"], row["cancel_child_rpcs"]), ("stopped", 3))


if __name__ == "__main__":
    unittest.main()
