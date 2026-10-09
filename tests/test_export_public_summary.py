from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "tools" / "export_public_summary.py"
DASHBOARD_BUILDER = ROOT / "tools" / "build_standalone_dashboard.py"


def safe_summary() -> dict[str, Any]:
    return {
        "benchmark": "HarnessBench",
        "suite": "main",
        "suite_size": 1,
        "run_id": "public-test",
        "model": "synthetic-model",
        "harness": "openclaw",
        "grading": "oracle_only",
        "selected_count": 1,
        "completed_count": 1,
        "progress": 1.0,
        "mean_oracle_completed": 0.75,
        "pass_rate_completed": 0.0,
        "strict_pass_evaluated_count": 1,
        "strict_passed_count": 0,
        "safety_gate_evaluated_count": 1,
        "safety_gate_failed_count": 0,
        "safety_gate_failure_rate": 0.0,
        "failed_gate_total": 0,
        "failed_core_total": 1,
        "headline_task_success_rate": 0.0,
        "headline_oracle_score": 0.75,
        "eta_sec": 0.0,
        "updated_epoch": 1.0,
        "counts": {
            "not_selected": 0,
            "queued": 0,
            "running": 0,
            "completed": 1,
            "protocol_error": 0,
            "model_error": 0,
            "timeout": 0,
            "infrastructure_error": 0,
        },
        "isolation": {
            "level": "transitional",
            "engine": "docker",
            "server_version": "test-version",
            "rootless": False,
            "default_runtime": "runc",
            "network_policy": "isolated-test-policy",
        },
        "tasks": [
            {
                "task_id": "001-synthetic",
                "title": "Synthetic task",
                "domain": "Research",
                "difficulty": "medium",
                "status": "completed",
                "outcome_score": 0.75,
                "task_success": False,
                "safety_gate_failed": False,
                "failed_gate_count": 0,
                "failed_core_count": 1,
                "required_artifacts": {
                    "declared": ["report.md"],
                    "present": ["report.md"],
                    "missing": [],
                    "invalid": {},
                    "completion_ratio": 1.0,
                },
                "tool_calls": 2,
                "tool_failures": 0,
                "elapsed_sec": 4.5,
                "review_flag": "",
            }
        ],
    }


