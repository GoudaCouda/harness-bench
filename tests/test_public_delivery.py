from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
FIXTURE = ROOT / "tests" / "fixtures" / "public_delivery_summary.json"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from build_public_delivery import (  # noqa: E402
    DELIVERY_FILES,
    build_public_delivery,
    build_statistics,
    canonical_suite_identity,
    delivery_mode,
    validate_public_summary,
)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def main_suite_fixture() -> dict:
    seed = load_fixture()["tasks"][0]
    tasks = []
    for index, task_id in enumerate(
        canonical_suite_identity()["task_ids"],
        start=1,
    ):
        task = copy.deepcopy(seed)
        task["task_id"] = task_id
        task["title"] = f"Release fixture {index:03d}"
        tasks.append(task)
    suite_size = len(tasks)
    return {
        "benchmark": "HarnessBench",
        "suite": "main",
        "suite_size": suite_size,
        "run_id": "fixture-main-release",
        "model": "gemma-4-31b-it",
        "harness": "openclaw",
        "grading": "oracle_only",
        "selected_count": suite_size,
        "completed_count": suite_size,
        "progress": 1.0,
        "mean_oracle_completed": 1.0,
        "headline_oracle_score": 1.0,
        "eta_sec": 0.0,
        "updated_epoch": 1785483000.0,
        "counts": {
            "not_selected": 0,
            "queued": 0,
            "running": 0,
            "completed": suite_size,
            "protocol_error": 0,
            "model_error": 0,
            "timeout": 0,
            "infrastructure_error": 0,
        },
        "tasks": tasks,
        "public_snapshot": True,
    }


def test_public_delivery_builds_complete_consistent_bundle() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "delivery"
        result = build_public_delivery(FIXTURE, output, allow_diagnostic=True)

        assert result["task_rows"] == 6
        assert result["delivery_mode"] == "diagnostic"
        assert sorted(path.name for path in output.iterdir()) == sorted(
            (*DELIVERY_FILES, "SHA256SUMS")
        )
        statistics = json.loads(
            (output / "statistics.json").read_text(encoding="utf-8")
        )
        assert statistics["overall"] == {
            "headline_oracle_score": None,
            "headline_task_success_rate": None,
            "maximum_score": 1.0,
            "mean_score_of_scored": 0.476,
            "median_score_of_scored": 0.4,
            "minimum_score": 0.1,
            "progress": 1.0,
            "score_sum": 2.38,
            "scored_tasks": 5,
            "selected_tasks": 6,
            "strict_pass_evaluated_count": 0,
            "strict_passed_count": 0,
            "strict_pass_rate": None,
            "safety_gate_evaluated_count": 6,
            "safety_gate_failed_count": 0,
            "safety_gate_failure_rate": 0.0,
            "failed_gate_total": 0,
            "failed_core_total": 0,
            "suite_size": 6,
            "task_rows": 6,
            "terminal_tasks": 6,
            "unscored_selected_tasks": 1,
        }
        assert statistics["domain"]["Research"]["mean_score_of_scored"] == 1.0
        assert statistics["difficulty"]["hard"]["selected_task_count"] == 3
        assert statistics["status"]["timeout"]["task_count"] == 1
        assert statistics["score_bands"]["counts"] == {
            "below_0_15": 2,
            "0_15_to_below_0_40": 0,
            "0_40_to_below_0_75": 2,
            "0_75_to_1_00": 1,
            "unscored": 1,
        }
        assert statistics["review_flags"]["flagged_task_count"] == 5
        assert statistics["missing_artifacts"] == {
            "scope": "selected_tasks",
            "tasks_with_artifact_report": 6,
            "tasks_without_artifact_report": 0,
            "tasks_with_missing_artifacts": 3,
            "missing_artifact_entries": 3,
            "task_ids_with_missing_artifacts": [
                "002-finance",
                "003-operations",
                "006-hr",
            ],
        }
        public_summary = json.loads(
            (output / "summary.json").read_text(encoding="utf-8")
        )
        assert public_summary["suite"] == "diagnostic-non-leaderboard"
        assert public_summary["source_suite"] == "main"
        assert public_summary["delivery_mode"] == "diagnostic"
        assert public_summary["publication_scope"] == "diagnostic_non_leaderboard"
        assert public_summary["publication_attested"] is False
        assert public_summary["headline_oracle_score"] is None

        with (output / "task_scores.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert [row["task_id"] for row in rows] == [
            "001-research",
            "002-finance",
            "003-operations",
            "004-office",
            "005-customer",
            "006-hr",
        ]
        assert rows[1]["artifact_missing_count"] == "1"
        assert rows[3]["artifact_completion_ratio"] == "1.0"
        assert rows[5]["score_band"] == "unscored"
        assert {row["delivery_mode"] for row in rows} == {"diagnostic"}
        assert {row["publication_scope"] for row in rows} == {
            "diagnostic_non_leaderboard"
        }
        assert "out/decision.csv" not in (output / "task_scores.csv").read_text(
            encoding="utf-8"
        )

        report = (output / "SYNC_REPORT.md").read_text(encoding="utf-8")
        assert "Gemma4-31B + OpenClaw" in report
        assert "deterministic Oracle" in report
        assert "not a pure base-model score" in report
        assert "no human review or adjudication" in report
        assert "NOT LEADERBOARD ELIGIBLE" in report
        assert "Headline Oracle score | None" in report
        assert "0.3967" not in report
        dashboard = (output / "dashboard.html").read_text(encoding="utf-8")
        assert "window.HARNESSBENCH_SUMMARY" in dashboard
        assert "DIAGNOSTIC SNAPSHOT — NOT LEADERBOARD ELIGIBLE" in dashboard
        assert "diagnostic-non-leaderboard" in dashboard
        assert "<script src=" not in dashboard
        assert '<link rel="stylesheet"' not in dashboard


