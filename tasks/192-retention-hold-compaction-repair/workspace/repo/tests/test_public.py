import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.solution import plan_retention_hold_compaction
class PublicTest(unittest.TestCase):
 def test_visible_shape(self):
  data=json.loads((ROOT/'input.json').read_text()); out=plan_retention_hold_compaction(*(data[n] for n in ('requests', 'policy'))); self.assertIsInstance(out,dict); self.assertTrue(out)
 def test_inputs_unchanged(self):
  data=json.loads((ROOT/'input.json').read_text()); before=json.dumps(data,sort_keys=True); plan_retention_hold_compaction(*(data[n] for n in ('requests', 'policy'))); self.assertEqual(before,json.dumps(data,sort_keys=True))
if __name__=='__main__': unittest.main()
