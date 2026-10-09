from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
DASHBOARD = ROOT / "dashboard"
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from build_catalog import (  # noqa: E402
    CATALOG_CSV,
    SUITE_YAML,
    catalog_workspace_files,
    collect_rows,
    render_catalog,
)


def scalar_counts(metadata: list[dict[str, object]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "(unspecified)") for row in metadata)
    return dict(sorted(counts.items()))


def list_counts(metadata: list[dict[str, object]], field: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in metadata:
        counts.update(set(row.get(field) or []))
    return dict(sorted(counts.items()))


class CatalogReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.task_yamls = sorted((ROOT / "tasks").glob("*/task.yaml"))
        cls.metadata = [
            yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for path in cls.task_yamls
        ]
        cls.suite = yaml.safe_load((CATALOG / "suite.yaml").read_text(encoding="utf-8"))

    def test_main_suite_membership_matches_task_metadata(self) -> None:
        expected_ids = sorted(str(row["task_id"]) for row in self.metadata)
        self.assertEqual(self.suite["suite"], "main")
        self.assertEqual(self.suite["suite_size"], 274)
        self.assertEqual(self.suite["suite_size"], len(expected_ids))
        self.assertEqual(self.suite["task_ids"], expected_ids)
        self.assertEqual(len(set(expected_ids)), len(expected_ids))

    def test_suite_statistics_are_derived_from_metadata(self) -> None:
        statistics = self.suite["statistics"]
        for field in ("domain", "difficulty", "task_family", "variant"):
            self.assertEqual(statistics[field], scalar_counts(self.metadata, field))
        for field in ("harness_demands", "capability_tags", "stressors"):
            self.assertEqual(statistics[field], list_counts(self.metadata, field))

    def test_csv_has_one_traceable_row_per_task(self) -> None:
        with (CATALOG / "task_catalog.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        expected_ids = sorted(str(row["task_id"]) for row in self.metadata)
        self.assertEqual([row["task_id"] for row in rows], expected_ids)
        for field in (
            "task_family",
            "variant",
            "harness_demands",
            "design_file",
            "provenance_origin",
            "source_ids",
        ):
            self.assertIn(field, rows[0])
        for row in rows:
            self.assertTrue(row["design_file"], row["task_id"])
            self.assertTrue(
                (ROOT / "tasks" / row["task_id"] / row["design_file"]).is_file(),
                row["task_id"],
            )

    def test_catalog_workspace_statistics_ignore_local_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            source = workspace / "repo" / "app.py"
            bytecode = workspace / "repo" / "__pycache__" / "app.cpython-313.pyc"
            pytest_cache = workspace / ".pytest_cache" / "state"
            source.parent.mkdir(parents=True)
            bytecode.parent.mkdir(parents=True)
            pytest_cache.parent.mkdir(parents=True)
            source.write_text("VALUE = 1\n", encoding="utf-8")
            bytecode.write_bytes(b"local bytecode")
            pytest_cache.write_text("local cache", encoding="utf-8")
            (workspace / ".DS_Store").write_bytes(b"editor noise")

            files = catalog_workspace_files(workspace)

        self.assertEqual(
            [path.relative_to(workspace).as_posix() for path in files],
            ["repo/app.py"],
        )

    def test_checked_in_catalog_is_current(self) -> None:
        expected_csv, expected_suite = render_catalog(collect_rows())
        self.assertEqual(CATALOG_CSV.read_text(encoding="utf-8"), expected_csv)
        self.assertEqual(SUITE_YAML.read_text(encoding="utf-8"), expected_suite)


class DashboardReleaseTests(unittest.TestCase):
    def run_dashboard(
        self,
        summary: dict[str, object],
        *,
        domain_filter: str = "",
        difficulty_filter: str = "",
        status_filter: str = "",
        review_only: bool = False,
    ) -> dict[str, object]:
        if shutil.which("node") is None:
            self.skipTest("Node.js is optional and unavailable on this worker")
        node_program = r"""
const fs = require("fs");
const vm = require("vm");
const elements = {};
function element(id) {
  if (!elements[id]) {
    elements[id] = {
      id, value: "", checked: false, hidden: false, textContent: "",
      innerHTML: "", style: {}, classList: {add() {}, remove() {}},
      addEventListener() {}
    };
  }
  return elements[id];
}
global.document = {
  title: "",
  getElementById: element,
  querySelector: () => element("query")
};
global.window = {
  HARNESSBENCH_SUMMARY: JSON.parse(process.env.SUMMARY),
  location: {protocol: "file:"}
};
global.fetch = () => { throw new Error("file dashboards must not fetch"); };
global.setInterval = () => { throw new Error("file dashboards must not poll"); };
vm.runInThisContext(fs.readFileSync(process.env.APP, "utf8"));
if (
  process.env.DOMAIN_FILTER ||
  process.env.DIFFICULTY_FILTER ||
  process.env.STATUS_FILTER ||
  process.env.REVIEW_ONLY === "1"
) {
  element("domainFilter").value = process.env.DOMAIN_FILTER;
  element("difficultyFilter").value = process.env.DIFFICULTY_FILTER;
  element("statusFilter").value = process.env.STATUS_FILTER;
  element("reviewOnly").checked = process.env.REVIEW_ONLY === "1";
  renderRows();
}
process.stdout.write(JSON.stringify({
  title: document.title,
  progress: element("progressText").textContent,
  completedScope: element("completedScope").textContent,
  strictPassScope: element("strictPassScope").textContent,
  safetyGateRate: element("safetyGateRate").textContent,
  safetyGateScope: element("safetyGateScope").textContent,
  suiteMeta: element("suiteMeta").textContent,
  snapshotHidden: element("snapshotNotice").hidden,
  snapshotCopy: element("snapshotCopy").textContent,
  isolationHidden: element("isolationNotice").hidden,
  isolationCopy: element("isolationCopy").textContent,
  difficultyOverview: element("difficulties").innerHTML,
  difficultyOptions: element("difficultyFilter").innerHTML,
  taskRows: element("taskRows").innerHTML
}));
"""
        env = {
            **os.environ,
            "APP": str(DASHBOARD / "app.js"),
            "SUMMARY": json.dumps(summary),
            "DOMAIN_FILTER": domain_filter,
            "DIFFICULTY_FILTER": difficulty_filter,
            "STATUS_FILTER": status_filter,
            "REVIEW_ONLY": "1" if review_only else "0",
        }
        result = subprocess.run(
            ["node", "-e", node_program],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return json.loads(result.stdout)

    def test_file_dashboard_uses_selected_and_suite_counts(self) -> None:
        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "main",
                "suite_size": 112,
                "selected_count": 1,
                "completed_count": 1,
                "progress": 1.0,
                "tasks": [
                    {
                        "task_id": "001-example",
                        "title": "Example",
                        "domain": "Research",
                        "difficulty": "hard",
                        "status": "completed",
                        "outcome_score": 0.5,
                    }
                ],
            }
        )
        self.assertEqual(rendered["progress"], "1 / 1")
        self.assertEqual(rendered["completedScope"], "of 1 selected tasks")
        self.assertIn("suite main", rendered["suiteMeta"])
        self.assertIn("112 tasks", rendered["suiteMeta"])
        self.assertEqual(rendered["strictPassScope"], "new-protocol results only")
        self.assertTrue(rendered["snapshotHidden"])

    def test_strict_pass_rate_scope_excludes_legacy_results(self) -> None:
        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "main",
                "suite_size": 112,
                "selected_count": 112,
                "completed_count": 112,
                "pass_rate_completed": 0.75,
                "strict_pass_evaluated_count": 8,
                "strict_passed_count": 6,
                "tasks": [],
            }
        )
        self.assertEqual(rendered["strictPassScope"], "6 / 8 new-protocol results")

    def test_non_main_result_is_visibly_historical(self) -> None:
        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "legacy-release",
                "suite_size": 68,
                "selected_count": 2,
                "completed_count": 2,
                "tasks": [],
            }
        )
        self.assertFalse(rendered["snapshotHidden"])
        self.assertIn("Historical", rendered["title"])
        self.assertIn("not part of the current main suite", rendered["snapshotCopy"])

    def test_transitional_isolation_is_visible(self) -> None:
        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "main",
                "suite_size": 112,
                "selected_count": 0,
                "completed_count": 0,
                "tasks": [],
                "isolation": {
                    "level": "transitional",
                    "engine": "docker",
                    "server_version": "29.4.2",
                    "rootless": False,
                    "default_runtime": "runc",
                    "network_policy": ("direct-no-secret-model-endpoint-over-bridge"),
                },
            }
        )
        self.assertFalse(rendered["isolationHidden"])
        self.assertIn("rootful", rendered["isolationCopy"])
        self.assertIn("isolation transitional", rendered["suiteMeta"])

    def test_difficulty_overview_and_filter_cover_easy_medium_hard(self) -> None:
        tasks = [
            {
                "task_id": f"00{index}-{difficulty}",
                "title": f"{difficulty.title()} Task",
                "domain": "Research",
                "difficulty": difficulty,
                "status": "completed",
                "outcome_score": score,
            }
            for index, (difficulty, score) in enumerate(
                (("easy", 1.0), ("medium", 0.5), ("hard", 0.0)),
                start=1,
            )
        ]
        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "main",
                "suite_size": 112,
                "selected_count": 3,
                "completed_count": 3,
                "tasks": tasks,
            },
            difficulty_filter="medium",
        )

        for difficulty in ("easy", "medium", "hard"):
            self.assertIn(
                f"<strong>{difficulty}</strong>", rendered["difficultyOverview"]
            )
            self.assertIn(f'value="{difficulty}"', rendered["difficultyOptions"])
        self.assertIn(
            "1 selected · 1 finished · 1 scored", rendered["difficultyOverview"]
        )
        self.assertIn("Medium Task", rendered["taskRows"])
        self.assertNotIn("Easy Task", rendered["taskRows"])
        self.assertNotIn("Hard Task", rendered["taskRows"])

    def test_difficulty_filter_composes_with_existing_ledger_filters(self) -> None:
        def task(
            task_id: str,
            title: str,
            *,
            domain: str = "Research",
            difficulty: str = "medium",
            status: str = "completed",
            review_flag: str | None = "inspect",
        ) -> dict[str, object]:
            return {
                "task_id": task_id,
                "title": title,
                "domain": domain,
                "difficulty": difficulty,
                "status": status,
                "review_flag": review_flag,
            }

        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "main",
                "suite_size": 112,
                "selected_count": 5,
                "completed_count": 4,
                "tasks": [
                    task("001-keep", "Keep"),
                    task("002-domain", "Wrong Domain", domain="Finance"),
                    task("003-difficulty", "Wrong Difficulty", difficulty="hard"),
                    task("004-status", "Wrong Status", status="running"),
                    task("005-review", "No Review", review_flag=None),
                ],
            },
            domain_filter="Research",
            difficulty_filter="medium",
            status_filter="completed",
            review_only=True,
        )

        self.assertIn(">Keep<", rendered["taskRows"])
        for excluded in (
            "Wrong Domain",
            "Wrong Difficulty",
            "Wrong Status",
            "No Review",
        ):
            self.assertNotIn(excluded, rendered["taskRows"])

    def test_group_scores_exclude_infrastructure_and_show_safety_metrics(self) -> None:
        rendered = self.run_dashboard(
            {
                "benchmark": "HarnessBench",
                "suite": "main",
                "suite_size": 112,
                "selected_count": 3,
                "completed_count": 2,
                "safety_gate_evaluated_count": 1,
                "safety_gate_failed_count": 1,
                "safety_gate_failure_rate": 1.0,
                "failed_core_total": 2,
                "tasks": [
                    {
                        "task_id": "001-scoreable",
                        "title": "Scoreable",
                        "domain": "Research",
                        "difficulty": "hard",
                        "status": "completed",
                        "outcome_score": 0.2,
                        "safety_gate_failed": True,
                        "failed_gate_count": 1,
                        "failed_core_count": 2,
                    },
                    {
                        "task_id": "002-infra",
                        "title": "Infra residue",
                        "domain": "Research",
                        "difficulty": "hard",
                        "status": "infrastructure_error",
                        "outcome_score": 1.0,
                        "safety_gate_failed": True,
                        "failed_gate_count": 9,
                        "failed_core_count": 9,
                    },
                    {
                        "task_id": "003-running",
                        "title": "Running residue",
                        "domain": "Research",
                        "difficulty": "hard",
                        "status": "running",
                        "outcome_score": 0.9,
                    },
                ],
            }
        )

        self.assertIn("<b>20.0</b>", rendered["difficultyOverview"])
        self.assertIn("1 scored · 1 gate fail", rendered["difficultyOverview"])
        self.assertNotIn("73.3", rendered["difficultyOverview"])
        self.assertEqual(rendered["safetyGateRate"], "100.0")
        self.assertEqual(
            rendered["safetyGateScope"],
            "1 / 1 scoreable · 2 core",
        )
        self.assertIn("1 GATE FAIL", rendered["taskRows"])

    def test_standalone_bundle_contains_every_file_dependency(self) -> None:
        summary = {
            "benchmark": "HarnessBench",
            "suite": "main",
            "suite_size": 112,
            "selected_count": 0,
            "completed_count": 0,
            "tasks": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "summary.json"
            output = root / "dashboard.html"
            source.write_text(json.dumps(summary), encoding="utf-8")
            subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools" / "build_standalone_dashboard.py"),
                    str(source),
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            html = output.read_text(encoding="utf-8")
        self.assertIn("window.HARNESSBENCH_SUMMARY", html)
        self.assertIn("<style>", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn('<link rel="stylesheet"', html)

    def test_standalone_bundle_rejects_both_deep_invalidation_markers(self) -> None:
        summary = {
            "benchmark": "HarnessBench",
            "suite": "main",
            "suite_size": 112,
            "selected_count": 0,
            "completed_count": 0,
            "tasks": [],
        }
        sensitive_content = (
            "https://" + "example.invalid/" + "github_" + "pat_" + "synthetic"
        )
        for marker_name in ("RUN_INVALIDATED.json", "INVALIDATED.json"):
            with self.subTest(marker_name=marker_name):
                with tempfile.TemporaryDirectory() as tmp:
                    formal = Path(tmp) / "formal"
                    merged = formal.joinpath(
                        "one", "two", "three", "four", "five", "merged"
                    )
                    merged.mkdir(parents=True)
                    source = merged / "summary.json"
                    output = merged / "dashboard.html"
                    source.write_text(json.dumps(summary), encoding="utf-8")
                    (formal / marker_name).write_text(
                        json.dumps({"reason": sensitive_content}) + "\n",
                        encoding="utf-8",
                    )
                    completed = subprocess.run(
                        [
                            "python3",
                            str(ROOT / "tools" / "build_standalone_dashboard.py"),
                            str(source),
                            str(output),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("explicitly invalidated", completed.stderr)
                    self.assertNotIn(sensitive_content, completed.stderr)
                    self.assertNotIn(str(formal), completed.stderr)
                    self.assertFalse(output.exists())

    def test_release_ui_has_no_obsolete_fixed_denominator(self) -> None:
        text = "\n".join(
            (DASHBOARD / name).read_text(encoding="utf-8")
            for name in ("index.html", "app.js")
        ).lower()
        for stale in ("formal 68", "of 68 tasks", "available at 68/68", "|| 68"):
            self.assertNotIn(stale, text)


if __name__ == "__main__":
    unittest.main()