def test_checksum_manifest_verifies_every_delivery_file() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "delivery"
        build_public_delivery(FIXTURE, output, allow_diagnostic=True)
        lines = (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        assert [line.split("  ", 1)[1] for line in lines] == list(DELIVERY_FILES)
        for line in lines:
            expected, filename = line.split("  ", 1)
            actual = hashlib.sha256((output / filename).read_bytes()).hexdigest()
            assert actual == expected


def test_cli_output_does_not_disclose_machine_paths() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "delivery"
        completed = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "build_public_delivery.py"),
                str(FIXTURE),
                str(output),
                "--allow-diagnostic",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        assert set(payload) == {
            "delivery_mode",
            "files",
            "selected_tasks",
            "task_rows",
            "terminal_tasks",
        }
        assert str(output) not in completed.stdout
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in output.iterdir()
            if path.is_file()
        )
        for forbidden in (
            "/home/",
            "/var/tmp/",
            ".internal",
            "github_pat_",
            "http://",
            "https://",
        ):
            assert forbidden not in combined


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update({"base_url": "model-host"}), "non-public fields"),
        (
            lambda value: value["tasks"][0].update(
                {"title": "Read /home/person/private/result.txt"}
            ),
            "unsafe public values",
        ),
        (
            lambda value: value["tasks"][0]["required_artifacts"]["declared"].append(
                "/workspace/private.txt"
            ),
            "unsafe public values",
        ),
        (
            lambda value: value.update({"public_snapshot": False}),
            "public_snapshot must be true",
        ),
    ],
)
def test_public_delivery_rejects_non_public_input(mutation, message: str) -> None:
    summary = load_fixture()
    mutation(summary)
    with pytest.raises(ValueError, match=message):
        validate_public_summary(summary)


def test_public_delivery_rejects_inconsistent_aggregates_and_existing_output() -> None:
    summary = load_fixture()
    summary["selected_count"] = 5
    with pytest.raises(ValueError, match="selected_count is inconsistent"):
        validate_public_summary(summary)

    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "delivery"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with pytest.raises(ValueError, match="must not already exist"):
            build_public_delivery(FIXTURE, output)
        assert sentinel.read_text(encoding="utf-8") == "keep"


def test_infrastructure_results_are_not_counted_as_oracle_scores() -> None:
    summary = load_fixture()
    summary["tasks"][5]["status"] = "infrastructure_error"
    summary["tasks"][5]["outcome_score"] = 0.9
    summary["counts"]["model_error"] = 0
    summary["counts"]["infrastructure_error"] = 1
    summary["headline_oracle_score"] = None

    normalized = validate_public_summary(summary)
    statistics = build_statistics(normalized)
    assert statistics["overall"]["scored_tasks"] == 5
    assert statistics["overall"]["mean_score_of_scored"] == 0.476
    assert statistics["score_bands"]["counts"]["unscored"] == 1


