import unittest
from src.identifier_migrator import migrate_identifiers


class IdentifierTests(unittest.TestCase):
    def test_compatibility_collision_is_quarantined(self):
        records=[{"record_id":"a","identifier":"Ｋey","references":[]},{"record_id":"b","identifier":"key","references":[]}]
        result=migrate_identifiers(records,[],{"normalization":"NFKC","case_insensitive":True,"max_codepoints":20})
        self.assertEqual([row["status"] for row in result["records"]],["collision","collision"])
        self.assertEqual(result["conflicts"][0]["canonical_identifier"],"key")

    def test_visual_confusable_is_not_automatically_merged(self):
        records=[{"record_id":"latin","identifier":"Alpha","references":[]},{"record_id":"greek","identifier":"Αlpha","references":[]}]
        result=migrate_identifiers(records,[],{"normalization":"NFKC","case_insensitive":True,"max_codepoints":20})
        self.assertEqual([row["status"] for row in result["records"]],["accepted","accepted"])


if __name__=="__main__": unittest.main()
