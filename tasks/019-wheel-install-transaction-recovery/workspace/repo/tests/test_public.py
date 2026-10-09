import unittest

from src.install_recovery import plan_recovery


class RecoveryPlannerTests(unittest.TestCase):
    def test_created_file_is_removed(self):
        state = {"files":[{"path":"nova/new.py","digest":"sha256=bmV3","owners":["nova"]}]}
        journal = {"package":"nova","phase":"applying","entries":[{"path":"nova/new.py","before":None,"after_digest":"sha256=bmV3","applied":True}]}
        record = [{"path":"nova/new.py","digest":"sha256=bmV3","size":3}]
        self.assertEqual(plan_recovery(state, journal, record)["actions"], [{"kind":"remove","path":"nova/new.py"}])

    def test_drift_suppresses_the_whole_plan(self):
        state = {"files":[
            {"path":"nova/a.py","digest":"sha256=bmV3","owners":["nova"]},
            {"path":"nova/b.py","digest":"sha256=bGF0ZXI","owners":["nova"]},
        ]}
        journal = {"package":"nova","phase":"recovering","entries":[
            {"path":"nova/a.py","before":None,"after_digest":"sha256=bmV3","applied":True},
            {"path":"nova/b.py","before":None,"after_digest":"sha256=bmV3Mg","applied":True},
        ]}
        record = [
            {"path":"nova/a.py","digest":"sha256=bmV3","size":3},
            {"path":"nova/b.py","digest":"sha256=bmV3Mg","size":4},
        ]
        plan = plan_recovery(state, journal, record)
        self.assertEqual(plan["decision"], "manual_intervention")
        self.assertEqual(plan["actions"], [])


if __name__ == "__main__":
    unittest.main()