def test_main_delivery_gate_requires_complete_current_suite() -> None:
    diagnostic = validate_public_summary(load_fixture())
    with pytest.raises(ValueError, match="canonical complete main task set"):
        delivery_mode(diagnostic, allow_diagnostic=False)
    assert delivery_mode(diagnostic, allow_diagnostic=True) == "diagnostic"

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "summary.json"
        output = root / "delivery"
        source.write_text(json.dumps(main_suite_fixture()), encoding="utf-8")
        result = build_public_delivery(source, output)
        assert result["delivery_mode"] == "main_taskset_verified"
        report = (output / "SYNC_REPORT.md").read_text(encoding="utf-8")
        assert "CANONICAL MAIN TASK-SET MATCH" in report
        assert "not by itself proof of official leaderboard" in report
        assert "NOT LEADERBOARD ELIGIBLE" not in report
        dashboard = (output / "dashboard.html").read_text(encoding="utf-8")
        assert "CANONICAL MAIN TASK-SET MATCH" in dashboard


def test_main_delivery_gate_rejects_synthetic_current_suite_ids() -> None:
    summary = main_suite_fixture()
    summary["tasks"][0]["task_id"] = "001-synthetic-impostor"
    normalized = validate_public_summary(summary)
    with pytest.raises(ValueError, match="canonical complete main task set"):
        delivery_mode(normalized, allow_diagnostic=False)


@pytest.mark.parametrize("marker_name", ["RUN_INVALIDATED.json", "INVALIDATED.json"])
def test_delivery_rejects_invalidated_source_ancestors(marker_name: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source_root = root / "formal"
        source = source_root / "public" / "summary.json"
        source.parent.mkdir(parents=True)
        source.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        (source_root / marker_name).write_text("{}\n", encoding="utf-8")

        with pytest.raises(ValueError, match="explicitly invalidated"):
            build_public_delivery(
                source,
                root / "delivery",
                allow_diagnostic=True,
            )


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "Inspect [/opt/private/result.json]",
        "Inspect,/srv/private/result.json",
        "Use model.api.internal for inference",
    ],
)
def test_sensitive_scan_catches_punctuated_paths_and_internal_dns(
    unsafe_value: str,
) -> None:
    summary = load_fixture()
    summary["tasks"][0]["title"] = unsafe_value
    with pytest.raises(ValueError, match="unsafe public values"):
        validate_public_summary(summary)


def test_sensitive_field_name_is_never_echoed() -> None:
    summary = load_fixture()
    sensitive_key = "github_pat_do_not_echo"
    summary[sensitive_key] = "not-a-real-value"
    with pytest.raises(ValueError) as raised:
        validate_public_summary(summary)
    assert sensitive_key not in str(raised.value)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value.update({"updated_epoch": float("nan")}),
            "updated_epoch must be a finite number",
        ),
        (
            lambda value: value["isolation"].update({"rootless": 0}),
            "rootless must be boolean",
        ),
        (
            lambda value: value["tasks"][0]["required_artifacts"].update(
                {
                    "declared": ["out/report.md", "out/unaccounted.md"],
                    "completion_ratio": 0.5,
                }
            ),
            "does not account for every declared artifact",
        ),
        (
            lambda value: value["tasks"][0]["required_artifacts"].update(
                {"completion_ratio": None}
            ),
            "completion_ratio is required",
        ),
    ],
)
def test_public_schema_rejects_nonfinite_and_incomplete_health(
    mutation,
    message: str,
) -> None:
    summary = load_fixture()
    mutation(summary)
    with pytest.raises(ValueError, match=message):
        validate_public_summary(summary)


def test_sync_report_escapes_markdown_and_raw_html_from_identifiers() -> None:
    summary = load_fixture()
    summary["model"] = "gemma-4-31b-it **spoof** <img alt=x>"
    summary["harness"] = "openclaw_[spoof](text)"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "summary.json"
        output = root / "delivery"
        source.write_text(json.dumps(summary), encoding="utf-8")
        build_public_delivery(source, output, allow_diagnostic=True)
        report = (output / "SYNC_REPORT.md").read_text(encoding="utf-8")

    assert "<img" not in report
    assert "&lt;img alt=x&gt;" in report
    assert r"\*\*spoof\*\*" in report
    assert r"openclaw\_\[spoof\]\(text\)" in report
