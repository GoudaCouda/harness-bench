import unittest

from src.wheel_selector import select_wheel


class WheelSelectorTests(unittest.TestCase):
    def test_target_tag_priority_beats_asset_order(self):
        target = {
            "project": "demo-kit",
            "version": "1.0",
            "supported_tags": ["cp312-cp312-linux_x86_64", "py3-none-any"],
            "allow_yanked": False,
        }
        assets = [
            {"filename": "demo_kit-1.0-py3-none-any.whl", "sha256": "a" * 64, "size": 1, "yanked": False},
            {"filename": "demo_kit-1.0-cp312-cp312-linux_x86_64.whl", "sha256": "b" * 64, "size": 2, "yanked": False},
        ]
        result = select_wheel(target, assets)
        self.assertEqual(result["filename"], assets[1]["filename"])
        self.assertEqual(result["matched_tag"], target["supported_tags"][0])

    def test_yanked_asset_is_not_selected_by_default(self):
        target = {
            "project": "demo-kit",
            "version": "1.0",
            "supported_tags": ["py3-none-any"],
            "allow_yanked": False,
        }
        assets = [{"filename": "demo_kit-1.0-py3-none-any.whl", "sha256": "a" * 64, "size": 1, "yanked": True}]
        self.assertEqual(select_wheel(target, assets)["decision"], "no_compatible")


if __name__ == "__main__":
    unittest.main()
