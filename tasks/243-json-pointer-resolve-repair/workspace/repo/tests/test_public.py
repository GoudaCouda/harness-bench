import unittest
from pointer import resolve_pointer


class PointerTests(unittest.TestCase):
    def test_array_member(self):
        doc = {"mills": [{"mill_id": "m-east"}, {"mill_id": "m-west"}]}
        self.assertEqual(resolve_pointer(doc, "/mills/1/mill_id"), "m-west")

    def test_empty_pointer_returns_document(self):
        doc = {"mill_id": "m-east"}
        self.assertEqual(resolve_pointer(doc, ""), doc)

    def test_tilde_unescape(self):
        doc = {"a/b": {"~t": "tilde"}}
        self.assertEqual(resolve_pointer(doc, "/a~1b/~0t"), "tilde")

    def test_missing_raises(self):
        with self.assertRaises(ValueError):
            resolve_pointer({"mills": ["east"]}, "/mills/3")


if __name__ == "__main__":
    unittest.main()
