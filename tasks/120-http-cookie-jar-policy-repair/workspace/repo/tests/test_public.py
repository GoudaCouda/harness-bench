import unittest
from src.cookie_jar import reconcile_cookie_jar

class CookieJarTests(unittest.TestCase):
    def test_host_only_and_path_order(self):
        jar=[]
        responses=[{"response_id":"r","scheme":"https","host":"a.example.com","path":"/x/y","received_at":10,"set_cookie":["root=1; Path=/","deep=2; Path=/x"]}]
        requests=[{"request_id":"q","scheme":"https","host":"a.example.com","path":"/x/z","at":11,"http_api":True}]
        result=reconcile_cookie_jar(jar,responses,requests,{"public_suffixes":["com"]})
        self.assertEqual(result["requests"][0]["cookie_header"],"deep=2; root=1")

    def test_max_age_zero_beats_expires(self):
        jar=[dict(name="a",value="1",domain="example.com",path="/",host_only=False,secure=False,http_only=False,expires_at=None,creation_index=0)]
        response={"response_id":"r","scheme":"https","host":"www.example.com","path":"/","received_at":10,"set_cookie":["a=2; Domain=example.com; Path=/; Expires=999; Max-Age=0"]}
        result=reconcile_cookie_jar(jar,[response],[],{"public_suffixes":["com"]})
        self.assertEqual(result["store"],[])

if __name__=="__main__": unittest.main()
