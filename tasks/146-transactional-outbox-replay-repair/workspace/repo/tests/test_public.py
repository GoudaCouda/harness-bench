import unittest
from src.outbox_recovery import recover_outbox

H="a"*64
POLICY={"now":100,"worker":"relay-a","lease_seconds":30,"max_attempts":3}

def event(**updates):
    row={"event_id":"e1","aggregate_id":"order-1","sequence":1,"payload_hash":H,"status":"pending","attempts":0,"lease_owner":None,"lease_until":None,"last_error":None}
    row.update(updates); return row

class RecoveryTests(unittest.TestCase):
    def test_unknown_is_probed_not_republished(self):
        rows=[event(status="leased",attempts=1,lease_owner="relay-z",lease_until=80)]
        receipts=[{"event_id":"e1","attempt":1,"outcome":"unknown","payload_hash":H,"observed_at":90}]
        result=recover_outbox(rows,receipts,POLICY)
        self.assertEqual(result["actions"][0]["type"],"probe")
        self.assertEqual(result["state"][0],rows[0])

    def test_late_ack_unblocks_next_sequence(self):
        rows=[event(status="leased",attempts=2,lease_owner="relay-z",lease_until=80),event(event_id="e2",sequence=2)]
        receipts=[{"event_id":"e1","attempt":1,"outcome":"acked","payload_hash":H,"observed_at":95}]
        result=recover_outbox(rows,receipts,POLICY)
        self.assertEqual(result["state"][0]["status"],"sent")
        self.assertEqual(result["actions"][0]["event_id"],"e2")

if __name__=="__main__": unittest.main()
