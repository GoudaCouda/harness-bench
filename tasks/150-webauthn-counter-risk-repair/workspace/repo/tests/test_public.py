import unittest
from src.assertion_risk import assess_assertions

POLICY={"allowed_origins":["https://admin.example.test","https://login.example.test"],"rp_id":"example.test","require_user_verification":True,"device_counter_action":"reject","synced_counter_action":"flag"}

def credential(eligible=False,count=4):
    return {"credential_id":"cred-one","user_id":"user-one","sign_count":count,"backup_eligible":eligible,"backup_state":eligible,"status":"active","risk":"normal","last_assertion":None}

def assertion(assertion_id,count,eligible=False):
    return {"assertion_id":assertion_id,"credential_id":"cred-one","user_id":"user-one","sign_count":count,"backup_eligible":eligible,"backup_state":eligible,"signature_valid":True,"user_verified":True,"origin":"https://login.example.test","rp_id":"example.test"}

class AssertionTests(unittest.TestCase):
    def test_device_regression_rejects_without_counter_overwrite(self):
        result=assess_assertions([credential()], [assertion("auth-one",3)], POLICY)
        self.assertEqual(result["decisions"][0]["decision"],"rejected")
        self.assertEqual(result["credentials"][0]["sign_count"],4)

    def test_synced_equal_counter_flags_but_accepts(self):
        result=assess_assertions([credential(True)], [assertion("auth-two",4,True)], POLICY)
        self.assertEqual(result["decisions"][0]["decision"],"accepted")
        self.assertEqual(result["credentials"][0]["risk"],"elevated")

if __name__=="__main__": unittest.main()
