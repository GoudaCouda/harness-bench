import unittest

from src.admission import evaluate_admission


POLICY = {"require_side_effect_free": False, "immutable_paths": ["metadata/name"]}
WEBHOOK = {
    "name": "public",
    "operations": ["CREATE"],
    "resources": ["pods"],
    "excluded_namespaces": [],
    "side_effects": "None",
    "failure_policy": "Fail",
    "reinvocation_policy": "IfNeeded",
    "available": True,
    "mutations": [
        {"path": "metadata/labels/team", "mode": "set_if_missing", "value": "demo"}
    ],
}
REQUEST = {
    "request_id": "public",
    "operation": "CREATE",
    "resource": "pods",
    "namespace": "apps",
    "dry_run": False,
    "mirror_pod": False,
    "fields": {"metadata/name": "pod"},
}


class AdmissionTests(unittest.TestCase):
    def test_default_is_applied(self):
        result = evaluate_admission([REQUEST], [WEBHOOK], POLICY)
        self.assertEqual(result["objects"][0]["fields"]["metadata/labels/team"], "demo")

    def test_existing_default_is_preserved(self):
        request = dict(REQUEST)
        request["fields"] = {"metadata/name": "pod", "metadata/labels/team": "owner"}
        result = evaluate_admission([request], [WEBHOOK], POLICY)
        self.assertEqual(
            result["objects"][0]["fields"]["metadata/labels/team"], "owner"
        )


if __name__ == "__main__":
    unittest.main()
