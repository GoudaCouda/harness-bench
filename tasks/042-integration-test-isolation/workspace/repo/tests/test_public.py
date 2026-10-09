import unittest
from src.isolation_runner import run_isolated_suite

class IsolationTests(unittest.TestCase):
    def test_each_test_gets_fresh_nested_fixture(self):
        tests=[{"test_id":"a","operations":[{"op":"append","key":"items","value":1}]},{"test_id":"b","operations":[{"op":"assert_equal","key":"items","value":[]}]}]
        result=run_isolated_suite({"items":[]},tests,1,[],1)
        self.assertEqual([x["status"] for x in result],["passed","passed"])
    def test_expired_quarantine_does_not_hide_failure(self):
        tests=[{"test_id":"a","operations":[{"op":"assert_equal","key":"x","value":2}]}]
        result=run_isolated_suite({"x":1},tests,1,[{"test_id":"a","expires_day":4}],5)
        self.assertEqual(result[0]["status"],"failed")

if __name__=="__main__":unittest.main()
