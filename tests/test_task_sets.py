from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harnessbench.task_sets import (
    TaskSetError,
    bytes_sha256,
    load_task_set,
    make_task_selection_identity,
    task_ids_sha256,
    validate_task_selection_identity,
)


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from run_benchmark import (  # noqa: E402
    BenchmarkTask,
    freeze_task_set_manifest,
    resolve_benchmark_selection,
    select_benchmark_tasks,
)


def manifest_text(
    *,
    task_count: int,
    task_ids: str,
    source_suite_size: int,
    extra: str = "",
    policy_extra: str = "",
    source_suite: str = "main",
) -> str:
    return f"""\
schema_version: 1
task_set: curated
status: research_subset
source_suite: {source_suite}
source_suite_size: {source_suite_size}
task_count: {task_count}
selection_policy:
  selected_at: '2026-07-31'
  model_outcomes_used: false
  changes_main_membership: false
  relocates_task_directories: false
  purpose: Validate the protocol.
{policy_extra}task_ids: [{task_ids}]
{extra}"""


class TaskSetLoaderTests(unittest.TestCase):
    def write_manifest(self, catalog: Path, name: str, text: str) -> Path:
        path = catalog / f"{name}.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_loads_valid_manifest_and_preserves_declared_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary)
            self.write_manifest(
                catalog,
                "curated",
                manifest_text(
                    task_count=2,
                    task_ids="002-beta, 001-alpha",
                    source_suite_size=3,
                ),
            )
            task_set = load_task_set(
                catalog,
                "curated",
                known_task_ids={"001-alpha", "002-beta", "003-gamma"},
            )

        self.assertEqual(task_set.schema_version, 1)
        self.assertEqual(task_set.name, "curated")
        self.assertEqual(task_set.status, "research_subset")
        self.assertEqual(task_set.source_suite, "main")
        self.assertEqual(task_set.source_suite_size, 3)
        self.assertEqual(task_set.task_count, 2)
        self.assertFalse(task_set.selection_policy["model_outcomes_used"])
        self.assertEqual(task_set.task_ids, ("002-beta", "001-alpha"))
        self.assertRegex(task_set.manifest_sha256, r"^sha256:[0-9a-f]{64}$")

    def test_checked_in_standard237_manifest_loads_against_main_suite(self) -> None:
        known_task_ids = {
            task_yaml.parent.name for task_yaml in (ROOT / "tasks").glob("*/task.yaml")
        }
        task_set = load_task_set(
            ROOT / "catalog",
            "standard237",
            known_task_ids=known_task_ids,
        )
        self.assertEqual(task_set.task_count, 237)
        self.assertEqual(len(task_set.task_ids), 237)
        self.assertEqual(task_set.source_suite_size, 237)
        self.assertTrue(str(task_set.status).startswith("frozen_"))

    def test_checked_in_standard254_manifest_loads_against_main_suite(self) -> None:
        known_task_ids = {
            task_yaml.parent.name for task_yaml in (ROOT / "tasks").glob("*/task.yaml")
        }
        task_set = load_task_set(
            ROOT / "catalog",
            "standard254",
            known_task_ids=known_task_ids,
        )
        self.assertEqual(task_set.task_count, 254)
        self.assertEqual(len(task_set.task_ids), 254)
        self.assertEqual(task_set.source_suite_size, 254)
        self.assertTrue(str(task_set.status).startswith("frozen_"))

    def test_checked_in_standard274_manifest_loads_against_main_suite(self) -> None:
        known_task_ids = {
            task_yaml.parent.name for task_yaml in (ROOT / "tasks").glob("*/task.yaml")
        }
        task_set = load_task_set(
            ROOT / "catalog",
            "standard274",
            known_task_ids=known_task_ids,
        )
        self.assertEqual(task_set.task_count, 274)
        self.assertEqual(len(task_set.task_ids), 274)
        self.assertEqual(task_set.source_suite_size, 274)
        self.assertEqual(len(known_task_ids), 274)

    def test_rejects_unsafe_name_before_resolving_a_path(self) -> None:
        with self.assertRaisesRegex(TaskSetError, "must match"):
            load_task_set(
                Path("/does/not/matter"),
                "../curated",
                known_task_ids=set(),
            )

    def test_rejects_duplicate_yaml_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary)
            self.write_manifest(
                catalog,
                "curated",
                """\
schema_version: 1
task_set: curated
task_set: replacement
status: research_subset
source_suite: main
source_suite_size: 1
task_count: 1
selection_policy:
  selected_at: '2026-07-31'
  model_outcomes_used: false
  changes_main_membership: false
  relocates_task_directories: false
  purpose: Validate the protocol.
task_ids: [001-alpha]
""",
            )
            with self.assertRaisesRegex(TaskSetError, "duplicate key"):
                load_task_set(
                    catalog,
                    "curated",
                    known_task_ids={"001-alpha"},
                )

    def test_rejects_duplicate_task_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary)
            self.write_manifest(
                catalog,
                "curated",
                manifest_text(
                    task_count=2,
                    task_ids="001-alpha, 001-alpha",
                    source_suite_size=1,
                ),
            )
            with self.assertRaisesRegex(TaskSetError, "duplicate task ID"):
                load_task_set(
                    catalog,
                    "curated",
                    known_task_ids={"001-alpha"},
                )

    def test_rejects_count_drift_and_unknown_task_ids(self) -> None:
        cases = (
            (
                manifest_text(
                    task_count=2,
                    task_ids="001-alpha",
                    source_suite_size=1,
                ),
                "task_count mismatch",
            ),
            (
                manifest_text(
                    task_count=1,
                    task_ids="999-missing",
                    source_suite_size=1,
                ),
                "unknown task ID",
            ),
        )
        for manifest, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                catalog = Path(tmp)
                self.write_manifest(catalog, "curated", manifest)
                with self.assertRaisesRegex(TaskSetError, expected):
                    load_task_set(
                        catalog,
                        "curated",
                        known_task_ids={"001-alpha"},
                    )

    def test_rejects_unknown_manifest_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary)
            self.write_manifest(
                catalog,
                "curated",
                manifest_text(
                    task_count=1,
                    task_ids="001-alpha",
                    source_suite_size=1,
                    extra="description: not-part-of-schema-v1\n",
                ),
            )
            with self.assertRaisesRegex(TaskSetError, "unknown field"):
                load_task_set(
                    catalog,
                    "curated",
                    known_task_ids={"001-alpha"},
                )

    def test_rejects_task_set_from_another_source_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary)
            self.write_manifest(
                catalog,
                "curated",
                manifest_text(
                    task_count=1,
                    task_ids="001-alpha",
                    source_suite_size=1,
                    source_suite="bogus",
                ),
            )
            with self.assertRaisesRegex(TaskSetError, "source_suite must be 'main'"):
                load_task_set(
                    catalog,
                    "curated",
                    known_task_ids={"001-alpha"},
                )

    def test_rejects_unknown_selection_policy_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary)
            self.write_manifest(
                catalog,
                "curated",
                manifest_text(
                    task_count=1,
                    task_ids="001-alpha",
                    source_suite_size=1,
                    policy_extra="  hidden_knob: true\n",
                ),
            )
            with self.assertRaisesRegex(TaskSetError, "selection_policy.*unknown"):
                load_task_set(
                    catalog,
                    "curated",
                    known_task_ids={"001-alpha"},
                )


