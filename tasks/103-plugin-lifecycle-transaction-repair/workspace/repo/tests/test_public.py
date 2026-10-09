import unittest
from src.plugin_lifecycle import reconcile_plugins


class LifecycleTests(unittest.TestCase):
    def test_enable_dependency_order_and_registry(self):
        catalog=[{"name":"base","depends":[],"hooks":["h0"]},{"name":"leaf","depends":["base"],"hooks":["h1"]}]
        state=dict(generation=0,active=[],registrations=[])
        result=reconcile_plugins(state,catalog,{"enable":["leaf"],"disable":[]},{"activate":[],"deactivate":[]})
        self.assertEqual(result["journal"]["activation_order"],["base","leaf"])
        self.assertEqual(result["state"]["active"],["base","leaf"])

    def test_activation_failure_rolls_back_exact_state(self):
        catalog=[{"name":"a","depends":[],"hooks":["ha"]},{"name":"b","depends":["a"],"hooks":["hb"]}]
        state=dict(generation=2,active=[],registrations=[{"plugin":"stale","hook":"x"}])
        result=reconcile_plugins(state,catalog,{"enable":["b"],"disable":[]},{"activate":["b"],"deactivate":[]})
        self.assertEqual(result["state"],state)
        self.assertEqual(result["journal"]["rollback_order"],["a"])


if __name__ == "__main__":
    unittest.main()
