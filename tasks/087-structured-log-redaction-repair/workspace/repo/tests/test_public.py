import unittest

from src.redactor import redact_event


POLICY = {
    "sensitive_keys": ["password", "access_token"],
    "replacement": "[REDACTED]",
    "text_assignments": ["password", "api_key"],
}


class RedactorTests(unittest.TestCase):
    def test_nested_exact_key_and_harmless_substring(self):
        source = {"auth": {"Access_Token": "secret"}, "tokenizer": "ready"}
        result = redact_event(source, POLICY)
        self.assertEqual(result["event"]["auth"]["Access_Token"], "[REDACTED]")
        self.assertEqual(result["event"]["tokenizer"], "ready")
        self.assertEqual(source["auth"]["Access_Token"], "secret")

    def test_text_forms(self):
        source = {"message": "Bearer abc.def then api_key = k-1"}
        result = redact_event(source, POLICY)
        self.assertEqual(
            result["event"]["message"],
            "Bearer [REDACTED] then api_key = [REDACTED]",
        )


if __name__ == "__main__":
    unittest.main()
