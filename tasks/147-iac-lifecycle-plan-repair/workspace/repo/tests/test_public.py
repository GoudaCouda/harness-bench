import unittest
from src.lifecycle_plan import build_lifecycle_plan

POLICY=dict(allow_destroy=True,sensitive_keys=[])

def resource(address,attributes,**life):
    lifecycle=dict(create_before_destroy=False,prevent_destroy=False,ignore_changes=[],replace_triggered_by=[],moved_from=None); lifecycle.update(life)
    return {"address":address,"depends_on":[],"attributes":attributes,"immutable":[],"lifecycle":lifecycle}

def state(address,attributes): return {"address":address,"generation":1,"depends_on":[],"attributes":attributes}
def seen(address,attributes): return {"address":address,"exists":True,"attributes":attributes,"unknown":[]}

class LifecycleTests(unittest.TestCase):
    def test_ignored_drift_is_noop(self):
        resources=[resource("cache.main",{"ttl":60},ignore_changes=["ttl"])]
        result=build_lifecycle_plan(resources,[state("cache.main",{"ttl":60})],[seen("cache.main",{"ttl":90})],POLICY)
        self.assertEqual(result["plan"]["resources"][0]["action"],"no-op")
        self.assertEqual(result["plan"]["resources"][0]["after"]["ttl"],90)

    def test_move_preserves_identity(self):
        resources=[resource("app.new",{"image":"v1"},moved_from="app.old")]
        result=build_lifecycle_plan(resources,[state("app.old",{"image":"v1"})],[seen("app.old",{"image":"v1"})],POLICY)
        self.assertEqual(result["plan"]["resources"][0]["action"],"no-op")
        self.assertEqual(result["summary"]["moved_count"],1)

if __name__=="__main__": unittest.main()
