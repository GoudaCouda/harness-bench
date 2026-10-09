import unittest
from src.rerun_planner import plan_rerun
class RerunTests(unittest.TestCase):
 def test_skipped_dependent_follows_failure(self):
  w=[{"job_id":"a","needs":[],"shards":["one"],"consumes":[],"side_effect":False},{"job_id":"b","needs":["a"],"shards":["one"],"consumes":["a"],"side_effect":False}];r=[{"job_id":"a","shard":"one","status":"failure","attempt":1,"artifact_fresh":False},{"job_id":"b","shard":"one","status":"skipped","attempt":1,"artifact_fresh":False}];p=plan_rerun(w,r,{"rerun_cancelled":True,"allow_side_effects":False});self.assertEqual([x["action"] for x in p["plan"]],["rerun","rerun"])
if __name__=="__main__":unittest.main()