class BenchmarkTaskSetSelectionTests(unittest.TestCase):
    def make_tasks(self, root: Path) -> list[BenchmarkTask]:
        return [
            BenchmarkTask(
                task_id=task_id,
                title=task_id,
                domain="test",
                difficulty="test",
                task_dir=root / task_id,
                metadata={},
                definition_sha256=str(index) * 64,
            )
            for index, task_id in enumerate(
                ("001-alpha", "002-beta", "003-gamma"),
                start=1,
            )
        ]

    def test_named_set_selects_in_canonical_suite_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog"
            catalog.mkdir()
            (catalog / "curated.yaml").write_text(
                manifest_text(
                    task_count=2,
                    task_ids="003-gamma, 001-alpha",
                    source_suite_size=3,
                ),
                encoding="utf-8",
            )
            selected = select_benchmark_tasks(
                self.make_tasks(root),
                requested_tasks=None,
                task_set_name="curated",
                catalog_dir=catalog,
            )

        self.assertEqual(
            [task.task_id for task in selected],
            ["001-alpha", "003-gamma"],
        )

    def test_named_selection_identity_is_global_and_manifest_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog"
            catalog.mkdir()
            manifest = manifest_text(
                task_count=2,
                task_ids="003-gamma, 001-alpha",
                source_suite_size=3,
            )
            (catalog / "curated.yaml").write_text(manifest, encoding="utf-8")
            selection = resolve_benchmark_selection(
                self.make_tasks(root),
                requested_tasks=None,
                task_set_name="curated",
                catalog_dir=catalog,
            )

            self.assertEqual(selection.identity["mode"], "named")
            self.assertEqual(selection.identity["task_set"], "curated")
            self.assertEqual(selection.identity["declared_count"], 2)
            self.assertEqual(
                selection.identity["task_ids_sha256"],
                task_ids_sha256(("001-alpha", "003-gamma")),
            )
            self.assertEqual(
                selection.identity["manifest_sha256"],
                bytes_sha256(manifest.encode("utf-8")),
            )

            frozen_catalog = freeze_task_set_manifest(root / "run", selection)
            frozen = frozen_catalog / "curated.yaml"
            self.assertEqual(frozen.read_text(encoding="utf-8"), manifest)
            frozen.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                freeze_task_set_manifest(root / "run", selection)

    def test_task_selection_identity_is_order_independent_and_strict(self) -> None:
        first = make_task_selection_identity(
            mode="inline",
            task_ids=("002-beta", "001-alpha"),
        )
        second = make_task_selection_identity(
            mode="inline",
            task_ids=("001-alpha", "002-beta"),
        )
        self.assertEqual(first, second)
        invalid = {**first, "declared_count": True}
        with self.assertRaisesRegex(TaskSetError, "declared_count"):
            validate_task_selection_identity(invalid)

    def test_legacy_tasks_selection_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tasks = self.make_tasks(Path(temporary))
            selected = select_benchmark_tasks(
                tasks,
                requested_tasks=" 003-gamma,001-alpha ",
                task_set_name=None,
            )
            self.assertEqual(
                [task.task_id for task in selected],
                ["001-alpha", "003-gamma"],
            )
            with self.assertRaisesRegex(ValueError, "unknown benchmark task"):
                select_benchmark_tasks(
                    tasks,
                    requested_tasks="999-missing",
                    task_set_name=None,
                )

    def test_empty_task_set_name_is_rejected_instead_of_selecting_full_suite(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(TaskSetError, "must match"):
                select_benchmark_tasks(
                    self.make_tasks(Path(temporary)),
                    requested_tasks=None,
                    task_set_name="",
                )

    def test_entrypoints_make_tasks_and_task_set_mutually_exclusive(self) -> None:
        commands = (
            [
                sys.executable,
                str(ROOT / "tools" / "run_benchmark.py"),
                "--base-url",
                "http://model.invalid/v1",
                "--model",
                "test",
                "--tasks",
                "001-alpha",
                "--task-set",
                "curated",
            ],
            [
                sys.executable,
                str(ROOT / "tools" / "task_maintenance" / "validate_docker_grader.py"),
                "--tasks",
                "001-alpha",
                "--task-set",
                "curated",
            ],
        )
        for command in commands:
            with self.subTest(entrypoint=command[1]):
                completed = subprocess.run(
                    command,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn("not allowed with argument", completed.stderr)

    def test_runner_rejects_missing_task_set_before_creating_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_root = Path(temporary) / "must-not-exist"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "run_benchmark.py"),
                    "--base-url",
                    "http://model.invalid/v1",
                    "--model",
                    "test",
                    "--task-set",
                    "missing",
                    "--run-root",
                    str(run_root),
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("task selection preflight failed", completed.stderr)
            self.assertIn("manifest does not exist", completed.stderr)
            self.assertFalse(run_root.exists())

    def test_docker_grader_rejects_task_set_with_numeric_range(self) -> None:
        entrypoint = str(
            ROOT / "tools" / "task_maintenance" / "validate_docker_grader.py"
        )
        for range_arguments in (("--start", "3"), ("--end", "200")):
            with self.subTest(range_arguments=range_arguments):
                completed = subprocess.run(
                    [
                        sys.executable,
                        entrypoint,
                        "--task-set",
                        "curated",
                        *range_arguments,
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn(
                    "--task-set cannot be combined with --start or --end",
                    completed.stderr,
                )


if __name__ == "__main__":
    unittest.main()