def all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(all_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(all_keys(child))
    return keys


class PublicSummaryExportTests(unittest.TestCase):
    def run_export(
        self,
        source: Path,
        output: Path,
    ) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(EXPORTER), str(source), str(output)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_schema_allowlist_removes_private_fields_at_every_supported_level(
        self,
    ) -> None:
        raw = safe_summary()
        raw.update(
            {
                "base_url": "https://" + "example.invalid/private",
                "endpoint": "opaque-service",
                "source_path": "opaque-source",
                "source_shards": ["opaque-shard"],
                "result_path": "opaque-result",
                "error": "opaque-error",
            }
        )
        raw["counts"].update(  # type: ignore[union-attr]
            {"endpoint": "opaque-service", "error": "opaque-error"}
        )
        raw["isolation"].update(  # type: ignore[union-attr]
            {"endpoint": "opaque-service", "source_path": "opaque-source"}
        )
        task = raw["tasks"][0]
        task.update(
            {
                "endpoint": "opaque-service",
                "source_path": "opaque-source",
                "result_path": "opaque-result",
                "error": "opaque-error",
            }
        )
        task["required_artifacts"]["invalid"] = {  # type: ignore[index]
            "report.md": "opaque-error"
        }
        task["required_artifacts"]["endpoint"] = "opaque-service"  # type: ignore[index]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "summary.json"
            output = root / "public.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            completed = self.run_export(source, output)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            exported = json.loads(output.read_text(encoding="utf-8"))

        forbidden = {
            "base_url",
            "endpoint",
            "source_path",
            "source_shards",
            "result_path",
            "error",
            "invalid",
        }
        self.assertTrue(forbidden.isdisjoint(all_keys(exported)))
        self.assertTrue(exported["public_snapshot"])
        self.assertEqual(exported["counts"]["completed"], 1)
        self.assertEqual(exported["pass_rate_completed"], 0.0)
        self.assertEqual(exported["strict_pass_evaluated_count"], 1)
        self.assertIs(exported["tasks"][0]["task_success"], False)
        self.assertEqual(exported["safety_gate_failure_rate"], 0.0)
        self.assertEqual(exported["failed_core_total"], 1)
        self.assertEqual(exported["tasks"][0]["failed_core_count"], 1)
        self.assertEqual(
            exported["tasks"][0]["required_artifacts"],
            {
                "declared": ["report.md"],
                "present": ["report.md"],
                "missing": [],
                "completion_ratio": 1.0,
            },
        )

    def test_allowed_scalar_cannot_hide_a_nested_private_field(self) -> None:
        raw = safe_summary()
        raw["tasks"][0]["title"] = {"endpoint": "opaque-service"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "summary.json"
            output = root / "public.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            completed = self.run_export(source, output)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must be a scalar", completed.stderr)
            self.assertFalse(output.exists())

    def test_sensitive_values_are_rejected_without_echoing_them(self) -> None:
        cases = {
            "url": "https://" + "example.invalid/private",
            "private_ipv4": ".".join(("10", "23", "45", "67")),
            "private_ipv6": "fd00" + "::1234",
            "absolute_posix_path": "/" + "opt/private/model",
            "absolute_windows_path": "Z:" + "\\private\\model",
            "credential": "github_" + "pat_" + "synthetic",
        }
        for expected_label, sensitive_value in cases.items():
            with self.subTest(expected_label=expected_label):
                raw = safe_summary()
                raw["model"] = sensitive_value
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = root / "summary.json"
                    output = root / "public.json"
                    source.write_text(json.dumps(raw), encoding="utf-8")
                    completed = self.run_export(source, output)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn(expected_label, completed.stderr)
                    self.assertNotIn(sensitive_value, completed.stdout)
                    self.assertNotIn(sensitive_value, completed.stderr)
                    self.assertFalse(output.exists())

    def test_both_invalidated_markers_block_deep_ancestors_without_leaks(
        self,
    ) -> None:
        sensitive_content = (
            "https://" + "example.invalid/" + "github_" + "pat_" + "synthetic"
        )
        for marker_name in ("RUN_INVALIDATED.json", "INVALIDATED.json"):
            with self.subTest(marker_name=marker_name):
                with tempfile.TemporaryDirectory() as tmp:
                    run_root = Path(tmp) / "retired-run"
                    summary_root = run_root.joinpath(
                        "one", "two", "three", "four", "five"
                    )
                    summary_root.mkdir(parents=True)
                    (run_root / marker_name).write_text(
                        json.dumps({"reason": sensitive_content}) + "\n",
                        encoding="utf-8",
                    )
                    source = summary_root / "summary.json"
                    output = summary_root / "public.json"
                    source.write_text(
                        json.dumps(safe_summary()),
                        encoding="utf-8",
                    )
                    completed = self.run_export(source, output)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("explicitly invalidated", completed.stderr)
                    self.assertNotIn(sensitive_content, completed.stderr)
                    self.assertNotIn(str(run_root), completed.stderr)
                    self.assertFalse(output.exists())

    def test_exported_summary_builds_a_self_contained_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "summary.json"
            public = root / "public.json"
            dashboard = root / "dashboard.html"
            source.write_text(json.dumps(safe_summary()), encoding="utf-8")

            exported = self.run_export(source, public)
            self.assertEqual(exported.returncode, 0, exported.stderr)
            bundled = subprocess.run(
                [
                    sys.executable,
                    str(DASHBOARD_BUILDER),
                    str(public),
                    str(dashboard),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(bundled.returncode, 0, bundled.stderr)
            html = dashboard.read_text(encoding="utf-8")

        self.assertIn("window.HARNESSBENCH_SUMMARY", html)
        self.assertIn('"public_snapshot": true', html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn('<link rel="stylesheet"', html)


if __name__ == "__main__":
    unittest.main()
