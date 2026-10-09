import unittest
from src.case_rename import plan_case_renames


class CaseRenameTests(unittest.TestCase):
    def test_case_only_rename_uses_temporary_hop(self):
        result = plan_case_renames(
            [{"path":"src/API.py","oid":"a" * 40,"stage":0}],
            [{"from":"src/API.py","to":"src/api.py"}],
            True,
        )
        self.assertEqual(len(result["operations"]), 2)
        self.assertEqual(result["operations"][-1]["to"], "src/api.py")
        self.assertEqual(result["final_entries"][0]["oid"], "a" * 40)

    def test_simple_rename_is_direct(self):
        result = plan_case_renames(
            [{"path":"old.txt","oid":"b" * 40,"stage":0}],
            [{"from":"old.txt","to":"new.txt"}],
            False,
        )
        self.assertEqual(result["operations"], [{"op":"git_mv","from":"old.txt","to":"new.txt"}])


if __name__ == "__main__":
    unittest.main()
