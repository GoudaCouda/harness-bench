import unittest

from src.api_compat import compare_api_schemas


def policy():
    return {
        "reject_unknown_request_properties": True,
        "closed_response_enums": True,
        "closed_response_variants": True,
        "require_discriminator_property": True,
    }


def schema(direction, required, properties):
    return {
        "schema_id": "sample",
        "direction": direction,
        "required": required,
        "properties": properties,
        "discriminator": None,
    }


def prop(name, *, enum=None, nullable=False, read_only=False, write_only=False):
    return {
        "name": name,
        "type": "string",
        "enum": enum,
        "nullable": nullable,
        "read_only": read_only,
        "write_only": write_only,
    }


class CompatibilityTests(unittest.TestCase):
    def test_required_request_addition_breaks(self):
        old = [schema("request", [], [prop("value")])]
        new = [schema("request", ["value"], [prop("value")])]
        row = compare_api_schemas(old, new, policy())["findings"][0]
        self.assertEqual((row["status"], row["reason"]), ("breaking", "required_added"))

    def test_response_enum_widening_breaks_closed_consumers(self):
        old = [schema("response", [], [prop("state", enum=["a"])])]
        new = [schema("response", [], [prop("state", enum=["a", "b"])])]
        row = compare_api_schemas(old, new, policy())["findings"][0]
        self.assertEqual(row["reason"], "enum_widened")

    def test_readonly_request_field_is_inactive(self):
        old = [schema("request", [], [])]
        new = [schema("request", ["id"], [prop("id", read_only=True)])]
        self.assertEqual(compare_api_schemas(old, new, policy())["findings"], [])


if __name__ == "__main__":
    unittest.main()
