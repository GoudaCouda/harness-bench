from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from harnessbench.grading.oracle_contract import (
    ORACLE_CONTRACT_VERSION,
    WORKSPACE_MUTATION_SCHEMA_VERSION,
    manifest_sha256,
    workspace_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    path = ROOT / "tools" / "task_maintenance" / "validate_docker_grader.py"
    spec = importlib.util.spec_from_file_location("validate_docker_grader_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load validate_docker_grader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DockerGraderReferenceValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator()

    def test_trusted_report_binds_final_identity_and_safety(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "result.json").write_text('{"ok": true}\n')
            report = self.validator.trusted_reference_report(
                workspace,
                {
                    "allowed_created": ["result.json"],
                    "allowed_modified": [],
                    "allowed_deleted": [],
                },
            )
            manifest = workspace_manifest(workspace)
        self.assertEqual(
            report["schema_version"],
            WORKSPACE_MUTATION_SCHEMA_VERSION,
        )
        self.assertTrue(report["complete"])
        self.assertTrue(report["safe"])
        self.assertEqual(report["created"], [])
        self.assertEqual(report["modified"], [])
        self.assertEqual(report["deleted"], [])
        self.assertEqual(report["final_workspace_sha256"], manifest_sha256(manifest))
        self.assertEqual(report["final_workspace_entry_count"], len(manifest))

    def test_render_reference_mount_paths_canonicalizes_persisted_git_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            runtime = root / "runtime"
            workspace.mkdir()
            runtime.mkdir()
            (workspace / ".git").write_text(
                f"gitdir: {runtime}/workspace-clone/.git\n",
                encoding="utf-8",
            )
            (runtime / "config").write_text(
                f"worktree = {workspace}\nremote = {runtime}/remote.git\n",
                encoding="utf-8",
            )
            (runtime / "object.bin").write_bytes(b"\xff\x00")
            self.validator.render_reference_mount_paths(workspace, runtime)
            dotgit = (workspace / ".git").read_text(encoding="utf-8")
            config = (runtime / "config").read_text(encoding="utf-8")
        self.assertEqual(dotgit, "gitdir: /runtime/workspace-clone/.git\n")
        self.assertIn("worktree = /workspace", config)
        self.assertIn("remote = /runtime/remote.git", config)

    def test_prepare_reference_excludes_runtime_cache_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "001-test"
            seed = task_dir / "workspace" / "repo"
            cache = seed / "__pycache__"
            cache.mkdir(parents=True)
            (seed / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            (cache / "module.cpython-310.pyc").write_bytes(b"cache")
            (seed / ".DS_Store").write_bytes(b"metadata")
            (task_dir / "reference").mkdir()
            task = self.validator.TaskReference(
                task_id="001-test",
                task_dir=task_dir,
                metadata={
                    "task_id": "001-test",
                    "workspace_dir": "workspace",
                    "required_artifacts": [],
                    "mutation_contract": {
                        "allowed_created": [],
                        "allowed_modified": [],
                        "allowed_deleted": [],
                    },
                },
            )

            with self.validator.prepare_reference(task) as prepared:
                self.assertTrue((prepared.workspace / "repo" / "module.py").is_file())
                self.assertFalse((prepared.workspace / "repo" / "__pycache__").exists())
                self.assertFalse((prepared.workspace / "repo" / ".DS_Store").exists())
                self.assertTrue(
                    (prepared.hidden / "workspace/repo/module.py").is_file()
                )
                self.assertFalse(
                    (prepared.hidden / "workspace/repo/__pycache__").exists()
                )
                self.assertFalse(
                    (prepared.hidden / "workspace/repo/.DS_Store").exists()
                )

    def perfect_result(self) -> dict[str, object]:
        return {
            "task_id": "001-meeting-summary",
            "outcome_score": 1.0,
            "checks": [],
            "oracle_contract_version": ORACLE_CONTRACT_VERSION,
            "required_artifact_contract": {"complete": True},
            "workspace_mutation_contract": {
                "schema_version": WORKSPACE_MUTATION_SCHEMA_VERSION,
                "complete": True,
                "safe": True,
            },
            "grader_isolation": {
                "network": "none",
                "workspace": "read_only",
                "workspace_write_probe_blocked": True,
                "oracle_visible_to_agent": False,
            },
            "grader_runtime": {
                "python": "3.10.0",
                "git": "git version 2.39.5",
            },
        }

    def test_validate_grader_result_accepts_complete_perfect_reference(self) -> None:
        result = self.validator.validate_grader_result(
            self.perfect_result(),
            task_id="001-meeting-summary",
            minimum_score=1.0,
        )
        self.assertEqual(result["outcome_score"], 1.0)

    def test_validate_grader_result_rejects_low_score_and_bad_isolation(self) -> None:
        low_score = self.perfect_result()
        low_score["outcome_score"] = 0.9
        with self.assertRaisesRegex(ValueError, "below required"):
            self.validator.validate_grader_result(
                low_score,
                task_id="001-meeting-summary",
                minimum_score=1.0,
            )
        bad_isolation = self.perfect_result()
        bad_isolation["grader_isolation"] = {
            **bad_isolation["grader_isolation"],
            "workspace_write_probe_blocked": False,
        }
        with self.assertRaisesRegex(ValueError, "isolation"):
            self.validator.validate_grader_result(
                bad_isolation,
                task_id="001-meeting-summary",
                minimum_score=1.0,
            )

    def test_grader_command_uses_production_read_only_mount_graph(self) -> None:
        task = self.validator.TaskReference(
            task_id="001-meeting-summary",
            task_dir=Path("/suite/tasks/001-meeting-summary"),
            metadata={
                "required_artifacts": ["result.json"],
                "oracle_module": "oracle_grade.py",
            },
        )
        prepared = self.validator.PreparedReference(
            workspace=Path("/trial/workspace"),
            runtime=Path("/trial/runtime"),
            grader_control=Path("/trial/grader-control"),
            hidden=Path("/trial/hidden"),
        )
        command = self.validator.grader_command(
            task,
            prepared,
            image="harnessbench/grader:test",
        )
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("--security-opt no-new-privileges:true", joined)
        self.assertIn("--env PYTHONDONTWRITEBYTECODE=1", joined)
        self.assertIn(
            "type=bind,src=/trial/workspace,dst=/workspace,readonly",
            command,
        )
        self.assertIn(
            "type=bind,src=/trial/hidden,dst=/hidden,readonly",
            command,
        )
        self.assertEqual(command[-1], "harnessbench/grader:test")

    def test_run_one_collects_nonzero_container_exit_as_failure(self) -> None:
        task = self.validator.TaskReference(
            task_id="001-meeting-summary",
            task_dir=Path("/suite/tasks/001-meeting-summary"),
            metadata={},
        )
        prepared = self.validator.PreparedReference(
            workspace=Path("/trial/workspace"),
            runtime=Path("/trial/runtime"),
            grader_control=Path("/trial/grader-control"),
            hidden=Path("/trial/hidden"),
        )
        context = mock.MagicMock()
        context.__enter__.return_value = prepared
        context.__exit__.return_value = False
        with (
            mock.patch.object(
                self.validator,
                "prepare_reference",
                return_value=context,
            ),
            mock.patch.object(
                self.validator,
                "docker",
                return_value=SimpleNamespace(
                    returncode=17,
                    stdout="",
                    stderr="grader failed",
                ),
            ),
        ):
            row = self.validator.run_one(
                task,
                image="harnessbench/grader:test",
                timeout_sec=30,
                minimum_score=1.0,
            )
        self.assertFalse(row["pass"])
        self.assertIn("exited 17", row["error"])

    def test_inspect_image_requires_current_source_label(self) -> None:
        expected = self.validator.grader_source_sha256()
        payload = {
            "Id": "sha256:image",
            "Config": {
                "Labels": {
                    self.validator.GRADER_SOURCE_LABEL: expected,
                }
            },
        }
        with mock.patch.object(
            self.validator,
            "docker",
            return_value=SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            ),
        ):
            identity = self.validator.inspect_grader_image("grader:test")
        self.assertEqual(identity["id"], "sha256:image")
        self.assertEqual(identity["source_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
