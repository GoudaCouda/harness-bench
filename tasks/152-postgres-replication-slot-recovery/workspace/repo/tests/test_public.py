import unittest
from src.slot_recovery import plan_slot_recovery

OBS={"primary_wal_lsn":110,"oldest_available_lsn":20,"standby_synced_slots":[],"maintenance_window":True}; POLICY={"max_retained_bytes":55,"require_synced_failover":False}
def slot(restart=60,active=False):return {"slot_name":"slot-a","database":"db","plugin":"pgoutput","active":active,"restart_lsn":restart,"confirmed_flush_lsn":80,"wal_status":"reserved","invalidation_reason":None,"failover":False,"synced":False}
def consumer(state="stopped",can=True):return {"consumer_id":"worker-a","slot_name":"slot-a","database":"db","plugin":"pgoutput","last_applied_lsn":75,"can_resnapshot":can,"state":state}
class RecoveryTests(unittest.TestCase):
    def test_healthy_stopped_consumer_resumes(self):self.assertEqual(plan_slot_recovery([slot()],[consumer()],OBS,POLICY)["plans"][0]["action"],"resume")
    def test_active_over_cap_slot_blocks(self):self.assertEqual(plan_slot_recovery([slot(40,True)],[consumer("running")],OBS,POLICY)["plans"][0]["reason"],"slot_active")
if __name__=="__main__":unittest.main()
