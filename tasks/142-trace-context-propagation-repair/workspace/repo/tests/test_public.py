import unittest
from src.trace_context import propagate_contexts

POLICY=dict(vendor_key="acme",sensitive_baggage_keys=["user.id"],max_tracestate_entries=8,max_baggage_entries=8)

def request(**updates):
    row=dict(request_id="public-q",traceparent=["00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-00"],tracestate=[],baggage=[],participate=False,boundary="internal",local_parent_id="1111111111111111",fallback_trace_id="22222222222222222222222222222222",vendor_value="public-v",sampled=False)
    row.update(updates); return row

class TraceTests(unittest.TestCase):
    def test_invalid_tracestate_does_not_restart_trace(self):
        result=propagate_contexts([request(tracestate=["bad==x"])],POLICY)["decisions"][0]
        self.assertEqual(result["disposition"],"forwarded"); self.assertIsNone(result["tracestate"])

    def test_external_baggage_filter(self):
        result=propagate_contexts([request(boundary="external",baggage=["user.id=a,tenant=b"])],POLICY)["decisions"][0]
        self.assertEqual(result["baggage"],"tenant=b")

if __name__=="__main__": unittest.main()
