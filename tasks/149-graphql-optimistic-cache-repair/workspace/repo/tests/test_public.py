import unittest
from src.optimistic_cache import reconcile_cache

POLICY=dict(allowed_typenames=["Item"],max_active_layers=3)

class CacheTests(unittest.TestCase):
    def test_error_rolls_back_only_named_layer(self):
        base={"Item:1":{"value":"base"}}
        events=[
          {"kind":"optimistic","mutation_id":"public-a","mode":"apply","writes":[{"id":"Item:1","fields":{"value":"a"}}],"aliases":{}},
          {"kind":"optimistic","mutation_id":"public-b","mode":"apply","writes":[{"id":"Item:1","fields":{"value":"b"}}],"aliases":{}},
          {"kind":"error","mutation_id":"public-a","mode":"resolve","writes":[],"aliases":{}},
        ]
        result=reconcile_cache(base,events,POLICY)
        self.assertEqual(result["base"]["Item:1"]["value"],"base")
        self.assertEqual(result["visible"]["Item:1"]["value"],"b")

    def test_null_is_an_explicit_write(self):
        base={"Item:1":{"note":"old","value":1}}
        events=[{"kind":"optimistic","mutation_id":"public-c","mode":"apply","writes":[{"id":"Item:1","fields":{"note":None}}],"aliases":{}}]
        self.assertIsNone(reconcile_cache(base,events,POLICY)["visible"]["Item:1"]["note"])

if __name__=="__main__": unittest.main()
