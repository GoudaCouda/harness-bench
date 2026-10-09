from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from harnessbench.grading.oracle_contract import (
    OracleInfrastructureError,
    STRUCTURAL_POLICY_CASE_OWNED,
    WORKSPACE_MUTATION_SCHEMA_VERSION,
    normalize_mutation_contract,
    normalize_required_artifacts,
    required_artifact_report,
    safe_score_workspace,
    workspace_manifest,
    workspace_mutation_report,
)


class OracleContractTest(unittest.TestCase):
    def test_rejects_unsafe_paths(self) -> None:
        for value in ("/tmp/result.json", "../result.json", "../../x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_required_artifacts([value])

    def test_valid_required_artifacts_preserve_score(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "result.json").write_text('{"ok": true}\n')
            result = safe_score_workspace(
                lambda _: {"outcome_score": 0.75, "checks": []},
                workspace=workspace,
                required_artifacts=["result.json"],
                task_id="test",
            )
        self.assertEqual(result["outcome_score"], 0.75)
        self.assertTrue(result["required_artifact_contract"]["complete"])

    def test_invalid_required_artifact_gates_score(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 1.0, "checks": []}

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "result.json").write_text("{not json}\n")
            result = safe_score_workspace(
                oracle,
                workspace=workspace,
                required_artifacts=["result.json"],
                task_id="test",
            )
        self.assertEqual(result["outcome_score"], 0.0)
        self.assertFalse(called)
        self.assertTrue(result["business_evaluation_skipped"])
        self.assertFalse(result.get("oracle_contract_failure", False))
        self.assertIn(
            "result.json",
            result["required_artifact_contract"]["invalid"],
        )

    def test_case_owned_missing_artifact_runs_evaluator_and_keeps_natural_score(
        self,
    ) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {
                "outcome_score": 0.65,
                "weighted_score": 0.65,
                "task_success": False,
                "checks": [],
            }

        with tempfile.TemporaryDirectory() as temporary:
            result = safe_score_workspace(
                oracle,
                workspace=Path(temporary),
                required_artifacts=["result.json"],
                task_id="test",
                require_task_success=True,
                structural_policy=STRUCTURAL_POLICY_CASE_OWNED,
            )

        self.assertTrue(called)
        self.assertEqual(result["outcome_score"], 0.65)
        self.assertEqual(result["weighted_score"], 0.65)
        self.assertFalse(result["required_artifact_contract"]["complete"])
        self.assertTrue(result["required_artifact_contract"]["safe"])
        self.assertEqual(result["failed_contract_gates"], [])

    def test_case_owned_malformed_artifact_runs_evaluator(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 0.3, "task_success": False, "checks": []}

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "result.json").write_text("{not json}\n")
            result = safe_score_workspace(
                oracle,
                workspace=workspace,
                required_artifacts=["result.json"],
                task_id="test",
                require_task_success=True,
                structural_policy=STRUCTURAL_POLICY_CASE_OWNED,
            )

        self.assertTrue(called)
        self.assertEqual(result["outcome_score"], 0.3)
        self.assertFalse(result["required_artifact_contract"]["complete"])
        self.assertTrue(result["required_artifact_contract"]["safe"])
        self.assertEqual(result["failed_contract_gates"], [])

    def test_symlink_is_not_a_required_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            target = workspace / "target.txt"
            target.write_text("content\n")
            (workspace / "result.txt").symlink_to(target)
            report = required_artifact_report(
                workspace,
                ["result.txt"],
            )
        self.assertFalse(report["complete"])
        self.assertFalse(report["safe"])
        self.assertIn("result.txt", report["invalid"])

    def test_case_owned_required_symlink_is_a_safety_gate(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 1.0, "task_success": True, "checks": []}

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "target.txt").write_text("content\n")
            (workspace / "result.txt").symlink_to(workspace / "target.txt")
            result = safe_score_workspace(
                oracle,
                workspace=workspace,
                required_artifacts=["result.txt"],
                task_id="test",
                require_task_success=True,
                structural_policy=STRUCTURAL_POLICY_CASE_OWNED,
            )

        self.assertFalse(called)
        self.assertEqual(result["outcome_score"], 0.0)
        self.assertEqual(result["failed_contract_gates"], ["required_artifact_safety"])

    def test_oracle_errors_and_nonfinite_scores_become_zero(self) -> None:
        cases = (
            lambda _: (_ for _ in ()).throw(RuntimeError("broken")),
            lambda _: {"outcome_score": math.nan},
        )
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            for oracle in cases:
                with self.subTest(oracle=oracle):
                    result = safe_score_workspace(
                        oracle,
                        workspace=workspace,
                        required_artifacts=[],
                        task_id="test",
                    )
                    self.assertEqual(result["outcome_score"], 0.0)
                    self.assertTrue(result["oracle_contract_failure"])

    def test_trusted_dependency_failure_is_explicitly_non_scoreable(self) -> None:
        def unavailable(_: Path) -> dict:
            raise OracleInfrastructureError("pinned validator unavailable")

        with tempfile.TemporaryDirectory() as temporary:
            result = safe_score_workspace(
                unavailable,
                workspace=Path(temporary),
                required_artifacts=[],
                task_id="test",
            )

        self.assertEqual(result["outcome_score"], 0.0)
        self.assertTrue(result["oracle_contract_failure"])
        self.assertTrue(result["oracle_infrastructure_failure"])

    def test_undeclared_workspace_file_is_a_zero_score_gate(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 1.0, "checks": []}

        with tempfile.TemporaryDirectory() as workspace_temporary:
            workspace = Path(workspace_temporary)
            (workspace / "source.txt").write_text("trusted\n")
            (workspace / "answer.txt").write_text("tampered\n")
            mutation = workspace_mutation_report(
                {
                    "source.txt": {
                        "kind": "file",
                        "sha256": "trusted",
                        "size": 8,
                    }
                },
                workspace_manifest(workspace),
                contract={
                    "allowed_created": [],
                    "allowed_modified": [],
                    "allowed_deleted": [],
                },
            )
            result = safe_score_workspace(
                oracle,
                workspace=workspace,
                required_artifacts=[],
                task_id="test",
                workspace_mutation=mutation,
            )

        self.assertFalse(called)
        self.assertEqual(result["outcome_score"], 0.0)
        self.assertEqual(
            result["workspace_mutation_contract"]["unexpected_created"],
            ["answer.txt"],
        )

    def test_exact_mutation_allowance_does_not_disable_other_paths(
        self,
    ) -> None:
        contract = {
            "allowed_created": ["generated.txt"],
            "allowed_modified": ["source.txt"],
            "allowed_deleted": [],
        }
        self.assertEqual(normalize_mutation_contract(contract), contract)
        with tempfile.TemporaryDirectory() as workspace_temporary:
            workspace = Path(workspace_temporary)
            (workspace / "source.txt").write_text("edited\n")
            (workspace / "generated.txt").write_text("result\n")
            mutation = workspace_mutation_report(
                {
                    "source.txt": {
                        "kind": "file",
                        "sha256": "old",
                        "size": 8,
                    }
                },
                workspace_manifest(workspace),
                contract=contract,
            )
            result = safe_score_workspace(
                lambda _: {"outcome_score": 1.0, "checks": []},
                workspace=workspace,
                required_artifacts=[],
                task_id="test",
                workspace_mutation=mutation,
            )
        self.assertEqual(result["outcome_score"], 1.0)
        self.assertTrue(result["workspace_mutation_contract"]["complete"])

    def test_mutation_contract_rejects_glob_exceptions(self) -> None:
        with self.assertRaises(ValueError):
            normalize_mutation_contract({"allowed_created": ["**/*.json"]})

    def test_workspace_mutation_contract_supports_exact_paths_and_subtrees(
        self,
    ) -> None:
        contract = {
            "allowed_created": ["report.json", "normalized/"],
            "allowed_modified": ["repo/config.json"],
            "allowed_deleted": ["scratch/draft.json"],
        }
        self.assertEqual(normalize_mutation_contract(contract), contract)
        before = {
            "repo/config.json": {"kind": "file", "sha256": "old", "size": 3},
            "scratch/draft.json": {"kind": "file", "sha256": "draft", "size": 5},
            "evidence.csv": {"kind": "file", "sha256": "same", "size": 4},
        }
        after = {
            "repo/config.json": {"kind": "file", "sha256": "new", "size": 3},
            "report.json": {"kind": "file", "sha256": "report", "size": 6},
            "normalized/a.json": {"kind": "file", "sha256": "a", "size": 1},
            "evidence.csv": {"kind": "file", "sha256": "same", "size": 4},
        }
        report = workspace_mutation_report(before, after, contract=contract)
        self.assertEqual(
            report["schema_version"],
            WORKSPACE_MUTATION_SCHEMA_VERSION,
        )
        self.assertTrue(report["complete"])
        self.assertEqual(report["created"], ["normalized/a.json", "report.json"])
        self.assertEqual(report["modified"], ["repo/config.json"])
        self.assertEqual(report["deleted"], ["scratch/draft.json"])

    def test_workspace_mutation_contract_rejects_undeclared_and_unsafe_changes(
        self,
    ) -> None:
        before = {
            "evidence.csv": {"kind": "file", "sha256": "old", "size": 3},
        }
        after = {
            "evidence.csv": {"kind": "file", "sha256": "new", "size": 3},
            "answer.txt": {"kind": "file", "sha256": "answer", "size": 6},
            "escape": {"kind": "symlink", "target": "/etc/passwd"},
        }
        report = workspace_mutation_report(
            before,
            after,
            contract={
                "allowed_created": ["answer.txt", "escape"],
                "allowed_modified": [],
                "allowed_deleted": [],
            },
        )
        self.assertFalse(report["complete"])
        self.assertEqual(report["unexpected_created"], [])
        self.assertEqual(report["unexpected_modified"], ["evidence.csv"])
        self.assertEqual(report["unsafe_entries"], ["escape"])

    def test_declared_file_implicitly_allows_created_parent_directories(self) -> None:
        before: dict[str, dict[str, object]] = {}
        after = {
            "state/": {"kind": "directory"},
            "state/results/": {"kind": "directory"},
            "state/results/report.json": {"kind": "file", "sha256": "x", "size": 1},
        }
        report = workspace_mutation_report(
            before,
            after,
            contract={
                "allowed_created": ["state/results/report.json"],
                "allowed_modified": [],
                "allowed_deleted": [],
            },
        )
        self.assertTrue(report["complete"])
        self.assertEqual(report["unexpected_created"], [])

    def test_workspace_manifest_does_not_follow_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "data.txt").write_text("trusted\n")
            (workspace / "link").symlink_to("/etc/passwd")
            manifest = workspace_manifest(workspace)
        self.assertEqual(manifest["data.txt"]["kind"], "file")
        self.assertEqual(
            manifest["link"],
            {"kind": "symlink", "target": "/etc/passwd"},
        )

    def test_workspace_manifest_ignores_tool_runtime_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            cache = workspace / ".pytest_cache" / "v" / "cache"
            cache.mkdir(parents=True)
            (cache / "nodeids").write_text("[]\n")
            bytecode = workspace / "repo" / "__pycache__"
            bytecode.mkdir(parents=True)
            (bytecode / "module.cpython-312.pyc").write_bytes(b"cache")
            (workspace / "answer.json").write_text("{}\n")
            manifest = workspace_manifest(workspace)
        self.assertEqual(set(manifest), {"answer.json", "repo/"})

    def test_undeclared_empty_directory_is_a_mutation_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            before = workspace_manifest(workspace)
            (workspace / "unlisted").mkdir()
            after = workspace_manifest(workspace)
        report = workspace_mutation_report(
            before,
            after,
            contract={
                "allowed_created": [],
                "allowed_modified": [],
                "allowed_deleted": [],
            },
        )
        self.assertFalse(report["complete"])
        self.assertTrue(report["safe"])
        self.assertEqual(report["unexpected_created"], ["unlisted/"])

    def test_case_owned_regular_extra_is_diagnostic_not_a_gate(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 1.0, "task_success": True, "checks": []}

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            before = workspace_manifest(workspace)
            (workspace / "agent_notes.txt").write_text("scratch\n")
            mutation = workspace_mutation_report(
                before,
                workspace_manifest(workspace),
                contract={
                    "allowed_created": [],
                    "allowed_modified": [],
                    "allowed_deleted": [],
                },
                protected_paths=set(before),
            )
            result = safe_score_workspace(
                oracle,
                workspace=workspace,
                required_artifacts=[],
                task_id="test",
                workspace_mutation=mutation,
                require_task_success=True,
                structural_policy=STRUCTURAL_POLICY_CASE_OWNED,
            )

        self.assertTrue(called)
        self.assertFalse(mutation["complete"])
        self.assertTrue(mutation["safe"])
        self.assertEqual(result["outcome_score"], 1.0)
        self.assertEqual(result["failed_contract_gates"], [])

    def test_case_owned_task_owned_deletion_is_natural(self) -> None:
        before = {"repo/result.py": {"kind": "file", "sha256": "old", "size": 3}}
        report = workspace_mutation_report(
            before,
            {},
            contract={
                "allowed_created": [],
                "allowed_modified": ["repo/result.py"],
                "allowed_deleted": [],
            },
            protected_paths=set(before),
        )
        self.assertFalse(report["complete"])
        self.assertTrue(report["safe"])
        self.assertEqual(report["unexpected_deleted"], ["repo/result.py"])
        self.assertEqual(report["protected_deleted"], [])

    def test_case_owned_protected_input_change_is_a_safety_gate(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 1.0, "task_success": True, "checks": []}

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            source = workspace / "source.txt"
            source.write_text("before\n")
            before = workspace_manifest(workspace)
            source.write_text("after\n")
            mutation = workspace_mutation_report(
                before,
                workspace_manifest(workspace),
                contract={
                    "allowed_created": [],
                    "allowed_modified": [],
                    "allowed_deleted": [],
                },
                protected_paths=set(before),
            )
            result = safe_score_workspace(
                oracle,
                workspace=workspace,
                required_artifacts=[],
                task_id="test",
                workspace_mutation=mutation,
                require_task_success=True,
                structural_policy=STRUCTURAL_POLICY_CASE_OWNED,
            )

        self.assertFalse(called)
        self.assertFalse(mutation["safe"])
        self.assertEqual(mutation["protected_modified"], ["source.txt"])
        self.assertEqual(result["outcome_score"], 0.0)
        self.assertEqual(result["failed_contract_gates"], ["workspace_mutation_safety"])

    def test_workspace_mutation_violation_gates_before_task_oracle(self) -> None:
        called = False

        def oracle(_: Path) -> dict:
            nonlocal called
            called = True
            return {"outcome_score": 1.0, "checks": []}

        mutation = {
            "schema_version": WORKSPACE_MUTATION_SCHEMA_VERSION,
            "enabled": True,
            "complete": False,
            "unexpected_created": ["answer.txt"],
            "unexpected_modified": [],
            "unexpected_deleted": [],
            "unsafe_entries": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            result = safe_score_workspace(
                oracle,
                workspace=Path(temporary),
                required_artifacts=[],
                task_id="test",
                workspace_mutation=mutation,
            )
        self.assertFalse(called)
        self.assertEqual(result["outcome_score"], 0.0)
        check = next(
            item
            for item in result["checks"]
            if item["id"] == "workspace_mutation_contract"
        )
        self.assertFalse(check["pass"])

    def test_mutation_contract_rejects_globs_and_parent_traversal(self) -> None:
        for value in ("repo/**", "../report.json", "/tmp/report.json"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_mutation_contract({"allowed_created": [value]})


if __name__ == "__main__":
    unittest.main()
