import unittest
from src.message_resolver import render_message

class MessageTests(unittest.TestCase):
    def test_present_empty_does_not_fall_back(self):
        result=render_message({"fr-CA":{"x":""},"fr":{"x":"fallback"},"root":{}},{},"fr_CA","x",{},None)
        self.assertEqual(result["text"],"");self.assertEqual(result["locale_used"],"fr-CA")
    def test_explicit_parent_precedes_truncation(self):
        result=render_message({"en-001":{"x":"world"},"en":{"x":"language"},"root":{}},{"en-GB":"en-001"},"en-GB","x",{},None)
        self.assertEqual(result["text"],"world")

if __name__=="__main__":unittest.main()
