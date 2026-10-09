import unittest

from src.compatibility import assess_compatibility


class CompatibilityTests(unittest.TestCase):
    def test_new_required_request_field_is_breaking(self):
        before = {"op": {"request": {"properties": {}, "required": []}, "response": {"properties": {}, "required": []}}}
        after = {"op": {"request": {"properties": {"tenant": {"type": ["string"]}}, "required": ["tenant"]}, "response": {"properties": {}, "required": []}}}
        consumer = [{"consumer_id":"c","operations":["op"],"always_sends":{"op":[]},"request_values":{"op":{}},"response_fields":{"op":[]},"accepts_null":{"op":[]},"exhaustive_enums":{"op":[]},"reject_unknown_response":{"op":False}}]
        self.assertIn("request_required_added", [x["code"] for x in assess_compatibility(before, after, consumer)["issues"]])

    def test_tolerant_reader_accepts_new_response_field(self):
        before = {"op":{"request":{"properties":{},"required":[]},"response":{"properties":{},"required":[]}}}
        after = {"op":{"request":{"properties":{},"required":[]},"response":{"properties":{"trace":{"type":["string"]}},"required":[]}}}
        consumer = [{"consumer_id":"c","operations":["op"],"always_sends":{"op":[]},"request_values":{"op":{}},"response_fields":{"op":[]},"accepts_null":{"op":[]},"exhaustive_enums":{"op":[]},"reject_unknown_response":{"op":False}}]
        self.assertTrue(assess_compatibility(before, after, consumer)["compatible"])


if __name__ == "__main__": unittest.main()
