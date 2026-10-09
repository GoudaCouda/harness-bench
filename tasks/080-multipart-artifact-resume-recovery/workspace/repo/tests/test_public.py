import unittest
from src.multipart_resume import plan_multipart_resume


def session(state="in_progress"):
    return {"upload_id":"u1","object_key":"ci/a.bin","state":state,"part_count":2,"object_size":8,"minimum_part_size":5,"checksum_algorithm":"SHA256","checksum_type":"COMPOSITE","full_checksum":"f" * 64}


def local():
    return [{"part_number":1,"size":5,"checksum_sha256":"a" * 64},{"part_number":2,"size":3,"checksum_sha256":"b" * 64}]


class MultipartResumeTests(unittest.TestCase):
    def test_missing_part_is_uploaded_without_completion(self):
        pages=[{"upload_id":"u1","page":1,"is_truncated":False,"next_page":None,"parts":[{"part_number":1,"size":5,"checksum_sha256":"a" * 64,"etag":"e1"}]}]
        result=plan_multipart_resume(session(),local(),pages)
        self.assertEqual(result["decision"],"resume")
        self.assertEqual(result["pending_parts"],[2])
        self.assertNotIn("complete_multipart",[item["op"] for item in result["actions"]])

    def test_unknown_completion_only_probes(self):
        result=plan_multipart_resume(session("complete_unknown"),local(),[])
        self.assertEqual(result["decision"],"probe")
        self.assertEqual([item["op"] for item in result["actions"]],["head_verify"])


if __name__ == "__main__":
    unittest.main()
