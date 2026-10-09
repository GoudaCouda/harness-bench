from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harnessbench.grading.oracle_contract import (
    manifest_sha256,
    workspace_manifest,
    workspace_mutation_report,
)


ROOT = Path(__file__).resolve().parents[1]
GRADING_SOURCE = ROOT / "src" / "harnessbench" / "grading"
if str(GRADING_SOURCE) not in sys.path:
    sys.path.insert(0, str(GRADING_SOURCE))


def load_grader_entrypoint():
    path = ROOT / "docker" / "grader" / "grade_entrypoint.py"
    spec = importlib.util.spec_from_file_location("grader_entrypoint_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load grader entrypoint")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GraderMutationReportTests(unittest.TestCase):
    def report_for(self, workspace: Path) -> dict[str, object]:
        manifest = workspace_manifest(workspace)
        report = workspace_mutation_report(
            {},
            manifest,
            contract={
                "allowed_created": ["result.json"],
                "allowed_modified": [],
                "allowed_deleted": [],
            },
        )
        report["final_workspace_sha256"] = manifest_sha256(manifest)
        report["final_workspace_entry_count"] = len(manifest)
        return report

    def test_accepts_matching_final_workspace_digest(self) -> None:
        grader = load_grader_entrypoint()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            control = root / "control"
            workspace.mkdir()
            control.mkdir()
            (workspace / "result.json").write_text('{"ok": true}\n')
            (control / "workspace-mutation.json").write_text(
                json.dumps(self.report_for(workspace)),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {"HARNESSBENCH_MUTATION_REPORT": "workspace-mutation.json"},
            ):
                loaded = grader.workspace_mutation(workspace, control)
        self.assertTrue(loaded["complete"])
        self.assertTrue(loaded["safe"])

    def test_rejects_inconsistent_mutation_safety_classification(self) -> None:
        grader = load_grader_entrypoint()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            control = root / "control"
            workspace.mkdir()
            control.mkdir()
            (workspace / "result.json").write_text('{"ok": true}\n')
            report = self.report_for(workspace)
            report["safe"] = False
            (control / "workspace-mutation.json").write_text(
                json.dumps(report),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(
                    os.environ,
                    {"HARNESSBENCH_MUTATION_REPORT": "workspace-mutation.json"},
                ),
                self.assertRaisesRegex(RuntimeError, "safety state"),
            ):
                grader.workspace_mutation(workspace, control)

    def test_rejects_workspace_changed_after_trusted_snapshot(self) -> None:
        grader = load_grader_entrypoint()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            control = root / "control"
            workspace.mkdir()
            control.mkdir()
            (workspace / "result.json").write_text('{"ok": true}\n')
            (control / "workspace-mutation.json").write_text(
                json.dumps(self.report_for(workspace)),
                encoding="utf-8",
            )
            (workspace / "result.json").write_text('{"ok": false}\n')
            with (
                mock.patch.dict(
                    os.environ,
                    {"HARNESSBENCH_MUTATION_REPORT": "workspace-mutation.json"},
                ),
                self.assertRaisesRegex(RuntimeError, "digest"),
            ):
                grader.workspace_mutation(workspace, control)


class GraderSemanticJudgeRequestTests(unittest.TestCase):
    def test_builds_inert_request_from_hidden_rubric_and_builder(self) -> None:
        grader = load_grader_entrypoint()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hidden = root / "hidden"
            workspace = root / "workspace"
            (hidden / "tests" / "ground_truth").mkdir(parents=True)
            workspace.mkdir()
            (workspace / "memo.txt").write_text("candidate text\n", encoding="utf-8")
            (hidden / "tests" / "ground_truth" / "semantic_judge.yaml").write_text(
                "criteria:\n"
                "- id: meaning\n"
                "  question: Is the business meaning correct?\n",
                encoding="utf-8",
            )
            (hidden / "tests" / "test_outcome.py").write_text(
                "def build_semantic_judge_input(workspace):\n"
                '    return {"valid_native_document": True, '
                '"paragraphs": [(workspace / "memo.txt").read_text()]}\n',
                encoding="utf-8",
            )
            config = {
                "rubric_file": "tests/ground_truth/semantic_judge.yaml",
                "input_builder": "tests/test_outcome.py",
                "default_model": "agent",
                "score_role": "supplemental_non_leaderboard",
            }

            def hidden_path(_variable: str, fallback: str) -> Path:
                return hidden / fallback

            with (
                mock.patch.dict(
                    os.environ,
                    {"HARNESSBENCH_SEMANTIC_JUDGE_JSON": json.dumps(config)},
                ),
                mock.patch.object(grader, "hidden_path", side_effect=hidden_path),
            ):
                request = grader.semantic_judge_request(
                    workspace,
                    task_id="004-office-docs",
                )

        self.assertEqual(request["task_id"], "004-office-docs")
        self.assertEqual(request["rubric"]["criteria"][0]["id"], "meaning")
        self.assertEqual(request["candidate"]["paragraphs"], ["candidate text\n"])
        self.assertNotIn("criterion_ids", request)


if __name__ == "__main__":
    unittest.main()
