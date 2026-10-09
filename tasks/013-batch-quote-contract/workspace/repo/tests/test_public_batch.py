import json
import unittest
from pathlib import Path

from quote_service.batch import build_batch_quotes


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
COUPONS = json.loads((ROOT / "coupons.json").read_text(encoding="utf-8"))


class BatchQuotePublicTests(unittest.TestCase):
    def test_monthly_quote(self):
        actual = build_batch_quotes(
            [{"request_id": "Q-1", "plan": "starter", "seats": 3, "term_months": 1}],
            CATALOG,
            COUPONS,
            "2026-08-26",
        )
        self.assertEqual(actual, [{
            "request_id": "Q-1", "status": "quoted", "subtotal_cents": 3600,
            "term_discount_cents": 0, "coupon_discount_cents": 0,
            "total_cents": 3600,
        }])

    def test_annual_then_coupon_discount(self):
        actual = build_batch_quotes(
            [{"request_id": "Q-2", "plan": "team", "seats": 10, "term_months": 12, "coupon": "TEAM5"}],
            CATALOG,
            COUPONS,
            "2026-09-30",
        )[0]
        self.assertEqual(actual["subtotal_cents"], 330000)
        self.assertEqual(actual["term_discount_cents"], 49500)
        self.assertEqual(actual["coupon_discount_cents"], 14025)
        self.assertEqual(actual["total_cents"], 266475)

    def test_invalid_bool_seats_does_not_stop_other_items(self):
        actual = build_batch_quotes([
            {"request_id": "BAD", "plan": "starter", "seats": True, "term_months": 1},
            {"request_id": "OK", "plan": "starter", "seats": 2, "term_months": 1},
        ], CATALOG, COUPONS, "2026-08-26")
        self.assertEqual(actual[0], {"request_id": "BAD", "status": "rejected", "code": "invalid_seats"})
        self.assertEqual(actual[1]["total_cents"], 2400)


if __name__ == "__main__":
    unittest.main()
