from __future__ import annotations

import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from deadline_policy import (  # noqa: E402
    FixtureMetrics,
    deadline_flags,
    deadline_floor,
    evaluate_deadline,
    load_decision,
    rewrite_timeout_text,
    run,
)


class DeadlinePolicyUnitTests(unittest.TestCase):
    def test_flags_and_all_four_floor(self) -> None:
        flags = deadline_flags(
            {
                "difficulty": "hard",
                "required_artifacts": ["a", "b", "c", "d"],
                "stressors": ["a", "b", "c", "d"],
                "harness_demands": [],
            },
            FixtureMetrics(files=1, bytes=12 * 1024, newlines=0),
        )

        self.assertEqual(flags, {"H": True, "A": True, "I": True, "S": True})
        self.assertEqual(deadline_floor(flags), 1800)

    def test_input_flag_accepts_300_literal_newline_bytes(self) -> None:
        flags = deadline_flags(
            {},
            FixtureMetrics(files=1, bytes=600, newlines=300),
        )

        self.assertTrue(flags["I"])
        self.assertEqual(deadline_floor(flags), 1800)

    def test_workload_flags_do_not_reduce_the_global_floor(self) -> None:
        flags = deadline_flags(
            {
                "difficulty": "hard",
                "required_artifacts": ["a", "b", "c", "d"],
            },
            FixtureMetrics(files=0, bytes=0, newlines=0),
        )

        self.assertEqual(deadline_floor(flags), 1800)

    def test_effective_timeout_never_decreases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            (task_dir / "workspace").mkdir()
            decision = evaluate_deadline(
                task_dir,
                {
                    "task_id": "999-example",
                    "timeout_sec": 3600,
                    "difficulty": "easy",
                },
            )

        self.assertEqual(decision.floor, 1800)
        self.assertEqual(decision.effective_timeout, 3600)
        self.assertFalse(decision.changed)

    def test_workspace_measurement_uses_all_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            fixture_dir = task_dir / "visible" / "nested"
            fixture_dir.mkdir(parents=True)
            (fixture_dir / "rows.txt").write_bytes(b"x\n" * 300)
            decision = evaluate_deadline(
                task_dir,
                {
                    "task_id": "999-example",
                    "workspace_dir": "visible",
                    "timeout_sec": 600,
                },
            )

        self.assertEqual(decision.fixture_metrics.files, 1)
        self.assertEqual(decision.fixture_metrics.newlines, 300)
        self.assertEqual(decision.floor, 1800)
        self.assertEqual(decision.effective_timeout, 1800)

    def test_scalar_rewrite_preserves_surrounding_yaml(self) -> None:
        source = "task_id: 999-example\ntimeout_sec: 600  # keep\nfoo: bar\n"

        self.assertEqual(
            rewrite_timeout_text(source, 1200),
            "task_id: 999-example\ntimeout_sec: 1200  # keep\nfoo: bar\n",
        )

    def test_check_and_write_cli_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tasks_dir = Path(temporary)
            task_dir = tasks_dir / "999-example"
            (task_dir / "workspace").mkdir(parents=True)
            task_yaml = task_dir / "task.yaml"
            task_yaml.write_text(
                "task_id: 999-example\n"
                "workspace_dir: workspace\n"
                "timeout_sec: 600\n"
                "difficulty: easy\n",
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                check_status = run(tasks_dir, write=False)
                write_status = run(tasks_dir, write=True)
                final_status = run(tasks_dir, write=False)
            metadata = yaml.safe_load(task_yaml.read_text(encoding="utf-8"))

        self.assertEqual(check_status, 1)
        self.assertEqual(write_status, 0)
        self.assertEqual(final_status, 0)
        self.assertEqual(metadata["timeout_sec"], 1800)


class DeadlinePolicySuiteTests(unittest.TestCase):
    def test_suite_has_expected_flags_and_normalized_distribution(self) -> None:
        task_yamls = sorted(TASKS.glob("*/task.yaml"))
        decisions = [load_decision(path) for path in task_yamls]
        all_four = [
            item.task_id.split("-", 1)[0] for item in decisions if item.flag_count == 4
        ]
        distribution = Counter(item.effective_timeout for item in decisions)

        self.assertEqual(len(decisions), 274)
        self.assertEqual(
            all_four,
            [
                "001",
                "006",
                "007",
                "021",
                "031",
                "032",
                "038",
                "049",
                "071",
                "095",
                "097",
                "102",
                "105",
                "106",
                "107",
                "110",
                "111",
                "112",
                "113",
                "115",
                "116",
                "117",
                "118",
                "121",
                "122",
                "123",
                "124",
                "125",
                "126",
                "127",
                "129",
                "130",
                "132",
                "136",
                "137",
                "138",
                "140",
                "141",
                "144",
                "151",
                "162",
                "195",
                "197",
                "200",
                "201",
                "202",
                "203",
                "204",
                "205",
                "206",
                "207",
                "208",
                "209",
                "210",
                "211",
                "212",
                "214",
            ],
        )
        self.assertEqual(
            distribution,
            Counter({7200: 185, 3600: 44, 2400: 17, 1800: 28}),
        )
        self.assertEqual(
            next(
                item.effective_timeout
                for item in decisions
                if item.task_id == "088-cardinality-guarded-join"
            ),
            3600,
        )
        self.assertFalse(
            [item.task_id for item in decisions if item.changed],
            "all committed task deadlines must already satisfy the policy",
        )

    def test_every_task_yaml_still_contains_an_integer_timeout(self) -> None:
        for task_yaml in sorted(TASKS.glob("*/task.yaml")):
            with self.subTest(task=task_yaml.parent.name):
                metadata = yaml.safe_load(task_yaml.read_text(encoding="utf-8"))
                self.assertIs(type(metadata.get("timeout_sec")), int)
                self.assertGreater(metadata["timeout_sec"], 0)


if __name__ == "__main__":
    unittest.main()
