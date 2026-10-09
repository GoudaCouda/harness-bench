import unittest

from affected_build import plan_affected


class AffectedBuildTests(unittest.TestCase):
    def test_source_change_rebuilds_reverse_dependants(self):
        graph = {
            "packages": {
                "base": {
                    "dependencies": [],
                    "source_roots": ["base/src/"],
                    "generated_inputs": [],
                    "buildable": True,
                },
                "app": {
                    "dependencies": ["base"],
                    "source_roots": ["app/src/"],
                    "generated_inputs": [],
                    "buildable": True,
                },
            },
            "global_inputs": {},
        }
        self.assertEqual(
            plan_affected(["base/src/value.py"], graph),
            ["base", "app"],
        )

    def test_unowned_markdown_change_does_not_build(self):
        graph = {
            "packages": {
                "app": {
                    "dependencies": [],
                    "source_roots": ["app/src/"],
                    "generated_inputs": [],
                    "buildable": True,
                }
            },
            "global_inputs": {},
        }
        self.assertEqual(plan_affected(["docs/readme.md"], graph), [])


if __name__ == "__main__":
    unittest.main()
