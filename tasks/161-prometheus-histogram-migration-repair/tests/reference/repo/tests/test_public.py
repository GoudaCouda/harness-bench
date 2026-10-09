import unittest

from src.histogram_migration import plan_histogram_migration


POLICY = {
    "max_parity_error_pct": 1.5,
    "max_counter_resets": 1,
    "required_stable_windows": 3,
    "required_quiet_windows": 4,
    "min_native_schema": -3,
    "max_native_schema": 7,
    "rate_window": "15m",
}


def metric(**changes):
    value = {
        "metric_id": "latency",
        "metric_name": "http_request_duration_seconds",
        "query_kind": "quantile",
        "quantile": 0.95,
        "lower": None,
        "upper": None,
        "total_targets": 4,
        "native_targets": 2,
        "native_schema": 1,
        "parity_error_pct": 0.4,
        "counter_resets": 0,
        "current_query_mode": "classic",
        "consumer_native_ready": True,
        "stable_windows": 0,
        "classic_emit_enabled": True,
        "classic_quiet_windows": 0,
    }
    value.update(changes)
    return value


class HistogramTests(unittest.TestCase):
    def test_partial_rollout_keeps_classic_query(self):
        row = plan_histogram_migration([metric()], POLICY)["decisions"][0]
        self.assertEqual(
            (row["action"], row["reason"]), ("roll_out_native", "coverage_incomplete")
        )
        self.assertIn("_bucket", row["query"])

    def test_full_stable_rollout_switches_native(self):
        row = plan_histogram_migration(
            [metric(native_targets=4, stable_windows=3)], POLICY
        )["decisions"][0]
        self.assertEqual(
            (row["action"], row["reason"]),
            ("switch_query_to_native", "native_cutover_ready"),
        )


if __name__ == "__main__":
    unittest.main()
