import unittest
from src.field_ownership import apply_intents

POLICY=dict(allowed_paths=["/spec/image","/spec/replicas"],protected_prefixes=[])

class FieldTests(unittest.TestCase):
    def test_conflict_is_atomic(self):
        live={"/spec/image":"v1","/spec/replicas":2}; owners=[{"path":"/spec/image","managers":["deploy"]},{"path":"/spec/replicas","managers":["hpa"]}]
        intents=[{"request_id":"public-1","manager":"deploy","force":False,"fields":{"/spec/image":"v2","/spec/replicas":3}}]
        result=apply_intents(live,owners,{},intents,POLICY)
        self.assertEqual(result["decisions"][0]["status"],"conflict")
        self.assertEqual(result["object"],live); self.assertEqual(result["ownership"],owners)

    def test_same_value_shares_ownership(self):
        live={"/spec/image":"v1"}; owners=[{"path":"/spec/image","managers":["deploy"]}]
        intents=[{"request_id":"public-2","manager":"observer","force":False,"fields":{"/spec/image":"v1"}}]
        result=apply_intents(live,owners,{},intents,dict(allowed_paths=["/spec/image"],protected_prefixes=[]))
        self.assertEqual(result["ownership"][0]["managers"],["deploy","observer"])

if __name__=="__main__": unittest.main()
