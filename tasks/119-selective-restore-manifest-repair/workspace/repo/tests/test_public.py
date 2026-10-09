import unittest
from src.restore_planner import plan_restore


class RestoreTests(unittest.TestCase):
 def test_tombstone_removes_descendants(self):
  snapshots=[{"snapshot_id":"full","parent_id":None,"complete":True,"entries":[{"path":"/x","operation":"upsert","kind":"directory","checksum":None,"size":0},{"path":"/x/a","operation":"upsert","kind":"file","checksum":"a"*64,"size":1}]},{"snapshot_id":"inc","parent_id":"full","complete":True,"entries":[{"path":"/x","operation":"delete","kind":None,"checksum":None,"size":None}]}]
  req={"snapshot_id":"inc","target_root":"/r","include":[],"exclude":[],"overwrite":"if_changed","dry_run":True,"delete_extraneous":False}
  self.assertEqual(plan_restore(snapshots,[],req)["summary"]["selected"],0)
 def test_prefix_is_segment_aware(self):
  entries=[{"path":"/app/x","operation":"upsert","kind":"file","checksum":"a"*64,"size":1},{"path":"/apple/y","operation":"upsert","kind":"file","checksum":"b"*64,"size":1}]
  snapshots=[{"snapshot_id":"s","parent_id":None,"complete":True,"entries":entries}]
  req={"snapshot_id":"s","target_root":"/r","include":["/app"],"exclude":[],"overwrite":"if_changed","dry_run":True,"delete_extraneous":False}
  self.assertEqual([x["source_path"] for x in plan_restore(snapshots,[],req)["plan"]["actions"]],["/app/x"])
if __name__=="__main__":unittest.main()
